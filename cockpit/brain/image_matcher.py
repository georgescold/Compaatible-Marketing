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


# Plancher de pertinence semantique : une image n'est acceptee que si son score
# de RELEVANCE (recouvrement reel entre le brief du tweet et la description/tags
# de l'image) atteint ce seuil. Les bonus avatar/qualite/fit ne comptent PAS dans
# la relevance — ils ne peuvent donc plus, a eux seuls, faire passer une image
# hors-sujet (bug observe : avatar +2 + qualite +2 + fit +0.3 = 4.3 sans aucun mot
# du brief en commun). REL_FLOOR ~ 1 hit description (2.0) ou 1 emotion (2.5).
REL_FLOOR = 3.0

# Penalite appliquee au score total par utilisation globale anterieure de l'image
# (tous runs confondus). Etale les choix sur le pool au lieu de reprendre toujours
# les memes images les mieux notees. ~0.6/usage : 5 usages = -3.0, de quoi laisser
# passer devant une image equivalente jamais utilisee.
USAGE_PENALTY = 0.6

# Largeur de la bande "quasi-egalite" sous le meilleur score total : parmi les
# candidats dans cette bande, on prefere l'image la moins utilisee globalement
# (puis id stable). Apporte de la variete sans sacrifier la pertinence.
TIE_BAND = 1.0


def score_candidate(
    brief_tokens: set[str],
    avatar_primary: int | None,
    image: dict[str, Any],
) -> tuple[float, float]:
    """Score une image candidate pour un tweet donne.

    Retourne **(relevance, total)** :
    - `relevance` = match SEMANTIQUE pur (brief vs description + tags emotions/
      ambiance/setting/style). C'est lui qui doit franchir REL_FLOOR pour qu'une
      image soit eligible — garantit un vrai lien avec le tweet.
    - `total` = relevance + bonus (avatar, qualite, fit). Sert au classement une
      fois le plancher de pertinence franchi.

    Le compaatible_fit ne sert que de filtre d'eligibilite (high/medium ok,
    low/off_brand exclus) + un nudge de 0.3 en tiebreaker. Retourne (-1.0, -1.0)
    si l'image est ineligible.

    NB : la dedup run-global (une image = un seul tweet par run) et la penalite
    d'usage inter-runs sont gerees en amont dans match_images_for_run.
    """
    fit = image.get("compaatible_fit")
    if fit not in ("high", "medium"):
        return -1.0, -1.0

    # ── Relevance (semantique pure) ──
    relevance = 0.0
    # Match description : signal PRINCIPAL. Chaque mot du brief retrouve dans la
    # description vaut +2.0. Cap a 8 pour qu'une description longue ne gonfle pas.
    desc_norm = _normalize(image.get("description") or "")
    desc_hits = sum(1 for t in brief_tokens if t in desc_norm)
    relevance += min(desc_hits, 8) * 2.0

    # Tag overlap : signaux secondaires forts (emotions > ambiance > setting > style)
    emo_tokens = _array_tokens(image.get("emotions"))
    amb_tokens = _array_tokens(image.get("ambiance"))
    set_tokens = _array_tokens(image.get("setting"))
    style_tokens = _array_tokens(image.get("style_tags"))

    relevance += len(brief_tokens & emo_tokens) * 2.5
    relevance += len(brief_tokens & amb_tokens) * 2.0
    relevance += len(brief_tokens & set_tokens) * 1.5
    relevance += len(brief_tokens & style_tokens) * 1.0

    # ── Bonus (ne comptent PAS dans la relevance) ──
    bonus = 0.0
    # Avatar match (si la persona a un avatar primaire) : signal stable
    suggested = image.get("suggested_avatars") or []
    if avatar_primary is not None and avatar_primary in suggested:
        bonus += 2.0
    # Bonus qualite (quality_score 1-10, baseline 5)
    q = image.get("quality_score") or 5
    bonus += (q - 5) * 0.4
    # Tres leger nudge en faveur de HIGH a egalite (tiebreaker uniquement)
    if fit == "high":
        bonus += 0.3

    return relevance, relevance + bonus


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


