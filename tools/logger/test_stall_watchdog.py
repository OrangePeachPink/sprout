"""Tests for the serial-stall watchdog (#417).

The 2026-06-30 evidence: the logger sat quiet for 9 minutes because a *silent*
stall (port open, device not streaming) makes `readline()` return b"" forever and
the old loop only reconnected on a `SerialException`. These tests pin the new
behaviour: detect the stall from a clock, force a reconnect, and mark an honest
`# reconnect` seam so the hole is queryable, never silently stitched.
"""

from __future__ import annotations

from pathlib import Path

from tools.logger import plants_logger as pl


class _Clock:
    """A hand-cranked monotonic clock so the watchdog tests never touch wall time."""

    def __init__(self, t0: float = 1000.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #


def test_stall_timeout_keys_off_cadence_with_a_floor() -> None:
    assert pl.stall_timeout_s(None) == pl.STALL_FLOOR_S  # unknown cadence -> floor
    assert pl.stall_timeout_s(0) == pl.STALL_FLOOR_S
    assert pl.stall_timeout_s(5000) == pl.STALL_FLOOR_S  # 2x5s=10s < floor -> floor
    assert pl.stall_timeout_s(60000) == 120.0  # 2x60s dominates the floor


def test_cadence_ms_from_header() -> None:
    hdr = ["# fw=0.7.0  git=abc  cadence_ms=30000  cadence_src=nvs", "# device_id=x"]
    assert pl.cadence_ms_from_header(hdr) == 30000
    assert pl.cadence_ms_from_header(["# no cadence here"]) is None


def test_watchdog_trips_only_after_the_timeout() -> None:
    clk = _Clock()
    wd = pl.StallWatchdog(90.0, clock=clk)
    assert not wd.stalled()
    clk.advance(89)
    assert not wd.stalled()
    clk.advance(2)  # now 91s since last data
    assert wd.stalled()
    assert wd.gap_s() == 91


def test_watchdog_mark_data_and_retune() -> None:
    clk = _Clock()
    wd = pl.StallWatchdog(90.0, clock=clk)
    clk.advance(200)
    assert wd.stalled()
    wd.mark_data()  # a fresh row resets the clock
    assert not wd.stalled()
    wd.retune(10.0)  # a faster cadence tightens the window
    clk.advance(11)
    assert wd.stalled()


def test_reconnect_seam_line_is_honest() -> None:
    from datetime import datetime, timezone

    now = datetime(2026, 6, 30, 18, 34, 0, tzinfo=timezone.utc)
    line = pl.reconnect_seam_line(541.0, now, "stall-watchdog")
    assert line.startswith("# reconnect")
    assert "gap_s=541.0" in line
    assert "reason=stall-watchdog" in line
    assert "2026-06-30T18:34:00" in line


def test_write_comment_lands_in_the_segment(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    csvlog = pl.RotatingCsv(str(tmp_path))
    assert csvlog.write_comment("# reconnect gap_s=1") is None  # no segment open yet
    dev = _dev_dict()
    csvlog.write(dev, 1, datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc))
    path = csvlog.write_comment("# reconnect  gap_s=120.0  reason=stall-watchdog")
    assert path is not None
    assert "# reconnect  gap_s=120.0  reason=stall-watchdog" in Path(path).read_text()


# --------------------------------------------------------------------------- #
# integration: full detect -> reconnect -> seam, with an injected fake serial
# --------------------------------------------------------------------------- #


def _dev_dict() -> dict:
    return {
        "record_type": "plants.soil",
        "session_id": "sess001",
        "device_id": "plants_esp32_test",
        "fw": "0.7.0",
        "millis_ms": "30000",
        "sensor_model": "UMLIFE_v2_TLC555",
        "sensor_id": "s3",
        "sensor_position": "origplant",
        "channel": "soil_moisture",
        "raw_value": "1500",
        "value": "",
        "unit": "",
        "quality_flag": "OK",
        "payload": "level=OK",
        "_crc_ok": None,
    }


class _FakeSerial:
    """Replays a script of readline() bytes, advancing the shared clock each read so
    a run of empty reads crosses the stall threshold deterministically."""

    def __init__(self, script: list, clock: _Clock, advance_per_read: float) -> None:
        self._script = list(script)
        self._clock = clock
        self._advance = advance_per_read

    def readline(self) -> bytes:
        self._clock.advance(self._advance)
        if not self._script:
            return b""  # idle: port open, nothing streaming
        item = self._script.pop(0)
        if callable(item):
            return item()  # e.g. raise KeyboardInterrupt to stop the logger
        return item

    def close(self) -> None:
        pass


def test_run_detects_silent_stall_reconnects_and_marks_seam(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(pl, "serial_lock", None)  # no lock-file side effects
    monkeypatch.setattr(pl, "archive_logs", None)  # no git archive side effects
    clk = _Clock()

    row = ",".join(_dev_dict()[c] for c in pl.DEVICE_COLS).encode("latin-1") + b"\n"
    header = b"# fw=0.7.0  git=abc  cadence_ms=30000\n"

    def _stop() -> bytes:
        raise KeyboardInterrupt

    # serial #1: header + one row, then silence (advance 100 s/read > 90 s floor).
    s1 = _FakeSerial([header, row], clk, advance_per_read=100.0)
    # serial #2 (after reconnect): stop cleanly so the test terminates.
    s2 = _FakeSerial([_stop], clk, advance_per_read=0.0)
    serials = iter([s1, s2])

    pl.run(
        "COM_TEST",
        19200,
        str(tmp_path),
        0,
        open_fn=lambda: next(serials),
        clock=clk,
        sleep=lambda *_: None,
    )

    seg = next(tmp_path.glob("*.csv"))
    text = seg.read_text()
    assert "# reconnect" in text and "reason=stall-watchdog" in text
    assert "plants.soil" in text  # the real row was still logged before the stall
