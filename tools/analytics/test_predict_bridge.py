"""#1243 D5 — the Predict bridge: one shape, the mask bound once, exact-µs rates,
caveats travelling, and the two-registries resolution with its provenance."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.device_registry import Device, Registry
from tools.analytics.predict_bridge import (
    COLUMNS,
    build_views,
    current_arc,
    read_segments,
    resolve_identity,
    segment_rows,
)
from tools.analytics.segment_history import TierRow

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _rows(spec):
    return [TierRow(T0 + timedelta(minutes=m), float(v), "OK") for m, v in spec]


def _drydown(start_m, start_raw, per_step, n, step_m=30):
    return [(start_m + i * step_m, start_raw + i * per_step) for i in range(n)]


def _sawtooth():
    """steady dry-down → a watering transient → rebound → steady again."""
    return _rows(
        [
            *_drydown(0, 1600, 5, 40),
            (1200, 1500.0),  # the -300 single-step drop (onset)
            (1230, 1400.0),
            *_drydown(1260, 1420, 4, 40),
        ]
    )


def test_the_shape_is_one_shape_and_the_mask_binds_once() -> None:
    rows = segment_rows({"pA": _sawtooth()}, "static")
    assert rows, "the sawtooth must produce segments"
    for r in rows:
        assert set(r) == set(COLUMNS)  # THE shape — no per-consumer variants
    kinds = {r["kind"] for r in rows}
    assert "steady-drying" in kinds and "watering-transient" in kinds
    for r in rows:
        # the guarantee lives in the view: valid iff steady-drying, and an invalid
        # segment carries NO rate a consumer could accidentally fit
        assert r["valid_for_trend"] == (r["kind"] == "steady-drying")
        if not r["valid_for_trend"]:
            assert r["rate_c_per_h"] is None


def test_rate_is_exact_counts_per_hour_over_us() -> None:
    # +5 counts per 30 min = exactly +10.0 counts/hour
    rows = segment_rows({"pA": _rows(_drydown(0, 1500, 5, 30))}, "static")
    (seg,) = [r for r in rows if r["valid_for_trend"]]
    assert seg["rate_c_per_h"] == 10.0
    assert seg["duration_us"] == 29 * 30 * 60 * 1_000_000  # exact integer µs
    assert seg["n"] == 30 and seg["raw_first"] == 1500.0


def test_a_thin_segment_reports_no_rate_never_a_fabricated_zero() -> None:
    rows = segment_rows({"pA": _rows([(0, 1500), (30, 1505)])}, "static")
    assert all(r["rate_c_per_h"] is None for r in rows)  # 2 rows < FIT_MIN_ROWS


def test_caveats_travel_onto_every_row_of_that_plant() -> None:
    profiles = {
        "p07": {
            "plant_id": "p07",
            "hydrology": {"probe_reading_caveat": "may-underread-standing-water"},
        }
    }
    rows = segment_rows(
        {
            "p07": _rows(_drydown(0, 1500, 5, 10)),
            "p01": _rows(_drydown(0, 1500, 5, 10)),
        },
        "static",
        profiles,
    )
    p07 = [r for r in rows if r["plant_id"] == "p07"]
    p01 = [r for r in rows if r["plant_id"] == "p01"]
    assert p07 and all(r["caveat"] == "may-underread-standing-water" for r in p07)
    assert p01 and all(r["caveat"] is None for r in p01)  # absent-safe, never ""


def test_current_arc_is_the_latest_valid_arc_or_an_honest_none() -> None:
    rows = segment_rows({"pA": _sawtooth()}, "static")
    arc = current_arc(rows)
    assert arc is not None and arc["rate_c_per_h"] is not None
    # it must be the LATEST valid arc, not the first
    valid = [r for r in rows if r["valid_for_trend"]]
    assert arc["t1"] == max(r["t1"] for r in valid)
    # a plant with only a transient has no valid arc — the predictor's abstain input
    only_drop = segment_rows({"pB": _rows([(0, 2000), (1, 1700), (2, 1650)])}, "static")
    assert current_arc([r for r in only_drop if r["kind"] != "steady-drying"]) is None


def test_identity_falls_back_to_static_and_stamps_its_provenance() -> None:
    reg = Registry(
        devices=[
            Device(
                device_id="devA",
                board="esp32dev",
                label="A",
                channels={"s1": {"plant_id": "pA", "plant_name": "a"}},
            )
        ]
    )
    # no local temporal instance in the test env -> the static fallback answers,
    # and says so (the C2 finding, resolved in ONE place)
    pairs, source = resolve_identity(reg)
    assert source in ("temporal", "static")
    if source == "static":
        assert pairs == {("devA", "s1"): "pA"}
    rows = segment_rows({"pA": _rows(_drydown(0, 1500, 5, 10))}, source)
    assert all(r["identity_source"] == source for r in rows)  # stamped on every row


def test_views_materialize_and_read_back_filtered(tmp_path: Path) -> None:
    import duckdb

    raw = tmp_path / "raw" / "date=2026-07-01" / "device=devA"
    raw.mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t (timestamp_utc TIMESTAMP, device_id VARCHAR, sensor_id VARCHAR,"
        " raw_value INTEGER, band VARCHAR, quality_flag VARCHAR, session_id VARCHAR,"
        " config_id VARCHAR)"
    )
    con.executemany(
        "INSERT INTO t VALUES (?, 'devA', 's1', ?, 'Moist', 'OK', 'x', 'c')",
        [(str(T0 + timedelta(minutes=30 * i))[:19], 1500 + 5 * i) for i in range(30)],
    )
    con.execute(f"COPY t TO '{(raw / 'part.parquet').as_posix()}' (FORMAT PARQUET)")
    con.close()

    reg = Registry(
        devices=[
            Device(
                device_id="devA",
                board="esp32dev",
                label="A",
                channels={"s1": {"plant_id": "pA", "plant_name": "a"}},
            )
        ]
    )
    stats = build_views(tmp_path / "raw", tmp_path / "views", registry=reg)
    assert stats["segments"] >= 1 and stats["valid_segments"] >= 1
    assert stats["current_arcs"] == 1
    back = read_segments(root=tmp_path / "views")
    assert back and set(back[0]) == set(COLUMNS)
    valid = read_segments(valid_only=True, root=tmp_path / "views")
    assert valid and all(r["valid_for_trend"] for r in valid)
    assert read_segments(plant_id="nope", root=tmp_path / "views") == []


def test_temporal_is_rejected_when_it_maps_a_fleet_the_tier_never_saw() -> None:
    # The live defect this guard exists for: the temporal loader falls back to the
    # committed EXAMPLE on a host with no local instance and returns plausible pairs
    # for devices that never logged a row. Non-emptiness is NOT proof — preferring it
    # would stamp `temporal` on rows the static registry actually mapped.
    from tools.analytics import predict_bridge

    reg = Registry(
        devices=[
            Device(
                device_id="realdev",
                board="esp32dev",
                label="R",
                channels={"s1": {"plant_id": "pA", "plant_name": "a"}},
            )
        ]
    )
    fake_temporal = {("ghostdev", "s1"): "pZ"}  # a fleet the tier has never seen
    orig = (
        predict_bridge.registry_plant_map
        if hasattr(predict_bridge, "registry_plant_map")
        else None
    )
    from tools.analytics import tier_store

    tier_store.registry_plant_map = lambda *a, **k: fake_temporal
    try:
        pairs, source = resolve_identity(reg, None, devices_in_tier={"realdev"})
        assert source == "static"  # rejected: zero overlap with the real tier
        # #1315: the static fallback is now keyed in the CANONICAL chN namespace —
        # the registry's "s1" key folds to "ch2" (the port that emitted s1). The
        # guard is unchanged and still rejects the ghost fleet (source == "static");
        # only the key shape moved, which is the translation doing its job.
        assert pairs == {("realdev", "ch2"): "pA"}
        # and when the temporal map DOES cover the tier, it wins honestly
        _pairs2, source2 = resolve_identity(reg, None, devices_in_tier={"ghostdev"})
        assert source2 == "temporal"
    finally:
        tier_store.registry_plant_map = orig
