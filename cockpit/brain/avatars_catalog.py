"""Catalogue des 11 avatars Compaatible.

Parse `Compaatible/Avatars Compaatible.md` au démarrage et expose une liste
structurée pour les dropdowns UI + l'injection dans les prompts manuels.

Source de vérité : le fichier markdown. Cache lru pour éviter de re-parser.
"""
from __future__ import annotations
import re
from functools import lru_cache

from config import PROJECT_ROOT


_AVATAR_HEADER_RE = re.compile(
    r"^##\s*AVATAR\s+(\d+)\s*:\s*(.+?)\s*$",
    re.MULTILINE,
)
_QUI_CEST_RE = re.compile(
    r"^\*\*Qui c'est\s*:?\*\*\s*:?\s*(.+?)$",
    re.MULTILINE,
)


def _strip_md(text: str) -> str:
    """Nettoie quelques marqueurs markdown pour un affichage UI propre."""
    text = re.sub(r"\\([\\\-_])", r"\1", text)  # escape backslashes
    text = text.replace("**", "").strip()
    return text


@lru_cache(maxsize=1)
def list_avatars() -> list[dict]:
    """Retourne [{id, name, tagline, qui_cest_summary, full_block}] pour les 11 avatars.

    `full_block` = section markdown complète de l'avatar (sert au prompt LLM).
    `qui_cest_summary` = première phrase de "Qui c'est" (sert à la dropdown UI).
    """
    path = PROJECT_ROOT / "Compaatible" / "Avatars Compaatible.md"
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    headers = list(_AVATAR_HEADER_RE.finditer(text))
    avatars: list[dict] = []

    for i, m in enumerate(headers):
        avatar_id = int(m.group(1))
        name = _strip_md(m.group(2))
        start = m.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[start:end].strip()

        # Première phrase de "Qui c'est" pour résumé UI court
        qui = _QUI_CEST_RE.search(block)
        summary = _strip_md(qui.group(1)) if qui else ""
        # On garde la 1ère phrase seulement (jusqu'au premier point)
        if summary:
            first_period = summary.find(".")
            if first_period > 0:
                summary = summary[:first_period + 1]
            summary = summary.strip()

        avatars.append({
            "id": avatar_id,
            "name": name,
            "tagline": name,  # alias UI
            "summary": summary,
            "full_block": block,
        })

    return avatars


def get_avatar(avatar_id: int) -> dict | None:
    """Retourne l'avatar par id (1-11) ou None."""
    for a in list_avatars():
        if a["id"] == avatar_id:
            return a
    return None


def get_avatars_brief() -> list[dict]:
    """Version légère pour les dropdowns : [{id, name, summary}]."""
    return [{"id": a["id"], "name": a["name"], "summary": a["summary"]} for a in list_avatars()]
