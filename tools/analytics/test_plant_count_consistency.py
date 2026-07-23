"""#807 — the Moisture-history header count must agree with the masthead. It was
counting every channel incl. retired-rig ones (13) and calling them "plants,"
while the masthead honestly showed 8 live + 2 retired. The trajectory now plots
and counts only LIVE channels, matching fleet.channels_active.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.dashboard import RETIRE_AFTER_H, build_context
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
_EDGE = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def _row(dev: str, sess: str, ts: datetime, sensor: str, raw: int) -> str:
    u = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    lo = ts.strftime("%Y-%m-%d %H:%M:%S.000")
    ms = int(ts.timestamp() * 1000) % 10_000_000
    return f"plants.soil,{u},{lo},{sess},{dev},{ms},{sensor},{raw},OK,level=OK\n"


def _reg() -> Registry:
    ch = {"s1": {"plant_id": "p1"}, "s2": {"plant_id": "p2"}}
    return Registry(
        devices=[
            Device("launch", "esp32", "L", channels=ch),  # live
            Device("sparerig", "esp32", "S", channels=ch),  # will auto-retire (old)
        ]
    )


def _ctx(tmp_path: Path):
    # launch: 2 channels live at the edge; sparerig: 2 channels, last seen long ago
    rows_live = "".join(
        _row("launch", "sL", _EDGE - timedelta(seconds=s), ch, 2400)
        for s in (60, 30, 0)
        for ch in ("s1", "s2")
    )
    old = _EDGE - timedelta(hours=RETIRE_AFTER_H + 6)
    rows_retired = "".join(
        _row("sparerig", "sS", old - timedelta(seconds=s), ch, 3000)
        for s in (30, 0)
        for ch in ("s1", "s2")
    )
    pL = tmp_path / "L.csv"
    pL.write_text(_HEADER.format(sess="sL") + _COLS + rows_live, encoding="utf-8")
    pS = tmp_path / "S.csv"
    pS.write_text(_HEADER.format(sess="sS") + _COLS + rows_retired, encoding="utf-8")
    return build_context(parse_files([str(pL), str(pS)]), registry=_reg())


def test_trajectory_count_matches_the_masthead_active_count(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    # the retired rig is demoted (sanity)
    retired = {g["device_id"] for g in ctx["devices"] if g["retired"]}
    assert retired == {"sparerig"}
    # the two surfaces AGREE on the honest live count (2 live channels)
    assert ctx["fleet"]["channels_active"] == 2
    assert ctx["trajectory"]["plant_count"] == 2
    assert ctx["trajectory"]["plant_count"] == ctx["fleet"]["channels_active"]


def test_retired_channels_are_not_plotted(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    ids = [d["id"] for d in ctx["trajectory"]["datasets"]]
    # exactly the two LIVE channels are plotted; the retired rig's are gone
    assert len(ids) == 2
    assert not any(i.endswith("sparerig") for i in ids)
    assert all(i.endswith("launch") for i in ids)


def test_single_live_device_unaffected(tmp_path: Path) -> None:
    # a plain one-device log (no retirement) still plots + counts all its channels
    rows = "".join(
        _row("launch", "sL", _EDGE - timedelta(seconds=s), ch, 2400)
        for s in (60, 30, 0)
        for ch in ("s1", "s2")
    )
    p = tmp_path / "L.csv"
    p.write_text(_HEADER.format(sess="sL") + _COLS + rows, encoding="utf-8")
    ctx = build_context(parse_files([str(p)]), registry=_reg())
    assert ctx["trajectory"]["plant_count"] == 2
    assert ctx["trajectory"]["plant_count"] == ctx["fleet"]["channels_active"]
