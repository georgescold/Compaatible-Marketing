"""Estimation grossière du coût d'un run AVANT lancement.

Utilisé par les pages preflight (reprise / extension) pour afficher à l'user
combien va lui coûter approximativement le run complet, en fonction du modèle
sélectionné en Settings et du nombre de tweets à traiter.

Empreintes tokens : approximatives, basées sur la taille des prompts système
(copywriting/extension ~50k tokens cachés) + des messages user typiques (~2k)
+ outputs JSON typiques (~4k). Marge ~±25% sur la valeur réelle.
"""
from __future__ import annotations

from brain.llm_client import estimate_cost, PRICING


# Empreintes tokens approximatives. À recalibrer ponctuellement si les prompts
# système grossissent (typiquement +5k par injection de gros bloc).
# Mesurées sur prompts.py au 2026-05-19 (post-expansion : modes blog_pivot,
# image-thread rule, is_quote_trigger/is_clivant, T1 forms étendues).
# Pour copywriting/extension : inclut le system block COMPLET (56k mesurés)
# + le playbook+persona injectés en user-blocks cachables (~5-6k typiques).
# Les valeurs sont alignées avec les `cache write=...` observés dans les runs.
SYS_TOKENS = {
    "copywriting": 62000,   # system (~56k) + playbook+persona cached (~6k)
    "extension":   62000,   # même structure
    "analyze":      1500,   # role + brief court
    "persona":     27000,   # role + brief + avatars full
    "vision":      25000,   # role + brief produit + avatars + règles annotation
}
USER_FRESH_PER_CHUNK = 1500   # chunk de 20 tweets + instruction variable
OUTPUT_PER_CHUNK     = 4500   # JSON output (20 tweets × ~225 tokens chacun)
# Note thinking models : pour Gemini Pro/Pro-Preview, candidates_token_count
# inclut le raisonnement → l'output billing réel peut monter à 6-8k pour 20
# tweets. La constante reste sur la moyenne observée (~3500 sur runs réels) ;
# elle reste prudente sur le haut. Recalibrer si l'écart dérive.

# Empreintes par image vision : on injecte une image (~1600 tokens encodée par
# Anthropic en moyenne pour les formats web normaux 800×800-ish) + instruction
# courte (~50 tokens), et l'output JSON tient en ~600 tokens.
VISION_IMAGE_TOKENS  = 1600
VISION_USER_PER_IMG  = 80
VISION_OUTPUT_PER_IMG = 600


# Marge "retry empty-chunk" appliquee a l'estimation copywriting/extension pour
# les modeles Gemini thinking-Pro. Empirique (runs #45 et #46) : ~33% des
# chunks copywriting reviennent vides sur Pro Preview et declenchent un retry
# (cf. copywriter._process_chunk). Le retry consomme ~70% du cout d'un chunk
# normal (cache hit, output fresh seulement). Marge globale : 0.33 * 0.70 = 23%
# arrondi a 20% pour rester conservateur sans gonfler artificiellement.
# Anthropic et les modeles non-thinking (Flash/Flash-Lite) ont 0% de marge.
_RETRY_MARGIN_BY_MODEL: dict[str, float] = {
    "gemini-3.1-pro-preview": 0.20,
    "gemini-3-pro":           0.20,
    "gemini-3.1-pro":         0.20,
    "gemini-3.5-flash":       0.20,
}


def _retry_margin(model: str) -> float:
    """Marge multiplicative a appliquer au cout copywriting pour couvrir les
    retries auto sur chunks vides. 0 = pas de retry attendu."""
    return _RETRY_MARGIN_BY_MODEL.get(model, 0.0)


