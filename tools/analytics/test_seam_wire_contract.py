#!/usr/bin/env python3
"""#1338 seam 2 (host half) — **wire schema ↔ host parser**.

The middle seam of the epic's three. `TELEMETRY_SCHEMA.md` is the contract two
independent implementations are built against: firmware emits rows to it, and
`parse_v1` reads rows by it. Each side has strong tests **against itself** —
`test_parse_v4.py` proves the parser handles what it expects, and the firmware suite
proves the emitter emits what it intends — and that is exactly the configuration where
both stay green while the *document between them* says a third thing.

**This file is the host half only.** It asserts the parser against the written
contract. The emitter half is 🔧 Firmware's and belongs beside their build, because a
seam is only closed when both sides are pinned to the same sentence; a host-only check
proves the parser reads the contract, never that the boards write it. Stated so the
seam is not mistaken for complete.

**Method, per the epic's constraint.** Executable claims with citations — the document
is checked by *presence*, never parsed as a grammar. A claim fails here when the parser
and the contract disagree about what the wire means, which is the moment a reader of
either one is being misled.

**How to read a failure.** Not "the parser is broken". It means the shipped parser and
the published contract disagree, and someone downstream is trusting the wrong one. Fix
by deciding which is right and moving the other deliberately — never by relaxing the
assertion, which restores the silence this seam exists to break.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.parse_v1 import (
    CANONICAL_COLUMNS,
    CHANNEL_ID_SCHEMA_VERSION,
    STABLE_ID_SCHEMA_VERSION,
    parse_file,
)

_SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "TELEMETRY_SCHEMA.md"

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _doc() -> str:
    assert _SCHEMA.is_file(), "TELEMETRY_SCHEMA.md is missing — the contract is gone"
    return _SCHEMA.read_text(encoding="utf-8", errors="replace")


def _row(
    tmp: Path, *, version: int, sensor: str, flag: str = "OK", payload: str = "level=OK"
) -> Path:
    p = tmp / f"seam_v{version}.csv"
    p.write_text(
        f"# schema_version={version}  fw=0.8.0  git=t  device_id=dev1  session_id=s1\n"
        + _COLS
        + "plants.soil,2026-07-20T00:00:00.000000Z,x,s1,dev1,"
        + f"{sensor},1500,{flag},{payload}\n",
        encoding="utf-8",
    )
    return p


# --------------------------------------------------------------------------- #
# W1 — the column vocabulary is the same on both sides (§2)
# --------------------------------------------------------------------------- #
def test_w1_every_parsed_column_is_a_documented_column() -> None:
    """§2's table is the column contract; the parser's fallback order must not
    contain a column the document has never heard of."""
    doc = _doc()
    for column in CANONICAL_COLUMNS:
        assert f"`{column}`" in doc, f"parser knows {column!r}; the contract does not"


def test_w1b_the_documented_count_is_the_parsers_count() -> None:
    # §2 numbers its rows 1..23; a silent add on either side desynchronises them
    assert len(CANONICAL_COLUMNS) == 23
    assert "| 23 |" in _doc()


# --------------------------------------------------------------------------- #
# W2 — the two schema_version boundaries mean what the document says (§2 f6/f11)
# --------------------------------------------------------------------------- #
def test_w2_the_stable_id_boundary_is_v3(tmp_path: Path) -> None:
    """*"Set at `schema_version=3`"* — §2 field 6 (ADR-0027)."""
    assert STABLE_ID_SCHEMA_VERSION == 3
    assert "schema_version=3" in _doc() or "`schema_version=3`" in _doc()
    v3 = parse_file(str(_row(tmp_path, version=3, sensor="s1"))).readings[0]
    v2 = parse_file(str(_row(tmp_path, version=2, sensor="s1"))).readings[0]
    assert v3.device_id_is_stable_id is True
    assert v2.device_id_is_stable_id is False


def test_w2b_the_channel_boundary_is_v5(tmp_path: Path) -> None:
    """*"the board channel at `schema_version>=5`"* — §2 field 11 (ADR-0036)."""
    assert CHANNEL_ID_SCHEMA_VERSION == 5
    doc = _doc()
    assert "schema_version>=5" in doc or "schema_version=5" in doc
    v5 = parse_file(str(_row(tmp_path, version=5, sensor="ch0"))).readings[0]
    v4 = parse_file(str(_row(tmp_path, version=4, sensor="s3"))).readings[0]
    assert v5.sensor_id_is_channel is True
    assert v4.sensor_id_is_channel is False
    # and the historical row keeps its token verbatim — never rewritten (ADR-0036 §4)
    assert v4.sensor_id == "s3"


# --------------------------------------------------------------------------- #
# W3 — the quality enum, and the #1152 fault tokens (§4)
# --------------------------------------------------------------------------- #
def test_w3_the_documented_quality_values_survive_the_parser(tmp_path: Path) -> None:
    """§4's shared enum. The parser carries the flag verbatim — a normalisation here
    would silently reclassify a fault, which is the trust signal itself."""
    doc = _doc()
    for flag in ("OK", "SUSPECT", "NO_SIGNAL", "SENSOR_FAULT", "SATURATED"):
        assert flag in doc, f"{flag} is not in the contract"
        r = parse_file(str(_row(tmp_path, version=4, sensor="s1", flag=flag))).readings[
            0
        ]
        assert r.quality_flag == flag, "quality_flag must be carried verbatim"


def test_w3b_the_fault_reason_tokens_are_documented_and_parsed(tmp_path: Path) -> None:
    """*"reason payload `fault=open_adc`"* / *"`fault=rate_spike`"* — §4 (#1152)."""
    doc = _doc()
    for token in ("open_adc", "rate_spike"):
        assert token in doc, f"{token} is emitted-by-contract but undocumented"
    r = parse_file(
        str(
            _row(
                tmp_path,
                version=4,
                sensor="s1",
                flag="SENSOR_FAULT",
                payload="level=DRY;fault=open_adc",
            )
        )
    ).readings[0]
    assert (r.payload or {}).get("fault") == "open_adc"


# --------------------------------------------------------------------------- #
# W4 — raw is authoritative and the legacy % never becomes truth (§2 f15)
# --------------------------------------------------------------------------- #
def test_w4_raw_is_preserved_and_value_is_not_promoted(tmp_path: Path) -> None:
    """§2 f15: raw_value + band are authoritative; never an uncalibrated %."""
    doc = _doc()
    assert "raw_value" in doc and "authoritative" in doc
    r = parse_file(str(_row(tmp_path, version=4, sensor="s1"))).readings[0]
    assert r.raw_value == 1500  # exactly as the wire said, untransformed


# --------------------------------------------------------------------------- #
# W5 — the payload is `;`-separated k=v (§6)
# --------------------------------------------------------------------------- #
def test_w5_the_payload_grammar_matches_the_contract(tmp_path: Path) -> None:
    """*"`;`-sep `k=v`"* — §2 field 22 / §6."""
    r = parse_file(
        str(
            _row(
                tmp_path,
                version=4,
                sensor="s1",
                payload="level=OK;role=disp;spread=50;gpio=36",
            )
        )
    ).readings[0]
    assert (r.payload or {}).get("gpio") == "36"
    assert (r.payload or {}).get("role") == "disp"


# --------------------------------------------------------------------------- #
# W6 — the seam's own honesty: the contract exists and names its own version
# --------------------------------------------------------------------------- #
def test_w6_the_contract_document_is_present_and_cited_correctly() -> None:
    doc = _doc()
    assert "schema_version" in doc
    assert "plants.soil" in doc  # the record_type this whole seam is about
