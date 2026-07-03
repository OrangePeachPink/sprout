"""Tests for identifier_guard (#558).

Every identifier-shaped test string is BUILT AT RUNTIME (join/format) so this
file never contains a literal MAC / USB-ID for the guard to flag - the guard
scans the whole tracked tree, including its own tests.
"""

from __future__ import annotations

import struct

from identifier_guard import (
    MAC_RE,
    USB_INSTANCE_RE,
    VID_PID_RE,
    jpeg_meta_segments,
    jpeg_strip,
    png_meta_chunks,
    png_strip,
    scan_text,
)

# --- dynamic fixtures --------------------------------------------------------


def mac(sep: str, groups: int) -> str:
    return sep.join(f"{n:02x}" for n in range(0xA0, 0xA0 + groups))


def eui64_fffe(sep: str) -> str:
    parts = ["24", "6f", "28", "ff", "fe", "9a", "bc", "de"]
    return sep.join(parts)


def vid_pid() -> str:
    return "VID_" + "10C4" + "&" + "PID_" + "EA60"


def usb_instance(serial: str = "") -> str:
    base = "USB" + "\\" + vid_pid()
    return base + ("\\" + serial if serial else "")


# --- text classes ------------------------------------------------------------


def hits(text: str) -> list[tuple[str, str]]:
    return [(f.cls, f.text) for f in scan_text("x.md", text.encode(), None)]


def test_mac_colon_6_group():
    assert ("mac", mac(":", 6)) in hits(f"esptool says MAC: {mac(':', 6)} done")


def test_mac_hyphen_6_group():
    # Device Manager / Windows convention
    assert ("mac", mac("-", 6)) in hits(f"Physical Address {mac('-', 6)}")


def test_eui64_fffe_8_group():
    assert ("mac", eui64_fffe(":")) in hits(f"base {eui64_fffe(':')} derived")


def test_timestamp_range_not_flagged():
    # The real bench-log false positive a naive [:-] class matches (#558):
    # two clock times joined by a hyphen. Consistent-separator must reject it.
    assert hits("window 07:18:17-12:16:24 local") == []


def test_date_slug_not_flagged():
    assert hits("docs/evidence/2026-07-01-esp32-s3-c5-intake/") == []


def test_mixed_separator_not_flagged():
    mixed = mac(":", 3) + "-" + mac(":", 3)
    assert all(cls != "mac" for cls, _ in hits(f"see {mixed}"))


def test_vid_pid_flagged():
    assert ("vid-pid", vid_pid()) in hits(f"bridge enumerated as {vid_pid()}")


def test_usb_instance_with_serial_flagged_once():
    inst = usb_instance("0001A2B3C4")
    found = hits(f'InstanceId: "{inst}"')
    assert ("usb-instance", inst) in found
    # the contained bare VID/PID span must be suppressed, not double-reported
    assert all(cls != "vid-pid" for cls, _ in found)


def test_denylist_literal_and_regex():
    import re as _re

    deny = [_re.compile(_re.escape("MyHomeNet"), _re.IGNORECASE)]
    found = scan_text("x.md", b"joined ssid myhomenet quickly", deny)
    assert [(f.cls) for f in found] == ["denylist"]


# --- JPEG --------------------------------------------------------------------


def make_jpeg(with_exif: bool) -> bytes:
    out = bytearray(b"\xff\xd8")  # SOI
    if with_exif:
        payload = b"Exif\x00\x00" + b"\x01" * 10
        out += b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    # a harmless APP0/JFIF segment that must survive stripping
    jfif = b"JFIF\x00" + b"\x01\x02"
    out += b"\xff\xe0" + struct.pack(">H", len(jfif) + 2) + jfif
    out += b"\xff\xda" + struct.pack(">H", 4) + b"\x00\x00"  # SOS
    out += b"\xaa\xbb\xcc"  # fake entropy data
    out += b"\xff\xd9"  # EOI
    return bytes(out)


def test_jpeg_exif_detected():
    assert jpeg_meta_segments(make_jpeg(True)) == ["APP1(EXIF/XMP)"]


def test_jpeg_clean_is_clean():
    assert jpeg_meta_segments(make_jpeg(False)) == []


def test_jpeg_strip_removes_exif_keeps_image():
    stripped = jpeg_strip(make_jpeg(True))
    assert jpeg_meta_segments(stripped) == []
    assert stripped.startswith(b"\xff\xd8") and stripped.endswith(b"\xff\xd9")
    assert b"JFIF" in stripped  # non-metadata segment survived
    assert b"\xaa\xbb\xcc" in stripped  # entropy data untouched


# --- PNG ---------------------------------------------------------------------


def png_chunk(ctype: bytes, data: bytes) -> bytes:
    import zlib

    return (
        struct.pack(">I", len(data))
        + ctype
        + data
        + struct.pack(">I", zlib.crc32(ctype + data))
    )


def make_png(with_text: bool) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
    text = png_chunk(b"tEXt", b"Author\x00somebody") if with_text else b""
    idat = png_chunk(b"IDAT", b"\x00\x01")
    iend = png_chunk(b"IEND", b"")
    return sig + ihdr + text + idat + iend


def test_png_text_chunk_detected():
    assert png_meta_chunks(make_png(True)) == ["tEXt"]


def test_png_strip_removes_text_keeps_structure():
    stripped = png_strip(make_png(True))
    assert png_meta_chunks(stripped) == []
    assert b"IHDR" in stripped and b"IDAT" in stripped and b"IEND" in stripped
    assert b"somebody" not in stripped


def test_regex_objects_importable():
    # the compiled patterns are part of the module contract (used in docs/tests)
    assert MAC_RE.pattern and USB_INSTANCE_RE.pattern and VID_PID_RE.pattern
