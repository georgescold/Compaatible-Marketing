"""Wrapper Anthropic API avec support du prompt caching.

Le prompt caching est CRITIQUE pour ce projet : on injecte ~15-20k tokens de
knowledge base + avatars dans chaque appel. Sans cache, on paie ce contexte
N fois (N = nombre de tweets). Avec cache, on paie 10% après le 1er appel.

Économie typique : 90% sur l'input.
"""
from __future__ import annotations
from typing import Any, Iterable
import os
import sys
import threading
import time

from anthropic import Anthropic

from config import Config
from brain.db import get_settings


class _Heartbeat:
    """Imprime un tick sur stdout toutes les `interval` secondes tant qu'il tourne.
    Utilisé pendant les appels API longs pour montrer que le pipeline est vivant.
    """

    def __init__(self, label: str, interval: float = 5.0):
        self.label = label
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_time: float = 0.0

    def __enter__(self):
        self._start_time = time.time()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        elapsed = time.time() - self._start_time
        outcome = f"FAILED ({exc_type.__name__})" if exc_type else "done"
        print(f" {outcome} in {elapsed:.1f}s", flush=True)
        sys.stdout.flush()

    def _run(self):
        # Première impression : nom de l'opération
        sys.stdout.write(f"           ... {self.label}")
        sys.stdout.flush()
        while not self._stop.wait(self.interval):
            elapsed = time.time() - self._start_time
            sys.stdout.write(f" +{int(elapsed)}s")
            sys.stdout.flush()


def resolve_api_key() -> str | None:
    """Résout la clé API selon la même priorité que get_client() :
    1) DB Settings (saisie via l'UI), 2) variable d'env ANTHROPIC_API_KEY.
    Retourne None si aucune des deux n'est définie.
    """
    try:
        settings = get_settings()
        db_key = (settings.get("anthropic_api_key") or "").strip() or None
    except Exception:
        db_key = None
    env_key = (Config.ANTHROPIC_API_KEY_ENV or "").strip() or None
    return db_key or env_key


def is_api_key_configured() -> bool:
    """Indique si une clé API est disponible (DB ou .env). Utilisé pour activer
    les CTA UI sans risquer de bloquer un user qui n'a configuré sa clé qu'en .env.
    """
    return resolve_api_key() is not None


def get_client() -> Anthropic:
    """Construit un client Anthropic. La clé vient en priorité de la DB (Settings UI),
    puis du .env (ANTHROPIC_API_KEY). Timeout 5 min par appel pour éviter les
    requêtes qui pendent indéfiniment.
    """
    api_key = resolve_api_key()
    if not api_key:
        raise RuntimeError(
            "Clé API Anthropic absente. Configure-la dans Settings ou dans .env (ANTHROPIC_API_KEY)."
        )
    return Anthropic(api_key=api_key, timeout=300.0, max_retries=2)


