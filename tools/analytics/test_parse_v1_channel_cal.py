"""Tests for per-channel cal-bounds provenance parsing (#404, PROPOSED format).

Extends #295's shared cal-bounds line with an optional per-channel override. This
covers the honest fallback chain (per-channel -> shared header -> compiled default)
and the ADR-0022 confidence-vocabulary guard.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools.analytics.parse_v1 import (
    DEFAULT_CAL_BOUNDS,
    cal_bounds_for_channel,
    parse_file,
)

_COLS = "record_type,timestamp_utc,session_id,raw_value,quality_flag,payload"
_ROW = "plants.soil,2026-06-27T00:00:30.000Z,sess001,1312,OK,level=well watered;gpio=36"

_HEADER_ONE_CHANNEL = textwrap.dedent(f"""\
    # log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00
    # logger=plants_logger_0_4  schema_version=1
    # fw=0.7.0  git=test0000  run=test
    # session_id=sess001  cadence_ms=30000
    # cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]
    # cal_ch s1: bounds=3100,2200,1900,1600,1200,1080 src=bench confidence=calibrated
    {_COLS}
    {_ROW}
""")

_HEADER_UNKNOWN_CONFIDENCE = textwrap.dedent(f"""\
    # log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00
    # logger=plants_logger_0_4  schema_version=1
    # session_id=sess003  cadence_ms=30000
    # cal_ch s2: bounds=3000,2100,1800,1500,1100,1000 src=bench confidence=definitely
    {_COLS}
    {_ROW.replace("sess001", "sess003")}
""")

_HEADER_NO_CAL_AT_ALL = textwrap.dedent(f"""\
    # log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00
    # logger=plants_logger_0_4  schema_version=1
    # session_id=sess004  cadence_ms=30000
    {_COLS}
    {_ROW.replace("sess001", "sess004")}
""")


@pytest.fixture()
def csv_one_channel(tmp_path: Path) -> Path:
    p = tmp_path / "one_channel.csv"
    p.write_text(_HEADER_ONE_CHANNEL, encoding="utf-8")
    return p


@pytest.fixture()
def csv_unknown_confidence(tmp_path: Path) -> Path:
    p = tmp_path / "unknown_confidence.csv"
    p.write_text(_HEADER_UNKNOWN_CONFIDENCE, encoding="utf-8")
    return p


@pytest.fixture()
def csv_no_cal(tmp_path: Path) -> Path:
    p = tmp_path / "no_cal.csv"
    p.write_text(_HEADER_NO_CAL_AT_ALL, encoding="utf-8")
    return p


def test_per_channel_line_parses(csv_one_channel: Path) -> None:
    data = parse_file(csv_one_channel)
    seg = data.segments[0]
    ch = seg.per_channel_cal["s1"]
    assert ch.bounds == [3100, 2200, 1900, 1600, 1200, 1080]
    assert ch.src == "bench"
    assert ch.confidence == "calibrated"
    assert ch.scope == "channel"  # unset in the fixture -> the honest default


def test_channel_with_override_wins_over_shared(csv_one_channel: Path) -> None:
    data = parse_file(csv_one_channel)
    bounds, confidence = cal_bounds_for_channel(data.segments[0], "s1")
    assert bounds == [3100, 2200, 1900, 1600, 1200, 1080]
    assert confidence == "calibrated"


def test_channel_without_override_falls_back_to_shared_header(
    csv_one_channel: Path,
) -> None:
    # s2 has no cal_ch line in this header; it falls back to the shared bounds.
    data = parse_file(csv_one_channel)
    bounds, confidence = cal_bounds_for_channel(data.segments[0], "s2")
    assert bounds == [3050, 2140, 1830, 1520, 1150, 1050]
    assert confidence == "provisional"  # the shared line carries no confidence claim


def test_no_cal_anywhere_falls_back_to_compiled_default(csv_no_cal: Path) -> None:
    data = parse_file(csv_no_cal)
    bounds, confidence = cal_bounds_for_channel(data.segments[0], "s1")
    assert bounds == list(DEFAULT_CAL_BOUNDS)
    assert confidence == "provisional"


def test_unrecognized_confidence_degrades_to_provisional(
    csv_unknown_confidence: Path,
) -> None:
    # ADR-0022's vocabulary is provisional|calibrated|corroborated - "definitely"
    # (not in that set) must never be trusted at face value.
    data = parse_file(csv_unknown_confidence)
    ch = data.segments[0].per_channel_cal["s2"]
    assert ch.confidence == "provisional"


def test_malformed_cal_ch_line_is_skipped_not_raised(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text(
        textwrap.dedent(f"""\
            # log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00
            # session_id=sess005
            # cal_ch no-colon-here
            {_COLS}
            {_ROW.replace("sess001", "sess005")}
        """),
        encoding="utf-8",
    )
    data = parse_file(bad)  # must not raise
    assert data.segments[0].per_channel_cal == {}
