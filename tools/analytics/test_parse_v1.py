"""Tests for parse_v1 — targeted assertions for the cal-bounds contract (#295).

The comprehensive golden round-trip suite (plants_logger + parse_v1) lives in #291.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import DEFAULT_CAL_BOUNDS, parse_file

# --------------------------------------------------------------------------- #
# fixtures — minimal column set; parse_v1 maps by name so a subset CSV is valid
# --------------------------------------------------------------------------- #

# Short column header + one data row — well under the 88-char line limit.
_COLS = "record_type,timestamp_utc,session_id,raw_value,quality_flag,payload"
_ROW = "plants.soil,2026-06-27T00:00:30.000Z,sess001,1312,OK,level=well watered;gpio=36"

_HEADER_WITH_BOUNDS = textwrap.dedent(f"""\
    # log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00
    # logger=plants_logger_0_4  schema_version=1
    # plants telemetry  schema_version=1
    # fw=0.7.0  git=test0000  run=test
    # session_id=sess001  cadence_ms=30000
    # cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]
    {_COLS}
    {_ROW}
""")

_HEADER_WITHOUT_BOUNDS = textwrap.dedent(f"""\
    # log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00
    # logger=plants_logger_0_4  schema_version=1
    # plants telemetry  schema_version=1
    # fw=0.7.0  git=test0000  run=test
    # session_id=sess002  cadence_ms=30000
    {_COLS}
    {_ROW.replace("sess001", "sess002")}
""")


@pytest.fixture()
def csv_with_bounds(tmp_path: Path) -> Path:
    p = tmp_path / "with_bounds.csv"
    p.write_text(_HEADER_WITH_BOUNDS, encoding="utf-8")
    return p


@pytest.fixture()
def csv_without_bounds(tmp_path: Path) -> Path:
    p = tmp_path / "without_bounds.csv"
    p.write_text(_HEADER_WITHOUT_BOUNDS, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# DEFAULT_CAL_BOUNDS sanity
# --------------------------------------------------------------------------- #


def test_default_cal_bounds_matches_firmware() -> None:
    """DEFAULT_CAL_BOUNDS must sibling the firmware classic default — the #995/#1174
    ratified in-soil ladder (ADR-0035, #1218 host-mirror contract)."""
    assert DEFAULT_CAL_BOUNDS == (2293, 2086, 1879, 1673, 1466, 1259)


# --------------------------------------------------------------------------- #
# header-derived bounds win
# --------------------------------------------------------------------------- #


def test_header_bounds_are_used_when_present(csv_with_bounds: Path) -> None:
    data = parse_file(csv_with_bounds)
    assert len(data.segments) == 1
    seg = data.segments[0]
    assert seg.cal_bounds == [3050, 2140, 1830, 1520, 1150, 1050]
    assert seg.cal_bounds_source == "header"


def test_header_bounds_win_over_default(csv_with_bounds: Path) -> None:
    """Header-derived bounds must be used even when they match the default."""
    data = parse_file(csv_with_bounds)
    assert data.segments[0].cal_bounds_source == "header"


# --------------------------------------------------------------------------- #
# missing header → flagged default
# --------------------------------------------------------------------------- #


def test_default_bounds_used_when_header_absent(csv_without_bounds: Path) -> None:
    data = parse_file(csv_without_bounds)
    seg = data.segments[0]
    assert seg.cal_bounds == list(DEFAULT_CAL_BOUNDS)
    assert seg.cal_bounds_source == "default"


def test_default_bounds_always_populated(csv_without_bounds: Path) -> None:
    """cal_bounds is never empty after parsing — always header or default."""
    data = parse_file(csv_without_bounds)
    assert data.segments[0].cal_bounds  # non-empty


def test_summary_flags_default_bounds(csv_without_bounds: Path) -> None:
    data = parse_file(csv_without_bounds)
    summary = data.summary()
    assert "fallback default" in summary


# --------------------------------------------------------------------------- #
# cadence_src banner field (#322 / Firmware #351)
# --------------------------------------------------------------------------- #


def _cadence_csv(tmp_path: Path, src: str) -> Path:
    body = textwrap.dedent(f"""\
        # session_id=sess001  cadence_ms=500  cadence_src={src}
        # cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]
        {_COLS}
        {_ROW}
    """)
    p = tmp_path / f"cad_{src}.csv"
    p.write_text(body, encoding="utf-8")
    return p


def test_cadence_src_temp(tmp_path: Path) -> None:
    # a session-only experiment override is parsed as cadence_src=temp (won't persist)
    seg = parse_file(_cadence_csv(tmp_path, "temp")).segments[0]
    assert seg.cadence_ms == 500
    assert seg.cadence_src == "temp"


def test_cadence_src_nvs(tmp_path: Path) -> None:
    seg = parse_file(_cadence_csv(tmp_path, "nvs")).segments[0]
    assert seg.cadence_src == "nvs"  # the deliberate persisted default


def test_cadence_src_absent_is_none(tmp_path: Path) -> None:
    # an older banner without the field -> None (no false claim about the source)
    body = textwrap.dedent(f"""\
        # session_id=sess001  cadence_ms=30000
        # cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]
        {_COLS}
        {_ROW}
    """)
    p = tmp_path / "cad_none.csv"
    p.write_text(body, encoding="utf-8")
    seg = parse_file(p).segments[0]
    assert seg.cadence_ms == 30000
    assert seg.cadence_src is None
