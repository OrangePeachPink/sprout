"""Tests for the event-annotated bench-data view (#380).

Fixture-based (a synthetic survey sidecar mirroring the Sage P01-P11 shape) so the
flattening, the derived-provisional band, the event classification, and the DuckDB
annotated view are all deterministic and decoupled from the live bench evidence.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_events as be

# A two-plant survey: P01 has clean last/median raw; P08 has pre/post/delta phases;
# P99 is narrative-only (events, no per-probe raw) — must yield events, no readings.
_SURVEY = {
    "experiment_id": "20260629_sage_fixture",
    "plant_segments": [
        {
            "plant_id": "P01",
            "plant": "pothos",
            "evidence_quality": "clean four-probe baseline",
            "water_balance": {"applied_cups": 1.0, "runoff_observed": False},
            "selected_log_summary": {
                "window_local": "2026-06-29 07:18 to 12:16",
                "median_raw": {"s1": 1272, "s2": 1431, "s3": 1244, "s4": 1126},
                "last_raw": {"s1": 1280, "s2": 1437, "s3": 1251, "s4": 1138},
            },
            "events": [
                {
                    "time_local": "2026-06-29 12:23 CDT",
                    "event": "Applied ~1 cup water, no runoff.",
                },
                {
                    "time_local": "2026-06-29 12:16 CDT",
                    "event": "Final monitor state before probe pull.",
                },
            ],
        },
        {
            "plant_id": "P08",
            "plant": "snake plant",
            "evidence_quality": "strong staged-dosing; s3 contact-invalid placement",
            "water_balance": {"applied_cups": 0.5, "runoff_observed": True},
            "selected_log_summary": {
                "pre_water_raw": {"s1": 3274, "s2": 3169, "s3": 3176, "s4": 3183},
                "post_water_raw": {"s1": 2921, "s2": 3191, "s3": 1977, "s4": 3154},
                "post_water_delta_raw": {"s1": -353, "s2": 22, "s3": -1199, "s4": -29},
            },
            "events": [
                {
                    "time_local": "2026-06-29 18:30 CDT",
                    "event": "Filled cachepot tray, paused for soak.",
                },
            ],
        },
        {
            "plant_id": "P99",
            "plant": "narrative only",
            "evidence_quality": "observation note",
            "selected_log_summary": {"closeout_call": "looked fine"},
            "events": [{"time_local": "n/a", "event": "Reseated probe by hand."}],
        },
    ],
}


def _survey_dir(tmp_path: Path) -> Path:
    (tmp_path / "20260629_sage_fixture.json").write_text(
        json.dumps(_SURVEY), encoding="utf-8"
    )
    return tmp_path


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #


def test_band_for_raw_dry_to_wet() -> None:
    assert be.band_for_raw(3274) == "air-dry"  # >= b0, driest
    assert be.band_for_raw(1977) == "needs water"
    assert be.band_for_raw(1272) == "well watered"  # low raw = wet
    assert be.band_for_raw(900) == "submerged"  # below every boundary
    assert be.band_for_raw(None) is None
    assert be.band_for_raw("nan") is None


def test_classify_event() -> None:
    assert be.classify_event("Applied ~1 cup water, no runoff") == "watering"
    assert be.classify_event("Filled cachepot tray, paused") == "tray"
    assert be.classify_event("s3 contact-invalid placement") == "contact"
    assert be.classify_event("Reseated probe by hand") == "probe"
    assert be.classify_event("Plant looked perky") == "observation"


# --------------------------------------------------------------------------- #
# flattening
# --------------------------------------------------------------------------- #


def test_load_and_reading_rows(tmp_path: Path) -> None:
    segs = be.load_segments(_survey_dir(tmp_path))
    assert {s["plant_id"] for s in segs} == {"P01", "P08", "P99"}
    rows = be.reading_rows(segs)
    # P01: 2 phases x 4 probes = 8; P08: 3 phases x 4 = 12; P99: 0 (narrative)
    assert len(rows) == 20
    plants = {r["plant_id"] for r in rows}
    assert plants == {"P01", "P08"}  # P99 contributes no readings
    # phase + derived band carried; band derived for absolute raw
    p08_post = next(
        r
        for r in rows
        if r["plant_id"] == "P08"
        and r["phase"] == "post_water_raw"
        and r["probe"] == "s3"
    )
    assert p08_post["raw"] == 1977 and p08_post["band"] == "needs water"
    assert p08_post["band_basis"] == "derived-provisional"
    assert p08_post["contact_caveat"] is True  # from evidence_quality
    # a delta phase carries the raw delta but NO band (it's a change, not a level)
    p08_delta = next(
        r
        for r in rows
        if r["plant_id"] == "P08"
        and r["phase"] == "post_water_delta_raw"
        and r["probe"] == "s3"
    )
    assert (
        p08_delta["raw"] == -1199
        and p08_delta["band"] is None
        and p08_delta["is_delta"] is True
    )


def test_event_rows_classified(tmp_path: Path) -> None:
    rows = be.event_rows(be.load_segments(_survey_dir(tmp_path)))
    assert len(rows) == 4  # 2 (P01) + 1 (P08) + 1 (P99)
    types = {r["event_type"] for r in rows}
    assert {"watering", "tray", "probe"} <= types
    assert all(r["plant_id"] and r["event_text"] for r in rows)


# --------------------------------------------------------------------------- #
# the DuckDB annotated view
# --------------------------------------------------------------------------- #


def test_build_store_and_annotated_view(tmp_path: Path) -> None:
    store = tmp_path / "bench.duckdb"
    summary = be.build_store(docs_dir=_survey_dir(tmp_path), out_path=store)
    assert summary == {"plants": 2, "readings": 20, "events": 4}
    # the annotated view: each reading carries its plant's events, aggregated
    rows = be.query(
        "SELECT plant_id, probe, band, event_count, events FROM bench_annotated "
        "WHERE plant_id='P08' AND phase='post_water_raw' AND probe='s3'",
        out_path=store,
    )
    assert len(rows) == 1
    r = rows[0]
    assert r["band"] == "needs water" and r["event_count"] == 1
    assert "tray:" in r["events"]  # the classified annotation rode along
    # the transient json load-sidecars are cleaned up
    assert not (tmp_path / "_bench_readings.json").exists()
