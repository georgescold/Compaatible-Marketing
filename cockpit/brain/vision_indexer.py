"""Pipeline d'indexation des images via l'API Anthropic Vision.

Pour chaque image du dossier `Images/`, génère les métadonnées marketing structurées
(description, émotions, ambiance, couleurs, fit Compaatible, avatars cibles) et insère/MAJ
dans la table `mkt_images`.
"""
from __future__ import annotations
import base64
import hashlib
import json
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Callable

from brain import llm_client, db, image_batch_state, prompts
from brain.source_analyzer import parse_json_response
from config import Config


SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


# Plafond par batch d'indexation, calibre sur les quotas RPD du provider.
# Anthropic tier standard et Gemini Pro sont contraints (Pro = 250 RPD).
# Flash Lite (150k RPD) et Flash (10k RPD) permettent de tres gros batchs.
_BATCH_CAPS_BY_MODEL: dict[str, int] = {
    # Gemini Flash Lite : 150 000 RPD, on laisse pratiquement libre.
    "gemini-3.1-flash-lite":  50000,
    # Gemini Flash full : 10 000 RPD, large mais pas illimite.
    "gemini-3-flash":          5000,
    # Gemini Pro / Pro Preview : 250 RPD, cap conservateur.
    "gemini-3.1-pro-preview":   200,
    "gemini-3.1-pro":           200,
    "gemini-3-pro":             200,
    # Anthropic : pas de RPD strict mais rate-limit par minute selon le tier.
    "claude-haiku-4-5-20251001": 500,
    "claude-sonnet-4-6":         500,
    "claude-opus-4-7":           300,
}
_BATCH_CAP_DEFAULT = 500


def max_batch_size_for_model(model: str | None) -> int:
    """Plafond legitime d'un batch d'indexation pour un modele donne.

    Sert a borner l'input UI et les routes serveur pour eviter qu'un user
    lance 10 000 indexations sur un modele qui a 250 RPD/jour.
    """
    if not model:
        return _BATCH_CAP_DEFAULT
    return _BATCH_CAPS_BY_MODEL.get(model, _BATCH_CAP_DEFAULT)


def list_all_images() -> list[str]:
    """Liste tous les noms de fichiers images dans Config.IMAGES_DIR."""
    if not Config.IMAGES_DIR.exists():
        return []
    out = []
    for p in sorted(Config.IMAGES_DIR.iterdir()):
        if p.suffix.lower() in SUPPORTED_FORMATS:
            out.append(p.name)
    return out


def list_unindexed(limit: int | None = None) -> list[str]:
    """Liste les images du dossier pas encore présentes en DB."""
    all_imgs = set(list_all_images())
    with db.cursor() as cur:
        cur.execute("SELECT filename FROM mkt_images")
        indexed = {r["filename"] for r in cur.fetchall()}
    remaining = sorted(all_imgs - indexed)
    return remaining[:limit] if limit else remaining


def count_stats() -> dict:
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM mkt_images")
        total_indexed = cur.fetchone()["n"]

        cur.execute("""
            SELECT compaatible_fit, COUNT(*) AS n
            FROM mkt_images
            GROUP BY compaatible_fit
            ORDER BY compaatible_fit
        """)
        by_fit = {r["compaatible_fit"]: r["n"] for r in cur.fetchall()}

    return {
        "total_on_disk": len(list_all_images()),
        "indexed": total_indexed,
        "unindexed": len(list_all_images()) - total_indexed,
        "by_fit": by_fit,
    }


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def image_to_base64(path: Path) -> tuple[str, str]:
    """Retourne (media_type, base64_data)."""
    ext = path.suffix.lower()
    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_map.get(ext, "image/jpeg")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return media_type, data


