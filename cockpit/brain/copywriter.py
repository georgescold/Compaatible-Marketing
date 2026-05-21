"""Stage 2 : génération des tweets Compaatible originaux à partir du playbook + persona.

Traite par chunks (~15-20 tweets sources par appel API) pour rester dans les limites de tokens
output et éviter les hallucinations sur de très longs JSON.
"""
from __future__ import annotations
import json
import re
import sys
import time
from typing import Any

from brain import prompts, llm_client, db, csv_parser
from brain.source_analyzer import parse_json_response


_MENTION_RE = re.compile(r"@[A-Za-z0-9_]{1,15}")
_URL_RE = re.compile(r"https?://\S+")


def _clean_text_segment(text: str) -> str:
    """Applique les regles typographiques a un segment hors-URL :
    collapse espaces multiples, pas d'espace avant .!?;:,
    et espace apres .!?;: si suivi d'une lettre (eviter "ça.Tu" → "ça. Tu").

    On NE TOUCHE PAS aux virgules suivies de chiffres (decimaux "9,99") ni aux
    points suivis de chiffres (versions "1.5"). Pour les autres ponctuations,
    seules `.!?;:` declenchent l'ajout d'espace en aval.
    """
    if not text:
        return text
    # Collapse multiples espaces / tabs / nbsp en un seul espace (preserve \n)
    text = re.sub(r"[ \t ]+", " ", text)
    # Pas d'espace avant la ponctuation
    text = re.sub(r" +([,.!?;:])", r"\1", text)
    # Espace apres ,.!?;: si suivi directement d'une lettre (sentence/clause
    # boundary collee par le LLM). On exige une lettre pour preserver les
    # decimaux ("9,99" reste "9,99", "1.5" reste "1.5") et les version numbers.
    text = re.sub(r"([,.!?;:])([A-Za-zÀ-ÿ])", r"\1 \2", text)
    return text


def _normalize_spacing(content: str) -> str:
    """Normalisation typographique appliquée systematiquement a chaque tweet
    avant insert DB et avant chaque édition manuelle.

    - Collapse espaces multiples → 1 espace
    - Pas d'espace avant `, . ! ? ; :`
    - Espace après `.!?;:` quand suivi d'une lettre
    - Garantit un espace entre du texte et une URL (et entre URL et texte)
      sans toucher au contenu de l'URL
    - Trim leading/trailing whitespace

    Idempotent : safe à appliquer plusieurs fois.
    """
    if not content:
        return content

    # Découpe en segments alternés (texte, url, texte, url, …)
    parts: list[tuple[str, str]] = []  # (kind, value)
    last_end = 0
    for m in _URL_RE.finditer(content):
        if m.start() > last_end:
            parts.append(("text", content[last_end:m.start()]))
        parts.append(("url", m.group(0)))
        last_end = m.end()
    if last_end < len(content):
        parts.append(("text", content[last_end:]))

    if not parts:
        return content.strip()

    # Nettoyage des segments texte (les URLs sont intouchées)
    parts = [(k, _clean_text_segment(v) if k == "text" else v) for k, v in parts]

    # Recompose en garantissant un espace au joint si les deux côtés y sont collés
    out: list[str] = []
    for i, (kind, value) in enumerate(parts):
        out.append(value)
        if i + 1 >= len(parts):
            continue
        next_kind, next_val = parts[i + 1]
        if not value or not next_val:
            continue
        last_char = value[-1]
        first_char_next = next_val[0]
        if not last_char.isspace() and not first_char_next.isspace():
            out.append(" ")

    return "".join(out).strip()


def _names_compaatible(content: str | None) -> bool:
    """True si le mot "compaatible" apparaît dans le texte HORS URL.

    Une URL `https://compaatible.com/blog/...` partagée sans nommer le produit
    dans le texte ne compte pas comme mention produit (doctrine Loys : "les
    blogs ne comptent pas" dans le ratio plafond).
    """
    if not content:
        return False
    text_no_urls = _URL_RE.sub("", content)
    return "compaatible" in text_no_urls.lower()

# Sanitizer post-LLM : tirets cadratin/en-dash (marqueurs IA) + règles globales.
# Les cadratins sont remplacés en hard (filet de sécurité). Les autres règles sont
# auditées (log uniquement) car un remplacement aveugle casserait le sens.
_EM_DASH_RE = re.compile(r"\s*—\s*")
_EN_DASH_RE = re.compile(r"\s*–\s*")
_BANNED_GLOBAL_RE = re.compile(
    r"\b(algorithmes?|scientifiquement\s+prouv[ée]e?s?|r[ée]v[ée]lations?)\b",
    re.IGNORECASE,
)

# Détection prix/tarif (audit non-bloquant). Si un tweet matche, on log un WARN.
# La règle marketing est ABSOLUE : la persona ne parle jamais argent. On ne
# remplace pas automatiquement car le contexte peut être trompeur (ex. "valoir
# le coup", "valeur", "investir dans soi") — c'est à Loys de relire les hits.
#
# Patterns couverts :
# - Symboles : € (avec ou sans chiffre adjacent)
# - Chiffres + euros : "9,99 euros", "10€", "5 euro"
# - % de réduction : "-40%", "30 %", "-50 pourcent"
# - Lexique tarif : prix, tarif, tarifaire, payant, gratuit, gratuite, gratuit·e,
#   gratuites, abonnement, abonné(e), forfait, essai gratuit, sans engagement,
#   remboursement, remboursé
_PRICE_LEAK_RE = re.compile(
    # Note : le trailing `\b` est applique UNIQUEMENT a l'alternative
    # alphabetique (`eur(?:os?)?\b`). Pour `€` (non-word char), un `\b` apres
    # ne match pas (les deux cotes sont non-word), ce qui ferait perdre la
    # capture de `9,99€` complet. Sans `\b` apres `€`, on capture l'expression
    # numerique entiere.
    r"(\b\d+[,.]?\d*\s?(?:€|eur(?:os?)?\b)|€|\b-?\d+\s?%|\b-?\d+\s?pourcent\b|"
    r"\b(?:prix|tarifs?|tarifaires?|payants?e?s?|gratuit(?:e|es|s)?|"
    r"abonnements?|abonn[ée]e?s?|forfaits?|cotisations?|remboursements?|rembours[ée]e?s?|remboursables?|"
    r"sans\s+engagement|essai\s+gratuit)\b)",
    re.IGNORECASE,
)

