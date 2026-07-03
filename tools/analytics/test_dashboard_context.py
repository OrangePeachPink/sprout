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


# --------------------------------------------------------------------------- #
# #577: pressure render — the EXTERIOR-family exception (ADR-0023 §3)
# --------------------------------------------------------------------------- #

# parse_v1 maps columns by name, so a pressure column + its payload tag is all
# that's needed - independent of the fill layer (#567) that produces them live.
_PCOLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,sensor_id,"
    "raw_value,quality_flag,pressure_context_hpa,payload\n"
)


def _psoil(ts: str, sid: str, raw: int, *, hpa: str = "", tag: str = "") -> str:
    local = ts.replace("Z", "")
    payload = "level=well watered;gpio=36"
    if tag:
        payload += f";pressure_context_source={tag}"
    return f"plants.soil,{ts},{local},sess1,{sid},{raw},OK,{hpa},{payload}\n"


def test_tagged_pressure_reaches_the_card(tmp_path: Path) -> None:
    log = tmp_path / "p.csv"
    log.write_text(
        _HEADER
        + _PCOLS
        + _psoil(
            "2026-07-03T00:00:30.000Z",
            "s1",
            1500,
            hpa="1013.2",
            tag="weather_openmeteo",
        ),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(log)]))
    s1 = next(s for s in ctx["sensors"] if s["id"] == "s1")
    assert s1["pressure"] == {"hpa": 1013.2, "source": "weather_openmeteo"}
    # exterior pressure is kept SEPARATE from the interior ambient block
    assert s1["ambient"] is None


def test_untagged_pressure_value_never_renders(tmp_path: Path) -> None:
    """Same no-untagged-display fence as interior: a pressure value that lost
    its tag (hand-edited CSV) is not surfaced - honest provenance or nothing."""
    log = tmp_path / "q.csv"
    log.write_text(
        _HEADER + _PCOLS + _psoil("2026-07-03T00:00:30.000Z", "s1", 1500, hpa="1013.2"),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(log)]))
    assert next(s for s in ctx["sensors"] if s["id"] == "s1")["pressure"] is None


def test_no_pressure_column_exposes_none(tmp_path: Path) -> None:
    # a pre-#567 log with no pressure at all -> honest None, never fabricated
    log = tmp_path / "r.csv"
    log.write_text(
        _HEADER + _COLS + _soil("2026-07-03T00:00:30.000Z", "s1", 1500),
        encoding="utf-8",
    )
    assert build_context(parse_files([str(log)]))["sensors"][0]["pressure"] is None


def test_pressure_and_interior_render_independently(tmp_path: Path) -> None:
    """A row can carry BOTH an interior ambient fill and the exterior pressure
    exception - each renders on its own line with its own tag (ADR-0023: the
    two families never merge into one display)."""
    log = tmp_path / "s.csv"
    cols = (
        "record_type,timestamp_utc,timestamp_local,session_id,sensor_id,"
        "raw_value,quality_flag,temp_context_c,rh_context_pct,"
        "pressure_context_hpa,payload\n"
    )
    ts = "2026-07-03T00:00:30.000Z"
    row = (
        f"plants.soil,{ts},{ts[:-1]},sess1,s1,1500,OK,21.84,48.10,1013.2,"
        "level=well watered;gpio=36;context_source=sht45_onrig;"
        "pressure_context_source=weather_openmeteo\n"
    )
    log.write_text(_HEADER + cols + row, encoding="utf-8")
    s1 = next(
        s for s in build_context(parse_files([str(log)]))["sensors"] if s["id"] == "s1"
    )
    assert s1["ambient"]["source"] == "sht45_onrig"
    assert s1["pressure"]["source"] == "weather_openmeteo"
    assert s1["ambient"]["temp_c"] == 21.84 and s1["pressure"]["hpa"] == 1013.2
