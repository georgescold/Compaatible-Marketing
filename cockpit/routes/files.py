"""Routes Fichiers : historique des CSV envoyés à Cortex + consultation détaillée.

Chaque envoi vers l'API Cortex (`POST /api/v1/files`) crée une row dans
`mkt_cortex_uploads` avec les métadonnées + le chemin du CSV archivé sur disque.
L'onglet Fichiers donne accès à l'historique complet et au contenu de chaque CSV.
"""
from __future__ import annotations
import csv as csvmod
import io as iomod
import json
from pathlib import Path

from flask import Blueprint, render_template, redirect, url_for, flash, send_file, abort

from brain import db


bp = Blueprint("files", __name__, url_prefix="/files")


def _list_uploads(limit: int = 200) -> list[dict]:
    """Tous les envois Cortex, du plus récent au plus ancien, avec join persona/run."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
              u.id, u.csv_run_id, u.persona_id, u.filename, u.file_id_cortex,
              u.eligible_count, u.cortex_valid_tweets, u.cortex_threads,
              u.cortex_warnings, u.sent_at, u.status, u.error_message,
              u.archived_csv_path,
              p.first_name AS persona_first_name,
              p.avatar_id_primary AS persona_avatar,
              r.source_csv_name AS run_source_csv_name
            FROM mkt_cortex_uploads u
            LEFT JOIN mkt_personas_emerged p ON u.persona_id = p.id
            LEFT JOIN mkt_csv_runs r ON u.csv_run_id = r.id
            ORDER BY u.sent_at DESC, u.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def _get_upload(upload_id: int) -> dict | None:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
              u.*,
              p.first_name AS persona_first_name,
              p.avatar_id_primary AS persona_avatar,
              r.source_csv_name AS run_source_csv_name
            FROM mkt_cortex_uploads u
            LEFT JOIN mkt_personas_emerged p ON u.persona_id = p.id
            LEFT JOIN mkt_csv_runs r ON u.csv_run_id = r.id
            WHERE u.id = %s
            """,
            (upload_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def _parse_csv_preview(csv_path_str: str, max_rows: int = 50) -> dict:
    """Lit le CSV archivé et renvoie {headers, rows[], total_rows, truncated}.

    Retourne {'error': '...'} si le fichier n'existe pas ou est illisible.
    """
    if not csv_path_str:
        return {"error": "Aucun chemin CSV archivé pour cet envoi."}
    p = Path(csv_path_str)
    if not p.exists():
        return {"error": f"Fichier introuvable sur disque : {p.name}"}
    try:
        with p.open("r", encoding="utf-8", newline="") as f:
            reader = csvmod.reader(f)
            rows = list(reader)
    except Exception as e:
        return {"error": f"Lecture impossible : {type(e).__name__}: {e}"}
    if not rows:
        return {"headers": [], "rows": [], "total_rows": 0, "truncated": False}
    headers = rows[0]
    data_rows = rows[1:]
    total = len(data_rows)
    truncated = total > max_rows
    return {
        "headers": headers,
        "rows": data_rows[:max_rows],
        "total_rows": total,
        "truncated": truncated,
        "shown_rows": min(total, max_rows),
    }


@bp.route("/")
def index():
    """Liste de tous les envois Cortex, du plus récent au plus ancien."""
    uploads = _list_uploads(limit=200)
    return render_template("files_index.html", uploads=uploads)


@bp.route("/<int:upload_id>")
def detail(upload_id: int):
    """Détail d'un envoi : métadonnées + aperçu inline du CSV."""
    upload = _get_upload(upload_id)
    if not upload:
        flash("Envoi introuvable.", "error")
        return redirect(url_for("files.index"))

    preview = _parse_csv_preview(upload.get("archived_csv_path") or "", max_rows=50)

    # Parse parse_summary_json pour affichage structuré
    parse_summary = upload.get("parse_summary_json")
    if isinstance(parse_summary, str):
        try:
            parse_summary = json.loads(parse_summary)
        except Exception:
            parse_summary = None

    return render_template(
        "files_detail.html",
        upload=upload,
        preview=preview,
        parse_summary=parse_summary,
    )


@bp.route("/<int:upload_id>/download")
def download(upload_id: int):
    """Re-télécharge le CSV archivé qui avait été envoyé à Cortex."""
    upload = _get_upload(upload_id)
    if not upload:
        flash("Envoi introuvable.", "error")
        return redirect(url_for("files.index"))
    csv_path_str = upload.get("archived_csv_path")
    if not csv_path_str:
        flash("Aucun fichier archivé pour cet envoi.", "error")
        return redirect(url_for("files.detail", upload_id=upload_id))
    csv_path = Path(csv_path_str)
    if not csv_path.exists():
        flash(f"Le fichier n'est plus sur disque : {csv_path.name}", "error")
        return redirect(url_for("files.detail", upload_id=upload_id))
    return send_file(
        csv_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name=upload.get("filename") or csv_path.name,
    )
