"""#1137 slice 1 — the manual watering journal. A one-tap "glug glug" writes a
``source="manual"`` event; it reads back as the latest per plant, and a torn line never
breaks the read. Absence is first-class (no journal -> no events, never a crash).
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from watering_log import latest_by_plant, load_events, log_manual


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
