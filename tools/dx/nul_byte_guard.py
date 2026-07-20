#!/usr/bin/env python3
"""#1327 tripwire — no raw NUL bytes in tracked text files.

A source file holding a raw ``0x00`` (a heredoc or generator that emitted a literal
NUL where ``\\0`` was meant) becomes **binary** to git and to every line-oriented tool.
``cal_resolver.c`` carried exactly two, in ``copy_str()``'s terminators, and the
compile still worked, the tests still passed, and CI stayed green for weeks.

What silently stopped working was the quality floor itself. ``grep``/``rg`` answer
``Binary file matches`` and emit **no lines**, so cspell, identifier-guard (PII),
identity-label-guard, voice-guard and clang-format-changed-lines each had nothing to
inspect — and each still printed a green line. ``.gitattributes`` ``text=auto eol=lf``
does not apply to binary files either, so the file escaped the repo's LF policy
(126 CRLF / 0 LF, against pure-LF siblings).

The generalization is the reason this exists: **a guard that skips a file without
announcing it is indistinguishable from a guard that passed it.** The PII sweep is the
sharpest case — a file that goes binary for an unrelated reason drops out of it with no
signal at all. That is a privacy hole, not a tidiness one.

A file is exempt only when the repo *declares* it binary — ``binary`` set, or ``text``
unset, in ``.gitattributes``. That is the cleaner key than a second allowlist: the repo
already states the intent there, in one place, and a new binary asset type is declared
once rather than twice.

Run standalone: ``python tools/dx/nul_byte_guard.py --check``
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_CHUNK = 65536


def _git(args: list[str], repo: Path) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True
    ).stdout


def tracked_files(repo: Path = _REPO) -> list[str]:
    """Every tracked path, repo-relative, in git's own encoding-safe -z form."""
    out = _git(["ls-files", "-z"], repo)
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def declared_binary(paths: list[str], repo: Path = _REPO) -> set[str]:
    """The subset the repo DECLARES binary via .gitattributes.

    ``binary`` is a macro for ``-diff -merge -text``, so both keys are asked: a path is
    exempt when ``binary`` is set or ``text`` is unset."""
    if not paths:
        return set()
    proc = subprocess.run(
        ["git", "check-attr", "-z", "--stdin", "binary", "text"],
        cwd=repo,
        input="\0".join(paths).encode("utf-8", "surrogateescape"),
        check=True,
        capture_output=True,
    )
    fields = proc.stdout.decode("utf-8", "surrogateescape").split("\0")
    exempt: set[str] = set()
    # -z output is a flat (path, attr, value) triple stream.
    for path, attr, value in zip(fields[0::3], fields[1::3], fields[2::3]):
        if (attr == "binary" and value == "set") or (
            attr == "text" and value == "unset"
        ):
            exempt.add(path)
    return exempt


def first_nul(path: Path) -> int | None:
    """Byte offset of the first NUL, or None. Chunked: stops at the first hit, so a
    large asset is never fully read just to fail."""
    offset = 0
    try:
        with path.open("rb") as fh:
            while chunk := fh.read(_CHUNK):
                found = chunk.find(b"\x00")
                if found != -1:
                    return offset + found
                offset += len(chunk)
    except OSError:
        return (
            None  # unreadable/vanished (e.g. a staged delete) — not this guard's call
        )
    return None


def scan(
    paths: list[str], exempt: set[str], repo: Path = _REPO
) -> list[tuple[str, int]]:
    """Every (path, byte-offset) where a non-exempt tracked file holds a NUL."""
    hits: list[tuple[str, int]] = []
    for rel in paths:
        if rel in exempt:
            continue
        full = repo / rel
        if not full.is_file():
            continue
        at = first_nul(full)
        if at is not None:
            hits.append((rel, at))
    return hits


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    paths = tracked_files()
    exempt = declared_binary(paths)

    if "--list-binary" in argv:
        print(f"{len(exempt)} tracked path(s) declared binary in .gitattributes:")
        for rel in sorted(exempt):
            print(f"  {rel}")
        return 0

    hits = scan(paths, exempt)
    if not hits:
        return 0

    print(
        "nul-byte-guard: raw NUL byte in a tracked text file — this file is BINARY to "
        "git and invisible to every text hook (#1327):",
        file=sys.stderr,
    )
    for rel, at in hits:
        print(f"  {rel}  first NUL at byte {at}", file=sys.stderr)
    print(
        "\nWhile it stays binary, cspell / identifier-guard (PII) /\n"
        "identity-label-guard / voice-guard / clang-format-changed-lines all\n"
        "silently inspect NOTHING here and still report green, and\n"
        ".gitattributes eol=lf does not apply. Replace the literal NUL with an\n"
        "escape (e.g. '\\0' in C), then re-run.\n"
        f"({len(exempt)} path(s) exempt — .gitattributes declares them binary; "
        "`--list-binary` lists them.)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
