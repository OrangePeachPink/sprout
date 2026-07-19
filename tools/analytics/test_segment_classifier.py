"""#1244 — the C0 segment classifier: golden fixture pins the segment boundaries.

A hand-built plant-week-in-miniature (60 s cadence): steady drying, one wire-flagged
row, a confirmed watering transient, the time-boxed rebound window — with the boundary
indices asserted EXACTLY, plus the near-miss cases the rules must refuse (a small dip
that reverts is noise, not a watering).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import Reading
from segment_classifier import (
    CONFIRM_DROP_RAW,
    segments,
    valid_for_trend,
)

_T0 = datetime(2026, 7, 19, 6, 0, 0, tzinfo=timezone.utc)


def _r(i, raw, quality="OK"):
    return Reading(
        "plants.soil",
        _T0 + timedelta(minutes=i),  # 60 s cadence
        None,
        None,
        "sess",
        "dev1",
        "0.8.0",
        "x",
        None,
        "UMLIFE_v2_TLC555",
        "s1",
        "",
        "s1",
        raw,
        None,
        "",
        quality,
        {"level": "OK"},
    )


def _golden():
    rows = []
    for i in range(50):  # 0..49 steady drying (slowly rising raw)
        rows.append(_r(i, 1600 + i))
    rows.append(_r(50, 1650, quality="SUSPECT"))  # 50 — a distrusted row
    for i in range(51, 100):  # 51..99 steady again
        rows.append(_r(i, 1600 + i))
    falls = [1620, 1540, 1460, 1380, 1310, 1300]  # 100..105 the watering transient
    for k, raw in enumerate(falls):
        rows.append(_r(100 + k, raw))
    for k in range(10):  # 106..115 rebound (rising +30/step, inside the 3 h window)
        rows.append(_r(106 + k, 1330 + 30 * k))
    return rows


def test_golden_fixture_boundaries_exact() -> None:
    got = [(s.kind, s.i0, s.i1) for s in segments(_golden())]
    assert got == [
        ("steady-drying", 0, 49),
        ("flagged", 50, 50),
        ("steady-drying", 51, 98),
        # the last pre-drop reading (99) anchors the transient run
        ("watering-transient", 99, 105),
        ("rebound", 106, 115),
    ]


def test_valid_for_trend_is_steady_only() -> None:
    mask = valid_for_trend(_golden())
    assert sum(mask) == 98  # 50 + 48 steady rows
    assert not any(mask[99:])  # transient + rebound never feed a trend fit
    assert mask[0] and mask[98] and not mask[50]


def test_a_small_reverting_dip_is_noise_not_a_watering() -> None:
    # a -70 single dip that reverts: onset fires but the run never reaches
    # CONFIRM_DROP_RAW total fall — no transient, the week stays one steady segment.
    rows = [_r(i, 1600) for i in range(10)]
    rows.append(_r(10, 1530))  # -70 dip (≥ onset, < confirm since it reverts)
    rows += [_r(11 + i, 1600) for i in range(10)]
    assert CONFIRM_DROP_RAW > 70  # the premise of the case
    assert [s.kind for s in segments(rows)] == ["steady-drying"]


def test_a_quiet_week_is_one_steady_segment() -> None:
    rows = [_r(i, 1500 + i) for i in range(40)]
    got = segments(rows)
    assert [(s.kind, s.i0, s.i1) for s in got] == [("steady-drying", 0, 39)]
    assert all(valid_for_trend(rows))


def test_the_gentle_bromeliad_class_watering_is_caught() -> None:
    # the band-jump detector missed the Bromeliad's ~220-count 1-band drink (live,
    # 2026-07-19); the raw-domain rule must catch exactly this shape.
    rows = [_r(i, 1790 + (i % 2)) for i in range(20)]  # flat needs-water plateau
    rows.append(_r(20, 1690))  # -100
    rows.append(_r(21, 1580))  # -110 → total 210 ≥ CONFIRM_DROP_RAW
    rows += [_r(22 + i, 1580 + (i % 2)) for i in range(8)]  # settled wet plateau
    kinds = {s.kind for s in segments(rows)}
    assert "watering-transient" in kinds
