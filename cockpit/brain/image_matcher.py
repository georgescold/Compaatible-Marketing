"""Stage 3 : matching tweet -> image en batch.

Loys clique le bouton "Integrer les images" sur un run. Pour chaque tweet du run
ou needs_image=TRUE ET image_id IS NULL, on trouve la meilleure image dans
mkt_images (filtree par fit Compaatible + public_url presente) et on remplit
image_id + image_chosen_at + media_url (URL publique pour Cortex).

Aucun appel API externe : pur scoring SQL/Python a partir des metadonnees deja
en DB. Le `image_brief` produit a l'etape 1 par le copywriter sert d'input ;
les tags structures (emotions, ambiance, setting, style_tags, suggested_avatars)
et le compaatible_fit servent de signal de matching.

INTERNE : les champs `needs_image`, `image_brief`, `image_id`, `image_chosen_at`
ne doivent JAMAIS apparaitre dans le CSV exporte vers Cortex (cf.
feedback_internal_fields_not_in_csv en memoire). Seul `media_url` part vers
Cortex avec l'URL publique HTTPS de l'image choisie.
"""
from __future__ import annotations
import re
import threading
import time
import unicodedata
from datetime import datetime
from typing import Any

from brain import db


# ─── Progression in-memory (un seul matching en cours par run) ────────────────
#
# Pourquoi pas run_state ? run_state est cablé pour les étapes du PIPELINE de
# génération. Le matching est une action ponctuelle post-pipeline, avec sa
# propre granularité (tweet par tweet). On garde un dict séparé pour ne pas
# polluer run_state ni casser le rendu de la page tweets_run_running.html.
_progress_lock = threading.Lock()
_progress: dict[int, dict[str, Any]] = {}


def _init_progress(run_id: int, total: int, pool_size: int) -> None:
    with _progress_lock:
        _progress[run_id] = {
            "run_id": run_id,
            "status": "running",          # running | completed | failed
            "started_at": time.time(),
            "ended_at": None,
            "total": total,
            "processed": 0,
            "matched": 0,
            "no_brief": 0,
            "no_candidate": 0,
            "pool_size": pool_size,
            "last_action": "",            # texte court : ce qui vient d'être fait
            "error": None,
            "result": None,               # dict final stats quand terminé
        }


def _update_progress(run_id: int, **fields: Any) -> None:
    with _progress_lock:
        s = _progress.get(run_id)
        if s is not None:
            s.update(fields)


def _finalize_progress(
    run_id: int,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    with _progress_lock:
        s = _progress.get(run_id)
        if s is None:
            # Cas rare : appel après cleanup. On recrée un snapshot minimal pour
            # que l'UI sache que c'est terminé.
            _progress[run_id] = {
                "run_id": run_id,
                "status": "failed" if error else "completed",
                "started_at": time.time(),
                "ended_at": time.time(),
                "total": 0,
                "processed": 0,
                "matched": 0,
                "no_brief": 0,
                "no_candidate": 0,
                "pool_size": 0,
                "last_action": "",
                "error": error,
                "result": result,
            }
            return
        s["status"] = "failed" if error else "completed"
        s["ended_at"] = time.time()
        s["error"] = error
        if result is not None:
            s["result"] = result


def get_progress(run_id: int) -> dict[str, Any] | None:
    """Retourne une COPIE du snapshot de progression, ou None si jamais lancé."""
    with _progress_lock:
        s = _progress.get(run_id)
        if s is None:
            return None
        snap = dict(s)
        now = time.time()
        snap["elapsed_s"] = round((s.get("ended_at") or now) - s["started_at"], 1)
        return snap


def cleanup_progress(run_id: int) -> None:
    """Permet à l'UI de relancer un matching propre après avoir consommé le résultat."""
    with _progress_lock:
        _progress.pop(run_id, None)


# Mots-outils a ignorer dans les briefs (FR + EN basique)
_STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "a", "au",
    "aux", "ce", "cet", "cette", "ces", "qui", "que", "quoi", "dont", "ou", "en", "dans",
    "sur", "sous", "avec", "sans", "pour", "par", "vers", "chez", "the", "a", "an", "of",
    "and", "or", "to", "for", "with", "without", "in", "on", "at", "by", "image", "visuel",
    "photo", "scene",
}


