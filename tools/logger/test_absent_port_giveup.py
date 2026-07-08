"""#813 (F5-B) — the monitor bounds its absent-port retry: exponential backoff,
an announced give-up after a window of continuous absence, and an honest exit
code. A port that returns within the window resumes (a transient blip never kills
the monitor, #691).
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plants_logger as pl


class _Boom(Exception):
    """A sentinel raised from a fake port's readline to break out of run() once
    the test has proven the connection was (re)established."""


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch):
    # neutralise the advisory serial lock (it writes to the repo logs dir) + keep
    # the give-up window small so the bounded loop resolves fast.
    monkeypatch.setattr(pl, "serial_lock", None)
    monkeypatch.setattr(pl, "PORT_ABSENT_GIVEUP_S", 10.0)
    monkeypatch.setattr(pl, "PORT_RETRY_BASE_S", 1.0)
    monkeypatch.setattr(pl, "PORT_RETRY_MAX_S", 4.0)


def test_gives_up_after_bounded_absence(tmp_path, capsys) -> None:
    # open always fails; the clock marches past the give-up window
    clk = itertools.count(0, 5)  # watchdog-init=0, then failures at 5, 10, 15
    sleeps: list[float] = []

    def open_fn():
        raise OSError("no such port")

    code = pl.run(
        "COMX",
        19200,
        str(tmp_path),
        0,
        open_fn=open_fn,
        clock=lambda: next(clk),
        sleep=sleeps.append,
    )
    assert code == pl.GIVE_UP_EXIT  # honest, non-zero, distinct exit
    out = capsys.readouterr().out
    assert "COMX absent for" in out and "stopping" in out  # announced, never silent
    # exponential backoff on the way there: 1s then 2s (base doubling, capped)
    assert sleeps[:2] == [1.0, 2.0]


def test_transient_blip_resumes_without_giving_up(tmp_path) -> None:
    # two failed opens (a blip), then the port returns -> we connect and read.
    # If the blip had counted toward give-up we'd get GIVE_UP_EXIT, not a connect.
    opens = {"n": 0}
    clk = itertools.count(0, 3)  # never reaches the 10s window before the 3rd open

    class _FakePort:
        def readline(self):
            raise _Boom()  # break out once we've proven we connected

    def open_fn():
        opens["n"] += 1
        if opens["n"] <= 2:
            raise OSError("usb blip")
        return _FakePort()

    with pytest.raises(_Boom):  # reached the read loop == connection survived
        pl.run(
            "COMX",
            19200,
            str(tmp_path),
            0,
            open_fn=open_fn,
            clock=lambda: next(clk),
            sleep=lambda *_a: None,
        )
    assert opens["n"] == 3  # blipped twice, connected on the third — no give-up


def test_backoff_never_exceeds_the_cap(tmp_path, capsys) -> None:
    clk = itertools.count(0, 1)  # slow clock: many retries before the window
    sleeps: list[float] = []
    pl.run(
        "COMX",
        19200,
        str(tmp_path),
        0,
        open_fn=lambda: (_ for _ in ()).throw(OSError("gone")),
        clock=lambda: next(clk),
        sleep=sleeps.append,
    )
    assert max(sleeps) <= pl.PORT_RETRY_MAX_S  # capped, never unbounded growth
    assert sleeps[:3] == [1.0, 2.0, 4.0]  # 1 -> 2 -> 4, then capped at 4
