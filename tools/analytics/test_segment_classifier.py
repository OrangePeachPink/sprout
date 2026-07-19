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


def test_c1_rebound_ends_when_the_rate_settles_not_at_a_clock() -> None:
    # C1: a fast 1 h recovery (+120 c/h) then a flat drying arc (+4 c/h). The rate rule
    # ends the rebound at the settle; C0's 3 h box would have held it 2 h too long.
    rows = [_r(i, 1700 - i) for i in range(10)]  # steady pre-arc
    falls = [1560, 1420, 1300]  # 10..12 the transient (-140 steps, confirmed)
    for k, raw in enumerate(falls):
        rows.append(_r(10 + k, raw))
    for k in range(60):  # 13..72 one hour of fast recovery (+2 raw/min = +120 c/h)
        rows.append(_r(13 + k, 1300 + 2 * k))
    for k in range(90):  # 73..162 settled slow drying (+4 c/h — under the 30 c/h bar)
        rows.append(_r(73 + k, 1420 + k // 15))
    kinds = {s.kind: (s.i0, s.i1) for s in segments(rows) if s.kind != "steady-drying"}
    assert "watering-transient" in kinds and "rebound" in kinds
    r0, r1 = kinds["rebound"]
    # the transient's trough-noise rule swallows the first wobble of the recovery;
    # the rebound starts immediately after wherever the transient run ends
    assert r0 == kinds["watering-transient"][1] + 1
    # the settle happens ~row 73; the 30-min forward window ends the rebound within
    # a window's width of it — and far before the old 3 h box (row 193)
    assert 45 <= r1 <= 80


def test_c1_a_slow_recovery_extends_past_the_old_3h_box() -> None:
    # the splash-evaporation arc: +60 c/h sustained for 5 h. Rate-based keeps it
    # rebound the whole way (the old box cut it at 3 h and let the trend fit +60 c/h
    # "drying" — the live absurdity).
    rows = [_r(i, 1900) for i in range(5)]
    rows.append(_r(5, 1700))  # a -200 single-step transient
    for k in range(300):  # 6..305 five hours at +1 raw/min = +60 c/h
        rows.append(_r(6 + k, 1700 + k))
    kinds = {s.kind: (s.i0, s.i1) for s in segments(rows) if s.kind == "rebound"}
    r0, r1 = kinds["rebound"]
    assert r1 - r0 > 240  # far beyond a 3 h (180-row) box; capped only by REBOUND_MAX_H


def test_passes_reproduce_the_maintainer_session_truth_in_miniature() -> None:
    from segment_classifier import passes

    def t(day, h, m):
        return datetime(2026, 7, day, h, m, tzinfo=timezone.utc)

    events = [
        # the 07-10 "dose session": spread over ~100 min (gaps < 75) — ONE pass
        (t(10, 15, 0), "soil", "s2@dev"),
        (t(10, 16, 5), "soil", "s3@dev"),
        (t(10, 16, 40), "soil", "s4@dev"),
        # the 07-19 pass: detections + catch-up glugs 16 min later — ONE pass
        (t(19, 18, 4), "soil", "s1@dev"),
        (t(19, 18, 6), "glug", "p02"),
        (t(19, 18, 22), "glug", "p11"),
    ]
    got = passes(events)
    assert [(p.pass_id, p.n) for p in got] == [
        ("2026-07-10T15:00", 3),
        ("2026-07-19T18:04", 3),
    ]
    # the naive 30-min gap splits the dose session TWICE — the calibration's point
    assert len(passes(events, gap_min=30.0)) == 4
