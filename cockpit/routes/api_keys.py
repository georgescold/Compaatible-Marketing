"""Routes UI pour la gestion des clés API du cockpit."""
from __future__ import annotations
from flask import Blueprint, render_template, request, redirect, url_for, flash

from brain import api_keys


bp = Blueprint("api_keys", __name__, url_prefix="/api-keys")


AVAILABLE_SCOPES = [
    ("images:write", "Upload + ré-indexation d'images"),
    ("images:read", "Lecture des images annotées"),
]


@bp.route("/")
def index():
    keys = api_keys.list_keys(include_revoked=True)
    new_key = request.args.get("new_key")  # affiché une seule fois après création
    new_key_id = request.args.get("new_key_id", type=int)
    return render_template(
        "api_keys.html",
        keys=keys,
        scopes=AVAILABLE_SCOPES,
        new_key=new_key,
        new_key_id=new_key_id,
    )


@bp.route("/create", methods=["POST"])
def create():
    name = (request.form.get("name") or "").strip()
    notes = (request.form.get("notes") or "").strip() or None
    selected_scopes = request.form.getlist("scopes")

    if not name:
        flash("Le nom de la clé est obligatoire.", "error")
        return redirect(url_for("api_keys.index"))

    valid_scopes = {s for s, _ in AVAILABLE_SCOPES}
    scopes = [s for s in selected_scopes if s in valid_scopes] or None

    try:
        result = api_keys.create_key(name=name, scopes=scopes, notes=notes)
    except Exception as e:
        flash(f"Erreur création : {e}", "error")
        return redirect(url_for("api_keys.index"))

    return redirect(url_for(
        "api_keys.index",
        new_key=result["key_plaintext"],
        new_key_id=result["id"],
    ))


@bp.route("/<int:key_id>/revoke", methods=["POST"])
def revoke(key_id: int):
    if api_keys.revoke_key(key_id):
        flash("Clé révoquée.", "success")
    else:
        flash("Clé introuvable ou déjà révoquée.", "info")
    return redirect(url_for("api_keys.index"))


@bp.route("/<int:key_id>/delete", methods=["POST"])
def delete(key_id: int):
    if api_keys.delete_key(key_id):
        flash("Clé supprimée définitivement.", "success")
    else:
        flash("Clé introuvable.", "info")
    return redirect(url_for("api_keys.index"))
