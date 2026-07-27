"""#679 (ADR-0028) sensorless plants are first-class 'alive, not probed'.

A probe-less plant (tiny pot, hard rootball, a cactus) is present by design. The
dashboard is data-driven (no probe -> no reading -> no card), so v0.7.0 rendered
only the 8 probed windowsill plants and the 3 sensorless ones were invisible.
These tests pin the registry representation + the context emit that give them a
home, and the honesty rules: never degraded, and a real reading always wins.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context
from tools.analytics.device_registry import Device, Registry, load_registry
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id=s1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _log(tmp_path: Path) -> str:
    ts = "2026-07-05T00:00:30.000Z"
    row = f"plants.soil,{ts},{ts[:-1]},s1,dev1,s1,2400,OK,level=DRY\n"
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + row, encoding="utf-8")
    return str(p)


def _reg(sensorless: list, probed_pid: str = "p01") -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="dev1",
                board="esp32dev",
                label="A",
                channels={"s1": {"plant_id": probed_pid, "plant_name": "fern"}},
            )
        ],
        sensorless=sensorless,
    )


# --------------------------------------------------------------------------- #
# registry representation
# --------------------------------------------------------------------------- #
def test_registry_lists_sensorless_plants() -> None:
    reg = _reg(
        [
            {
                "plant_id": "p08",
                "plant_name": "cactus",
                "plant_type": "cactus",
                "reason": "no spike",
            },
            {"plant_id": "p09", "plant_name": "aloe"},
        ]
    )
    sl = reg.sensorless_plants()
    assert [p["plant_id"] for p in sl] == ["p08", "p09"]  # sorted, stable order
    assert sl[0]["reason"] == "no spike"
    assert sl[0]["plant_type"] == "cactus"
    assert sl[1]["plant_name"] == "aloe"


def test_probed_plant_is_never_shown_sensorless() -> None:
    # p01 is probed on dev1/s1 AND (mistakenly) listed sensorless -> the real
    # reading wins; it is filtered out of the sensorless roster.
    reg = _reg([{"plant_id": "p01", "plant_name": "fern"}], probed_pid="p01")
    assert reg.sensorless_plants() == []


def test_absent_sensorless_is_empty() -> None:
    reg = _reg([])
    assert reg.sensorless_plants() == []


def test_config_parses_optional_sensorless_key(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.json"
    cfg.write_text(
        '{"schema_version":1,"devices":['
        '{"device_id":"d1","board":"esp32dev","channels":'
        '{"s1":{"plant_id":"p01","plant_name":"fern"}}}],'
        '"sensorless":[{"plant_id":"p08","plant_name":"cactus","reason":"tiny pot"}]}',
        encoding="utf-8",
    )
    reg = load_registry(cfg)
    sl = reg.sensorless_plants()
    assert len(sl) == 1 and sl[0]["plant_id"] == "p08" and sl[0]["reason"] == "tiny pot"


# --------------------------------------------------------------------------- #
# dashboard context emit
# --------------------------------------------------------------------------- #
def test_context_emits_sensorless_cards(tmp_path: Path) -> None:
    reg = _reg([{"plant_id": "p08", "plant_name": "cactus", "reason": "no spike"}])
    ctx = build_context(parse_files([_log(tmp_path)]), registry=reg)
    assert [p["plant_id"] for p in ctx["sensorless"]] == ["p08"]
    # the probed plant still renders as a normal sensor card, unaffected
    assert any(s.get("plant_name") == "fern" for s in ctx["sensors"])


def test_no_sensorless_key_is_empty_list(tmp_path: Path) -> None:
    reg = _reg([])
    ctx = build_context(parse_files([_log(tmp_path)]), registry=reg)
    assert ctx["sensorless"] == []  # absent-safe, never missing
