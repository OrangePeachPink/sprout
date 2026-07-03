"""Tests for tagged interior-ambient display (#562, ADR-0023 v2): the card's
context values only ever render WITH their source tag - build_context() exposes
value+tag together or nothing at all (the "no untagged display" AC).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=test123  run=ctxtest\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,sensor_id,"
    "raw_value,quality_flag,temp_context_c,rh_context_pct,payload\n"
)


def _soil(
    ts: str,
    sid: str,
    raw: int,
    *,
    temp: str = "",
    rh: str = "",
    payload: str = "level=well watered;gpio=36",
) -> str:
    local = ts.replace("Z", "")
    return f"plants.soil,{ts},{local},sess1,{sid},{raw},OK,{temp},{rh},{payload}\n"


def test_tagged_context_reaches_the_card(tmp_path: Path) -> None:
    log = tmp_path / "a.csv"
    log.write_text(
        _HEADER
        + _COLS
        + _soil(
            "2026-07-03T00:00:30.000Z",
            "s1",
            1500,
            temp="21.84",
            rh="48.10",
            payload="level=well watered;gpio=36;context_source=sht45_onrig",
        ),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(log)]))
    s1 = next(s for s in ctx["sensors"] if s["id"] == "s1")
    assert s1["ambient"] == {
        "temp_c": 21.84,
        "rh_pct": 48.10,
        "source": "sht45_onrig",
    }


def test_untagged_context_values_never_render(tmp_path: Path) -> None:
    """The fence in the display layer: a context value that somehow lost its
    tag (hand-edited CSV, foreign tool) is NOT surfaced - a value without
    provenance must not render as if it had some."""
    log = tmp_path / "b.csv"
    log.write_text(
        _HEADER
        + _COLS
        + _soil("2026-07-03T00:00:30.000Z", "s1", 1500, temp="21.84", rh="48.10"),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(log)]))
    s1 = next(s for s in ctx["sensors"] if s["id"] == "s1")
    assert s1["ambient"] is None


def test_rows_without_context_expose_none(tmp_path: Path) -> None:
    log = tmp_path / "c.csv"
    log.write_text(
        _HEADER + _COLS + _soil("2026-07-03T00:00:30.000Z", "s1", 1500),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(log)]))
    assert ctx["sensors"][0]["ambient"] is None
