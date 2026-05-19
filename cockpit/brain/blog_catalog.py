"""Catalogue d'articles blog Compaatible exposé aux prompts copywriting.

Lecture seule sur la table `blog_articles` (règle absolue Loys : jamais
d'UPDATE/DELETE/DROP/ALTER sur les tables blog). Cache mémoire process
+ cache prompt Anthropic en aval pour amortir le coût.
"""
from __future__ import annotations
from functools import lru_cache

from brain import db


@lru_cache(maxsize=4)
def fetch_catalog(language: str = "fr") -> tuple[dict, ...]:
    """Retourne le catalogue complet des articles publiés pour la langue donnée.

    Tuple (immutable, hashable) pour autoriser lru_cache. Chaque entrée :
    {slug, title, excerpt, category}. Trié par date de publication décroissante
    (les plus récents d'abord, mais le LLM verra tout).
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT slug, title, excerpt, category "
            "FROM blog_articles "
            "WHERE is_published = TRUE AND language = %s "
            "ORDER BY published_at DESC NULLS LAST, id",
            (language,),
        )
        return tuple(dict(r) for r in cur.fetchall())


def format_for_prompt(catalog: tuple[dict, ...] | list[dict]) -> str:
    """Format compact pour injection prompt. Une ligne par article :
    `- /slug · [catégorie] Titre — excerpt (tronqué).`
    """
    if not catalog:
        return "(catalogue vide — pas d'articles disponibles pour cette langue)"
    lines = []
    for a in catalog:
        excerpt = (a.get("excerpt") or "").strip().replace("\n", " ")
        if len(excerpt) > 220:
            excerpt = excerpt[:217] + "…"
        cat = a.get("category") or "?"
        title = (a.get("title") or "").strip()
        lines.append(f"- /{a['slug']} · [{cat}] {title} — {excerpt}")
    return "\n".join(lines)


def valid_slugs(language: str = "fr") -> set[str]:
    """Set des slugs valides pour la langue donnée. Utilisé pour valider les URLs blog."""
    return {a["slug"] for a in fetch_catalog(language)}


def build_catalog_block(language: str = "fr") -> str:
    """Bloc texte complet prêt à mettre dans un message system caché."""
    catalog = fetch_catalog(language)
    header = (
        f"## CATALOGUE BLOG COMPAATIBLE — articles publiés ({language}, {len(catalog)} entrées)\n\n"
        "Base d'URL : `https://compaatible.com/blog/{slug}`.\n"
        "Tu peux pointer vers un de ces articles quand un tweet, un thread ou une scène "
        "touche naturellement à un thème approfondi ici. Les slugs ci-dessous existent — "
        "n'invente jamais de slug, ça donne un lien mort.\n\n"
    )
    return header + format_for_prompt(catalog)
