"""#875 Q4 — plant photo intake: a small, light, EXIF-stripped avatar.

The maintainer's call: support a photo of the *actual* plant so you can tell at a glance
which one Sprout means — from a phone, camera, computer file, or (later) a URL. Store a
**small, light representative image**, never a heavy high-res one, and **never a
cloud round-trip**. Fancy tricks (background removal, avatar filters) are out of
scope — just a clean, downsampled thumbnail.

**Privacy (non-negotiable):** a camera photo carries EXIF — GPS coordinates of home,
device serials, timestamps. This module **strips all of it** (applies the orientation
tag first, then writes a fresh image with no metadata) before the file ever lands in
``config/photos/`` (which is gitignored — same fence class as the home coordinates).

**Source safety:** this util ingests **bytes or a local path only**. A server-side fetch
of an arbitrary user URL is an SSRF risk, so URL support is deliberately left to the
caller (the browser fetches the URL and uploads the bytes, or a future guarded fetch) —
a security decision for the grill, not a default this util makes.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

# A representative avatar, not a gallery image: cap the long edge, re-encode small.
# 320 px is plenty to recognise a plant at a glance; JPEG q82 lands well under ~50 KB.
MAX_EDGE = 320
JPEG_QUALITY = 82
_REPO = Path(__file__).resolve().parents[2]
_PHOTOS_DIR = _REPO / "config" / "photos"


def registry_photo_path(plant_id: str) -> str:
    """The repo-relative path stored on ``Plant.photo`` for a plant's avatar."""
    return f"config/photos/{plant_id}.jpg"


def _open(src: bytes | str | Path) -> Image.Image:
    """Open from raw bytes or a local file path. (No network — URL fetch is the
    caller's, to keep SSRF out of this util.)"""
    if isinstance(src, bytes | bytearray):
        return Image.open(io.BytesIO(bytes(src)))
    p = Path(src)
    if not p.is_file():
        raise FileNotFoundError(f"no such image file: {p}")
    return Image.open(p)


def ingest_photo(
    src: bytes | str | Path, plant_id: str, *, photos_dir: str | Path | None = None
) -> Path:
    """Downsample + EXIF-strip an image into a small avatar at
    ``<photos_dir>/<plant_id>.jpg``, returning the saved path. Never upscales; applies
    the orientation tag then drops ALL metadata; converts to RGB so it always encodes
    as a light JPEG. Raises on an unreadable / non-image source."""
    if not plant_id:
        raise ValueError("a plant_id is required to name the avatar")
    with _open(src) as im:
        im = ImageOps.exif_transpose(im)  # honour rotation BEFORE we discard EXIF
        im = im.convert("RGB")  # drop alpha/palette — a solid, small JPEG
        im.thumbnail((MAX_EDGE, MAX_EDGE))  # keep aspect, never enlarge
        dest = Path(photos_dir) if photos_dir else _PHOTOS_DIR
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"{plant_id}.jpg"
        # No `exif=`/`icc_profile=` passed → the written file carries no metadata.
        im.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return out
