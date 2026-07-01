"""Tests for the source-adapter seam (#277).

Covers TetheredAdapter's behavior-preserving wrap of parse_files()/gather_inputs(),
so refactoring dashboard.py/serve.py's call sites onto the seam is provably a
no-behavior-change move.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import parse_files
from source_adapter import TetheredAdapter

_COLS = "record_type,timestamp_utc,session_id,raw_value,quality_flag,payload"
_ROW = "plants.soil,2026-06-27T00:00:30.000Z,sess001,1312,OK,level=well watered;gpio=36"
_HEADER = "# log_start_utc=2026-06-27T00:00:00Z  tz_offset=-05:00\n"


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "one.csv"
    p.write_text(f"{_HEADER}{_COLS}\n{_ROW}\n", encoding="utf-8")
    return p


def test_explicit_inputs_match_parse_files_directly(tmp_path: Path) -> None:
    csv = _write(tmp_path)
    direct = parse_files([str(csv)])
    via_adapter = TetheredAdapter().load([str(csv)])
    assert len(via_adapter.readings) == len(direct.readings) == 1
    assert via_adapter.readings[0].raw_value == direct.readings[0].raw_value
    assert via_adapter.sources == direct.sources


def test_no_inputs_uses_the_injected_discover_callable(tmp_path: Path) -> None:
    csv = _write(tmp_path)
    calls = {"n": 0}

    def fake_discover() -> list[str]:
        calls["n"] += 1
        return [str(csv)]

    data = TetheredAdapter(discover=fake_discover).load()
    assert calls["n"] == 1
    assert len(data.readings) == 1


def test_no_inputs_and_no_discover_is_empty_not_raise() -> None:
    data = TetheredAdapter().load()
    assert data.readings == [] and data.segments == []


def test_explicit_inputs_bypass_discover(tmp_path: Path) -> None:
    csv = _write(tmp_path)
    calls = {"n": 0}

    def fake_discover() -> list[str]:
        calls["n"] += 1
        return ["should-not-be-used.csv"]

    data = TetheredAdapter(discover=fake_discover).load([str(csv)])
    assert calls["n"] == 0  # explicit inputs win; discover never called
    assert len(data.readings) == 1
