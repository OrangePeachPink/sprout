"""#627/#717 the band-history view substrate — per plant, where it sits across the
7 bands + how it's drifting over the window, assembled from the merged #650
band-movement substrate. Honesty: device-emitted bands only, discrete transitions
(never a line), per-device fenced, plant-first labels, trend in the unit of bands.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id=s1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(minute: int, raw: int, level: str, sensor: str = "s2") -> str:
    ts = f"2026-07-05T00:{minute:02d}:30.000Z"
    return f"plants.soil,{ts},{ts[:-1]},s1,dev1,{sensor},{raw},OK,level={level}\n"


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="dev1",
                board="esp32dev",
                label="A",
                channels={"s2": {"plant_id": "p02", "plant_name": "pothos"}},
            )
        ]
    )


def _ctx(tmp_path: Path, rows: str):
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + rows, encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=_reg())


# a run that dries from well-watered (wet) down to needs-water (drier)
_DRYING = "".join(
    [
        _row(0, 1500, "well watered"),
        _row(1, 1500, "well watered"),
        _row(2, 1900, "OK"),
        _row(3, 2300, "needs water"),
        _row(4, 2350, "needs water"),
    ]
)


def test_band_history_present_and_plant_first(tmp_path: Path) -> None:
    bh = _ctx(tmp_path, _DRYING)["band_history"]
    assert len(bh) == 1
    e = bh[0]
    assert e["label"] == "pothos"  # plant-first, not the machine sensor id
    assert e["plant_id"] == "p02"
    assert e["current"]["band"] == "needs water"  # where it is now


def test_trend_reads_as_drift_toward_water(tmp_path: Path) -> None:
    e = _ctx(tmp_path, _DRYING)["band_history"][0]
    # well watered -> needs water is a drift toward "water me"
    assert e["trend"]["dir"] == "drying"
    assert e["trend"]["from_band"] == "well watered"
    assert e["trend"]["to_band"] == "needs water"
    assert e["trend"]["steps"] < 0  # net movement toward the dry (lower) end


def test_touched_band_span_and_discrete_trail(tmp_path: Path) -> None:
    e = _ctx(tmp_path, _DRYING)["band_history"][0]
    # touched bands: needs water (driest) .. well watered (wettest)
    assert e["driest"] == "needs water"
    assert e["wettest"] == "well watered"
    assert e["span"] == e["wettest_index"] - e["driest_index"] > 0
    # discrete transitions — a step per band change, never one row per reading
    seq = [t["band"] for t in e["transitions"]]
    assert seq == ["well watered", "OK", "needs water"]  # 3 steps, not 5 rows


def test_steady_plant_has_no_false_trend(tmp_path: Path) -> None:
    steady = "".join(_row(i, 1900, "OK") for i in range(4))
    e = _ctx(tmp_path, steady)["band_history"][0]
    assert e["trend"]["dir"] == "steady"
    assert e["span"] == 0  # never left the band


def test_unmapped_channel_falls_back_but_still_shows(tmp_path: Path) -> None:
    # no registry -> no plant name; the entity still appears, labeled by its
    # channel id (honest: the movement is real even if the plant is unnamed).
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + _DRYING, encoding="utf-8")
    bh = build_context(parse_files([str(p)]), registry=Registry())["band_history"]
    assert bh[0]["label"] == "s2" and bh[0]["plant_name"] is None
