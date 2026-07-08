"""#840 — header + date fields render local-time-first with NO UTC clutter.

The live header showed "… UTC-05:00 · UTC …Z" (UTC twice) because the verbose OS
zone name fell back to the offset and the `· UTC …Z` secondary was always on. This
pins: verbose OS zones abbreviate (Central Daylight Time -> CDT), the UTC secondary
is droppable, and the dashboard's human display fields carry no UTC.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files
from timefmt import _abbrev_zone, local_first, local_first_system

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id=s1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


# --------------------------------------------------------------------------- #
# the zone abbreviation (the fix for "UTC-05:00" reading as UTC)
# --------------------------------------------------------------------------- #
def test_verbose_os_zone_abbreviates_to_initials() -> None:
    assert _abbrev_zone("Central Daylight Time") == "CDT"
    assert _abbrev_zone("Eastern Standard Time") == "EST"
    assert _abbrev_zone("Pacific Daylight Time") == "PDT"
    # not a standard "<Region> Standard|Daylight Time" -> no fabricated abbrev
    assert _abbrev_zone("Coordinated Universal Time") == ""
    assert _abbrev_zone("CDT") == ""


# --------------------------------------------------------------------------- #
# the UTC secondary is droppable
# --------------------------------------------------------------------------- #
def test_utc_secondary_dropped() -> None:
    ts = datetime(2026, 7, 8, 0, 47, 59, tzinfo=timezone.utc)
    with_sec = local_first(ts, tz_offset_hours=-5, seconds=True, utc_secondary=True)
    no_sec = local_first(ts, tz_offset_hours=-5, seconds=True, utc_secondary=False)
    assert "· UTC" in with_sec  # default keeps it (back-compat)
    assert "· UTC" not in no_sec and "Z" not in no_sec
    assert no_sec.startswith("2026-07-07 19:47:59")  # local time, clean


def test_system_local_first_is_clean_local() -> None:
    ts = datetime(2026, 7, 8, 0, 47, 59, tzinfo=timezone.utc)
    s = local_first_system(ts, seconds=True, utc_secondary=False)
    assert "· UTC" not in s  # no secondary
    # host tz here is Central Daylight Time -> abbreviates to CDT, never "UTC-…"
    # (on a differently-zoned host it's that host's abbrev/offset, still no `· UTC`)
    assert "Central Daylight Time" not in s  # the verbose OS name never leaks


# --------------------------------------------------------------------------- #
# the dashboard's header/date fields carry no UTC
# --------------------------------------------------------------------------- #
def test_meta_display_fields_have_no_utc(tmp_path: Path) -> None:
    ts = "2026-07-08T00:47:59.000Z"
    row = f"plants.soil,{ts},2026-07-07 19:47:59.000,s1,dev1,s1,2400,OK,level=DRY\n"
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + row, encoding="utf-8")
    reg = Registry(devices=[Device("dev1", "esp32", "A", channels={"s1": {}})])
    m = build_context(parse_files([str(p)]), registry=reg)["meta"]
    for field in ("start_display", "last_display", "generated_display"):
        assert "· UTC" not in m[field], (
            f"{field} still shows a UTC secondary: {m[field]}"
        )
        assert "Z" not in m[field], f"{field} still shows a UTC time: {m[field]}"
