"""#822 — the pass-anchored watering-cycle range: B (fleet anchors to the PASS) +
A (the 2 h lead-in pad), absent-safe, and honest when it can't serve what was asked."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.analytics.cycle_range import LEAD_IN_H, cycle_window, fleet_pass_anchors
from tools.analytics.segment_history import TierRow

T0 = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _series(watering_hours, span_h=200):
    """A dry-down with a -300 transient at each given hour (a detected watering)."""
    rows, raw = [], 1500.0
    for h in range(span_h):
        if h in watering_hours:
            raw = max(1200.0, raw - 300)
            rows.append(TierRow(T0 + timedelta(hours=h), raw, "OK"))
            rows.append(TierRow(T0 + timedelta(hours=h, minutes=2), raw + 5, "OK"))
            continue
        raw += 8
        rows.append(TierRow(T0 + timedelta(hours=h), raw, "OK"))
    return rows


def test_window_anchors_to_the_last_pass_with_the_two_hour_pad() -> None:
    series = {"pA": _series({40, 120})}
    now = T0 + timedelta(hours=200)
    w = cycle_window(series, which="cycle1", now=now)
    assert w is not None and w["exact"] is True
    anchor = datetime.fromisoformat(w["anchor"])
    t0 = datetime.fromisoformat(w["t0"])
    # the newest pass, not the older one; the anchor sits at the last PRE-drop
    # reading (the classifier's run start), so it lands just before the nominal hour
    assert timedelta(hours=115) <= (anchor - T0) <= timedelta(hours=121)
    assert (anchor - t0) == timedelta(hours=LEAD_IN_H)  # ruling A: the 2 h pad
    assert w["pad_h"] == 2.0
    # the span is handed to the caller in plain hours, so it composes with the chips
    assert w["hours"] > 80  # ~80 h of arc + the pad, not a fixed chip


def test_cycle2_reaches_the_previous_pass_so_cadence_is_comparable() -> None:
    series = {"pA": _series({40, 120})}
    now = T0 + timedelta(hours=200)
    one = cycle_window(series, which="cycle1", now=now)
    two = cycle_window(series, which="cycle2", now=now)
    assert two["exact"] is True
    assert datetime.fromisoformat(two["anchor"]) < datetime.fromisoformat(one["anchor"])
    assert two["hours"] > one["hours"]  # a wider window, two cycles of shape


def test_the_fleet_anchor_is_the_pass_not_one_plants_own_event() -> None:
    # ruling B: two plants watered ~30 min apart are ONE round (75-min gap), so the
    # fleet window opens on the round, never on whichever plant happened to be last
    a = _series({40})
    b = [TierRow(t.timestamp_utc + timedelta(minutes=30), t.raw_value, "OK") for t in a]
    anchors = fleet_pass_anchors({"pA": a, "pB": b})
    assert len(anchors) == 1  # one pass, not two per-plant events


def test_no_watering_on_record_declines_instead_of_inventing_an_anchor() -> None:
    flat = {
        "pA": [TierRow(T0 + timedelta(hours=h), 1500.0 + h, "OK") for h in range(50)]
    }
    assert cycle_window(flat, which="cycle1", now=T0 + timedelta(hours=50)) is None


def test_asking_for_two_cycles_with_one_on_record_says_what_it_served() -> None:
    series = {"pA": _series({40})}
    w = cycle_window(series, which="cycle2", now=T0 + timedelta(hours=100))
    assert w["requested"] == "cycle2" and w["label"] == "cycle1"
    assert w["exact"] is False  # never silently a different window than claimed


def test_a_glug_only_plant_still_anchors_the_fleet_window() -> None:
    # a sensorless plant's manual glug is real watering evidence (#1137)
    flat = {
        "pA": [TierRow(T0 + timedelta(hours=h), 1500.0 + h, "OK") for h in range(50)]
    }
    glug = [(T0 + timedelta(hours=20), "glug", "pS")]
    w = cycle_window(
        flat, journal_events=glug, which="cycle1", now=T0 + timedelta(hours=50)
    )
    assert w is not None
    assert datetime.fromisoformat(w["anchor"]) == T0 + timedelta(hours=20)
