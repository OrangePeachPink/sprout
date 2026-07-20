"""#1148 — the evaluation substrate: one payload, three candidates, honest absence."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from multiplant_history import (
    PlantRow,
    build_payload,
    daily_rows,
    fleet_envelope,
)

T0 = datetime(2026, 7, 10, tzinfo=timezone.utc)


def _rows(spec):
    return [
        PlantRow(T0 + timedelta(hours=h), float(raw), "OK", band)
        for h, raw, band in spec
    ]


def test_the_days_band_is_dwell_dominant_not_the_last_blip() -> None:
    # 20 h in "OK" then a single late reading in "DRY": the day is OK, because a
    # last-reading rule would let one blip rename a whole day of the plant's life
    spec = [(h, 1500 + h, "OK") for h in range(0, 21)] + [(21, 2400, "DRY")]
    out = daily_rows({"pA": _rows(spec)}, T0, T0 + timedelta(days=2))
    (day,) = out["pA"]
    assert day["band"] == "OK"
    assert day["bands_us"]["OK"] > day["bands_us"].get("DRY", 0)
    assert day["n"] == 22 and len(day["points"]) == 22  # the shape lane keeps all


def test_an_outage_cannot_win_the_day(tmp_path=None) -> None:
    # one reading in "DRY", then a 10 h gap, then a full day of "OK": the capped
    # dwell keeps the outage from crowning the band it merely preceded
    spec = [(0, 2400, "DRY")] + [(10 + h, 1500, "OK") for h in range(12)]
    out = daily_rows({"pA": _rows(spec)}, T0, T0 + timedelta(days=2))
    (day,) = out["pA"]
    assert day["band"] == "OK"


def test_envelope_names_the_desert_dweller_and_ships_both_ink_orders() -> None:
    now = T0 + timedelta(days=6)
    # pA watered recently (a -300 transient), pB long ago
    recent = [(h, 2000, "DRY") for h in range(0, 100, 2)]
    recent += [(100, 1700, "well watered"), (102, 1720, "well watered")]
    old = [(h, 1800, "OK") for h in range(0, 4)]
    old += [(4, 1500, "well watered"), (6, 1520, "well watered")]
    old += [(h, 1600 + h, "OK") for h in range(8, 120, 4)]
    names = {"pA": "Fern", "pB": "Cactus"}
    env = fleet_envelope({"pA": _rows(recent), "pB": _rows(old)}, None, names, now)
    assert env["longest_cycle"]["plant_name"] == "Cactus"  # the forgotten one
    assert env["last_watering"]["days_ago"] < env["longest_cycle"]["days_ago"]
    # both ink references ship — Design-QA's open question is a render switch
    assert [p["plant_id"] for p in env["by_recency"]] == ["pA", "pB"]
    assert [p["plant_id"] for p in env["by_need"]] == ["pB", "pA"]


def test_an_unwatered_fleet_says_so_instead_of_inventing_a_headline() -> None:
    flat = _rows([(h, 1500 + h, "OK") for h in range(40)])
    env = fleet_envelope({"pA": flat}, None, {"pA": "Fern"}, T0 + timedelta(days=3))
    assert env["last_watering"] is None and env["longest_cycle"] is None
    assert env["n_passes"] == 0  # no fabricated "watered today"


def test_payload_is_absent_safe_and_keeps_sensorless_plants(tmp_path: Path) -> None:
    reg = Registry(
        devices=[Device(device_id="d1", board="esp32dev", label="A", channels={})],
        sensorless=[{"plant_id": "pS", "plant_name": "Cactus"}],
    )
    payload = build_payload(registry=reg, root=tmp_path, events_root=tmp_path, now=T0)
    ids = [p["plant_id"] for p in payload["plants"]]
    assert "pS" in ids  # a sensorless plant appears, never vanishes
    assert payload["rows"]["pS"] == [] and payload["ledger"]["pS"] == []
    assert payload["envelope"]["last_watering"] is None
    # the three candidates are named in the payload's own register
    assert set(payload["candidates"].values()) == {"rows", "envelope", "ledger"}


def test_every_live_band_resolves_to_a_mood(tmp_path: Path) -> None:
    # the render guarantee: a candidate can never draw a moodless bar
    reg = Registry(devices=[], sensorless=[{"plant_id": "pS", "plant_name": "C"}])
    payload = build_payload(registry=reg, root=tmp_path, events_root=tmp_path, now=T0)
    assert payload["moods_resolved"] is True and payload["unmapped_bands"] == []
