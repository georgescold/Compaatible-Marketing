"""Wrapper Google Gemini API avec support du Context Caching.

Pendant qu'Anthropic utilise `cache_control` inline sur les blocs, Gemini utilise
un endpoint séparé (`client.caches.create`) qui retourne un `cache_name` à
référencer dans les appels suivants. Le cache a un TTL (par défaut 1h) et est
immutable une fois créé.

Stratégie de caching pour ce projet :
- Le 1er chunk d'un run paie le cache write (~50k tokens system + 20-30k tokens
  user constants : playbook + persona).
- Les chunks suivants paient le cache read (~75% moins cher que fresh) tant que
  le TTL n'est pas écoulé (1h par défaut → couvre tous les runs typiques).

Compat API : la signature `call_messages()` reproduit celle d'`anthropic_client`
pour permettre un dispatch transparent depuis `llm_client.py`.
"""
from __future__ import annotations
from typing import Any
import hashlib
import json
import os
import sys
import threading
import time

from config import Config
from brain.db import get_settings


# Registre in-memory des caches Gemini créés pendant ce process.
# Clé = sha256 du payload cacheable (model + system + content stable).
# Valeur = (cache_name, expires_at_unix). Cache TTL Gemini par défaut = 1h.
_CACHE_REGISTRY: dict[str, tuple[str, float]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 3600  # 1h, suffisant pour un run copywriter complet

# Seuil minimum de tokens pour activer Gemini Context Caching.
# En-dessous, l'overhead de création du cache ne vaut pas le coup et certains
# modèles refusent même de cacher (cf. doc Google : minimum ~4096 tokens).
_MIN_CACHEABLE_TOKENS_APPROX = 5000  # estimation par chars/4
_CHARS_PER_TOKEN_APPROX = 4


def _detect_daily_quota_exhausted(err: Exception) -> tuple[bool, int | None, str | None]:
    """Inspecte une ClientError Gemini 429 pour déterminer si c'est un quota JOURNALIER
    (vs un 429 RPM transitoire). Retourne (is_daily, retry_after_seconds, quota_metric).

    Critères :
    - status_code 429 ET (quotaId contient 'PerDay' OU retryDelay > 300s)
    Le retryDelay vient de google.rpc.RetryInfo dans details[]. Sur quota journalier,
    Gemini renvoie typiquement 18000s+ (5h+).
    """
    status = getattr(err, "code", None) or getattr(err, "status_code", None)
    if status != 429:
        return (False, None, None)

    # google-genai stocke parfois le payload sur err.details ou err.args. On parse
    # robustement le repr() qui contient toujours la string JSON complète.
    payload: dict[str, Any] = {}
    raw = getattr(err, "details", None) or getattr(err, "_response_json", None)
    if isinstance(raw, dict):
        payload = raw
    else:
        # Fallback : extraire le JSON du str(err)
        s = str(err)
        try:
            start = s.find("{")
            end = s.rfind("}")
            if start >= 0 and end > start:
                # Le SDK utilise simple-quotes dans le repr — json.loads échoue.
                # On utilise ast.literal_eval qui accepte les dict Python.
                import ast
                payload = ast.literal_eval(s[start:end + 1])
        except Exception:
            payload = {}

    error_block = payload.get("error", payload) if isinstance(payload, dict) else {}
    details = error_block.get("details") or []

    retry_after: int | None = None
    quota_metric: str | None = None
    is_per_day = False
    for d in details if isinstance(details, list) else []:
        if not isinstance(d, dict):
            continue
        tname = d.get("@type", "")
        if tname.endswith("QuotaFailure"):
            for v in d.get("violations") or []:
                qid = (v.get("quotaId") or "")
                if "PerDay" in qid:
                    is_per_day = True
                quota_metric = quota_metric or v.get("quotaMetric") or qid
        elif tname.endswith("RetryInfo"):
            rd = d.get("retryDelay") or ""
            # Format : "19897s" ou "PT5H30M37.292S" selon les versions
            try:
                if rd.endswith("s") and not rd.startswith("PT"):
                    retry_after = int(float(rd[:-1]))
            except (ValueError, AttributeError):
                pass

    # Considérer journalier si quotaId PerDay OU retryDelay > 5min (cache TTL Claude)
    is_daily = is_per_day or (retry_after is not None and retry_after > 300)
    return (is_daily, retry_after, quota_metric)


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
        sys.stdout.write(f"           ... {self.label}")
        sys.stdout.flush()
        while not self._stop.wait(self.interval):
            elapsed = time.time() - self._start_time
            sys.stdout.write(f" +{int(elapsed)}s")
            sys.stdout.flush()


def resolve_api_key() -> str | None:
    """Résout la clé API selon la même priorité qu'anthropic_client :
    1) DB Settings (saisie via l'UI), 2) variable d'env GEMINI_API_KEY.
    """
    try:
        settings = get_settings()
        db_key = (settings.get("gemini_api_key") or "").strip() or None
    except Exception:
        db_key = None
    env_key = (Config.GEMINI_API_KEY_ENV or "").strip() or None
    return db_key or env_key


def is_api_key_configured() -> bool:
    return resolve_api_key() is not None


def get_client():
    """Construit un client Gemini. Import paresseux du SDK pour éviter de payer
    l'overhead d'import quand on n'utilise que Claude.
    """
    api_key = resolve_api_key()
    if not api_key:
        raise RuntimeError(
            "Clé API Gemini absente. Configure-la dans Settings ou dans .env (GEMINI_API_KEY)."
        )
    from google import genai
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Conversion du format Anthropic vers Gemini
# ---------------------------------------------------------------------------

def _extract_text_from_block(block: Any) -> str:
    """Récupère le texte d'un bloc, qu'il soit dict {"type":"text","text":...} ou str."""
    if isinstance(block, str):
        return block
    if isinstance(block, dict):
        return block.get("text") or ""
    return ""


def _has_cache_control(block: Any) -> bool:
    return isinstance(block, dict) and bool(block.get("cache_control"))


def _split_at_last_cache_breakpoint(blocks: list) -> tuple[list, list]:
    """Sépare une liste de blocs en (cacheable_prefix, fresh_suffix).

    Le breakpoint est le DERNIER bloc avec cache_control (inclus dans cacheable).
    Si aucun bloc n'a cache_control, tout est fresh (cacheable_prefix vide).
    """
    last_idx = -1
    for i, b in enumerate(blocks):
        if _has_cache_control(b):
            last_idx = i
    if last_idx < 0:
        return [], list(blocks)
    return list(blocks[: last_idx + 1]), list(blocks[last_idx + 1:])


def _blocks_to_text(blocks: list) -> str:
    """Concatène une liste de blocs en un seul texte (séparateurs \\n\\n)."""
    parts = [_extract_text_from_block(b) for b in blocks]
    return "\n\n".join(p for p in parts if p)


def _normalize_messages(messages: list) -> list[dict]:
    """Normalise messages Anthropic vers une liste interne {role, content_list}.
    content_list est toujours une liste de blocs dict {"type":"text","text":...}.
    """
    normalized = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content")
        if isinstance(content, str):
            blocks = [{"type": "text", "text": content}]
        elif isinstance(content, list):
            blocks = []
            for b in content:
                if isinstance(b, str):
                    blocks.append({"type": "text", "text": b})
                else:
                    blocks.append(dict(b))
        else:
            blocks = []
        normalized.append({"role": role, "content_list": blocks})
    return normalized


def _approx_token_count(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN_APPROX)


# ---------------------------------------------------------------------------
# Conversion vers le format Gemini (google-genai types)
# ---------------------------------------------------------------------------

def _gemini_role(anthropic_role: str) -> str:
    """Anthropic 'assistant' → Gemini 'model'. 'user' reste 'user'."""
    if anthropic_role == "assistant":
        return "model"
    return "user"


def _block_to_gemini_parts(block: Any) -> list:
    """Convertit un bloc Anthropic (texte ou image) en list[types.Part] Gemini.

    - Bloc texte ({"type":"text","text":...} ou str) → Part.from_text
    - Bloc image ({"type":"image","source":{"type":"base64","media_type":...,"data":...}})
      → Part.from_bytes(data=bytes, mime_type=...)

    Retourne une liste vide si le bloc est inutile (texte vide, format inconnu).
    """
    from google.genai import types
    if isinstance(block, str):
        return [types.Part.from_text(text=block)] if block else []
    if not isinstance(block, dict):
        return []
    btype = block.get("type")
    if btype == "text":
        text = block.get("text") or ""
        return [types.Part.from_text(text=text)] if text else []
    if btype == "image":
        src = block.get("source") or {}
        if src.get("type") != "base64":
            return []
        media_type = src.get("media_type") or "image/jpeg"
        b64_data = src.get("data") or ""
        if not b64_data:
            return []
        import base64 as _b64
        try:
            raw = _b64.b64decode(b64_data)
        except Exception:
            return []
        return [types.Part.from_bytes(data=raw, mime_type=media_type)]
    return []


def _build_gemini_contents(messages_normalized: list[dict]) -> list:
    """Convertit messages normalisés en list[Content] Gemini.

    Support multimodal : un message peut contenir texte + image. Les blocs image
    sont convertis en types.Part.from_bytes (le SDK Gemini accepte les images
    inline jusqu'à ~20 MB par appel).
    """
    from google.genai import types
    contents = []
    for m in messages_normalized:
        role = _gemini_role(m["role"])
        parts = []
        for block in m["content_list"]:
            parts.extend(_block_to_gemini_parts(block))
        if not parts:
            continue
        contents.append(types.Content(role=role, parts=parts))
    return contents


# ---------------------------------------------------------------------------
# Context Caching
# ---------------------------------------------------------------------------

def _compute_cache_hash(model: str, cacheable_system: str, cacheable_first_user: str) -> str:
    """Hash du payload cacheable. Inclut le model id pour ne pas réutiliser un
    cache créé pour un autre modèle (l'API Google refuserait de toute façon).
    """
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\n---SYS---\n")
    h.update(cacheable_system.encode("utf-8"))
    h.update(b"\n---USR---\n")
    h.update(cacheable_first_user.encode("utf-8"))
    return h.hexdigest()


def _get_or_create_cache(
    client,
    model: str,
    cacheable_system: str,
    cacheable_first_user: str,
) -> tuple[str, bool]:
    """Retourne (cache_name, was_created).

    Cherche un cache valide dans le registre in-memory ; en crée un si miss ou
    si expiré. Thread-safe via _CACHE_LOCK.
    """
    from google.genai import types

    key = _compute_cache_hash(model, cacheable_system, cacheable_first_user)
    now = time.time()

    with _CACHE_LOCK:
        existing = _CACHE_REGISTRY.get(key)
        if existing and existing[1] > now + 60:  # marge 1 min avant expiration
            return existing[0], False

    # Cache miss : on crée. L'appel API est hors lock pour ne pas bloquer.
    config_kwargs: dict[str, Any] = {"ttl": f"{_CACHE_TTL_SECONDS}s"}
    if cacheable_system:
        config_kwargs["system_instruction"] = cacheable_system
    if cacheable_first_user:
        config_kwargs["contents"] = [
            types.Content(role="user", parts=[types.Part.from_text(text=cacheable_first_user)])
        ]

    cache = client.caches.create(
        model=model,
        config=types.CreateCachedContentConfig(**config_kwargs),
    )
    cache_name = cache.name
    expires_at = now + _CACHE_TTL_SECONDS

    with _CACHE_LOCK:
        _CACHE_REGISTRY[key] = (cache_name, expires_at)
    return cache_name, True


# ---------------------------------------------------------------------------
# API publique : call_messages (compat anthropic_client)
# ---------------------------------------------------------------------------

def call_messages(
    model: str,
    system_blocks: list[dict[str, Any]] | str,
    messages: list[dict[str, Any]],
    max_tokens: int = 2048,
    temperature: float = 1.0,
    use_cache: bool = True,
    thinking_budget: int | None = None,
) -> dict[str, Any]:
    """Appelle l'API Gemini avec une signature compatible Anthropic.

    Retourne un dict :
    {
        "text": "...",
        "usage": {
            "input_tokens": N (fresh non cachés),
            "cached_tokens": N (lus depuis le cache),
            "cache_creation_tokens": N (écrits dans le cache, 1er appel),
            "output_tokens": N,
            "cost_usd_estimate": float,
        },
        "stop_reason": "...",
        "raw": <response>,
    }
    """
    from google.genai import types

    client = get_client()

    # 1) Normaliser le system (string ou list) → list de blocs
    if isinstance(system_blocks, str):
        sys_blocks_list = [{"type": "text", "text": system_blocks}]
    else:
        sys_blocks_list = list(system_blocks or [])

    # 2) Trouver le breakpoint cache sur les blocs system. Pour Gemini, le
    #    system_instruction est monolithique : on cache TOUT le system si UN
    #    bloc a cache_control (les blocs cachables se trouvent toujours dans
    #    le système pour ce projet).
    has_cache_marker_sys = any(_has_cache_control(b) for b in sys_blocks_list)
    full_system_text = _blocks_to_text(sys_blocks_list)

    # 3) Normaliser les messages
    msgs_norm = _normalize_messages(messages)

    # 4) Si on a un cache marker côté user (1er message), splitter sa content list
    cacheable_first_user_text = ""
    fresh_first_user_blocks: list[dict] | None = None
    if msgs_norm and msgs_norm[0]["role"] == "user":
        first = msgs_norm[0]["content_list"]
        cacheable_user, fresh_user = _split_at_last_cache_breakpoint(first)
        if cacheable_user:
            cacheable_first_user_text = _blocks_to_text(cacheable_user)
            fresh_first_user_blocks = fresh_user
        else:
            fresh_first_user_blocks = first
    elif msgs_norm:
        fresh_first_user_blocks = msgs_norm[0]["content_list"]

    # 5) Décider si on active le caching pour cet appel
    cacheable_total_chars = len(full_system_text) + len(cacheable_first_user_text)
    cacheable_tokens_est = _approx_token_count(full_system_text + cacheable_first_user_text)
    enable_cache = (
        use_cache
        and (has_cache_marker_sys or bool(cacheable_first_user_text))
        and cacheable_tokens_est >= _MIN_CACHEABLE_TOKENS_APPROX
    )

    cache_name: str | None = None
    cache_was_created = False
    if enable_cache:
        try:
            cache_name, cache_was_created = _get_or_create_cache(
                client=client,
                model=model,
                cacheable_system=full_system_text,
                cacheable_first_user=cacheable_first_user_text,
            )
        except Exception as e:
            # Cache creation échoue (modèle non supporté, payload trop court côté API…).
            # On poursuit sans cache pour ne pas casser le run.
            print(f"           gemini cache: SKIP ({type(e).__name__}: {e})", flush=True)
            enable_cache = False
            cache_name = None

    # 6) Construire les contents Gemini. Si cache actif : on N'inclut PAS le contenu cacheable
    #    dans le request (il est référencé via cached_content). On envoie uniquement le
    #    "reste" : fresh part du 1er user + tous les messages suivants.
    if enable_cache and cache_name:
        # Premier message : ne garder que la partie fresh
        rebuilt_first: dict | None = None
        if fresh_first_user_blocks:
            rebuilt_first = {"role": "user", "content_list": fresh_first_user_blocks}
        request_msgs = []
        if rebuilt_first:
            request_msgs.append(rebuilt_first)
        request_msgs.extend(msgs_norm[1:])
        contents = _build_gemini_contents(request_msgs)
        # system_instruction est dans le cache → ne pas le repasser
        system_for_request: str | None = None
    else:
        contents = _build_gemini_contents(msgs_norm)
        system_for_request = full_system_text or None

    # 7) Config Gemini
    config_kwargs: dict[str, Any] = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if cache_name:
        config_kwargs["cached_content"] = cache_name
    elif system_for_request:
        config_kwargs["system_instruction"] = system_for_request

    # Thinking budget explicite : par defaut Gemini Pro/Pro-Preview gere son
    # budget thinking automatiquement, mais sur certains chunks il s'arrete trop
    # tot et produit un JSON vide. Forcer un budget genereux pousse le modele a
    # mieux raisonner avant de produire (mais ne garantit pas un succes).
    # `thinking_budget=0` desactive completement le thinking (modeles non-Pro).
    if thinking_budget is not None:
        try:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=thinking_budget
            )
        except Exception as e:
            print(f"           gemini: thinking_config ignore ({type(e).__name__}: {e})", flush=True)

    # Structured Outputs natif : si le prompt mentionne JSON (cas 99% de notre
    # pipeline : analyze/persona/copywriter), on force Gemini à produire du JSON
    # syntaxiquement valide via response_mime_type="application/json". Sans ça,
    # Gemini produit ~30-40% de JSON cassé sur des outputs riches (constaté en
    # run réel : 2 chunks copywriter sur 3 ont échoué au parsing).
    fresh_user_text = " ".join(
        _blocks_to_text(m["content_list"])
        for m in msgs_norm
    )
    full_prompt_for_detect = (full_system_text + " " + cacheable_first_user_text + " " + fresh_user_text).lower()
    if "json" in full_prompt_for_detect:
        config_kwargs["response_mime_type"] = "application/json"

    label = f"API {model} ({max_tokens} max_tokens)"
    if cache_name:
        label += f" · cache {'CREATED' if cache_was_created else 'HIT'}"

    with _Heartbeat(label, interval=5.0):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as e:
            # Détection 429 quota journalier → on remonte une exception dédiée
            # qui sera reconnue par le pipeline (bail-out propre, pas de retry inutile).
            is_daily, retry_after, quota_metric = _detect_daily_quota_exhausted(e)
            if is_daily:
                from brain.llm_client import LLMQuotaExhaustedError
                raise LLMQuotaExhaustedError(
                    provider="gemini",
                    model=model,
                    retry_after_seconds=retry_after,
                    quota_metric=quota_metric,
                    raw_message=str(e),
                ) from e
            raise

    # 8) Extraire le texte
    text = getattr(response, "text", "") or ""

    # 9) Usage : Gemini renvoie usage_metadata avec :
    #    - prompt_token_count : total input (incl. cached + fresh)
    #    - cached_content_token_count : portion lue depuis le cache
    #    - candidates_token_count : output
    usage_meta = getattr(response, "usage_metadata", None)
    prompt_total = getattr(usage_meta, "prompt_token_count", 0) or 0
    cached_tokens = getattr(usage_meta, "cached_content_token_count", 0) or 0
    output_tokens = getattr(usage_meta, "candidates_token_count", 0) or 0
    input_fresh = max(0, prompt_total - cached_tokens)

    # cache_creation_tokens : non rapporté par Gemini sur les calls normaux.
    # On l'estime à `cacheable_tokens_est` lors du 1er appel qui a créé le cache,
    # puis 0 ensuite. Sert au coût visible (cache write).
    if cache_was_created and enable_cache:
        cache_creation_tokens = cacheable_tokens_est
    else:
        cache_creation_tokens = 0

    cost = estimate_cost(model, input_fresh, cached_tokens, cache_creation_tokens, output_tokens)

    if cache_name:
        cache_status = "CREATED" if cache_was_created else "HIT"
    elif enable_cache:
        cache_status = "FAILED"
    else:
        cache_status = "OFF (below threshold or no breakpoint)"
    print(
        f"           cache: read={cached_tokens} write={cache_creation_tokens} fresh={input_fresh} "
        f"out={output_tokens} · {cache_status} · ~${cost:.4f}",
        flush=True,
    )

    return {
        "text": text,
        "usage": {
            "input_tokens": input_fresh,
            "cached_tokens": cached_tokens,
            "cache_creation_tokens": cache_creation_tokens,
            "output_tokens": output_tokens,
            "cost_usd_estimate": cost,
        },
        "stop_reason": "stop",
        "raw": response,
    }


