"""Orchestration du pipeline tweets : upload → analyze → persona → adapt → validate → save.

Le pipeline tourne en background thread (lancé par la route upload). La page UI poll
l'état du run via brain.run_state pour afficher l'avancement en temps réel.
"""
from __future__ import annotations
import json
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from brain import csv_parser, source_analyzer, persona_generator, copywriter, db, run_state, llm_client
from brain.db import get_settings


class PipelineError(Exception):
    pass


def _log(run_id: int | None, stage: str, msg: str) -> None:
    """Log structuré sur stdout + run_state pour que l'UI le voie en temps réel."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{stage}] {msg}", flush=True)
    sys.stdout.flush()
    if run_id is not None:
        run_state.update_message(run_id, msg, stage_key=stage if stage in {"parse", "analyze", "persona", "copy", "done"} else None)


def _print_run_dashboard(run_id: int) -> None:
    """Affiche le dashboard ASCII du run à la fin du pipeline (ou d'une extension).

    Lit la DB via brain.run_dashboard. Non-bloquant : si la collecte échoue,
    on log l'erreur et on continue — le dashboard ne doit jamais faire planter
    le pipeline.
    """
    try:
        from brain import run_dashboard
        stats = run_dashboard.build(run_id)
        block = run_dashboard.format_text(stats)
        print("", flush=True)
        print(block, flush=True)
        print("", flush=True)
    except Exception as e:
        print(f"[dashboard] echec affichage · {type(e).__name__}: {e}", flush=True)


def prepare_run(
    file_bytes: bytes,
    source_csv_name: str,
    max_source_tweets: int | None = None,
    parent_run_id: int | None = None,
    resume_skip_first_n: int | None = None,
    resume_playbook: dict | None = None,
    resume_stats: dict | None = None,
    resume_persona: dict | None = None,
    resume_persona_id: int | None = None,
    auto_match_images: bool = False,
    override_models: dict | None = None,
) -> dict:
    """Étape synchrone rapide : sauvegarde le fichier, parse le CSV, applique la limite,
    crée la row mkt_csv_runs en status=running. Retourne {run_id, parsed, models}.
    À appeler depuis la route upload AVANT de lancer le thread.

    parent_run_id : si fourni, lien vers un run précédent (utile pour "full run" relancé
    depuis un run limité).

    Mode reprise (resume_*) : quand l'utilisateur relance un preview en full run, on
    réutilise le playbook + la persona déjà calculés par le run parent pour éviter de
    repayer ces étapes. resume_skip_first_n indique combien de tweets sources (triés
    par engagement) ont déjà été traités par le parent : on les saute pour ne copywriter
    que le reliquat.
    """
    settings = get_settings()
    models = {
        "translation": settings["model_translation"],
        "analysis": settings["model_analysis"],
        "adaptation": settings["model_adaptation"],
    }
    # Override par-run (choix UI au preflight). Les clés absentes/None retombent
    # sur la valeur Settings ci-dessus.
    if override_models:
        for k in ("translation", "analysis", "adaptation"):
            v = override_models.get(k)
            if v:
                models[k] = v

    # Sauvegarder le fichier
    from config import Config
    Config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived_path = Config.UPLOADS_DIR / f"{timestamp}_{source_csv_name}"
    archived_path.write_bytes(file_bytes)

    # Parser
    try:
        parsed = csv_parser.parse_csv(file_bytes)
    except Exception as e:
        raise PipelineError(f"Erreur parsing CSV : {e}")

    if parsed["valid_rows"] == 0:
        raise PipelineError(
            "CSV parsé mais 0 ligne valide (content vide ou colonne content introuvable). "
            f"Colonnes détectées : {parsed.get('columns')}"
        )

    # Health check structurel : tag-spam, volume, doublons, longueurs.
    # En mode RESUME (resume_skip_first_n présent), on saute le health check : le CSV
    # parent a déjà été validé et filtré, on lui fait confiance.
    health: dict | None = None
    if not resume_skip_first_n:
        health = csv_parser.validate_csv_health(parsed)
        if health["fatal_errors"]:
            raise PipelineError(
                "CSV invalide structurellement : " + " | ".join(health["fatal_errors"])
            )
        n_before = len(parsed["rows"])
        parsed["rows"] = health["filtered_rows"]
        parsed["valid_rows"] = len(parsed["rows"])
        parsed["total_rows"] = len(parsed["rows"])
        n_after = len(parsed["rows"])
        if n_before != n_after:
            print(f"[health] {n_before - n_after} tag-spam row(s) filtrees ({n_before} -> {n_after})", flush=True)
        for w in health.get("warnings", []):
            print(f"[health] warning: {w}", flush=True)

    full_count = parsed["valid_rows"]

    # Mode reprise : on trie par engagement et on saute les N premiers (déjà traités par le parent).
    # Le copywriter retriera derrière (sort stable) → l'ordre reste cohérent.
    skipped_count = 0
    if resume_skip_first_n and resume_skip_first_n > 0:
        sorted_all = csv_parser.top_n_by_engagement(parsed["rows"], n=len(parsed["rows"]))
        if len(sorted_all) <= resume_skip_first_n:
            raise PipelineError(
                f"Reprise impossible : le run parent a déjà traité tous les {len(sorted_all)} tweets "
                f"valides du CSV (skip_first_n={resume_skip_first_n}). Rien à faire."
            )
        parsed["rows"] = sorted_all[resume_skip_first_n:]
        parsed["valid_rows"] = len(parsed["rows"])
        parsed["total_rows"] = len(parsed["rows"])
        skipped_count = resume_skip_first_n

    # Appliquer la limite tout de suite (toutes les étapes voient le même sous-ensemble)
    truncated = False
    if max_source_tweets and parsed["valid_rows"] > max_source_tweets:
        parsed["rows"] = csv_parser.top_n_by_engagement(parsed["rows"], n=max_source_tweets)
        parsed["valid_rows"] = len(parsed["rows"])
        parsed["total_rows"] = len(parsed["rows"])
        truncated = True

    # Créer la row DB (avec les méta nécessaires pour relancer en full run plus tard)
    run_id = _create_run(
        source_csv_name=source_csv_name,
        source_csv_size_kb=max(1, len(file_bytes) // 1024),
        source_tweets_count=parsed["valid_rows"],
        detected_language=parsed["detected_language"],
        source_handle=parsed["source_handle"],
        model_translation=models["translation"],
        model_analysis=models["analysis"],
        model_adaptation=models["adaptation"],
        archived_csv_path=str(archived_path),
        max_source_tweets=max_source_tweets,
        parent_run_id=parent_run_id,
    )

    # Persiste le health check (warnings + stats) sur le run pour affichage UI
    if health is not None:
        try:
            _update_run(run_id, health_check_json=json.dumps({
                "warnings": health.get("warnings", []),
                "stats": health.get("stats", {}),
            }, ensure_ascii=False))
        except Exception as e:
            print(f"[health] persistence ignoree : {e}", flush=True)

    # Initialiser l'état partagé pour le polling UI
    run_state.init(run_id)
    parse_msg = (
        f"CSV parsé · {parsed['valid_rows']}"
        f"{'/' + str(full_count) if (truncated or skipped_count) else ''} tweets"
        f"{' · reprise (' + str(skipped_count) + ' déjà traités)' if skipped_count else ''}"
        f" · langue={parsed['detected_language']} · handle=@{parsed['source_handle'] or '?'}"
    )
    if health and health.get("warnings"):
        parse_msg += f" · {len(health['warnings'])} warning(s) CSV"
    run_state.begin_stage(run_id, "parse", parse_msg)

    return {
        "run_id": run_id,
        "parsed": parsed,
        "models": models,
        "max_source_tweets": max_source_tweets,
        "source_csv_name": source_csv_name,
        "full_count": full_count,
        "truncated": truncated,
        "skipped_count": skipped_count,
        "resume_playbook": resume_playbook,
        "resume_stats": resume_stats,
        "resume_persona": resume_persona,
        "resume_persona_id": resume_persona_id,
        "parent_run_id": parent_run_id,
        "auto_match_images": auto_match_images,
    }


def run_pipeline_async(prep: dict) -> None:
    """Lance run_pipeline dans un thread daemon. Retourne immédiatement.

    Le thread écrit l'avancement dans run_state (pour la page UI qui poll) et la DB
    (pour les résultats finaux).
    """
    t = threading.Thread(target=_run_in_background, args=(prep,), daemon=True)
    t.start()


def _run_in_background(prep: dict) -> None:
    run_id = prep["run_id"]
    try:
        result = run_pipeline(prep)
    except Exception:
        # Tout est déjà loggé + persisté par run_pipeline. On évite juste que le thread crash silencieux.
        return

    # Extension chaînée upfront depuis le preflight upload : on enchaîne ici
    # tant qu'on est dans le thread daemon, après que le run initial soit completé.
    chain_count = int(prep.get("chain_extension_count") or 0)
    if chain_count <= 0:
        return
    if not result or result.get("paused"):
        return
    if result.get("quota_exhausted"):
        # Inutile de chaîner une extension : la même clé va re-toucher le quota.
        # Mieux : on log et on laisse l'user relancer manuellement quand la quota reset.
        _log(result.get("run_id"), "copy", "Extension chaînée SKIP · quota épuisé sur le run initial")
        return
    persona = result.get("persona")
    persona_id = result.get("persona_id")
    playbook = result.get("playbook")
    if not (persona and persona_id and playbook):
        return

    try:
        run_row = get_run(run_id) or {}
        ext_prep = prepare_extension_run(
            parent_run_id=run_id,
            count=chain_count,
            playbook=playbook,
            persona=persona,
            persona_id=persona_id,
            source_handle=run_row.get("source_handle"),
            source_csv_name_parent=run_row.get("source_csv_name"),
            detected_language=run_row.get("detected_language"),
            auto_match_images=bool(prep.get("auto_match_images")),
            override_models={"adaptation": prep["models"].get("adaptation")},
        )
        _log(run_id, "copy", f"Extension chaînée · démarrage de {chain_count} tweets en invention pure")
        run_extension_pipeline(ext_prep)
    except Exception as e:
        _log(run_id, "fail", f"Extension chaînée ECHOUEE · {type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stdout)


def run_pipeline(prep: dict) -> dict:
    """Pipeline complet à partir d'un dict prepare_run(). Sync : usage normal via thread."""
    run_id = prep["run_id"]
    parsed = prep["parsed"]
    models = prep["models"]
    max_source_tweets = prep["max_source_tweets"]
    source_csv_name = prep["source_csv_name"]

    resume_playbook = prep.get("resume_playbook")
    resume_persona = prep.get("resume_persona")
    resume_persona_id = prep.get("resume_persona_id")
    resume_stats = prep.get("resume_stats")
    parent_run_id = prep.get("parent_run_id")

    pipeline_start = time.time()
    _log(run_id, "parse",
        f"Pipeline #{run_id} demarre · {parsed['valid_rows']} tweets"
        f"{' · reprise depuis #' + str(parent_run_id) if (resume_playbook and parent_run_id) else ''}"
        f" · modeles analysis={models['analysis']} adaptation={models['adaptation']}"
    )

    total_usage = {"input_tokens": 0, "cached_tokens": 0, "cache_creation_tokens": 0, "output_tokens": 0, "cost_usd_estimate": 0.0}

    try:
        # Stage 1 : analyze (skip si on reprend depuis un parent qui l'a déjà fait)
        if resume_playbook:
            playbook = resume_playbook
            n_mechanisms = len(playbook.get("mechanisms", []))
            run_state.skip_stage(run_id, "analyze",
                f"Réutilisé du run #{parent_run_id} · {n_mechanisms} mécanismes (pas de nouvel appel API)"
            )
            _log(run_id, "analyze", f"SKIP · playbook reutilise du run #{parent_run_id} · {n_mechanisms} mecanismes")
            # On persiste le playbook sur le nouveau run pour cohérence (la page UI le lit depuis ce run)
            _update_run(
                run_id,
                playbook_json=json.dumps(playbook, ensure_ascii=False),
                source_stats_json=json.dumps(resume_stats or {}, ensure_ascii=False),
            )
        else:
            run_state.begin_stage(run_id, "analyze", f"Appel API ({models['analysis']}) en cours · injection KB + avatars (~40k tokens)...")
            t0 = time.time()
            _update_run(run_id, current_stage="analyzing")
            analysis = source_analyzer.analyze(parsed, model=models["analysis"])
            _merge_usage(total_usage, analysis["usage"])
            playbook = analysis["playbook"]
            n_mechanisms = len(playbook.get("mechanisms", []))
            _log(run_id, "analyze", f"OK · {n_mechanisms} mecanismes identifies · {analysis['usage']['input_tokens']} in / {analysis['usage']['output_tokens']} out tokens ({time.time()-t0:.1f}s)")
            _update_run(
                run_id,
                playbook_json=json.dumps(playbook, ensure_ascii=False),
                source_stats_json=json.dumps(analysis["stats"], ensure_ascii=False),
            )

        # Stage 2 : persona (skip si on reprend)
        if resume_persona and resume_persona_id:
            persona = resume_persona
            persona_id = resume_persona_id
            run_state.skip_stage(run_id, "persona",
                f"Réutilisé du run #{parent_run_id} · {persona.get('first_name','?')} "
                f"({persona.get('age','?')} ans) · avatar {persona.get('avatar_id_primary','?')}"
            )
            _log(run_id, "persona", f"SKIP · persona #{persona_id} ({persona.get('first_name','?')}) reutilisee du run #{parent_run_id}")
            _update_run(run_id, persona_id=persona_id)
        else:
            run_state.begin_stage(run_id, "persona", f"Appel API ({models['analysis']}) · lecture des tweets sources et émergence de la persona...")
            t0 = time.time()
            _update_run(run_id, current_stage="persona")
            persona_result = persona_generator.generate(
                playbook=playbook,
                model=models["analysis"],
                parsed_csv=parsed,
                source_csv=source_csv_name,
                source_handle=parsed["source_handle"],
            )
            _merge_usage(total_usage, persona_result["usage"])
            persona = persona_result["persona"]
            persona_id = persona_result["persona_id"]
            _log(run_id, "persona", f"OK · {persona.get('first_name','?')} ({persona.get('age','?')} ans) · avatar {persona.get('avatar_id_primary','?')} ({time.time()-t0:.1f}s)")
            _update_run(run_id, persona_id=persona_id)

        # Stage 3 : copywriting
        n_chunks_estimated = (parsed["valid_rows"] + 19) // 20  # CHUNK_SIZE = 20
        run_state.begin_stage(run_id, "copy", f"Appel API ({models['adaptation']}) · ~{n_chunks_estimated} chunks de 20 tweets à adapter...")
        t0 = time.time()
        _update_run(run_id, current_stage="adapting")
        corpus = copywriter.generate_corpus(
            parsed_csv=parsed,
            playbook=playbook,
            persona=persona,
            model=models["adaptation"],
            csv_run_id=run_id,
            persona_id=persona_id,
            max_source_tweets=max_source_tweets,
            progress_run_id=run_id,
            start_chunk_idx=prep.get("start_chunk_idx", 0),
        )
        _merge_usage(total_usage, corpus["usage"])

        # Pause demandée par l'utilisateur entre 2 chunks : on arrête proprement.
        if corpus.get("paused"):
            pause_state = {
                "mode": "copywriting",
                "next_chunk_idx": corpus["next_chunk_idx"],
                "total_chunks": corpus["total_chunks"],
            }
            _update_run(
                run_id,
                current_stage="paused",
                status="paused",
                pause_state_json=json.dumps(pause_state),
                output_tweets_count=corpus["tweets_inserted"],
                input_tokens=total_usage["input_tokens"],
                cached_tokens=total_usage["cached_tokens"],
                output_tokens=total_usage["output_tokens"],
                cost_usd=total_usage["cost_usd_estimate"],
            )
            run_state.mark_paused(run_id, f"Pause au chunk {corpus['next_chunk_idx']}/{corpus['total_chunks']} · {corpus['tweets_inserted']} tweet(s) déjà inséré(s)")
            _log(run_id, "copy", f"PAUSE · chunk {corpus['next_chunk_idx']}/{corpus['total_chunks']} · {corpus['tweets_inserted']} tweets sauvegardés")
            return {
                "run_id": run_id,
                "persona_id": persona_id,
                "persona": persona,
                "playbook": playbook,
                "tweets_inserted": corpus["tweets_inserted"],
                "paused": True,
                "usage": total_usage,
            }

        # Quota épuisé en cours de boucle : on persiste ce qu'on a sauvé,
        # status='completed_partial' (pour distinguer d'un completed plein),
        # et on ne chaine PAS d'extension.
        quota_hit = bool(corpus.get("quota_exhausted"))
        if quota_hit:
            _log(run_id, "copy", f"QUOTA · arret apres {corpus['tweets_inserted']} tweet(s) · pas d'extension chainee")
        else:
            _log(run_id, "copy", f"OK · {corpus['tweets_inserted']} tweets generes en {corpus.get('chunks_processed','?')} chunks ({time.time()-t0:.1f}s)")

        # Auto-matching images si demandé (option preflight)
        if prep.get("auto_match_images"):
            _auto_match_images(run_id)

        # Final : completed (ou completed_partial si quota)
        threads_count = _count_threads(run_id)
        final_status = "completed_partial" if quota_hit else "completed"
        final_stage = "quota_exhausted" if quota_hit else "completed"
        final_err = corpus.get("quota_error") if quota_hit else None
        _update_run(
            run_id,
            current_stage=final_stage,
            status=final_status,
            completed_at=datetime.now().isoformat(),
            output_tweets_count=corpus["tweets_inserted"],
            threads_count=threads_count,
            input_tokens=total_usage["input_tokens"],
            cached_tokens=total_usage["cached_tokens"],
            output_tokens=total_usage["output_tokens"],
            cost_usd=total_usage["cost_usd_estimate"],
            error_message=final_err,
        )

        elapsed = time.time() - pipeline_start
        if quota_hit:
            _log(run_id, "done", f"Pipeline INTERROMPU (quota) · {corpus['tweets_inserted']} tweets · {threads_count} threads · ${total_usage['cost_usd_estimate']:.4f} · {elapsed:.1f}s total")
        else:
            _log(run_id, "done", f"Pipeline complet · {corpus['tweets_inserted']} tweets · {threads_count} threads · ${total_usage['cost_usd_estimate']:.4f} · {elapsed:.1f}s total")
        _print_run_dashboard(run_id)
        run_state.finalize(run_id, success=not quota_hit, error=final_err)

        return {
            "run_id": run_id,
            "persona_id": persona_id,
            "persona": persona,
            "playbook": playbook,
            "tweets_inserted": corpus["tweets_inserted"],
            "threads_count": threads_count,
            "usage": total_usage,
            "quota_exhausted": quota_hit,
        }

    except llm_client.LLMQuotaExhaustedError as e:
        # Quota touché HORS boucle copywriter (analyze ou persona) : pas de partial
        # à sauver, on échoue le run avec un message friendly.
        err_msg = str(e)
        _log(run_id, "fail", f"QUOTA · {err_msg}")
        _update_run(run_id, status="failed", current_stage="quota_exhausted", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        _log(run_id, "fail", f"ECHEC pipeline · {err_msg}")
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        _update_run(run_id, status="failed", current_stage="failed", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise


def prepare_extension_run(
    parent_run_id: int,
    count: int,
    playbook: dict,
    persona: dict,
    persona_id: int,
    source_handle: str | None = None,
    source_csv_name_parent: str | None = None,
    detected_language: str | None = None,
    auto_match_images: bool = False,
    override_models: dict | None = None,
) -> dict:
    """Lance une extension sur le RUN PARENT (pas de nouveau run créé).

    Les nouveaux tweets sont insérés avec `csv_run_id = parent_run_id` et un
    `extension_idx` qui indique le batch (1, 2, 3...). Ainsi le download CSV
    du parent contient TOUS les tweets (originaux + toutes les extensions) et
    on garde la traçabilité via extension_idx.
    """
    settings = get_settings()
    models = {
        "translation": settings["model_translation"],
        "analysis": settings["model_analysis"],
        "adaptation": settings["model_adaptation"],
    }
    if override_models:
        for k in ("translation", "analysis", "adaptation"):
            v = override_models.get(k)
            if v:
                models[k] = v

    if count <= 0:
        raise PipelineError("Le nombre de tweets à inventer doit être > 0.")
    if count > 2000:
        raise PipelineError(f"Trop de tweets demandés en une fois ({count}). Maximum 2000 par run d'extension.")

    # Vérifier que le parent existe et n'est pas déjà en cours
    parent = get_run(parent_run_id)
    if not parent:
        raise PipelineError(f"Run parent #{parent_run_id} introuvable.")
    if parent.get("status") == "running":
        raise PipelineError(f"Run parent #{parent_run_id} est déjà en cours. Attends qu'il se termine.")

    # Calculer next_extension_idx : MAX(extension_idx) sur les tweets du parent + 1
    with db.cursor() as cur:
        cur.execute(
            "SELECT COALESCE(MAX(extension_idx), 0) AS max_idx FROM mkt_tweets WHERE csv_run_id = %s",
            (parent_run_id,),
        )
        next_extension_idx = (cur.fetchone()["max_idx"] or 0) + 1

    # Marquer le run parent comme "extending" pour que l'UI affiche bien le poll
    _update_run(
        parent_run_id,
        status="running",
        current_stage="extending",
        # On garde le model_adaptation existant ou on prend celui choisi pour l'extension
        model_adaptation=models["adaptation"],
    )

    # State mémoire pour le poll UI : on réinit avec parse/analyze/persona déjà cochés
    run_state.init(parent_run_id)
    run_state.skip_stage(parent_run_id, "parse", "Extension : pas de CSV à parser.")
    run_state.skip_stage(parent_run_id, "analyze", "Réutilisé du run d'origine.")
    run_state.skip_stage(parent_run_id, "persona", "Réutilisé du run d'origine.")

    return {
        "run_id": parent_run_id,
        "parent_run_id": parent_run_id,
        "count": count,
        "extension_idx": next_extension_idx,
        "playbook": playbook,
        "persona": persona,
        "persona_id": persona_id,
        "models": models,
        "source_handle": source_handle,
        "auto_match_images": auto_match_images,
    }


def run_extension_async(prep: dict) -> None:
    """Lance run_extension_pipeline dans un thread daemon."""
    t = threading.Thread(target=_run_extension_in_background, args=(prep,), daemon=True)
    t.start()


def _run_extension_in_background(prep: dict) -> None:
    try:
        run_extension_pipeline(prep)
    except Exception:
        pass


def run_extension_pipeline(prep: dict) -> dict:
    """Pipeline extension : ajoute N tweets au RUN PARENT avec extension_idx.

    On opère sur le parent_run_id, donc :
    - les tweets sont insérés avec csv_run_id = parent_run_id et extension_idx = N
    - les métriques (cost, tokens, output_tweets_count, threads_count) sont CUMULÉES
      sur le parent au lieu d'être remplacées
    """
    from brain import copywriter

    run_id = prep["run_id"]  # == parent_run_id depuis prepare_extension_run
    parent_run_id = prep["parent_run_id"]
    count = prep["count"]
    extension_idx = prep["extension_idx"]
    playbook = prep["playbook"]
    persona = prep["persona"]
    persona_id = prep["persona_id"]
    models = prep["models"]

    # Lit l'état actuel du parent pour cumuler les métriques
    parent_initial = get_run(parent_run_id) or {}
    base_cost = float(parent_initial.get("cost_usd") or 0.0)
    base_input = int(parent_initial.get("input_tokens") or 0)
    base_cached = int(parent_initial.get("cached_tokens") or 0)
    base_output = int(parent_initial.get("output_tokens") or 0)

    pipeline_start = time.time()
    _log(run_id, "parse", f"Extension #{extension_idx} sur run #{parent_run_id} demarre · {count} tweets demandes · modele {models['adaptation']}")

    total_usage = {"input_tokens": 0, "cached_tokens": 0, "cache_creation_tokens": 0, "output_tokens": 0, "cost_usd_estimate": 0.0}

    try:
        # Échantillon des tweets déjà produits par cette persona (calibre de voix)
        existing_sample = _fetch_voice_sample(persona_id, limit=60)
        _log(run_id, "copy", f"Calibre de voix · {len(existing_sample)} tweets existants extraits de la persona #{persona_id}")

        # Ratio mentions Compaatible observé sur les tweets ORIGINAUX (cible naturelle)
        mention_stats = _fetch_persona_mention_ratio(persona_id)
        if mention_stats:
            _log(run_id, "copy", f"Cible mentions · {mention_stats['named']}/{mention_stats['total']} originaux = {mention_stats['ratio']*100:.1f}% (a repliquer en extension)")
        else:
            _log(run_id, "copy", "Cible mentions · pas assez de tweets originaux (< 20) pour calculer le ratio, fallback 5-8%")

        # Ratios stylistiques (threads vs isoles, densite image) sur les originaux
        # → on calque l'extension sur ce que la persona a deja fait, pas sur une
        # doctrine generique. Coherence maximale du compte dans le temps.
        style_stats = _fetch_persona_style_stats(persona_id)
        if style_stats:
            _log(
                run_id, "copy",
                f"Cible style · threads {style_stats['thread_posts']}/{style_stats['total_posts']} posts = "
                f"{style_stats['thread_post_ratio']*100:.0f}% · images {style_stats['img_msgs']}/{style_stats['total_msgs']} msgs = "
                f"{style_stats['image_ratio']*100:.0f}% (a repliquer en extension)"
            )
        else:
            _log(run_id, "copy", "Cible style · pas assez de posts originaux (< 15), fallback doctrine generique")

        # Génération
        n_chunks_estimated = (count + 19) // 20
        run_state.begin_stage(run_id, "copy", f"Extension #{extension_idx} · {models['adaptation']} · ~{n_chunks_estimated} chunks à inventer...")
        t0 = time.time()
        _update_run(run_id, current_stage="extending")
        corpus = copywriter.generate_extension(
            playbook=playbook,
            persona=persona,
            count=count,
            existing_sample=existing_sample,
            model=models["adaptation"],
            csv_run_id=parent_run_id,
            persona_id=persona_id,
            progress_run_id=run_id,
            start_chunk_idx=prep.get("start_chunk_idx", 0),
            extension_idx=extension_idx,
            mention_stats=mention_stats,
            style_stats=style_stats,
        )
        _merge_usage(total_usage, corpus["usage"])

        # Compteur cumulé : tous les tweets du parent (originaux + toutes extensions)
        cumulative_tweets = _count_run_tweets(parent_run_id)
        cumulative_threads = _count_threads(parent_run_id)

        if corpus.get("paused"):
            pause_state = {
                "mode": "extension",
                "next_chunk_idx": corpus["next_chunk_idx"],
                "total_chunks": corpus["total_chunks"],
                "extension_idx": extension_idx,
                "count": count,
                # Persist `extra_done` pour que le top-up apres reprise reparte
                # la ou il s'est arrete et respecte le plafond MAX_EXTRA.
                "extra_done": int(corpus.get("extra_done") or 0),
            }
            _update_run(
                run_id,
                current_stage="paused",
                status="paused",
                pause_state_json=json.dumps(pause_state),
                output_tweets_count=cumulative_tweets,
                threads_count=cumulative_threads,
                input_tokens=base_input + total_usage["input_tokens"],
                cached_tokens=base_cached + total_usage["cached_tokens"],
                output_tokens=base_output + total_usage["output_tokens"],
                cost_usd=base_cost + total_usage["cost_usd_estimate"],
            )
            run_state.mark_paused(run_id, f"Pause au chunk {corpus['next_chunk_idx']}/{corpus['total_chunks']} (extension #{extension_idx}) · {corpus['tweets_inserted']} tweet(s) déjà inséré(s)")
            _log(run_id, "copy", f"PAUSE extension #{extension_idx} · chunk {corpus['next_chunk_idx']}/{corpus['total_chunks']} · {corpus['tweets_inserted']} tweets sauvegardés")
            return {
                "run_id": run_id,
                "persona_id": persona_id,
                "tweets_inserted": corpus["tweets_inserted"],
                "paused": True,
                "usage": total_usage,
            }

        quota_hit = bool(corpus.get("quota_exhausted"))
        if quota_hit:
            _log(run_id, "copy", f"QUOTA · extension #{extension_idx} interrompue apres {corpus['tweets_inserted']} tweet(s)")
        else:
            _log(run_id, "copy", f"OK · extension #{extension_idx} : {corpus['tweets_inserted']} tweets inventes en {corpus.get('chunks_processed','?')} chunks ({time.time()-t0:.1f}s)")

        # Auto-matching images si demandé (option preflight)
        if prep.get("auto_match_images"):
            _auto_match_images(run_id)

        # Final : on cumule les coûts + tokens sur le parent
        final_status = "completed_partial" if quota_hit else "completed"
        final_stage = "quota_exhausted" if quota_hit else "completed"
        final_err = corpus.get("quota_error") if quota_hit else None
        _update_run(
            run_id,
            current_stage=final_stage,
            status=final_status,
            completed_at=datetime.now().isoformat(),
            output_tweets_count=cumulative_tweets,
            threads_count=cumulative_threads,
            input_tokens=base_input + total_usage["input_tokens"],
            cached_tokens=base_cached + total_usage["cached_tokens"],
            output_tokens=base_output + total_usage["output_tokens"],
            cost_usd=base_cost + total_usage["cost_usd_estimate"],
            error_message=final_err,
        )

        elapsed = time.time() - pipeline_start
        if quota_hit:
            _log(run_id, "done", f"Extension #{extension_idx} INTERROMPUE (quota) · {corpus['tweets_inserted']} nouveaux tweets · cumul total {cumulative_tweets} · ${total_usage['cost_usd_estimate']:.4f} · {elapsed:.1f}s")
        else:
            _log(run_id, "done", f"Extension #{extension_idx} complete · {corpus['tweets_inserted']} nouveaux tweets · cumul total {cumulative_tweets} · ${total_usage['cost_usd_estimate']:.4f} (extension) · {elapsed:.1f}s")
        _print_run_dashboard(run_id)
        run_state.finalize(run_id, success=not quota_hit, error=final_err)

        return {
            "run_id": run_id,
            "persona_id": persona_id,
            "tweets_inserted": corpus["tweets_inserted"],
            "threads_count": cumulative_threads,
            "usage": total_usage,
            "quota_exhausted": quota_hit,
        }

    except llm_client.LLMQuotaExhaustedError as e:
        err_msg = str(e)
        _log(run_id, "fail", f"QUOTA extension · {err_msg}")
        _update_run(run_id, status="failed", current_stage="quota_exhausted", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        _log(run_id, "fail", f"ECHEC extension · {err_msg}")
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        _update_run(run_id, status="failed", current_stage="failed", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise


# ─── Pipeline pour persona créée manuellement (sans CSV source) ──────────────

def prepare_manual_run(
    persona_id: int,
    count: int,
    model: str,
    auto_match_images: bool = False,
) -> dict:
    """Prépare un run pour une persona créée manuellement (sans CSV source).

    Crée un nouveau run racine (pas d'extension d'un parent) avec :
    - playbook_json = {} (la persona manuelle n'a pas de mécaniques extraites
      d'un compte source ; le LLM s'appuie uniquement sur la fiche avatar +
      voix + techniques copywriting universelles du system prompt).
    - source_csv_name = '(persona manuelle)' (marqueur pour distinguer).
    - parent_run_id = NULL (c'est un run racine pour cette persona).

    Réutilise `copywriter.generate_extension` qui sait déjà inventer depuis
    persona + playbook sans tweets sources. Pour ce run, extension_idx=None
    → les tweets seront marqués comme originaux de la persona.
    """
    if count <= 0:
        raise PipelineError("Le nombre de tweets à inventer doit être > 0.")
    if count > 2000:
        raise PipelineError(f"Trop de tweets demandés ({count}). Maximum 2000 par run.")

    # Charge la persona depuis DB pour vérifier qu'elle existe + construire le dict
    with db.cursor() as cur:
        cur.execute(
            "SELECT first_name, age, gender, bio_twitter, backstory, avatar_id_primary, "
            "avatar_id_secondary, voice_signature, vocabulary_yes, vocabulary_no, "
            "profile_photo_prompt, banner_prompt FROM mkt_personas_emerged WHERE id = %s",
            (persona_id,),
        )
        row = cur.fetchone()
    if not row:
        raise PipelineError(f"Persona #{persona_id} introuvable.")
    persona = dict(row)

    # Création du run row (pas de CSV, pas de playbook)
    run_id = _create_run(
        persona_id=persona_id,
        source_csv_name="(persona manuelle)",
        source_csv_size_kb=0,
        source_tweets_count=0,
        model_translation=None,
        model_analysis=None,
        model_adaptation=model,
        playbook_json=json.dumps({}),
        current_stage="copy",
        parent_run_id=None,
    )

    # State mémoire pour le polling UI : skip parse/analyze/persona
    run_state.init(run_id)
    run_state.skip_stage(run_id, "parse", "Persona manuelle : pas de CSV à parser.")
    run_state.skip_stage(run_id, "analyze", "Persona manuelle : pas de compte source à analyser.")
    run_state.skip_stage(run_id, "persona", "Persona déjà créée manuellement.")

    return {
        "run_id": run_id,
        "count": count,
        "persona": persona,
        "persona_id": persona_id,
        "model": model,
        "auto_match_images": auto_match_images,
    }


def run_manual_async(prep: dict) -> None:
    """Lance run_manual_pipeline dans un thread daemon."""
    t = threading.Thread(target=_run_manual_in_background, args=(prep,), daemon=True)
    t.start()


def _run_manual_in_background(prep: dict) -> None:
    try:
        run_manual_pipeline(prep)
    except Exception:
        pass


def run_manual_pipeline(prep: dict) -> dict:
    """Génère N tweets pour une persona manuelle (run racine, pas extension).

    Réutilise `copywriter.generate_extension` (qui sait inventer sans sources)
    mais avec extension_idx=None pour que les tweets soient stockés comme
    originaux de cette persona.
    """
    from brain import copywriter

    run_id = prep["run_id"]
    count = prep["count"]
    persona = prep["persona"]
    persona_id = prep["persona_id"]
    model = prep["model"]

    pipeline_start = time.time()
    _log(run_id, "parse", f"Run manuel sur persona #{persona_id} ({persona['first_name']}) demarre · {count} posts demandes · modele {model}")

    total_usage = {"input_tokens": 0, "cached_tokens": 0, "cache_creation_tokens": 0, "output_tokens": 0, "cost_usd_estimate": 0.0}

    try:
        # Échantillon de voix : pour une persona manuelle au premier run, il n'y a
        # encore aucun tweet existant. Le sample sera vide, et la consigne système
        # gère ce cas ("(aucun tweet existant : démarrage du corpus)").
        existing_sample = _fetch_voice_sample(persona_id, limit=60)
        _log(run_id, "copy", f"Calibre de voix · {len(existing_sample)} tweets existants (vide pour 1er run manuel)")

        # Stats persona : None au 1er run (pas assez de tweets pour calculer)
        mention_stats = _fetch_persona_mention_ratio(persona_id)
        style_stats = _fetch_persona_style_stats(persona_id)
        if mention_stats is None:
            _log(run_id, "copy", "Cible mentions · 1er run manuel, fallback doctrine 5-8% du prompt")
        if style_stats is None:
            _log(run_id, "copy", "Cible style · 1er run manuel, fallback jugement editorial du prompt")

        n_chunks_estimated = (count + 19) // 20
        run_state.begin_stage(run_id, "copy", f"Manuel · {model} · ~{n_chunks_estimated} chunks à inventer...")
        t0 = time.time()
        _update_run(run_id, current_stage="copying")

        # Playbook vide : la persona manuelle n'en a pas. Le copywriter s'appuie
        # uniquement sur le system prompt (avatars + techniques + cascade) + persona.
        corpus = copywriter.generate_extension(
            playbook={},
            persona=persona,
            count=count,
            existing_sample=existing_sample,
            model=model,
            csv_run_id=run_id,        # le run lui-même est la "racine"
            persona_id=persona_id,
            progress_run_id=run_id,
            start_chunk_idx=0,
            extension_idx=None,       # tweets = originaux de la persona
            mention_stats=mention_stats,
            style_stats=style_stats,
        )
        _merge_usage(total_usage, corpus["usage"])

        cumulative_tweets = _count_run_tweets(run_id)
        cumulative_threads = _count_threads(run_id)

        if corpus.get("paused"):
            pause_state = {
                "mode": "manual",
                "next_chunk_idx": corpus["next_chunk_idx"],
                "total_chunks": corpus["total_chunks"],
                "count": count,
                "extra_done": int(corpus.get("extra_done") or 0),
            }
            _update_run(
                run_id,
                current_stage="paused",
                status="paused",
                pause_state_json=json.dumps(pause_state),
                output_tweets_count=cumulative_tweets,
                threads_count=cumulative_threads,
                input_tokens=total_usage["input_tokens"],
                cached_tokens=total_usage["cached_tokens"],
                output_tokens=total_usage["output_tokens"],
                cost_usd=total_usage["cost_usd_estimate"],
            )
            run_state.mark_paused(run_id, f"Pause au chunk {corpus['next_chunk_idx']}/{corpus['total_chunks']} · {corpus['tweets_inserted']} tweet(s) déjà inséré(s)")
            _log(run_id, "copy", f"PAUSE manuel · chunk {corpus['next_chunk_idx']}/{corpus['total_chunks']} · {corpus['tweets_inserted']} tweets sauvegardés")
            return {
                "run_id": run_id,
                "persona_id": persona_id,
                "tweets_inserted": corpus["tweets_inserted"],
                "paused": True,
                "usage": total_usage,
            }

        quota_hit = bool(corpus.get("quota_exhausted"))
        if quota_hit:
            _log(run_id, "copy", f"QUOTA · run manuel interrompu apres {corpus['tweets_inserted']} tweet(s)")
        else:
            _log(run_id, "copy", f"OK · run manuel : {corpus['tweets_inserted']} tweets inventes en {corpus.get('chunks_processed','?')} chunks ({time.time()-t0:.1f}s)")

        if prep.get("auto_match_images"):
            _auto_match_images(run_id)

        final_status = "completed_partial" if quota_hit else "completed"
        final_stage = "quota_exhausted" if quota_hit else "completed"
        final_err = corpus.get("quota_error") if quota_hit else None
        _update_run(
            run_id,
            current_stage=final_stage,
            status=final_status,
            completed_at=datetime.now().isoformat(),
            output_tweets_count=cumulative_tweets,
            threads_count=cumulative_threads,
            input_tokens=total_usage["input_tokens"],
            cached_tokens=total_usage["cached_tokens"],
            output_tokens=total_usage["output_tokens"],
            cost_usd=total_usage["cost_usd_estimate"],
            error_message=final_err,
        )

        elapsed = time.time() - pipeline_start
        _log(run_id, "done", f"Run manuel {'INTERROMPU (quota)' if quota_hit else 'complet'} · {cumulative_tweets} tweets · ${total_usage['cost_usd_estimate']:.4f} · {elapsed:.1f}s")
        _print_run_dashboard(run_id)
        run_state.finalize(run_id, success=not quota_hit, error=final_err)

        return {
            "run_id": run_id,
            "persona_id": persona_id,
            "tweets_inserted": corpus["tweets_inserted"],
            "threads_count": cumulative_threads,
            "usage": total_usage,
            "quota_exhausted": quota_hit,
        }

    except llm_client.LLMQuotaExhaustedError as e:
        err_msg = str(e)
        _log(run_id, "fail", f"QUOTA run manuel · {err_msg}")
        _update_run(run_id, status="failed", current_stage="quota_exhausted", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        _log(run_id, "fail", f"ECHEC run manuel · {err_msg}")
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        _update_run(run_id, status="failed", current_stage="failed", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise


def resume_paused_async(run_id: int, override_models: dict | None = None) -> None:
    """Lance la reprise d'un run paused dans un thread daemon."""
    t = threading.Thread(target=_resume_paused_in_background, args=(run_id, override_models), daemon=True)
    t.start()


def _resume_paused_in_background(run_id: int, override_models: dict | None) -> None:
    try:
        resume_paused_pipeline(run_id, override_models)
    except Exception:
        pass


def resume_paused_pipeline(run_id: int, override_models: dict | None = None) -> dict:
    """Reprend un run en status='paused' à partir du chunk sauvegardé.

    Lit pause_state_json pour savoir où reprendre (next_chunk_idx) et dans quel
    mode ('copywriting' | 'extension'). Permet de changer le modèle d'adaptation
    via override_models : {'adaptation': '<id>'}.
    """
    from brain import copywriter
    from config import Config

    run = get_run(run_id)
    if not run:
        raise PipelineError(f"Run #{run_id} introuvable.")
    if run.get("status") != "paused":
        raise PipelineError(f"Run #{run_id} n'est pas en pause (status={run.get('status')}).")
    raw = run.get("pause_state_json")
    if not raw:
        raise PipelineError(f"Run #{run_id} paused mais pause_state_json absent : impossible de reprendre.")
    pause_state = raw if isinstance(raw, dict) else json.loads(raw)
    mode = pause_state.get("mode")
    start_chunk_idx = int(pause_state.get("next_chunk_idx") or 0)

    # Modèle adaptation : override > celui du run > settings
    model_adaptation = (override_models or {}).get("adaptation") or run.get("model_adaptation")
    if not model_adaptation:
        settings = get_settings()
        model_adaptation = settings["model_adaptation"]

    # Persona depuis DB
    persona_id = run.get("persona_id")
    if not persona_id:
        raise PipelineError(f"Run #{run_id} paused sans persona_id : impossible de reprendre.")
    with db.cursor() as cur:
        cur.execute(
            "SELECT first_name, age, bio_twitter, backstory, avatar_id_primary, "
            "avatar_id_secondary, voice_signature, vocabulary_yes, vocabulary_no, "
            "profile_photo_prompt, banner_prompt FROM mkt_personas_emerged WHERE id = %s",
            (persona_id,),
        )
        row = cur.fetchone()
    if not row:
        raise PipelineError(f"Persona #{persona_id} introuvable.")
    persona = dict(row)

    # Playbook depuis DB
    raw_pb = run.get("playbook_json")
    if not raw_pb:
        raise PipelineError(f"Run #{run_id} sans playbook_json.")
    playbook = raw_pb if isinstance(raw_pb, dict) else json.loads(raw_pb)

    # Reset status + clear pause_state
    _update_run(run_id, status="running", current_stage="adapting", pause_state_json=None, error_message=None)
    if run_state.get(run_id) is None:
        # État mémoire perdu (typique : reprise après restart Flask). On ré-initialise
        # et on marque parse/analyze/persona comme déjà faits pour que l'UI les affiche
        # cochés et non pas en attente.
        run_state.init(run_id)
        run_state.skip_stage(run_id, "parse", "Déjà fait avant la pause.")
        run_state.skip_stage(run_id, "analyze", "Déjà fait avant la pause.")
        run_state.skip_stage(run_id, "persona", "Déjà fait avant la pause.")
    else:
        # Run encore en mémoire (typique : reprise immédiate sans restart Flask).
        # Clear ended_at + status sinon elapsed_s reste figé à la valeur de pause.
        run_state.clear_pause_for_resume(run_id)
    run_state.begin_stage(run_id, "copy", f"Reprise · modèle {model_adaptation} · chunk {start_chunk_idx+1}/{pause_state.get('total_chunks','?')}")
    _log(run_id, "copy", f"RESUME · mode={mode} · start_chunk={start_chunk_idx} · model={model_adaptation}")

    total_usage = {"input_tokens": run.get("input_tokens") or 0,
                   "cached_tokens": run.get("cached_tokens") or 0,
                   "cache_creation_tokens": 0,
                   "output_tokens": run.get("output_tokens") or 0,
                   "cost_usd_estimate": float(run.get("cost_usd") or 0.0)}

    try:
        if mode == "copywriting":
            csv_path_str = run.get("archived_csv_path")
            if not csv_path_str:
                raise PipelineError(f"Run #{run_id} sans archived_csv_path : impossible de reprendre le copywriting.")
            from pathlib import Path
            from brain import csv_parser
            csv_path = Path(csv_path_str)
            if not csv_path.exists():
                raise PipelineError(f"CSV archivé introuvable : {csv_path.name}")
            parsed = csv_parser.parse_csv(csv_path.read_bytes())
            # Re-applique le health filter pour rester cohérent avec le run initial
            health = csv_parser.validate_csv_health(parsed)
            parsed["rows"] = health["filtered_rows"]
            parsed["valid_rows"] = len(parsed["rows"])
            corpus = copywriter.generate_corpus(
                parsed_csv=parsed,
                playbook=playbook,
                persona=persona,
                model=model_adaptation,
                csv_run_id=run_id,
                persona_id=persona_id,
                max_source_tweets=run.get("max_source_tweets"),
                progress_run_id=run_id,
                start_chunk_idx=start_chunk_idx,
            )
        elif mode == "extension":
            # Reprise d'une extension : on récupère count + extension_idx depuis pause_state
            count = int(pause_state.get("count") or 0)
            ext_idx = pause_state.get("extension_idx")
            if not count or not ext_idx:
                raise PipelineError(f"Pause state d'extension incomplet (count={count}, extension_idx={ext_idx})")
            existing_sample = _fetch_voice_sample(persona_id, limit=60)
            mention_stats = _fetch_persona_mention_ratio(persona_id)
            style_stats = _fetch_persona_style_stats(persona_id)
            # Reprise des top-ups si la pause est arrivee pendant le top-up
            # (extra_done > 0). 0 si la pause etait dans la boucle principale.
            resume_extra_done = int(pause_state.get("extra_done") or 0)
            corpus = copywriter.generate_extension(
                playbook=playbook,
                persona=persona,
                count=count,
                existing_sample=existing_sample,
                model=model_adaptation,
                csv_run_id=run_id,
                persona_id=persona_id,
                progress_run_id=run_id,
                start_chunk_idx=start_chunk_idx,
                extension_idx=int(ext_idx),
                mention_stats=mention_stats,
                style_stats=style_stats,
                start_extra_done=resume_extra_done,
            )
        else:
            raise PipelineError(f"Mode pause inconnu : {mode}")

        # Merge usage (additif sur le partiel déjà payé)
        for k in total_usage:
            if k in corpus.get("usage", {}):
                total_usage[k] += corpus["usage"][k]

        # Mémorise le modèle effectivement utilisé pour la reprise (utile post-mortem)
        _update_run(run_id, model_adaptation=model_adaptation)

        # Pause à nouveau demandée pendant la reprise ?
        if corpus.get("paused"):
            pause_state2 = {
                "mode": mode,
                "next_chunk_idx": corpus["next_chunk_idx"],
                "total_chunks": corpus["total_chunks"],
            }
            new_total_out = (run.get("output_tweets_count") or 0) + corpus["tweets_inserted"]
            _update_run(
                run_id,
                current_stage="paused",
                status="paused",
                pause_state_json=json.dumps(pause_state2),
                output_tweets_count=new_total_out,
                input_tokens=total_usage["input_tokens"],
                cached_tokens=total_usage["cached_tokens"],
                output_tokens=total_usage["output_tokens"],
                cost_usd=total_usage["cost_usd_estimate"],
            )
            run_state.mark_paused(run_id, f"Pause au chunk {corpus['next_chunk_idx']}/{corpus['total_chunks']} · cumul {new_total_out} tweet(s)")
            return {"run_id": run_id, "paused": True, "tweets_inserted": new_total_out, "usage": total_usage}

        # Terminé (ou quota épuisé en cours de reprise)
        new_total_out = (run.get("output_tweets_count") or 0) + corpus["tweets_inserted"]
        threads_count = _count_threads(run_id)
        quota_hit = bool(corpus.get("quota_exhausted"))
        final_status = "completed_partial" if quota_hit else "completed"
        final_stage = "quota_exhausted" if quota_hit else "completed"
        final_err = corpus.get("quota_error") if quota_hit else None
        _update_run(
            run_id,
            current_stage=final_stage,
            status=final_status,
            completed_at=datetime.now().isoformat(),
            output_tweets_count=new_total_out,
            threads_count=threads_count,
            input_tokens=total_usage["input_tokens"],
            cached_tokens=total_usage["cached_tokens"],
            output_tokens=total_usage["output_tokens"],
            cost_usd=total_usage["cost_usd_estimate"],
            error_message=final_err,
        )
        if quota_hit:
            _log(run_id, "done", f"Reprise INTERROMPUE (quota) · {new_total_out} tweets cumul · ${total_usage['cost_usd_estimate']:.4f}")
        else:
            _log(run_id, "done", f"Reprise terminée · {new_total_out} tweets cumul · ${total_usage['cost_usd_estimate']:.4f}")
        run_state.finalize(run_id, success=not quota_hit, error=final_err)
        return {"run_id": run_id, "paused": False, "tweets_inserted": new_total_out, "usage": total_usage, "quota_exhausted": quota_hit}

    except llm_client.LLMQuotaExhaustedError as e:
        err_msg = str(e)
        _log(run_id, "fail", f"QUOTA reprise · {err_msg}")
        _update_run(run_id, status="failed", current_stage="quota_exhausted", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise

    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        _log(run_id, "fail", f"ECHEC reprise · {err_msg}")
        traceback.print_exc(file=sys.stdout)
        _update_run(run_id, status="failed", current_stage="failed", error_message=err_msg)
        run_state.finalize(run_id, success=False, error=err_msg)
        raise


def _auto_match_images(run_id: int) -> None:
    """Lance image_matcher.match_images_for_run et logge le résultat sans planter le pipeline.

    Le matching est local (SQL/Python) et rapide. On l'invoque post-copy quand l'user a
    coché l'option dans le preflight.
    """
    try:
        from brain import image_matcher
        result = image_matcher.match_images_for_run(run_id)
        parts = [f"{result.get('matched', 0)} tweet(s) matche(s)"]
        if result.get("no_brief"):
            parts.append(f"{result['no_brief']} sans brief")
        if result.get("no_candidate"):
            parts.append(f"{result['no_candidate']} sans candidate")
        parts.append(f"pool {result.get('pool_size', 0)} images eligibles")
        _log(run_id, "copy", "Images · " + " · ".join(parts))
    except Exception as e:
        # Non-bloquant : on logge mais on ne fait pas échouer le run pour ça
        _log(run_id, "copy", f"Auto-matching images ECHEC (non-bloquant) · {type(e).__name__}: {e}")


def _fetch_voice_sample(persona_id: int, limit: int = 60) -> list[str]:
    """Récupère un échantillon de tweets déjà produits par la persona pour calibrer la voix.

    Stratégie : on échantillonne UNIQUEMENT sur les tweets ORIGINAUX (extension_idx IS NULL).
    Raison : si on incluait les extensions précédentes, chaque nouvelle extension se
    calibrerait sur les précédentes — la voix dérive en se compoundant à chaque génération
    (analyse menée sur run 56 Thaïs : mentions Compaatible 14% origines → 23% en ext,
    "méthode" ×8, "30 facettes" ×5). La voix de référence reste celle adaptée des sources.

    Si la persona n'a aucun tweet original encore (cas limite : extension lancée sur un run
    vide), fallback sur tous les tweets de la persona.
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT content FROM mkt_tweets WHERE persona_id = %s "
            "AND extension_idx IS NULL "
            "ORDER BY created_at DESC, id DESC LIMIT %s",
            (persona_id, limit),
        )
        rows = cur.fetchall()
        if not rows:
            # Fallback : pas d'originaux disponibles, on prend ce qu'on a
            cur.execute(
                "SELECT content FROM mkt_tweets WHERE persona_id = %s "
                "ORDER BY created_at DESC, id DESC LIMIT %s",
                (persona_id, limit),
            )
            rows = cur.fetchall()
    return [r["content"] for r in rows if r.get("content")]


def _fetch_persona_mention_ratio(persona_id: int) -> dict | None:
    """Calcule le ratio de mentions Compaatible sur les tweets ORIGINAUX de la persona
    (extension_idx IS NULL). Sert de cible naturelle pour les extensions :
    on replique le ratio observe au lieu d'imposer une fourchette generique.

    Retourne {total, named, ratio, source} ou None si pas assez de tweets (< 20)
    pour un calcul fiable (alors le caller utilisera le fallback 5-8%).
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS total, "
            "COUNT(*) FILTER (WHERE LOWER(content) LIKE '%%compaatible%%') AS named "
            "FROM mkt_tweets WHERE persona_id = %s AND extension_idx IS NULL",
            (persona_id,),
        )
        row = cur.fetchone()
    total = int(row.get("total") or 0)
    named = int(row.get("named") or 0)
    if total < 20:
        return None
    return {"total": total, "named": named, "ratio": named / total, "source": "originaux"}


def _fetch_persona_style_stats(persona_id: int) -> dict | None:
    """Calcule deux ratios stylistiques sur les tweets ORIGINAUX de la persona
    (extension_idx IS NULL), a repliquer dans les extensions pour maximiser la
    coherence du compte dans le temps :

    - thread_post_ratio : sur l'ensemble des POSTS atomiques (1 thread = 1 post,
      1 tweet isole = 1 post), part des posts qui sont des threads. C'est la
      vraie cadence "thread vs isole" qu'a la persona dans son feed.
    - image_ratio : part des messages avec needs_image=TRUE. Donne la densite
      visuelle a laquelle la persona a habitue son audience.

    Retourne None si pas assez de posts (< 15) pour que le ratio soit stable.
    Dans ce cas le caller utilisera la doctrine generique du prompt.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE thread_key IS NULL) AS isolated_msgs,
              COUNT(DISTINCT thread_key) FILTER (WHERE thread_key IS NOT NULL) AS thread_posts,
              COUNT(*) AS total_msgs,
              COUNT(*) FILTER (WHERE needs_image = TRUE) AS img_msgs
            FROM mkt_tweets
            WHERE persona_id = %s AND extension_idx IS NULL
            """,
            (persona_id,),
        )
        row = cur.fetchone()
    isolated_posts = int(row.get("isolated_msgs") or 0)
    thread_posts = int(row.get("thread_posts") or 0)
    total_msgs = int(row.get("total_msgs") or 0)
    img_msgs = int(row.get("img_msgs") or 0)
    total_posts = isolated_posts + thread_posts
    if total_posts < 15 or total_msgs == 0:
        return None
    return {
        "total_posts": total_posts,
        "thread_posts": thread_posts,
        "isolated_posts": isolated_posts,
        "thread_post_ratio": thread_posts / total_posts,
        "total_msgs": total_msgs,
        "img_msgs": img_msgs,
        "image_ratio": img_msgs / total_msgs,
        "source": "originaux",
    }


def _create_run(**fields) -> int:
    cols = list(fields.keys())
    placeholders = ",".join(f"%({c})s" for c in cols)
    col_names = ",".join(cols)
    sql = f"INSERT INTO mkt_csv_runs ({col_names}, status, started_at) VALUES ({placeholders}, 'running', NOW()) RETURNING id"
    with db.cursor() as cur:
        cur.execute(sql, fields)
        return cur.fetchone()["id"]


def _update_run(run_id: int, **fields) -> None:
    if not fields:
        return
    set_clauses = ", ".join(f"{k} = %({k})s" for k in fields)
    fields["id"] = run_id
    with db.cursor() as cur:
        cur.execute(f"UPDATE mkt_csv_runs SET {set_clauses} WHERE id = %(id)s", fields)


def _merge_usage(total: dict, partial: dict) -> None:
    for k in total:
        if k in partial and isinstance(partial[k], (int, float)):
            total[k] += partial[k]


def _count_threads(run_id: int) -> int:
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(DISTINCT thread_key) FROM mkt_tweets "
            "WHERE csv_run_id = %s AND thread_key IS NOT NULL",
            (run_id,),
        )
        return cur.fetchone()["count"]


def _count_run_tweets(run_id: int) -> int:
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM mkt_tweets WHERE csv_run_id = %s", (run_id,))
        return cur.fetchone()["n"]


def get_run(run_id: int) -> dict | None:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT r.*, p.first_name AS persona_first_name, p.bio_twitter AS persona_bio,
                   p.backstory AS persona_backstory, p.avatar_id_primary AS persona_avatar,
                   p.voice_signature AS persona_voice
            FROM mkt_csv_runs r
            LEFT JOIN mkt_personas_emerged p ON r.persona_id = p.id
            WHERE r.id = %s
            """,
            (run_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def list_runs(limit: int = 50) -> list[dict]:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT r.id, r.source_csv_name, r.status, r.current_stage,
                   r.source_tweets_count, r.output_tweets_count, r.threads_count,
                   r.started_at, r.completed_at, r.cost_usd, r.source_handle,
                   r.persona_id,
                   p.first_name AS persona_first_name, p.avatar_id_primary AS persona_avatar
            FROM mkt_csv_runs r
            LEFT JOIN mkt_personas_emerged p ON r.persona_id = p.id
            ORDER BY r.started_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def delete_run(run_id: int, also_delete_orphan_persona: bool = False) -> dict:
    """Supprime un run et tous ses tweets. Optionnellement supprime aussi la persona
    si elle devient orpheline (plus aucun run ne la référence).

    Refuse de supprimer un run en status='running' pour ne pas tuer un thread actif.

    Retourne un dict de stats : {run_deleted, tweets_deleted, persona_deleted, persona_first_name}.
    """
    run = get_run(run_id)
    if not run:
        raise ValueError(f"Run #{run_id} introuvable.")
    if run.get("status") == "running":
        raise ValueError(f"Run #{run_id} encore en cours · attends la fin avant de supprimer.")

    persona_id = run.get("persona_id")
    persona_first_name = run.get("persona_first_name")

    with db.cursor() as cur:
        # 1. Supprimer les tweets du run
        cur.execute("DELETE FROM mkt_tweets WHERE csv_run_id = %s", (run_id,))
        tweets_deleted = cur.rowcount

        # 2. Casser les liens parent_run_id depuis d'éventuels enfants (pas de FK, pas de cascade)
        cur.execute(
            "UPDATE mkt_csv_runs SET parent_run_id = NULL WHERE parent_run_id = %s",
            (run_id,),
        )

        # 3. Supprimer le run lui-même
        cur.execute("DELETE FROM mkt_csv_runs WHERE id = %s", (run_id,))
        run_deleted = cur.rowcount

        # 4. Si demandé : supprimer la persona si plus aucun run ne la référence
        persona_deleted = False
        if also_delete_orphan_persona and persona_id:
            cur.execute(
                "SELECT COUNT(*) AS n FROM mkt_csv_runs WHERE persona_id = %s",
                (persona_id,),
            )
            remaining = cur.fetchone()["n"]
            if remaining == 0:
                cur.execute("DELETE FROM mkt_personas_emerged WHERE id = %s", (persona_id,))
                persona_deleted = cur.rowcount > 0

    # Cleanup run_state mémoire (best-effort)
    try:
        run_state.cleanup(run_id)
    except Exception:
        pass

    return {
        "run_deleted": bool(run_deleted),
        "tweets_deleted": tweets_deleted,
        "persona_deleted": persona_deleted,
        "persona_first_name": persona_first_name,
        "persona_id": persona_id,
    }


def list_personas(limit: int = 100) -> list[dict]:
    """Liste les personas avec quelques agrégats : nb de runs, nb de tweets, dernier run.

    Calcule runs et tweets en sous-requetes pour eviter le produit cartesien
    classique (deux LEFT JOIN + GROUP BY multipliait SUM(cost_usd) par le nombre
    de tweets de la persona, d'ou des couts UI delirants comme $2000).
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT p.*,
                   COALESCE(rs.runs_count, 0)        AS runs_count,
                   COALESCE(rs.total_cost_usd, 0)    AS total_cost_usd,
                   rs.last_run_at,
                   rs.first_run_at,
                   COALESCE(ts.tweets_count, 0)      AS tweets_count
            FROM mkt_personas_emerged p
            LEFT JOIN (
                SELECT persona_id,
                       COUNT(*)        AS runs_count,
                       SUM(cost_usd)   AS total_cost_usd,
                       MAX(started_at) AS last_run_at,
                       MIN(started_at) AS first_run_at
                FROM mkt_csv_runs
                GROUP BY persona_id
            ) rs ON rs.persona_id = p.id
            LEFT JOIN (
                SELECT persona_id, COUNT(*) AS tweets_count
                FROM mkt_tweets
                GROUP BY persona_id
            ) ts ON ts.persona_id = p.id
            ORDER BY rs.last_run_at DESC NULLS LAST, p.id DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_persona(persona_id: int) -> dict | None:
    """Charge une persona avec agrégats. Retourne None si introuvable.

    Meme strategie que list_personas : sous-requetes pour eviter le produit
    cartesien qui faisait exploser total_cost_usd.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT p.*,
                   COALESCE(rs.runs_count, 0)        AS runs_count,
                   COALESCE(rs.total_cost_usd, 0)    AS total_cost_usd,
                   rs.last_run_at,
                   rs.first_run_at,
                   COALESCE(ts.tweets_count, 0)      AS tweets_count
            FROM mkt_personas_emerged p
            LEFT JOIN (
                SELECT persona_id,
                       COUNT(*)        AS runs_count,
                       SUM(cost_usd)   AS total_cost_usd,
                       MAX(started_at) AS last_run_at,
                       MIN(started_at) AS first_run_at
                FROM mkt_csv_runs
                WHERE persona_id = %s
                GROUP BY persona_id
            ) rs ON rs.persona_id = p.id
            LEFT JOIN (
                SELECT persona_id, COUNT(*) AS tweets_count
                FROM mkt_tweets
                WHERE persona_id = %s
                GROUP BY persona_id
            ) ts ON ts.persona_id = p.id
            WHERE p.id = %s
            """,
            (persona_id, persona_id, persona_id),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_runs_for_persona(persona_id: int) -> list[dict]:
    """Tous les runs d'une persona, du plus récent au plus ancien."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, source_csv_name, source_handle, status, current_stage,
                   source_tweets_count, output_tweets_count, threads_count,
                   started_at, completed_at, cost_usd, archived_csv_path,
                   max_source_tweets, parent_run_id
            FROM mkt_csv_runs
            WHERE persona_id = %s
            ORDER BY started_at DESC NULLS LAST, id DESC
            """,
            (persona_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def get_root_run_for_persona(persona_id: int) -> dict | None:
    """Retourne le run "racine" d'une persona : le premier run qui a un CSV archivé.

    Un run d'extension n'a pas de CSV ; on cherche donc le run le plus ancien qui
    a un archived_csv_path. C'est le CSV source à partir duquel la persona a émergé.
    """
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM mkt_csv_runs
            WHERE persona_id = %s AND archived_csv_path IS NOT NULL
            ORDER BY started_at ASC NULLS LAST, id ASC
            LIMIT 1
            """,
            (persona_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def get_tweets_for_persona(persona_id: int) -> list[dict]:
    """Tous les tweets d'une persona, tous runs confondus. Ordonnés pour publication :
    par run, puis originaux d'abord (extension_idx NULL), puis extensions chronologiques."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM mkt_tweets
            WHERE persona_id = %s
            ORDER BY csv_run_id NULLS LAST,
                     extension_idx NULLS FIRST,
                     COALESCE(thread_key, ''),
                     COALESCE(thread_order, 0),
                     id
            """,
            (persona_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def delete_persona(persona_id: int) -> dict:
    """Cascade : supprime tous les tweets et runs de cette persona, puis la persona elle-même.

    Refuse si un run de la persona est encore en cours.
    """
    persona = get_persona(persona_id)
    if not persona:
        raise ValueError(f"Persona #{persona_id} introuvable.")

    with db.cursor() as cur:
        cur.execute(
            "SELECT id FROM mkt_csv_runs WHERE persona_id = %s AND status = 'running'",
            (persona_id,),
        )
        running = [r["id"] for r in cur.fetchall()]
    if running:
        raise ValueError(
            f"Persona #{persona_id} a des runs en cours ({', '.join(str(r) for r in running)}). "
            "Attends leur fin avant de supprimer."
        )

    runs = get_runs_for_persona(persona_id)
    tweets_deleted_total = 0
    runs_deleted_total = 0

    with db.cursor() as cur:
        # Supprimer tous les tweets de cette persona (couvre tous les runs y compris orphelins)
        cur.execute("DELETE FROM mkt_tweets WHERE persona_id = %s", (persona_id,))
        tweets_deleted_total = cur.rowcount

        # Casser les liens parent_run_id depuis d'éventuels enfants externes
        for r in runs:
            cur.execute(
                "UPDATE mkt_csv_runs SET parent_run_id = NULL WHERE parent_run_id = %s",
                (r["id"],),
            )

        # Supprimer tous les runs de la persona
        cur.execute("DELETE FROM mkt_csv_runs WHERE persona_id = %s", (persona_id,))
        runs_deleted_total = cur.rowcount

        # Supprimer la persona elle-même
        cur.execute("DELETE FROM mkt_personas_emerged WHERE id = %s", (persona_id,))

    # Cleanup mémoire run_state best-effort
    for r in runs:
        try:
            run_state.cleanup(r["id"])
        except Exception:
            pass

    return {
        "persona_first_name": persona.get("first_name"),
        "tweets_deleted": tweets_deleted_total,
        "runs_deleted": runs_deleted_total,
    }


def get_tweets_for_run(run_id: int) -> list[dict]:
    """Tous les tweets d'un run, ordonnés pour la publication Cortex :

    1. Tweets originaux (extension_idx IS NULL) en premier
    2. Puis extension #1, puis extension #2, etc.
    3. À l'intérieur de chaque bucket : par thread_key, thread_order, id

    Le CSV Cortex hérite naturellement de cet ordre. extension_idx n'est PAS
    exporté dans le CSV (champ interne) ; pour Cortex c'est juste une suite
    continue de tweets.
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT * FROM mkt_tweets WHERE csv_run_id = %s "
            "ORDER BY extension_idx NULLS FIRST, "
            "COALESCE(thread_key, ''), COALESCE(thread_order, 0), id",
            (run_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def update_tweet(tweet_id: int, **fields) -> None:
    if not fields:
        return
    set_clauses = ", ".join(f"{k} = %({k})s" for k in fields)
    fields["id"] = tweet_id
    # Recompute char_count si content changé
    if "content" in fields:
        fields["char_count"] = len(fields["content"])
        set_clauses += ", char_count = %(char_count)s"
    with db.cursor() as cur:
        cur.execute(f"UPDATE mkt_tweets SET {set_clauses} WHERE id = %(id)s", fields)


def delete_tweet(tweet_id: int) -> None:
    with db.cursor() as cur:
        cur.execute("DELETE FROM mkt_tweets WHERE id = %s", (tweet_id,))
