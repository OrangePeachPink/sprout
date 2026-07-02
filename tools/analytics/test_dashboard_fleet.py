"""Tests for fleet-registry plant attribution on dashboard cards (#486, epic #448).

The tethered-today building block for "monitor all plants": build_context()
attributes each channel to a plant via device_registry.plant_for(device_id,
sensor_id), so a card shows a plant name instead of a bare channel id once a
fleet config assigns one. Unknown device / unassigned channel / no config all
degrade honestly to None - the registry never invents a plant, and the card
still renders on raw sensor id (#486's own honesty contract, inherited from
#485).

This does NOT cover N simultaneous devices streaming over WiFi - that transport
is still blocked on #276/#277. It covers the attribution layer that view will
need, using whatever device(s) are already present in parsed log data today.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_HEADER = (
    "# fw=0.7.0  git=test123  run=fleettest\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)


def _row(
    sid: str, device_id: str, raw: int, ts: str = "2026-06-28T00:00:30.000Z"
) -> str:
    local = ts.replace("Z", "")
    return (
        f"plants.soil,{ts},{local},sess1,{device_id},{sid},{raw},"
        "OK,level=well watered;gpio=36\n"
    )


def _write(path: Path, rows: list[str]) -> None:
    path.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")


def _registry() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="sprout-classic-01",
                board="esp32dev",
                label="classic",
                channels={
                    "s1": {"plant_id": "P01", "plant_name": "Monstera"},
                    "s2": {},  # present, unassigned
                },
            )
        ]
    )


def test_known_device_and_channel_gets_a_plant_name(tmp_path: Path) -> None:
    log = tmp_path / "a.csv"
    _write(log, [_row("s1", "sprout-classic-01", 1500)])
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    s1 = next(s for s in ctx["sensors"] if s["id"] == "s1")
    assert s1["plant_id"] == "P01"
    assert s1["plant_name"] == "Monstera"
    assert s1["device_id"] == "sprout-classic-01"


def test_unassigned_channel_is_honest_none(tmp_path: Path) -> None:
    log = tmp_path / "b.csv"
    _write(log, [_row("s2", "sprout-classic-01", 1500)])
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    s2 = next(s for s in ctx["sensors"] if s["id"] == "s2")
    assert s2["plant_id"] is None
    assert s2["plant_name"] is None


def test_unknown_device_is_honest_none(tmp_path: Path) -> None:
    log = tmp_path / "c.csv"
    _write(log, [_row("s1", "some-other-esp32", 1500)])
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    s1 = next(s for s in ctx["sensors"] if s["id"] == "s1")
    assert s1["plant_id"] is None
    assert s1["plant_name"] is None
    assert s1["device_id"] == "some-other-esp32"


def test_empty_registry_never_raises_and_stays_honest(tmp_path: Path) -> None:
    log = tmp_path / "d.csv"
    _write(log, [_row("s1", "sprout-classic-01", 1500)])
    ctx = build_context(parse_files([str(log)]), registry=Registry())
    s1 = next(s for s in ctx["sensors"] if s["id"] == "s1")
    assert s1["plant_id"] is None and s1["plant_name"] is None


def test_missing_device_id_column_degrades_to_none(tmp_path: Path) -> None:
    # a pre-#278 row with no device_id column at all - device_id reads "" from
    # the row, which no registry config assigns, so attribution stays honest
    log = tmp_path / "e.csv"
    cols = (
        "record_type,timestamp_utc,timestamp_local,session_id,"
        "sensor_id,raw_value,quality_flag,payload\n"
    )
    row = (
        "plants.soil,2026-06-28T00:00:30.000Z,2026-06-28T00:00:30.000,"
        "sess1,s1,1500,OK,level=well watered;gpio=36\n"
    )
    log.write_text(_HEADER + cols + row, encoding="utf-8")
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    s1 = next(s for s in ctx["sensors"] if s["id"] == "s1")
    assert s1["plant_id"] is None and s1["device_id"] is None


def test_default_registry_param_loads_without_crashing(tmp_path: Path) -> None:
    # no registry passed -> load_registry() falls back to the committed
    # config/devices.example.json (a real device_id won't collide with it, so
    # attribution stays None, but the call path itself must not raise)
    log = tmp_path / "f.csv"
    _write(log, [_row("s1", "Sprout ESP32", 1500)])
    ctx = build_context(parse_files([str(log)]))
    assert ctx["sensors"][0]["id"] == "s1"  # renders regardless of attribution


if __name__ == "__main__":
    for fn in (
        test_known_device_and_channel_gets_a_plant_name,
        test_unassigned_channel_is_honest_none,
        test_unknown_device_is_honest_none,
        test_empty_registry_never_raises_and_stays_honest,
        test_missing_device_id_column_degrades_to_none,
        test_default_registry_param_loads_without_crashing,
    ):
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
