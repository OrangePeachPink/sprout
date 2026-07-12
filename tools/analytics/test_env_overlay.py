"""#922 — the opt-in environment overlay on the per-plant trajectory.

Data half: each trajectory dataset carries a per-plant `env_points` series (temp/RH,
time-aligned to the moisture points) + a `has_env` flag so the surface offers the toggle
only when context exists. The overlay is context, NOT cause (moisture stays the hero;
env is a faint second layer that never asserts a link). The value-verdict (which columns
earn their space) is the companion doc, docs/analysis/env-value-verdict.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=test123  run=envtest\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,sensor_id,"
    "raw_value,quality_flag,temp_context_c,rh_context_pct,payload\n"
)


def _soil(ts: str, raw: int, *, temp: str = "", rh: str = "", ctx: bool = False) -> str:
    local = ts.replace("Z", "")
    pay = "level=well watered;gpio=36"
    if ctx:
        pay += ";context_source=sht45_onrig"
    return f"plants.soil,{ts},{local},sess1,s1,{raw},OK,{temp},{rh},{pay}\n"


def _traj(ctx, rows):
    log = ctx / "a.csv"
    log.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    dsets = build_context(parse_files([str(log)]))["trajectory"]["datasets"]
    return next(d for d in dsets if d["id"] == "s1")


def test_env_points_are_time_aligned_and_flagged(tmp_path: Path) -> None:
    d = _traj(
        tmp_path,
        [
            _soil("2026-07-03T00:00:30.000Z", 1500, temp="21.8", rh="48.1", ctx=True),
            _soil("2026-07-03T00:30:30.000Z", 1520, temp="23.0", rh="45.0", ctx=True),
            _soil("2026-07-03T01:00:30.000Z", 1540, temp="24.5", rh="43.2", ctx=True),
        ],
    )
    assert d["has_env"] is True  # context exists -> the toggle is offered
    # env_points run parallel to the moisture points, same x-axis (time-aligned)
    assert len(d["env_points"]) == len(d["points"])
    xs_m = [p["x"] for p in d["points"]]
    xs_e = [p["x"] for p in d["env_points"]]
    assert xs_m == xs_e
    assert d["env_points"][0]["temp_c"] == 21.8
    assert d["env_points"][-1]["rh_pct"] == 43.2


def test_no_context_means_no_toggle_and_null_points(tmp_path: Path) -> None:
    d = _traj(
        tmp_path,
        [
            _soil("2026-07-03T00:00:30.000Z", 1500),  # no temp/rh, no context_source
            _soil("2026-07-03T00:30:30.000Z", 1520),
        ],
    )
    assert d["has_env"] is False  # honest-empty: the overlay toggle never appears
    assert all(p["temp_c"] is None and p["rh_pct"] is None for p in d["env_points"])


# --------------------------------------------------------------------------- #
# the surface: opt-in, hero-preserving, context-not-cause (structure assertions)
# --------------------------------------------------------------------------- #
_TPL = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
    encoding="utf-8"
)


def test_overlay_is_opt_in_and_labelled_context_not_cause() -> None:
    assert "let __envOverlay = false;" in _TPL  # default OFF (never on the glance)
    assert "context, not cause" in _TPL  # the honesty label the toggle carries
    # the env series ride a SEPARATE right axis (moisture keeps the left axis = hero)
    assert "yAxisID:'env'" in _TPL
    assert (
        "d.id===sid" in _TPL and "has_env" in _TPL
    )  # toggle gated on the plant's flag
