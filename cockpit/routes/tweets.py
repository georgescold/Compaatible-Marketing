"""Routes Tweets : upload, run, view, edit inline, download CSV format Cortex."""
from __future__ import annotations
import io
import re
import secrets
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify
from werkzeug.utils import secure_filename

from brain import pipeline, cortex_validator, run_state, cortex_client, image_matcher
from brain.llm_client import is_api_key_configured
from config import Config

bp = Blueprint("tweets", __name__, url_prefix="/tweets")


@bp.route("/")
def index():
    runs = pipeline.list_runs(limit=30)
    return render_template("tweets.html", runs=runs, api_key_set=is_api_key_configured())


def _pending_upload_path(token: str) -> Path:
    """Chemin du CSV en attente de confirmation preflight (token-named).

    Whitelist sur le token pour éviter toute traversée de chemin : on n'accepte
    que des tokens hex courts générés par secrets.token_hex.
    """
    if not re.fullmatch(r"[a-f0-9]{16,64}", token or ""):
        raise ValueError("token de upload invalide")
    Config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return Config.UPLOADS_DIR / f"pending_{token}.csv"


@bp.route("/upload", methods=["POST"])
def upload():
    """Étape 1 : réception du fichier. Parse léger, sauvegarde token-named,
    redirige vers la page preflight pour choix modèle + cost estimate live."""
    from brain import csv_parser, cost_estimator
    from brain.db import get_settings

    f = request.files.get("csv_file")
    if not f or not f.filename:
        flash("Aucun fichier sélectionné.", "error")
        return redirect(url_for("tweets.index"))

    filename = secure_filename(f.filename)
    if not filename.lower().endswith(".csv"):
        flash("Le fichier doit être un .csv.", "error")
        return redirect(url_for("tweets.index"))

    file_bytes = f.read()
    max_tweets = request.form.get("max_tweets")
    max_tweets_int = int(max_tweets) if max_tweets and max_tweets.isdigit() else None

    # Parse léger pour valider tout de suite + obtenir le n_tweets utilisé dans le cost estimate
    try:
        parsed = csv_parser.parse_csv(file_bytes)
    except Exception as e:
        flash(f"Erreur parsing CSV : {e}", "error")
        return redirect(url_for("tweets.index"))
    if parsed["valid_rows"] == 0:
        flash(
            "CSV parsé mais 0 ligne valide (content vide ou colonne content introuvable). "
            f"Colonnes détectées : {parsed.get('columns')}",
            "error",
        )
        return redirect(url_for("tweets.index"))

    full_count = parsed["valid_rows"]
    n_tweets = min(max_tweets_int, full_count) if max_tweets_int else full_count

    # Sauvegarde token-named (sera consommée par /upload/launch ou expirée par cleanup)
    token = secrets.token_hex(16)
    pending_path = _pending_upload_path(token)
    pending_path.write_bytes(file_bytes)

    # Default modèles : Settings
    settings = get_settings()
    default_analysis = settings.get("model_analysis") or "claude-sonnet-4-6"
    default_adaptation = settings.get("model_adaptation") or "claude-sonnet-4-6"

    cost = cost_estimator.estimate_pipeline_cost(
        model_adaptation=default_adaptation,
        n_tweets=n_tweets,
        mode="fresh",
        model_analysis=default_analysis,
    )

    return render_template(
        "tweets_upload_preflight.html",
        token=token,
        source_csv_name=filename,
        full_count=full_count,
        n_tweets=n_tweets,
        max_tweets=max_tweets_int,
        detected_language=parsed["detected_language"],
        source_handle=parsed["source_handle"],
        default_analysis=default_analysis,
        default_adaptation=default_adaptation,
        available_models=Config.AVAILABLE_MODELS,
        cost=cost,
    )


@bp.route("/upload/launch", methods=["POST"])
def upload_launch():
    """Étape 2 : confirmation preflight → vrai démarrage du pipeline."""
    token = (request.form.get("token") or "").strip()
    source_csv_name = (request.form.get("source_csv_name") or "").strip() or "upload.csv"
    max_tweets = request.form.get("max_tweets")
    max_tweets_int = int(max_tweets) if max_tweets and max_tweets.isdigit() else None
    model_analysis = (request.form.get("model_analysis") or "").strip() or None
    model_adaptation = (request.form.get("model_adaptation") or "").strip() or None

    # Extension chaînée upfront (optionnelle)
    chain_extension = bool(request.form.get("chain_extension"))
    chain_count_raw = (request.form.get("chain_extension_count") or "").strip()
    chain_extension_count = 0
    if chain_extension and chain_count_raw.isdigit():
        chain_extension_count = int(chain_count_raw)
        if chain_extension_count < 0:
            chain_extension_count = 0
        if chain_extension_count > 2000:
            chain_extension_count = 2000

    try:
        pending_path = _pending_upload_path(token)
    except ValueError:
        flash("Token d'upload invalide ou expiré. Recommence l'upload.", "error")
        return redirect(url_for("tweets.index"))
    if not pending_path.exists():
        flash("Fichier en attente introuvable (expiré ou serveur redémarré). Recommence l'upload.", "error")
        return redirect(url_for("tweets.index"))

    file_bytes = pending_path.read_bytes()
    override_models = {"analysis": model_analysis, "adaptation": model_adaptation}

    print(f"\n[upload] Confirm preflight · {source_csv_name} · max_tweets={max_tweets_int} · models=ana:{model_analysis} adp:{model_adaptation}", flush=True)
    try:
        prep = pipeline.prepare_run(
            file_bytes=file_bytes,
            source_csv_name=source_csv_name,
            max_source_tweets=max_tweets_int,
            override_models=override_models,
        )
    except pipeline.PipelineError as e:
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur pipeline : {e}", "error")
        return redirect(url_for("tweets.index"))
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur inattendue : {type(e).__name__}: {e}", "error")
        return redirect(url_for("tweets.index"))

    # Cleanup du pending : prepare_run a archivé une copie horodatée propre
    try:
        pending_path.unlink()
    except OSError:
        pass

    # Stash extension chaînée : _run_in_background l'enchaîne après succès
    if chain_extension_count > 0:
        prep["chain_extension_count"] = chain_extension_count
        print(f"[upload] Extension chaînée prévue : +{chain_extension_count} tweets après run initial", flush=True)

    pipeline.run_pipeline_async(prep)
    return redirect(url_for("tweets.show_run", run_id=prep["run_id"]))


