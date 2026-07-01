"""Tests for the bench-provenance panel's latest-segment selection (#496).

A live incident: the provenance card showed a stale firmware identity from a
legacy-converted capture instead of the current live session, because
``segments[-1]`` is file-glob order (alphabetical filename), not chronological
order. This covers the fix: pick by each segment's real ``log_start_utc``
(host-timestamped, absent on legacy conversions) instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from parse_v1 import parse_files

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(ts: str, sid: str, raw: int, session: str) -> str:
    local = ts.replace("Z", "")
    return f"plants.soil,{ts},{local},{session},{sid},{raw},OK,level=OK;gpio=36\n"


def _live_header(fw: str, git: str, device_id: str, log_start_utc: str) -> str:
    # Matches plants_logger.py / experiment_capture.py's real header shape.
    return (
        f"# log_start_utc={log_start_utc}  tz_offset=-05:00\n"
        f"# fw={fw}  git={git}  run=liverun  device_id={device_id}  schema_version=1\n"
        "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
    )


def _legacy_header(fw: str, device_id: str) -> str:
    # Matches legacy_log.py's real header shape - NO log_start_utc key at all.
    return (
        f"# fw={fw}  device_id={device_id}  schema_version=1  logger=legacy-convert\n"
        "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
    )


def test_picks_the_live_segment_even_when_legacy_file_sorts_last(
    tmp_path: Path,
) -> None:
    # Names chosen so glob-sort (alphabetical) puts the LEGACY file last - the exact
    # #496 incident: "plants_..." legacy file sorting after an "aaa_..." live one.
    live = tmp_path / "aaa_live.csv"
    legacy = tmp_path / "zzz_legacy.csv"
    live.write_text(
        _live_header("0.8.0", "156ca68", "Sprout ESP32", "2026-07-01T16:50:00.000Z")
        + _COLS
        + _row("2026-07-01T16:55:00.000Z", "s1", 1500, "live1"),
        encoding="utf-8",
    )
    legacy.write_text(
        _legacy_header("0.3.2", "plants_esp32_f4e9d4")
        + _COLS
        + _row("2026-06-25T00:00:00.000Z", "s1", 1400, "legacy-x"),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(live), str(legacy)]))
    dev = ctx["provenance"]["device"]
    assert dev["device_id"] == "Sprout ESP32"  # the LIVE segment, not the legacy one
    assert dev["fw"] == "0.8.0" and dev["fw_git"] == "156ca68"
    assert dev["legacy_converted"] is False


def test_legacy_only_view_flags_itself_honestly(tmp_path: Path) -> None:
    legacy = tmp_path / "only_legacy.csv"
    legacy.write_text(
        _legacy_header("0.3.2", "plants_esp32_f4e9d4")
        + _COLS
        + _row("2026-06-25T00:00:00.000Z", "s1", 1400, "legacy-x"),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(legacy)]))
    dev = ctx["provenance"]["device"]
    assert dev["device_id"] == "plants_esp32_f4e9d4"  # true fact about that capture
    assert dev["legacy_converted"] is True  # but honestly labelled as not-live
