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
