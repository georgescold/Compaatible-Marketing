"""Upload des images mkt_images vers Supabase Storage + remplissage de public_url.

Workflow :
1. Crée (idempotent) un bucket PUBLIC dans Supabase Storage.
2. Sélectionne en DB toutes les images compaatible_fit IN ('high','medium') AND public_url IS NULL.
3. Pour chaque, upload Images/{filename} via l'API Storage REST.
4. UPDATE mkt_images SET public_url = <url publique> WHERE id = ...

Requiert SUPABASE_URL et SUPABASE_SERVICE_ROLE_KEY dans cockpit/.env.

Re-runnable : skip les images dont public_url est déjà set. Si un upload échoue
(fichier manquant, réseau...), on log et on continue avec les suivantes.

NE TOUCHE PAS aux tables blogs (blog_articles, regions_seo, villes_seo).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Importer db_config depuis ce même dossier
sys.path.insert(0, os.path.dirname(__file__))
from db_config import get_conn  # noqa: E402

# Charger le .env du cockpit
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COCKPIT_ENV = PROJECT_ROOT / "cockpit" / ".env"
load_dotenv(COCKPIT_ENV)

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
BUCKET = os.getenv("SUPABASE_IMAGES_BUCKET", "mkt-images").strip()
IMAGES_DIR = PROJECT_ROOT / "Images"

CONTENT_TYPE_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def fail(msg: str) -> None:
    print(f"[FATAL] {msg}", file=sys.stderr)
    sys.exit(1)


def headers_json() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "apikey": SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
    }


def ensure_bucket() -> None:
    """Crée le bucket public s'il n'existe pas déjà. Idempotent."""
    print(f"[bucket] Vérification du bucket '{BUCKET}'...")
    r = requests.get(
        f"{SUPABASE_URL}/storage/v1/bucket/{BUCKET}",
        headers=headers_json(),
        timeout=15,
    )
    if r.status_code == 200:
        info = r.json()
        if not info.get("public"):
            fail(
                f"Bucket '{BUCKET}' existe mais n'est PAS public. "
                "Va dans Supabase Dashboard → Storage et coche 'Public bucket', "
                "ou supprime-le et relance ce script."
            )
        print(f"[bucket] OK : '{BUCKET}' existe déjà et est public.")
        return

    # Supabase Storage renvoie HTTP 400 avec body statusCode='404' quand le bucket n'existe pas.
    # On considère "not found" si le body contient ce marqueur, peu importe le code HTTP.
    body_lower = r.text.lower() if r.text else ""
    if r.status_code == 404 or ("not found" in body_lower) or ('"statuscode":"404"' in body_lower):
        pass  # tombe sur le code de création ci-dessous
    else:
        fail(f"Erreur inattendue en vérifiant le bucket : {r.status_code} {r.text}")

    # Création
    print(f"[bucket] Création de '{BUCKET}' (public)...")
    r = requests.post(
        f"{SUPABASE_URL}/storage/v1/bucket",
        headers=headers_json(),
        json={
            "id": BUCKET,
            "name": BUCKET,
            "public": True,
            "file_size_limit": 5 * 1024 * 1024,  # 5 MB par image (cf. spec Cortex)
            "allowed_mime_types": list(set(CONTENT_TYPE_BY_EXT.values())),
        },
        timeout=15,
    )
    if r.status_code not in (200, 201):
        fail(f"Création du bucket échouée : {r.status_code} {r.text}")
    print(f"[bucket] Créé.")


def public_url_for(filename: str) -> str:
    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{filename}"


def upload_one(filename: str) -> tuple[bool, str]:
    """Upload Images/{filename} vers le bucket. Retourne (ok, message/url)."""
    local = IMAGES_DIR / filename
    if not local.exists():
        return False, f"fichier local manquant : {local}"

    ext = local.suffix.lower()
    content_type = CONTENT_TYPE_BY_EXT.get(ext)
    if not content_type:
        return False, f"extension non supportée : {ext}"

    url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{filename}"
    with open(local, "rb") as f:
        data = f.read()

    if len(data) > 5 * 1024 * 1024:
        return False, f"fichier > 5 MB ({len(data)} octets), skip"

    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
            "apikey": SERVICE_ROLE_KEY,
            "Content-Type": content_type,
            "x-upsert": "true",  # idempotent si on relance
        },
        data=data,
        timeout=60,
    )
    if r.status_code in (200, 201):
        return True, public_url_for(filename)
    return False, f"HTTP {r.status_code} : {r.text[:200]}"


def main() -> None:
    if not SUPABASE_URL:
        fail("SUPABASE_URL manquant dans cockpit/.env")
    if not SERVICE_ROLE_KEY:
        fail(
            "SUPABASE_SERVICE_ROLE_KEY manquant dans cockpit/.env. "
            "Récupère-la dans Supabase Dashboard → Project Settings → API → service_role."
        )
    if not IMAGES_DIR.exists():
        fail(f"Dossier Images introuvable : {IMAGES_DIR}")

    ensure_bucket()

    conn = get_conn()
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # On uploade TOUTES les images en DB (tous fits), pas seulement high/medium :
    # ça donne la flexibilité de re-classer une image plus tard sans re-uploader.
    # Le matcher continue de filtrer sur compaatible_fit IN ('high','medium') à la lecture.
    cur.execute(
        """
        SELECT id, filename, compaatible_fit
        FROM mkt_images
        WHERE public_url IS NULL
        ORDER BY id
        """
    )
    rows = cur.fetchall()
    total = len(rows)
    print(f"[scan] {total} image(s) éligible(s) à uploader.")

    ok_count = 0
    fail_count = 0
    t0 = time.time()

    for i, row in enumerate(rows, start=1):
        filename = row["filename"]
        success, info = upload_one(filename)
        if not success:
            fail_count += 1
            print(f"  [{i}/{total}] FAIL {filename} → {info}")
            continue

        # UPDATE public_url
        cur.execute(
            "UPDATE mkt_images SET public_url = %s WHERE id = %s",
            (info, row["id"]),
        )
        conn.commit()
        ok_count += 1
        if i % 10 == 0 or i == total:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed else 0
            print(f"  [{i}/{total}] OK ({rate:.1f} img/s) — dernier : {filename}")

    cur.close()
    conn.close()

    print()
    print(f"[done] succès : {ok_count} / échecs : {fail_count} / total : {total}")
    if ok_count:
        print(
            f"[done] public_url renseignée pour {ok_count} images. "
            "Tu peux relancer 'Intégrer les images' dans le cockpit."
        )


if __name__ == "__main__":
    main()
