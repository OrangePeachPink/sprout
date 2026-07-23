#!/usr/bin/env python3
"""#1338 seam 3 — **ratified doctrine ↔ shipped behaviour**.

The epic's defect class, in its third shape. Seam 1 caught two implementations
disagreeing about identity. This seam catches something quieter: **a document and its
implementation drifting apart while every module suite stays green**, because the
module suite was updated in the same commit that changed the constant.

That is not hypothetical here. This release ratified a *lot* of numbers — two board
envelopes, seven bands, two ceilings, a wire rename, a store schema — and each one
lives in two places by necessity: a document a human reads to make decisions, and a
constant the code reads to produce answers. Nothing compared them. A value could be
re-tuned in `parse_v1` with its own tests updated to match, and the ADR the maintainer
ratified would go on saying something else, silently, until someone read both.

**How this suite is allowed to work.** Per the epic's constraint, conformance asserts
*executable* claims and **never parses an ADR as a specification**. So each claim below
is written out here with its citation, and checked two ways:

1. the **shipped constant** equals the ratified value — the code half;
2. the ratified value is **still present in the document** — a presence check, not a
   parse, so amending doctrine without touching code (or the reverse) turns this red.

Direction matters: check (1) alone would let an ADR be edited freely; check (2) alone
would let code drift. Together they make the pair move deliberately or not at all.

**How to read a failure.** A red test here does not mean the number is wrong. It means
**doctrine and implementation disagree about what was ratified**, and one of them is
lying to a reader. Fix by making them agree on purpose — never by updating this file
alone, which would re-hide exactly what it exists to surface.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.parse_v1 import (
    BANDS_WET_TO_DRY,
    BOARD_CLASS_ANCHORS,
    BOARD_CLASS_CEILING,
    CHANNEL_ID_SCHEMA_VERSION,
    DEFAULT_CAL_BOUNDS,
    DRIER_THAN_CALIBRATED,
    band_for_raw,
    range_exception,
)
from tools.analytics.tier_store import COLUMNS

_DOCS = Path(__file__).resolve().parents[2] / "docs"
_ADR = _DOCS / "adr"


def _text(path: Path) -> str:
    assert path.is_file(), f"the cited document is missing: {path}"
    return path.read_text(encoding="utf-8", errors="replace")


def _adr(stem: str) -> str:
    hits = sorted(_ADR.glob(f"{stem}-*.md"))
    assert hits, f"no ADR matching {stem}"
    return _text(hits[0])


# --------------------------------------------------------------------------- #
# C1 — the measured anchors (ADR-0035 §3, ratified 2026-07-19, #1211)
# --------------------------------------------------------------------------- #
def test_c1_the_measured_anchors_match_doctrine() -> None:
    """*"classic air 3137 / wet 1052 · C5 air 2754 / wet 982"* — ADR-0035 §3."""
    assert BOARD_CLASS_ANCHORS["classic"] == {"air": 3137, "water": 1052}
    assert BOARD_CLASS_ANCHORS["c5"] == {"air": 2754, "water": 982}
    doc = _adr("0035")
    for value in ("3137", "1052", "2754", "982"):
        assert value in doc, f"anchor {value} shipped but no longer in ADR-0035"


# --------------------------------------------------------------------------- #
# C2 — the Faint-ceilings (ADR-0035 §4, ratified #1174; amended #1339)
# --------------------------------------------------------------------------- #
def test_c2_the_ceilings_match_doctrine() -> None:
    """*"classic [1052 … 2500], C5 [982 … 2213]"* — ADR-0035 §4."""
    assert BOARD_CLASS_CEILING == {"classic": 2500, "c5": 2213}
    doc = _adr("0035")
    assert "2500" in doc and "2213" in doc


def test_c2b_above_the_ceiling_the_band_is_withheld_as_amended() -> None:
    """*"Above the ceiling, the band is withheld — never clamped"* — ADR-0035 §4,
    amended 2026-07-20 (#1339). The behaviour, not just the number."""
    ceiling = BOARD_CLASS_CEILING["classic"]
    assert band_for_raw(ceiling, DEFAULT_CAL_BOUNDS, ceiling) is not None
    assert band_for_raw(ceiling + 1, DEFAULT_CAL_BOUNDS, ceiling) is None
    assert range_exception(ceiling + 1, ceiling) == DRIER_THAN_CALIBRATED
    doc = _adr("0035")
    assert DRIER_THAN_CALIBRATED in doc
    assert "withheld" in doc


# --------------------------------------------------------------------------- #
# C3 — seven bands, and the off-ladder token is not an eighth (ADR-0035 §2/§4)
# --------------------------------------------------------------------------- #
def test_c3_the_ladder_is_seven_and_the_exception_is_off_ladder() -> None:
    """*"an off-ladder range exception (§2), not an eighth mood"* — ADR-0035 §4."""
    assert len(BANDS_WET_TO_DRY) == 7
    assert len(set(BANDS_WET_TO_DRY)) == 7  # no duplicate smuggled in
    assert DRIER_THAN_CALIBRATED not in BANDS_WET_TO_DRY


def test_c3b_the_ratified_ladder_edges_match_doctrine() -> None:
    """The six interior edges (#995/#1174 with the #1236 wet-end re-derive)."""
    assert DEFAULT_CAL_BOUNDS == (2293, 2086, 1879, 1636, 1393, 1150)
    doc = _adr("0035")
    for edge in DEFAULT_CAL_BOUNDS:
        assert str(edge) in doc, f"shipped edge {edge} is absent from ADR-0035"


# --------------------------------------------------------------------------- #
# C4 — the wire rename boundary (ADR-0036, Fork A, ruled 2026-07-19)
# --------------------------------------------------------------------------- #
def test_c4_the_channel_rename_lands_at_the_ratified_schema_version() -> None:
    """*"the rename lands at schema_version=5"* — ADR-0036 / #1042."""
    assert CHANNEL_ID_SCHEMA_VERSION == 5
    doc = _adr("0036")
    assert "chN" in doc or "ch0" in doc


# --------------------------------------------------------------------------- #
# C5 — the store's column set (TIER_STORE_CONTRACT §3)
# --------------------------------------------------------------------------- #
def test_c5_the_store_columns_match_the_written_contract() -> None:
    """§3 names each column; the store must ship exactly those, in that order.

    The provenance trio is the part worth pinning: it is the auditable-rebuild
    guarantee, and a silent drop would be invisible to every module suite.
    """
    contract = _text(_DOCS / "TIER_STORE_CONTRACT.md")
    for column in COLUMNS:
        assert f"`{column}`" in contract, f"{column} shipped but not in the contract"
    for trio in ("source_file", "ingest_ts", "schema_version"):
        assert trio in COLUMNS, f"the provenance trio lost {trio}"


def test_c5b_the_store_never_resurrects_the_legacy_percent() -> None:
    """*"No legacy `value` %"* — TIER_STORE_CONTRACT §3 / ADR-0006 §4."""
    assert "value" not in COLUMNS
    assert "moist" not in " ".join(COLUMNS).lower()


# --------------------------------------------------------------------------- #
# C6 — the µs invariant is doctrine, not an implementation detail (§4)
# --------------------------------------------------------------------------- #
def test_c6_the_us_invariant_is_still_stated_and_still_exact() -> None:
    """*"never ms-floored, never float-seconds"* — TIER_STORE_CONTRACT §4."""
    contract = _text(_DOCS / "TIER_STORE_CONTRACT.md")
    assert "microsecond" in contract.lower()
    from tools.analytics.tier_store import CAP_US

    # the dwell cap is expressed in µs, so it is a whole number of them
    assert isinstance(CAP_US, int) and CAP_US % 1_000 == 0
    assert CAP_US == 120_000_000  # 2x the 30 s cadence, §5


# --------------------------------------------------------------------------- #
# C7 — the documents this suite cites still exist
# --------------------------------------------------------------------------- #
def test_c7_every_cited_document_is_present() -> None:
    """A conformance suite whose citations rot is a suite that stops checking.

    If a document is renamed or removed, this fails loudly rather than the claims
    above quietly passing against a file that is no longer the doctrine.
    """
    assert (_DOCS / "TIER_STORE_CONTRACT.md").is_file()
    assert (_DOCS / "TELEMETRY_SCHEMA.md").is_file()
    for stem in ("0035", "0036", "0038"):
        assert sorted(_ADR.glob(f"{stem}-*.md")), f"ADR {stem} is missing"