def build_system_for_vision() -> list[dict]:
    """Prompt système pour l'annotation marketing d'une image."""
    return [
        {
            "type": "text",
            "text": (
                "Tu es un directeur artistique expert en marketing relationnel. Tu annotes des images "
                "d'inspiration pour un projet marketing Compaatible (app de rencontres française basée "
                "sur le Big Five). Tu juges chaque image sur sa pertinence pour ce produit + tu produis "
                "des métadonnées structurées exploitables en base de données."
            ),
        },
        {
            "type": "text",
            "text": "## CONTEXTE PRODUIT\n\n" + prompts.get_compaatible_brief(),
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": "## AVATARS COMPAATIBLE — FICHIER COMPLET\n\n" + prompts.get_avatars_full(),
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                "## RÈGLES D'ANNOTATION\n\n"
                "Pour chaque image, produis une description **ultra-détaillée** (8-15 lignes) qui couvre :\n"
                "- ce qui est présent physiquement (personnes, objets, scène, cadrage)\n"
                "- l'ambiance et la lumière\n"
                "- les émotions générées chez le spectateur\n"
                "- le style visuel (photo réelle / illustration / anime / flat-lay / vintage / etc.)\n"
                "- la palette de couleurs dominante\n\n"
                "## RÈGLE DURE — DROIT À L'IMAGE\n\n"
                "Avant tout autre jugement, repère les **visages photo-réels clairement identifiables**. "
                "Un visage est *clairement identifiable* quand un humain pourrait reconnaître la personne sur "
                "la photo : traits distincts visibles (yeux, nez, bouche), photo nette, frontale ou trois-quarts, "
                "pas une silhouette/contre-jour/flou/profil illisible/dos tourné, et **pas une illustration** "
                "(anime, dessin, peinture sont OK même avec visage net). Si tu en vois au moins un :\n"
                "- `clearly_identifiable_face` = `true`\n"
                "- `compaatible_fit` = **`off_brand`** automatiquement, même si le reste de l'image est "
                "parfaite. C'est une règle juridique (droit à l'image) qui prime sur l'esthétique.\n"
                "- Mentionne brièvement dans `usage_warning` : « visage photo-réel identifiable — droit "
                "à l'image ».\n"
                "Sinon `clearly_identifiable_face` = `false` et tu juges `compaatible_fit` normalement.\n\n"
                "Puis tu juges l'**adéquation Compaatible** (`compaatible_fit`) sur 4 niveaux :\n"
                "- `high` : couple intime sans face très exposée, anime romantique chaleureux, mains, scènes "
                "cozy, scènes contemplatives qui parlent à un avatar Compaatible. Palette compatible avec "
                "burgundy/cream/warm.\n"
                "- `medium` : utilisable avec contexte (text overlay, retouche, etc.). Faces partiellement "
                "visibles mais NON identifiables (silhouettes, profils flous, contre-jours), usage organique "
                "inspirationnel OK.\n"
                "- `low` : peu d'intérêt direct pour Compaatible (mariage très culturel, photos couple "
                "tres engagées avec bague, etc.). À conserver pour cas rares.\n"
                "- `off_brand` : visages photo-réels clairement identifiables (cf règle ci-dessus), luxe "
                "ostentatoire (yachts, voitures de sport, marques visibles), flat-lays mode sans personne, "
                "vintage avec watermarks, photos sexy/pin-up, contenu sans rapport avec une rencontre/"
                "relation. À ignorer.\n\n"
                "Pour `suggested_avatars` : array d'IDs (1-11) des avatars qui résoneraient avec l'image. "
                "Vide si off_brand. Cohérence avec le ton de l'image.\n\n"
                "**Format de sortie : JSON strict, rien d'autre, pas de bloc ``` :**\n\n"
                "```json\n"
                "{\n"
                '  "image_type": "photo_real | anime_illustration | painting | flatlay_outfit | graphic_text | mixed",\n'
                '  "subject_type": "couple | single_person | group | body_part | object_scene | nature | mixed",\n'
                '  "people_count": 0,\n'
                '  "faces_visible": false,\n'
                '  "clearly_identifiable_face": false,\n'
                '  "description": "Description ultra-détaillée en 8-15 lignes...",\n'
                '  "marketing_use": "Comment utiliser cette image en marketing Compaatible (2-4 phrases).",\n'
                '  "emotions": ["intimacy","warmth","melancholy"],\n'
                '  "ambiance": ["cozy","cinematic","sunset"],\n'
                '  "setting": ["indoor","bedroom"],\n'
                '  "colors": ["warm","amber","muted"],\n'
                '  "style_tags": ["pinterest_aesthetic","soft_focus"],\n'
                '  "cultural_specificity": "universal",\n'
                '  "has_text_overlay": false,\n'
                '  "text_content": null,\n'
                '  "quality_score": 8,\n'
                '  "composition": "close_up | mid_shot | wide | pov | from_behind",\n'
                '  "compaatible_fit": "high | medium | low | off_brand",\n'
                '  "suggested_avatars": [5, 6, 9],\n'
                '  "suggested_platforms": ["twitter","reddit","instagram"],\n'
                '  "usage_warning": null,\n'
                '  "notes": null\n'
                "}\n"
                "```"
            ),
            "cache_control": {"type": "ephemeral"},
        },
    ]


