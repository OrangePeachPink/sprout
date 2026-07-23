"""#1248 C4 — the backtest harness: causality enforced by the harness, honest
abstain/unresolved accounting, exact scoring, and the baseline slope predictor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.backtest import actual_waterings, backtest, baseline_predictor
from tools.analytics.segment_history import TierRow

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _rows(spec):
    """spec: (minutes, raw) pairs -> TierRows at 30 s-grade fidelity."""
    return [TierRow(T0 + timedelta(minutes=m), float(v), "OK") for m, v in spec]


def _drydown(start_m, start_raw, rate_per_30m, n, step_m=30):
    return [(start_m + i * step_m, start_raw + i * rate_per_30m) for i in range(n)]


def test_harness_enforces_causality_the_predictor_cannot_peek() -> None:
    rows = _rows(_drydown(0, 1500, 5, 200))
    seen = []

    def probe(causal, now, prior):
        seen.append((max(r.timestamp_utc for r in causal), now))
        return None

    backtest({"pA": rows}, {"pA": []}, predictor=probe)
    assert seen, "the probe must have been called"
    for max_ts, now in seen:
        assert max_ts <= now  # the slice never contains the future


def test_scoring_oracle_zero_biased_plus_five() -> None:
    rows = _rows(_drydown(0, 1500, 5, 400))  # 200 h of drying
    actual = T0 + timedelta(hours=150)

    def oracle(causal, now, prior):
        return actual

    def biased(causal, now, prior):
        return actual + timedelta(hours=5)

    r0 = backtest({"pA": rows}, {"pA": [actual]}, predictor=oracle)["pA"]
    r5 = backtest({"pA": rows}, {"pA": [actual]}, predictor=biased)["pA"]
    assert r0["mae_h"] == 0.0 and r0["median_err_h"] == 0.0
    assert r5["mae_h"] == 5.0 and r5["median_err_h"] == 5.0
    # forecasts made AFTER the only actual have nothing to score against
    assert r0["n_unresolved"] > 0 and r0["n_scored"] > 0
    assert r0["n_scored"] + r0["n_unresolved"] + r0["n_abstain"] == r0["n_attempts"]


def test_abstain_is_counted_never_coerced() -> None:
    rows = _rows(_drydown(0, 1500, 5, 100))
    r = backtest({"pA": rows}, {"pA": []}, predictor=lambda c, n, p: None)["pA"]
    assert r["n_abstain"] == r["n_attempts"] and r["n_scored"] == 0
    assert r["mae_h"] is None  # no invented score


def test_baseline_learns_her_threshold_and_projects_the_slope() -> None:
    # A prior watering at raw≈2000 teaches the threshold; then a clean 10 c/h
    # dry-down from 1500 must project the crossing near the true instant.
    seg1 = _drydown(0, 1700, 5, 61)  # drying to 2000 at minute 1800
    drop = [(1801, 1400.0), (1802, 1300.0)]  # the watering transient (-300 single-step)
    seg2 = _drydown(1980, 1500, 5, 240)  # 10 c/h again; hits 2000 at +100 h
    rows = _rows(seg1 + drop + seg2)
    watering = T0 + timedelta(minutes=1801)
    now = T0 + timedelta(hours=50)  # mid-segment-2, well before the true crossing
    causal = [r for r in rows if r.timestamp_utc <= now]
    predicted = baseline_predictor(causal, now, [watering])
    assert predicted is not None
    true_cross = T0 + timedelta(minutes=1980 + (2000 - 1500) / 5 * 30)
    assert abs((predicted - true_cross).total_seconds()) < 3600  # within an hour
    # without a prior watering there is no personal threshold -> honest abstain
    assert baseline_predictor(causal, now, []) is None


def test_actuals_cluster_transients_and_glugs_into_passes(tmp_path: Path) -> None:
    seg = _rows(
        [
            *_drydown(0, 2000, 0, 3),
            (90, 1600.0),
            (91, 1550.0),
            *_drydown(120, 1560, 1, 10),
        ]
    )
    journal = tmp_path / "j.jsonl"
    journal.write_text(
        '{"plant_id": "pA", "source": "manual", "ts": "2026-07-01T01:35:00Z"}\n'
        '{"plant_id": "pB", "source": "manual", "ts": "2026-07-01T01:40:00Z"}\n',
        encoding="utf-8",
    )
    actuals = actual_waterings({"pA": seg}, journal)
    # pA: the soil onset (01:00) + its glug (01:35) = ONE pass, one event
    assert len(actuals["pA"]) == 1
    # pB is sensorless-style: its glug alone still yields an actual
    assert len(actuals["pB"]) == 1