# Auto-corrections post-LLM : mots/expressions sûrs à remplacer mécaniquement
# (sens préservé, longueur compatible avec 280 chars dans la quasi-totalité des cas).
# Toute substitution préserve la casse de la première lettre.
# Format : (regex à matcher case-insensitive, fonction de remplacement basée sur le match)
def _preserve_case(match: "re.Match[str]", replacement: str) -> str:
    """Renvoie `replacement` avec la casse de la première lettre alignée sur le match."""
    original = match.group(0)
    if original[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


_AUTO_REPLACE_RULES: list[tuple[re.Pattern[str], str]] = [
    # "révélation/révélations" → "annonce/annonces" (terme officiel "annonce des
    # compatibilités" trop long pour un remplacement sûr ≤ 280, "annonce" suffit
    # à neutraliser le marqueur IA).
    (re.compile(r"\br[ée]v[ée]lations\b", re.IGNORECASE), "annonces"),
    (re.compile(r"\br[ée]v[ée]lation\b", re.IGNORECASE), "annonce"),
    # "algorithme/algorithmes" → "méthode/méthodes" (équivalent sémantique, même
    # longueur ou plus court, sans risque de casser une phrase).
    (re.compile(r"\balgorithmes\b", re.IGNORECASE), "méthodes"),
    (re.compile(r"\balgorithme\b", re.IGNORECASE), "méthode"),
]

# Séparateurs préférés pour les coupures de thread, par ordre décroissant de qualité.
# On préfère couper à une fin de phrase, puis à une clause, puis (dernier recours) à un espace.
_SPLIT_SEPARATORS = [". ", "! ", "? ", "\n\n", "\n", ". \"", " — ", " - ", " : ", "; ", ", ", " "]


def _is_inside_url(text: str, pos: int) -> bool:
    """True si la position `pos` tombe à l'intérieur d'une URL (pour éviter de la couper)."""
    for m in _URL_RE.finditer(text):
        if m.start() <= pos < m.end():
            return True
    return False


def _find_split_point(text: str, max_len: int) -> int:
    """Cherche une bonne position de coupure ≤ max_len.

    Stratégie : balayer les séparateurs préférés dans une fenêtre [max_len - 100 : max_len],
    prendre le plus à droite qui respecte max_len. Ne jamais couper à l'intérieur d'une URL.
    Dernier recours : coupure à un espace ; si rien ne marche, coupure dure (très rare).
    """
    if len(text) <= max_len:
        return len(text)

    window_lo = max(0, max_len - 100)
    # Fenêtre des positions valides pour un séparateur
    for sep in _SPLIT_SEPARATORS:
        idx = text.rfind(sep, window_lo, max_len)
        if idx < 0:
            continue
        # Position de coupe = juste après le séparateur (qu'on garde dans la partie gauche)
        cut = idx + len(sep)
        # Sauf si on tombe dans une URL : on continue à chercher
        if _is_inside_url(text, cut - 1) or _is_inside_url(text, cut):
            continue
        return cut

    # Dernier recours : couper à un espace dans la fenêtre
    space = text.rfind(" ", window_lo, max_len)
    if space > 0 and not _is_inside_url(text, space):
        return space + 1
    # Vraiment rien : coupe dure (édge case, ne devrait pas arriver avec du texte normal)
    return max_len


_MIN_ORPHAN_LEN = 50  # seuil sous lequel un fragment de fin est considéré orphelin


def _truncate_to_sentence_boundary(text: str, max_len: int) -> str | None:
    """Tronque `text` à la dernière frontière propre (phrase > clause > espace)
    qui reste ≤ max_len. Retourne None s'il n'y a aucune frontière acceptable.

    Utilisé en fallback quand on préfère raccourcir le tweet plutôt que de
    créer un orphelin moche.
    """
    text = text.strip()
    if len(text) <= max_len:
        return text
    cut = _find_split_point(text, max_len)
    if cut <= 0 or cut > max_len:
        return None
    truncated = text[:cut].rstrip()
    # On enlève la ponctuation orpheline en fin de troncation
    truncated = truncated.rstrip(" ,;:")
    if not truncated or len(truncated) < 40:
        return None
    return truncated


def _rebalance_last_two(combined: str, max_len: int) -> list[str] | None:
    """Re-splitte un texte en 2 parties équilibrées (chacune ≥ ~50 chars, ≤ max_len).

    Cherche un séparateur de phrase/clause/espace le plus proche du MILIEU plutôt
    que de la fin, pour éviter un fragment orphelin. Retourne [left, right] si une
    coupure équilibrée existe, None sinon.
    """
    n = len(combined)
    if n <= max_len:
        return [combined]
    target = n // 2
    lo = max(_MIN_ORPHAN_LEN, target - 90)
    hi = min(max_len, target + 90)
    if hi <= lo:
        return None

    best_cut: int | None = None
    best_dist = 10**9
    for sep in _SPLIT_SEPARATORS:
        start = lo
        while True:
            idx = combined.find(sep, start, hi)
            if idx < 0:
                break
            cut = idx + len(sep)
            if not (_is_inside_url(combined, cut - 1) or _is_inside_url(combined, cut)):
                left_len = len(combined[:cut].rstrip())
                right_len = len(combined[cut:].lstrip())
                if left_len <= max_len and right_len <= max_len \
                   and left_len >= _MIN_ORPHAN_LEN and right_len >= _MIN_ORPHAN_LEN:
                    dist = abs(cut - target)
                    if dist < best_dist:
                        best_cut = cut
                        best_dist = dist
            start = idx + 1
        if best_cut is not None:
            break  # séparateur de meilleure préférence trouvé, suffisant

    if best_cut is None:
        return None
    left = combined[:best_cut].rstrip()
    right = combined[best_cut:].lstrip()
    return [left, right]


# Détection d'énumération inline numérotée : "1. ... 2. ... 3. ..." ou "1) ... 2) ...".
# Doctrine Loys (2026-05-21) : une énumération dans un thread doit avoir UN tweet
# par item, jamais tous les items entassés dans un seul post. Le LLM produit
# parfois la version inline malgré le prompt → on auto-splitte au moment d'insérer.
_ENUM_ITEM_RE = re.compile(r"(?:(?<=^)|(?<=[\s.,!?:]))(\d{1,2})[\.\)]\s+")
_ENUM_PREAMBLE_MIN_LEN = 20  # préambule plus court → on l'attache au premier item


def _split_enumeration(content: str) -> list[str] | None:
    """Détecte une énumération inline numérotée (1. … 2. … 3. …) et la découpe
    en un item par tweet.

    Conditions de déclenchement :
    - ≥ 2 items détectés
    - les numéros forment une séquence stricte commençant à 1 (1, 2, 3, …)
    - chaque numéro est précédé d'un début de chaîne, d'un espace, ou d'une
      ponctuation de fin de phrase (évite "1.5" ou "il y a 7. raisons")

    Retourne :
    - None si pas d'énumération valide
    - Liste de strings sinon. Le préambule éventuel (texte avant "1.") devient
      son propre tweet s'il fait ≥ 20 chars ; sinon il est collé au premier item.
    """
    if not content:
        return None
    matches = list(_ENUM_ITEM_RE.finditer(content))
    if len(matches) < 2:
        return None
    nums = [int(m.group(1)) for m in matches]
    if nums[0] != 1:
        return None
    for i in range(1, len(nums)):
        if nums[i] != nums[i - 1] + 1:
            return None

    items: list[str] = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        items.append(content[start:end].strip())

    preamble = content[: matches[0].start()].strip()
    if preamble:
        if len(preamble) >= _ENUM_PREAMBLE_MIN_LEN:
            return [preamble, *items]
        items[0] = f"{preamble} {items[0]}".strip()
    return items


def _split_into_thread(content: str, max_len: int = 280) -> list[str]:
    """Découpe intelligente d'un contenu trop long.

    Stratégie en cascade, dans l'ordre de préférence :

    1. **Tient en un tweet** (≤ max_len) → renvoyé tel quel.
    2. **Overflow modeste** (≤ 50 chars de trop) et truncation propre qui garde
       ≥ 80 % du contenu → on TRONQUE à la dernière frontière de phrase. Préféré
       à un split qui créerait un orphelin de 8 chars.
    3. **Split avec rebalance** : on découpe greedy à droite, puis si le dernier
       fragment est < 50 chars, on re-splitte les deux dernières parties autour
       du milieu pour qu'aucune ne reste orpheline.
    4. **Rebalance impossible** : si même rééquilibrage échoue, on TRONQUE la
       dernière partie à la frontière propre la plus proche ≤ max_len et on
       droppe l'orphelin. Mieux un thread net qu'un thread bancal.

    Préserve les URLs (jamais coupées au milieu).
    """
    content = content.strip()
    if len(content) <= max_len:
        return [content]

    overflow = len(content) - max_len

    # (2) Overflow modeste : truncation préférée si on garde l'essentiel
    if overflow <= 50:
        truncated = _truncate_to_sentence_boundary(content, max_len)
        if truncated and len(truncated) >= int(len(content) * 0.80):
            return [truncated]

    # (3) Split classique
    parts: list[str] = []
    remaining = content
    safety_iters = 0
    while len(remaining) > max_len and safety_iters < 50:
        safety_iters += 1
        cut = _find_split_point(remaining, max_len)
        left = remaining[:cut].rstrip()
        right = remaining[cut:].lstrip()
        if not left or left == remaining:
            left = remaining[:max_len]
            right = remaining[max_len:].lstrip()
        parts.append(left)
        remaining = right
    if remaining:
        parts.append(remaining)

    # Anti-orphelin : si le dernier fragment est trop court
    if len(parts) >= 2 and len(parts[-1]) < _MIN_ORPHAN_LEN:
        combined = (parts[-2] + " " + parts[-1]).strip()
        rebalanced = _rebalance_last_two(combined, max_len)
        if rebalanced and len(rebalanced) == 2:
            parts[-2:] = rebalanced
        else:
            # (4) Rebalance impossible → on tronque proprement la fin
            truncated = _truncate_to_sentence_boundary(combined, max_len)
            if truncated:
                parts[-2:] = [truncated]
            else:
                # Aucune frontière propre : on droppe juste l'orphelin
                parts.pop()

    return parts


_BLOG_URL_RE = re.compile(r"https?://(?:www\.)?compaatible\.com/blog/([A-Za-z0-9_-]+)")


def _validate_and_clean_blog_urls(content: str, valid_slugs: set[str]) -> tuple[str, int]:
    """Vérifie que toutes les URLs `compaatible.com/blog/{slug}` du contenu utilisent un slug
    valide. Si un slug est inventé/inexistant, on retire l'URL et on nettoie autour.

    Retourne (content_corrigé, nb_urls_invalides_retirées).

    Stratégie de nettoyage en cas d'URL invalide : on retire l'URL ET on enlève la phrase
    courte qui l'introduisait si elle se termine par cette URL (genre "à lire ici : <url>").
    """
    invalid_count = 0

    def replace(match: re.Match) -> str:
        nonlocal invalid_count
        slug = match.group(1)
        if slug in valid_slugs:
            return match.group(0)  # URL valide, on garde
        invalid_count += 1
        return ""  # URL invalide : on la retire

    cleaned = _BLOG_URL_RE.sub(replace, content)
    if invalid_count == 0:
        return content, 0

    # Nettoyage typo : espaces multiples, espaces avant ponctuation, ponctuation orpheline
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = cleaned.strip(" ,;:")
    return cleaned, invalid_count


def _sanitize_dashes(content: str) -> tuple[str, int]:
    """Remplace les tirets cadratin (—) et en-dash (–), marqueurs IA reconnaissables.

    Stratégie : `—` → `, ` (pause équivalente, sens préservé dans 95% des cas),
    `–` → `-`. Évite ensuite les virgules doubles et collapse les espaces.
    Retourne (texte nettoyé, nb_remplacements).
    """
    if not content:
        return content, 0
    em = len(_EM_DASH_RE.findall(content))
    en = len(_EN_DASH_RE.findall(content))
    if em == 0 and en == 0:
        return content, 0
    out = _EM_DASH_RE.sub(", ", content)
    out = _EN_DASH_RE.sub("-", out)
    # Collapse virgules doubles, espaces multiples, espaces avant ponctuation
    out = re.sub(r",\s*,", ",", out)
    out = re.sub(r"\s+", " ", out)
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    return out.strip(), em + en


def _auto_replace_banned(content: str) -> tuple[str, list[str]]:
    """Applique les substitutions automatiques sûres définies dans _AUTO_REPLACE_RULES.

    Retourne (texte corrigé, liste des mots remplacés tels qu'apparus dans le texte).
    Préserve la casse de la première lettre. Idempotent.
    """
    if not content:
        return content, []
    replaced: list[str] = []
    out = content
    for pattern, replacement in _AUTO_REPLACE_RULES:
        def sub(m: "re.Match[str]") -> str:
            replaced.append(m.group(0))
            return _preserve_case(m, replacement)
        out = pattern.sub(sub, out)
    return out, replaced


def _audit_banned_terms(content: str, vocabulary_no: list[str] | None) -> dict[str, list[str]]:
    """Détecte (sans remplacer) les violations des règles d'écriture globales et
    du vocabulary_no propre à la persona. Log uniquement : un remplacement
    aveugle (ex. "algorithme" → "méthode") casserait souvent le sens.
    """
    hits = {"global": [], "vocab_no": [], "price": []}
    if not content:
        return hits
    hits["global"] = [m.group(0) for m in _BANNED_GLOBAL_RE.finditer(content)]
    hits["price"] = [m.group(0) for m in _PRICE_LEAK_RE.finditer(content)]
    if vocabulary_no:
        for word in vocabulary_no:
            if not word or len(word.strip()) < 3:
                continue
            if re.search(rf"\b{re.escape(word.strip())}\b", content, re.IGNORECASE):
                hits["vocab_no"].append(word.strip())
    return hits


def _strip_mentions(content: str) -> str:
    """Retire toutes les @mentions du contenu et nettoie les espaces/ponctuation orphelins.

    Filet de sécurité : la règle "aucune @mention" est imposée par le prompt système ;
    cette fonction s'occupe des rares cas où l'IA en laisse passer une malgré tout.
    Préserve le sens du tweet en collapsant les espaces et en virant les espaces avant
    ponctuation.
    """
    if not content:
        return content
    out = _MENTION_RE.sub("", content)
    # Collapse espaces multiples
    out = re.sub(r"\s+", " ", out)
    # Espace avant ponctuation
    out = re.sub(r"\s+([,.!?;:])", r"\1", out)
    # Ponctuation orpheline en fin
    out = out.strip(" ,;:")
    return out


CHUNK_SIZE = 20  # nombre de tweets sources par appel API

# Marge appliquee en extension : `count` represente des POSTS atomiques (un
# thread = 1 post, un tweet isole = 1 post). Le modele genere ~1.4 tweets par
# post en moyenne (observation runs reels). On pre-alloue ce ratio en chunks ;
# si on est encore sous la cible apres tous les chunks, on en lance jusqu'a
# MAX_EXTRA_EXTENSION_CHUNKS supplementaires pour atteindre la cible.
POSTS_TO_MESSAGES_OVERSHOOT = 1.5
EXTRA_EXTENSION_CHUNK_SIZE = 10
MAX_EXTRA_EXTENSION_CHUNKS = 5


def _log(msg: str) -> None:
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [copy]   {msg}", flush=True)
    sys.stdout.flush()


def generate_corpus(
    parsed_csv: dict[str, Any],
    playbook: dict,
    persona: dict,
    model: str,
    csv_run_id: int,
    persona_id: int,
    max_source_tweets: int | None = None,
    progress_run_id: int | None = None,
    start_chunk_idx: int = 0,
) -> dict[str, Any]:
    """Génère un corpus complet de tweets Compaatible.

    max_source_tweets : si fourni, limite la taille du source utilisé (utile pour preview rapide).
    progress_run_id : si fourni, pousse l'avancement vers run_state pour l'UI.
    start_chunk_idx : 0 = run normal. > 0 = reprise après pause, on saute les chunks
    déjà traités (leurs tweets sont déjà en DB grâce à l'insertion incrémentale).

    Insère les tweets DB chunk par chunk pour permettre une pause propre sans perdre
    le travail déjà fait. Si run_state.is_pause_requested(progress_run_id) est vrai
    entre deux chunks, sort proprement avec un dict {paused: True, next_chunk_idx}.
    """
    from brain import run_state

    rows = parsed_csv["rows"]
    content_col = parsed_csv["content_column"]

    # Prioriser les top tweets pour le traitement (les moins engageants apportent peu)
    sorted_rows = csv_parser.top_n_by_engagement(rows, n=len(rows))
    if max_source_tweets:
        sorted_rows = sorted_rows[:max_source_tweets]

    total_usage = {"input_tokens": 0, "cached_tokens": 0, "cache_creation_tokens": 0, "output_tokens": 0, "cost_usd_estimate": 0.0}

    chunks = [sorted_rows[i : i + CHUNK_SIZE] for i in range(0, len(sorted_rows), CHUNK_SIZE)]
    total_chunks = len(chunks)
    _log(f"{len(sorted_rows)} tweets sources a traiter en {total_chunks} chunks de {CHUNK_SIZE}"
         + (f" · reprise depuis chunk {start_chunk_idx+1}" if start_chunk_idx else ""))

    if progress_run_id is not None:
        msg_start = (
            f"{len(sorted_rows)} tweets en {total_chunks} chunks · "
            + (f"reprise au chunk {start_chunk_idx+1}/{total_chunks}" if start_chunk_idx else "démarrage")
        )
        run_state.update_message(progress_run_id, msg_start, stage_key="copy")

    inserted_total = 0
    failed_chunks = 0

    for chunk_idx in range(start_chunk_idx, total_chunks):
        # Check pause avant chaque chunk (sauf le premier traité après start, qui est l'avant-dernier point de sortie)
        if progress_run_id is not None and run_state.is_pause_requested(progress_run_id):
            _log(f"pause demandee · sortie propre avant chunk {chunk_idx+1}/{total_chunks}")
            return {
                "tweets_inserted": inserted_total,
                "chunks_processed": chunk_idx,
                "usage": total_usage,
                "paused": True,
                "next_chunk_idx": chunk_idx,
                "total_chunks": total_chunks,
            }

        chunk = chunks[chunk_idx]
        human_idx = chunk_idx + 1  # 1-based pour l'UI
        t0 = time.time()
        _log(f"chunk {human_idx}/{total_chunks} ({len(chunk)} tweets) · appel API...")
        if progress_run_id is not None:
            run_state.update_message(progress_run_id, f"Chunk {human_idx}/{total_chunks} · appel API en cours sur {len(chunk)} tweets...", stage_key="copy")
        try:
            chunk_tweets = _process_chunk(chunk, content_col, playbook, persona, model, human_idx, total_chunks)
        except llm_client.LLMQuotaExhaustedError as e:
            # Quota journalier : inutile de continuer, tous les chunks suivants
            # vont taper le même mur. On bail-out avec ce qu'on a déjà inséré.
            _log(f"chunk {human_idx}/{total_chunks} QUOTA · {e} · arret immediat de la boucle")
            if progress_run_id is not None:
                run_state.update_message(progress_run_id, f"Quota épuisé au chunk {human_idx}/{total_chunks} · {inserted_total} tweet(s) sauvegardé(s)", stage_key="copy")
            return {
                "tweets_inserted": inserted_total,
                "chunks_processed": chunk_idx,
                "usage": total_usage,
                "paused": False,
                "quota_exhausted": True,
                "quota_error": str(e),
            }
        except Exception as e:
            failed_chunks += 1
            _log(f"chunk {human_idx}/{total_chunks} ECHEC ({type(e).__name__}: {e}) · skip et continue")
            if progress_run_id is not None:
                run_state.update_message(progress_run_id, f"Chunk {human_idx}/{total_chunks} échoué · skip et continue ({failed_chunks} chunk(s) perdu(s))", stage_key="copy")
            continue
        for k, v in chunk_tweets["usage"].items():
            total_usage[k] += v
        # Insert ce chunk en DB tout de suite (savepoint en cas de pause/crash)
        n_ins = _insert_tweets_batch(chunk_tweets["tweets"], csv_run_id, persona_id)
        inserted_total += n_ins
        _log(f"chunk {human_idx}/{total_chunks} OK · {len(chunk_tweets['tweets'])} tweets · {n_ins} inseres · {chunk_tweets['usage']['cached_tokens']} cached/{chunk_tweets['usage']['input_tokens']} in tokens · ${chunk_tweets['usage']['cost_usd_estimate']:.4f} ({time.time()-t0:.1f}s)")
        if progress_run_id is not None:
            run_state.update_message(progress_run_id, f"Chunk {human_idx}/{total_chunks} OK · {len(chunk_tweets['tweets'])} tweets ({time.time()-t0:.1f}s)", stage_key="copy")

    return {
        "tweets_inserted": inserted_total,
        "chunks_processed": total_chunks,
        "usage": total_usage,
        "paused": False,
    }


def generate_extension(
    playbook: dict,
    persona: dict,
    count: int,
    existing_sample: list[str],
    model: str,
    csv_run_id: int,
    persona_id: int,
    progress_run_id: int | None = None,
    start_chunk_idx: int = 0,
    extension_idx: int | None = None,
    mention_stats: dict | None = None,
    style_stats: dict | None = None,
    start_extra_done: int = 0,
) -> dict[str, Any]:
    """Génère `count` POSTS ATOMIQUES ORIGINAUX dans la voix de la persona.

    Sémantique de `count` (décision Loys 2026-05-18) : 1 thread = 1 post, 1
    tweet isolé = 1 post. Cible exprimée en POSTS, pas en messages individuels.
    Le modèle reçoit une consigne de ~`count * 1.5` messages (marge pour les
    threads). Après tous les chunks, si on est sous la cible, on lance jusqu'à
    MAX_EXTRA_EXTENSION_CHUNKS chunks supplémentaires pour atteindre `count`.

    existing_sample : échantillon des tweets déjà produits, sert de calibre de voix.
    Insère par chunk pour permettre la pause. Check is_pause_requested entre chunks.
    """
    import math
    from brain import run_state

    total_usage = {"input_tokens": 0, "cached_tokens": 0, "cache_creation_tokens": 0, "output_tokens": 0, "cost_usd_estimate": 0.0}

    # `count` est la cible POSTS atomiques. On pré-alloue des chunks pour
    # générer ~count * 1.5 messages (marge threading), puis on ajuste si besoin.
    target_posts = count
    target_messages = max(CHUNK_SIZE, math.ceil(target_posts * POSTS_TO_MESSAGES_OVERSHOOT))

    # Chunks (max 20 tweets par appel, comme generate_corpus)
    chunks_sizes: list[int] = []
    remaining = target_messages
    while remaining > 0:
        s = min(CHUNK_SIZE, remaining)
        chunks_sizes.append(s)
        remaining -= s
    total_chunks = len(chunks_sizes)

    _log(
        f"extension · {target_posts} posts cibles (~{target_messages} messages, "
        f"marge threading +{int((POSTS_TO_MESSAGES_OVERSHOOT-1)*100)}%) en "
        f"{total_chunks} chunks ({chunks_sizes})"
        + (f" · reprise depuis chunk {start_chunk_idx+1}" if start_chunk_idx else "")
    )
    if progress_run_id is not None:
        msg = (
            f"Extension · {target_posts} posts en {total_chunks} chunks · "
            + (f"reprise au chunk {start_chunk_idx+1}/{total_chunks}" if start_chunk_idx else "démarrage")
        )
        run_state.update_message(progress_run_id, msg, stage_key="copy")

    # Reconstituer le contexte "tweets déjà générés dans ce run" depuis la DB
    # (utile en reprise pour que la voix reste cohérente).
    already_generated: list[dict] = []
    if start_chunk_idx > 0:
        with db.cursor() as cur:
            cur.execute(
                "SELECT content FROM mkt_tweets WHERE csv_run_id = %s "
                "ORDER BY id DESC LIMIT 30",
                (csv_run_id,),
            )
            already_generated = [{"content": r["content"]} for r in cur.fetchall()][::-1]

    inserted_total = 0
    failed_chunks_ext = 0

    # Budget mentions Compaatible au niveau du RUN d'extension entier (pas par chunk).
    # Sans ça, chaque chunk peut taper son plafond et le ratio global dérive (analyse
    # run 56 Thaïs : cible 14% par chunk → ratio global observé 23%). On calcule la
    # cible totale ici, et avant chaque chunk on recompute le budget restant à partir
    # de ce qui a déjà été mentionné. Si on est en avance, le chunk suivant baisse
    # son plafond. Cible totale = target_messages * target_ratio observé.
    extension_mention_target_total: int | None = None
    if mention_stats and mention_stats.get("ratio") is not None:
        extension_mention_target_total = max(0, round(target_messages * mention_stats["ratio"]))
        _log(
            f"extension · budget mentions Compaatible · cible globale {extension_mention_target_total} "
            f"sur ~{target_messages} messages (ratio cible {mention_stats['ratio']*100:.1f}% des originaux)"
        )

    for chunk_idx in range(start_chunk_idx, total_chunks):
        if progress_run_id is not None and run_state.is_pause_requested(progress_run_id):
            _log(f"pause demandee · sortie propre avant chunk extension {chunk_idx+1}/{total_chunks}")
            return {
                "tweets_inserted": inserted_total,
                "chunks_processed": chunk_idx,
                "usage": total_usage,
                "paused": True,
                "next_chunk_idx": chunk_idx,
                "total_chunks": total_chunks,
            }

        chunk_count = chunks_sizes[chunk_idx]
        human_idx = chunk_idx + 1
        t0 = time.time()

        # Budget restant pour ce chunk (run-level cap, pas per-chunk)
        remaining_budget: int | None = None
        if extension_mention_target_total is not None:
            mentions_so_far = _count_extension_mentions_so_far(csv_run_id, extension_idx)
            remaining_budget = max(0, extension_mention_target_total - mentions_so_far)
            _log(
                f"extension chunk {human_idx}/{total_chunks} · budget mentions restant : "
                f"{remaining_budget} (déjà mentionné : {mentions_so_far}/{extension_mention_target_total})"
            )

        _log(f"extension chunk {human_idx}/{total_chunks} ({chunk_count} tweets) · appel API...")
        if progress_run_id is not None:
            run_state.update_message(progress_run_id, f"Chunk {human_idx}/{total_chunks} · génération de {chunk_count} tweets originaux...", stage_key="copy")
        try:
            chunk_tweets = _process_extension_chunk(
                chunk_count, playbook, persona, existing_sample, model, human_idx, total_chunks,
                already_generated=already_generated,
                mention_stats=mention_stats,
                style_stats=style_stats,
                remaining_mention_budget=remaining_budget,
                target_messages_total=target_messages,
            )
        except llm_client.LLMQuotaExhaustedError as e:
            _log(f"extension chunk {human_idx}/{total_chunks} QUOTA · {e} · arret immediat de la boucle")
            if progress_run_id is not None:
                run_state.update_message(progress_run_id, f"Quota épuisé au chunk extension {human_idx}/{total_chunks} · {inserted_total} tweet(s) inserts", stage_key="copy")
            return {
                "tweets_inserted": inserted_total,
                "chunks_processed": chunk_idx,
                "usage": total_usage,
                "paused": False,
                "quota_exhausted": True,
                "quota_error": str(e),
            }
        except Exception as e:
            failed_chunks_ext += 1
            _log(f"extension chunk {human_idx}/{total_chunks} ECHEC ({type(e).__name__}: {e}) · skip et continue")
            if progress_run_id is not None:
                run_state.update_message(progress_run_id, f"Chunk {human_idx}/{total_chunks} échoué · skip ({failed_chunks_ext} chunk(s) perdu(s))", stage_key="copy")
            continue
        # Force adaptation_level + clear source_text par sécurité
        for t in chunk_tweets["tweets"]:
            t["adaptation_level"] = "original_inspired"
            t["source_text"] = None
            t["source_language"] = None
            t["translation_fr"] = None
        already_generated.extend(chunk_tweets["tweets"])
        for k, v in chunk_tweets["usage"].items():
            total_usage[k] += v
        n_ins = _insert_tweets_batch(chunk_tweets["tweets"], csv_run_id, persona_id, extension_idx=extension_idx)
        inserted_total += n_ins
        _log(f"extension chunk {human_idx}/{total_chunks} OK · {len(chunk_tweets['tweets'])} tweets · {n_ins} inseres · ext_idx={extension_idx} · ${chunk_tweets['usage']['cost_usd_estimate']:.4f} ({time.time()-t0:.1f}s)")
        if progress_run_id is not None:
            run_state.update_message(progress_run_id, f"Chunk {human_idx}/{total_chunks} OK · {len(chunk_tweets['tweets'])} tweets ({time.time()-t0:.1f}s)", stage_key="copy")

    # Top-up : si on est encore sous la cible de posts atomiques (a cause de
    # plus de threads que prevu), on lance jusqu'a MAX_EXTRA_EXTENSION_CHUNKS
    # chunks de EXTRA_EXTENSION_CHUNK_SIZE chacun pour completer.
    # `start_extra_done` : nombre de top-ups deja faits avant pause (0 sinon).
    current_posts = _count_posts_for_extension(csv_run_id, extension_idx)
    extra_done = start_extra_done
    if start_extra_done > 0:
        _log(f"extension · reprise apres pause · {start_extra_done} top-up(s) deja fait(s), il en reste {MAX_EXTRA_EXTENSION_CHUNKS - start_extra_done}")
    while current_posts < target_posts and extra_done < MAX_EXTRA_EXTENSION_CHUNKS:
        if progress_run_id is not None and run_state.is_pause_requested(progress_run_id):
            _log(
                f"pause demandee · sortie propre apres top-up · "
                f"{current_posts}/{target_posts} posts atteints"
            )
            return {
                "tweets_inserted": inserted_total,
                # next_chunk_idx = total_chunks pour que la reprise saute la
                # boucle principale et reparte directement en top-up
                "chunks_processed": total_chunks + extra_done,
                "usage": total_usage,
                "paused": True,
                "next_chunk_idx": total_chunks,
                "total_chunks": total_chunks,
                "extra_done": extra_done,
            }

        missing = target_posts - current_posts
        # Genere au max EXTRA_EXTENSION_CHUNK_SIZE, mais on peut viser plus serre
        # si on n'a qu'a combler 2-3 posts.
        extra_n = min(EXTRA_EXTENSION_CHUNK_SIZE, max(CHUNK_SIZE // 4, math.ceil(missing * POSTS_TO_MESSAGES_OVERSHOOT)))
        extra_done += 1
        extra_human_idx = total_chunks + extra_done
        t0 = time.time()
        _log(
            f"extension top-up {extra_done}/{MAX_EXTRA_EXTENSION_CHUNKS} · "
            f"{current_posts}/{target_posts} posts seulement · {extra_n} tweets complementaires · appel API..."
        )
        if progress_run_id is not None:
            run_state.update_message(
                progress_run_id,
                f"Top-up · {current_posts}/{target_posts} posts · génération de {extra_n} tweets...",
                stage_key="copy",
            )
        # Budget restant pour ce top-up (run-level cap)
        extra_remaining_budget: int | None = None
        if extension_mention_target_total is not None:
            mentions_so_far = _count_extension_mentions_so_far(csv_run_id, extension_idx)
            extra_remaining_budget = max(0, extension_mention_target_total - mentions_so_far)

        try:
            extra_chunk = _process_extension_chunk(
                extra_n, playbook, persona, existing_sample, model,
                extra_human_idx, total_chunks + MAX_EXTRA_EXTENSION_CHUNKS,
                already_generated=already_generated,
                mention_stats=mention_stats,
                style_stats=style_stats,
                remaining_mention_budget=extra_remaining_budget,
                target_messages_total=target_messages,
            )
        except llm_client.LLMQuotaExhaustedError as e:
            _log(f"extension top-up {extra_done} QUOTA · {e} · arret immediat de la boucle top-up")
            return {
                "tweets_inserted": inserted_total,
                "chunks_processed": total_chunks + extra_done,
                "usage": total_usage,
                "paused": False,
                "quota_exhausted": True,
                "quota_error": str(e),
            }
        except Exception as e:
            _log(f"extension top-up {extra_done} ECHEC ({type(e).__name__}: {e}) · skip")
            continue
        for t in extra_chunk["tweets"]:
            t["adaptation_level"] = "original_inspired"
            t["source_text"] = None
            t["source_language"] = None
            t["translation_fr"] = None
        already_generated.extend(extra_chunk["tweets"])
        for k, v in extra_chunk["usage"].items():
            total_usage[k] += v
        n_ins_extra = _insert_tweets_batch(
            extra_chunk["tweets"], csv_run_id, persona_id, extension_idx=extension_idx
        )
        inserted_total += n_ins_extra
        current_posts = _count_posts_for_extension(csv_run_id, extension_idx)
        _log(
            f"extension top-up {extra_done} OK · {len(extra_chunk['tweets'])} tweets · "
            f"{n_ins_extra} inseres · cumul posts atteints {current_posts}/{target_posts} · "
            f"${extra_chunk['usage']['cost_usd_estimate']:.4f} ({time.time()-t0:.1f}s)"
        )

    if current_posts < target_posts:
        _log(
            f"extension top-up · plafond atteint ({MAX_EXTRA_EXTENSION_CHUNKS} extras) · "
            f"{current_posts}/{target_posts} posts (cible non atteinte, mais on s'arrete pour eviter "
            f"l'emballement)"
        )
    else:
        _log(f"extension · cible posts atteinte · {current_posts}/{target_posts}")

    return {
        "tweets_inserted": inserted_total,
        "chunks_processed": total_chunks + extra_done,
        "usage": total_usage,
        "paused": False,
    }


def _count_extension_mentions_so_far(csv_run_id: int, extension_idx: int | None) -> int:
    """Compte les tweets de l'extension en cours qui nomment Compaatible.

    Cible : run-level cap sur les mentions, pour éviter la dérive observée
    (cible per-chunk 14% mais ratio global 23% sur run 56 Thaïs). Avant chaque
    chunk on regarde combien on a déjà mentionné, on en déduit le budget restant.

    Le filtre est cohérent avec `_fetch_persona_mention_ratio` (LIKE '%compaatible%'
    incluant les URL) pour que cible et compteur s'alignent.
    """
    with db.cursor() as cur:
        if extension_idx is None:
            cur.execute(
                "SELECT COUNT(*) AS n FROM mkt_tweets "
                "WHERE csv_run_id = %s AND extension_idx IS NULL "
                "AND LOWER(content) LIKE %s",
                (csv_run_id, "%compaatible%"),
            )
        else:
            cur.execute(
                "SELECT COUNT(*) AS n FROM mkt_tweets "
                "WHERE csv_run_id = %s AND extension_idx = %s "
                "AND LOWER(content) LIKE %s",
                (csv_run_id, extension_idx, "%compaatible%"),
            )
        return int(cur.fetchone()["n"] or 0)


def _count_posts_for_extension(csv_run_id: int, extension_idx: int | None) -> int:
    """Compte les posts atomiques pour un (csv_run_id, extension_idx) donne.

    Un post atomique = un thread (peu importe son nb de tweets) OU un tweet isole.
    Utilise par generate_extension pour decider si on a atteint la cible `count`.
    """
    with db.cursor() as cur:
        if extension_idx is None:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE thread_key IS NULL) AS isolated,
                    COUNT(DISTINCT thread_key) FILTER (WHERE thread_key IS NOT NULL) AS threads
                FROM mkt_tweets
                WHERE csv_run_id = %s AND extension_idx IS NULL
                """,
                (csv_run_id,),
            )
        else:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE thread_key IS NULL) AS isolated,
                    COUNT(DISTINCT thread_key) FILTER (WHERE thread_key IS NOT NULL) AS threads
                FROM mkt_tweets
                WHERE csv_run_id = %s AND extension_idx = %s
                """,
                (csv_run_id, extension_idx),
            )
        row = cur.fetchone() or {}
    return int(row.get("isolated") or 0) + int(row.get("threads") or 0)


def _process_extension_chunk(
    chunk_count: int,
    playbook: dict,
    persona: dict,
    existing_sample: list[str],
    model: str,
    chunk_idx: int,
    total_chunks: int,
    already_generated: list[dict],
    mention_stats: dict | None = None,
    style_stats: dict | None = None,
    remaining_mention_budget: int | None = None,
    target_messages_total: int | None = None,
) -> dict:
    """Un chunk d'extension : on demande chunk_count tweets originaux, en partageant
    l'échantillon des tweets existants pour calibrer la voix + les tweets déjà générés
    dans ce run (pour éviter les doublons inter-chunks).

    mention_stats : ratio Compaatible observé sur les originaux de la persona, à
    répliquer (cible naturelle au lieu d'une fourchette générique).
    remaining_mention_budget : si fourni, plafond DUR de mentions Compaatible pour
    ce chunk, calculé au niveau du run d'extension. Évite la dérive per-chunk
    qui compoundait le ratio global.
    style_stats : ratios threads-vs-isoles et needs_image observes sur les
    originaux. Sert a aligner la cadence de l'extension sur la signature deja
    construite par la persona — coherence maximale du compte dans le temps.
    """
    # Blocs cachables (constants pour tous les chunks du run)
    playbook_block = {
        "type": "text",
        "text": f"## Playbook source\n```json\n{json.dumps(playbook, indent=2, ensure_ascii=False)}\n```",
    }

    # VOIX DE LA PERSONA — bloc dédié hors du JSON pour qu'il pèse plus lourd
    # que les autres champs (corrige la dérive observée : extensions plus emojis,
    # plus formulaires, plus marketing que les originaux malgré voice_signature
    # présente dans le JSON dump).
    voice_sig = (persona.get("voice_signature") or "").strip()
    vocab_yes = persona.get("vocabulary_yes") or []
    vocab_no = persona.get("vocabulary_no") or []
    voice_block_parts = [
        "## VOIX DE LA PERSONA — marqueurs NON NÉGOCIABLES\n",
        "Ces marqueurs définissent la signature reconnaissable de la persona. ",
        "Avant chaque tweet, relis cette section et vérifie que ton tweet en porte ",
        "au moins quelques-uns. **Pas de pastiche, pas de surdose** — l'objectif est ",
        "que tes tweets puissent se glisser dans le corpus existant sans qu'on ",
        "devine qu'ils sont postérieurs.\n",
    ]
    if voice_sig:
        voice_block_parts.append(f"\n### Signature de voix\n{voice_sig}\n")
    if vocab_yes:
        voice_block_parts.append(
            "\n### Vocabulaire SIGNATURE (à mobiliser régulièrement)\n"
            + ", ".join(f"`{w}`" for w in vocab_yes)
            + "\n"
        )
    if vocab_no:
        voice_block_parts.append(
            "\n### Vocabulaire BANNI pour cette persona (jamais)\n"
            + ", ".join(f"`{w}`" for w in vocab_no)
            + "\n"
        )
    voice_block_parts.append(
        "\n### Anti-dérive éditoriale\n"
        "Quand on prolonge un corpus existant, la tentation est forte de glisser hors "
        "voix sans s'en rendre compte. Quatre dérives à surveiller pour TOI sur cette "
        "persona précise :\n\n"
        "1. **Densité d'emojis vs la signature** : compare la fréquence d'emojis que "
        "tu vas produire avec ce que dit la `Signature de voix` ci-dessus. Si elle "
        "décrit une persona qui en utilise peu, n'en ajoute pas par habitude. Si elle "
        "en utilise beaucoup, ne les retire pas non plus. C'est la signature qui dicte, "
        "pas une moyenne.\n\n"
        "2. **Ton quand tu nommes Compaatible** : la persona parle de l'app comme elle "
        "parlerait à une copine — elle la cite, elle raconte ce que ça a changé pour "
        "elle. Elle ne fait PAS une démonstration produit. Quand un tweet glisse vers "
        "un registre argumentaire (fonctionnalités, propriétés du produit, mécanismes "
        "techniques nommés comme des features), tu es sorti de la voix. Reviens au "
        "registre d'expérience vécue.\n\n"
        "3. **Variété des ouvertures** : si tu remarques que plusieurs de tes tweets "
        "commencent par le même type de structure (interrogation, énoncé général, "
        "constatation), c'est un signal de paresse éditoriale. Les hook_patterns "
        "doivent rester aussi variés que dans l'échantillon des tweets existants — pas "
        "concentrés sur un seul mode.\n\n"
        "4. **Cadence thread/isolé** : ne dérive pas vers plus de threads (ou moins) "
        "que ce que la persona fait dans l'échantillon. La cadence chiffrée que tu "
        "reçois plus bas est la cible — respecte-la.\n\n"
        "**Test mental avant chaque tweet** : si tu le glissais au milieu de "
        "l'échantillon des tweets existants, est-ce qu'un lecteur attentif pourrait "
        "deviner que c'est toi (LLM en extension) plutôt que la persona ? Si oui, "
        "réécris. Le critère, c'est l'indétectabilité."
    )
    voice_block = {
        "type": "text",
        "text": "".join(voice_block_parts),
    }

    # Reste de la persona (backstory, avatars, etc.) — utile pour la cohérence
    # mais sans la voix qui a été extraite plus haut.
    persona_minus_voice = {k: v for k, v in persona.items() if k not in ("voice_signature", "vocabulary_yes", "vocabulary_no")}
    persona_block = {
        "type": "text",
        "text": f"## Persona Compaatible (contexte)\n```json\n{json.dumps(persona_minus_voice, indent=2, ensure_ascii=False)}\n```",
    }
    existing_block = {
        "type": "text",
        "text": (
            "## Tweets déjà produits par cette persona (calibre de voix · ne pas dupliquer)\n\n"
            + ("\n".join(f"- {t}" for t in existing_sample) if existing_sample else "(aucun tweet existant : démarrage du corpus)")
        ),
        "cache_control": {"type": "ephemeral"},
    }

    # Bloc variable : ce qu'on demande pour CE chunk + ce qu'on vient juste de générer
    just_generated_text = ""
    if already_generated:
        recent = already_generated[-30:]
        just_generated_text = (
            "\n\n## Tweets que tu viens de générer dans ce run (ne pas dupliquer, varier les angles)\n\n"
            + "\n".join(f"- {t.get('content','')}" for t in recent if t.get("content"))
        )

    # Plafond mentions Compaatible : on observe le ratio des originaux pour fixer
    # un plafond, JAMAIS une cible. Doctrine Loys : les mentions sont strictement
    # adaptatives — un tweet ne nomme Compaatible QUE si la matière s'y prête.
    # Aucun quota minimal, jamais. Le plafond global empêche la sur-mention que
    # produirait sinon le cumul des plafonds per-chunk (run 56 Thaïs : cumul à
    # 23% alors que ratio originaux 14%).
    if mention_stats and mention_stats.get("ratio") is not None:
        target_ratio = mention_stats["ratio"]
        natural_count = round(chunk_count * target_ratio)
        # Plafond per-chunk avec un peu de flex au-dessus du naturel
        per_chunk_cap = max(natural_count + 1, 2)
        # Plafond effectif = min(per-chunk, budget restant au niveau du run)
        if remaining_mention_budget is not None:
            effective_cap = min(per_chunk_cap, remaining_mention_budget)
            budget_note = (
                f"\n\n**Budget global restant pour le run d'extension** : "
                f"{remaining_mention_budget} mention(s) Compaatible maximum sur l'ensemble "
                "des chunks restants. Ce budget se consomme au fil de ton avancée — il "
                "diminue chaque fois que tu nommes Compaatible dans un chunk précédent. "
                "Quand il atteint 0, plus aucune mention n'est autorisée jusqu'à la fin "
                "de l'extension."
            )
        else:
            effective_cap = per_chunk_cap
            budget_note = ""

        mention_target_text = (
            "\n\n## PLAFOND MENTIONS COMPAATIBLE — strictement adaptatif, jamais forcé\n\n"
            f"Sur les **{mention_stats['total']} tweets originaux** de cette persona, "
            f"**{mention_stats['named']} nomment Compaatible** ({target_ratio*100:.1f}%). "
            "C'est ce que produit cette persona QUAND la matière s'y prête — pas un quota "
            "à atteindre.\n\n"
            "**Règle absolue : tu ne mentionnes Compaatible que si le tweet s'y prête "
            "naturellement.** Aucun chunk n'a de quota minimal. **0 mention sur ce chunk "
            "est un résultat parfaitement valide** si aucun tweet ne s'y prête — c'est "
            "souvent le bon choix par défaut.\n\n"
            f"**Plafond DUR sur ce chunk : {effective_cap} mention(s) maximum.** "
            "Au-delà, tu forces des pivots qui ne tiennent pas naturellement — donc tu "
            "sors hors voix. Ce plafond est calculé pour que sur l'ensemble du run "
            "d'extension le ratio global reste proche du ratio observé sur les "
            "originaux ; si chaque chunk pousse au plafond, le ratio global explose "
            "au-dessus de la signature de la persona."
            f"{budget_note}"
        )
    else:
        mention_target_text = (
            "\n\n## PLAFOND MENTIONS COMPAATIBLE — strictement adaptatif\n\n"
            "Pas assez de tweets originaux pour calculer un ratio spécifique à la persona. "
            "Doctrine par défaut : tu mentionnes Compaatible UNIQUEMENT si le tweet s'y "
            "prête naturellement, jamais par quota. **Plafond strict : 10% des tweets du "
            "chunk maximum.** 0 mention est parfaitement valide si rien ne s'y prête."
        )

    # Cibles stylistiques (threads vs isoles, densite image) calees sur les
    # originaux de la persona. Meme philosophie que mention_stats : on replique
    # ce que la persona fait deja, pour que l'extension se glisse sans rupture
    # dans son feed historique.
    if style_stats:
        thr_ratio = style_stats["thread_post_ratio"]
        img_ratio = style_stats["image_ratio"]
        expected_threads = round(chunk_count * thr_ratio)
        style_target_text = (
            "\n\n## CIBLE STYLE (specifique a cette persona)\n\n"
            f"**Threads vs tweets isoles** : sur les {style_stats['total_posts']} posts originaux "
            f"de cette persona, **{style_stats['thread_posts']} sont des threads** "
            f"({thr_ratio*100:.0f}%). C'est sa cadence naturelle. Sur ce chunk de "
            f"{chunk_count} posts, vise environ **{expected_threads} thread(s)**, le reste "
            "en tweets isoles. Marge de 1-2 acceptable selon ce qui se prete. "
            "Un thread anemique vaut moins qu'un bon one-liner : si la matiere ne se prete "
            "pas, sors un isole.\n\n"
            f"**Images** : sur les {style_stats['total_msgs']} messages originaux de cette persona, "
            f"**{style_stats['img_msgs']} ont needs_image=true** ({img_ratio*100:.0f}%). "
            f"Replique cette densite : vise environ **{round(chunk_count*img_ratio)} message(s)** "
            f"sur {chunk_count} avec needs_image=true. Renseigne image_brief en consequence "
            "(brief semantique riche, voir consigne systeme). Pas plus, pas moins — "
            "c'est la signature visuelle deja construite par la persona."
        )
    else:
        style_target_text = (
            "\n\n## CIBLE STYLE\n\n"
            "Pas assez de posts originaux pour calculer un ratio specifique persona. "
            "Fallback : **jugement editorial** sur thread vs isole (lis l'echantillon "
            "et capte la cadence). Pour les images, cible **25-40%** des messages avec "
            "needs_image=true."
        )

    chunk_block = {
        "type": "text",
        "text": (
            f"## Chunk {chunk_idx}/{total_chunks} · génère {chunk_count} tweets ORIGINAUX\n\n"
            "Pas de tweet source. Pure invention dans la voix de la persona, en t'appuyant "
            "sur les mécanismes du playbook. Tous les tweets sortent en "
            "`adaptation_level=\"original_inspired\"` et `source_text=null`."
            f"{mention_target_text}"
            f"{style_target_text}"
            f"{just_generated_text}"
        ),
    }

    # Ordre des blocs : la voix passe en premier (avant playbook/persona/échantillon)
    # pour que le LLM la voie comme la contrainte la plus saillante. La persona JSON
    # (backstory, avatars) reste en contexte mais sans la voix qui a été extraite.
    user_content = [voice_block, playbook_block, persona_block, existing_block, chunk_block]
    sys_blocks = prompts.build_system_for_extension()
    result = llm_client.call_messages(
        model=model,
        system_blocks=sys_blocks,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=32768,
        temperature=0.95,
    )

    parsed, total_usage = _parse_or_repair(result, model, sys_blocks, user_content, label=f"ext chunk {chunk_idx}/{total_chunks}")
    tweets = parsed.get("tweets", [])

    # Retry-on-empty (meme rationale que _process_chunk : Gemini Pro thinking
    # rend parfois tweets:[] alors que le JSON est valide). Retry combine
    # thinking_budget genereux + temperature plus basse.
    if not tweets:
        _log(
            f"ext chunk {chunk_idx}/{total_chunks} WARNING · JSON parse OK mais 0 tweet retourne · "
            f"out_tokens={total_usage.get('output_tokens', 0)} · "
            f"retry avec thinking_budget=8192 + temperature=0.7..."
        )
        retry_result = llm_client.call_messages(
            model=model,
            system_blocks=sys_blocks,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=32768,
            temperature=0.7,
            thinking_budget=8192,
        )
        try:
            retry_parsed, retry_usage = _parse_or_repair(retry_result, model, sys_blocks, user_content, label=f"ext chunk {chunk_idx}/{total_chunks} retry")
            retry_tweets = retry_parsed.get("tweets", [])
            for k in total_usage:
                if k in retry_usage:
                    total_usage[k] += retry_usage[k]
            if retry_tweets:
                _log(f"ext chunk {chunk_idx}/{total_chunks} retry OK · {len(retry_tweets)} tweet(s) recuperes")
                tweets = retry_tweets
            else:
                _log(f"ext chunk {chunk_idx}/{total_chunks} retry ECHEC · toujours 0 tweet · on abandonne ce chunk")
        except Exception as e:
            _log(f"ext chunk {chunk_idx}/{total_chunks} retry ECHEC ({type(e).__name__}: {e}) · on abandonne ce chunk")
            for k in total_usage:
                if k in retry_result["usage"]:
                    total_usage[k] += retry_result["usage"][k]

    return {"tweets": tweets, "usage": total_usage}


def _process_chunk(chunk: list[dict], content_col: str, playbook: dict, persona: dict,
                    model: str, chunk_idx: int, total_chunks: int) -> dict:
    def shrink(row: dict) -> dict:
        return {
            "text": (row.get(content_col) or "").strip(),
            "likes": csv_parser.safe_int(row.get("likes", 0)),
            "retweets": csv_parser.safe_int(row.get("retweets", 0)),
            "views": csv_parser.safe_int(row.get("views", 0)),
        }

    # Découpage en blocs pour le prompt caching :
    # - playbook + persona sont CONSTANTS pour tous les chunks d'un run → mis en blocs cachables.
    # - cache_control sur le dernier bloc constant (persona) crée un breakpoint qui sera lu en cache
    #   dès le 2e chunk. Le chunk variable et l'instruction restent après le breakpoint.
    playbook_block = {
        "type": "text",
        "text": f"## Playbook source\n```json\n{json.dumps(playbook, indent=2, ensure_ascii=False)}\n```",
    }
    persona_block = {
        "type": "text",
        "text": f"## Persona Compaatible\n```json\n{json.dumps(persona, indent=2, ensure_ascii=False)}\n```",
        "cache_control": {"type": "ephemeral"},
    }
    chunk_block = {
        "type": "text",
        "text": (
            f"## Chunk de tweets sources {chunk_idx}/{total_chunks} ({len(chunk)} tweets)\n"
            f"```json\n{json.dumps([shrink(r) for r in chunk], indent=2, ensure_ascii=False)}\n```\n\n"
            "Pour ce chunk, produis le JSON des tweets Compaatible. Tu peux générer plus, moins ou autant "
            "de tweets que de sources, selon ton jugement. Tu peux fusionner plusieurs sources en un thread. "
            "Tu peux créer des tweets purement originaux inspirés des mécanismes."
        ),
    }

    user_content = [playbook_block, persona_block, chunk_block]
    sys_blocks = prompts.build_system_for_copywriting()
    result = llm_client.call_messages(
        model=model,
        system_blocks=sys_blocks,
        messages=[{"role": "user", "content": user_content}],
        max_tokens=32768,
        temperature=0.9,
    )

    parsed, total_usage = _parse_or_repair(result, model, sys_blocks, user_content, label=f"chunk {chunk_idx}/{total_chunks}")
    tweets = parsed.get("tweets", [])

    # Retry-on-empty : sur les modeles thinking (Gemini Pro), il arrive que la
    # reponse soit un JSON valide mais avec tweets:[] - typiquement le modele
    # s'arrete trop tot (les chunks rates ont produit moins d'out_tokens que
    # les chunks reussis, pas plus). Donc le retry combine DEUX leviers :
    # 1) thinking_budget=8192 force le modele a mieux raisonner avant l'output
    # 2) temperature=0.6 reduit la divergence aleatoire du raisonnement
    # Pour Anthropic, thinking_budget est ignore proprement par le dispatcher.
    if not tweets:
        _log(
            f"chunk {chunk_idx}/{total_chunks} WARNING · JSON parse OK mais 0 tweet retourne · "
            f"out_tokens={total_usage.get('output_tokens', 0)} · "
            f"retry avec thinking_budget=8192 + temperature=0.6..."
        )
        retry_result = llm_client.call_messages(
            model=model,
            system_blocks=sys_blocks,
            messages=[{"role": "user", "content": user_content}],
            max_tokens=32768,
            temperature=0.6,
            thinking_budget=8192,
        )
        try:
            retry_parsed, retry_usage = _parse_or_repair(retry_result, model, sys_blocks, user_content, label=f"chunk {chunk_idx}/{total_chunks} retry")
            retry_tweets = retry_parsed.get("tweets", [])
            for k in total_usage:
                if k in retry_usage:
                    total_usage[k] += retry_usage[k]
            if retry_tweets:
                _log(f"chunk {chunk_idx}/{total_chunks} retry OK · {len(retry_tweets)} tweet(s) recuperes")
                tweets = retry_tweets
            else:
                _log(f"chunk {chunk_idx}/{total_chunks} retry ECHEC · toujours 0 tweet · on abandonne ce chunk")
        except Exception as e:
            _log(f"chunk {chunk_idx}/{total_chunks} retry ECHEC ({type(e).__name__}: {e}) · on abandonne ce chunk")
            for k in total_usage:
                if k in retry_result["usage"]:
                    total_usage[k] += retry_result["usage"][k]

    return {"tweets": tweets, "usage": total_usage}


def _parse_or_repair(result: dict, model: str, system_blocks: list, original_user_content, label: str = "chunk") -> tuple[dict, dict]:
    """Parse le JSON de la réponse. Si invalide, fait UN retry self-fix via API.

    Retourne (parsed_dict, usage_aggrégé). Lève JSONDecodeError si le retry échoue
    aussi — le caller décide alors de skip le chunk ou de propager.
    """
    from brain.source_analyzer import parse_json_response
    try:
        return parse_json_response(result["text"]), result["usage"]
    except (json.JSONDecodeError, ValueError) as e:
        _log(f"{label} · JSON invalide ({type(e).__name__}: {e}) · retry self-fix...")
        fix_prompt = (
            "Ta réponse précédente contient du JSON invalide. "
            f"Erreur : {e}\n\n"
            "Renvoie UNIQUEMENT le JSON corrigé, même structure, rien d'autre — "
            "pas de commentaire avant/après, pas de bloc markdown. Vérifie : "
            "guillemets correctement échappés à l'intérieur des strings, pas de "
            "virgules trailing, accolades/crochets équilibrés."
        )
        retry = llm_client.call_messages(
            model=model,
            system_blocks=system_blocks,
            messages=[
                {"role": "user", "content": original_user_content},
                {"role": "assistant", "content": result["text"]},
                {"role": "user", "content": fix_prompt},
            ],
            max_tokens=32768,
            temperature=0.2,
        )
        parsed = parse_json_response(retry["text"])  # peut encore lever → caller skip
        merged = {k: result["usage"].get(k, 0) + retry["usage"].get(k, 0) for k in result["usage"]}
        _log(f"{label} · self-fix OK")
        return parsed, merged


def _insert_tweets_batch(tweets: list[dict], csv_run_id: int, persona_id: int,
                          extension_idx: int | None = None) -> int:
    """Insère les tweets en DB. Calcule thread_order pour les threads.

    Si un tweet dépasse 280 chars (l'IA s'est plantée malgré la consigne), il est
    automatiquement découpé en un thread aux meilleures frontières (phrase > clause
    > espace), en préservant les URLs intactes. Les métadonnées (image_brief,
    adaptation_level…) s'appliquent à tous les morceaux du split.

    `extension_idx` : NULL pour les tweets du run d'origine, 1/2/3... pour les
    batchs d'extension successifs. Permet de tracer l'origine quand on agrège
    tout sous le même csv_run_id.
    """
    if not tweets:
        return 0

    thread_counters: dict[str, int] = {}
    rows_to_insert = []
    stripped_mention_count = 0
    invalid_blog_count = 0
    autosplit_count = 0
    autosplit_seq = 0  # compteur pour générer des thread_key uniques pour les auto-splits
    tk_collisions = 0
    dash_replacements = 0
    auto_replaced_words: list[str] = []
    banned_global_hits: list[str] = []
    vocab_no_hits: list[str] = []
    price_leak_hits: list[str] = []

    # Catalogue blog pour valider les slugs (charge une fois par batch, lru_cache derrière)
    from brain import blog_catalog
    valid_slugs = blog_catalog.valid_slugs("fr")

    # vocabulary_no de la persona pour l'audit post-LLM (mots que CETTE persona
    # ne dirait jamais, déduits des tweets sources au stage persona). Log only.
    with db.cursor() as cur:
        cur.execute(
            "SELECT vocabulary_no FROM mkt_personas_emerged WHERE id = %s",
            (persona_id,),
        )
        row = cur.fetchone()
    persona_vocab_no: list[str] = (row.get("vocabulary_no") or []) if row else []

    # Thread_keys déjà existants pour ce run (autres chunks). Le modèle ne sait pas
    # ce que les chunks précédents ont produit, donc il réinvente parfois le même
    # kebab-case naturel ("aimer-vs-convenir") → faux thread fusionné + mentions
    # quasi dupliquées. On suffixe pour garantir l'unicité par run.
    with db.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT thread_key FROM mkt_tweets "
            "WHERE csv_run_id = %s AND thread_key IS NOT NULL",
            (csv_run_id,),
        )
        existing_tks: set[str] = {r["thread_key"] for r in cur.fetchall()}

    def _ensure_unique_tk(base_tk: str) -> str:
        """Suffixe -2, -3, ... si base_tk déjà utilisé sur ce run."""
        if base_tk not in existing_tks:
            existing_tks.add(base_tk)
            return base_tk
        n = 2
        while f"{base_tk}-{n}" in existing_tks:
            n += 1
        new_tk = f"{base_tk}-{n}"
        existing_tks.add(new_tk)
        return new_tk

    # Remap intra-chunk : un thread_key explicite du modèle peut apparaître sur
    # plusieurs tweets ce chunk-ci ; on veut tous les regrouper sous le MÊME
    # nouveau key remap (donc résolution une seule fois par base_tk).
    tk_remap: dict[str, str] = {}

    def _resolve_tk(explicit_tk: str | None) -> str | None:
        if not explicit_tk:
            return None
        if explicit_tk in tk_remap:
            return tk_remap[explicit_tk]
        resolved = _ensure_unique_tk(explicit_tk)
        if resolved != explicit_tk:
            nonlocal tk_collisions
            tk_collisions += 1
        tk_remap[explicit_tk] = resolved
        return resolved

    for t in tweets:
        raw = (t.get("content") or "").strip()
        # Normalisation typographique systematique (espaces, ponctuation, jonction URL)
        # appliquee en premier pour que toutes les etapes suivantes (mention strip,
        # dash sanitize, split en thread, audit char_count) voient le texte propre.
        content = _normalize_spacing(raw)
        before_mention_strip = content
        content = _strip_mentions(content)
        if content != before_mention_strip:
            stripped_mention_count += 1
        # Filet de sécurité cadratin/en-dash : remplacement hard avant tout split
        # pour que le compte de chars (≤280) reflète la version finale insérée.
        content, n_dashes = _sanitize_dashes(content)
        dash_replacements += n_dashes
        # Auto-corrections sûres : "révélation" → "annonce", "algorithme" → "méthode"
        # (avant audit, pour que les hits restants reflètent vraiment ce qui reste à relire).
        content, replaced_here = _auto_replace_banned(content)
        auto_replaced_words.extend(replaced_here)
        # Audit règles globales + vocabulary_no de la persona + leak de prix (log only)
        hits = _audit_banned_terms(content, persona_vocab_no)
        banned_global_hits.extend(hits["global"])
        vocab_no_hits.extend(hits["vocab_no"])
        price_leak_hits.extend(hits["price"])
        # Validation des URLs blog : retire les slugs inventés (filet anti-hallucination)
        content, n_bad_blogs = _validate_and_clean_blog_urls(content, valid_slugs)
        invalid_blog_count += n_bad_blogs
        if not content:
            continue

        # Champs INTERNES image (étape 1) : ne sortiront jamais du CSV Cortex.
        needs_img = bool(t.get("needs_image"))
        img_brief = (t.get("image_brief") or None) if needs_img else None

        explicit_tk = (t.get("thread_key") or "").strip() or None
        # Résoudre maintenant (suffixe si collision avec un autre chunk de ce run)
        resolved_explicit_tk = _resolve_tk(explicit_tk)

        # Étape 1 : énumération inline ("1. … 2. … 3. …") → un item par tweet.
        # Doctrine : pas d'énumération entassée dans un seul post. Si détectée,
        # on force le mode thread.
        enum_parts = _split_enumeration(content)
        if enum_parts and len(enum_parts) >= 2:
            # Chaque item peut encore dépasser 280 chars → on passe chacun dans
            # le splitter de longueur. La liste finale enchaîne tous les morceaux.
            parts: list[str] = []
            for item in enum_parts:
                parts.extend(_split_into_thread(item, max_len=280))
        else:
            # Étape 2 (cas standard) : split par longueur si > 280 chars
            parts = _split_into_thread(content, max_len=280)

        if len(parts) > 1:
            autosplit_count += 1
            # Si l'IA n'avait pas prévu de thread, on en crée un auto-split.
            # Si elle en avait un, on garde son thread_key (les parts s'enchaînent dedans).
            if not resolved_explicit_tk:
                autosplit_seq += 1
                tk = f"autosplit-r{csv_run_id}-{autosplit_seq:03d}"
                # autosplit keys sont déjà uniques par construction → on les inscrit
                existing_tks.add(tk)
            else:
                tk = resolved_explicit_tk
        else:
            tk = resolved_explicit_tk

        # Insert chaque partie. Les métadonnées (adaptation_level, image, reasoning…) sont
        # répliquées sur chaque partie pour cohérence DB ; en pratique le 1er tweet du
        # thread est celui qui porte le sens éditorial principal.
        for part in parts:
            thread_order = None
            if tk:
                thread_counters[tk] = thread_counters.get(tk, 0) + 1
                thread_order = thread_counters[tk]

            rows_to_insert.append({
                "persona_id": persona_id,
                "csv_run_id": csv_run_id,
                "extension_idx": extension_idx,
                "content": part,  # ≤ 280 garanti par _split_into_thread
                "media_url": None,
                "scheduled_at": None,
                "thread_key": tk,
                "thread_order": thread_order,
                "source_text": t.get("source_text"),
                "source_lang": t.get("source_language"),
                "translation_fr": t.get("translation_fr"),
                "hook_pattern": t.get("hook_pattern"),
                "mechanism_applied": t.get("mechanism_applied"),
                "integration_strategy": t.get("integration_strategy"),
                "adaptation_level": t.get("adaptation_level"),
                "reasoning": t.get("reasoning"),
                "needs_image": needs_img,
                "image_brief": img_brief,
                "is_quote_trigger": bool(t.get("is_quote_trigger")),
                "is_clivant": bool(t.get("is_clivant")),
                "char_count": len(part),
                "status": "draft",
            })

    if not rows_to_insert:
        return 0

    # Canonicalisation du pattern image dans les threads (règle dure) :
    # un thread porte ses images soit sur TOUS les messages, soit uniquement T1,
    # soit uniquement le dernier. Toute autre distribution est ramenée à l'un de
    # ces patterns en retirant les flags needs_image excédentaires.
    rows_to_insert, img_stats = _enforce_thread_image_pattern(rows_to_insert)
    if img_stats["threads_canonicalized"]:
        _log(
            f"image pattern enforce · {img_stats['threads_canonicalized']} thread(s) "
            f"recadré(s) sur pattern legal · {img_stats['flags_dropped']} flag(s) needs_image retiré(s) "
            f"(répartition finale : all={img_stats['pattern_all']} · first={img_stats['pattern_first']} · "
            f"last={img_stats['pattern_last']} · cleared={img_stats['pattern_none']})"
        )

    # Régulation post-LLM de la mention "Compaatible" :
    # - tweet isolé qui nomme Compaatible → drop
    # - T1 d'un thread qui nomme Compaatible → drop thread entier
    # - plafond 15% cumulé sur le run → drop des mentions T2+ excédentaires
    #   (les mentions URL-only ne sont PAS comptées, cf _names_compaatible)
    # Renumérote thread_order après les drops.
    rows_to_insert, comp_stats = _enforce_compaatible_rules(rows_to_insert, csv_run_id=csv_run_id)
    if comp_stats["dropped_isolated_mentions"]:
        _log(
            f"compaatible enforce · {comp_stats['dropped_isolated_mentions']} mention(s) "
            "en tweet isolé retirée(s) (doctrine : T2+ uniquement)"
        )
    if comp_stats["dropped_t1_threads"]:
        _log(
            f"compaatible enforce · {comp_stats['dropped_t1_threads']} thread(s) entier(s) "
            f"retiré(s) car T1 nommait Compaatible "
            f"({comp_stats['dropped_t1_tweets']} tweet(s) au total)"
        )
    if comp_stats["dropped_excess_mentions"]:
        _log(
            f"compaatible enforce · {comp_stats['dropped_excess_mentions']} mention(s) "
            f"T2+ retirée(s) pour respecter le plafond 15% cumulé "
            f"(ratio cumulé {comp_stats['cumulative_ratio']*100:.1f}% sur {comp_stats['cumulative_total']} tweets du run)"
        )

    if not rows_to_insert:
        return 0

    cols = list(rows_to_insert[0].keys())
    placeholders = ",".join(f"%({c})s" for c in cols)
    col_names = ",".join(cols)
    sql = f"INSERT INTO mkt_tweets ({col_names}) VALUES ({placeholders}) RETURNING id"

    inserted = 0
    with db.cursor() as cur:
        for row in rows_to_insert:
            cur.execute(sql, row)
            inserted += 1
    if stripped_mention_count:
        _log(f"mention strip · {stripped_mention_count} tweet(s) avaient une @mention residuelle, nettoyee avant insert")
    if invalid_blog_count:
        _log(f"blog slug · {invalid_blog_count} URL(s) /blog/<slug> avec slug invalide retirees (l'IA a hallucine un slug)")
    if autosplit_count:
        _log(f"autosplit · {autosplit_count} tweet(s) > 280 chars ont ete decoupes en threads (preserve les URLs)")
    if tk_collisions:
        _log(f"thread_key dedup · {tk_collisions} thread_key(s) du modele collisionnaient avec un chunk precedent, suffixes pour garantir l'unicite intra-run")
    if dash_replacements:
        _log(f"dash sanitize · {dash_replacements} tiret(s) cadratin/en-dash remplaces (marqueurs IA, prompt non respecte)")
    if auto_replaced_words:
        from collections import Counter
        top = Counter(w.lower() for w in auto_replaced_words).most_common(5)
        _log(f"auto-replace · {len(auto_replaced_words)} mot(s) interdit(s) corriges automatiquement : {top} (liste noire CLAUDE.md)")
    if banned_global_hits:
        from collections import Counter
        top = Counter(h.lower() for h in banned_global_hits).most_common(5)
        _log(f"AUDIT regles globales · {len(banned_global_hits)} hit(s) : {top} (non remplaces, a relire)")
    if vocab_no_hits:
        from collections import Counter
        top = Counter(w.lower() for w in vocab_no_hits).most_common(5)
        _log(f"AUDIT vocabulary_no persona · {len(vocab_no_hits)} hit(s) : {top} (non remplaces, a relire)")
    if price_leak_hits:
        from collections import Counter
        top = Counter(h.lower() for h in price_leak_hits).most_common(10)
        _log(
            f"AUDIT prix/tarif · {len(price_leak_hits)} hit(s) : {top} · "
            "regle absolue violee, la persona ne doit jamais parler argent · A RELIRE/CORRIGER"
        )

    # Audit de la regle "mention Compaatible >= 5% en T2+ d'un thread"
    _audit_compaatible_mentions(rows_to_insert, csv_run_id=csv_run_id)

    return inserted