def _normalize(text: str) -> str:
    """Strip accents + lowercase pour matching robuste."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _tokenize(text: str) -> set[str]:
    """Tokens significatifs (>=3 chars, hors stopwords) d'un brief."""
    norm = _normalize(text)
    tokens = re.findall(r"[a-z]{3,}", norm)
    return {t for t in tokens if t not in _STOPWORDS}


def _array_tokens(values: list[str] | None) -> set[str]:
    """Convertit un ARRAY DB (emotions/ambiance/...) en set de tokens normalises."""
    if not values:
        return set()
    out = set()
    for v in values:
        if not v:
            continue
        norm = _normalize(v)
        # On garde les valeurs entieres (ex: 'golden_hour', 'south_asian') ET les sous-tokens
        out.add(norm)
        for t in re.findall(r"[a-z]{3,}", norm):
            if t not in _STOPWORDS:
                out.add(t)
    return out


def score_candidate(
    brief_tokens: set[str],
    avatar_primary: int | None,
    image: dict[str, Any],
    used_image_ids: set[int],
) -> float:
    """Score une image candidate pour un tweet donne.

    Le score domine sur le MATCH SEMANTIQUE entre le brief du tweet et la
    description + tags de l'image. Le compaatible_fit ne sert plus que de
    filtre d'eligibilite (high/medium ok, low/off_brand exclus) — il
    n'apporte plus de bonus de score : une image MEDIUM dont la description
    matche parfaitement bat une HIGH generique.
    """
    score = 0.0

    # Filtre d'eligibilite (pas de bonus). low/off_brand sont deja exclus en amont
    # par _load_candidate_pool, mais on garde le garde-fou ici.
    fit = image.get("compaatible_fit")
    if fit not in ("high", "medium"):
        return -1.0

    # Match description : signal PRINCIPAL. Chaque mot du brief retrouve
    # dans la description de l'image vaut +2.0. Cap a 8 pour eviter
    # qu'une description tres longue gonfle artificiellement le score.
    desc_norm = _normalize(image.get("description") or "")
    desc_hits = sum(1 for t in brief_tokens if t in desc_norm)
    score += min(desc_hits, 8) * 2.0

    # Tag overlap : signaux secondaires forts (emotions > ambiance > setting > style)
    emo_tokens = _array_tokens(image.get("emotions"))
    amb_tokens = _array_tokens(image.get("ambiance"))
    set_tokens = _array_tokens(image.get("setting"))
    style_tokens = _array_tokens(image.get("style_tags"))

    score += len(brief_tokens & emo_tokens) * 2.5
    score += len(brief_tokens & amb_tokens) * 2.0
    score += len(brief_tokens & set_tokens) * 1.5
    score += len(brief_tokens & style_tokens) * 1.0

    # Avatar match (si la persona a un avatar primaire) : signal stable
    suggested = image.get("suggested_avatars") or []
    if avatar_primary is not None and avatar_primary in suggested:
        score += 2.0

    # Bonus qualite (quality_score 1-10, baseline 5)
    q = image.get("quality_score") or 5
    score += (q - 5) * 0.4

    # Tres leger nudge en faveur de HIGH a egalite parfaite (tiebreaker uniquement)
    if fit == "high":
        score += 0.3

    # Penalite si deja utilisee dans ce run (eviter la repetition)
    if image.get("id") in used_image_ids:
        score -= 4.0

    return score


def _load_candidate_pool() -> list[dict[str, Any]]:
    """Charge toutes les images eligibles : fit high/medium ET public_url presente."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, filename, public_url, compaatible_fit,
                   description, emotions, ambiance, setting, style_tags,
                   suggested_avatars, quality_score, usage_warning
            FROM mkt_images
            WHERE compaatible_fit IN ('high', 'medium')
              AND public_url IS NOT NULL
            """
        )
        return [dict(r) for r in cur.fetchall()]


