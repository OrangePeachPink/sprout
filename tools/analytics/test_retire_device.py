"""#683 device lifecycle — a retired/archived board (registry flag OR silent past
RETIRE_AFTER_H relative to the fleet's live edge) demotes to a slim row and drops
out of the active fleet count. Reversible + honest: raw data is preserved.

The live 16h dogfood rendered 4 device groups but only 2 were launch MCUs; the
two pre-launch test rigs (offline ~1 day) still rendered as full groups and
inflated "4 devices · 13 channels".
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import RETIRE_AFTER_H, build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id={sess}\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "millis_ms,sensor_id,raw_value,quality_flag,payload\n"
)
_EDGE = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def _row(dev: str, sess: str, ts: datetime, raw: int, sensor: str = "s1") -> str:
    u = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    lo = ts.strftime("%Y-%m-%d %H:%M:%S.000")
    ms = int(ts.timestamp() * 1000) % 10_000_000
    return f"plants.soil,{u},{lo},{sess},{dev},{ms},{sensor},{raw},OK,level=DRY\n"


def _write(tmp_path: Path, sess: str, rows: str) -> str:
    p = tmp_path / f"{sess}.csv"
    p.write_text(_HEADER.format(sess=sess) + _COLS + rows, encoding="utf-8")
    return str(p)


def _reg(retire_spare: bool = False) -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="launch1",
                board="esp32dev",
                label="Launch",
                channels={"s1": {}},
            ),
            Device(
                device_id="spare1",
                board="esp32dev",
                label="Spare",
                channels={"s1": {}},
                retired=retire_spare,
            ),
        ]
    )


def _build(tmp_path: Path, spare_last: datetime, registry: Registry):
    # launch board is live at the fleet edge; spare's last reading is `spare_last`
    live = "".join(
        _row("launch1", "sL", _EDGE - timedelta(seconds=s), 2400) for s in (60, 30, 0)
    )
    spare = "".join(
        _row("spare1", "sS", spare_last - timedelta(seconds=s), 3000) for s in (30, 0)
    )
    ctx = build_context(
        parse_files([_write(tmp_path, "sL", live), _write(tmp_path, "sS", spare)]),
        registry=registry,
    )
    devs = {g["device_id"]: g for g in ctx["devices"]}
    return ctx, devs


def test_registry_flag_retires_regardless_of_age(tmp_path: Path) -> None:
    # spare is fresh (reporting now) but explicitly archived in the registry
    _ctx, devs = _build(tmp_path, spare_last=_EDGE, registry=_reg(retire_spare=True))
    assert devs["spare1"]["retired"] is True
    assert devs["spare1"]["retired_reason"] == "archived"
    assert devs["launch1"]["retired"] is False


def test_auto_demote_after_hours_silent(tmp_path: Path) -> None:
    # spare last seen well over the window before the fleet's live edge -> auto
    old = _EDGE - timedelta(hours=RETIRE_AFTER_H + 6)
    _ctx, devs = _build(tmp_path, spare_last=old, registry=_reg())
    assert devs["spare1"]["retired"] is True
    assert devs["spare1"]["retired_reason"] == "offline"  # not a registry edit


def test_recent_device_is_not_retired(tmp_path: Path) -> None:
    recent = _EDGE - timedelta(hours=RETIRE_AFTER_H - 2)  # within the window
    _ctx, devs = _build(tmp_path, spare_last=recent, registry=_reg())
    assert devs["spare1"]["retired"] is False
    assert devs["spare1"]["retired_reason"] is None


def test_fleet_summary_counts_only_active(tmp_path: Path) -> None:
    old = _EDGE - timedelta(hours=RETIRE_AFTER_H + 6)
    ctx, _devs = _build(tmp_path, spare_last=old, registry=_reg())
    f = ctx["fleet"]
    assert f["devices_active"] == 1  # only the launch board
    assert f["devices_retired"] == 1
    assert f["channels_active"] == 1  # the retired board's channel drops out
    assert f["retire_after_h"] == RETIRE_AFTER_H


def test_raw_rows_preserved_when_retired(tmp_path: Path) -> None:
    old = _EDGE - timedelta(hours=RETIRE_AFTER_H + 6)
    data = parse_files([_write(tmp_path, "sS", _row("spare1", "sS", old, 3000))])
    assert len(data.readings) == 1
    assert data.readings[0].raw_value == 3000  # retirement de-emphasizes, never deletes
