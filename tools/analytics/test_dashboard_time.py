"""Local-time-first display labels on the dashboard (#328 slice 2, #840).

build_context() adds *_display fields for the human-facing header labels + a
local-first start_axis for the chart x-axis. Since #840 these render in the host's
LOCAL zone (abbreviated, e.g. CDT) with **no UTC secondary** — UTC is not a human
clock (#720). The machine *_local fields stay untouched (last_local is
JS-Date-parsed for freshness).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from tools.analytics.dashboard import build_context
from tools.analytics.parse_v1 import parse_files
from tools.analytics.timefmt import local_first_system

# the two soil rows are stamped 18:14:30Z (start) and 18:15:00Z (last)
_START_UTC = datetime(2026, 6, 28, 18, 14, 30, tzinfo=timezone.utc)
_LAST_UTC = datetime(2026, 6, 28, 18, 15, 0, tzinfo=timezone.utc)

_HEADER = (
    "# fw=0.7.0  git=test123  run=timetest\n"
    "# device_id=plants_esp32_test  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(utc: str, local: str, sid: str, raw: int) -> str:
    return (
        f"plants.soil,{utc},{local},sess1,{sid},{raw},OK,level=well watered;gpio=36\n"
    )


def _ctx(tmp_path: Path):
    log = tmp_path / "t.csv"
    # timestamp_local is UTC-5 (Chicago summer): 18:14:30Z -> 13:14:30 local.
    log.write_text(
        _HEADER
        + _COLS
        + _row("2026-06-28T18:14:30.000Z", "2026-06-28T13:14:30.000", "s1", 1500)
        + _row("2026-06-28T18:14:30.000Z", "2026-06-28T13:14:30.000", "s2", 1550)
        + _row("2026-06-28T18:15:00.000Z", "2026-06-28T13:15:00.000", "s1", 1505)
        + _row("2026-06-28T18:15:00.000Z", "2026-06-28T13:15:00.000", "s2", 1555),
        encoding="utf-8",
    )
    return build_context(parse_files([str(log)]))


def test_start_display_is_local_first_no_utc(tmp_path: Path) -> None:
    # #840: host-local zone, NO `· UTC …Z` secondary, NO bare-UTC time. Compared
    # against local_first_system so the test is host-tz-agnostic (CI vs CDT).
    m = _ctx(tmp_path)["meta"]
    assert m["start_display"] == local_first_system(
        _START_UTC, seconds=True, utc_secondary=False
    )
    assert m["last_display"] == local_first_system(
        _LAST_UTC, seconds=True, utc_secondary=False
    )
    for f in (m["start_display"], m["last_display"]):
        assert "· UTC" not in f and "Z" not in f  # no UTC clutter


def test_machine_local_fields_are_unchanged(tmp_path: Path) -> None:
    # The chart anchor + JS Date parse rely on the bare local string — must not gain
    # the zone/UTC suffix, or `new Date(...)` and the axis label break.
    m = _ctx(tmp_path)["meta"]
    assert m["start_local"] == "2026-06-28 13:14:30"
    assert m["last_local"] == "2026-06-28 13:15:00"


def test_generated_display_is_local_first_no_utc(tmp_path: Path) -> None:
    # Host-tz dependent, so assert shape not value: "<date> <time> <zone>", no UTC.
    m = _ctx(tmp_path)["meta"]
    assert "· UTC" not in m["generated_display"]
    assert not m["generated_display"].rstrip().endswith("Z")
    assert re.match(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \S+$", m["generated_display"]
    )


def test_chart_axis_anchor_is_local_first_no_utc(tmp_path: Path) -> None:
    # The chart x-axis anchor shows local + zone (#328/#840), no UTC anywhere.
    traj = _ctx(tmp_path)["trajectory"]
    assert traj["start_axis"] == local_first_system(
        _START_UTC, seconds=True, utc_secondary=False
    )
    assert "· UTC" not in traj["start_axis"] and "Z" not in traj["start_axis"]
    assert traj["start_local"] == "2026-06-28 13:14:30"  # bare machine anchor kept