def _enforce_thread_image_pattern(rows: list[dict]) -> tuple[list[dict], dict]:
    """Canonicalise la distribution `needs_image` au sein de chaque thread.

    Règle dure (cf prompts.py) : si un thread porte au moins une image, le pattern
    doit être l'un de ces trois et aucun autre :
    - ALL   : toutes les positions ont needs_image=true
    - FIRST : seul le T1 (thread_order le plus petit) a needs_image=true
    - LAST  : seul le dernier (thread_order le plus grand) a needs_image=true

    Si le modèle a produit un pattern différent (ex: T2 seul, T1+T3, deux du
    milieu), on snap au pattern legal le plus proche selon cette priorité :
    1. Si T1 a needs_image=true → on garde FIRST, on retire les autres flags.
    2. Sinon si le dernier a needs_image=true → on garde LAST, on retire les autres.
    3. Sinon → on retire tous les flags du thread (ALL n'est pas inféré, c'est
       trop agressif sans intention claire).

    Les tweets isolés (thread_key=None) ne sont pas touchés.

    Retire image_brief en même temps que needs_image pour cohérence DB.

    Retourne (rows, stats) — la liste est mutée en place pour les flags.
    """
    stats = {
        "threads_canonicalized": 0,
        "flags_dropped": 0,
        "pattern_all": 0,
        "pattern_first": 0,
        "pattern_last": 0,
        "pattern_none": 0,
    }
    if not rows:
        return rows, stats

    # Groupe par thread_key (ignore les isolés)
    threads: dict[str, list[dict]] = {}
    for r in rows:
        tk = r.get("thread_key")
        if not tk:
            continue
        threads.setdefault(tk, []).append(r)

    for tk, members in threads.items():
        # Tri stable par thread_order (déjà numéroté à ce stade)
        members.sort(key=lambda r: (r.get("thread_order") or 0))
        n = len(members)
        if n < 2:
            # Thread d'1 seul tweet : géré comme isolé, on laisse tel quel
            continue

        flags = [bool(m.get("needs_image")) for m in members]
        n_img = sum(flags)
        if n_img == 0:
            continue  # aucun flag, rien à faire

        is_all = (n_img == n)
        is_first_only = (flags[0] and n_img == 1)
        is_last_only = (flags[-1] and n_img == 1)

        if is_all:
            stats["pattern_all"] += 1
            continue
        if is_first_only:
            stats["pattern_first"] += 1
            continue
        if is_last_only:
            stats["pattern_last"] += 1
            continue

        # Pattern non legal : on snap selon priorité T1 > dernier > clear-all
        target = None
        if flags[0]:
            target = "first"
        elif flags[-1]:
            target = "last"
        else:
            target = "none"

        for idx, m in enumerate(members):
            keep = (
                (target == "first" and idx == 0)
                or (target == "last" and idx == n - 1)
            )
            if m.get("needs_image") and not keep:
                m["needs_image"] = False
                m["image_brief"] = None
                stats["flags_dropped"] += 1

        stats["threads_canonicalized"] += 1
        if target == "first":
            stats["pattern_first"] += 1
        elif target == "last":
            stats["pattern_last"] += 1
        else:
            stats["pattern_none"] += 1

    return rows, stats


