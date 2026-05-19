"""État partagé in-memory des batches d'indexation d'images en cours.

Même esprit que run_state : le batch tourne dans un thread daemon, la page UI poll
cet état pour afficher l'avancement en temps réel. Pas de persistance DB du batch
lui-même (les images annotées sont en DB via mkt_images, le batch est juste un
groupage transitoire pour l'UI).
"""
from __future__ import annotations
import itertools
import threading
import time
from collections import deque
from typing import Any


_lock = threading.Lock()
_state: dict[int, dict[str, Any]] = {}
_id_counter = itertools.count(1)

MAX_BATCHES_IN_MEMORY = 20
RECENT_IMAGES_KEEP = 24


def new_id() -> int:
    return next(_id_counter)


def _evict_old_locked() -> None:
    if len(_state) <= MAX_BATCHES_IN_MEMORY:
        return
    finished = [(bid, s) for bid, s in _state.items() if s.get("status") != "running"]
    finished.sort(key=lambda kv: kv[1].get("ended_at") or kv[1].get("started_at") or 0)
    to_remove = len(_state) - MAX_BATCHES_IN_MEMORY
    for bid, _ in finished[:to_remove]:
        _state.pop(bid, None)


def init(batch_id: int, total: int, model: str) -> None:
    now = time.time()
    with _lock:
        _evict_old_locked()
        _state[batch_id] = {
            "batch_id": batch_id,
            "status": "running",
            "model": model,
            "total": total,
            "processed": 0,
            "ok_count": 0,
            "error_count": 0,
            "by_fit": {"high": 0, "medium": 0, "low": 0, "off_brand": 0},
            "current_filename": None,
            "started_at": now,
            "ended_at": None,
            "error": None,
            "usage": {
                "input_tokens": 0,
                "cached_tokens": 0,
                "cache_creation_tokens": 0,
                "output_tokens": 0,
                "cost_usd_estimate": 0.0,
            },
            "recent": deque(maxlen=RECENT_IMAGES_KEEP),
            "log_tail": deque(maxlen=80),
        }


def mark_current(batch_id: int, filename: str) -> None:
    """Annonce le démarrage de l'image en cours (avant l'appel API)."""
    now = time.time()
    with _lock:
        s = _state.get(batch_id)
        if not s:
            return
        s["current_filename"] = filename
        s["log_tail"].append({
            "ts": now,
            "stage": "call",
            "text": f"Annotation en cours · {filename}",
        })


def record_result(batch_id: int, filename: str, result: dict[str, Any]) -> None:
    """Enregistre le résultat d'une image (ok ou erreur) et met à jour les stats."""
    now = time.time()
    with _lock:
        s = _state.get(batch_id)
        if not s:
            return
        s["processed"] += 1

        if result.get("ok"):
            s["ok_count"] += 1
            meta = result.get("metadata") or {}
            fit = meta.get("compaatible_fit")
            if fit in s["by_fit"]:
                s["by_fit"][fit] += 1
            usage = result.get("usage") or {}
            for k in s["usage"]:
                if k in usage:
                    s["usage"][k] += usage[k]
            s["recent"].appendleft({
                "filename": filename,
                "ok": True,
                "fit": fit,
                "image_type": meta.get("image_type"),
                "subject_type": meta.get("subject_type"),
                "ts": now,
            })
            s["log_tail"].append({
                "ts": now,
                "stage": "ok",
                "text": f"{filename} · fit={fit or '?'} · {meta.get('image_type') or '?'}",
            })
        else:
            s["error_count"] += 1
            err = result.get("error") or "erreur inconnue"
            s["recent"].appendleft({
                "filename": filename,
                "ok": False,
                "error": err,
                "ts": now,
            })
            s["log_tail"].append({
                "ts": now,
                "stage": "err",
                "text": f"{filename} · ECHEC · {err[:120]}",
            })


def finalize(batch_id: int, success: bool, error: str | None = None) -> None:
    now = time.time()
    with _lock:
        s = _state.get(batch_id)
        if not s:
            return
        s["status"] = "completed" if success else "failed"
        s["ended_at"] = now
        s["error"] = error
        s["current_filename"] = None
        s["log_tail"].append({
            "ts": now,
            "stage": "done" if success else "fail",
            "text": (
                f"Batch terminé · {s['ok_count']}/{s['total']} OK"
                if success
                else f"Batch interrompu · {error}"
            ),
        })


def get(batch_id: int) -> dict[str, Any] | None:
    with _lock:
        s = _state.get(batch_id)
        if s is None:
            return None
        now = time.time()
        return {
            "batch_id": s["batch_id"],
            "status": s["status"],
            "model": s["model"],
            "total": s["total"],
            "processed": s["processed"],
            "ok_count": s["ok_count"],
            "error_count": s["error_count"],
            "by_fit": dict(s["by_fit"]),
            "current_filename": s["current_filename"],
            "started_at": s["started_at"],
            "ended_at": s["ended_at"],
            "elapsed_s": round((s["ended_at"] or now) - s["started_at"], 1),
            "error": s["error"],
            "usage": dict(s["usage"]),
            "recent": list(s["recent"]),
            "log_tail": list(s["log_tail"])[-40:],
        }


def list_active() -> list[int]:
    """Retourne les batch_ids encore running (utile au cas où on veut un index)."""
    with _lock:
        return [bid for bid, s in _state.items() if s.get("status") == "running"]
