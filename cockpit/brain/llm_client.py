"""Dispatcher LLM unifié : route les appels vers Anthropic ou Gemini selon
le prefix du model id ("claude-*" → Anthropic, "gemini-*" → Google).

Permet aux call-sites (copywriter, source_analyzer, persona_generator) de
n'importer qu'un seul module et de switcher de provider transparently via le
choix du modèle dans Settings.

Signature `call_messages()` strictement compatible Anthropic : les blocs
`cache_control={"type":"ephemeral"}` sont interprétés par le client Gemini
comme des breakpoints de Context Caching équivalents.
"""
from __future__ import annotations
from typing import Any

from brain import anthropic_client, gemini_client


class UnknownProviderError(RuntimeError):
    """Levé si le model id ne matche ni 'claude-*' ni 'gemini-*'."""


class LLMQuotaExhaustedError(RuntimeError):
    """Quota journalier épuisé sur le provider (retry > 5 minutes).

    Distinct d'un 429 RPM transitoire : ici le retry est si long (souvent plusieurs
    heures) qu'il est inutile de continuer la boucle de chunks ou de chaîner une
    extension. Le pipeline doit s'arrêter proprement et le rapporter à l'user.
    """

    def __init__(self, provider: str, model: str, retry_after_seconds: int | None, quota_metric: str | None, raw_message: str):
        self.provider = provider
        self.model = model
        self.retry_after_seconds = retry_after_seconds
        self.quota_metric = quota_metric
        self.raw_message = raw_message
        if retry_after_seconds and retry_after_seconds >= 3600:
            hint = f"{retry_after_seconds // 3600}h{(retry_after_seconds % 3600) // 60:02d}"
        elif retry_after_seconds:
            hint = f"{retry_after_seconds // 60} min"
        else:
            hint = "plusieurs heures"
        scope = quota_metric or "daily quota"
        super().__init__(
            f"Quota {provider} ({model}) épuisé · {scope} · retry dans ~{hint}. "
            f"Solution : activer la facturation sur le projet GCP/Anthropic, ou attendre le reset."
        )


def provider_of(model: str) -> str:
    """Retourne 'anthropic' ou 'gemini' selon le prefix du model id."""
    if not model:
        raise UnknownProviderError("model id vide")
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith("gemini"):
        return "gemini"
    raise UnknownProviderError(f"model id inconnu : {model!r} (attendu : claude-* ou gemini-*)")


def call_messages(
    model: str,
    system_blocks: list[dict[str, Any]] | str,
    messages: list[dict[str, Any]],
    max_tokens: int = 2048,
    temperature: float = 1.0,
    use_cache: bool = True,
    thinking_budget: int | None = None,
) -> dict[str, Any]:
    """Dispatch vers le client adapté. Signature et format de retour identiques
    quel que soit le provider (cf. anthropic_client.call_messages docstring).

    `thinking_budget` : option Gemini-specifique (ignoree pour Anthropic).
    Force un budget thinking explicite en tokens. None = auto (defaut).
    """
    provider = provider_of(model)
    if provider == "anthropic":
        # Anthropic ne supporte pas thinking_budget de la meme maniere ; on l'ignore.
        return anthropic_client.call_messages(
            model=model,
            system_blocks=system_blocks,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            use_cache=use_cache,
        )
    # gemini
    return gemini_client.call_messages(
        model=model,
        system_blocks=system_blocks,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        use_cache=use_cache,
        thinking_budget=thinking_budget,
    )


def estimate_cost(model: str, input_tokens: int, cached_read: int, cache_write: int, output_tokens: int) -> float:
    """Estimation de coût unifiée."""
    try:
        provider = provider_of(model)
    except UnknownProviderError:
        return 0.0
    if provider == "anthropic":
        return anthropic_client.estimate_cost(model, input_tokens, cached_read, cache_write, output_tokens)
    return gemini_client.estimate_cost(model, input_tokens, cached_read, cache_write, output_tokens)


def is_api_key_configured(model: str | None = None) -> bool:
    """Si `model` fourni : vérifie la clé du provider de ce model.
    Si None : True si AU MOINS un provider a une clé configurée (les CTA UI génériques).
    """
    if model:
        try:
            provider = provider_of(model)
        except UnknownProviderError:
            return False
        if provider == "anthropic":
            return anthropic_client.is_api_key_configured()
        return gemini_client.is_api_key_configured()
    return anthropic_client.is_api_key_configured() or gemini_client.is_api_key_configured()


def resolve_api_key(model: str) -> str | None:
    """Résout la clé pour le provider du model donné."""
    provider = provider_of(model)
    if provider == "anthropic":
        return anthropic_client.resolve_api_key()
    return gemini_client.resolve_api_key()


# PRICING unifié pour les outils qui veulent juste check "is this model priced".
# Construit dynamiquement à l'import.
PRICING: dict[str, dict[str, float]] = {}
PRICING.update(anthropic_client.PRICING)
PRICING.update(gemini_client.PRICING)