def _enforce_compaatible_rules(
    rows: list[dict],
    csv_run_id: int | None = None,
    plafond_cumule: float = 0.15,
) -> tuple[list[dict], dict]:
    """Régulation post-LLM de la mention "Compaatible".

    Applique 3 règles dans cet ordre, par retrait de tweets uniquement
    (jamais de modification de contenu) :

    1. **Tweet isolé qui nomme Compaatible** → retiré (violation doctrine T2+).
    2. **T1 d'un thread qui nomme Compaatible** → tout le thread est retiré
       (T1 = hook ; un hook qui pitche le produit casse le thread entier).
    3. **Plafond 15% cumulé sur le run** : si le ratio (mentions déjà en DB pour
       ce csv_run_id + mentions du chunk en cours) / (total déjà en DB + total
       du chunk) > 15%, retirer les mentions T2+ excédentaires du chunk courant
       (dernières positions d'abord). Si csv_run_id=None, le plafond s'applique
       sur le chunk seul (fallback rétrocompatible pour les appels hors run).

    Les mentions URL-only (où "compaatible" n'apparaît que dans une URL
    `compaatible.com/...`) ne sont PAS comptées — cf `_names_compaatible`.

    Renumérote `thread_order` après retraits pour combler les trous.
    Si un thread tombe à 1 tweet → le tweet devient isolé (thread_key=null).

    Retourne (rows filtrés, dict de stats).
    """
    stats = {
        "dropped_isolated_mentions": 0,
        "dropped_t1_threads": 0,
        "dropped_t1_tweets": 0,
        "dropped_excess_mentions": 0,
        "final_named": 0,
        "final_total": 0,
        "final_ratio": 0.0,
        "cumulative_named": 0,
        "cumulative_total": 0,
        "cumulative_ratio": 0.0,
    }
    if not rows:
        return rows, stats

    def is_named(r: dict) -> bool:
        return _names_compaatible(r.get("content"))

    # Étape 1 : retirer les tweets isolés qui nomment Compaatible
    after_step1 = []
    for r in rows:
        if is_named(r) and not r.get("thread_key"):
            stats["dropped_isolated_mentions"] += 1
            continue
        after_step1.append(r)

    # Étape 2 : retirer les threads dont le T1 nomme Compaatible (thread entier)
    threads_to_drop = {
        r["thread_key"]
        for r in after_step1
        if is_named(r) and r.get("thread_order") == 1 and r.get("thread_key")
    }
    if threads_to_drop:
        stats["dropped_t1_threads"] = len(threads_to_drop)
        after_step2 = []
        for r in after_step1:
            if r.get("thread_key") in threads_to_drop:
                stats["dropped_t1_tweets"] += 1
                continue
            after_step2.append(r)
    else:
        after_step2 = after_step1

    # Étape 3 : plafond cumulé 15% sur tout le run (les chunks précédents
    # déjà insérés + le chunk en cours après étapes 1-2).
    existing_named, existing_total = (
        _count_existing_mentions(csv_run_id) if csv_run_id else (0, 0)
    )
    total = len(after_step2)
    if total > 0:
        named_indices = [i for i, r in enumerate(after_step2) if is_named(r)]
        chunk_named = len(named_indices)
        global_named = existing_named + chunk_named
        global_total = existing_total + total

        if global_total > 0 and global_named / global_total > plafond_cumule:
            # x = nombre de mentions à retirer DU CHUNK pour que
            # (global_named - x) / (global_total - x) ≤ plafond
            import math
            x_to_drop = max(
                0,
                math.ceil(
                    (global_named - plafond_cumule * global_total) / (1 - plafond_cumule)
                ),
            )
            x_to_drop = min(x_to_drop, chunk_named)
            indices_to_drop = set(named_indices[-x_to_drop:]) if x_to_drop > 0 else set()
            stats["dropped_excess_mentions"] = len(indices_to_drop)
            after_step3 = [r for i, r in enumerate(after_step2) if i not in indices_to_drop]
        else:
            after_step3 = after_step2
    else:
        after_step3 = after_step2

    # Renumérotation thread_order : combler les trous laissés par les drops T2+
    counters: dict[str, int] = {}
    for r in after_step3:
        tk = r.get("thread_key")
        if not tk:
            continue
        counters[tk] = counters.get(tk, 0) + 1
        r["thread_order"] = counters[tk]
    # Si un thread tombe à 1 tweet seul → dégradation en tweet isolé
    for r in after_step3:
        tk = r.get("thread_key")
        if tk and counters.get(tk, 0) == 1:
            r["thread_key"] = None
            r["thread_order"] = None

    final_total = len(after_step3)
    final_named = sum(1 for r in after_step3 if is_named(r))
    stats["final_total"] = final_total
    stats["final_named"] = final_named
    stats["final_ratio"] = (final_named / final_total) if final_total > 0 else 0.0
    # Cumul après ce chunk (utile pour le log enforce + audit)
    stats["cumulative_named"] = existing_named + final_named
    stats["cumulative_total"] = existing_total + final_total
    stats["cumulative_ratio"] = (
        stats["cumulative_named"] / stats["cumulative_total"]
        if stats["cumulative_total"] > 0
        else 0.0
    )
    return after_step3, stats


