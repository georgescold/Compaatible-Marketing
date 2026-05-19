"""Fonction d'insertion d'une image annotée dans la table images.

Importée par le pipeline d'annotation (qui appelle Claude Code multimodal pour
générer les métadonnées et appelle ensuite insert_image()).

Le pipeline d'annotation lui-même n'est PAS dans ce fichier (il vit dans la
conversation Claude Code, qui lit les images en multimodal et appelle ce script
via Bash pour persister).
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import psycopg2.extras

from db_config import get_conn


IMAGES_DIR = Path(r"C:\Users\loysc\Desktop\Compaatible marketing\Images")


def file_hash(path: Path) -> str:
    """Hash SHA-256 du fichier (8 premiers hex)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def insert_image(metadata: dict[str, Any]) -> int:
    """Insère ou met à jour l'image (sur conflit filename, UPDATE).

    metadata doit contenir au minimum : filename, description.
    Retourne l'id généré.
    """
    if "filename" not in metadata or "description" not in metadata:
        raise ValueError("metadata must contain at least 'filename' and 'description'")

    # Enrichir avec stats fichier si pas déjà fait
    path = IMAGES_DIR / metadata["filename"]
    if path.exists():
        if "file_hash" not in metadata:
            metadata["file_hash"] = file_hash(path)
        if "file_size_kb" not in metadata:
            metadata["file_size_kb"] = max(1, path.stat().st_size // 1024)
        if "format" not in metadata:
            metadata["format"] = path.suffix.lstrip(".").lower()

    conn = get_conn(autocommit=True)
    cur = conn.cursor()

    cols = list(metadata.keys())
    placeholders = ",".join(f"%({c})s" for c in cols)
    col_names = ",".join(cols)
    update_set = ",".join(f"{c}=EXCLUDED.{c}" for c in cols if c != "filename")

    sql = (
        f"INSERT INTO mkt_images ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT (filename) DO UPDATE SET {update_set}, annotated_at = NOW() "
        f"RETURNING id;"
    )

    cur.execute(sql, metadata)
    new_id = cur.fetchone()[0]

    cur.close()
    conn.close()
    return new_id


def insert_image_from_json(json_str: str) -> int:
    """CLI helper : reçoit un JSON sur stdin/arg, l'insère."""
    metadata = json.loads(json_str)
    return insert_image(metadata)


def list_unannotated(limit: int = 20) -> list[str]:
    """Retourne les noms de fichiers de Images/ pas encore en DB."""
    all_files = {p.name for p in IMAGES_DIR.glob("*.jpg")}
    all_files |= {p.name for p in IMAGES_DIR.glob("*.png")}

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT filename FROM mkt_images")
    done = {row[0] for row in cur.fetchall()}
    cur.close()
    conn.close()

    remaining = sorted(all_files - done)
    return remaining[:limit]


def count_annotated() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM mkt_images")
    n = cur.fetchone()[0]
    cur.close()
    conn.close()
    return n


if __name__ == "__main__":
    # CLI minimal :
    # python insert_image.py --json '{"filename": "...", "description": "...", ...}'
    # python insert_image.py --next 10     -> liste 10 noms non annotés
    # python insert_image.py --count       -> nombre d'images annotées
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python insert_image.py --json '<json>'")
        print("  python insert_image.py --next [N]")
        print("  python insert_image.py --count")
        sys.exit(1)

    if sys.argv[1] == "--count":
        print(count_annotated())
    elif sys.argv[1] == "--next":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        for fn in list_unannotated(n):
            print(fn)
    elif sys.argv[1] == "--json":
        new_id = insert_image_from_json(sys.argv[2])
        print(f"Inserted id={new_id}")
    else:
        print("Unknown command:", sys.argv[1])
        sys.exit(2)
