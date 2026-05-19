"""Dashboard stats par run : mentions Compaatible, distributions, structure narrative.

Lit la DB (mkt_tweets + mkt_csv_runs) pour un csv_run_id donne et produit
un dict de stats. Deux renderers fournis :
- format_text() : bloc ASCII pour la console (lancer-cockpit.bat)
- les memes stats sont aussi consommees par le template Jinja de la page run

Les accents sont volontairement omis dans format_text() car la console Windows
utilisee par Loys (cp1252) ne les rend pas fiablement (cf. logs cockpit).
"""
from __future__ import annotations
import re
from collections import Counter
from typing import Any

from brain import db
from brain.copywriter import _names_compaatible, _URL_RE


_BLOG_URL_RE = re.compile(r"https?://compaatible\.com/blog/", re.IGNORECASE)
_COMPAATIBLE_DOMAIN_RE = re.compile(r"https?://compaatible\.com", re.IGNORECASE)


def build(csv_run_id: int) -> dict[str, Any]:
    """Collecte toutes les stats du run pour affichage dashboard.

    Retourne un dict avec sous-objets : mentions, threads, distribution,
    content, et meta (cost/duration). Si le run n'a aucun tweet, retourne
    {"empty": True, "csv_run_id": ...}.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT content, thread_key, thread_order, hook_pattern,
                   adaptation_level, integration_strategy, needs_image,
                   char_count, extension_idx, source_lang, media_url, status
            FROM mkt_tweets
            WHERE csv_run_id = %s
            ORDER BY id
            """,
            (csv_run_id,),
        )
        tweets = cur.fetchall()

        cur.execute(
            """
            SELECT cost_usd, started_at, completed_at, output_tweets_count
            FROM mkt_csv_runs WHERE id = %s
            """,
            (csv_run_id,),
        )
        run = cur.fetchone()

    if not tweets:
        return {"empty": True, "csv_run_id": csv_run_id}

    total = len(tweets)

    # ---------- Mentions Compaatible ----------
    # Catégories disjointes :
    # - text     : "Compaatible" hors URL (compté dans le plafond 15%)
    # - url_blog : tweet qui ne nomme pas Compaatible dans le texte mais inclut
    #              une URL https://compaatible.com/blog/...  (le "blog ne compte pas")
    # - url_other : URL compaatible.com hors /blog/ sans mention texte (rare)
    mentions_text = 0
    mentions_url_blog = 0
    mentions_url_other = 0
    for t in tweets:
        content = t.get("content") or ""
        has_text_mention = _names_compaatible(content)
        if has_text_mention:
            mentions_text += 1
        else:
            if _BLOG_URL_RE.search(content):
                mentions_url_blog += 1
            elif _COMPAATIBLE_DOMAIN_RE.search(content):
                mentions_url_other += 1

    ratio_text = mentions_text / total if total else 0.0

    # ---------- Structure narrative (threads vs isoles) ----------
    thread_keys = [t.get("thread_key") for t in tweets if t.get("thread_key")]
    thread_counter = Counter(thread_keys)
    n_threads = len(thread_counter)
    n_thread_tweets = sum(thread_counter.values())
    n_isolated = total - n_thread_tweets
    avg_thread_size = (n_thread_tweets / n_threads) if n_threads else 0.0
    max_thread_size = max(thread_counter.values()) if thread_counter else 0

    # ---------- Distributions ----------
    hooks = Counter(t.get("hook_pattern") for t in tweets if t.get("hook_pattern"))
    adaptations = Counter(t.get("adaptation_level") for t in tweets if t.get("adaptation_level"))
    integrations = Counter((t.get("integration_strategy") or "none") for t in tweets)
    languages = Counter((t.get("source_lang") or "(inconnu)") for t in tweets)
    extensions = Counter((t.get("extension_idx") if t.get("extension_idx") is not None else 0) for t in tweets)
    statuses = Counter((t.get("status") or "draft") for t in tweets)

    # ---------- Contenu ----------
    chars = [int(t.get("char_count") or 0) for t in tweets]
    total_chars = sum(chars)
    avg_chars = total_chars / total if total else 0
    over_280 = sum(1 for c in chars if c > 280)
    needs_image = sum(1 for t in tweets if t.get("needs_image"))
    has_media = sum(1 for t in tweets if t.get("media_url"))

    # ---------- Run meta ----------
    cost_usd = float(run.get("cost_usd") or 0) if run else 0.0
    duration_seconds = None
    if run and run.get("started_at") and run.get("completed_at"):
        try:
            duration_seconds = (run["completed_at"] - run["started_at"]).total_seconds()
        except Exception:
            duration_seconds = None

    return {
        "empty": False,
        "csv_run_id": csv_run_id,
        "total": total,
        "mentions": {
            "text": mentions_text,
            "ratio_text": ratio_text,
            "url_blog": mentions_url_blog,
            "url_other": mentions_url_other,
            "total_url_only": mentions_url_blog + mentions_url_other,
            "total_any": mentions_text + mentions_url_blog + mentions_url_other,
        },
        "threads": {
            "count": n_threads,
            "tweets_in_threads": n_thread_tweets,
            "isolated": n_isolated,
            "avg_size": avg_thread_size,
            "max_size": max_thread_size,
        },
        "distribution": {
            "hook_pattern": hooks.most_common(),
            "adaptation_level": adaptations.most_common(),
            "integration_strategy": integrations.most_common(),
            "source_lang": languages.most_common(),
            "extension_idx": sorted(extensions.items()),
            "status": statuses.most_common(),
        },
        "content": {
            "total_chars": total_chars,
            "avg_chars": avg_chars,
            "over_280": over_280,
            "needs_image": needs_image,
            "has_media": has_media,
        },
        "cost_usd": cost_usd,
        "duration_seconds": duration_seconds,
    }


