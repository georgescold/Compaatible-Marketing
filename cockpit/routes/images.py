"""Routes Images : galerie, indexation batch/unitaire, fichiers servis."""
from __future__ import annotations
from flask import Blueprint, render_template, request, send_from_directory, jsonify, abort, redirect, url_for, flash

from config import Config
from brain import image_batch_state, vision_indexer
from brain.llm_client import is_api_key_configured
from brain.db import get_settings


bp = Blueprint("images", __name__, url_prefix="/images")


@bp.route("/")
def index():
    stats = vision_indexer.count_stats()

    # Filtres GET
    fit_filter = request.args.getlist("fit")  # multi-select
    avatar = request.args.get("avatar", type=int)
    emotion = request.args.get("emotion") or None
    ambiance = request.args.get("ambiance") or None
    image_type = request.args.get("image_type") or None
    search = request.args.get("q") or None
    page = max(1, request.args.get("page", default=1, type=int))
    per_page = 48

    images, total = vision_indexer.query_images(
        fit=fit_filter if fit_filter else None,
        avatar_id=avatar,
        emotion=emotion,
        ambiance=ambiance,
        image_type=image_type,
        search=search,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    total_pages = max(1, (total + per_page - 1) // per_page)

    api_key_set = is_api_key_configured()

    return render_template(
        "images.html",
        stats=stats,
        images=images,
        total=total,
        page=page,
        total_pages=total_pages,
        per_page=per_page,
        api_key_set=api_key_set,
        filters={
            "fit": fit_filter,
            "avatar": avatar,
            "emotion": emotion,
            "ambiance": ambiance,
            "image_type": image_type,
            "q": search,
        },
    )


@bp.route("/cost-estimate", methods=["POST"])
def cost_estimate():
    """JSON : recalcule le coût d'un batch vision pour {model, n_images}."""
    from brain import cost_estimator

    data = request.get_json(silent=True) or {}
    model = (data.get("model") or "").strip()
    try:
        n_images = int(data.get("n_images") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "n_images invalide"}), 400
    if not model or n_images <= 0:
        return jsonify({"ok": False, "error": "model et n_images > 0 requis"}), 400

    cost = cost_estimator.estimate_vision_batch(model=model, n_images=n_images)
    return jsonify({"ok": True, "cost": cost})


@bp.route("/serve/<path:filename>")
def serve(filename: str):
    """Sert une image du dossier Images/ (sécurisé par send_from_directory)."""
    return send_from_directory(str(Config.IMAGES_DIR), filename)


@bp.route("/<path:filename>/detail")
def detail(filename: str):
    row = vision_indexer.get_image(filename)
    if not row:
        return jsonify({"ok": False, "error": "Image non indexée."}), 404
    return jsonify({"ok": True, "image": _serialize(row)})


@bp.route("/<path:filename>/delete", methods=["POST"])
def delete_one(filename: str):
    """Supprime une image : row DB + fichier disque. Les tweets qui la référençaient
    voient image_id, media_url, image_chosen_at remis à NULL."""
    result = vision_indexer.delete_image(filename, delete_file=True)
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error") or "erreur"}), 400
    return jsonify(result)


@bp.route("/<path:filename>/reclassify", methods=["POST"])
def reclassify_one(filename: str):
    """Met à jour compaatible_fit d'une image (high/medium/low/off_brand)."""
    data = request.get_json(silent=True) or {}
    new_fit = (data.get("fit") or "").strip()
    result = vision_indexer.update_image_fit(filename, new_fit)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/bulk-delete", methods=["POST"])
def bulk_delete():
    """Supprime en masse toutes les images d'un fit donné. Body: {fit: '<value>'}.
    Renvoie le décompte de suppressions + nb de tweets déliés."""
    data = request.get_json(silent=True) or {}
    fit = (data.get("fit") or "").strip()
    result = vision_indexer.bulk_delete_by_fit(fit)
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@bp.route("/<path:filename>/index", methods=["POST"])
def index_one(filename: str):
    settings = get_settings()
    model = settings.get("model_vision") or "claude-haiku-4-5-20251001"
    if not is_api_key_configured(model):
        provider = "Gemini" if model.startswith("gemini") else "Anthropic"
        return jsonify({"ok": False, "error": f"Clé API {provider} absente (modèle vision = {model})."}), 400
    result = vision_indexer.index_image(filename, model=model)
    return jsonify({"ok": result["ok"], "result": result if result["ok"] else None,
                    "error": result.get("error")})


@bp.route("/batch-index", methods=["POST"])
def batch_index():
    """Étape 1 : preflight. Calcule la liste effective des images à indexer et
    affiche la page avec dropdown modèle + cost estimate live."""
    from brain import cost_estimator

    settings = get_settings()
    default_model = settings.get("model_vision") or "claude-haiku-4-5-20251001"
    if not is_api_key_configured(default_model):
        provider = "Gemini" if default_model.startswith("gemini") else "Anthropic"
        flash(f"Clé API {provider} absente (modèle vision = {default_model}). Configure-la dans Settings.", "error")
        return redirect(url_for("images.index"))

    limit = request.form.get("limit", default=20, type=int)
    limit = max(1, min(limit, 200))

    targets = vision_indexer.list_unindexed(limit=limit)
    if not targets:
        flash("Aucune image non annotée à traiter.", "info")
        return redirect(url_for("images.index"))

    cost = cost_estimator.estimate_vision_batch(model=default_model, n_images=len(targets))

    return render_template(
        "images_batch_preflight.html",
        n_images=len(targets),
        limit=limit,
        targets_sample=targets[:8],
        default_model=default_model,
        available_models=Config.AVAILABLE_MODELS,
        cost=cost,
    )


@bp.route("/batch-index/launch", methods=["POST"])
def batch_index_launch():
    """Étape 2 : confirmation preflight → lance vraiment le batch en arrière-plan."""
    limit = request.form.get("limit", default=20, type=int)
    limit = max(1, min(limit, 200))
    model = (request.form.get("model_vision") or "").strip()
    if not model:
        flash("Modèle vision manquant.", "error")
        return redirect(url_for("images.index"))
    if not is_api_key_configured(model):
        provider = "Gemini" if model.startswith("gemini") else "Anthropic"
        flash(f"Clé API {provider} absente (modèle vision = {model}). Configure-la dans Settings.", "error")
        return redirect(url_for("images.index"))

    targets = vision_indexer.list_unindexed(limit=limit)
    if not targets:
        flash("Aucune image non annotée à traiter.", "info")
        return redirect(url_for("images.index"))

    batch_id = vision_indexer.index_batch_async(targets, model=model)
    return redirect(url_for("images.batch_show", batch_id=batch_id))


@bp.route("/batch/<int:batch_id>")
def batch_show(batch_id: int):
    state = image_batch_state.get(batch_id)
    if not state:
        flash("Batch introuvable (état mémoire perdu, relance un nouveau batch).", "error")
        return redirect(url_for("images.index"))
    return render_template("images_batch_running.html", batch=state)


@bp.route("/batch/<int:batch_id>/status")
def batch_status(batch_id: int):
    state = image_batch_state.get(batch_id)
    if not state:
        return jsonify({"error": "not_found"}), 404
    return jsonify(state)


def _serialize(row: dict) -> dict:
    """Convertit les types non sérialisables pour le JSON (datetime, etc.)."""
    out = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