@bp.route("/cost-estimate", methods=["POST"])
def cost_estimate():
    """Endpoint JSON pour recalculer un coût estimé en live depuis le preflight.

    Body JSON attendu : {mode, n_tweets, model_adaptation, model_analysis?}.
    `mode` : 'fresh' | 'copywriting' | 'extension'. En mode 'fresh', il faut aussi
    fournir `model_analysis` (utilisé pour les stages analyze + persona).
    """
    from brain import cost_estimator

    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "copywriting").strip()
    if mode not in ("fresh", "copywriting", "extension"):
        return jsonify({"ok": False, "error": "mode invalide"}), 400

    try:
        n_tweets = int(data.get("n_tweets") or 0)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "n_tweets invalide"}), 400
    if n_tweets <= 0:
        return jsonify({"ok": False, "error": "n_tweets doit être > 0"}), 400

    model_adaptation = (data.get("model_adaptation") or "").strip()
    model_analysis = (data.get("model_analysis") or "").strip() or None
    if not model_adaptation:
        return jsonify({"ok": False, "error": "model_adaptation requis"}), 400
    if mode == "fresh" and not model_analysis:
        return jsonify({"ok": False, "error": "model_analysis requis en mode fresh"}), 400

    cost = cost_estimator.estimate_pipeline_cost(
        model_adaptation=model_adaptation,
        n_tweets=n_tweets,
        mode=mode,
        model_analysis=model_analysis,
    )

    # Extension chaînée (optionnelle, depuis preflight upload uniquement)
    try:
        n_extension = int(data.get("n_extension") or 0)
    except (TypeError, ValueError):
        n_extension = 0
    if n_extension > 0 and mode == "fresh":
        # `n_extension` est exprime en POSTS atomiques (1 thread = 1 post).
        # Le copywriter genere ~1.5x plus de messages pour la marge threading
        # + jusqu'a MAX_EXTRA chunks de EXTRA_CHUNK_SIZE en top-up si la cible
        # de posts n'est pas atteinte. On estime sur le CEILING (worst case)
        # pour que la facture reelle soit toujours <= ce qu'on annonce.
        from brain.copywriter import (
            POSTS_TO_MESSAGES_OVERSHOOT,
            MAX_EXTRA_EXTENSION_CHUNKS,
            EXTRA_EXTENSION_CHUNK_SIZE,
        )
        import math
        n_messages_ceiling = (
            math.ceil(n_extension * POSTS_TO_MESSAGES_OVERSHOOT)
            + MAX_EXTRA_EXTENSION_CHUNKS * EXTRA_EXTENSION_CHUNK_SIZE
        )
        ext = cost_estimator.estimate_pipeline_cost(
            model_adaptation=model_adaptation,
            n_tweets=n_messages_ceiling,
            mode="extension",
        )
        cost["extension_usd"] = ext["copy_total_usd"]
        cost["extension_chunks"] = ext["chunks"]
        cost["total_usd"] = round(cost["total_usd"] + ext["copy_total_usd"], 4)
    else:
        cost["extension_usd"] = 0.0
        cost["extension_chunks"] = 0

    return jsonify({"ok": True, "cost": cost})