def format_text(stats: dict[str, Any], width: int = 72) -> str:
    """Rend les stats en bloc ASCII pour la console.

    ASCII-safe (pas d'accents, pas d'Unicode au-dela du Latin-1 de base) car
    la console Windows par defaut sur la machine de Loys est en cp1252.
    """
    if stats.get("empty"):
        return f"[dashboard] Run #{stats['csv_run_id']} : aucun tweet"

    total = stats["total"]
    lines: list[str] = []

    def hr(char: str = "=") -> str:
        return char * width

    def kv(label: str, value: str, indent: int = 2) -> str:
        pad = " " * indent
        col = width - indent - len(value)
        if col < len(label) + 1:
            return f"{pad}{label} {value}"
        return f"{pad}{label:<{col}s}{value}"

    def bar(pct: float, max_chars: int = 24) -> str:
        n = int(round(pct / 100 * max_chars))
        n = max(0, min(max_chars, n))
        return "#" * n

    def fmt_dist(items: list[tuple], top: int = 10) -> list[str]:
        if not items:
            return ["    (aucune donnee)"]
        out = []
        # Largeur de la 1ere colonne dynamique (cap a 28)
        col_w = min(28, max((len(str(k)) for k, _ in items[:top]), default=8))
        for k, v in items[:top]:
            pct = v / total * 100
            key = str(k)
            out.append(f"    {key:<{col_w}s}  {v:>4d}  {pct:>5.1f}%  {bar(pct)}")
        return out

    lines.append(hr("="))
    lines.append(f"  DASHBOARD - Run #{stats['csv_run_id']} - {total} tweets")
    lines.append(hr("="))

    # ---------- Mentions ----------
    m = stats["mentions"]
    lines.append("")
    lines.append("MENTIONS COMPAATIBLE")
    lines.append(hr("-"))
    lines.append(kv("Texte (comptees dans plafond 15%)",
                    f"{m['text']:>4d}  ({m['ratio_text']*100:>5.1f}%)"))
    lines.append(kv("URL blog seule  (NON comptees)",
                    f"{m['url_blog']:>4d}"))
    lines.append(kv("URL compaatible.com hors blog",
                    f"{m['url_other']:>4d}"))
    lines.append(kv("TOTAL mentions visibles (texte + URLs)",
                    f"{m['total_any']:>4d}"))
    if m["ratio_text"] > 0.15:
        lines.append(kv(">> WARN : ratio texte au-dessus du plafond 15%",
                        f"{m['ratio_text']*100:.1f}%"))

    # ---------- Threads ----------
    th = stats["threads"]
    lines.append("")
    lines.append("STRUCTURE NARRATIVE")
    lines.append(hr("-"))
    lines.append(kv("Threads",
                    f"{th['count']:>4d}  ({th['tweets_in_threads']} tweets, moy {th['avg_size']:.1f}, max {th['max_size']})"))
    lines.append(kv("Tweets isoles",
                    f"{th['isolated']:>4d}"))

    # ---------- Distributions ----------
    d = stats["distribution"]
    lines.append("")
    lines.append("HOOK PATTERN")
    lines.append(hr("-"))
    lines.extend(fmt_dist(d["hook_pattern"]))

    lines.append("")
    lines.append("ADAPTATION LEVEL  (rewritten_in_voice / light_polish / ...)")
    lines.append(hr("-"))
    lines.extend(fmt_dist(d["adaptation_level"]))

    lines.append("")
    lines.append("INTEGRATION STRATEGY  (none / blog_pivot / direct_mention / ...)")
    lines.append(hr("-"))
    lines.extend(fmt_dist(d["integration_strategy"]))

    if len(d["source_lang"]) > 1:
        lines.append("")
        lines.append("LANGUE SOURCE")
        lines.append(hr("-"))
        lines.extend(fmt_dist(d["source_lang"]))

    # Extension origin si pertinent (run + extensions)
    if len(d["extension_idx"]) > 1:
        lines.append("")
        lines.append("ORIGINE (extension 0 = run initial)")
        lines.append(hr("-"))
        labelled = [(f"extension {k}" if k else "run initial", v) for k, v in d["extension_idx"]]
        lines.extend(fmt_dist(labelled))

    # ---------- Contenu ----------
    c = stats["content"]
    lines.append("")
    lines.append("CONTENU")
    lines.append(hr("-"))
    lines.append(kv("Total caracteres",         f"{c['total_chars']:>6d}"))
    lines.append(kv("Moyenne / tweet",          f"{c['avg_chars']:>6.0f} chars"))
    lines.append(kv("Tweets > 280 (anomalie)",  f"{c['over_280']:>6d}"))
    lines.append(kv("Tweets needs_image",       f"{c['needs_image']:>6d}"))
    lines.append(kv("Tweets avec media_url",    f"{c['has_media']:>6d}"))

    # ---------- Run meta ----------
    lines.append("")
    lines.append("RUN")
    lines.append(hr("-"))
    lines.append(kv("Cout total",  f"${stats['cost_usd']:.4f}"))
    if stats.get("duration_seconds"):
        dur = int(stats["duration_seconds"])
        m_, s_ = divmod(dur, 60)
        h_, m_ = divmod(m_, 60)
        if h_:
            dur_str = f"{h_}h {m_}m {s_}s"
        else:
            dur_str = f"{m_}m {s_}s"
        lines.append(kv("Duree totale", dur_str))

    lines.append(hr("="))
    return "\n".join(lines)