# ---------------------------------------------------------------------------
# Pricing & utilities
# ---------------------------------------------------------------------------

# Tarifs publics Google Cloud Gemini au moment de l'écriture (mai 2026).
# Format : USD par 1M tokens. Pour cache_read : Google facture 25% du tarif
# input sur Gemini 2.5+ ; on suppose le même ratio sur 3.x. cache_write : facturé
# au tarif input plein (pas de surcoût à la création).
PRICING = {
    "gemini-3.1-pro-preview": {"input": 2.0,  "output": 12.0, "cache_read": 0.5,  "cache_write": 2.0},
    "gemini-3-pro":           {"input": 2.0,  "output": 12.0, "cache_read": 0.5,  "cache_write": 2.0},
    "gemini-3.1-pro":         {"input": 2.0,  "output": 12.0, "cache_read": 0.5,  "cache_write": 2.0},
    "gemini-3.5-flash":       {"input": 1.5,  "output": 9.0,  "cache_read": 0.15,  "cache_write": 1.5},
    "gemini-3-flash":         {"input": 0.5,  "output": 3.0,  "cache_read": 0.125, "cache_write": 0.5},
    "gemini-3.1-flash-lite":  {"input": 0.10, "output": 0.40, "cache_read": 0.025, "cache_write": 0.10},
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


def test_api_key(api_key: str) -> tuple[bool, str]:
    """Test rapide d'une clé API Gemini.

    Envoie un message minimal ('ping', max_output_tokens=10) et vérifie qu'on
    récupère une réponse. Coût négligeable (~$0.00001).
    """
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        # gemini-3.1-pro-preview est le modèle ciblé par ce projet (id officiel mai 2026)
        r = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text="ping")])],
            config=types.GenerateContentConfig(max_output_tokens=10, temperature=0.0),
        )
        _ = getattr(r, "text", "")
        return True, "Cle API valide (ping Gemini 3.1 Pro Preview OK)."
    except Exception as e:
        return False, f"Cle invalide : {e}"


def mask_api_key(key: str | None, visible_prefix: int = 8, visible_suffix: int = 4) -> str:
    """Masque une clé API pour affichage. Réutilisable sur n'importe quel format."""
    if not key:
        return ""
    if len(key) <= visible_prefix + visible_suffix + 2:
        return key[:visible_prefix] + "…"
    return f"{key[:visible_prefix]}……{key[-visible_suffix:]}"
