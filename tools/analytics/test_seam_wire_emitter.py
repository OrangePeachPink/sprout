#!/usr/bin/env python3
"""#1338 seam 2 (**emitter half**) — wire schema ↔ firmware emitter.

The sibling of `test_seam_wire_contract.py`, which pins the **host parser** to
`TELEMETRY_SCHEMA.md`. That file says plainly why it is only half a seam:

    a host-only check proves the parser reads the contract, never that the boards
    write it.

This is the other side. It asserts the **firmware emitter** — `firmware/lib/telemetry/`
and `firmware/include/config.h` — against the same document. With both halves in place
the seam is closed in the sense the epic means: two independent implementations pinned
to the same sentences, so they can no longer agree with each other while the document
between them says a third thing.

**Why Python, and why here.** The claims span a markdown contract and C sources; the C
suite cannot read the document, and the document cannot read the C. This lives beside
its three siblings in `tools/analytics/` for one reason — a conformance suite that is
split across two directories gets run as two suites, and half-run conformance is the
failure mode the epic exists to remove.

**Method, per the epic's constraint.** Executable claims with citations. The document
is checked by **presence**, never parsed as a grammar; the firmware is checked by
**source inspection**, never by rebuilding a parser for C. A claim fails when the
emitter and the contract disagree about what the wire means.

**How to read a failure.** Not "the firmware is broken." It means the shipped emitter
and the published contract disagree, and a reader of either is being misled. Fix by
deciding which is right and moving the other deliberately — never by relaxing the
assertion, which restores exactly the silence this seam exists to break.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = _ROOT / "docs" / "TELEMETRY_SCHEMA.md"
_CONFIG = _ROOT / "firmware" / "include" / "config.h"
_TELEM_C = _ROOT / "firmware" / "lib" / "telemetry" / "telemetry.c"


def _read(p: Path) -> str:
    assert p.is_file(), f"{p.name} is missing — one side of the seam is gone"
    return p.read_text(encoding="utf-8", errors="replace")


def _doc() -> str:
    return _read(_SCHEMA)


def _emitted_string_literals(src: str, func: str) -> set[str]:
    """Every string literal returned by one C function — the tokens that function
    can actually put on the wire. Scoped to the function so an unrelated literal
    elsewhere in the file cannot make a claim pass."""
    start = src.index(func)
    depth, i, body_start = 0, start, None
    while i < len(src):
        if src[i] == "{":
            depth += 1
            if body_start is None:
                body_start = i
        elif src[i] == "}":
            depth -= 1
            if depth == 0 and body_start is not None:
                break
        i += 1
    body = src[body_start : i + 1]
    return set(re.findall(r'return\s+"([^"]+)"', body))


# --- E1: the schema version the firmware stamps is the one the doc calls current ---


def test_e1_firmware_schema_version_is_the_documented_current_version() -> None:
    """The emitter stamps `PLANTS_SCHEMA_VERSION` on every row. If the document has
    moved to a version the firmware does not emit, every shipped row is labelled
    under a contract nobody is reading it by."""
    m = re.search(r"PLANTS_SCHEMA_VERSION\s*=\s*(\d+)", _read(_CONFIG))
    assert m, "config.h no longer defines PLANTS_SCHEMA_VERSION"
    fw_version = int(m.group(1))
    doc = _doc()
    assert f"v{fw_version}" in doc or f"schema_version={fw_version}" in doc, (
        f"the firmware emits schema v{fw_version}, which the schema doc never mentions"
    )


def test_e1b_the_channel_rename_landed_at_the_documented_version() -> None:
    """ADR-0036 ruled the `sensor_id` rename is a schema BOUNDARY, and the document
    names the version. The emitter must carry `chN` at that version and not before —
    a board emitting the new token under an old version number is precisely the
    never-stitch violation the boundary exists to prevent."""
    cfg = _read(_CONFIG)
    m = re.search(r"PLANTS_SCHEMA_VERSION\s*=\s*(\d+)", cfg)
    fw_version = int(m.group(1))
    names = re.search(r"SENSOR_NAMES\[NUM_SENSORS\]\s*=\s*\{([^}]*)\}", cfg)
    assert names, "config.h no longer defines SENSOR_NAMES"
    tokens = re.findall(r'"([^"]+)"', names.group(1))

    doc = _doc()
    assert "ch0" in doc, "the doc does not document the chN channel tokens"
    if fw_version >= 5:
        assert all(t.startswith("ch") for t in tokens), (
            f"schema v{fw_version} must emit channel tokens, got {tokens}"
        )
    else:
        assert not any(t.startswith("ch") for t in tokens), (
            f"chN emitted under v{fw_version} — the rename must ride its own version"
        )


# --- E2: closed vocabularies — the emitter cannot invent a token ------------------


def test_e2_every_quality_flag_the_emitter_can_return_is_documented() -> None:
    """`quality_flag` is a CLOSED enum: the host drops an unknown value rather than
    passing it through, so a token the firmware invents does not degrade — it
    silently deletes the row's quality signal."""
    emitted = _emitted_string_literals(_read(_TELEM_C), "telemetry_quality_flag")
    doc = _doc()
    undocumented = sorted(t for t in emitted if t not in doc)
    assert not undocumented, (
        f"the emitter can return {undocumented}, which TELEMETRY_SCHEMA.md does not "
        "document — the host will drop it"
    )


def test_e2b_every_fault_reason_the_emitter_can_return_is_documented() -> None:
    """`fault=` is an OPEN payload token by design, but the shipped set is still
    documented. An undocumented reason is not a parse failure — it is a reason
    nobody downstream can interpret, which is worse than silence because it looks
    like information."""
    emitted = _emitted_string_literals(_read(_TELEM_C), "telemetry_fault_reason")
    doc = _doc()
    undocumented = sorted(t for t in emitted if t not in doc)
    assert not undocumented, (
        f"the emitter can return fault={undocumented}, undocumented in "
        "TELEMETRY_SCHEMA.md — a reason no reader can interpret"
    )


def test_e2c_the_record_type_matches_the_documented_namespace() -> None:
    """The namespaced `record_type` is the join key shared with the companion
    project. A drift here does not fail loudly — it produces two datasets that
    never join and no error to explain why."""
    m = re.search(r'RECORD_TYPE_SOIL\s*=\s*"([^"]+)"', _read(_CONFIG))
    assert m, "config.h no longer defines RECORD_TYPE_SOIL"
    rt = m.group(1)
    assert rt in _doc(), (
        f"the emitter stamps record_type={rt}, undocumented in the schema"
    )


# --- E3: the document actually says these things (guards against a moved doc) ----


def test_e3_the_contract_document_still_carries_the_cited_sections() -> None:
    """Each claim above reads the document by presence. If the document is
    restructured so those anchors vanish, the assertions would pass vacuously —
    which is the failure mode a conformance suite must never have. This is the
    tripwire for that."""
    doc = _doc()
    for anchor in ("quality_flag", "record_type", "sensor_id", "schema"):
        assert anchor in doc, (
            f"TELEMETRY_SCHEMA.md no longer mentions {anchor!r} — the claims above "
            "would start passing vacuously"
        )


def test_e3b_the_emitter_sources_are_where_the_claims_say_they_are() -> None:
    """Same tripwire, firmware side. If telemetry.c moves or the functions are
    renamed, the extraction above would raise rather than silently pass — but this
    states it as a claim so the failure names the cause."""
    src = _read(_TELEM_C)
    for func in ("telemetry_quality_flag", "telemetry_fault_reason"):
        assert func in src, (
            f"{func} is gone from telemetry.c — the seam claims are stale"
        )
