"""Local-time-first display labels on the dashboard (#328 slice 2).

build_context() adds *_display fields (local + explicit zone + UTC secondary) for
the human-facing header labels, while the machine *_local fields stay untouched —
start_local anchors the chart axis and last_local is JS-Date-parsed for freshness.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from parse_v1 import parse_files

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
    return build_context(parse_files([str(log)]))["meta"]


def test_start_display_is_local_first_with_utc_secondary(tmp_path: Path) -> None:
    m = _ctx(tmp_path)
    assert m["start_display"] == "2026-06-28 13:14:30 UTC-05:00 · UTC 18:14:30Z"
    assert m["last_display"] == "2026-06-28 13:15:00 UTC-05:00 · UTC 18:15:00Z"


def test_machine_local_fields_are_unchanged(tmp_path: Path) -> None:
    # The chart anchor + JS Date parse rely on the bare local string — must not gain
    # the zone/UTC suffix, or `new Date(...)` and the axis label break.
    m = _ctx(tmp_path)
    assert m["start_local"] == "2026-06-28 13:14:30"
    assert m["last_local"] == "2026-06-28 13:15:00"


def test_generated_display_is_local_first_shaped(tmp_path: Path) -> None:
    # Host-tz dependent, so assert shape not value: local first, UTC secondary.
    m = _ctx(tmp_path)
    assert " · UTC " in m["generated_display"]
    assert m["generated_display"].rstrip().endswith("Z")
