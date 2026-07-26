"""#1137 slice 1 — the manual watering journal. A one-tap "glug glug" writes a
``source="manual"`` event; it reads back as the latest per plant, and a torn line never
breaks the read. Absence is first-class (no journal -> no events, never a crash).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.analytics.watering_log import latest_by_plant, load_events, log_manual


def _journal(tmp_path: Path) -> Path:
    return tmp_path / "watering_log.local.jsonl"


def test_log_manual_writes_a_source_manual_event(tmp_path: Path) -> None:
    j = _journal(tmp_path)
    ev = log_manual("p03", ml=237.0, note="a good pour", path=j)
    assert ev["plant_id"] == "p03"
    assert ev["source"] == "manual"  # the honest label the chip distinguishes
    assert ev["ml"] == 237.0 and ev["note"] == "a good pour"
    assert ev["ts"].endswith("Z")  # UTC, second precision
    assert load_events(j) == [ev]  # round-trips


def test_a_blank_plant_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        log_manual("  ", path=_journal(tmp_path))


def test_ml_and_note_are_optional(tmp_path: Path) -> None:
    ev = log_manual("p01", path=_journal(tmp_path))
    assert "ml" not in ev and "note" not in ev  # a bare "I watered it" is enough


def test_absent_journal_is_empty_never_a_crash(tmp_path: Path) -> None:
    assert load_events(tmp_path / "nope.jsonl") == []
    assert latest_by_plant(tmp_path / "nope.jsonl") == {}


def test_latest_by_plant_is_by_timestamp_not_file_order(tmp_path: Path) -> None:
    j = _journal(tmp_path)
    # append an OLDER watering after a newer one (a back-dated correction)
    log_manual("p01", ts=datetime(2026, 7, 18, 9, tzinfo=timezone.utc), path=j)
    log_manual("p01", ts=datetime(2026, 7, 17, 9, tzinfo=timezone.utc), path=j)
    log_manual("p02", ts=datetime(2026, 7, 18, 8, tzinfo=timezone.utc), path=j)
    latest = latest_by_plant(j)
    assert latest["p01"]["ts"] == "2026-07-18T09:00:00Z"  # newest, not last-written
    assert latest["p02"]["ts"] == "2026-07-18T08:00:00Z"


def test_a_torn_line_is_skipped_not_fatal(tmp_path: Path) -> None:
    j = _journal(tmp_path)
    log_manual("p05", path=j)
    with j.open("a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")  # a half-flushed line
        fh.write("\n")  # a blank line
    events = load_events(j)
    assert len(events) == 1 and events[0]["plant_id"] == "p05"


# --------------------------------------------------------------------------- #
# #1203 glug phase 2 — the verdict layer
# --------------------------------------------------------------------------- #


def test_event_id_is_derived_so_it_survives_a_detector_rebuild() -> None:
    from datetime import datetime, timezone

    from tools.analytics.watering_log import event_id_for

    onset = datetime(2026, 7, 19, 18, 5, 40, tzinfo=timezone.utc)
    eid = event_id_for("p02", onset)
    assert eid == "p02@2026-07-19T18:05"  # minute granularity, no allocated serial
    # a rebuild recomputes the SAME id from the same event — verdicts stay bound
    assert event_id_for("p02", onset.replace(second=59)) == eid
    assert event_id_for("p02", "2026-07-19T18:05:40Z") == eid  # ISO string too


def test_a_verdict_appends_and_never_erases_the_rejection(tmp_path) -> None:
    from tools.analytics.watering_log import detection_state, log_verdict, verdicts

    j = tmp_path / "j.jsonl"
    eid = "p02@2026-07-08T00:21"
    assert detection_state(eid, j) == "proposed"  # unreviewed is never 'confirmed'
    log_verdict(eid, "rejected", path=j)
    assert detection_state(eid, j) == "rejected"
    log_verdict(eid, "confirmed", path=j)  # she changes her mind
    assert detection_state(eid, j) == "confirmed"  # newest wins
    # but the rejection is STILL on disk — it is the detector's training signal
    body = j.read_text(encoding="utf-8")
    assert '"state": "rejected"' in body and '"state": "confirmed"' in body
    assert len(verdicts(j)) == 1  # one event, one current state


def test_verdicts_and_manual_waterings_share_the_journal_without_collision(tmp_path):
    from tools.analytics.watering_log import (
        load_events,
        log_manual,
        log_verdict,
        verdicts,
    )

    j = tmp_path / "j.jsonl"
    log_manual("p01", path=j)
    log_verdict("p01@2026-07-19T18:05", "confirmed", path=j)
    log_manual("p02", path=j)
    # the manual reader ignores verdicts; the verdict reader ignores waterings
    assert [e["plant_id"] for e in load_events(j)] == ["p01", "p02"]
    assert list(verdicts(j)) == ["p01@2026-07-19T18:05"]


def test_precision_reports_both_numerals_and_abstains_before_any_ruling(tmp_path):
    from tools.analytics.watering_log import log_verdict, precision_so_far

    j = tmp_path / "j.jsonl"
    detected = ["a@1", "b@2", "c@3", "d@4"]
    p0 = precision_so_far(detected, j)
    assert p0["detected"] == 4 and p0["proposed"] == 4
    assert p0["precision"] is None  # nothing ruled -> no invented ratio
    log_verdict("a@1", "confirmed", path=j)
    log_verdict("b@2", "confirmed", path=j)
    log_verdict("c@3", "rejected", path=j)
    p = precision_so_far(detected, j)
    assert (p["confirmed"], p["rejected"], p["ruled"], p["proposed"]) == (2, 1, 3, 1)
    assert abs(p["precision"] - 2 / 3) < 1e-9  # over RULED events only


# --------------------------------------------------------------------------- #
# #1671 — the watering SESSION: many pours, one watering
# --------------------------------------------------------------------------- #
def test_pours_within_the_gap_are_one_session_with_a_running_total(tmp_path) -> None:
    """The maintainer's shape: carry over half a cup, watch, top up two minutes later,
    and again. Three journal rows, one watering, one total."""
    from datetime import timedelta

    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    for offset, ml in ((0, 118.3), (2, 118.3), (9, 59.1)):
        log_manual("p11", ts=t0 + timedelta(minutes=offset), ml=ml, path=j)
    (s,) = sessions_for_plant("p11", path=j)
    assert s["pours"] == 3
    assert s["total_ml"] == 295.7  # = 1 1/4 cups
    assert s["span_min"] == 9.0


def test_a_pour_past_the_gap_starts_a_NEW_session(tmp_path) -> None:
    """Yesterday's watering is not part of today's. The gap is the classifier's own
    PASS_GAP_MIN, imported rather than restated so the two can never disagree."""
    from datetime import timedelta

    from tools.analytics.watering_log import SESSION_GAP_MIN, sessions_for_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p11", ts=t0, ml=118.3, path=j)
    log_manual("p11", ts=t0 + timedelta(minutes=SESSION_GAP_MIN + 1), ml=59.1, path=j)
    a, b = sessions_for_plant("p11", path=j)
    assert a["pours"] == 1 and b["pours"] == 1


def test_a_mixed_session_reports_a_FLOOR_and_says_how_many_are_missing(tmp_path):
    """A session where one pour was logged without an amount has a total that is a
    floor, not a measurement. Collapsing the two would put a short number into the dose
    corpus wearing the same shape as a real one (ADR-0028)."""
    from datetime import timedelta

    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p06", ts=t0, ml=118.3, path=j)
    log_manual("p06", ts=t0 + timedelta(minutes=3), path=j)  # no amount
    (s,) = sessions_for_plant("p06", path=j)
    assert s["pours"] == 3 - 1 and s["measured"] == 1 and s["unmeasured"] == 1
    assert s["total_ml"] == 118.3  # the floor, and `unmeasured` says it is one


def test_a_session_with_no_amounts_at_all_totals_None_never_zero(tmp_path) -> None:
    """ "Nothing was measured" and "she poured nothing" are different statements, and
    only one of them is ever true here."""
    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    log_manual("p04", ts=datetime(2026, 7, 26, tzinfo=timezone.utc), path=j)
    (s,) = sessions_for_plant("p04", path=j)
    assert s["total_ml"] is None and s["unmeasured"] == 1


def test_open_session_closes_once_she_has_walked_away(tmp_path) -> None:
    """The tally is for the plant she is standing in front of. Past the gap it becomes
    history and the card returns to its ordinary last-watered line."""
    from datetime import timedelta

    from tools.analytics.watering_log import SESSION_GAP_MIN, open_session

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p11", ts=t0, ml=118.3, path=j)
    assert open_session("p11", now=t0 + timedelta(minutes=20), path=j) is not None
    later = t0 + timedelta(minutes=SESSION_GAP_MIN + 5)
    assert open_session("p11", now=later, path=j) is None


def test_sessions_are_per_plant_never_pooled(tmp_path) -> None:
    from tools.analytics.watering_log import open_sessions_by_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p11", ts=t0, ml=118.3, path=j)
    log_manual("p06", ts=t0, ml=59.1, path=j)
    out = open_sessions_by_plant(now=t0, path=j)
    assert out["p11"]["total_ml"] == 118.3
    assert out["p06"]["total_ml"] == 59.1


def test_a_session_carries_its_start_end_and_spread(tmp_path) -> None:
    """ "When did it start, when did it end, how long was it spread over" — the three
    the maintainer asked for, on the session rather than reconstructed from rows."""
    from datetime import timedelta

    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p11", ts=t0, ml=118.3, path=j)
    log_manual("p11", ts=t0 + timedelta(minutes=12), ml=59.1, path=j)
    (s,) = sessions_for_plant("p11", path=j)
    assert s["first_ts"] == "2026-07-26T14:00:00Z"
    assert s["last_ts"] == "2026-07-26T14:12:00Z"
    assert s["span_min"] == 12.0
    assert [p["at_min"] for p in s["sequence"]] == [0.0, 12.0]
    assert s["gaps_min"] == [12.0]  # the wait between pours, not recomputed downstream


def test_the_sequence_distinguishes_even_from_tapering(tmp_path) -> None:
    """Two sessions can both total 1 1/2 cups and mean opposite things: four even
    quarters is a plant taking water steadily; 3/4 -> 1/2 -> 1/4 -> 1/8 is one that
    stopped accepting it. The total cannot tell them apart; the sequence can."""
    from datetime import timedelta

    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    for i, ml in enumerate((88.7, 88.7, 88.7, 88.7)):
        log_manual("p10", ts=t0 + timedelta(minutes=3 * i), ml=ml, path=j)
    for i, ml in enumerate((177.4, 118.3, 59.1, 29.6)):
        log_manual("p11", ts=t0 + timedelta(minutes=3 * i), ml=ml, path=j)
    assert sessions_for_plant("p10", path=j)[0]["trend"] == "flat_within_tolerance"
    assert sessions_for_plant("p11", path=j)[0]["trend"] == "monotone_decreasing"


def test_an_unmeasured_pour_leaves_the_session_TRENDLESS(tmp_path) -> None:
    """A sequence with an unknown term has no trend. Guessing one would put an
    interpretation into the corpus that no measurement supports."""
    from datetime import timedelta

    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p03", ts=t0, ml=118.3, path=j)
    log_manual("p03", ts=t0 + timedelta(minutes=2), path=j)  # no amount
    log_manual("p03", ts=t0 + timedelta(minutes=5), ml=59.1, path=j)
    (s,) = sessions_for_plant("p03", path=j)
    assert s["trend"] is None
    assert s["ml_per_min"] is None  # a floor must not masquerade as an average
    assert s["total_ml"] == 177.4 and s["unmeasured"] == 1


def test_a_single_pour_has_no_trend_and_no_rate(tmp_path) -> None:
    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    log_manual("p07", ts=datetime(2026, 7, 26, tzinfo=timezone.utc), ml=59.1, path=j)
    (s,) = sessions_for_plant("p07", path=j)
    assert s["trend"] is None and s["ml_per_min"] is None and s["span_min"] == 0.0


def test_the_rate_is_the_sessions_own_delivery_rate(tmp_path) -> None:
    from datetime import timedelta

    from tools.analytics.watering_log import sessions_for_plant

    j = _journal(tmp_path)
    t0 = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p02", ts=t0, ml=118.3, path=j)
    log_manual("p02", ts=t0 + timedelta(minutes=10), ml=118.3, path=j)
    (s,) = sessions_for_plant("p02", path=j)
    assert s["ml_per_min"] == round(236.6 / 10, 2)


def test_previous_session_is_the_last_CLOSED_one(tmp_path) -> None:
    """Asked while she is mid-session, "the previous watering" means the one before
    this — not the one she is standing in."""
    from datetime import timedelta

    from tools.analytics.watering_log import previous_session

    j = _journal(tmp_path)
    now = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p04", ts=now - timedelta(days=5), ml=118.3, path=j)
    log_manual(
        "p04", ts=now - timedelta(days=5) + timedelta(minutes=4), ml=59.1, path=j
    )
    log_manual("p04", ts=now, ml=236.6, path=j)  # today's, still open
    prev = previous_session("p04", now=now + timedelta(minutes=5), path=j)
    assert prev["total_ml"] == 177.4 and prev["span_min"] == 4.0
    assert prev["first_ts"].startswith("2026-07-21")


def test_previous_session_is_None_when_there_has_only_ever_been_one(tmp_path) -> None:
    from datetime import timedelta

    from tools.analytics.watering_log import previous_session

    j = _journal(tmp_path)
    now = datetime(2026, 7, 26, 14, 0, tzinfo=timezone.utc)
    log_manual("p09", ts=now, ml=59.1, path=j)
    assert previous_session("p09", now=now + timedelta(minutes=1), path=j) is None