def index_image(filename: str, model: str) -> dict[str, Any]:
    """Indexe une image. Insère/MAJ en DB. Retourne {ok, metadata, usage}."""
    path = Config.IMAGES_DIR / filename
    if not path.exists():
        return {"ok": False, "error": f"Fichier introuvable : {filename}"}

    media_type, data = image_to_base64(path)

    user_content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
        {"type": "text", "text": f"Annote cette image (filename: `{filename}`). Retourne UNIQUEMENT le JSON spécifié."},
    ]

    try:
        result = llm_client.call_messages(
            model=model,
            system_blocks=build_system_for_vision(),
            messages=[{"role": "user", "content": user_content}],
            max_tokens=2048,
            temperature=0.5,
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "filename": filename}

    try:
        meta = parse_json_response(result["text"])
    except Exception as e:
        return {"ok": False, "error": f"JSON parse error: {e}", "raw": result["text"][:200], "filename": filename}

    # Override "droit a l'image" : si visage photo-reel clairement identifiable,
    # on force off_brand peu importe ce que le modele a propose. Garde-fou
    # juridique : prime sur l'esthetique. On garde trace du downgrade dans
    # usage_warning pour que l'utilisateur comprenne pourquoi l'image est OFF.
    if meta.get("clearly_identifiable_face") is True:
        original_fit = meta.get("compaatible_fit")
        if original_fit != "off_brand":
            meta["compaatible_fit"] = "off_brand"
            note = "Visage photo-reel identifiable - droit a l'image (downgrade auto en off_brand)"
            existing = (meta.get("usage_warning") or "").strip()
            meta["usage_warning"] = f"{note}. {existing}".strip() if existing else note
            meta["notes"] = (meta.get("notes") or "") + f" [auto: fit force off_brand (modele proposait {original_fit})]"

    # Enrichir
    meta["filename"] = filename
    meta["file_hash"] = file_hash(path)
    stat = path.stat()
    meta["file_size_kb"] = max(1, stat.st_size // 1024)
    meta["format"] = path.suffix.lower().lstrip(".")
    # Annotated_by = modèle utilisé
    meta["annotated_by"] = f"vision_indexer:{model}"

    inserted_id = upsert_image(meta)

    return {
        "ok": True,
        "id": inserted_id,
        "filename": filename,
        "metadata": meta,
        "usage": result["usage"],
    }


def upsert_image(meta: dict) -> int:
    """INSERT ON CONFLICT UPDATE. Retourne l'id."""
    # Whitelist des colonnes pour éviter d'envoyer des champs inattendus
    allowed = {
        "filename", "file_hash", "width", "height", "file_size_kb", "format",
        "image_type", "subject_type", "people_count", "faces_visible",
        "description", "marketing_use",
        "emotions", "ambiance", "setting", "colors", "style_tags",
        "cultural_specificity", "has_text_overlay", "text_content",
        "quality_score", "composition",
        "compaatible_fit", "suggested_avatars", "suggested_platforms", "usage_warning",
        "annotated_by", "notes",
    }
    fields = {k: v for k, v in meta.items() if k in allowed and v is not None}

    cols = list(fields.keys())
    placeholders = ",".join(f"%({c})s" for c in cols)
    col_names = ",".join(cols)
    update_set = ",".join(f"{c}=EXCLUDED.{c}" for c in cols if c != "filename")

    sql = (
        f"INSERT INTO mkt_images ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT (filename) DO UPDATE SET {update_set}, annotated_at=NOW() "
        f"RETURNING id"
    )

    with db.cursor() as cur:
        cur.execute(sql, fields)
        return cur.fetchone()["id"]


def index_batch(filenames: list[str], model: str, on_progress: Callable[[int, int, dict], None] | None = None) -> dict:
    """Indexe un batch. on_progress(i, total, result) appelé à chaque image."""
    results = []
    total_usage = {"input_tokens": 0, "cached_tokens": 0, "cache_creation_tokens": 0, "output_tokens": 0, "cost_usd_estimate": 0.0}
    errors = []

    for i, fn in enumerate(filenames, 1):
        r = index_image(fn, model)
        results.append(r)
        if on_progress:
            on_progress(i, len(filenames), r)
        if r["ok"]:
            for k in total_usage:
                if k in r.get("usage", {}):
                    total_usage[k] += r["usage"][k]
        else:
            errors.append({"filename": fn, "error": r.get("error")})

    return {
        "total": len(filenames),
        "ok_count": sum(1 for r in results if r["ok"]),
        "errors": errors,
        "usage": total_usage,
    }


def index_batch_async(filenames: list[str], model: str) -> int:
    """Lance un batch d'indexation dans un thread daemon. Retourne le batch_id.

    L'avancement est écrit dans image_batch_state pour la page UI qui poll.
    """
    batch_id = image_batch_state.new_id()
    image_batch_state.init(batch_id, total=len(filenames), model=model)

    def _runner():
        try:
            stopped_early = False
            for fn in filenames:
                # Check stop flag avant chaque image. Sortie propre = on garde
                # tout ce qui a deja ete annote, on ne supprime rien.
                if image_batch_state.is_stop_requested(batch_id):
                    stopped_early = True
                    break
                image_batch_state.mark_current(batch_id, fn)
                try:
                    r = index_image(fn, model)
                except Exception as e:
                    r = {"ok": False, "error": f"{type(e).__name__}: {e}", "filename": fn}
                    traceback.print_exc(file=sys.stdout)
                    sys.stdout.flush()
                image_batch_state.record_result(batch_id, fn, r)
            if stopped_early:
                image_batch_state.finalize(
                    batch_id, success=False,
                    error="Batch interrompu par l'utilisateur (les images deja annotees sont conservees)."
                )
            else:
                image_batch_state.finalize(batch_id, success=True)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            image_batch_state.finalize(batch_id, success=False, error=f"{type(e).__name__}: {e}")

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return batch_id


def query_images(
    fit: list[str] | None = None,
    avatar_id: int | None = None,
    emotion: str | None = None,
    ambiance: str | None = None,
    image_type: str | None = None,
    search: str | None = None,
    limit: int = 60,
    offset: int = 0,
    indexed_only: bool = False,
) -> tuple[list[dict], int]:
    """Recherche dans mkt_images. Retourne (rows, total_count)."""
    where = []
    params: dict = {}

    if fit:
        where.append("compaatible_fit = ANY(%(fit)s)")
        params["fit"] = fit
    if avatar_id:
        where.append("%(av)s = ANY(suggested_avatars)")
        params["av"] = avatar_id
    if emotion:
        where.append("%(em)s = ANY(emotions)")
        params["em"] = emotion
    if ambiance:
        where.append("%(am)s = ANY(ambiance)")
        params["am"] = ambiance
    if image_type:
        where.append("image_type = %(it)s")
        params["it"] = image_type
    if search:
        where.append("(description ILIKE %(q)s OR marketing_use ILIKE %(q)s OR filename ILIKE %(q)s)")
        params["q"] = f"%{search}%"

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with db.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM mkt_images {where_sql}", params)
        total = cur.fetchone()["n"]

        cur.execute(
            f"SELECT id, filename, image_type, subject_type, compaatible_fit, "
            f"suggested_avatars, emotions, ambiance, description "
            f"FROM mkt_images {where_sql} "
            f"ORDER BY id DESC LIMIT %(limit)s OFFSET %(offset)s",
            {**params, "limit": limit, "offset": offset},
        )
        rows = [dict(r) for r in cur.fetchall()]

    return rows, total


def get_image(filename: str) -> dict | None:
    with db.cursor() as cur:
        cur.execute("SELECT * FROM mkt_images WHERE filename = %s", (filename,))
        row = cur.fetchone()
        return dict(row) if row else None


_ALLOWED_FITS = {"high", "medium", "low", "off_brand"}


def update_image_fit(filename: str, new_fit: str) -> dict:
    """Reclasse une image dans une autre catégorie de fit Compaatible.

    Whitelist stricte des valeurs : high | medium | low | off_brand. Toute autre
    valeur est refusée pour éviter qu'on pollue la DB avec des fits non gérés
    par l'UI (filtres + dot couleur).
    """
    if new_fit not in _ALLOWED_FITS:
        return {"ok": False, "error": f"Valeur fit invalide : {new_fit} (attendu : {', '.join(sorted(_ALLOWED_FITS))})"}
    if not filename or "/" in filename or "\\" in filename:
        return {"ok": False, "error": f"Nom de fichier invalide : {filename}"}

    with db.cursor() as cur:
        cur.execute(
            "UPDATE mkt_images SET compaatible_fit = %s WHERE filename = %s RETURNING id",
            (new_fit, filename),
        )
        row = cur.fetchone()
    if not row:
        return {"ok": False, "error": f"Image {filename} introuvable."}
    return {"ok": True, "filename": filename, "new_fit": new_fit}


def bulk_delete_by_fit(fit: str) -> dict:
    """Supprime en masse toutes les images dont compaatible_fit = X.

    Boucle sur delete_image pour réutiliser exactement la même logique (FK
    cleanup sur mkt_tweets, suppression fichier disque). Retourne le total
    supprimé et la somme des tweets déliés."""
    if fit not in _ALLOWED_FITS:
        return {"ok": False, "error": f"Valeur fit invalide : {fit}"}

    with db.cursor() as cur:
        cur.execute(
            "SELECT filename FROM mkt_images WHERE compaatible_fit = %s",
            (fit,),
        )
        filenames = [r["filename"] for r in cur.fetchall()]

    if not filenames:
        return {"ok": True, "fit": fit, "deleted": 0, "tweets_unlinked": 0, "files_deleted": 0}

    deleted = 0
    tweets_unlinked = 0
    files_deleted = 0
    errors: list[dict] = []
    for fn in filenames:
        r = delete_image(fn, delete_file=True)
        if r.get("ok"):
            deleted += 1
            tweets_unlinked += r.get("tweets_unlinked", 0)
            if r.get("file_deleted"):
                files_deleted += 1
        else:
            errors.append({"filename": fn, "error": r.get("error")})

    return {
        "ok": True,
        "fit": fit,
        "deleted": deleted,
        "tweets_unlinked": tweets_unlinked,
        "files_deleted": files_deleted,
        "errors": errors,
    }


def delete_image(filename: str, delete_file: bool = True) -> dict:
    """Supprime une image : row mkt_images + (optionnel) fichier disque.

    Les tweets qui référencent cette image via image_id voient leur FK passée
    automatiquement à NULL (ON DELETE SET NULL côté schéma). On force aussi
    media_url et image_chosen_at à NULL sur ces tweets pour éviter qu'un lien
    Cortex pointe vers une image supprimée.

    Retourne {ok, tweets_unlinked, file_deleted, filename}.
    """
    # Sécurité chemin : on n'accepte pas de séparateur ni de chemin relatif
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        return {"ok": False, "error": f"Nom de fichier invalide : {filename}"}

    with db.cursor() as cur:
        cur.execute("SELECT id, public_url FROM mkt_images WHERE filename = %s", (filename,))
        row = cur.fetchone()
        if not row:
            return {"ok": False, "error": f"Image {filename} introuvable en DB."}
        image_id = row["id"]

        # Nettoyer media_url / image_chosen_at sur les tweets qui référencent cette image.
        # ON DELETE SET NULL gère image_id, mais pas ces deux colonnes.
        cur.execute(
            "UPDATE mkt_tweets SET media_url = NULL, image_chosen_at = NULL "
            "WHERE image_id = %s",
            (image_id,),
        )
        tweets_unlinked = cur.rowcount

        # Supprimer la row image (cascade via FK pour mkt_tweets.image_id).
        cur.execute("DELETE FROM mkt_images WHERE id = %s", (image_id,))

    # Supprimer le fichier disque si demandé
    file_deleted = False
    if delete_file:
        path = Config.IMAGES_DIR / filename
        try:
            if path.exists():
                path.unlink()
                file_deleted = True
        except OSError as e:
            print(f"[vision_indexer] Suppression fichier {filename} ECHEC : {e}", flush=True)

    return {
        "ok": True,
        "filename": filename,
        "tweets_unlinked": tweets_unlinked,
        "file_deleted": file_deleted,
    }


def delete_images_by_filenames(filenames: list[str]) -> dict:
    """Supprime en masse une LISTE explicite d'images (selection manuelle UI).

    Pour chaque image : tweets delies (image_id via FK SET NULL + media_url /
    image_chosen_at remis a NULL), row mkt_images supprimee, fichier disque
    efface. Retourne {ok, deleted, tweets_unlinked, files_deleted, errors}.
    """
    clean: list[str] = []
    seen: set[str] = set()
    for fn in filenames or []:
        fn = (fn or "").strip()
        if not fn or "/" in fn or "\\" in fn or ".." in fn:
            continue
        if fn not in seen:
            seen.add(fn)
            clean.append(fn)
    if not clean:
        return {"ok": False, "error": "Aucun nom de fichier valide fourni."}

    with db.cursor() as cur:
        cur.execute(
            """
            UPDATE mkt_tweets t
               SET image_id = NULL, media_url = NULL, image_chosen_at = NULL
              FROM mkt_images i
             WHERE t.image_id = i.id
               AND i.filename = ANY(%s)
            """,
            (clean,),
        )
        tweets_unlinked = cur.rowcount or 0
        cur.execute(
            "DELETE FROM mkt_images WHERE filename = ANY(%s) RETURNING filename",
            (clean,),
        )
        deleted_rows = cur.fetchall()

    files_deleted = 0
    errors: list[str] = []
    for r in deleted_rows:
        fn = r["filename"]
        path = Config.IMAGES_DIR / fn
        try:
            if path.exists():
                path.unlink()
                files_deleted += 1
        except OSError as e:
            errors.append(f"{fn}: {e}")

    return {
        "ok": True,
        "deleted": len(deleted_rows),
        "tweets_unlinked": tweets_unlinked,
        "files_deleted": files_deleted,
        "errors": errors,
    }


def delete_images_by_filters(
    fit: list[str] | None = None,
    avatar_id: int | None = None,
    emotion: str | None = None,
    ambiance: str | None = None,
    image_type: str | None = None,
    search: str | None = None,
) -> dict:
    """Supprime TOUTES les images correspondant aux filtres courants (toutes pages
    confondues), pas seulement celles visibles a l'ecran.

    Construit la meme clause WHERE que query_images pour que "supprimer tout ce
    qui correspond" colle exactement a ce que l'utilisateur a filtre.

    Garde-fou : refuse une suppression SANS aucun filtre (eviter un wipe total
    accidentel du corpus). Pour tout vider, passer par un filtre explicite.
    Retourne {ok, deleted, tweets_unlinked, files_deleted, errors}.
    """
    where = []
    params: dict = {}
    if fit:
        where.append("compaatible_fit = ANY(%(fit)s)")
        params["fit"] = fit
    if avatar_id:
        where.append("%(av)s = ANY(suggested_avatars)")
        params["av"] = avatar_id
    if emotion:
        where.append("%(em)s = ANY(emotions)")
        params["em"] = emotion
    if ambiance:
        where.append("%(am)s = ANY(ambiance)")
        params["am"] = ambiance
    if image_type:
        where.append("image_type = %(it)s")
        params["it"] = image_type
    if search:
        where.append("(description ILIKE %(q)s OR marketing_use ILIKE %(q)s OR filename ILIKE %(q)s)")
        params["q"] = f"%{search}%"

    if not where:
        return {"ok": False, "error": "Suppression globale sans filtre refusee. Applique au moins un filtre (fit, avatar, recherche...)."}

    where_sql = "WHERE " + " AND ".join(where)

    with db.cursor() as cur:
        cur.execute(
            f"""
            UPDATE mkt_tweets t
               SET image_id = NULL, media_url = NULL, image_chosen_at = NULL
              FROM mkt_images i
             WHERE t.image_id = i.id
               AND i.id IN (SELECT id FROM mkt_images {where_sql})
            """,
            params,
        )
        tweets_unlinked = cur.rowcount or 0
        cur.execute(
            f"DELETE FROM mkt_images {where_sql} RETURNING filename",
            params,
        )
        deleted_rows = cur.fetchall()

    files_deleted = 0
    errors: list[str] = []
    for r in deleted_rows:
        fn = r["filename"]
        path = Config.IMAGES_DIR / fn
        try:
            if path.exists():
                path.unlink()
                files_deleted += 1
        except OSError as e:
            errors.append(f"{fn}: {e}")

    return {
        "ok": True,
        "deleted": len(deleted_rows),
        "tweets_unlinked": tweets_unlinked,
        "files_deleted": files_deleted,
        "errors": errors,
    }
