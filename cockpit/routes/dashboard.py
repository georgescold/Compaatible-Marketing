"""Routes du dashboard (page d'accueil) avec métriques + activité récente."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, render_template

from brain.db import check_db_ready, get_settings, cursor
from brain.llm_client import is_api_key_configured
from brain import pipeline, vision_indexer

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    db_ok, db_msg = check_db_ready()
    settings = get_settings()
    api_key_set = is_api_key_configured()

    metrics = _gather_metrics() if db_ok else _empty_metrics()
    activity = _recent_activity(limit=8) if db_ok else []

    # Compteur dynamique de la knowledge base (pour la card pipeline KB)
    from brain import knowledge_search
    kb_files_count = len(knowledge_search.list_files())

    return render_template(
        "dashboard.html",
        db_ok=db_ok,
        db_msg=db_msg,
        api_key_set=api_key_set,
        settings=settings,
        metrics=metrics,
        activity=activity,
        kb_files_count=kb_files_count,
    )


def _gather_metrics() -> dict:
    """Retourne les 3 métriques principales avec leurs deltas (7 derniers jours vs précédents)."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    with cursor() as cur:
        # Tweets générés
        cur.execute("SELECT COUNT(*) AS n FROM mkt_tweets")
        tweets_total = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) AS n FROM mkt_tweets WHERE created_at >= %s", (week_ago,))
        tweets_7d = cur.fetchone()["n"]
        cur.execute(
            "SELECT COUNT(*) AS n FROM mkt_tweets WHERE created_at >= %s AND created_at < %s",
            (two_weeks_ago, week_ago),
        )
        tweets_prev7 = cur.fetchone()["n"]

        # Images
        cur.execute("SELECT COUNT(*) AS n FROM mkt_images")
        images_total = cur.fetchone()["n"]

        # Coût API : somme cost_usd des runs
        cur.execute("SELECT COALESCE(SUM(cost_usd), 0) AS s FROM mkt_csv_runs")
        cost_total = float(cur.fetchone()["s"] or 0)
        cur.execute("SELECT COALESCE(SUM(cost_usd), 0) AS s FROM mkt_csv_runs WHERE started_at >= %s", (week_ago,))
        cost_7d = float(cur.fetchone()["s"] or 0)

        # Personas
        cur.execute("SELECT COUNT(*) AS n FROM mkt_personas_emerged")
        personas_total = cur.fetchone()["n"]

        # Runs ce mois
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        cur.execute("SELECT COUNT(*) AS n FROM mkt_csv_runs WHERE started_at >= %s", (first_of_month,))
        runs_this_month = cur.fetchone()["n"]

    images_on_disk = len(vision_indexer.list_all_images())

    # Deltas
    def fmt_delta(curr: int, prev: int) -> dict:
        if prev == 0:
            if curr == 0:
                return {"text": "stable", "direction": "stable"}
            return {"text": f"+{curr}", "direction": "up"}
        diff_pct = ((curr - prev) / prev) * 100
        if abs(diff_pct) < 1:
            return {"text": "stable", "direction": "stable"}
        direction = "up" if diff_pct > 0 else "down"
        return {"text": f"{abs(diff_pct):.1f}% vs 7j precedents", "direction": direction}

    return {
        "tweets_total": tweets_total,
        "tweets_delta": fmt_delta(tweets_7d, tweets_prev7),
        "images_total": images_total,
        "images_on_disk": images_on_disk,
        "images_pct": int((images_total / images_on_disk * 100)) if images_on_disk else 0,
        "cost_total": cost_total,
        "cost_7d": cost_7d,
        "personas_total": personas_total,
        "runs_this_month": runs_this_month,
    }


def _empty_metrics() -> dict:
    return {
        "tweets_total": 0,
        "tweets_delta": {"text": "—", "direction": "stable"},
        "images_total": 0,
        "images_on_disk": 0,
        "images_pct": 0,
        "cost_total": 0.0,
        "cost_7d": 0.0,
        "personas_total": 0,
        "runs_this_month": 0,
    }


def _recent_activity(limit: int = 8) -> list[dict]:
    """Concatène les derniers événements (runs, personas, images batches) en feed."""
    events: list[dict] = []

    with cursor() as cur:
        # Derniers runs (csv_runs)
        cur.execute(
            """
            SELECT r.id, r.source_csv_name, r.status, r.started_at, r.completed_at,
                   r.output_tweets_count, r.source_handle,
                   p.first_name AS persona_name
            FROM mkt_csv_runs r
            LEFT JOIN mkt_personas_emerged p ON r.persona_id = p.id
            ORDER BY r.started_at DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
        for r in cur.fetchall():
            d = dict(r)
            status = d["status"]
            if status == "completed":
                dot = "ok"
            elif status == "failed":
                dot = "err"
            else:
                # paused, running, completed_partial → warning
                dot = "warn"
            persona = d["persona_name"] or "—"
            count = d["output_tweets_count"] or 0
            handle = d["source_handle"] or "?"
            text = f"Run #{d['id']} {status} · persona {persona} · {count} tweets · source @{handle}"
            events.append({
                "dot": dot,
                "text": text,
                "ts": d["completed_at"] or d["started_at"],
                "kind": "run",
                "id": d["id"],
            })

    events.sort(key=lambda e: e["ts"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return events[:limit]
