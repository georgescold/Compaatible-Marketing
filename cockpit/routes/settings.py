"""Routes Settings : clés API (Anthropic + Gemini) + modèles par tâche + intégration Cortex."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from markupsafe import escape

from brain.db import get_settings, update_settings
from brain.anthropic_client import test_api_key as anthropic_test_api_key, list_available_models, mask_api_key
from brain.gemini_client import test_api_key as gemini_test_api_key
from brain.llm_client import PRICING as LLM_PRICING
from brain import cortex_client

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET"])
def index():
    settings = get_settings()
    # Coût estimé pour un run de référence (50 tweets sources + run copywriting standard).
    # Permet aux utilisateurs de comparer "en euros réels" plutôt que par tokens/1M.
    # Valeurs approchées : ~50k tokens system cachés + ~30k chunks user + ~13.5k output.
    typical_run_50_tweets = {}
    for m in list_available_models():
        p = LLM_PRICING.get(m["id"])
        if not p:
            typical_run_50_tweets[m["id"]] = None
            continue
        # 1er chunk : cache write 50k + fresh 1.5k user + 4.5k output
        # Chunks 2-3 : cache read 50k + fresh 1.5k user + 4.5k output (×2)
        first = (50000/1e6) * p["cache_write"] + (1500/1e6) * p["input"] + (4500/1e6) * p["output"]
        later = (50000/1e6) * p["cache_read"]  + (1500/1e6) * p["input"] + (4500/1e6) * p["output"]
        typical_run_50_tweets[m["id"]] = round(first + 2 * later, 4)
    return render_template(
        "settings.html",
        settings=settings,
        models=list_available_models(),
        pricing=LLM_PRICING,
        typical_run_50_tweets=typical_run_50_tweets,
        masked_api_key=mask_api_key(settings.get("anthropic_api_key")),
        masked_gemini_key=mask_api_key(settings.get("gemini_api_key")),
        masked_cortex_token=mask_api_key(settings.get("cortex_api_token")),
    )


@bp.route("/save", methods=["POST"])
def save():
    fields: dict = {}

    # Clé API Anthropic (on ne la sauvegarde que si non vide pour éviter de l'écraser avec un blank)
    api_key = (request.form.get("anthropic_api_key") or "").strip()
    if api_key:
        fields["anthropic_api_key"] = api_key

    # Clé API Gemini (même logique)
    gemini_key = (request.form.get("gemini_api_key") or "").strip()
    if gemini_key:
        fields["gemini_api_key"] = gemini_key

    # Token Cortex (même logique : vide = ne pas écraser)
    cortex_token = (request.form.get("cortex_api_token") or "").strip()
    if cortex_token:
        fields["cortex_api_token"] = cortex_token

    # URL Cortex (vide volontaire = pas d'écrasement non plus, sinon on sauvegarde)
    cortex_url = (request.form.get("cortex_base_url") or "").strip()
    if cortex_url:
        fields["cortex_base_url"] = cortex_url.rstrip("/")

    # Modèles par tâche
    for key in ("model_translation", "model_analysis", "model_adaptation", "model_vision",
                "model_image_association"):
        val = (request.form.get(key) or "").strip()
        if val:
            fields[key] = val

    if fields:
        update_settings(**fields)
        flash("Settings sauvegardés.", "success")
    else:
        flash("Aucun changement.", "info")

    return redirect(url_for("settings.index"))


# Champs sensibles qu'on autorise à effacer via /clear-credential. Allowlist stricte
# pour éviter qu'une requête malveillante puisse passer field=id ou autre.
_CLEARABLE_FIELDS = {
    "anthropic_api_key": "Clé Anthropic",
    "gemini_api_key": "Clé Gemini",
    "cortex_api_token": "Token Cortex",
    "cortex_base_url": "URL Cortex",
}


@bp.route("/clear-credential", methods=["POST"])
def clear_credential():
    """Efface un credential (set à NULL en DB). Le champ à effacer est fourni
    via form param `field`, validé contre _CLEARABLE_FIELDS.
    """
    field = (request.form.get("field") or "").strip()
    if field not in _CLEARABLE_FIELDS:
        flash(f"Champ inconnu : {field!r}.", "error")
        return redirect(url_for("settings.index"))

    update_settings(**{field: None})
    flash(f"{_CLEARABLE_FIELDS[field]} retirée.", "success")
    return redirect(url_for("settings.index"))


@bp.route("/test-key", methods=["POST"])
def test_key():
    """Mode classique (redirect + flash) pour fallback non-htmx."""
    api_key = (request.form.get("anthropic_api_key") or "").strip()
    if not api_key:
        api_key = get_settings().get("anthropic_api_key") or ""
    if not api_key:
        flash("Aucune clé à tester.", "error")
        return redirect(url_for("settings.index"))

    ok, msg = anthropic_test_api_key(api_key)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("settings.index"))


@bp.route("/test-key/inline", methods=["POST"])
def test_key_inline():
    """Test htmx : retourne un fragment HTML (pill ok/err + message) injecté inline.

    `source` query/form param :
    - `saved` : teste la clé déjà en DB (ignore l'input)
    - autre  : teste la valeur saisie dans le champ anthropic_api_key (input)
    """
    source = (request.form.get("source") or "input").strip()
    if source == "saved":
        api_key = (get_settings().get("anthropic_api_key") or "").strip()
        label_origin = "clé enregistrée"
    else:
        api_key = (request.form.get("anthropic_api_key") or "").strip()
        label_origin = "clé saisie"

    if not api_key:
        return (
            f'<div class="alert err"><span class="dot err"></span>'
            f'<span>Aucune {label_origin} à tester.</span></div>',
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    ok, msg = anthropic_test_api_key(api_key)
    cls = "ok" if ok else "err"
    return (
        f'<div class="alert {cls}"><span class="dot {cls}"></span>'
        f'<span><strong>{"OK" if ok else "ECHEC"}</strong> · {escape(msg)} '
        f'<span class="muted text-xs">({label_origin})</span></span></div>',
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@bp.route("/test-gemini-key/inline", methods=["POST"])
def test_gemini_key_inline():
    """Test htmx d'une clé Gemini. Même UX que test_key_inline mais sur Google."""
    source = (request.form.get("source") or "input").strip()
    if source == "saved":
        api_key = (get_settings().get("gemini_api_key") or "").strip()
        label_origin = "clé enregistrée"
    else:
        api_key = (request.form.get("gemini_api_key") or "").strip()
        label_origin = "clé saisie"

    if not api_key:
        return (
            f'<div class="alert err"><span class="dot err"></span>'
            f'<span>Aucune {label_origin} à tester.</span></div>',
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    ok, msg = gemini_test_api_key(api_key)
    cls = "ok" if ok else "err"
    return (
        f'<div class="alert {cls}"><span class="dot {cls}"></span>'
        f'<span><strong>{"OK" if ok else "ECHEC"}</strong> · {escape(msg)} '
        f'<span class="muted text-xs">({label_origin})</span></span></div>',
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@bp.route("/test-cortex/inline", methods=["POST"])
def test_cortex_inline():
    """Test htmx Cortex : retourne un fragment HTML (pill ok/err + message)."""
    # Sauvegarde temporaire des valeurs saisies si fournies (comportement identique à test-cortex)
    fields: dict = {}
    token = (request.form.get("cortex_api_token") or "").strip()
    if token:
        fields["cortex_api_token"] = token
    url = (request.form.get("cortex_base_url") or "").strip()
    if url:
        fields["cortex_base_url"] = url.rstrip("/")
    if fields:
        update_settings(**fields)

    try:
        payload = cortex_client.ping()
    except cortex_client.CortexConfigError as e:
        return (
            f'<div class="alert err"><span class="dot err"></span><span>Cortex : {escape(str(e))}</span></div>',
            200, {"Content-Type": "text/html; charset=utf-8"},
        )
    except cortex_client.CortexError as e:
        return (
            f'<div class="alert err"><span class="dot err"></span><span><strong>ECHEC</strong> · {escape(str(e))}</span></div>',
            200, {"Content-Type": "text/html; charset=utf-8"},
        )
    user_id = payload.get("user_id", "?")
    return (
        f'<div class="alert ok"><span class="dot ok"></span>'
        f'<span><strong>OK</strong> · ping Cortex valide · user_id <span class="mono">{escape(str(user_id))}</span></span></div>',
        200, {"Content-Type": "text/html; charset=utf-8"},
    )


@bp.route("/test-cortex", methods=["POST"])
def test_cortex():
    """Tente d'enregistrer les valeurs Cortex saisies (si non vides) puis appelle GET /ping."""
    fields: dict = {}
    token = (request.form.get("cortex_api_token") or "").strip()
    if token:
        fields["cortex_api_token"] = token
    url = (request.form.get("cortex_base_url") or "").strip()
    if url:
        fields["cortex_base_url"] = url.rstrip("/")
    if fields:
        update_settings(**fields)

    try:
        payload = cortex_client.ping()
    except cortex_client.CortexConfigError as e:
        flash(f"Cortex : {e}", "error")
        return redirect(url_for("settings.index"))
    except cortex_client.CortexError as e:
        flash(f"Cortex KO : {e}", "error")
        return redirect(url_for("settings.index"))

    user_id = payload.get("user_id", "?")
    flash(f"Cortex OK — user_id {user_id}", "success")
    return redirect(url_for("settings.index"))