def _load_pending_tweets(run_id: int) -> list[dict[str, Any]]:
    """Tweets du run en attente de matching : needs_image=TRUE ET image_id IS NULL."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT t.id, t.content, t.image_brief, t.persona_id,
                   p.avatar_id_primary
            FROM mkt_tweets t
            LEFT JOIN mkt_personas_emerged p ON p.id = t.persona_id
            WHERE t.csv_run_id = %s
              AND t.needs_image = TRUE
              AND t.image_id IS NULL
            ORDER BY t.id
            """,
            (run_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def match_images_for_run(run_id: int) -> dict[str, Any]:
    """Matche tous les tweets en attente d'un run avec les meilleures images.

    Retourne un dict avec les stats :
      - matched   : nb tweets matches
      - no_candidate : nb tweets ou aucune image n'a passe le score min
      - no_brief  : nb tweets needs_image=true mais image_brief vide (skipped)
      - pool_size : nb images eligibles dans le pool
    """
    pool = _load_candidate_pool()
    pending = _load_pending_tweets(run_id)

    _init_progress(run_id, total=len(pending), pool_size=len(pool))

    if not pending:
        result = {"matched": 0, "no_candidate": 0, "no_brief": 0, "pool_size": len(pool)}
        _finalize_progress(run_id, result=result)
        return result

    if not pool:
        result = {
            "matched": 0, "no_candidate": len(pending), "no_brief": 0, "pool_size": 0,
            "warning": "Aucune image avec public_url. Upload tes images d'abord (Supabase Storage / CDN / Imgur)."
        }
        _update_progress(run_id, no_candidate=len(pending),
                         last_action="Aucune image avec public_url dans le pool.")
        _finalize_progress(run_id, result=result)
        return result

    used_image_ids: set[int] = set()
    # Pre-charger les images deja utilisees dans ce run (au cas ou on relance)
    with db.cursor() as cur:
        cur.execute(
            "SELECT image_id FROM mkt_tweets WHERE csv_run_id = %s AND image_id IS NOT NULL",
            (run_id,),
        )
        used_image_ids = {r["image_id"] for r in cur.fetchall() if r["image_id"]}

    matched = 0
    no_candidate = 0
    no_brief = 0

    for idx, tw in enumerate(pending, start=1):
        brief = (tw.get("image_brief") or "").strip()
        if not brief:
            no_brief += 1
            _update_progress(run_id, processed=idx, no_brief=no_brief,
                             last_action=f"tweet #{tw['id']} : pas de brief image, skip")
            continue

        brief_tokens = _tokenize(brief)
        avatar_primary = tw.get("avatar_id_primary")

        # Scorer toutes les candidates
        scored = []
        for img in pool:
            s = score_candidate(brief_tokens, avatar_primary, img, used_image_ids)
            if s > 0:
                scored.append((s, img))

        if not scored:
            no_candidate += 1
            _update_progress(run_id, processed=idx, no_candidate=no_candidate,
                             last_action=f"tweet #{tw['id']} : aucune image au-dessus du seuil")
            continue

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_img = scored[0]

        # Seuil minimum : on veut un vrai match semantique, pas juste un fit
        # acceptable sans aucun chevauchement avec le brief.
        if best_score < 4.0:
            no_candidate += 1
            _update_progress(run_id, processed=idx, no_candidate=no_candidate,
                             last_action=f"tweet #{tw['id']} : meilleur score {best_score:.1f} < 4.0")
            continue

        # Persister
        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE mkt_tweets
                   SET image_id = %s,
                       image_chosen_at = %s,
                       media_url = %s
                 WHERE id = %s
                """,
                (best_img["id"], datetime.utcnow(), best_img["public_url"], tw["id"]),
            )
        used_image_ids.add(best_img["id"])
        matched += 1
        _update_progress(
            run_id,
            processed=idx,
            matched=matched,
            last_action=f"tweet #{tw['id']} → image {best_img['filename']} (score {best_score:.1f})",
        )

    result = {
        "matched": matched,
        "no_candidate": no_candidate,
        "no_brief": no_brief,
        "pool_size": len(pool),
        "pending_total": len(pending),
    }
    _finalize_progress(run_id, result=result)
    return result


def stats_for_run(run_id: int) -> dict[str, Any]:
    """Stats pour l'UI : combien de tweets needs_image, combien deja matches."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE needs_image = TRUE) AS needs_image,
                COUNT(*) FILTER (WHERE needs_image = TRUE AND image_id IS NOT NULL) AS already_matched,
                COUNT(*) FILTER (WHERE needs_image = TRUE AND image_id IS NULL) AS pending
            FROM mkt_tweets
            WHERE csv_run_id = %s
            """,
            (run_id,),
        )
        row = dict(cur.fetchone())
    return row