@bp.route("/runs/<int:run_id>")
def show_run(run_id: int):
    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))

    # Mapping {id: name} des 11 avatars Compaatible — pour afficher "Avatar N — Le/La Name"
    # à côté du Run # dans le header (rappel rapide du positionnement de la persona).
    from brain import avatars_catalog
    avatar_names = {a["id"]: a["name"] for a in avatars_catalog.get_avatars_brief()}

    # Tant que le pipeline tourne, on affiche la page "running" avec polling JS.
    if run.get("status") == "running":
        return render_template(
            "tweets_run_running.html",
            run=run,
            stages=run_state.STAGES,
            avatar_names=avatar_names,
        )

    tweets = pipeline.get_tweets_for_run(run_id)

    # Valider l'ensemble pour afficher warnings et erreurs
    cortex_rows = [{"content": t["content"], "media_url": t["media_url"],
                    "scheduled_at": str(t["scheduled_at"]) if t["scheduled_at"] else "",
                    "thread_key": t["thread_key"]} for t in tweets]
    validation = cortex_validator.validate_batch(cortex_rows)

    # Parse playbook
    import json
    playbook = None
    if run.get("playbook_json"):
        try:
            playbook = run["playbook_json"] if isinstance(run["playbook_json"], dict) else json.loads(run["playbook_json"])
        except Exception:
            playbook = None

    # Parse health check structurel (warnings CSV)
    health = None
    if run.get("health_check_json"):
        try:
            raw = run["health_check_json"]
            health = raw if isinstance(raw, dict) else json.loads(raw)
        except Exception:
            health = None

    # Dashboard détaillé du run (mentions Compaatible texte/URL, distributions,
    # structure narrative). Non-bloquant : si la collecte échoue, on log et on
    # passe None — la section dashboard du template est conditionnée à sa présence.
    dashboard = None
    try:
        from brain import run_dashboard
        dashboard = run_dashboard.build(run_id)
    except Exception as e:
        import sys
        print(f"[show_run] dashboard build failed · {type(e).__name__}: {e}", file=sys.stderr, flush=True)

    return render_template(
        "tweets_run.html",
        run=run,
        tweets=tweets,
        validation=validation,
        playbook=playbook,
        health=health,
        dashboard=dashboard,
        cortex_configured=cortex_client.is_configured(),
        avatar_names=avatar_names,
    )


@bp.route("/runs/<int:run_id>/pause", methods=["POST"])
def request_pause(run_id: int):
    """Pose le flag de pause sur le run en cours. Le copywriter sortira
    proprement entre deux chunks (les tweets déjà insérés restent en DB)."""
    run = pipeline.get_run(run_id)
    if not run:
        return jsonify({"ok": False, "error": "Run introuvable."}), 404
    if run.get("status") != "running":
        return jsonify({"ok": False, "error": f"Run non-running (status={run.get('status')})."}), 400
    ok = run_state.request_pause(run_id)
    if not ok:
        return jsonify({"ok": False, "error": "Pause refusée (run pas en mémoire ou pas en cours)."}), 400
    return jsonify({"ok": True})


