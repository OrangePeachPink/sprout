"""Cross-channel spread is FENCED per device (#651 / #575).

Each device's co-located probes are a meaningful max-min; blending probes from
different pots/boards into one number has no physical meaning. Sweeps already key
on session_id (device-owned), so the blend was at the *aggregation* level - every
device's per-sweep spread folded into one global mean/max/series. This pins the
per-device split (and that a single-device install is numerically unchanged).
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context
from tools.analytics.device_registry import Registry
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=t  run=spread\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "millis_ms,sensor_id,raw_value,quality_flag,payload\n"
)


def _row(ts, session, device, millis, sid, raw):
    return (
        f"plants.soil,{ts},{ts[:-1]},{session},{device},{millis},"
        f"{sid},{raw},OK,level=OK;gpio=36\n"
    )


def _ctx(tmp_path: Path, rows: list[str]):
    p = tmp_path / "s.csv"
    p.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=Registry())


def _t(mins: int) -> str:
    return f"2026-07-04T00:{mins:02d}:30.000Z"


def _by_dev(spread: list) -> dict:
    return {s["device_id"]: s for s in spread}


def test_two_devices_get_separate_spread_series_never_blended(tmp_path: Path) -> None:
    rows = [
        # device A: two sweeps, spreads 100 then 200 (mean 150, max 200)
        _row(_t(0), "sessA", "devA", 1000, "s1", 1500),
        _row(_t(0), "sessA", "devA", 1000, "s2", 1600),
        _row(_t(1), "sessA", "devA", 2000, "s1", 1500),
        _row(_t(1), "sessA", "devA", 2000, "s2", 1700),
        # device B: two sweeps, spreads 50 then 10 (mean 30, max 50)
        _row(_t(0), "sessB", "devB", 1000, "s1", 3000),
        _row(_t(0), "sessB", "devB", 1000, "s2", 3050),
        _row(_t(1), "sessB", "devB", 2000, "s1", 3000),
        _row(_t(1), "sessB", "devB", 2000, "s2", 3010),
    ]
    spread = _ctx(tmp_path, rows)["spread"]
    assert isinstance(spread, list) and len(spread) == 2  # one series per device
    by = _by_dev(spread)
    assert by["devA"]["max"] == 200 and by["devA"]["current"] == 200  # last sweep
    assert by["devA"]["mean"] == 150.0
    assert by["devB"]["max"] == 50 and by["devB"]["current"] == 10  # last sweep = 10
    assert by["devB"]["mean"] == 30.0
    # the blend the old code produced: neither device's spread is the cross-device
    # max-min (3050-1500=1550), nor the blended mean(100,200,50,10)=90
    for s in spread:
        assert s["max"] != 1550
        assert s["mean"] != 90


def test_single_device_is_one_series_unchanged(tmp_path: Path) -> None:
    rows = [
        _row(_t(0), "sessA", "devA", 1000, "s1", 1500),
        _row(_t(0), "sessA", "devA", 1000, "s2", 1600),  # spread 100
        _row(_t(1), "sessA", "devA", 2000, "s1", 1500),
        _row(_t(1), "sessA", "devA", 2000, "s2", 1800),  # spread 300
    ]
    spread = _ctx(tmp_path, rows)["spread"]
    assert len(spread) == 1
    s = spread[0]
    assert s["device_id"] == "devA"
    assert s["current"] == 300 and s["max"] == 300
    assert s["mean"] == 200.0 and s["median"] == 200
    assert len(s["points"]) == 2


def test_a_lone_probe_earns_no_spread(tmp_path: Path) -> None:
    # one device, one channel - no co-located peer to spread against
    rows = [
        _row(_t(0), "sessA", "devA", 1000, "s1", 1500),
        _row(_t(1), "sessA", "devA", 2000, "s1", 1520),
    ]
    assert _ctx(tmp_path, rows)["spread"] == []  # honest absence, not a zero


def test_one_device_with_pair_another_with_lone_probe(tmp_path: Path) -> None:
    rows = [
        _row(_t(0), "sessA", "devA", 1000, "s1", 1500),
        _row(_t(0), "sessA", "devA", 1000, "s2", 1650),  # devA spread 150
        _row(_t(0), "sessB", "devB", 1000, "s1", 3000),  # devB: lone probe, no peer
    ]
    spread = _ctx(tmp_path, rows)["spread"]
    assert [s["device_id"] for s in spread] == ["devA"]  # only the paired device
    assert spread[0]["max"] == 150
