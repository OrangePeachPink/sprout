"""Tests for the local-time-first formatter (#328)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tools.analytics import timefmt

_SUMMER = datetime(2026, 6, 28, 18, 14, tzinfo=timezone.utc)  # 13:14 CDT
_WINTER = datetime(2026, 1, 15, 18, 14, tzinfo=timezone.utc)  # 12:14 CST


def _has_tzdb(name: str) -> bool:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(name)
        return True
    except Exception:
        return False


def test_offset_only_is_honest_about_the_zone() -> None:
    # No tz_name -> render the numeric offset, never a guessed abbreviation.
    s = timefmt.local_first(_SUMMER, tz_offset_hours=-5)
    assert s == "2026-06-28 13:14 UTC-05:00 · UTC 18:14Z"


def test_utc_only_when_no_zone_given() -> None:
    assert timefmt.local_first(_SUMMER) == "2026-06-28 18:14 UTC · UTC 18:14Z"


def test_seconds_flag() -> None:
    s = timefmt.local_first(_SUMMER, tz_offset_hours=-5, seconds=True)
    assert s == "2026-06-28 13:14:00 UTC-05:00 · UTC 18:14:00Z"


def test_naive_input_is_assumed_utc() -> None:
    naive = datetime(2026, 6, 28, 18, 14)
    assert timefmt.local_first(naive, tz_offset_hours=-5).endswith("UTC 18:14Z")


def test_midnight_crossing_shows_the_utc_date() -> None:
    # 01:30Z on the 29th is 20:30 on the 28th local (-5): UTC date differs -> shown.
    utc = datetime(2026, 6, 29, 1, 30, tzinfo=timezone.utc)
    s = timefmt.local_first(utc, tz_offset_hours=-5)
    assert s == "2026-06-28 20:30 UTC-05:00 · UTC 2026-06-29 01:30Z"


def test_bad_tz_name_falls_back_to_offset() -> None:
    s = timefmt.local_first(_SUMMER, tz_name="Not/AZone", tz_offset_hours=-5)
    assert s == "2026-06-28 13:14 UTC-05:00 · UTC 18:14Z"


@pytest.mark.skipif(
    not _has_tzdb("America/Chicago"), reason="IANA tz database unavailable"
)
def test_iana_zone_renders_true_abbreviation() -> None:
    # The AC's headline example: a real DST-correct abbreviation when tz_name is set.
    assert timefmt.local_first(_SUMMER, tz_name="America/Chicago") == (
        "2026-06-28 13:14 CDT · UTC 18:14Z"
    )
    assert timefmt.local_first(_WINTER, tz_name="America/Chicago").split(" · ")[0] == (
        "2026-01-15 12:14 CST"
    )
