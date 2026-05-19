"""API publique du cockpit Compaatible (auth par clé Bearer).

Permet à un logiciel externe de :
- pousser des fichiers images dans Images/ et déclencher leur indexation
- consulter le statut d'un batch d'indexation
- lister / lire les métadonnées d'images déjà annotées

Auth : header `Authorization: Bearer cmp_xxxxxxxx...`
"""
from __future__ import annotations
import re
from functools import wraps
from pathlib import Path
from typing import Callable

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from brain import api_keys, image_batch_state, vision_indexer
from brain.llm_client import is_api_key_configured
from brain.db import get_settings
from config import Config


bp = Blueprint("api", __name__, url_prefix="/api/v1")


# ──────────────────────────── Auth ────────────────────────────

def _extract_bearer() -> str | None:
    auth = request.headers.get("Authorization", "")
    m = re.match(r"^Bearer\s+(.+)$", auth.strip())
    if m:
        return m.group(1).strip()
    # Fallback : ?api_key= ou X-API-Key header (utile pour debug rapide)
    return request.headers.get("X-API-Key") or request.args.get("api_key")


def require_key(scope: str | None = None) -> Callable:
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            token = _extract_bearer()
            if not token:
                return jsonify({"ok": False, "error": "missing_api_key",
                                "hint": "Send Authorization: Bearer <key>"}), 401
            key_row = api_keys.verify(token)
            if not key_row:
                return jsonify({"ok": False, "error": "invalid_or_revoked_key"}), 401
            if scope and not api_keys.has_scope(key_row, scope):
                return jsonify({"ok": False, "error": "insufficient_scope",
                                "required": scope, "granted": key_row.get("scopes")}), 403
            request.api_key = key_row  # type: ignore[attr-defined]
            return fn(*args, **kwargs)
        return wrapper
    return decorator


# ──────────────────────────── Endpoints ────────────────────────────

@bp.route("/health")
@require_key()
def health():
    key = request.api_key  # type: ignore[attr-defined]
    return jsonify({
        "ok": True,
        "service": "compaatible-cockpit",
        "key_name": key["name"],
        "scopes": key["scopes"],
    })


@bp.route("/images/upload", methods=["POST"])
@require_key("images:write")
def images_upload():
    """Upload un ou plusieurs fichiers images. Déclenche un batch d'indexation Vision.

    Multipart form : champ `files` (un ou plusieurs).
    Optionnel : `auto_index=false` pour juste sauvegarder sans déclencher l'IA.

    Retourne : {ok, saved: [filenames], skipped: [...], batch_id, batch_status_url}
    """
    if not is_api_key_configured():
        return jsonify({"ok": False, "error": "anthropic_api_key_missing",
                        "hint": "Configure la clé Anthropic dans /settings"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "error": "no_files",
                        "hint": "Envoie un ou plusieurs fichiers via le champ 'files' (multipart)"}), 400

    auto_index = request.form.get("auto_index", "true").lower() != "false"

    Config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    skipped: list[dict] = []

    for f in files:
        if not f or not f.filename:
            continue
        safe = secure_filename(f.filename)
        if not safe:
            skipped.append({"filename": f.filename, "reason": "invalid_filename"})
            continue
        ext = Path(safe).suffix.lower()
        if ext not in vision_indexer.SUPPORTED_FORMATS:
            skipped.append({"filename": safe, "reason": f"unsupported_format ({ext})"})
            continue

        dest = Config.IMAGES_DIR / safe
        # Si collision, on suffixe avec un compteur
        if dest.exists():
            stem, suffix = dest.stem, dest.suffix
            i = 1
            while dest.exists():
                dest = Config.IMAGES_DIR / f"{stem}_{i}{suffix}"
                i += 1
            safe = dest.name

        f.save(dest)
        saved.append(safe)

    response: dict = {
        "ok": True,
        "saved": saved,
        "skipped": skipped,
        "saved_count": len(saved),
    }

    if auto_index and saved:
        settings = get_settings()
        model = settings.get("model_vision") or "claude-haiku-4-5-20251001"
        batch_id = vision_indexer.index_batch_async(saved, model=model)
        response["batch_id"] = batch_id
        response["batch_status_url"] = f"/api/v1/batches/{batch_id}"
        response["model"] = model

    return jsonify(response), 201


@bp.route("/batches/<int:batch_id>")
@require_key("images:read")
def batch_status(batch_id: int):
    state = image_batch_state.get(batch_id)
    if not state:
        return jsonify({"ok": False, "error": "batch_not_found"}), 404
    return jsonify({"ok": True, "batch": state})


@bp.route("/images")
@require_key("images:read")
def images_list():
    fit = request.args.getlist("fit") or None
    avatar = request.args.get("avatar", type=int)
    emotion = request.args.get("emotion") or None
    ambiance = request.args.get("ambiance") or None
    image_type = request.args.get("image_type") or None
    search = request.args.get("q") or None
    limit = max(1, min(request.args.get("limit", default=50, type=int), 200))
    offset = max(0, request.args.get("offset", default=0, type=int))

    rows, total = vision_indexer.query_images(
        fit=fit, avatar_id=avatar, emotion=emotion, ambiance=ambiance,
        image_type=image_type, search=search, limit=limit, offset=offset,
    )
    return jsonify({
        "ok": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [_serialize(r) for r in rows],
    })


@bp.route("/images/<path:filename>")
@require_key("images:read")
def images_get(filename: str):
    row = vision_indexer.get_image(filename)
    if not row:
        return jsonify({"ok": False, "error": "image_not_found"}), 404
    return jsonify({"ok": True, "image": _serialize(row)})


@bp.route("/images/<path:filename>/reindex", methods=["POST"])
@require_key("images:write")
def images_reindex(filename: str):
    if not is_api_key_configured():
        return jsonify({"ok": False, "error": "anthropic_api_key_missing"}), 400
    settings = get_settings()
    model = settings.get("model_vision") or "claude-haiku-4-5-20251001"
    batch_id = vision_indexer.index_batch_async([filename], model=model)
    return jsonify({"ok": True, "batch_id": batch_id,
                    "batch_status_url": f"/api/v1/batches/{batch_id}"}), 202


def _serialize(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ──────────────────────────── Erreurs ────────────────────────────

@bp.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": "payload_too_large",
                    "hint": "Limite serveur 64 Mo par requête"}), 413
