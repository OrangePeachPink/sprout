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


# --------------------------------------------------------------------------- #
# #1435 — the trial must distinguish "tier not built" from "genuinely empty"
# --------------------------------------------------------------------------- #
def test_tier_state_empty_when_no_parquet(tmp_path: Path) -> None:
    """An empty store root is "empty" — the launcher has not filled it yet (#1466).
    A surface must say "still gathering", never "no readings"."""
    from multiplant_history import tier_state

    assert tier_state(tmp_path) == "empty"


def test_the_payload_carries_the_tier_state(tmp_path: Path) -> None:
    """The signal Design's render branch needs (#1435 pt 3): on an unbuilt store the
    payload says so, so calm-empty can tell dark from genuinely-empty."""
    reg = Registry(devices=[], sensorless=[{"plant_id": "pS", "plant_name": "C"}])
    payload = build_payload(registry=reg, root=tmp_path, events_root=tmp_path, now=T0)
    assert payload["tier_state"] == "empty"  # unbuilt, not "no readings"
    assert payload["bands_seen"] == []  # and empty — but now DISTINGUISHABLE from ready


def _fill_store(root: Path, rows: list[tuple[str, int]]) -> None:
    """Write one real parquet partition of soil rows (device 'dev', 2026-07-10)."""
    import pytest

    pytest.importorskip("duckdb")
    from parse_v1 import Reading
    from tier_store import build_partition

    tagged = [
        (
            Reading(
                "plants.soil",
                datetime(2026, 7, 10, 0, i, tzinfo=timezone.utc),
                None,
                None,
                "sess1",
                "dev",
                "0.8.0",
                "x",
                None,
                "UMLIFE_v2_TLC555",
                sensor,
                "",
                sensor,
                raw,
                None,
                "",
                "OK",
                {"level": "overwatered"},
            ),
            "seg.csv",
        )
        for i, (sensor, raw) in enumerate(rows)
    ]
    build_partition(tagged, "dev", datetime(2026, 7, 10).date(), out_root=root)


def test_tier_state_ready_and_both_generations_resolve(tmp_path: Path) -> None:
    """A built store is "ready"; and #1454's join means a window of v4 `s1` + v5 `ch2`
    rows for one channel BOTH resolve to the plant — the join symptom Design's point 1
    predicted is already cured, so the trial lights when the store is filled."""
    import pytest

    pytest.importorskip("duckdb")
    from multiplant_history import tier_state

    root = tmp_path / "tier"
    _fill_store(root, [("s1", 1500), ("ch2", 1520)])  # both token generations
    assert tier_state(root) == "ready"

    reg = Registry(
        devices=[
            Device(
                device_id="dev",
                board="esp32-classic",
                label="A",
                channels={"ch2": {"plant_id": "p11", "plant_name": "Fern"}},
            )
        ]
    )
    payload = build_payload(
        registry=reg,
        root=root,
        events_root=tmp_path,
        now=datetime(2026, 7, 11, tzinfo=timezone.utc),
    )
    assert payload["tier_state"] == "ready"
    assert "overwatered" in payload["bands_seen"]  # the band is live, not empty
    p11 = next(p for p in payload["plants"] if p["plant_id"] == "p11")
    assert p11["n_readings"] == 2  # BOTH s1 and ch2 resolved (the #1454 join)
