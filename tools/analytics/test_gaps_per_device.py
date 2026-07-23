"""#699 per-device gap / continuity surfacing for the WiFi fleet.

The gap machinery (#373/#374) was built for the single serial monitor log. v0.7.0
runs a WiFi-polled fleet where a board can drop WiFi for a stretch and come back.
These tests pin that:
  - a per-device dropout is detected PER DEVICE (not only in the aggregate), each
    board judged against its OWN cadence;
  - the trajectory line BREAKS across a real gap (a null-y point is inserted), so
    the chart never interpolates a straight line over a WiFi hole;
  - continuity metrics (coverage / longest / last gap) surface per device;
  - raw rows are untouched.

Honest-data law: gaps are surfaced, not smoothed (#373/#374).
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context
from tools.analytics.device_registry import Device, Registry
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.8.0  git=abc  session_id={sess}\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "millis_ms,sensor_id,raw_value,quality_flag,payload\n"
)


def _row(dev: str, sess: str, minute: int, raw: int, sensor: str = "s1") -> str:
    # a poll every whole minute; `minute` is minutes-since-midnight UTC. millis_ms
    # is distinct per poll so sweeps() splits ticks correctly (the real fleet log
    # carries it as a column, one value per poll cycle).
    hh, mm = divmod(minute, 60)
    ts = f"2026-07-05T{hh:02d}:{mm:02d}:00.000Z"
    return (
        f"plants.soil,{ts},{ts[:-1]},{sess},{dev},{minute * 60000},{sensor},"
        f"{raw},OK,transport=wifi_poll;level=DRY\n"
    )


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="aaa111",
                board="esp32dev",
                label="A",
                channels={"s1": {"plant_id": "p01", "plant_name": "fern"}},
            ),
            Device(
                device_id="bbb222",
                board="esp32dev",
                label="B",
                channels={"s1": {"plant_id": "p02", "plant_name": "pothos"}},
            ),
        ]
    )


def _write(tmp_path: Path, sess: str, rows: str) -> str:
    p = tmp_path / f"{sess}.csv"
    p.write_text(_HEADER.format(sess=sess) + _COLS + rows, encoding="utf-8")
    return str(p)


def _fleet(tmp_path: Path) -> dict:
    """Device A polls cleanly every minute for 30 min; device B polls every minute
    for 10 min, then drops WiFi for 25 min, then returns for 10 min."""
    a = "".join(_row("aaa111", "sA", m, 2400 + m) for m in range(0, 31))
    b_before = "".join(_row("bbb222", "sB", m, 3000 - m) for m in range(0, 11))
    b_after = "".join(_row("bbb222", "sB", m, 2600 - (m - 35)) for m in range(35, 46))
    ctx = build_context(
        parse_files(
            [_write(tmp_path, "sA", a), _write(tmp_path, "sB", b_before + b_after)]
        ),
        registry=_reg(),
    )
    return ctx


def test_per_device_gap_detected_only_on_the_device_that_dropped(
    tmp_path: Path,
) -> None:
    ctx = _fleet(tmp_path)
    gbd = ctx["gaps_by_device"]
    # device B dropped WiFi 10->35 min (25 min hole, well over its ~1 min cadence)
    assert len(gbd["bbb222"]) == 1
    assert gbd["bbb222"][0]["dur_min"] == 25.0
    # device A never dropped -> no gaps of its own, not tarred by B's dropout
    assert gbd["aaa111"] == []


def test_continuity_metrics_surface_per_device(tmp_path: Path) -> None:
    ctx = _fleet(tmp_path)
    by_id = {g["device_id"]: g for g in ctx["devices"]}
    a, b = by_id["aaa111"]["continuity"], by_id["bbb222"]["continuity"]
    assert a["gap_count"] == 0 and a["coverage_pct"] == 100.0
    assert b["gap_count"] == 1
    assert b["longest_gap_min"] == 25.0 and b["last_gap_min"] == 25.0
    # B: 25 min of gap over a 45 min observed span -> ~44% coverage, clearly < A
    assert b["coverage_pct"] is not None and b["coverage_pct"] < 60.0


def test_trajectory_line_breaks_across_the_dropout(tmp_path: Path) -> None:
    ctx = _fleet(tmp_path)
    dsets = {d["id"]: d for d in ctx["trajectory"]["datasets"]}
    # multi-device -> device-scoped ids (s1@<device_id>)
    b = next(d for k, d in dsets.items() if k.endswith("bbb222"))
    a = next(d for k, d in dsets.items() if k.endswith("aaa111"))
    # B's line carries exactly one null-y break at the dropout; A's carries none
    assert sum(1 for p in b["points"] if p["y"] is None) == 1
    assert all(p["y"] is not None for p in a["points"])
    # the break sits inside the hole (between ~10 and ~35 h-units... here minutes/60)
    brk = next(p for p in b["points"] if p["y"] is None)
    assert 0.16 < brk["x"] < 0.59  # ~10min .. ~35min expressed in hours


def test_raw_rows_untouched(tmp_path: Path) -> None:
    # every input row is still a parsed reading; the gap surfacing adds nothing
    # to and removes nothing from the raw record set.
    a = "".join(_row("aaa111", "sA", m, 2400 + m) for m in range(0, 5))
    data = parse_files([_write(tmp_path, "sA", a)])
    assert len(data.readings) == 5
    assert [r.raw_value for r in data.readings] == [2400, 2401, 2402, 2403, 2404]
