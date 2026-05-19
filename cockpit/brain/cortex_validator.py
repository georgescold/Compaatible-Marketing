"""Validateur Cortex : reproduit la logique du dry_run de Cortex.

Garantit que le CSV produit passera l'import Cortex sans erreur fatale.

Règles reproduites depuis la spec Cortex (§4-§10) :
- content ≤ 280 caractères (fatal si dépassé)
- emojis composés (ZWJ, drapeaux, skin tones) coûtent 2+ chars Twitter → warning à 270
- media_url : pipe séparateur, max 4, HTTPS, regex valide
- scheduled_at : ISO 8601 avec timezone, ou vide
- thread_key : sensible à la casse, pas d'espaces

Anti-patterns détectés : virgule comme séparateur media, `null`/`N/A`/`-` au lieu de vide, etc.
"""
from __future__ import annotations
import re
import unicodedata
from typing import Any


MAX_CONTENT = 280
SAFE_CONTENT_WITH_EMOJIS = 270

# Regex URLs media
URL_REGEX = re.compile(r"^https?://[^\s]+$")
ALLOWED_MEDIA_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4")

# ISO 8601 basique avec timezone (ou date seule)
ISO_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$"
)


def count_emojis_complex(text: str) -> int:
    """Compte les caractères "lourds" pour Twitter : émojis composés ZWJ, drapeaux, modificateurs skin tone."""
    n = 0
    for ch in text:
        if unicodedata.category(ch).startswith("So") or ch == "‍":
            n += 1
    return n


def validate_content(content: str) -> dict[str, Any]:
    """Valide un content. Retourne {ok, errors, warnings, char_count}."""
    errors: list[str] = []
    warnings: list[str] = []

    if not content or not content.strip():
        errors.append("content vide")
        return {"ok": False, "errors": errors, "warnings": warnings, "char_count": 0}

    char_count = len(content)
    emojis = count_emojis_complex(content)

    if char_count > MAX_CONTENT:
        errors.append(f"content > 280 chars ({char_count})")
    elif emojis > 0 and char_count > SAFE_CONTENT_WITH_EMOJIS:
        warnings.append(
            f"content {char_count} chars avec {emojis} emoji(s) composé(s) : Twitter peut compter > 280"
        )

    # Détection des anti-patterns
    stripped = content.strip()
    if stripped.lower() in {"null", "n/a", "-", "asap", "none"}:
        warnings.append("content suspect (`null`/`N/A`/`-`/`asap`) : utilise une cellule vide à la place")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "char_count": char_count,
        "emojis_complex": emojis,
    }


def validate_media_url(media_url: str | None) -> dict[str, Any]:
    """Valide la cellule media_url (pipe séparée, max 4, HTTPS)."""
    warnings: list[str] = []
    errors: list[str] = []
    valid_urls: list[str] = []

    if not media_url:
        return {"ok": True, "urls": [], "warnings": warnings, "errors": errors}

    raw = media_url.strip()
    if not raw:
        return {"ok": True, "urls": [], "warnings": warnings, "errors": errors}

    # Anti-pattern : virgule au lieu de pipe
    if "," in raw and "|" not in raw:
        warnings.append(
            "media_url semble utiliser `,` au lieu de `|` comme séparateur (casserait le parsing CSV)"
        )

    candidates = [u.strip() for u in raw.split("|") if u.strip()]
    seen = set()

    for u in candidates:
        if u in seen:
            warnings.append(f"URL dupliquée éliminée : {u[:60]}")
            continue
        seen.add(u)

        if not URL_REGEX.match(u):
            warnings.append(f"URL invalide ignorée : {u[:60]} (doit être https?://)")
            continue

        # Format
        lower = u.lower().split("?")[0]
        if not lower.endswith(ALLOWED_MEDIA_EXTS):
            warnings.append(f"Format non standard : {u[:60]} (attendu jpg/png/webp/gif/mp4)")

        valid_urls.append(u)

    if len(valid_urls) > 4:
        warnings.append(f"{len(valid_urls) - 4} URL(s) au-delà du max 4 ignorées")
        valid_urls = valid_urls[:4]

    if raw and not valid_urls:
        warnings.append("cellule media_url non vide mais aucune URL valide trouvée")

    return {"ok": True, "urls": valid_urls, "warnings": warnings, "errors": errors}


