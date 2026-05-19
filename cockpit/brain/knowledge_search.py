"""Recherche full-text dans les .md de Knowledges/.

Pour ~285 KB de texte total, le scan brut Python est instantané. Pas besoin de ripgrep
ou d'indexation. On retourne les matches avec un contexte ±100 chars autour.
"""
from __future__ import annotations
import re
from pathlib import Path

from config import Config


CONTEXT_CHARS = 120


def list_files() -> list[dict]:
    if not Config.KNOWLEDGE_DIR.exists():
        return []
    out = []
    for p in sorted(Config.KNOWLEDGE_DIR.glob("*.md")):
        out.append({
            "name": p.name,
            "size_kb": p.stat().st_size // 1024,
        })
    return out


def search(query: str, file_filter: str | None = None, max_results: int = 100) -> list[dict]:
    """Cherche `query` (case-insensitive) dans les .md. Retourne une liste de matches :
    [{
      "file": "00-MASTER-KB.md",
      "line": 12,
      "snippet_before": "...",
      "match": "query_text",
      "snippet_after": "...",
    }, ...]
    """
    q = query.strip()
    if not q:
        return []

    pattern = re.compile(re.escape(q), re.IGNORECASE)
    results: list[dict] = []

    files = Config.KNOWLEDGE_DIR.glob("*.md")
    for path in sorted(files):
        if file_filter and path.name != file_filter:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        for m in pattern.finditer(text):
            start = max(0, m.start() - CONTEXT_CHARS)
            end = min(len(text), m.end() + CONTEXT_CHARS)
            snippet = text[start:end]

            # Numéro de ligne approximatif
            line_num = text[: m.start()].count("\n") + 1

            results.append({
                "file": path.name,
                "line": line_num,
                "snippet_before": text[start : m.start()].replace("\n", " "),
                "match": text[m.start() : m.end()],
                "snippet_after": text[m.end() : end].replace("\n", " "),
            })

            if len(results) >= max_results:
                return results

    return results


def read_file_excerpt(filename: str, start_line: int = 1, lines: int = 200) -> str:
    """Renvoie un extrait du fichier autour d'une ligne donnée."""
    path = Config.KNOWLEDGE_DIR / filename
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    all_lines = text.splitlines()
    start = max(0, start_line - 1)
    return "\n".join(all_lines[start : start + lines])