def estimate_pipeline_cost(
    model_adaptation: str,
    n_tweets: int,
    mode: str = "copywriting",   # 'copywriting' | 'extension' | 'fresh'
    model_analysis: str | None = None,
) -> dict:
    """Estime le coût d'un run.

    - `mode='fresh'`     : analyze + persona + copywriting (run from scratch).
                           Nécessite `model_analysis`.
    - `mode='copywriting'` : copywriting seul (resume après preview).
    - `mode='extension'` : extension (invention pure).

    Retourne un dict avec breakdown lisible par l'UI :
    - `chunks` : nb de chunks copywriting estimés (20 tweets/chunk)
    - `analyze_usd`, `persona_usd` : 0 sauf mode='fresh'
    - `copy_first_chunk_usd` : 1er chunk (cache write)
    - `copy_subsequent_chunk_usd` : chunks suivants (cache read)
    - `copy_total_usd` : total copywriting
    - `total_usd` : total final
    """
    chunks = max(1, (n_tweets + 19) // 20)
    sys_size = SYS_TOKENS["extension"] if mode == "extension" else SYS_TOKENS["copywriting"]

    # 1er chunk : on PAIE le cache write sur les blocs constants
    first_cost = estimate_cost(
        model_adaptation,
        input_tokens=USER_FRESH_PER_CHUNK,
        cached_read=0,
        cache_write=sys_size,
        output_tokens=OUTPUT_PER_CHUNK,
    )
    # Chunks suivants : cache read (~10× moins cher que fresh)
    later_cost = estimate_cost(
        model_adaptation,
        input_tokens=USER_FRESH_PER_CHUNK,
        cached_read=sys_size,
        cache_write=0,
        output_tokens=OUTPUT_PER_CHUNK,
    )
    copy_total_nominal = first_cost + max(0, chunks - 1) * later_cost
    # Marge retry pour les modeles Gemini thinking-Pro (cf. _retry_margin).
    # Appliquee uniquement sur le copywriting/extension : analyze et persona
    # n'ont pas de retry-on-empty (1-shot, parse OK suffit).
    retry_margin = _retry_margin(model_adaptation)
    retry_overhead = round(copy_total_nominal * retry_margin, 4)
    copy_total = copy_total_nominal + retry_overhead

    breakdown = {
        "mode": mode,
        "n_tweets": n_tweets,
        "chunks": chunks,
        "model_adaptation": model_adaptation,
        "model_analysis": model_analysis if mode == "fresh" else None,
        "analyze_usd": 0.0,
        "persona_usd": 0.0,
        "copy_first_chunk_usd": round(first_cost, 4),
        "copy_subsequent_chunk_usd": round(later_cost, 4),
        "copy_total_nominal_usd": round(copy_total_nominal, 4),
        "retry_margin_pct": round(retry_margin * 100, 1),
        "retry_overhead_usd": retry_overhead,
        "copy_total_usd": round(copy_total, 4),
    }

    if mode == "fresh" and model_analysis:
        # Analyze : 1 appel, ~3k system + 3k user + 3k output
        analyze_cost = estimate_cost(
            model_analysis,
            input_tokens=SYS_TOKENS["analyze"] + 3000,
            cached_read=0,
            cache_write=0,
            output_tokens=3000,
        )
        # Persona : 1 appel, ~26k system + 2k user + 2k output
        persona_cost = estimate_cost(
            model_analysis,
            input_tokens=SYS_TOKENS["persona"] + 2000,
            cached_read=0,
            cache_write=0,
            output_tokens=2000,
        )
        breakdown["analyze_usd"] = round(analyze_cost, 4)
        breakdown["persona_usd"] = round(persona_cost, 4)
        total = analyze_cost + persona_cost + copy_total
    else:
        total = copy_total

    breakdown["total_usd"] = round(total, 4)
    breakdown["pricing_available"] = model_adaptation in PRICING and (
        model_analysis is None or model_analysis in PRICING
    )
    return breakdown


def estimate_vision_batch(model: str, n_images: int) -> dict:
    """Estime le coût d'un batch d'indexation Vision.

    Premier appel : cache write des ~30k tokens système. Appels suivants :
    cache read, ce qui réduit énormément le coût input. Chaque image ajoute
    ~1.6k input fresh (l'image elle-même) + ~80 user + ~600 output.

    Retourne un breakdown lisible par l'UI.
    """
    n_images = max(1, n_images)
    sys_size = SYS_TOKENS["vision"]

    first_cost = estimate_cost(
        model,
        input_tokens=VISION_IMAGE_TOKENS + VISION_USER_PER_IMG,
        cached_read=0,
        cache_write=sys_size,
        output_tokens=VISION_OUTPUT_PER_IMG,
    )
    later_cost = estimate_cost(
        model,
        input_tokens=VISION_IMAGE_TOKENS + VISION_USER_PER_IMG,
        cached_read=sys_size,
        cache_write=0,
        output_tokens=VISION_OUTPUT_PER_IMG,
    )
    total = first_cost + max(0, n_images - 1) * later_cost

    return {
        "model": model,
        "n_images": n_images,
        "first_image_usd": round(first_cost, 4),
        "subsequent_image_usd": round(later_cost, 4),
        "total_usd": round(total, 4),
        "pricing_available": model in PRICING,
    }