def _load_global_usage() -> dict[int, int]:
    """Compte, pour chaque image, le nombre de tweets (tous runs confondus) qui
    l'utilisent deja. Sert a la penalite d'usage : on etale les choix sur le pool
    au lieu de reprendre toujours les memes images les mieux notees.

    Calcule a la volee (pas de colonne de compteur) → reste exact apres
    suppressions/detachements d'images.
    """
    with db.cursor() as cur:
        cur.execute(
            "SELECT image_id, COUNT(*) AS n FROM mkt_tweets "
            "WHERE image_id IS NOT NULL GROUP BY image_id"
        )
        return {r["image_id"]: int(r["n"]) for r in cur.fetchall()}


def match_images_for_run(
    run_id: int,
    ai_assist: bool = False,
    model: str | None = None,
) -> dict[str, Any]:
    """Matche tous les tweets en attente d'un run avec les meilleures images.

    Algorithme (toujours actif) :
    1. **Plancher de pertinence** : seules les images dont le score de RELEVANCE
       (recouvrement brief↔description/tags) atteint REL_FLOOR sont eligibles.
       Tue les images hors-sujet qui ne tenaient que sur avatar/qualite/fit.
    2. **Variete inter-runs** : penalite d'usage (USAGE_PENALTY × nb d'utilisations
       globales) sur le score total + preference, a quasi-egalite (TIE_BAND), pour
       l'image la moins utilisee. Etale les choix au lieu de reprendre les memes.
    3. **Dedup intra-run** : une image = un seul tweet par run (inchange).

    ai_assist : si True, l'algo pre-selectionne un top-N par tweet et un modele
    (`model`) tranche via `_llm_rerank`. Sinon, choix 100% algorithmique (defaut).

    Retourne un dict de stats (matched, no_candidate, no_brief, pool_size, ...).
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

    # Usage global (tous runs) pour la penalite de variete. On le mute localement
    # au fil des picks de ce run pour que les tweets suivants voient l'usage a jour.
    usage_counts = _load_global_usage()

    matched = 0
    no_candidate = 0
    no_brief = 0
    floor_rejects = 0  # images recalees par le plancher de pertinence (audit)
    ai_used = 0

    for idx, tw in enumerate(pending, start=1):
        brief = (tw.get("image_brief") or "").strip()
        if not brief:
            no_brief += 1
            _update_progress(run_id, processed=idx, no_brief=no_brief,
                             last_action=f"tweet #{tw['id']} : pas de brief image, skip")
            continue

        brief_tokens = _tokenize(brief)
        avatar_primary = tw.get("avatar_id_primary")

        # Score chaque image candidate (hors images deja prises dans ce run).
        # On retient (relevance, adjusted_total, usage, img). adjusted_total =
        # total - penalite d'usage. Le plancher REL_FLOOR filtre sur la relevance
        # pure (semantique), pas sur le total gonfle par les bonus.
        scored = []
        for img in pool:
            if img.get("id") in used_image_ids:
                continue
            relevance, total = score_candidate(brief_tokens, avatar_primary, img)
            if relevance < REL_FLOOR:
                if relevance > 0:
                    floor_rejects += 1
                continue
            usage = usage_counts.get(img.get("id"), 0)
            adjusted = total - usage * USAGE_PENALTY
            scored.append((relevance, adjusted, usage, img))

        if not scored:
            no_candidate += 1
            _update_progress(run_id, processed=idx, no_candidate=no_candidate,
                             last_action=f"tweet #{tw['id']} : aucune image semantiquement pertinente (plancher {REL_FLOOR})")
            continue

        # Classement par score ajuste (penalite d'usage incluse), desc.
        scored.sort(key=lambda x: x[1], reverse=True)
        best_adjusted = scored[0][1]

        # Variete : parmi les candidats dans la bande quasi-egalite sous le
        # meilleur, prefere l'image la MOINS utilisee globalement (puis id stable).
        band = [c for c in scored if best_adjusted - c[1] <= TIE_BAND]
        band.sort(key=lambda x: (x[2], x[3].get("id") or 0))  # (usage asc, id asc)
        chosen = band[0]

        # Re-rank IA optionnel : l'algo propose un top-N, le modele tranche.
        if ai_assist and model:
            shortlist = [c[3] for c in scored[:5]]
            picked = _llm_rerank(tw, shortlist, model)
            if picked is not None:
                ai_used += 1
                chosen = next((c for c in scored if c[3].get("id") == picked), chosen)

        best_relevance, best_adj, best_usage, best_img = chosen

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
        usage_counts[best_img["id"]] = usage_counts.get(best_img["id"], 0) + 1
        matched += 1
        _update_progress(
            run_id,
            processed=idx,
            matched=matched,
            last_action=(
                f"tweet #{tw['id']} → image {best_img['filename']} "
                f"(rel {best_relevance:.1f} · usage anterieur {best_usage})"
            ),
        )

    _log_summary(run_id, matched, no_candidate, no_brief, floor_rejects, ai_used, ai_assist)

    result = {
        "matched": matched,
        "no_candidate": no_candidate,
        "no_brief": no_brief,
        "floor_rejects": floor_rejects,
        "ai_reranked": ai_used,
        "pool_size": len(pool),
        "pending_total": len(pending),
    }
    _finalize_progress(run_id, result=result)
    return result


def _log_summary(run_id: int, matched: int, no_candidate: int, no_brief: int,
                 floor_rejects: int, ai_used: int, ai_assist: bool) -> None:
    """Log de fin de matching pour audit (variete + pertinence)."""
    import sys
    parts = [
        f"[match] run #{run_id} · {matched} matched · {no_candidate} sans candidat",
        f"{no_brief} sans brief · {floor_rejects} recale(s) par plancher pertinence",
    ]
    if ai_assist:
        parts.append(f"{ai_used} tranche(s) par IA")
    print(" · ".join(parts), file=sys.stderr, flush=True)


def _llm_rerank(tweet: dict, shortlist: list[dict], model: str) -> int | None:
    """Demande a un modele de choisir la meilleure image parmi un shortlist pour
    un tweet donne. Retourne l'id image choisi, ou None (garder le choix algo).

    N'est appele que si ai_assist=True. Le modele recoit le contenu du tweet +
    son image_brief + la description/tags de chaque candidat, et renvoie l'id
    (ou 0 si aucune ne convient vraiment).
    """
    import json as _json
    import sys
    from brain import llm_client

    if not shortlist:
        return None

    candidates_txt = []
    for img in shortlist:
        candidates_txt.append(
            f"- id={img.get('id')} · fit={img.get('compaatible_fit')} · "
            f"description: {(img.get('description') or '').strip()[:300]} · "
            f"emotions: {', '.join(img.get('emotions') or [])} · "
            f"ambiance: {', '.join(img.get('ambiance') or [])} · "
            f"setting: {', '.join(img.get('setting') or [])}"
        )
    sys_block = (
        "Tu es un directeur artistique. On te donne un tweet (avec un brief image) "
        "et une liste d'images candidates deja pre-filtrees. Choisis l'UNE qui "
        "illustre le mieux le tweet — celle dont la scene, l'emotion et l'ambiance "
        "collent vraiment au contenu. Si AUCUNE ne convient honnetement, renvoie 0. "
        'Reponds UNIQUEMENT en JSON strict : {"image_id": <id ou 0>, "why": "<1 phrase>"}.'
    )
    user_txt = (
        f"## Tweet\n{(tweet.get('content') or '').strip()}\n\n"
        f"## Brief image\n{(tweet.get('image_brief') or '').strip()}\n\n"
        f"## Images candidates\n" + "\n".join(candidates_txt)
    )
    try:
        result = llm_client.call_messages(
            model=model,
            system_blocks=[{"type": "text", "text": sys_block}],
            messages=[{"role": "user", "content": user_txt}],
            max_tokens=256,
            temperature=0.2,
        )
        from brain.source_analyzer import parse_json_response
        parsed = parse_json_response(result["text"])
        picked = int(parsed.get("image_id") or 0)
        valid_ids = {img.get("id") for img in shortlist}
        if picked in valid_ids:
            return picked
        return None  # 0 ou id hors-shortlist → on garde le choix algo
    except Exception as e:
        print(f"[match] _llm_rerank ECHEC ({type(e).__name__}: {e}) · fallback algo", file=sys.stderr, flush=True)
        return None


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
