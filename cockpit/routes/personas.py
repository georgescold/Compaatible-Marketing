"""Routes Personas : liste, détail, téléchargements CSV (source + Cortex agrégé), suppression.

Création manuelle (sans CSV) : routes /new (form) → /new/generate (LLM) → /new/save.
Régénération : POST /new/generate avec le même payload.
"""
from __future__ import annotations
import io
import json
import sys
import traceback
from pathlib import Path

from flask import Blueprint, render_template, redirect, url_for, flash, send_file, request

from brain import pipeline, cortex_validator, avatars_catalog, persona_manual, db, cost_estimator
from config import Config

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

    # Pour le bloc "Générer des tweets" : modèles dispo + coût estimé par modèle
    settings = db.get_settings()
    default_model = settings.get("model_adaptation") or "claude-sonnet-4-6"
    # Cost estimate: on précalcule pour 100 posts (valeur indicative dans le form,
    # JS recalcule au changement de count via la formule first_chunk + (chunks-1)*later).
    cost_by_model = {
        m["id"]: cost_estimator.estimate_pipeline_cost(
            model_adaptation=m["id"],
            n_tweets=100,
            mode="extension",
        )
        for m in Config.AVAILABLE_MODELS
    }

    return render_template(
        "personas_detail.html",
        persona=persona,
        runs=runs,
        root_run=root_run,
        source_csv_available=source_csv_available,
        models=Config.AVAILABLE_MODELS,
        default_model=default_model,
        cost_by_model=cost_by_model,
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


@bp.route("/new", methods=["GET"])
def new():
    """Formulaire de création manuelle d'une persona."""
    avatars = avatars_catalog.get_avatars_brief()
    settings = db.get_settings()
    default_model = settings.get("model_adaptation") or "claude-sonnet-4-6"

    # Pré-calcule le coût estimé pour chaque modèle. La 1re génération paie le
    # cache write ; les régénérations à chaud (TTL 5min Anthropic) coûtent ~3-4x
    # moins. Le template affiche les deux et JS swap selon la dropdown.
    cost_by_model = {
        m["id"]: cost_estimator.estimate_manual_persona_cost(m["id"])
        for m in Config.AVAILABLE_MODELS
    }

    return render_template(
        "personas_new.html",
        avatars=avatars,
        models=Config.AVAILABLE_MODELS,
        default_model=default_model,
        cost_by_model=cost_by_model,
        emotional_levels=persona_manual.EMOTIONAL_INTENSITY_LEVELS,
        emotional_default=persona_manual.EMOTIONAL_INTENSITY_DEFAULT,
    )


def _parse_int(val: str | None, default: int | None = None) -> int | None:
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


@bp.route("/new/generate", methods=["POST"])
def new_generate():
    """Reçoit le formulaire (ou re-soumet pour régénérer), appelle le LLM, affiche la preview."""
    avatars = avatars_catalog.get_avatars_brief()

    gender = (request.form.get("gender") or "").strip()
    age = _parse_int(request.form.get("age"))
    avatar_primary = _parse_int(request.form.get("avatar_id_primary"))
    avatar_secondary = _parse_int(request.form.get("avatar_id_secondary")) or None
    first_name_hint = (request.form.get("first_name_hint") or "").strip() or None
    notes = (request.form.get("notes") or "").strip() or None
    model = (request.form.get("model") or "").strip()
    emotional_intensity = (
        request.form.get("emotional_intensity") or persona_manual.EMOTIONAL_INTENSITY_DEFAULT
    ).strip()

    # Validation
    errors = []
    if gender not in ("femme", "homme"):
        errors.append("Genre invalide (femme ou homme attendu).")
    if not age or age < 18 or age > 70:
        errors.append("Âge invalide (entier entre 18 et 70 attendu).")
    if not avatar_primary or avatar_primary < 1 or avatar_primary > 11:
        errors.append("Avatar primaire invalide (1-11 attendu).")
    if avatar_secondary and (avatar_secondary < 1 or avatar_secondary > 11):
        errors.append("Avatar secondaire invalide (1-11 ou vide).")
    if avatar_secondary and avatar_secondary == avatar_primary:
        errors.append("L'avatar secondaire doit être différent du primaire.")
    if not model:
        errors.append("Modèle LLM requis.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("personas.new"))

    try:
        result = persona_manual.generate_preview(
            gender=gender,
            age=age,
            avatar_id_primary=avatar_primary,
            avatar_id_secondary=avatar_secondary,
            first_name_hint=first_name_hint,
            notes=notes,
            model=model,
            emotional_intensity=emotional_intensity,
        )
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur génération : {type(e).__name__}: {e}", "error")
        return redirect(url_for("personas.new"))

    inputs = {
        "gender": gender,
        "age": age,
        "avatar_id_primary": avatar_primary,
        "avatar_id_secondary": avatar_secondary,
        "first_name_hint": first_name_hint or "",
        "notes": notes or "",
        "model": model,
        "emotional_intensity": emotional_intensity,
    }
    # Sérialisé en hidden field pour la sauvegarde (atomic transfer client → server).
    draft_payload = json.dumps({
        "persona": result["persona"],
        "previews": result["previews"],
        "inputs": inputs,
    }, ensure_ascii=False)

    return render_template(
        "personas_preview.html",
        persona=result["persona"],
        previews=result["previews"],
        avatar_primary=avatars_catalog.get_avatar(avatar_primary),
        avatar_secondary=avatars_catalog.get_avatar(avatar_secondary) if avatar_secondary else None,
        draft_payload=draft_payload,
        inputs=inputs,
        avatars=avatars,
        models=Config.AVAILABLE_MODELS,
        model=model,
        usage=result.get("usage", {}),
    )


def _parse_vocab_textarea(raw: str) -> list[str]:
    """Convertit un textarea multi-lignes en liste de mots/expressions (un par ligne).

    Ignore les lignes vides, trim chaque ligne. Préserve l'ordre.
    """
    if not raw:
        return []
    items = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        line = line.strip().strip(",").strip()
        if line:
            items.append(line)
    return items


@bp.route("/new/save", methods=["POST"])
def new_save():
    """Persiste la persona avec les valeurs (potentiellement éditées) du form.

    Lit chaque champ depuis request.form — l'utilisateur a pu modifier bio,
    backstory, voice_signature, vocab, prompts visuels avant de sauver.
    Les presets non négociables (gender, age, avatars) sont en hidden fields.
    Les preview tweets ne sont JAMAIS sauvegardés.
    """
    first_name = (request.form.get("first_name") or "").strip()
    if not first_name:
        flash("Persona invalide (prénom manquant).", "error")
        return redirect(url_for("personas.new"))

    gender = (request.form.get("gender") or "femme").strip()
    age = _parse_int(request.form.get("age"))
    avatar_primary = _parse_int(request.form.get("avatar_id_primary"))
    avatar_secondary_raw = (request.form.get("avatar_id_secondary") or "").strip()
    avatar_secondary = _parse_int(avatar_secondary_raw) if avatar_secondary_raw else None

    persona = {
        "first_name": first_name,
        "gender": gender,
        "age": age,
        "avatar_id_primary": avatar_primary,
        "avatar_id_secondary": avatar_secondary,
        "bio_twitter": (request.form.get("bio_twitter") or "").strip() or None,
        "backstory": (request.form.get("backstory") or "").strip() or None,
        "voice_signature": (request.form.get("voice_signature") or "").strip() or None,
        "vocabulary_yes": _parse_vocab_textarea(request.form.get("vocabulary_yes") or ""),
        "vocabulary_no": _parse_vocab_textarea(request.form.get("vocabulary_no") or ""),
        "profile_photo_prompt": (request.form.get("profile_photo_prompt") or "").strip() or None,
        "banner_prompt": (request.form.get("banner_prompt") or "").strip() or None,
    }

    try:
        persona_id = persona_manual.save_persona(persona)
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur sauvegarde : {type(e).__name__}: {e}", "error")
        return redirect(url_for("personas.new"))

    flash(f"Persona « {persona['first_name']} » créée (#{persona_id}).", "success")
    return redirect(url_for("personas.detail", persona_id=persona_id))


@bp.route("/<int:persona_id>/regen-visual/<kind>", methods=["POST"])
def regen_visual_prompt(persona_id: int, kind: str):
    """Régénère le prompt visuel (profile_photo ou banner) d'une persona existante.

    Appelle persona_manual.regenerate_visual_prompt() avec le modèle des settings
    (ou le modèle override fourni en POST), met à jour la DB, redirige vers la
    page detail avec un flash de confirmation.
    """
    if kind not in persona_manual.VISUAL_KINDS:
        flash(f"Type de visuel invalide : {kind}", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    persona = pipeline.get_persona(persona_id)
    if not persona:
        flash("Persona introuvable.", "error")
        return redirect(url_for("personas.index"))

    # Modèle : prend l'override du form, sinon le defaut Settings
    model = (request.form.get("model") or "").strip()
    if not model:
        settings = db.get_settings()
        model = settings.get("model_adaptation") or "claude-sonnet-4-6"

    try:
        result = persona_manual.regenerate_visual_prompt(
            persona=dict(persona),
            kind=kind,
            model=model,
        )
        persona_manual.update_persona_visual(persona_id, kind, result["prompt"])
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur régénération {kind} : {type(e).__name__}: {e}", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    label = "Photo de profil" if kind == "profile_photo" else "Bannière"
    cost = result.get("usage", {}).get("cost_usd_estimate", 0)
    flash(f"{label} régénérée · ${cost:.4f}", "success")
    return redirect(url_for("personas.detail", persona_id=persona_id))


@bp.route("/<int:persona_id>/generate", methods=["POST"])
def generate_for_persona(persona_id: int):
    """Lance un run de génération de tweets pour une persona (manuelle ou CSV-émergée).

    Crée un nouveau run racine avec playbook vide et démarre le copywriting en
    background. Redirige vers la page run (qui affiche le suivi live tant que
    `status='running'`, puis bascule sur la vue tweets quand terminé).
    """
    from brain import pipeline as _pipeline  # avoid shadowing

    persona = _pipeline.get_persona(persona_id)
    if not persona:
        flash("Persona introuvable.", "error")
        return redirect(url_for("personas.index"))

    count_raw = (request.form.get("count") or "").strip()
    model = (request.form.get("model") or "").strip()
    auto_match = bool(request.form.get("auto_match_images"))

    try:
        count = int(count_raw)
    except (TypeError, ValueError):
        flash("Nombre de posts invalide.", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    if count < 1 or count > 2000:
        flash("Le nombre de posts doit être entre 1 et 2000.", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    if not model:
        flash("Modèle LLM requis.", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    try:
        prep = _pipeline.prepare_manual_run(
            persona_id=persona_id,
            count=count,
            model=model,
            auto_match_images=auto_match,
        )
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur préparation : {type(e).__name__}: {e}", "error")
        return redirect(url_for("personas.detail", persona_id=persona_id))

    _pipeline.run_manual_async(prep)

    flash(
        f"Run #{prep['run_id']} lancé sur {persona['first_name']} · {count} posts demandés.",
        "success",
    )
    return redirect(url_for("tweets.show_run", run_id=prep["run_id"]))


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
