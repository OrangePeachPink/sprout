"""Local-time-first in the Lab Notebook views (#328 slice 3).

The lab catalog + detail render capture timestamps through ``_fmt_when``, which now
formats local-first (host timezone) with UTC secondary. Host-tz-dependent, so these
assert *shape*, not a fixed abbreviation.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import experiments_catalog as cat
import timefmt

_UTC = datetime(2026, 6, 28, 18, 14, tzinfo=timezone.utc)


def test_local_first_system_shape() -> None:
    s = timefmt.local_first_system(_UTC)
    assert " · UTC " in s and "18:14Z" in s  # local first, UTC secondary
    assert s.startswith("2026-06-")  # a date leads


def test_local_first_system_seconds() -> None:
    assert "18:14:00Z" in timefmt.local_first_system(_UTC, seconds=True)


def test_fmt_when_is_local_first() -> None:
    s = cat._fmt_when("2026-06-28T18:14:00Z")
    assert " · UTC " in s and "18:14Z" in s
    assert cat._fmt_when(None) == "—"
    assert cat._fmt_when("not-a-date") == "not-a-date"  # unparseable passes through
