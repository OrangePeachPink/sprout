"""Tests for the windowed band-movement substrate (#626, PRD-0007 slice 2).

Readings are driven through the real parse boundary (CSV -> parse_files) so the
band comes from the device-emitted ``payload.level`` exactly as it does live.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from band_movement import REWATER_WET_JUMP, as_dict, band_movements
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=test  run=movement\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(ts, device, sensor, raw, level, quality="OK"):
    payload = f"level={level};gpio=36" if level is not None else "gpio=36"
    return (
        f"plants.soil,{ts},{ts.replace('Z', '')},sess1,{device},"
        f"{sensor},{raw},{quality},{payload}\n"
    )


def _parse(tmp_path: Path, rows: list[str]):
    p = tmp_path / "m.csv"
    p.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    return parse_files([str(p)]).readings


def _t(mins: int) -> str:
    """The INPUT timestamp (millis precision, as the wire carries it)."""
    return f"2026-07-04T00:{mins:02d}:30.000Z"


def _out(mins: int) -> str:
    """The OUTPUT timestamp - the canonical second-precision Z the substrate emits
    (matching the dashboard's last_seen_utc formatting)."""
    return f"2026-07-04T00:{mins:02d}:30Z"


# --------------------------------------------------------------------------- #
# current / span / transitions
# --------------------------------------------------------------------------- #


def test_current_is_the_latest_band_bearing_reading(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 3000, "air-dry"),
            _row(_t(1), "d1", "s1", 1500, "well watered"),
        ],
    )
    (m,) = band_movements(rs)
    assert m.current == {"band": "well watered", "raw": 1500, "ts": _out(1)}
    assert m.n == 2


def test_span_is_measured_in_bands_wettest_and_driest_reached(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 1600, "well watered"),  # wet
            _row(_t(1), "d1", "s1", 2900, "DRY"),  # dry
            _row(_t(2), "d1", "s1", 1800, "OK"),  # mid
        ],
    )
    (m,) = band_movements(rs)
    assert m.driest == "DRY"
    assert m.wettest == "well watered"
    # DRY idx 1, well watered idx 4 -> span 3
    assert m.span == 3


def test_never_moving_band_has_zero_span(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [_row(_t(0), "d1", "s1", 1800, "OK"), _row(_t(1), "d1", "s1", 1790, "OK")],
    )
    (m,) = band_movements(rs)
    assert m.span == 0
    assert m.driest == m.wettest == "OK"


def test_transitions_are_first_plus_each_change_not_every_reading(
    tmp_path: Path,
) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 1800, "OK"),
            _row(_t(1), "d1", "s1", 1790, "OK"),  # no change - not a step
            _row(_t(2), "d1", "s1", 2900, "DRY"),  # change
            _row(_t(3), "d1", "s1", 2100, "needs water"),  # change
        ],
    )
    (m,) = band_movements(rs)
    assert m.transitions == [
        {"ts": _out(0), "band": "OK"},
        {"ts": _out(2), "band": "DRY"},
        {"ts": _out(3), "band": "needs water"},
    ]


def test_readings_are_ordered_by_time_before_aggregation(tmp_path: Path) -> None:
    # rows arrive out of order; the trail must still read chronologically
    rs = _parse(
        tmp_path,
        [
            _row(_t(2), "d1", "s1", 2900, "DRY"),
            _row(_t(0), "d1", "s1", 1600, "well watered"),
            _row(_t(1), "d1", "s1", 1800, "OK"),
        ],
    )
    (m,) = band_movements(rs)
    assert [t["band"] for t in m.transitions] == ["well watered", "OK", "DRY"]
    assert m.current["ts"] == _out(2)


# --------------------------------------------------------------------------- #
# R7 honesty: silent / band-less readings carry no movement
# --------------------------------------------------------------------------- #


def test_no_signal_and_bandless_readings_are_excluded(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 1800, "OK"),
            _row(_t(1), "d1", "s1", 0, None, quality="NO_SIGNAL"),  # no signal
            _row(_t(2), "d1", "s1", 1810, None),  # no level -> no band
        ],
    )
    (m,) = band_movements(rs)
    assert m.n == 1  # only the OK reading counted
    assert m.current["band"] == "OK"


