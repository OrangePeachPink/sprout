"""#718 the 'Moisture history' chart carries a plant-first label per trace, not a
machine id / GPIO. The legend + tooltip read the plant name; the data plane
supplies it (the template just renders `d.label`).
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context
from tools.analytics.device_registry import Device, Registry
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id=s1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _log(tmp_path: Path, probed: bool) -> str:
    rows = ""
    for i, raw in enumerate((2400, 2410, 2420)):
        ts = f"2026-07-05T00:{i:02d}:30.000Z"
        rows += f"plants.soil,{ts},{ts[:-1]},s1,dev1,s2,{raw},OK,level=DRY\n"
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + rows, encoding="utf-8")
    return str(p)


def test_trajectory_label_is_plant_first(tmp_path: Path) -> None:
    reg = Registry(
        devices=[
            Device(
                device_id="dev1",
                board="esp32dev",
                label="A",
                channels={"s2": {"plant_id": "p02", "plant_name": "pothos"}},
            )
        ]
    )
    ctx = build_context(parse_files([_log(tmp_path, True)]), registry=reg)
    ds = ctx["trajectory"]["datasets"]
    assert ds and all("label" in d for d in ds)
    assert ds[0]["label"] == "pothos"  # the plant name, not "s2" / a GPIO


def test_trajectory_label_falls_back_honestly(tmp_path: Path) -> None:
    # no registry -> no plant name; label falls back to the channel token, never
    # an invented name (honest: shows what's known).
    ctx = build_context(parse_files([_log(tmp_path, False)]), registry=Registry())
    ds = ctx["trajectory"]["datasets"]
    assert ds[0]["label"] == "s2"  # the bare channel id, no fabrication
