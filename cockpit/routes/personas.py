"""Routes Personas : liste, détail, téléchargements CSV (source + Cortex agrégé), suppression."""
from __future__ import annotations
import io
import sys
import traceback
from pathlib import Path

from flask import Blueprint, render_template, redirect, url_for, flash, send_file

from brain import pipeline, cortex_validator

bp = Blueprint("personas", __name__, url_prefix="/personas")


@bp.route("/")
def index():
    personas = pipeline.list_personas(limit=200)
    return render_template("personas_index.html", personas=personas)


@bp.route("/<int:persona_id>")
def detail(persona_id: int):
    persona = pipeline.get_persona(persona_id)
    if not persona:
        flash("Persona introuvable.", "error")
        return redirect(url_for("personas.index"))

    runs = pipeline.get_runs_for_persona(persona_id)
    root_run = pipeline.get_root_run_for_persona(persona_id)

    # CSV source : existe si le root run a un archived_csv_path qui existe sur disque
    source_csv_available = False
    if root_run and root_run.get("archived_csv_path"):
        source_csv_available = Path(root_run["archived_csv_path"]).exists()

    return render_template(
        "personas_detail.html",
        persona=persona,
        runs=runs,
        root_run=root_run,
        source_csv_available=source_csv_available,
    )


@bp.route("/<int:persona_id>/csv-source")
def download_source_csv(persona_id: int):
    """Télécharge le CSV initial à partir duquel la persona a émergé (root run)."""
    persona = pipeline.get_persona(persona_id)
    if not persona:
        flash("Persona introuvable.", "error")
        return redirect(url_for("personas.index"))

    root_run = pipeline.get_root_run_for_persona(persona_id)
    if not root_run or not root_run.get("archived_csv_path"):
        flash("Aucun CSV source archivé pour cette persona (créée par extension uniquement ?).", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    csv_path = Path(root_run["archived_csv_path"])
    if not csv_path.exists():
        flash(f"Le fichier CSV n'est plus sur disque : {csv_path.name}", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    return send_file(
        csv_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"source_{persona['first_name']}_{root_run['source_csv_name']}",
    )


@bp.route("/<int:persona_id>/csv-cortex")
def download_cortex_csv(persona_id: int):
    """Télécharge le CSV Cortex agrégé : tous les tweets de la persona, tous runs confondus.

    CONTRAT CORTEX : seules les 4 colonnes content/media_url/scheduled_at/thread_key.
    """
    persona = pipeline.get_persona(persona_id)
    if not persona:
        flash("Persona introuvable.", "error")
        return redirect(url_for("personas.index"))

    tweets = pipeline.get_tweets_for_persona(persona_id)
    eligible = [t for t in tweets if t.get("status") in (None, "draft", "approved")]
    if not eligible:
        flash("Aucun tweet exploitable pour cette persona.", "warning")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    cortex_rows = []
    for t in eligible:
        cortex_rows.append({
            "content": t["content"],
            "media_url": t["media_url"] or "",
            "scheduled_at": str(t["scheduled_at"]) if t["scheduled_at"] else "",
            "thread_key": t["thread_key"] or "",
        })
    csv_text = cortex_validator.format_for_cortex(cortex_rows)
    bio = io.BytesIO(csv_text.encode("utf-8"))
    bio.seek(0)

    filename = f"compaatible_{persona['first_name']}_corpus.csv"
    return send_file(bio, mimetype="text/csv", as_attachment=True, download_name=filename)


@bp.route("/<int:persona_id>/delete", methods=["POST"])
def delete(persona_id: int):
    """Supprime la persona + tous ses runs + tous ses tweets (cascade complète)."""
    try:
        stats = pipeline.delete_persona(persona_id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))
    except Exception as e:
        print(f"[delete_persona] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur suppression : {type(e).__name__}: {e}", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    flash(
        f"Persona « {stats['persona_first_name']} » supprimée · "
        f"{stats['runs_deleted']} run(s) et {stats['tweets_deleted']} tweet(s) en cascade.",
        "success",
    )
    return redirect(url_for("personas.index"))