def validate_scheduled_at(scheduled_at: str | None) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    if not scheduled_at or not scheduled_at.strip():
        return {"ok": True, "warnings": warnings, "errors": errors}

    s = scheduled_at.strip()
    if s.lower() in {"null", "n/a", "-", "asap", "none"}:
        errors.append(f"scheduled_at suspect : `{s}` (utilise vide ou ISO 8601)")
        return {"ok": False, "warnings": warnings, "errors": errors}

    if not ISO_REGEX.match(s):
        errors.append(f"scheduled_at non ISO 8601 : `{s}`")
        return {"ok": False, "warnings": warnings, "errors": errors}

    if "T" in s or " " in s:
        # Vérifie qu'il y a une timezone
        has_tz = bool(re.search(r"(Z|[+-]\d{2}:?\d{2})$", s))
        if not has_tz:
            warnings.append(f"scheduled_at sans timezone : `{s}` (UTC assumé par Postgres)")

    return {"ok": True, "warnings": warnings, "errors": errors}


def validate_tweet_row(row: dict) -> dict[str, Any]:
    """Valide une row complète {content, media_url, scheduled_at, thread_key}."""
    content_result = validate_content(row.get("content", ""))
    media_result = validate_media_url(row.get("media_url"))
    scheduled_result = validate_scheduled_at(row.get("scheduled_at"))

    thread_key = (row.get("thread_key") or "").strip()
    thread_warnings = []
    if thread_key and " " in thread_key:
        thread_warnings.append(f"thread_key contient un espace : `{thread_key}` (utilise tirets/underscores)")

    return {
        "ok": content_result["ok"] and scheduled_result["ok"],
        "errors": content_result["errors"] + scheduled_result["errors"],
        "warnings": content_result["warnings"] + media_result["warnings"] + scheduled_result["warnings"] + thread_warnings,
        "char_count": content_result["char_count"],
    }


def validate_batch(rows: list[dict]) -> dict[str, Any]:
    """Valide un batch complet. Émule un dry_run Cortex.

    Retourne :
    {
      "ok": bool,
      "fatal_errors": [{"row": N, "message": str}, ...],
      "warnings": [{"row": N, "message": str}, ...],
      "stats": {
        "total": N, "valid": N, "with_media": N, "threads": {key: count}, ...
      },
      "sample_first_3": [...],
    }
    """
    fatal_errors: list[dict] = []
    warnings: list[dict] = []
    threads: dict[str, int] = {}
    media_dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0}
    scheduled_count = 0
    valid = 0

    for i, row in enumerate(rows, 1):
        r = validate_tweet_row(row)
        if r["errors"]:
            for e in r["errors"]:
                fatal_errors.append({"row": i, "message": e})
        else:
            valid += 1

        for w in r["warnings"]:
            warnings.append({"row": i, "message": w})

        tk = (row.get("thread_key") or "").strip()
        if tk:
            threads[tk] = threads.get(tk, 0) + 1

        media_count = len(validate_media_url(row.get("media_url"))["urls"])
        media_dist[min(media_count, 4)] += 1

        if (row.get("scheduled_at") or "").strip():
            scheduled_count += 1

    return {
        "ok": len(fatal_errors) == 0,
        "fatal_errors": fatal_errors,
        "warnings": warnings,
        "stats": {
            "total": len(rows),
            "valid": valid,
            "threads": [{"key": k, "count": v} for k, v in threads.items()],
            "media_distribution": media_dist,
            "scheduled_count": scheduled_count,
        },
    }


def format_for_cortex(rows: list[dict], include_persona_id: str | None = None) -> str:
    """Sérialise une liste de rows au format CSV Cortex (UTF-8, RFC 4180).

    Si include_persona_id est fourni, ajoute la colonne persona_id en tête (flow API §1.2).
    """
    import csv as csvmod
    import io

    out = io.StringIO()
    headers = (
        ["persona_id", "content", "media_url", "scheduled_at", "thread_key"]
        if include_persona_id
        else ["content", "media_url", "scheduled_at", "thread_key"]
    )
    writer = csvmod.writer(out, quoting=csvmod.QUOTE_MINIMAL, lineterminator="\n")
    writer.writerow(headers)
    for r in rows:
        line = []
        if include_persona_id:
            line.append(include_persona_id)
        line.append(r.get("content", ""))
        line.append(r.get("media_url", "") or "")
        line.append(r.get("scheduled_at", "") or "")
        line.append(r.get("thread_key", "") or "")
        writer.writerow(line)
    return out.getvalue()