def _count_existing_mentions(csv_run_id: int) -> tuple[int, int]:
    """Compte (n_named_hors_url, n_total) parmi les tweets déjà insérés pour ce run.

    Source de vérité pour le plafond cumulé : on relit la DB à chaque chunk,
    car les chunks précédents peuvent inclure le run d'origine + des extensions
    chaînées sous le même csv_run_id.

    Implementation SQL : le strip d'URL + le check substring sont fait en base
    pour eviter de charger 1000+ contents en Python a chaque chunk. La regex SQL
    `https?://[^[:space:]]+` est l'equivalent POSIX de _URL_RE Python.
    """
    with db.cursor() as cur:
        # NB : `%%` echappe le `%` litteral dans psycopg2 (sinon il est confondu
        # avec un placeholder de parametre).
        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE LOWER(regexp_replace(COALESCE(content, ''),
                                                'https?://[^[:space:]]+',
                                                '',
                                                'g'))
                          LIKE '%%compaatible%%'
                ) AS named
            FROM mkt_tweets
            WHERE csv_run_id = %s
            """,
            (csv_run_id,),
        )
        row = cur.fetchone() or {}
    return int(row.get("named") or 0), int(row.get("total") or 0)


def _audit_compaatible_mentions(rows: list[dict], csv_run_id: int | None = None) -> None:
    """Log le ratio de tweets nommant 'Compaatible' et signale les violations de forme.

    Audite trois choses :
    - **Ratio cumulé sur le run** (vrai garde-fou) : plancher 5%, plafond 15%.
      Les mentions URL-only (`compaatible.com/...`) ne sont PAS comptées.
    - **Forme** : mention toujours en T2+ d'un thread (jamais T1, jamais isole).
    - **Position dans le chunk** : pas de grappe dans les 3 derniers tweets, pas
      de deux mentions dans la meme moitie. Voir le prompt copywriting pour la
      regle complete.

    Non bloquant : on n'altere pas les tweets, on log juste un warning si la
    regle est enfreinte. Loys peut decider de regenerer le chunk si besoin.
    """
    if not rows:
        return
    total = len(rows)
    indexed = list(enumerate(rows, 1))  # 1-based pour matcher l'ordre user-visible
    named_idx = [(i, r) for i, r in indexed if _names_compaatible(r.get("content"))]
    n_named = len(named_idx)
    ratio = n_named / total

    n_in_t1 = 0
    n_in_isolated = 0
    n_well_placed = 0
    for _, r in named_idx:
        tk = r.get("thread_key")
        order = r.get("thread_order")
        if not tk:
            n_in_isolated += 1
        elif order == 1:
            n_in_t1 += 1
        else:
            n_well_placed += 1

    # Cumulé sur le run (chunks précédents + ce chunk si déjà inséré). Le caller
    # appelle l'audit APRÈS l'insert, donc _count_existing_mentions reflète déjà
    # l'état post-chunk pour ce csv_run_id.
    cumul_named, cumul_total = (
        _count_existing_mentions(csv_run_id) if csv_run_id else (n_named, total)
    )
    cumul_ratio = cumul_named / cumul_total if cumul_total > 0 else 0.0

    _log(
        f"compaatible audit · {n_named}/{total} tweet(s) nomment Compaatible "
        f"({ratio*100:.1f}% chunk) · {n_well_placed} en T2+ d'un thread, "
        f"{n_in_t1} en T1 d'un thread, {n_in_isolated} en tweet isole · "
        f"cumul run {cumul_named}/{cumul_total} ({cumul_ratio*100:.1f}%)"
    )
    if cumul_total >= 20 and cumul_ratio < 0.05:
        _log(
            f"compaatible INFO · ratio cumulé {cumul_ratio*100:.1f}% < 5% sur le run · "
            "plancher non atteint, le modèle sous-place les mentions"
        )
    if cumul_ratio > 0.15:
        # Ne devrait plus jamais déclencher après _enforce_compaatible_rules.
        # Si ça arrive : bug de régulation.
        _log(
            f"compaatible WARN · ratio cumulé {cumul_ratio*100:.1f}% > 15% plafond "
            f"(post-régulation, sur {cumul_total} tweets du run) · anomalie, la régulation "
            "devrait avoir ramené le ratio sous le plafond"
        )
    if n_in_t1 or n_in_isolated:
        # Ne devrait plus jamais déclencher après _enforce_compaatible_rules.
        _log(
            f"compaatible WARN · {n_in_t1 + n_in_isolated} mention(s) hors-forme "
            "(T1 d'un thread ou tweet isole) restantes après régulation · anomalie"
        )

    # Audit de clustering (uniquement, pas de zone interdite). Une mention isolee
    # en queue de chunk n'est PAS un warning : si le tweet s'y pretait naturellement,
    # c'est OK. On signale uniquement les vrais regroupements visibles.
    if n_named >= 2 and total >= 6:
        positions = sorted(i for i, _ in named_idx)
        first_half = sum(1 for p in positions if p <= total / 2)
        second_half = n_named - first_half
        # 2+ mentions consecutives (X et X+1)
        consecutive = any(positions[k+1] - positions[k] == 1 for k in range(len(positions)-1))
        if consecutive:
            _log(
                f"compaatible WARN · mentions consecutives detectees aux positions {positions}/{total} · "
                "pas de respiration entre deux mentions"
            )
        # toutes du meme cote
        if first_half == 0 or second_half == 0:
            side = "premiere" if second_half == 0 else "seconde"
            _log(
                f"compaatible WARN · {n_named} mentions toutes dans la {side} moitie "
                f"(positions {positions}/{total}) · repartition desequilibree, le modele a probablement saute "
                "des opportunites plus naturelles plus tot/tard"
            )
