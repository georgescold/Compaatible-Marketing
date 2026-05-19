"""Parseur tolérant des CSV uploadés par l'utilisateur.

Le format typique est l'export Cortex (scrape) qui contient à la fois les colonnes Cortex
(content, media_url, scheduled_at, thread_key) ET les stats (likes, retweets, views, etc.).

On accepte aussi d'autres formats du moment qu'il y a au moins une colonne `content` (ou
`text` ou `tweet`) identifiable.
"""
from __future__ import annotations
import csv
import io
import re
from collections import Counter
from typing import Any


CONTENT_ALIASES = ["content", "text", "tweet", "tweets", "message", "body"]


def safe_int(v) -> int:
    """Conversion tolérante d'un champ CSV en entier.

    Les CSV scrappés contiennent souvent des cellules désalignées (guillemet mal
    échappé qui décale les colonnes) : un fragment de tweet peut atterrir dans
    une colonne `likes`/`retweets`/`views`. On retourne 0 plutôt que de crasher.
    """
    if v is None:
        return 0
    try:
        return int(float(str(v).replace(",", ".").strip() or 0))
    except (TypeError, ValueError):
        return 0


def safe_float(v) -> float:
    """Idem safe_int, version float. Strip '%' pour engagement_rate type '4.2%'."""
    if v is None:
        return 0.0
    try:
        return float(str(v).rstrip("%").replace(",", ".").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_csv(file_bytes: bytes) -> dict[str, Any]:
    """Parse un CSV uploadé. Retourne :
    {
      "rows": [dict, ...],
      "columns": [str],
      "content_column": str,
      "total_rows": int,
      "valid_rows": int,         # avec content non vide
      "detected_language": str,
      "source_handle": str | None,
      "warnings": [str],
    }
    """
    warnings: list[str] = []

    # Détecter encoding (BOM UTF-8 toléré)
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = file_bytes.decode("latin-1")
            warnings.append("Encoding latin-1 détecté (préfère UTF-8 pour éviter les artefacts).")
        except UnicodeDecodeError:
            raise ValueError("Encoding non supporté. Convertis le fichier en UTF-8.")

    # Détecter le séparateur (virgule ou point-virgule)
    sample = text[:4096]
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel  # fallback : virgule

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = list(reader)

    if not rows:
        raise ValueError("CSV vide ou sans header.")

    columns = list(rows[0].keys())

    # Trouver la colonne content
    content_col = None
    for alias in CONTENT_ALIASES:
        for c in columns:
            if c and c.strip().lower() == alias:
                content_col = c
                break
        if content_col:
            break

    if not content_col:
        raise ValueError(
            f"Aucune colonne de contenu trouvée. Aliases recherchés : {CONTENT_ALIASES}. "
            f"Colonnes présentes : {columns}"
        )

    # Filtrer les lignes vides (content vide)
    valid_rows = [r for r in rows if (r.get(content_col) or "").strip()]
    if len(valid_rows) < len(rows):
        warnings.append(f"{len(rows) - len(valid_rows)} ligne(s) sans content ignorées.")

    # Détecter handle source (si colonne handle ou username)
    handle = None
    for c in ["handle", "username", "user", "author"]:
        for col in columns:
            if col and col.strip().lower() == c:
                handles = [r.get(col, "").strip().lstrip("@") for r in valid_rows if r.get(col)]
                if handles:
                    most_common = Counter(handles).most_common(1)[0][0]
                    handle = most_common
                break
        if handle:
            break

    # Détecter langue dominante (heuristique simple, on demandera à l'IA pour confirmer)
    detected_lang = detect_language_simple([r[content_col] for r in valid_rows[:50]])

    return {
        "rows": valid_rows,
        "columns": columns,
        "content_column": content_col,
        "total_rows": len(rows),
        "valid_rows": len(valid_rows),
        "detected_language": detected_lang,
        "source_handle": handle,
        "warnings": warnings,
    }


# Mots fréquents par langue (~30 mots les + courants)
_LANG_KEYWORDS = {
    "fr": {"le", "la", "les", "de", "que", "et", "à", "un", "une", "il", "elle", "tu", "je", "nous", "vous",
           "pas", "qui", "dans", "pour", "avec", "sur", "ce", "cette", "mais", "ou", "où", "est", "sont", "j'ai",
           "tout", "c'est", "tweet", "moi"},
    "en": {"the", "and", "to", "of", "a", "in", "is", "it", "you", "that", "for", "on", "are", "as", "with",
           "his", "they", "be", "at", "this", "have", "from", "i", "we", "but", "not", "what", "all", "were"},
    "es": {"el", "la", "los", "las", "de", "que", "y", "a", "en", "un", "una", "es", "se", "no", "con",
           "por", "para", "como", "más", "pero", "su", "te", "le", "lo", "yo", "tú", "mi", "tu", "está", "esto"},
}


def detect_language_simple(texts: list[str]) -> str:
    counter = {"fr": 0, "en": 0, "es": 0}
    for t in texts:
        words = re.findall(r"\b[\w']+\b", t.lower())
        for lang, kws in _LANG_KEYWORDS.items():
            counter[lang] += sum(1 for w in words if w in kws)
    if all(v == 0 for v in counter.values()):
        return "unknown"
    return max(counter, key=counter.get)


def compute_engagement_stats(rows: list[dict], content_col: str) -> dict[str, Any]:
    """Calcule stats engagement si les colonnes existent."""
    likes = [safe_int(r.get("likes", 0)) for r in rows]
    rts = [safe_int(r.get("retweets", 0)) for r in rows]
    views = [safe_int(r.get("views", 0)) for r in rows]
    engagement = [safe_int(r.get("engagement", 0)) for r in rows]

    def median(lst):
        if not lst:
            return 0
        s = sorted(lst)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2

    content_lengths = [len((r.get(content_col) or "")) for r in rows]
    return {
        "tweets_count": len(rows),
        "likes_total": sum(likes),
        "likes_median": median([x for x in likes if x > 0] or [0]),
        "likes_max": max(likes) if likes else 0,
        "retweets_total": sum(rts),
        "views_total": sum(views),
        "has_engagement_data": any(x > 0 for x in likes),
        "length_chars_median": median(content_lengths or [0]),
        "length_chars_max": max(content_lengths or [0]),
    }


_MENTION_RE = re.compile(r"@[A-Za-z0-9_]{1,15}")
_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def is_tag_spam(text: str) -> bool:
    """Heuristique : True si le tweet est majoritairement une liste de @mentions.

    Cas typique à bannir : "@user1 @user2 @user3 @user4 thanks!", export de replies
    automatiques d'engagement, listes de tagging mutuel. Pas un vrai contenu éditorial.

    Critères : au moins 3 mentions, et les mentions représentent ≥ 50% des mots.
    Tweet trop court (<5 chars) considéré non-spam (laissera passer, sera filtré ailleurs).
    """
    if not text:
        return False
    text = text.strip()
    if len(text) < 5:
        return False
    mentions = _MENTION_RE.findall(text)
    if len(mentions) < 3:
        return False
    words = _WORD_RE.findall(text)
    if not words:
        return True
    return len(mentions) / len(words) >= 0.5


def validate_csv_health(parsed: dict) -> dict:
    """Diagnostic structurel du CSV après parse. Détecte les CSV inexploitables.

    Vérifie :
    - Volume minimum (>= 5 lignes utiles après filtrage)
    - Proportion de tag-spam (listes de mentions sans contenu éditorial)
    - Longueur moyenne plausible
    - Taux de doublons
    - Overflow 280 chars (signal possiblement hors-Twitter)

    Retourne :
        {
            "warnings": list[str],        — à afficher à l'user, non-bloquants
            "fatal_errors": list[str],    — bloquent le pipeline (PipelineError)
            "stats": dict,                — métriques calculées
            "filtered_rows": list[dict],  — rows utilisables (tag-spam retiré)
        }
    """
    rows = parsed.get("rows", [])
    content_col = parsed.get("content_column")
    warnings: list[str] = []
    fatal_errors: list[str] = []

    n_total = len(rows)
    if n_total == 0:
        fatal_errors.append("0 ligne valide dans le CSV (content vide ou colonne content introuvable).")
        return {"warnings": warnings, "fatal_errors": fatal_errors, "stats": {}, "filtered_rows": []}

    # 1. Filtrage tag-spam
    tag_spam_count = 0
    filtered_rows = []
    for r in rows:
        content = (r.get(content_col) or "").strip()
        if is_tag_spam(content):
            tag_spam_count += 1
        else:
            filtered_rows.append(r)
    tag_spam_rate = tag_spam_count / n_total

    if tag_spam_rate >= 0.3:
        fatal_errors.append(
            f"{tag_spam_count}/{n_total} tweets ({tag_spam_rate:.0%}) sont des listes de mentions "
            "@utilisateur (pas de contenu éditorial). Le CSV ressemble à un export de tag-spam, "
            "pas à une base de tweets exploitable. Vérifie que tu as bien exporté les tweets du "
            "compte, pas ses replies d'engagement automatique."
        )
    elif tag_spam_rate > 0.05:
        warnings.append(
            f"{tag_spam_count} tweets ({tag_spam_rate:.0%}) ressemblent à des listes de mentions. "
            "Filtrés automatiquement (non envoyés au pipeline)."
        )

    # 2. Volume minimum après filtrage
    if len(filtered_rows) < 5:
        fatal_errors.append(
            f"Seulement {len(filtered_rows)} tweets exploitables après filtrage. "
            "Trop peu pour analyser un compte (minimum 5)."
        )

    # 3. Longueurs
    contents = [(r.get(content_col) or "").strip() for r in filtered_rows]
    avg_len = (sum(len(c) for c in contents) / len(contents)) if contents else 0
    if contents and avg_len < 20:
        warnings.append(
            f"Longueur moyenne des tweets : {avg_len:.0f} chars (très courte). "
            "Vérifie que la colonne content est bien la bonne, ou que ce ne sont pas des handles."
        )

    # 4. Doublons
    unique_contents = set(contents)
    duplicate_rate = 1 - (len(unique_contents) / len(contents)) if contents else 0
    if duplicate_rate > 0.3:
        warnings.append(
            f"{duplicate_rate:.0%} de tweets dupliqués dans le CSV. "
            "Beaucoup de répétitions, l'adaptation risque d'être pauvre."
        )

    # 5. Overflow 280 (signal hors-Twitter possible)
    overflow = sum(1 for c in contents if len(c) > 280)
    if contents and overflow / len(contents) > 0.3:
        warnings.append(
            f"{overflow}/{len(contents)} tweets > 280 chars. Source possiblement hors Twitter "
            "(Threads, Bluesky, blog). Pas grave, juste signal — l'adaptation forcera ≤ 280."
        )

    # 6. Handle source unique
    if not parsed.get("source_handle"):
        warnings.append(
            "Handle source non détecté dans le CSV (colonne handle/username/user/author absente "
            "ou vide). Le pipeline continuera mais la persona ne pourra pas hériter d'un compte précis."
        )

    stats = {
        "total_rows_input": n_total,
        "tag_spam_count": tag_spam_count,
        "tag_spam_rate": round(tag_spam_rate, 3),
        "kept_rows": len(filtered_rows),
        "avg_length": round(avg_len, 1),
        "duplicate_rate": round(duplicate_rate, 3),
        "overflow_280": overflow,
    }

    return {
        "warnings": warnings,
        "fatal_errors": fatal_errors,
        "stats": stats,
        "filtered_rows": filtered_rows,
    }


def top_n_by_engagement(rows: list[dict], n: int = 50) -> list[dict]:
    """Retourne les top N tweets par engagement_rate (ou likes si rate absent)."""
    def score(r):
        # Préférer engagement_rate si dispo, sinon likes
        if r.get("engagement_rate"):
            return safe_float(r["engagement_rate"])
        return safe_int(r.get("likes", 0))

    return sorted(rows, key=score, reverse=True)[:n]


def bottom_n_by_engagement(rows: list[dict], n: int = 20, min_views: int = 100) -> list[dict]:
    """Retourne les N tweets avec engagement très faible (mais avec un minimum de views pour exclure les non-vus)."""
    # Garder uniquement les tweets vus mais peu engagés
    seen = [r for r in rows if safe_int(r.get("views", 0)) >= min_views]
    if not seen:
        return []

    def score(r):
        if r.get("engagement_rate"):
            return safe_float(r["engagement_rate"])
        return safe_int(r.get("likes", 0))

    return sorted(seen, key=score)[:n]


def sample_random(rows: list[dict], n: int = 20, seed: int = 42) -> list[dict]:
    import random
    if n >= len(rows):
        return rows
    r = random.Random(seed)
    return r.sample(rows, n)
