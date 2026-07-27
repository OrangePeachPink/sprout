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

**Source safety (grill-ruled #1039, LOCKED):** this util ingests **bytes or a local path
only**, and **server-side URL fetching is permanently deferred** — the browser upload is
the only intake, so the SSRF fence never opens. This costs nothing in reach: a
``<input type="file" accept="image/*">`` opens the OS photo library natively on phones
(iOS Photos, Google Photos), so "pick from my library" IS the browser-upload path.

**Input contract (#1039 Q4 spec):** accept only the raster formats in
``ALLOWED_INPUT_FORMATS`` (SVG/vector/unknown rejected — an SVG can carry script);
reject an upload over ``MAX_UPLOAD_BYTES`` before decoding; Pillow's decompression-bomb
guard covers pixel-count attacks. Output is always a small EXIF-stripped JPEG at
``config/photos/<plant_id>.jpg``, served read-only via ``GET /photo/<plant_id>``.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps

# A representative avatar, not a gallery image: cap the long edge, re-encode small.
# 320 px is plenty to recognise a plant at a glance; JPEG q82 lands well under ~50 KB.
MAX_EDGE = 320
JPEG_QUALITY = 82

# #1039 Q4 spec — INPUT FORMAT ALLOWLIST. The raster formats Pillow decodes reliably
# from a browser upload. iOS HEIC library photos: Safari re-encodes HEIC->JPEG when a
# `<input type="file" accept="image/*">` uploads them, so the server almost always
# receives JPEG; a raw HEIC (we don't ship pillow-heif) is rejected with a clear message
# rather than silently mishandled. SVG / vector / unknown formats are out (an SVG can
# carry script + external refs — never a safe avatar source).
ALLOWED_INPUT_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "GIF", "BMP", "TIFF"})
# #1039 Q4 spec — SIZE CAP. A phone photo is ~2-8 MB; 20 MB is generous headroom and a
# firm ceiling on the in-memory upload (a DoS guard). Enforced here AND at the serve
# boundary (defense in depth). Pillow's decompression-bomb guard covers pixel-count
# attacks separately (a small file that expands to billions of pixels).
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

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


def _check_size(src: bytes | str | Path) -> None:
    """Reject an over-cap upload before decoding (#1039 Q4). Bytes are measured
    directly; a path is ``stat``'d. A missing path falls through to ``_open``'s
    FileNotFoundError."""
    if isinstance(src, bytes | bytearray):
        n = len(src)
    else:
        p = Path(src)
        n = p.stat().st_size if p.is_file() else 0
    if n > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"image too large: {n} bytes exceeds the {MAX_UPLOAD_BYTES}-byte cap"
        )


def ingest_photo(
    src: bytes | str | Path, plant_id: str, *, photos_dir: str | Path | None = None
) -> Path:
    """Downsample + EXIF-strip an image into a small avatar at
    ``<photos_dir>/<plant_id>.jpg``, returning the saved path. Never upscales; applies
    the orientation tag then drops ALL metadata; converts to RGB so it always encodes
    as a light JPEG. Raises on an unreadable / non-image source."""
    if not plant_id:
        raise ValueError("a plant_id is required to name the avatar")
    _check_size(src)  # #1039 Q4: firm ceiling before we decode anything
    with _open(src) as im:
        fmt = (im.format or "").upper()  # header-derived; read before exif_transpose
        if fmt not in ALLOWED_INPUT_FORMATS:  # #1039 Q4: raster allowlist
            raise ValueError(
                f"unsupported image format {im.format!r} — "
                f"allowed: {', '.join(sorted(ALLOWED_INPUT_FORMATS))}"
            )
        im = ImageOps.exif_transpose(im)  # honour rotation BEFORE we discard EXIF
        im = im.convert("RGB")  # drop alpha/palette — a solid, small JPEG
        im.thumbnail((MAX_EDGE, MAX_EDGE))  # keep aspect, never enlarge
        dest = Path(photos_dir) if photos_dir else _PHOTOS_DIR
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"{plant_id}.jpg"
        # No `exif=`/`icc_profile=` passed → the written file carries no metadata.
        im.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return out
