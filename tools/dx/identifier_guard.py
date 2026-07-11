#!/usr/bin/env python3
"""Identifier guard - hardware/network PII scan for the tracked tree (#558).

Bench evidence (photos, serial logs, Device Manager transcriptions) can leak
identifiers that tie the repo to the maintainer's hardware and home network:

- **Image metadata**: EXIF / XMP / IPTC blocks in camera-origin photos carry
  GPS, device model/serial, and timestamps. Detected byte-level (JPEG segment
  walk, PNG chunk walk) - no image library, no re-encode.
- **MAC addresses** in text: 6-group (classic) and 7-8-group (EUI-64, incl.
  esptool's ``ff:fe`` expanded form), colon- or hyphen-separated. The regex
  requires a CONSISTENT separator via backreference - a mixed run like a
  bench-log time range ("07:18:17-12:16:24") never matches (verified against
  the real corpus; a naive [:-] class flags exactly that).
- **USB instance IDs** in text: ``USB\\VID_xxxx&PID_xxxx\\<serial>`` instance
  paths (the serial suffix is the unique-to-your-unit part) and bare
  ``VID_xxxx&PID_xxxx`` model IDs (flagged per the #558 directive; generic
  model-level mentions can be allowlisted with a reason).
- **SSIDs / hostnames / other operator-sensitive terms** in text: not
  regexable generically - matched against an OPERATOR-LOCAL denylist
  (``config/identifiers.local.txt``, gitignored; committing the denylist would
  itself leak the terms). Home-network names are the original case, but the
  same list also covers any literal an operator wants kept out of the public
  tree - e.g. internal or companion-project codenames not yet announced.
  One term per line (``re:`` prefix = regex). Absent file => the class is
  skipped with a note (that's the CI case; CI still enforces the regex
  classes). For CI to enforce HOSTNAMES too (the gitignored file is absent
  there), a COMMITTED companion holds the SHA-256 of each denied hostname,
  lowercased (``config/identifiers.denylist.sha256``): hashes are safe to
  commit, so the guard token-matches them without the hostname ever entering
  the tree, and a hostname finding reports its location only - never the token
  (#865). Seed with ``--deny-host <name>``.

Findings print MASKED by default (first/last fragment only) so a CI log never
re-leaks what it caught; ``--reveal`` unmasks for local triage.

False-positive escape hatch: ``tools/dx/identifier_guard_allowlist.txt`` -
one ``<path>:<exact matched text>`` per line, reason in a comment above it.
The allowlist file itself is the only file exempt from scanning (its entries
are, by definition, reviewed exceptions - and they would self-flag).

Modes:
    --check (default)   scan the tracked tree; exit 1 on findings
    --history           one-time audit of EVERY blob ever committed (#558 AC:
                        a replaced image still leaks from old commits)
    --strip FILE...     remove metadata segments/chunks from the given images
                        byte-level (JPEG: APP1/APP13/COM; PNG: eXIf/tEXt/zTXt/
                        iTXt) - pixels untouched, then you re-commit
    --reveal            print full matched text instead of masked

Wired as a BLOCKING pre-commit hook (unlike cspell's advisory posture): a
leak that lands in history needs `git filter-repo` to truly remove, so
prevention is the one cheap moment. Gate precedent: PR #568's manual
certification, which this makes mechanical.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = REPO / "tools" / "dx" / "identifier_guard_allowlist.txt"
DENYLIST_PATH = REPO / "config" / "identifiers.local.txt"
# Committed hostname denylist: SHA-256 (of the lowercased hostname) per line.
# Unlike DENYLIST_PATH (gitignored plaintext, absent in CI), the hashes are safe
# to commit — they don't reveal the plaintext — so CI enforces the class without
# the hostname ever entering the tree. Seed via `--deny-host` (#865).
HOSTNAME_HASHES_PATH = REPO / "config" / "identifiers.denylist.sha256"
# A hostname-shaped word token: alnum start, then alnum / hyphen / underscore.
HOST_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{1,62}")
# A hostname-denylist finding NEVER carries the matched token (it would re-leak
# in a CI log) — only this fixed marker. The operator sees path:line and looks.
HOST_REDACTED = "<redacted — matched the committed hostname denylist>"

# Consistent separator via backreference: 6-8 hex pairs, all-colon or
# all-hyphen. 6 = classic MAC; 8 = EUI-64 (esptool's ff:fe form is a subset).
MAC_RE = re.compile(
    r"\b(?:[0-9A-Fa-f]{2}([:-]))(?:[0-9A-Fa-f]{2}\1){4,6}[0-9A-Fa-f]{2}\b"
)
# Full Windows instance path first (may carry the per-unit serial suffix)...
USB_INSTANCE_RE = re.compile(
    r"USB\\VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}(?:\\[^\s\"'|)\]]+)?"
)
# ...then the bare model-ID form anywhere.
VID_PID_RE = re.compile(r"VID_[0-9A-Fa-f]{4}&PID_[0-9A-Fa-f]{4}")

TEXT_CLASSES = [  # scan order matters: earlier spans suppress contained later ones
    ("usb-instance", USB_INSTANCE_RE),
    ("vid-pid", VID_PID_RE),
    ("mac", MAC_RE),
]

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
# Known-binary extensions we never text-scan (images get the metadata scan).
SKIP_TEXT_EXTS = IMAGE_EXTS | {
    ".gif",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".pdf",
    ".bin",
    ".elf",
}

JPEG_META_MARKERS = {0xE1: "APP1(EXIF/XMP)", 0xED: "APP13(IPTC)", 0xFE: "COM"}
PNG_META_CHUNKS = {b"eXIf", b"tEXt", b"zTXt", b"iTXt"}
PNG_SIG = b"\x89PNG\r\n\x1a\n"


class Finding:
    def __init__(self, path: str, line: int, cls: str, text: str):
        self.path, self.line, self.cls, self.text = path, line, cls, text

    def masked(self, reveal: bool) -> str:
        if self.cls == "hostname-denylist":
            # Never echo the matched token, even with --reveal (#865): a CI log
            # must not re-leak the hostname it caught. Report location only.
            return f"{self.path}:{self.line}: [{self.cls}] {HOST_REDACTED}"
        t = self.text
        if not reveal and len(t) > 8:
            # ASCII mask (Windows consoles mangle a unicode ellipsis)
            t = f"{t[:4]}...{t[-2:]} ({len(t)} chars)"
        return f"{self.path}:{self.line}: [{self.cls}] {t}"


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, check=True
    ).stdout


def tracked_files() -> list[str]:
    return [p for p in _git("ls-files", "-z").decode().split("\0") if p]


def load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.exists():
        return set()
    lines = ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
    return {ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")}


def load_denylist() -> list[re.Pattern] | None:
    """Operator-local SSID/hostname patterns, or None if the file is absent."""
    if not DENYLIST_PATH.exists():
        return None
    pats: list[re.Pattern] = []
    for ln in DENYLIST_PATH.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln.startswith("re:"):
            pats.append(re.compile(ln[3:], re.IGNORECASE))
        else:
            pats.append(re.compile(re.escape(ln), re.IGNORECASE))
    return pats


def _hash_host(name: str) -> str:
    """SHA-256 of a hostname, lowercased first (#865 spec: lowercase-before-hash)."""
    return hashlib.sha256(name.strip().lower().encode("utf-8")).hexdigest()


def load_hostname_hashes() -> set[str]:
    """Committed hostname SHA-256 digests (empty set if the file is absent/empty)."""
    if not HOSTNAME_HASHES_PATH.exists():
        return set()
    out: set[str] = set()
    for ln in HOSTNAME_HASHES_PATH.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            out.add(ln.lower())
    return out


# --- text scanning ----------------------------------------------------------


def scan_text(
    path: str,
    data: bytes,
    denylist: list[re.Pattern] | None,
    host_hashes: set[str] | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:  # pragma: no cover - decode with replace shouldn't raise
        return findings
    for lineno, line in enumerate(text.splitlines(), 1):
        taken: list[tuple[int, int]] = []
        for cls, rx in TEXT_CLASSES:
            for m in rx.finditer(line):
                span = m.span()
                if any(span[0] >= a and span[1] <= b for a, b in taken):
                    continue  # contained in an earlier, more specific match
                taken.append(span)
                findings.append(Finding(path, lineno, cls, m.group(0)))
        if denylist:
            for rx in denylist:
                for m in rx.finditer(line):
                    findings.append(Finding(path, lineno, "denylist", m.group(0)))
        if host_hashes:
            # Whole-word tokens, lowercased + hashed, checked against the committed
            # digests. A match reports HOST_REDACTED, never the token (#865).
            # Skipped entirely when the denylist is empty (zero overhead).
            for m in HOST_TOKEN_RE.finditer(line):
                if _hash_host(m.group(0)) in host_hashes:
                    findings.append(
                        Finding(path, lineno, "hostname-denylist", HOST_REDACTED)
                    )
    return findings


# --- image metadata (byte-level, stdlib-only) --------------------------------


def jpeg_meta_segments(data: bytes) -> list[str]:
    """Names of metadata segments present in a JPEG byte string."""
    found: list[str] = []
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        return found
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            break  # not at a marker - stop walking rather than guess
        marker = data[i + 1]
        if marker == 0xD9 or marker == 0xDA:  # EOI / SOS: entropy data follows
            break
        seglen = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in JPEG_META_MARKERS:
            found.append(JPEG_META_MARKERS[marker])
        i += 2 + seglen
    return found


def jpeg_strip(data: bytes) -> bytes:
    """The same walk, dropping metadata segments; pixel data untouched."""
    out = bytearray(data[0:2])
    i = 2
    while i + 4 <= len(data):
        if data[i] != 0xFF:
            break
        marker = data[i + 1]
        if marker == 0xD9 or marker == 0xDA:
            break
        seglen = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker not in JPEG_META_MARKERS:
            out += data[i : i + 2 + seglen]
        i += 2 + seglen
    out += data[i:]  # SOS onward (entropy-coded data + EOI) verbatim
    return bytes(out)


def png_meta_chunks(data: bytes) -> list[str]:
    found: list[str] = []
    if not data.startswith(PNG_SIG):
        return found
    i = len(PNG_SIG)
    while i + 8 <= len(data):
        clen = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8]
        if ctype in PNG_META_CHUNKS:
            found.append(ctype.decode("latin-1"))
        if ctype == b"IEND":
            break
        i += 12 + clen  # len + type + data + crc
    return found


def png_strip(data: bytes) -> bytes:
    out = bytearray(PNG_SIG)
    i = len(PNG_SIG)
    while i + 8 <= len(data):
        clen = struct.unpack(">I", data[i : i + 4])[0]
        ctype = data[i + 4 : i + 8]
        if ctype not in PNG_META_CHUNKS:
            out += data[i : i + 12 + clen]
        if ctype == b"IEND":
            break
        i += 12 + clen
    return bytes(out)


def scan_image(path: str, data: bytes) -> list[Finding]:
    ext = Path(path).suffix.lower()
    segs: list[str] = []
    if ext in (".jpg", ".jpeg"):
        segs = jpeg_meta_segments(data)
    elif ext == ".png":
        segs = png_meta_chunks(data)
    return [Finding(path, 0, "image-metadata", s) for s in segs]


# --- modes -------------------------------------------------------------------


def scan_tree(
    denylist: list[re.Pattern] | None, host_hashes: set[str] | None = None
) -> list[Finding]:
    findings: list[Finding] = []
    allow = load_allowlist()
    rel_allowlist = ALLOWLIST_PATH.relative_to(REPO).as_posix()
    for path in tracked_files():
        if path == rel_allowlist:
            continue  # reviewed exceptions live here; they would self-flag
        full = REPO / path
        if not full.is_file():  # deleted-but-staged etc.
            continue
        data = full.read_bytes()
        ext = Path(path).suffix.lower()
        if ext in IMAGE_EXTS:
            findings.extend(scan_image(path, data))
        elif ext not in SKIP_TEXT_EXTS and b"\0" not in data[:8192]:
            findings.extend(scan_text(path, data, denylist, host_hashes))
    return [f for f in findings if f"{f.path}:{f.text}" not in allow]


def scan_history(
    denylist: list[re.Pattern] | None, host_hashes: set[str] | None = None
) -> list[Finding]:
    """Every unique blob ever committed, via one cat-file --batch stream."""
    seen: dict[str, str] = {}  # sha -> example path
    for line in _git("rev-list", "--objects", "--all").decode().splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and parts[1]:
            seen.setdefault(parts[0], parts[1])
    findings: list[Finding] = []
    proc = subprocess.Popen(
        ["git", "cat-file", "--batch"],
        cwd=REPO,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    assert proc.stdin and proc.stdout
    rel_allowlist = ALLOWLIST_PATH.relative_to(REPO).as_posix()

    def read_exact(n: int) -> bytes:
        # a pipe read() may return SHORT (observed on Windows) - loop to n bytes
        buf = bytearray()
        while len(buf) < n:
            chunk = proc.stdout.read(n - len(buf))
            if not chunk:
                raise EOFError("cat-file --batch stream ended early")
            buf += chunk
        return bytes(buf)

    for sha, path in seen.items():
        proc.stdin.write(f"{sha}\n".encode())
        proc.stdin.flush()
        header = proc.stdout.readline().decode("ascii", errors="replace").split()
        if len(header) < 3:  # "<sha> missing" - nothing further on the stream
            continue
        size = int(header[2])
        if header[1] != "blob":
            # trees/commits reach the batch stream too - MUST consume their
            # content + trailing LF or every later read is desynced (the bug
            # behind the first run's hang/UnicodeDecodeError).
            read_exact(size + 1)
            continue
        data = read_exact(size)
        read_exact(1)  # trailing LF
        # The allowlist file's own blobs legitimately contain the identifier
        # text they exempt - skip them by PATH, the SAME exemption scan_tree
        # makes for the working-tree copy (#573: without this the allowlist
        # blob self-flags forever in --history, poisoning the "history clean"
        # signal #558's AC exists to produce). Read the blob FIRST regardless,
        # or the batch stream desyncs on the next iteration.
        if path == rel_allowlist:
            continue
        label = f"{path}@{sha[:8]}"
        ext = Path(path).suffix.lower()
        if ext in IMAGE_EXTS:
            findings.extend(scan_image(label, data))
        elif ext not in SKIP_TEXT_EXTS and b"\0" not in data[:8192]:
            findings.extend(scan_text(label, data, denylist, host_hashes))
    proc.stdin.close()
    proc.wait()
    allow = load_allowlist()
    # history entries allowlist against their tree-path half (before the @sha)
    return [f for f in findings if f"{f.path.split('@')[0]}:{f.text}" not in allow]


def strip_files(paths: list[str]) -> int:
    rc = 0
    for p in paths:
        full = Path(p) if Path(p).is_absolute() else REPO / p
        data = full.read_bytes()
        ext = full.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            before, stripped = jpeg_meta_segments(data), jpeg_strip(data)
        elif ext == ".png":
            before, stripped = png_meta_chunks(data), png_strip(data)
        else:
            print(f"{p}: unsupported type for --strip (jpg/jpeg/png only)")
            rc = 1
            continue
        if not before:
            print(f"{p}: already clean")
            continue
        full.write_bytes(stripped)
        print(f"{p}: removed {', '.join(before)} ({len(data) - len(stripped)} bytes)")
    return rc


def deny_host(name: str) -> int:
    """Append a hostname's SHA-256 to the committed denylist. Idempotent; never
    echoes the name back (#865)."""
    digest = _hash_host(name)
    if digest in load_hostname_hashes():
        print("identifier-guard: already denied (no change).")
        return 0
    with HOSTNAME_HASHES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(digest + "\n")
    print(
        "identifier-guard: added 1 hostname hash to "
        "config/identifiers.denylist.sha256 - commit it."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--check", action="store_true", help="scan the tracked tree (default)"
    )
    ap.add_argument(
        "--history", action="store_true", help="scan every blob ever committed"
    )
    ap.add_argument(
        "--strip", nargs="+", metavar="FILE", help="strip metadata from images"
    )
    ap.add_argument(
        "--reveal", action="store_true", help="print full matches, not masked"
    )
    ap.add_argument(
        "--deny-host",
        metavar="HOSTNAME",
        help="append this hostname's SHA-256 to the committed denylist (#865)",
    )
    args = ap.parse_args(argv)

    if args.strip:
        return strip_files(args.strip)
    if args.deny_host:
        return deny_host(args.deny_host)

    denylist = load_denylist()
    host_hashes = load_hostname_hashes()
    where = "history" if args.history else "tree"
    findings = (
        scan_history(denylist, host_hashes)
        if args.history
        else scan_tree(denylist, host_hashes)
    )

    if denylist is None:
        print(
            "note: config/identifiers.local.txt absent - SSID/hostname denylist "
            "class skipped (regex classes still enforced)."
        )
    if not host_hashes:
        print(
            "note: config/identifiers.denylist.sha256 has no entries - hostname "
            "class inert (seed with --deny-host at go-public)."
        )
    if not findings:
        print(
            f"identifier-guard: {where} clean (MAC / USB-ID / image-metadata"
            f"{'' if denylist is None else ' / denylist'})."
        )
        return 0
    print(f"identifier-guard: {len(findings)} finding(s) in {where}:")
    for f in findings:
        print("  " + f.masked(args.reveal))
    print(
        "\nFix: remove the identifier (images: --strip FILE), or - for a "
        "verified-generic mention - allowlist it with a reason in "
        "tools/dx/identifier_guard_allowlist.txt (format: <path>:<matched text>)."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