def test_entity_with_only_silent_readings_yields_no_aggregation(
    tmp_path: Path,
) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 0, None, quality="NO_SIGNAL"),
            _row(_t(1), "d1", "s1", 1810, None),
        ],
    )
    assert band_movements(rs) == []  # nothing invented from a silent channel


# --------------------------------------------------------------------------- #
# R8 fencing + identity coalescing
# --------------------------------------------------------------------------- #


def test_two_devices_do_not_merge(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 1800, "OK"),
            _row(_t(0), "d2", "s1", 2900, "DRY"),
        ],
    )
    ms = band_movements(rs)
    assert [m.key for m in ms] == [("d1", "s1"), ("d2", "s1")]


def test_canonical_coalesces_a_renamed_board(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "old-id", "s1", 2900, "DRY"),
            _row(_t(1), "new-id", "s1", 1600, "well watered"),
        ],
    )
    canon = {"old-id": "new-id"}.get
    ms = band_movements(rs, canonical=lambda d: canon(d, d))
    # one coalesced entity, whole history, keyed on the live id
    assert len(ms) == 1
    m = ms[0]
    assert m.key == ("new-id", "s1")
    assert m.n == 2
    assert m.driest == "DRY" and m.wettest == "well watered"


# --------------------------------------------------------------------------- #
# re-water detection + the since-rewater window
# --------------------------------------------------------------------------- #


def test_sharp_wet_jump_landing_wet_is_a_detected_rewater(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 2900, "DRY"),  # idx 1
            _row(_t(1), "d1", "s1", 1600, "well watered"),  # idx 4 -> jump 3, lands wet
        ],
    )
    (m,) = band_movements(rs)
    assert m.rewater == {"ts": _out(1), "source": "detected"}


def test_small_wiggle_is_not_a_rewater(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 2100, "needs water"),  # idx 2
            _row(_t(1), "d1", "s1", 1800, "OK"),  # idx 3 -> jump 1 < threshold
        ],
    )
    (m,) = band_movements(rs)
    assert REWATER_WET_JUMP == 2
    assert m.rewater is None


def test_dry_side_jump_not_landing_wet_is_not_a_rewater(tmp_path: Path) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 3200, "air-dry"),  # idx 0
            _row(
                _t(1), "d1", "s1", 2100, "needs water"
            ),  # idx 2 -> jump 2 but lands dry
        ],
    )
    (m,) = band_movements(rs)
    assert m.rewater is None  # jump big enough, but didn't land at OK-or-wetter


def test_since_rewater_window_restricts_to_after_the_detected_event(
    tmp_path: Path,
) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 2900, "DRY"),  # before
            _row(_t(1), "d1", "s1", 1600, "well watered"),  # the re-water
            _row(_t(2), "d1", "s1", 1800, "OK"),  # after
        ],
    )
    (m,) = band_movements(rs, since_rewater=True)
    # only the re-water reading and after -> driest is OK, not DRY
    assert m.n == 2
    assert m.driest == "OK"
    assert m.transitions[0] == {"ts": _out(1), "band": "well watered"}


def test_since_rewater_omits_an_entity_with_no_detected_rewater(
    tmp_path: Path,
) -> None:
    rs = _parse(
        tmp_path,
        [
            _row(_t(0), "d1", "s1", 1800, "OK"),
            _row(_t(1), "d1", "s1", 1790, "OK"),
        ],
    )
    assert band_movements(rs, since_rewater=True) == []  # honest absence, not "all"


# --------------------------------------------------------------------------- #
# shape
# --------------------------------------------------------------------------- #


def test_as_dict_is_json_ready(tmp_path: Path) -> None:
    rs = _parse(tmp_path, [_row(_t(0), "d1", "s1", 1800, "OK")])
    (m,) = band_movements(rs)
    d = as_dict(m)
    assert d == {
        "device_id": "d1",
        "sensor_id": "s1",
        "n": 1,
        "current": {"band": "OK", "raw": 1800, "ts": _out(0)},
        "driest": "OK",
        "wettest": "OK",
        "span": 0,
        "transitions": [{"ts": _out(0), "band": "OK"}],
        "rewater": None,
    }


def test_empty_input_is_empty(tmp_path: Path) -> None:
    assert band_movements([]) == []
