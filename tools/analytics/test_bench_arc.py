"""Tests for the bench-arc recompute (#380), driven by the committed #419 data.

The headline behaviours: (1) the rule reproduces the curated `plant_arc_table.csv`
for uniform-wetting plants from raw samples; (2) it *honestly diverges* on
preferential-flow plants — the cross-probe median stays drier than the curated
single-responding-probe pick; (3) honest gaps stay null, never fabricated.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench_arc as ba


def _by_id() -> dict[str, dict]:
    return {r["plant_id"]: r for r in ba.recompute_arc()}


def test_recompute_is_deterministic() -> None:
    assert ba.recompute_arc() == ba.recompute_arc()


def test_all_eleven_plants_present() -> None:
    arc = _by_id()
    assert [f"P{n:02d}" for n in range(1, 12)] == sorted(arc)


def test_honest_gaps_stay_null() -> None:
    arc = _by_id()
    # P04/P05 bypassed — no valid wet peak; the read is a gap, not a fabricated number.
    for pid in ("P04", "P05", "P07"):
        assert arc[pid]["wettest"] is None
        assert arc[pid]["wettest_source"] == "gap"
    # P02/P03 had no durable pull checkpoint.
    for pid in ("P02", "P03"):
        assert arc[pid]["ending"] is None


def test_summary_phases_carried_and_flagged() -> None:
    # P01's dry/wet come from sidecar summaries (raw rows not committed) — carried,
    # flagged 'summary', and excluded from the sample reconciliation.
    p01 = _by_id()["P01"]
    assert p01["start_source"] == "summary" and p01["start"] == 2137
    assert p01["wettest_source"] == "summary" and p01["wettest"] == 1188
    assert p01["ending_source"] == "samples"  # the morning monitor *is* committed


def test_uniform_wetting_reproduces_curated() -> None:
    arc = _by_id()
    curated = ba.load_committed_arc_table()
    # P01 pull, P09 single-probe wettest, P06 wettest: rule == curation within tol.
    assert abs(arc["P01"]["ending"] - curated["P01"]["ending"]) <= 3
    assert abs(arc["P09"]["wettest"] - curated["P09"]["wettest"]) <= 5
    assert abs(arc["P06"]["wettest"] - curated["P06"]["wettest"]) <= 80


def test_preferential_flow_diverges_drier() -> None:
    arc = _by_id()
    curated = ba.load_committed_arc_table()
    # Where only one of several probes wetted, the cross-probe median is much DRIER
    # (higher raw) than the curated single-responding-probe pick. Honest, not a bug.
    for pid in ("P08", "P11"):
        assert arc[pid]["wettest"] - curated[pid]["wettest"] > 300


def test_wettest_instant_is_wetter_or_equal() -> None:
    # The instantaneous spike is never drier than the sustained cross-probe wettest.
    for r in ba.recompute_arc():
        if (
            r.get("wettest_source") == "samples"
            and r.get("wettest_instant") is not None
        ):
            assert r["wettest_instant"] <= r["wettest"]


def test_spread_surfaces_microzone_disagreement() -> None:
    arc = _by_id()
    # The preferential-flow pots carry a large pull-time probe spread — the signal.
    assert (
        arc["P11"]["ending_spread"] is not None and arc["P11"]["ending_spread"] > 1000
    )
    # A single-probe plant has no cross-probe spread.
    assert arc["P09"]["ending_spread"] is None


def test_band_derives_from_raw_not_tag() -> None:
    from parse_v1 import band_for_raw

    for r in ba.recompute_arc():
        if r.get("ending") is not None:
            assert r["ending_band"] == band_for_raw(r["ending"])


def test_reconcile_flags_preferential_flow() -> None:
    flagged = {
        (d["plant_id"], d["phase"])
        for d in ba.reconcile()
        if d["class"] == "preferential-flow/probe-set"
    }
    assert ("P08", "wettest") in flagged
    assert ("P11", "wettest") in flagged
