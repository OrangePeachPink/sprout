"""#900 (loud-failure slice) - archival failures and unavailability must SURFACE, never
be silently swallowed. Archival is the bounded-growth mechanism (closed segments gzip
out of logs/); when it silently fails or is unavailable, logs/ grows and the
operator sees nothing. Health goes to STDERR (the channel that survives the background
worker's capped log, #968); stdout is DEVNULL on the worker, where the old print() was
lost.

Root-causing the specific 07-07 stall + the backlog catch-up need a bench window; making
the signal loud (this slice) does not.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


class _Boom:
    @staticmethod
    def archive(**_kw):
        raise RuntimeError("archive dir gone")


class _Ok:
    calls = 0

    @classmethod
    def archive(cls, **_kw):
        cls.calls += 1


# --------------------------------------------------------------------------- #
# plants_logger._archive_step (module-level, function-based logger)
# --------------------------------------------------------------------------- #
def test_plants_archive_failure_is_loud_and_counted(monkeypatch, capsys) -> None:
    import plants_logger as pl

    pl._archive_fail_count = 0
    monkeypatch.setattr(pl, "archive_logs", _Boom)
    pl._archive_step("logs")
    err = capsys.readouterr().err
    assert "archive step FAILED" in err
    assert "1x" in err  # counted
    assert "accumulate in logs/" in err  # says what a silent lag would have hidden
    pl._archive_step("logs")
    assert (
        "2x" in capsys.readouterr().err
    )  # persistent lag climbs, never resets to silent


def test_plants_archive_success_clears_the_streak(monkeypatch, capsys) -> None:
    import plants_logger as pl

    pl._archive_fail_count = 5
    monkeypatch.setattr(pl, "archive_logs", _Ok)
    pl._archive_step("logs")
    assert pl._archive_fail_count == 0  # a clean run clears the streak
    assert capsys.readouterr().err == ""  # a healthy archive is quiet


def test_plants_archive_unavailable_is_stated_once(monkeypatch, capsys) -> None:
    import plants_logger as pl

    pl._archive_unavailable_warned = False
    monkeypatch.setattr(pl, "archive_logs", None)
    pl._archive_step("logs")
    assert "archival UNAVAILABLE" in capsys.readouterr().err  # never a silent no-op
    pl._archive_step("logs")
    assert capsys.readouterr().err == ""  # stated once, not on every step


# --------------------------------------------------------------------------- #
# fleet_logger.FleetLogger._archive (class-based logger)
# --------------------------------------------------------------------------- #
def _fleet(tmp_path):
    import fleet_logger as fl

    return fl, fl.FleetLogger(logdir=str(tmp_path), registry=[])


def test_fleet_archive_failure_is_loud_and_counted(
    monkeypatch, capsys, tmp_path
) -> None:
    fl, lg = _fleet(tmp_path)
    monkeypatch.setattr(fl, "archive_logs", _Boom)
    lg._archive()
    err = capsys.readouterr().err
    assert "archive step FAILED" in err and "1x" in err
    lg._archive()
    assert "2x" in capsys.readouterr().err
    assert lg._archive_fails == 2


def test_fleet_archive_unavailable_is_stated_once(
    monkeypatch, capsys, tmp_path
) -> None:
    fl, lg = _fleet(tmp_path)
    monkeypatch.setattr(fl, "archive_logs", None)
    lg._archive()
    assert "archival UNAVAILABLE" in capsys.readouterr().err
    lg._archive()
    assert capsys.readouterr().err == ""  # once, never per-poll spam
