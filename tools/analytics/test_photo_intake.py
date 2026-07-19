"""#875 Q4 — plant photo intake. The privacy-critical property: a camera photo's EXIF
(GPS of home, device serials) is GONE from the stored avatar. Plus: it downsamples to a
small light image, never upscales, and takes bytes or a path.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from photo_intake import (
    MAX_EDGE,
    MAX_UPLOAD_BYTES,
    ingest_photo,
    registry_photo_path,
)


def _jpeg_with_gps(path: Path, size=(1200, 900)) -> None:
    """A JPEG carrying EXIF incl. a GPS sub-IFD — a stand-in for a real phone photo."""
    im = Image.new("RGB", size, (80, 140, 60))
    exif = im.getexif()
    exif[0x010F] = "TestCam"  # Make
    exif[0x0132] = "2026:07:18 09:00:00"  # DateTime
    gps = exif.get_ifd(0x8825)  # the GPS IFD — the coordinates of home
    gps[1] = "N"  # GPSLatitudeRef — a string, no rationals to trip the writer
    gps[2] = (51.0, 30.0, 0.0)  # GPSLatitude (deg, min, sec) as floats
    im.save(path, "JPEG", exif=exif)


def test_ingest_strips_exif_including_gps(tmp_path: Path) -> None:
    src = tmp_path / "cam.jpg"
    _jpeg_with_gps(src)
    src_exif = Image.open(src).getexif()
    assert dict(src_exif) and dict(src_exif.get_ifd(0x8825))  # source HAS GPS metadata
    out = ingest_photo(src, "p01", photos_dir=tmp_path / "photos")
    got = Image.open(out).getexif()
    assert dict(got) == {}  # every top-level tag gone (Make/DateTime)
    assert not dict(got.get_ifd(0x8825))  # the GPS IFD — home coords — is gone


def test_ingest_downsamples_and_stays_light(tmp_path: Path) -> None:
    src = tmp_path / "big.jpg"
    Image.new("RGB", (2000, 1500), (0, 120, 0)).save(src, "JPEG", quality=95)
    out = ingest_photo(src, "p02", photos_dir=tmp_path / "photos")
    w, h = Image.open(out).size
    assert max(w, h) <= MAX_EDGE and (w, h) != (2000, 1500)
    assert out.stat().st_size < 60_000  # a light avatar, not a gallery image


def test_ingest_never_upscales(tmp_path: Path) -> None:
    src = tmp_path / "small.jpg"
    Image.new("RGB", (120, 90), (0, 120, 0)).save(src, "JPEG")
    out = ingest_photo(src, "p03", photos_dir=tmp_path / "photos")
    assert Image.open(out).size == (120, 90)  # already small — left as-is


def test_ingest_from_bytes_and_transparency(tmp_path: Path) -> None:
    buf = io.BytesIO()
    Image.new("RGBA", (500, 500), (0, 120, 0, 128)).save(buf, "PNG")
    out = ingest_photo(buf.getvalue(), "p04", photos_dir=tmp_path / "photos")
    assert out.is_file() and Image.open(out).format == "JPEG"  # alpha flattened to JPEG


def test_registry_path_convention() -> None:
    assert registry_photo_path("p07") == "config/photos/p07.jpg"


def test_a_missing_file_raises_for_the_caller_to_report(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ingest_photo(tmp_path / "nope.jpg", "p01", photos_dir=tmp_path / "photos")


def test_a_blank_plant_id_is_rejected(tmp_path: Path) -> None:
    src = tmp_path / "x.jpg"
    Image.new("RGB", (100, 100), (0, 0, 0)).save(src, "JPEG")
    with pytest.raises(ValueError):
        ingest_photo(src, "", photos_dir=tmp_path / "photos")


def test_an_oversize_upload_is_rejected_before_decoding(tmp_path: Path) -> None:
    # #1039 Q4 size cap: over-ceiling bytes are rejected (needn't even decode).
    with pytest.raises(ValueError, match="too large"):
        ingest_photo(b"\x00" * (MAX_UPLOAD_BYTES + 1), "p01", photos_dir=tmp_path)


def test_a_disallowed_format_is_rejected(tmp_path: Path) -> None:
    # #1039 Q4 allowlist: a Pillow-openable but non-allowed format (ICO) is refused.
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (0, 120, 0)).save(buf, "ICO")
    with pytest.raises(ValueError, match="unsupported image format"):
        ingest_photo(buf.getvalue(), "p01", photos_dir=tmp_path / "photos")


def test_the_allowed_raster_formats_pass(tmp_path: Path) -> None:
    for fmt, ext in (("PNG", "png"), ("WEBP", "webp"), ("BMP", "bmp")):
        buf = io.BytesIO()
        Image.new("RGB", (400, 300), (0, 120, 0)).save(buf, fmt)
        out = ingest_photo(buf.getvalue(), f"p_{ext}", photos_dir=tmp_path / "photos")
        assert out.is_file() and Image.open(out).format == "JPEG"
