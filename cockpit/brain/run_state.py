"""État partagé in-memory des pipelines en cours.

Le pipeline tourne dans un thread daemon. La page UI poll cet état via JSON pour
afficher l'avancement en temps réel. La DB reste source de vérité pour le résultat
final (status, persona, tweets), mais ce module porte le détail vivant (étape
actuelle, message courant, durées, log tail).

Pas de persistance : si Flask redémarre, l'état est perdu pour les runs en cours.
Acceptable : on tourne en local, et la DB garde status='failed' si on crash.
"""
from __future__ import annotations
import threading
import time
from collections import deque
from typing import Any


# Définition des étapes du pipeline, dans l'ordre. UI s'appuie dessus pour le rendu.
STAGES: list[dict[str, str]] = [
    {
        "key": "parse",
        "label": "Lecture CSV",
        "desc": "Parser le fichier, détecter la langue et le handle source.",
    },
    {
        "key": "analyze",
        "label": "Reverse-engineering",
        "desc": "L'IA identifie les mécanismes qui font marcher le compte source.",
    },
    {
        "key": "persona",
        "label": "Persona émergente",
        "desc": "L'IA lit les tweets sources et fait émerger une femme cohérente.",
    },
    {
        "key": "copy",
        "label": "Copywriting",
        "desc": "L'IA réécrit les tweets dans la voix de la persona Compaatible.",
    },
    {
        "key": "done",
        "label": "Validation Cortex",
        "desc": "Tweets stockés et validés au format prêt pour Cortex.",
    },
]


_lock = threading.Lock()
_state: dict[int, dict[str, Any]] = {}

# Plafond mémoire : on ne garde que les N runs les plus récents. Au-delà, on
# évince les plus anciens TERMINÉS (jamais un run encore en running, sinon le
# polling UI perdrait son état).
MAX_RUNS_IN_MEMORY = 50


def _evict_old_runs_locked() -> None:
    """À appeler avec _lock détenu. Supprime les runs terminés les plus anciens
    si on dépasse MAX_RUNS_IN_MEMORY."""
    if len(_state) <= MAX_RUNS_IN_MEMORY:
        return
    finished = [(rid, s) for rid, s in _state.items() if s.get("status") != "running"]
    finished.sort(key=lambda kv: kv[1].get("ended_at") or kv[1].get("started_at") or 0)
    to_remove = len(_state) - MAX_RUNS_IN_MEMORY
    for rid, _ in finished[:to_remove]:
        _state.pop(rid, None)


def init(run_id: int) -> None:
    """Enregistre un nouveau run avec toutes les étapes en pending."""
    now = time.time()
    with _lock:
        _evict_old_runs_locked()
        _state[run_id] = {
            "run_id": run_id,
            "status": "running",          # running | completed | failed | paused
            "current": "parse",
            "started_at": now,
            "ended_at": None,
            "error": None,
            "pause_requested": False,
            "stages": {
                s["key"]: {
                    "status": "pending",  # pending | running | done | failed
                    "started_at": None,
                    "ended_at": None,
                    "message": "",
                }
                for s in STAGES
            },
            "log_tail": deque(maxlen=80),
        }


def request_pause(run_id: int) -> bool:
    """Pose un flag de pause sur le run. Le copywriter vérifie ce flag entre
    chaque chunk et sort proprement si demandé. Retourne True si le flag a été
    posé, False si le run est introuvable ou déjà terminé."""
    with _lock:
        s = _state.get(run_id)
        if not s:
            return False
        if s.get("status") != "running":
            return False
        s["pause_requested"] = True
        s["log_tail"].append({
            "ts": time.time(),
            "stage": s.get("current") or "?",
            "text": "Pause demandée · sortie au prochain chunk",
        })
        return True


def is_pause_requested(run_id: int) -> bool:
    """Lu par le copywriter entre chaque chunk."""
    with _lock:
        s = _state.get(run_id)
        return bool(s and s.get("pause_requested"))


def mark_paused(run_id: int, message: str = "") -> None:
    """Marque le run comme paused (l'étape courante reste où elle est, pas un échec)."""
    now = time.time()
    with _lock:
        s = _state.get(run_id)
        if not s:
            return
        cur_key = s.get("current")
        cur = s["stages"].get(cur_key) if cur_key else None
        if cur and cur["status"] == "running":
            cur["status"] = "pending"  # repassée en pending pour signaler "à reprendre"
            cur["message"] = message or "En pause"
        s["status"] = "paused"
        s["ended_at"] = now
        s["pause_requested"] = False
        s["log_tail"].append({
            "ts": now,
            "stage": cur_key or "?",
            "text": message or "Run mis en pause.",
        })


