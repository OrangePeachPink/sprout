"""#1331 — identity resolves on the covering assignment interval, never the open one.

Two fixtures the issue names: a probe move (pre-move rows keep the old plant) and a
sampling gap (two segments, and no valid_for_trend window spanning the hole)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from segment_classifier import segments, valid_for_trend, valid_trend_runs
from segment_history import TierRow
from tier_store import (
    hours_per_band_duckdb,
    hours_per_band_truth,
    resolve_plant_at,
)

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
MOVE = "2026-07-03T00:00:00Z"  # the probe leaves p01 and lands on p02


def _write_parquet(root: Path, rows: list[tuple]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    out = root / "part.parquet"
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE t (timestamp_utc TIMESTAMP, device_id VARCHAR,"
        " sensor_id VARCHAR, raw_value INTEGER, band VARCHAR,"
        " quality_flag VARCHAR, session_id VARCHAR, config_id VARCHAR)"
    )
    con.executemany("INSERT INTO t VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.execute(f"COPY t TO '{out.as_posix()}' (FORMAT PARQUET)")
    con.close()
    return out


class _R:
    """A parsed-reading stand-in for the oracle path."""

    def __init__(self, ts, dev, sen, raw, band):
        self.timestamp_utc, self.device_id, self.sensor_id = ts, dev, sen
        self.raw_value, self.band, self.quality_flag = raw, band, "OK"


# the probe moved: p01 held the channel until MOVE, p02 holds it after
ASSIGNMENTS = [
    ("dev1", "s1", "p01", None, MOVE),  # grandfathered start, closed at the move
    ("dev1", "s1", "p02", MOVE, None),  # opens at the move, still open
]


def test_resolve_picks_the_covering_interval_on_both_sides_of_a_move() -> None:
    before = T0 + timedelta(days=1)
    after = T0 + timedelta(days=4)
    assert resolve_plant_at(ASSIGNMENTS, "dev1", "s1", before) == "p01"
    assert resolve_plant_at(ASSIGNMENTS, "dev1", "s1", after) == "p02"
    # the boundary is half-open: start <= t < end, so the move instant is the NEW plant
    assert (
        resolve_plant_at(
            ASSIGNMENTS, "dev1", "s1", datetime(2026, 7, 3, tzinfo=timezone.utc)
        )
        == "p02"
    )
    assert resolve_plant_at(ASSIGNMENTS, "dev1", "s2", before) is None  # other channel


def test_probe_move_pre_move_rows_keep_the_old_plant(tmp_path: Path) -> None:
    # THE fixture: without the interval join every one of these rows inherits p02,
    # retroactively relabelling p01's entire recorded life.
    rows, tagged = [], []
    for h in range(0, 96, 12):  # 4 days, spanning the move at day 2
        ts = (T0 + timedelta(hours=h)).replace(tzinfo=None)
        rows.append((ts, "dev1", "s1", 1500, "OK", "OK", "s", "c"))
        tagged.append((_R(T0 + timedelta(hours=h), "dev1", "s1", 1500, "OK"), "f.csv"))
    pq = _write_parquet(tmp_path / "part", rows)

    store = hours_per_band_duckdb(pq, ASSIGNMENTS)
    oracle = hours_per_band_truth(tagged, ASSIGNMENTS)

    assert store == oracle, "the store and its independent oracle must agree exactly"
    # BOTH plants appear — history is split at the move, not stitched onto today
    assert {p for p, _b in store} == {"p01", "p02"}
    assert store[("p01", "OK")] > 0 and store[("p02", "OK")] > 0


def test_the_oracle_does_not_share_the_implementations_premise() -> None:
    # the oracle resolves per row by linear scan; the store resolves by SQL interval
    # join. Same answer, different mechanism — that is what makes it a verifier.
    src = Path(__file__).resolve().parent / "tier_store.py"
    text = src.read_text(encoding="utf-8")
    truth = text.split("def hours_per_band_truth")[1]
    assert "resolve_plant_at" in truth  # per-row resolution
    assert "JOIN plant_map" not in truth  # not the same join it verifies


def test_classifier_gap_yields_two_segments_and_no_trend_spans_the_hole() -> None:
    # the 26 h 7/8->7/9 shape: a steady arc, a long sampling hole, another steady arc.
    rows = [
        TierRow(T0 + timedelta(minutes=30 * i), 1500.0 + 8 * i, "OK") for i in range(20)
    ]
    resume = rows[-1].timestamp_utc + timedelta(hours=26)
    rows += [
        TierRow(resume + timedelta(minutes=30 * i), 1700.0 + 8 * i, "OK")
        for i in range(20)
    ]

    segs = [s for s in segments(rows) if s.kind == "steady-drying"]
    assert len(segs) == 2, "a sampling hole must break the arc into two segments"

    # ...and the stronger property the issue names: no valid_for_trend WINDOW may
    # span the hole. A bridging window leaks a phantom slope into the predictor's
    # training filter even when the segment count is right.
    hole_start, hole_end = rows[19].timestamp_utc, rows[20].timestamp_utc
    assert hole_end - hole_start >= timedelta(hours=24)
    # both rows either side are honestly steady-drying, so the flat mask says True
    valid = valid_for_trend(rows)
    assert valid[19] and valid[20]
    # ...and the RUNS carry the discontinuity the mask cannot: no fittable window
    # contains rows from both sides, so no trend can span time nobody observed
    runs = valid_trend_runs(rows)
    assert len(runs) == 2
    assert [(a, b) for a, b in runs if a <= 19 and b >= 20] == []