def call_messages(
    model: str,
    system_blocks: list[dict[str, Any]] | str,
    messages: list[dict[str, Any]],
    max_tokens: int = 2048,
    temperature: float = 1.0,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Appelle l'API Messages.

    system_blocks : soit une string (prompt système simple), soit une liste de blocs
    structurés (pour activer le prompt caching sur certains blocs).

    Pour le caching : passer une liste de blocs, et marquer les gros blocs fixes avec
    `cache_control={"type": "ephemeral"}` :

        system_blocks = [
            {"type": "text", "text": "Tu es un copywriter Compaatible expert."},
            {"type": "text", "text": KNOWLEDGE_BASE_HUGE, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": AVATARS_INDEX, "cache_control": {"type": "ephemeral"}},
        ]

    Retourne un dict avec les champs utiles :
    {
        "text": "...",         # contenu textuel de la réponse
        "usage": {input_tokens, cached_tokens, output_tokens, cost_usd_estimate},
        "stop_reason": "...",
        "raw": <Message object original>,
    }
    """
    client = get_client()

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    # Opus 4.7 a déprécié le param temperature côté API (force la valeur par défaut).
    # Pour les autres modèles, on transmet la temperature normalement.
    if not _model_drops_temperature(model):
        kwargs["temperature"] = temperature

    if isinstance(system_blocks, str):
        kwargs["system"] = system_blocks
    else:
        kwargs["system"] = system_blocks

    # Heartbeat sur stdout pour qu'on voie que l'appel est vivant pendant les 30-180s
    # qu'il peut prendre (premier appel sans cache = input ~40k tokens).
    label = f"API {model} ({max_tokens} max_tokens)"
    with _Heartbeat(label, interval=5.0):
        response = client.messages.create(**kwargs)

    # Extraire le texte
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
    text = "\n".join(text_parts)

    # Usage + estimation coût
    usage = response.usage
    input_tokens = getattr(usage, "input_tokens", 0)
    cached_tokens = getattr(usage, "cache_read_input_tokens", 0)
    cache_creation = getattr(usage, "cache_creation_input_tokens", 0)
    output_tokens = getattr(usage, "output_tokens", 0)
    cost = estimate_cost(model, input_tokens, cached_tokens, cache_creation, output_tokens)

    total_input = cached_tokens + cache_creation + input_tokens
    hit_rate = (cached_tokens / total_input * 100.0) if total_input > 0 else 0.0
    if total_input == 0:
        cache_status = "no input"
    elif cached_tokens == 0 and cache_creation == 0:
        cache_status = "OFF (below min threshold or no breakpoint)"
    elif cached_tokens == 0:
        cache_status = "MISS (first call, writing cache)"
    else:
        cache_status = f"HIT {hit_rate:.1f}%"
    print(
        f"           cache: read={cached_tokens} write={cache_creation} fresh={input_tokens} "
        f"out={output_tokens} · {cache_status} · ~${cost:.4f}",
        flush=True,
    )

    return {
        "text": text,
        "usage": {
            "input_tokens": input_tokens,
            "cached_tokens": cached_tokens,
            "cache_creation_tokens": cache_creation,
            "output_tokens": output_tokens,
            "cost_usd_estimate": cost,
        },
        "stop_reason": response.stop_reason,
        "raw": response,
    }


# Modèles qui ne supportent plus le param `temperature` côté API (déprécié pour Opus 4.7).
# Le SDK lève BadRequestError si on l'envoie. On le drop en amont via _model_drops_temperature.
_MODELS_NO_TEMPERATURE = {
    "claude-opus-4-7",
}


def _model_drops_temperature(model: str) -> bool:
    """True si on doit retirer le param temperature avant d'appeler ce modèle."""
    if not model:
        return False
    return model in _MODELS_NO_TEMPERATURE or model.startswith("claude-opus-4-7")


# Tarifs approximatifs au moment de l'écriture (à actualiser si Anthropic change).
# Source : pricing public Anthropic. Format : USD par 1M tokens.
PRICING = {
    "claude-opus-4-7":           {"input": 5.0,  "output": 25.0, "cache_read": 0.5, "cache_write": 6.25},
    "claude-sonnet-4-6":         {"input": 3.0,  "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
    "claude-haiku-4-5-20251001": {"input": 1.0,  "output": 5.0,  "cache_read": 0.1, "cache_write": 1.25},
}


def estimate_cost(model: str, input_tokens: int, cached_read: int, cache_write: int, output_tokens: int) -> float:
    p = PRICING.get(model)
    if not p:
        return 0.0
    cost = (
        (input_tokens / 1_000_000) * p["input"]
        + (cached_read / 1_000_000) * p["cache_read"]
        + (cache_write / 1_000_000) * p["cache_write"]
        + (output_tokens / 1_000_000) * p["output"]
    )
    return round(cost, 6)


def list_available_models() -> list[dict[str, str]]:
    return Config.AVAILABLE_MODELS


def test_api_key(api_key: str) -> tuple[bool, str]:
    """Test rapide d'une clé API.

    Envoie un message minimal ('ping', max_tokens=10) à Haiku 4.5 et vérifie
    qu'on récupère une réponse 200. Coût : ~$0.00001 (négligeable).

    Retourne (ok, message).
    """
    try:
        client = Anthropic(api_key=api_key, timeout=15.0, max_retries=0)
        r = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True, "Clé API valide (ping Haiku 4.5 OK)."
    except Exception as e:
        return False, f"Clé invalide : {e}"


def mask_api_key(key: str | None, visible_prefix: int = 8, visible_suffix: int = 4) -> str:
    """Masque une clé API pour affichage : `sk-ant-a……a3f9`.

    Garde les `visible_prefix` premiers caractères et les `visible_suffix` derniers.
    Le reste devient des points de suspension.
    """
    if not key:
        return ""
    if len(key) <= visible_prefix + visible_suffix + 2:
        return key[:visible_prefix] + "…"
    return f"{key[:visible_prefix]}……{key[-visible_suffix:]}"
