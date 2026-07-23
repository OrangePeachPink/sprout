"""#685 integrity panel = a bounded summary + a log-LOCATOR, not an unbounded
per-session dump. The old per-session table hit ~8k DOM rows under the #712 reset
storm and re-rendered every refresh. The panel must stay small regardless of
dataset size and hand the operator the pointers to dive into the raw data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.dashboard import SESSIONS_SHOWN, _locator, build_context
from tools.analytics.device_registry import Device, Registry
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id={sess}\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "millis_ms,sensor_id,raw_value,quality_flag,payload\n"
)
_T0 = datetime(2026, 7, 5, 0, 0, 0, tzinfo=timezone.utc)


def _row(dev: str, sess: str, i: int, raw: int, sensor: str = "s1") -> str:
    ts = _T0 + timedelta(seconds=i * 30)
    u = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    lo = ts.strftime("%Y-%m-%d %H:%M:%S.000")
    return (
        f"plants.soil,{u},{lo},{sess},{dev},{i * 30000},{sensor},{raw},OK,level=DRY\n"
    )


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(device_id="devA", board="esp32dev", label="A", channels={"s1": {}}),
            Device(device_id="devB", board="esp32dev", label="B", channels={"s1": {}}),
        ]
    )


def _write(tmp_path: Path, name: str, rows: str, sess0: str) -> str:
    p = tmp_path / name
    p.write_text(_HEADER.format(sess=sess0) + _COLS + rows, encoding="utf-8")
    return str(p)


def _reset_storm(tmp_path: Path):
    """40 one-sweep sessions on devA (the reset-storm shape) + a clean devB run."""
    a = "".join(_row("devA", f"s{n:03d}", n, 2400 + n) for n in range(40))
    b = "".join(_row("devB", "sB", 100 + n, 3000 + n) for n in range(10))
    ctx = build_context(
        parse_files(
            [_write(tmp_path, "a.csv", a, "s000"), _write(tmp_path, "b.csv", b, "sB")]
        ),
        registry=_reg(),
    )
    return ctx["integrity"]


def test_sessions_are_bounded_with_a_total(tmp_path: Path) -> None:
    ig = _reset_storm(tmp_path)
    assert ig["sessions_total"] == 41  # 40 devA + 1 devB
    assert len(ig["sessions"]) == SESSIONS_SHOWN  # DOM stays bounded (last N)
    assert len(ig["sessions"]) < ig["sessions_total"]  # the dump is not shipped whole


def test_locator_points_at_the_data(tmp_path: Path) -> None:
    ig = _reset_storm(tmp_path)
    loc = ig["locator"]
    assert set(loc["active_files"]) == {"a.csv", "b.csv"}  # the segment files
    assert loc["active_count"] == 2
    assert loc["log_dirs"]  # the directory to hand an agent
    assert "archive" in loc["archive_dir"]  # repo-relative archive pointer


# --------------------------------------------------------------------------- #
# #965: fleet-poll HTTP sources are their own labeled line, never file cosplay.
# --------------------------------------------------------------------------- #


def test_locator_splits_fleet_endpoints_from_files() -> None:
    loc = _locator(
        [
            "C:/Users/x/dev/plants/logs/a.csv",
            "http://sprout-y9d41p.local",
            "http://sprout-8gtt1h.local/telemetry",  # a path to strip
        ]
    )
    # the file stays a file; the two endpoints become one labeled, host-only line
    assert loc["active_files"] == ["a.csv"]
    assert loc["active_count"] == 1
    assert loc["fleet_sources"] == ["sprout-8gtt1h.local", "sprout-y9d41p.local"]


def test_locator_never_mints_an_http_pseudo_dir() -> None:
    # the exact #965 artifact: `http://…` split as a path produced a stray `http:/`
    loc = _locator(["http://sprout-y9d41p.local", "http://sprout-8gtt1h.local"])
    assert all("http:" not in d for d in loc["log_dirs"])
    # no endpoint leaks into the file lists
    assert loc["active_files"] == []
    assert not any(".local" in f for f in loc["active_files"])


def test_locator_files_only_has_no_fleet_line() -> None:
    loc = _locator(["C:/x/logs/a.csv", "C:/x/logs/b.csv"])
    assert loc["fleet_sources"] == []  # a tethered-only capture shows no fleet line


def test_per_device_row_counts(tmp_path: Path) -> None:
    ig = _reset_storm(tmp_path)
    counts = {d["device_id"]: d["n"] for d in ig["per_device"]}
    assert counts == {"devA": 40, "devB": 10}
    # sorted busiest-first so the operator reads the dominant source at a glance
    assert ig["per_device"][0]["device_id"] == "devA"


def test_summary_survives_and_totals_are_honest(tmp_path: Path) -> None:
    ig = _reset_storm(tmp_path)
    # the compact summary the maintainer wants to keep
    assert ig["total"] == 50  # 40 + 10 readings, unbounded-safe count
    assert ig["sweeps"] >= 41
    assert ig["span_start"] and ig["span_end"] and ig["duration"]
