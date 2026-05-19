"""Genere des thumbnails <=1800px dans Images_thumbs/ pour permettre le batch
classifier de lire plusieurs images en parallele (limite Anthropic many-image
requests = 2000px max).

Idempotent : skip les fichiers deja generes (meme nom).
"""
from __future__ import annotations
import sys
from pathlib import Path

from PIL import Image

IMAGES_DIR = Path(r"C:\Users\loysc\Desktop\Compaatible marketing\Images")
THUMBS_DIR = Path(r"C:\Users\loysc\Desktop\Compaatible marketing\Images_thumbs")
MAX_DIM = 1280


def downscale_one(src: Path, dst: Path) -> str:
    """Retourne 'created', 'skipped', ou 'copied'."""
    if dst.exists():
        return "skipped"
    with Image.open(src) as im:
        im = im.convert("RGB") if im.mode not in ("RGB", "L") else im
        w, h = im.size
        if max(w, h) <= MAX_DIM:
            # Pas besoin de redim, copie en JPG
            im.save(dst, "JPEG", quality=85)
            return "copied"
        ratio = MAX_DIM / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        im = im.resize(new_size, Image.LANCZOS)
        im.save(dst, "JPEG", quality=85)
        return "created"


def main(limit: int | None = None):
    THUMBS_DIR.mkdir(exist_ok=True)
    all_files = sorted(
        [p for p in IMAGES_DIR.glob("*.jpg")] + [p for p in IMAGES_DIR.glob("*.png")]
    )
    if limit:
        all_files = all_files[:limit]

    stats = {"created": 0, "copied": 0, "skipped": 0, "error": 0}
    for i, src in enumerate(all_files, 1):
        # Thumb a TOUJOURS extension .jpg pour uniformiser
        dst = THUMBS_DIR / (src.stem + ".jpg")
        try:
            result = downscale_one(src, dst)
            stats[result] += 1
        except Exception as e:
            print(f"ERROR {src.name}: {e}")
            stats["error"] += 1
        if i % 100 == 0:
            print(f"  {i}/{len(all_files)} traites...")

    print(f"\nTotal : {len(all_files)} fichiers")
    print(f"  created  : {stats['created']}")
    print(f"  copied   : {stats['copied']}")
    print(f"  skipped  : {stats['skipped']}")
    print(f"  error    : {stats['error']}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