def clear_pause_for_resume(run_id: int) -> None:
    """Réveille un run paused en mémoire pour la reprise : status=running, ended_at=None,
    pause_requested=False. Si le run n'est pas en mémoire (Flask restart), no-op et le
    caller appellera init() à la place."""
    with _lock:
        s = _state.get(run_id)
        if not s:
            return
        s["status"] = "running"
        s["ended_at"] = None
        s["pause_requested"] = False
        s["log_tail"].append({
            "ts": time.time(),
            "stage": s.get("current") or "?",
            "text": "Reprise après pause.",
        })


def begin_stage(run_id: int, key: str, message: str = "") -> None:
    """Marque l'étape précédente comme done et démarre celle-ci."""
    now = time.time()
    with _lock:
        s = _state.get(run_id)
        if not s:
            return
        # Précédente : si elle était running, on la passe done
        prev_key = s.get("current")
        if prev_key and prev_key != key:
            prev = s["stages"].get(prev_key)
            if prev and prev["status"] == "running":
                prev["status"] = "done"
                prev["ended_at"] = now
        cur = s["stages"].get(key)
        if cur:
            cur["status"] = "running"
            cur["started_at"] = now
            cur["message"] = message
        s["current"] = key
        if message:
            s["log_tail"].append({"ts": now, "stage": key, "text": message})


def skip_stage(run_id: int, key: str, message: str = "") -> None:
    """Marque une étape comme done sans l'avoir exécutée (réutilisation depuis un run parent)."""
    now = time.time()
    with _lock:
        s = _state.get(run_id)
        if not s:
            return
        cur = s["stages"].get(key)
        if cur:
            cur["status"] = "done"
            cur["started_at"] = now
            cur["ended_at"] = now
            cur["message"] = message or "Réutilisé du run parent."
        s["current"] = key
        s["log_tail"].append({"ts": now, "stage": key, "text": message or "Réutilisé du run parent."})


def update_message(run_id: int, message: str, stage_key: str | None = None) -> None:
    """Met à jour le message courant de l'étape active (ou d'une étape précise)."""
    now = time.time()
    with _lock:
        s = _state.get(run_id)
        if not s:
            return
        target_key = stage_key or s.get("current")
        cur = s["stages"].get(target_key) if target_key else None
        if cur:
            cur["message"] = message
        s["log_tail"].append({"ts": now, "stage": target_key or "?", "text": message})


def finalize(run_id: int, success: bool, error: str | None = None) -> None:
    """Termine le run. Si success, marque l'étape current et 'done' comme done."""
    now = time.time()
    with _lock:
        s = _state.get(run_id)
        if not s:
            return
        cur_key = s.get("current")
        cur = s["stages"].get(cur_key) if cur_key else None
        if cur and cur["status"] == "running":
            cur["status"] = "done" if success else "failed"
            cur["ended_at"] = now
        if success:
            done_stage = s["stages"].get("done")
            if done_stage:
                done_stage["status"] = "done"
                done_stage["started_at"] = now
                done_stage["ended_at"] = now
                s["current"] = "done"
        s["status"] = "completed" if success else "failed"
        s["error"] = error
        s["ended_at"] = now
        s["log_tail"].append({
            "ts": now,
            "stage": s["current"],
            "text": "Pipeline terminé." if success else f"Pipeline en échec : {error}",
        })


def get(run_id: int) -> dict[str, Any] | None:
    """Retourne une copie sérialisable de l'état d'un run (ou None s'il n'existe pas)."""
    with _lock:
        s = _state.get(run_id)
        if s is None:
            return None
        now = time.time()
        stages_copy: dict[str, dict[str, Any]] = {}
        for k, v in s["stages"].items():
            sc = {**v}
            if sc["started_at"] and sc["ended_at"]:
                sc["duration_s"] = round(sc["ended_at"] - sc["started_at"], 1)
            elif sc["started_at"]:
                sc["duration_s"] = round(now - sc["started_at"], 1)
            else:
                sc["duration_s"] = None
            stages_copy[k] = sc
        return {
            "run_id": s["run_id"],
            "status": s["status"],
            "current": s["current"],
            "started_at": s["started_at"],
            "ended_at": s["ended_at"],
            "elapsed_s": round((s["ended_at"] or now) - s["started_at"], 1),
            "error": s["error"],
            "pause_requested": bool(s.get("pause_requested")),
            "stages": stages_copy,
            "stages_def": STAGES,
            "log_tail": list(s["log_tail"])[-30:],
        }


def cleanup(run_id: int) -> None:
    """Supprime un run de la mémoire (à appeler quand on n'a plus besoin de poller)."""
    with _lock:
        _state.pop(run_id, None)


def list_active() -> list[int]:
    """Retourne les run_ids des pipelines encore en cours.

    Utilisé par la sidebar UI pour afficher un indicateur "X runs actifs" et
    permettre à l'utilisateur de naviguer sans perdre la trace.
    """
    with _lock:
        return [rid for rid, s in _state.items() if s.get("status") == "running"]
