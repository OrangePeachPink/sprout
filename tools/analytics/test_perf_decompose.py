"""#953 first-load / range-switch decomposition.

The maintainer's lived report - first paint 15-18 s, a range switch ~10 s - has to be
*attributable* (parse vs cache-merge vs filter vs build_context) before the right phase
is optimized. `_context` attaches a per-phase millisecond breakdown to
`ctx['meta']['perf']`, and a full build slow enough to matter logs a one-line
decomposition to the server console she already watches - with fast cached polls staying
silent (threshold-gated), so the log captures the slow events, not the live view's poll.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import serve
from serve import _context, _perf_log

_HEADER = "# fw=0.7.0  git=t  device_id=classic  session_id=s1\n"
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _log(tmp_path: Path) -> Path:
    rows = "".join(
        f"plants.soil,2026-07-05T00:{m:02d}:30.000Z,x,s1,classic,s1,{2400 + m},OK,"
        f"level=DRY;gpio=35\n"
        for m in range(30)
    )
    p = tmp_path / "classic_20260705_000000.csv"
    p.write_text(_HEADER + _COLS + rows, encoding="utf-8")
    return p


def test_context_attaches_phase_breakdown(tmp_path: Path) -> None:
    ctx = _context([str(_log(tmp_path))])
    perf = ctx["meta"]["perf"]
    # every phase _context walks is present and integer-millisecond
    assert set(perf["phases"]) == {"select", "load", "filter", "build"}
    assert all(isinstance(v, int) for v in perf["phases"].values())
    # the counts that make a slow number interpretable
    assert perf["readings"] == 30
    assert perf["files"] == 1
    # #953 slice 2: the load phase carries its device-fetch portion; a tethered-only
    # corpus (no served devices) has none, so the split is honestly zero here.
    assert perf["fetch_ms"] == 0


def test_perf_log_stays_silent_below_threshold(tmp_path: Path, monkeypatch) -> None:
    # a fast build (a handful of readings) must not spam the console - this is what
    # keeps the live view's every-few-seconds poll quiet.
    ctx = _context([str(_log(tmp_path))])
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setattr(serve, "_PERF_MIN_MS", 1500)
    _perf_log(ctx, "serialize", 0.001, "7d")
    assert buf.getvalue() == ""


def test_perf_log_fires_for_a_slow_build(tmp_path: Path, monkeypatch) -> None:
    # threshold lowered to 0 → the slow event we actually want to capture logs one line
    # with the full phase decomposition, the range, and the reading/file counts.
    ctx = _context([str(_log(tmp_path))])
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setattr(serve, "_PERF_MIN_MS", 0)
    _perf_log(ctx, "serialize", 0.002, "30d")
    out = buf.getvalue()
    assert out.startswith("[perf] range=30d ")
    for phase in ("select=", "load=", "filter=", "build=", "serialize=", "total="):
        assert phase in out
    assert "30 readings" in out and "1 files" in out


def test_perf_log_annotates_load_with_device_fetch(monkeypatch) -> None:
    # #953 slice 2: when a served fleet makes load fetch-bound, the [perf] line marks
    # the fetch portion ON the load phase (a sub-component, NOT summed into total) — the
    # signal that separated the real ~14s cause (device timeouts) from re-parse.
    ctx = {
        "meta": {
            "perf": {
                "phases": {"select": 3, "load": 14000, "filter": 20, "build": 250},
                "readings": 10000,
                "files": 13,
                "fetch_ms": 13800,
            }
        }
    }
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setattr(serve, "_PERF_MIN_MS", 0)
    _perf_log(ctx, "serialize", 0.005, "12h")
    out = buf.getvalue()
    assert "load=14000ms(fetch 13800ms)" in out  # annotation on the load phase
    # the fetch is NOT double-counted into total (14000+... not +13800)
    assert "total=14278ms" in out


def test_perf_log_no_perf_meta_is_a_noop(monkeypatch) -> None:
    # a ctx without the perf block (an old/hand-built one) must never raise
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stderr", buf)
    monkeypatch.setattr(serve, "_PERF_MIN_MS", 0)
    _perf_log({"meta": {}}, "render", 5.0, "all")
    assert buf.getvalue() == ""


if __name__ == "__main__":
    import tempfile

    class _MP:
        def setattr(self, obj, name, val):
            setattr(obj, name, val)

    with tempfile.TemporaryDirectory() as d:
        test_context_attaches_phase_breakdown(Path(d))
    print("  PASS  test_context_attaches_phase_breakdown")
    with tempfile.TemporaryDirectory() as d:
        test_perf_log_stays_silent_below_threshold(Path(d), _MP())
    print("  PASS  test_perf_log_stays_silent_below_threshold")
    with tempfile.TemporaryDirectory() as d:
        test_perf_log_fires_for_a_slow_build(Path(d), _MP())
    print("  PASS  test_perf_log_fires_for_a_slow_build")
    test_perf_log_no_perf_meta_is_a_noop(_MP())
    print("  PASS  test_perf_log_no_perf_meta_is_a_noop")
    sys.stderr = sys.__stderr__
    print("All checks passed.")