@bp.route("/runs/<int:run_id>/resume-paused", methods=["GET"])
def resume_paused_preflight(run_id: int):
    """Page bandeau pour reprendre un run en pause : dropdown modèle + cost + confirm."""
    from brain import cost_estimator
    import json as _json

    if not is_api_key_configured():
        flash("Clé API Anthropic absente.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))
    if run.get("status") != "paused":
        flash(f"Run non en pause (status={run.get('status')}).", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    raw = run.get("pause_state_json")
    if not raw:
        flash("Pause state introuvable. Impossible de reprendre.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    pause_state = raw if isinstance(raw, dict) else _json.loads(raw)
    next_chunk_idx = int(pause_state.get("next_chunk_idx") or 0)
    total_chunks = int(pause_state.get("total_chunks") or 0)
    remaining_chunks = max(0, total_chunks - next_chunk_idx)
    n_tweets_remaining = remaining_chunks * 20  # estimation chunk size
    mode = pause_state.get("mode") or "copywriting"

    default_adaptation = run.get("model_adaptation") or "claude-sonnet-4-6"
    cost = cost_estimator.estimate_pipeline_cost(
        model_adaptation=default_adaptation,
        n_tweets=max(1, n_tweets_remaining),
        mode="extension" if mode == "extension" else "copywriting",
    )

    return render_template(
        "tweets_run_resume_paused.html",
        run=run,
        pause_state=pause_state,
        mode=mode,
        next_chunk_idx=next_chunk_idx,
        total_chunks=total_chunks,
        remaining_chunks=remaining_chunks,
        n_tweets_remaining=n_tweets_remaining,
        default_adaptation=default_adaptation,
        available_models=Config.AVAILABLE_MODELS,
        cost=cost,
    )


@bp.route("/runs/<int:run_id>/resume-paused/launch", methods=["POST"])
def resume_paused_launch(run_id: int):
    """Lance effectivement la reprise après confirmation."""
    if not is_api_key_configured():
        flash("Clé API Anthropic absente.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))
    if run.get("status") != "paused":
        flash(f"Run non en pause (status={run.get('status')}).", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    model_adaptation = (request.form.get("model_adaptation") or "").strip() or None
    override_models = {"adaptation": model_adaptation} if model_adaptation else None

    print(f"\n[resume-paused] Run #{run_id} · model={model_adaptation}", flush=True)
    try:
        pipeline.resume_paused_async(run_id, override_models=override_models)
    except Exception as e:
        print(f"[resume-paused] Exception : {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur reprise : {type(e).__name__}: {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    flash(
        f"Reprise lancée · run #{run_id} · modèle {model_adaptation or run.get('model_adaptation')}.",
        "success",
    )
    return redirect(url_for("tweets.show_run", run_id=run_id))


@bp.route("/runs/<int:run_id>/status")
def run_status(run_id: int):
    """JSON pour polling depuis la page running. Fusionne run_state in-memory + DB."""
    state = run_state.get(run_id)
    run = pipeline.get_run(run_id)

    if state is None and run is None:
        return jsonify({"error": "not_found"}), 404

    # Si l'état mémoire est perdu (restart Flask) on retombe sur la DB
    if state is None:
        return jsonify({
            "run_id": run_id,
            "status": run.get("status"),
            "current": run.get("current_stage"),
            "error": run.get("error_message"),
            "elapsed_s": None,
            "stages": {},
            "stages_def": run_state.STAGES,
            "log_tail": [],
            "from_db_fallback": True,
        })

    # Status DB est la source de vérité finale (un thread peut se terminer entre 2 polls)
    if run and run.get("status") in ("completed", "completed_partial", "failed") and state["status"] == "running":
        state["status"] = run["status"]

    return jsonify(state)


# ─── Helpers reprise/extension : chargement playbook + persona depuis run parent ────

def _load_parent_playbook_and_persona(run_id: int):
    """Cherche playbook + persona en remontant la chaîne des runs si nécessaire.

    Retourne (root_run, playbook, persona, persona_id) ou (None, None, None, None) si
    introuvable. root_run = le run où le playbook/persona ont été calculés à l'origine.
    """
    import json as _json
    from brain import db

    run = pipeline.get_run(run_id)
    if not run:
        return None, None, None, None

    cursor_run = run
    visited: set[int] = set()
    while cursor_run and (not cursor_run.get("playbook_json") or not cursor_run.get("persona_id")):
        if cursor_run["id"] in visited:
            break
        visited.add(cursor_run["id"])
        parent = cursor_run.get("parent_run_id")
        if not parent:
            break
        cursor_run = pipeline.get_run(parent)

    if not cursor_run or not cursor_run.get("playbook_json"):
        return None, None, None, None

    raw = cursor_run["playbook_json"]
    try:
        playbook = raw if isinstance(raw, dict) else _json.loads(raw)
    except Exception:
        return None, None, None, None

    persona_id = cursor_run.get("persona_id")
    if not persona_id:
        return None, None, None, None

    with db.cursor() as cur:
        cur.execute(
            "SELECT first_name, age, bio_twitter, backstory, avatar_id_primary, "
            "avatar_id_secondary, voice_signature, vocabulary_yes, vocabulary_no, "
            "profile_photo_prompt, banner_prompt "
            "FROM mkt_personas_emerged WHERE id = %s",
            (persona_id,),
        )
        row = cur.fetchone()
    if not row:
        return None, None, None, None
    return cursor_run, playbook, dict(row), persona_id


def _image_stats_for_run(run_id: int) -> dict:
    """Stats matching images pour décider du défaut checkbox preflight."""
    from brain import image_matcher
    try:
        return image_matcher.stats_for_run(run_id)
    except Exception:
        return {"needs_image": 0, "already_matched": 0, "pending": 0}


# ─── Reprise (full-run) : preflight + launch ────────────────────────────────

@bp.route("/runs/<int:run_id>/full-run", methods=["GET"])
def full_run_preflight(run_id: int):
    """Affiche la page preflight avant la reprise : coût estimé + option images."""
    from brain import csv_parser, cost_estimator

    if not is_api_key_configured():
        flash("Clé API Anthropic absente.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))

    csv_path_str = run.get("archived_csv_path")
    if not csv_path_str:
        flash("CSV source non archivé pour ce run. Re-uploade manuellement.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    csv_path = Path(csv_path_str)
    if not csv_path.exists():
        flash(f"Fichier CSV archivé introuvable : {csv_path.name}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    root_run, parent_playbook, parent_persona, parent_persona_id = _load_parent_playbook_and_persona(run_id)
    if not parent_playbook or not parent_persona:
        flash(
            "Playbook ou persona du run parent introuvable. La reprise ne peut pas réutiliser "
            "l'analyse. Re-uploade le CSV pour un run from scratch.",
            "error",
        )
        return redirect(url_for("tweets.show_run", run_id=run_id))

    # Compter les tweets restants : parse rapide du CSV pour avoir le total
    try:
        parsed = csv_parser.parse_csv(csv_path.read_bytes())
    except Exception as e:
        flash(f"Lecture du CSV archivé impossible : {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    skip_first_n = run.get("max_source_tweets") or 0
    full_csv_count = parsed["valid_rows"]
    n_tweets = max(0, full_csv_count - skip_first_n)
    if n_tweets == 0:
        flash("Le run parent a déjà traité tous les tweets du CSV. Rien à reprendre.", "warning")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    default_adaptation = run.get("model_adaptation") or "claude-sonnet-4-6"
    cost = cost_estimator.estimate_pipeline_cost(
        model_adaptation=default_adaptation,
        n_tweets=n_tweets,
        mode="copywriting",
    )

    parent_image_stats = _image_stats_for_run(run_id)
    default_include_images = parent_image_stats.get("already_matched", 0) > 0

    return render_template(
        "tweets_run_preflight.html",
        mode="resume",
        parent_run=run,
        n_tweets=n_tweets,
        full_csv_count=full_csv_count,
        cost=cost,
        parent_image_stats=parent_image_stats,
        default_include_images=default_include_images,
        launch_url=url_for("tweets.full_run_launch", run_id=run_id),
        count=None,
        available_models=Config.AVAILABLE_MODELS,
        default_adaptation=default_adaptation,
        default_analysis=run.get("model_analysis") or "claude-sonnet-4-6",
    )


@bp.route("/runs/<int:run_id>/full-run/launch", methods=["POST"])
def full_run_launch(run_id: int):
    """Lance effectivement la reprise après confirmation preflight."""
    if not is_api_key_configured():
        flash("Clé API Anthropic absente.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))

    csv_path_str = run.get("archived_csv_path")
    csv_path = Path(csv_path_str) if csv_path_str else None
    if not csv_path or not csv_path.exists():
        flash("CSV archivé introuvable.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    root_run, parent_playbook, parent_persona, parent_persona_id = _load_parent_playbook_and_persona(run_id)
    if not parent_playbook or not parent_persona:
        flash("Playbook ou persona du run parent introuvable.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    import json as _json
    raw_stats = run.get("source_stats_json")
    parent_stats = None
    if raw_stats:
        try:
            parent_stats = raw_stats if isinstance(raw_stats, dict) else _json.loads(raw_stats)
        except Exception:
            parent_stats = None

    skip_first_n = run.get("max_source_tweets") or 0
    include_images = bool(request.form.get("include_images"))
    model_adaptation = (request.form.get("model_adaptation") or "").strip() or None
    model_analysis = (request.form.get("model_analysis") or "").strip() or None
    override_models = {"adaptation": model_adaptation, "analysis": model_analysis}

    print(f"\n[full-run] Reprise depuis #{run_id} · skip top {skip_first_n} · persona '{parent_persona['first_name']}' · images={include_images} · models=adp:{model_adaptation}", flush=True)
    try:
        prep = pipeline.prepare_run(
            file_bytes=csv_path.read_bytes(),
            source_csv_name=run["source_csv_name"],
            max_source_tweets=None,
            parent_run_id=run_id,
            resume_skip_first_n=skip_first_n,
            resume_playbook=parent_playbook,
            resume_stats=parent_stats,
            resume_persona=parent_persona,
            resume_persona_id=parent_persona_id,
            auto_match_images=include_images,
            override_models=override_models,
        )
    except pipeline.PipelineError as e:
        flash(f"Erreur : {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    except Exception as e:
        print(f"[full-run] Exception : {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur inattendue : {type(e).__name__}: {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    pipeline.run_pipeline_async(prep)
    msg = (
        f"Reprise #{prep['run_id']} lancée sur les {prep['parsed']['valid_rows']} tweets restants "
        f"(parent #{run_id} · persona « {parent_persona['first_name']} »"
        f"{' · images auto' if include_images else ''})."
    )
    flash(msg, "success")
    return redirect(url_for("tweets.show_run", run_id=prep["run_id"]))


# ─── Extension : preflight + launch ────────────────────────────────────────

@bp.route("/runs/<int:run_id>/extend", methods=["POST"])
def extend_preflight(run_id: int):
    """Reçoit count depuis la barre d'action, affiche le preflight extension."""
    from brain import cost_estimator

    if not is_api_key_configured():
        flash("Clé API Anthropic absente.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    raw_count = (request.form.get("count") or "").strip()
    if not raw_count.isdigit():
        flash("Nombre de tweets invalide.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    count = int(raw_count)
    if count <= 0 or count > 2000:
        flash("Nombre de tweets hors limites (1-2000).", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))

    root_run, playbook, persona, persona_id = _load_parent_playbook_and_persona(run_id)
    if not playbook or not persona:
        flash(
            "Impossible de trouver le playbook ou la persona en remontant la chaîne. "
            "L'extension nécessite un run racine avec analyse complète.",
            "error",
        )
        return redirect(url_for("tweets.show_run", run_id=run_id))

    default_adaptation = run.get("model_adaptation") or "claude-sonnet-4-6"
    # `count` est exprime en POSTS atomiques (1 thread = 1 post). Le copywriter
    # genere ~1.5x plus de messages pour la marge threading + jusqu'a MAX_EXTRA
    # chunks de EXTRA_CHUNK_SIZE en top-up si la cible posts n'est pas atteinte.
    # On estime sur le CEILING worst case pour que la facture reelle <= annonce.
    from brain.copywriter import (
        POSTS_TO_MESSAGES_OVERSHOOT,
        MAX_EXTRA_EXTENSION_CHUNKS,
        EXTRA_EXTENSION_CHUNK_SIZE,
    )
    import math
    n_messages_ceiling = (
        math.ceil(count * POSTS_TO_MESSAGES_OVERSHOOT)
        + MAX_EXTRA_EXTENSION_CHUNKS * EXTRA_EXTENSION_CHUNK_SIZE
    )
    cost = cost_estimator.estimate_pipeline_cost(
        model_adaptation=default_adaptation,
        n_tweets=n_messages_ceiling,
        mode="extension",
    )

    parent_image_stats = _image_stats_for_run(run_id)
    default_include_images = parent_image_stats.get("already_matched", 0) > 0

    return render_template(
        "tweets_run_preflight.html",
        mode="extend",
        parent_run=run,
        n_tweets=count,
        full_csv_count=None,
        cost=cost,
        parent_image_stats=parent_image_stats,
        default_include_images=default_include_images,
        launch_url=url_for("tweets.extend_launch", run_id=run_id),
        count=count,
        available_models=Config.AVAILABLE_MODELS,
        default_adaptation=default_adaptation,
        default_analysis=run.get("model_analysis") or "claude-sonnet-4-6",
    )


@bp.route("/runs/<int:run_id>/extend/launch", methods=["POST"])
def extend_launch(run_id: int):
    """Lance effectivement l'extension après confirmation preflight."""
    if not is_api_key_configured():
        flash("Clé API Anthropic absente.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    raw_count = (request.form.get("count") or "").strip()
    if not raw_count.isdigit():
        flash("Nombre de tweets invalide.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    count = int(raw_count)
    if count <= 0 or count > 2000:
        flash("Nombre de tweets hors limites (1-2000).", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))

    root_run, playbook, persona, persona_id = _load_parent_playbook_and_persona(run_id)
    if not playbook or not persona:
        flash("Playbook ou persona introuvable.", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    include_images = bool(request.form.get("include_images"))
    model_adaptation = (request.form.get("model_adaptation") or "").strip() or None
    override_models = {"adaptation": model_adaptation}

    print(f"\n[extend] Lancement {count} tweets · parent #{run_id} · root #{root_run['id']} · persona '{persona['first_name']}' · images={include_images} · adp:{model_adaptation}", flush=True)
    try:
        prep = pipeline.prepare_extension_run(
            parent_run_id=run_id,
            count=count,
            playbook=playbook,
            persona=persona,
            persona_id=persona_id,
            source_handle=run.get("source_handle") or root_run.get("source_handle"),
            source_csv_name_parent=root_run.get("source_csv_name"),
            detected_language=run.get("detected_language") or root_run.get("detected_language"),
            auto_match_images=include_images,
            override_models=override_models,
        )
    except pipeline.PipelineError as e:
        flash(f"Erreur : {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    except Exception as e:
        print(f"[extend] Exception : {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur inattendue : {type(e).__name__}: {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    pipeline.run_extension_async(prep)
    flash(
        f"Extension #{prep['extension_idx']} lancée sur le run #{run_id} · "
        f"{count} tweets inventés dans la voix de « {persona['first_name']} »"
        f"{' · images auto' if include_images else ''}.",
        "success",
    )
    return redirect(url_for("tweets.show_run", run_id=run_id))


@bp.route("/runs/<int:run_id>/tweets/<int:tweet_id>/edit", methods=["POST"])
def edit_tweet(run_id: int, tweet_id: int):
    data = request.get_json() or {}
    fields = {}
    for k in ("content", "thread_key", "media_url", "scheduled_at", "status", "notes"):
        if k in data:
            v = data[k]
            if v == "":
                v = None
            fields[k] = v

    if not fields:
        return jsonify({"ok": False, "error": "Aucun champ à éditer."}), 400

    # Normalise + valide content si édité. La normalisation (espaces, ponctuation,
    # jonction URL/texte) est appliquée AVANT la validation pour que l'utilisateur
    # voie en DB la version finale "propre" et pas son brouillon avec espaces oubliés.
    if "content" in fields and fields["content"]:
        from brain.copywriter import _normalize_spacing
        fields["content"] = _normalize_spacing(fields["content"])
        v = cortex_validator.validate_content(fields["content"])
        if not v["ok"]:
            return jsonify({"ok": False, "errors": v["errors"], "warnings": v["warnings"]}), 400

    pipeline.update_tweet(tweet_id, **fields)
    return jsonify({"ok": True, "content": fields.get("content")})


@bp.route("/runs/<int:run_id>/tweets/<int:tweet_id>/delete", methods=["POST"])
def delete_tweet(run_id: int, tweet_id: int):
    pipeline.delete_tweet(tweet_id)
    return jsonify({"ok": True})


@bp.route("/runs/<int:run_id>/tweets/<int:tweet_id>/detach-image", methods=["POST"])
def detach_image(run_id: int, tweet_id: int):
    """Détache l'image du tweet sans la supprimer de la galerie : image_id,
    media_url, image_chosen_at repassent à NULL. L'image reste dispo pour un
    futur matching sur ce tweet ou un autre."""
    from brain import db
    with db.cursor() as cur:
        cur.execute(
            "UPDATE mkt_tweets SET image_id = NULL, media_url = NULL, image_chosen_at = NULL "
            "WHERE id = %s AND csv_run_id = %s RETURNING id",
            (tweet_id, run_id),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"ok": False, "error": "Tweet introuvable pour ce run."}), 404
    return jsonify({"ok": True})


@bp.route("/runs/<int:run_id>/delete", methods=["POST"])
def delete_run(run_id: int):
    """Supprime un run, ses tweets, et optionnellement sa persona si elle devient orpheline."""
    also_persona = bool(request.form.get("also_delete_persona"))
    try:
        stats = pipeline.delete_run(run_id, also_delete_orphan_persona=also_persona)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    except Exception as e:
        print(f"[delete_run] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc(file=sys.stdout)
        flash(f"Erreur suppression : {type(e).__name__}: {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    parts = [f"Run #{run_id} supprimé", f"{stats['tweets_deleted']} tweet(s) supprimé(s)"]
    if stats["persona_deleted"]:
        parts.append(f"persona « {stats['persona_first_name']} » supprimée (devenue orpheline)")
    elif also_persona and stats["persona_id"]:
        parts.append(f"persona « {stats['persona_first_name']} » conservée (d'autres runs la référencent)")
    flash(" · ".join(parts), "success")
    return redirect(url_for("tweets.index"))


@bp.route("/runs/<int:run_id>/match-images", methods=["POST"])
def match_images(run_id: int):
    """Etape 3 : matche en batch tous les tweets needs_image=true / image_id IS NULL
    du run avec la meilleure image (filtree par fit Compaatible + public_url presente).
    Met a jour image_id, image_chosen_at, media_url.

    Lance le matching dans un thread daemon et retourne immediatement 202.
    L'UI poll ensuite /runs/<id>/match-images/status pour afficher la progression."""
    run = pipeline.get_run(run_id)
    if not run:
        return jsonify({"ok": False, "error": "Run introuvable."}), 404

    # Si un matching tourne deja sur ce run, on ne l'ecrase pas.
    existing = image_matcher.get_progress(run_id)
    if existing and existing.get("status") == "running":
        return jsonify({"ok": True, "already_running": True}), 202

    # Nettoyage du snapshot precedent (sinon on garde l'ancien resultat ad vitam).
    image_matcher.cleanup_progress(run_id)

    def _worker(rid: int):
        try:
            image_matcher.match_images_for_run(rid)
        except Exception as e:
            print(f"[match] run #{rid} ECHEC : {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            traceback.print_exc()
            image_matcher._finalize_progress(rid, error=f"{type(e).__name__}: {e}")

    threading.Thread(target=_worker, args=(run_id,), daemon=True).start()
    return jsonify({"ok": True, "started": True}), 202


@bp.route("/runs/<int:run_id>/match-images/status")
def match_images_status(run_id: int):
    """Retourne le snapshot de progression du matching, ou 404 si aucun matching
    n'a ete lance pour ce run depuis le demarrage du serveur."""
    snap = image_matcher.get_progress(run_id)
    if snap is None:
        return jsonify({"ok": False, "error": "Aucun matching connu pour ce run."}), 404
    return jsonify({"ok": True, "progress": snap})


@bp.route("/runs/<int:run_id>/download")
def download(run_id: int):
    run = pipeline.get_run(run_id)
    if not run:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))

    tweets = pipeline.get_tweets_for_run(run_id)
    # Garder uniquement les approved + draft (skip ceux marqués 'rejected' si on en a)
    eligible = [t for t in tweets if t.get("status") in (None, "draft", "approved")]

    # CONTRAT CORTEX : seules ces 4 colonnes partent dans le CSV. Les champs
    # INTERNES (needs_image, image_brief, image_id, image_chosen_at,
    # reasoning, hook_pattern, adaptation_level, etc.) NE DOIVENT JAMAIS
    # apparaitre dans l'export. Cf. feedback_internal_fields_not_in_csv.
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

    filename = f"compaatible_run{run_id}_{run.get('persona_first_name', 'unknown')}.csv"
    return send_file(bio, mimetype="text/csv", as_attachment=True, download_name=filename)


def _sanitize_filename(raw: str | None, fallback: str) -> str:
    """Nettoie un nom de fichier utilisateur pour qu'il soit acceptable comme
    nom de fichier multipart et lisible dans l'UI Cortex.

    - Garde [A-Za-z0-9._-], remplace tout autre caractere (espaces, accents,
      slashes, etc.) par '_'.
    - Strip les '._-' en debut/fin pour eviter les noms degeneres '.csv' ou '_.csv'.
    - Force l'extension .csv (Cortex attend ce type MIME).
    - Cap a 200 caracteres pour eviter les noms aberrants.
    - Si l'entree est vide ou ne contient rien d'utile apres nettoyage, retourne
      le fallback (nom auto-genere par le serveur).
    """
    if not raw or not raw.strip():
        return fallback
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip())
    cleaned = cleaned.strip("._-")
    if not cleaned:
        return fallback
    if cleaned.lower().endswith(".csv"):
        # On normalise l'extension en minuscules sans toucher au reste.
        cleaned = cleaned[:-4] + ".csv"
    else:
        cleaned += ".csv"
    return cleaned[:200]


def _build_cortex_csv(run_id: int) -> tuple[bytes, str, int] | None:
    """Construit le CSV Cortex pour un run. Retourne (csv_bytes, filename, eligible_count)
    ou None si run introuvable. Lève ValueError si aucun tweet éligible.

    CONTRAT CORTEX : seules ces 4 colonnes (content, media_url, scheduled_at,
    thread_key) partent dans le CSV. Les champs INTERNES (needs_image,
    image_brief, image_id, image_chosen_at, reasoning, hook_pattern,
    adaptation_level, etc.) NE DOIVENT JAMAIS apparaitre dans l'export.
    Cf. feedback_internal_fields_not_in_csv en memoire.
    """
    run = pipeline.get_run(run_id)
    if not run:
        return None
    tweets = pipeline.get_tweets_for_run(run_id)
    eligible = [t for t in tweets if t.get("status") in (None, "draft", "approved")]
    if not eligible:
        raise ValueError("Aucun tweet éligible (statut draft/approved) à envoyer.")

    cortex_rows = [{
        "content": t["content"],
        "media_url": t["media_url"] or "",
        "scheduled_at": str(t["scheduled_at"]) if t["scheduled_at"] else "",
        "thread_key": t["thread_key"] or "",
    } for t in eligible]

    csv_text = cortex_validator.format_for_cortex(cortex_rows)
    filename = f"compaatible_run{run_id}_{run.get('persona_first_name', 'unknown')}.csv"
    return csv_text.encode("utf-8"), filename, len(eligible)


@bp.route("/runs/<int:run_id>/send-to-cortex", methods=["POST"])
def send_to_cortex(run_id: int):
    """Envoie le CSV du run directement vers l'API Cortex (POST /api/v1/files multipart).

    Le nom du fichier peut etre customise via le champ `filename` du form ; sinon on
    utilise le nom auto-genere `compaatible_run<id>_<persona>.csv`. Sanitization
    cote serveur dans `_sanitize_filename` (whitelist + force .csv)."""
    try:
        result = _build_cortex_csv(run_id)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))
    if result is None:
        flash("Run introuvable.", "error")
        return redirect(url_for("tweets.index"))

    csv_bytes, default_filename, eligible_count = result
    filename = _sanitize_filename(request.form.get("filename"), default_filename)

    # Validation locale avant envoi : si fatal, on n'appelle pas Cortex (gain de quota + msg plus clair).
    import csv as csvmod
    import io as iomod
    reader = csvmod.DictReader(iomod.StringIO(csv_bytes.decode("utf-8")))
    validation = cortex_validator.validate_batch(list(reader))
    if not validation["ok"]:
        first = validation["fatal_errors"][0]
        flash(
            f"CSV invalide localement (ligne {first['row']}: {first['message']}) — "
            f"corrige d'abord puis renvoie.",
            "error",
        )
        return redirect(url_for("tweets.show_run", run_id=run_id))

    # Archive le CSV envoyé sur disque avant l'upload — permet de re-consulter
    # le contenu exact via l'onglet Fichiers, peu importe le statut Cortex après.
    from datetime import datetime
    import json as _json
    archive_dir = Config.UPLOADS_DIR / "cortex_sent"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    archive_path = archive_dir / archive_filename
    archive_path.write_bytes(csv_bytes)
    archived_csv_path_str = str(archive_path)

    persona_id = run.get("persona_id")

    try:
        payload = cortex_client.upload_csv(csv_bytes, filename)
    except cortex_client.CortexConfigError as e:
        flash(f"Cortex non configuré : {e}", "error")
        return redirect(url_for("settings.index"))
    except cortex_client.CortexError as e:
        # Log l'envoi raté pour traçabilité dans l'onglet Fichiers.
        from brain import db as _db
        with _db.cursor() as _cur:
            _cur.execute(
                """INSERT INTO mkt_cortex_uploads
                   (csv_run_id, persona_id, filename, eligible_count, archived_csv_path,
                    status, error_message)
                   VALUES (%s, %s, %s, %s, %s, 'failed', %s)""",
                (run_id, persona_id, filename, eligible_count, archived_csv_path_str, str(e)),
            )
        flash(f"Envoi Cortex échoué : {e}", "error")
        return redirect(url_for("tweets.show_run", run_id=run_id))

    file_info = payload.get("file") or {}
    file_id = file_info.get("id", "?")
    summary = file_info.get("parse_summary") or {}
    valid = summary.get("validTweets", eligible_count)
    threads = len(summary.get("threads") or [])
    warnings = len(summary.get("warnings") or [])

    # Enregistre l'envoi réussi dans mkt_cortex_uploads pour l'onglet Fichiers.
    from brain import db as _db
    with _db.cursor() as _cur:
        _cur.execute(
            """INSERT INTO mkt_cortex_uploads
               (csv_run_id, persona_id, filename, file_id_cortex, eligible_count,
                cortex_valid_tweets, cortex_threads, cortex_warnings,
                parse_summary_json, archived_csv_path, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sent')""",
            (
                run_id, persona_id, filename, str(file_id), eligible_count,
                valid, threads, warnings,
                _json.dumps(payload, ensure_ascii=False), archived_csv_path_str,
            ),
        )

    parts = [f"{valid} tweet(s) valides envoyés vers Cortex"]
    if threads:
        parts.append(f"{threads} thread(s)")
    if warnings:
        parts.append(f"{warnings} warning(s)")
    parts.append(f"file_id {file_id}")
    flash(" · ".join(parts) + ". Va dans Cortex /fichiers pour attribuer à une persona.", "success")
    return redirect(url_for("tweets.show_run", run_id=run_id))
