"""#697: per-channel summary stats use the settled+valid window, not the
fresh-insertion warmup or fault/startup zeros. The trajectory keeps full history.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=t  run=settled\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _row(sec: int, raw: int, level: str, quality: str = "OK") -> str:
    ts = f"2026-07-05T00:00:{sec:02d}.000Z"
    return (
        f"plants.soil,{ts},{ts[:-1]},sess1,classic,s1,{raw},{quality},level={level}\n"
    )


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s1": {"plant_id": "p01", "plant_name": "pothos"}},
            )
        ]
    )


def _sensor(tmp_path: Path, rows):
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=_reg())["sensors"][0]


def test_fault_and_startup_zeros_do_not_poison_the_stats(tmp_path: Path) -> None:
    # the live `median 2 / range 0-2,289` case: startup zeros before the real read
    s = _sensor(
        tmp_path,
        [
            _row(10, 0, "submerged"),  # startup zero -> implausible_wet, excluded
            _row(20, 2, "submerged"),  # ditto
            _row(30, 2400, "DRY"),
            _row(40, 2450, "DRY"),
        ],
    )
    assert s["raw_min"] == 2400  # NOT 0
    assert s["raw_median"] == 2425
    assert s["raw_max"] == 2450
    assert s["n"] == 4  # trajectory/count still sees every reading


def test_fresh_insertion_air_dry_warmup_is_stripped(tmp_path: Path) -> None:
    # probe reads air (~3100) before it settles into soil - the leading air-dry run
    # must not drag the median toward air-dry.
    s = _sensor(
        tmp_path,
        [
            _row(10, 3100, "air-dry"),  # warmup
            _row(20, 3100, "air-dry"),  # warmup
            _row(30, 1900, "OK"),
            _row(40, 1950, "OK"),
        ],
    )
    assert s["raw_median"] == 1925  # settled soil, not ~3100
    assert s["raw_min"] == 1900


def test_a_genuinely_air_dry_plant_keeps_all_its_samples(tmp_path: Path) -> None:
    # a cactus / unwatered pot never leaves air-dry - do NOT strip it to empty.
    s = _sensor(
        tmp_path,
        [_row(10, 3100, "air-dry"), _row(20, 3150, "air-dry")],
    )
    assert s["raw_median"] == 3125  # kept, not emptied
    assert s["raw_min"] == 3100 and s["raw_max"] == 3150


def test_mid_run_dry_spell_is_kept_only_the_leading_warmup_strips(
    tmp_path: Path,
) -> None:
    # a channel that dries out mid-run (real air-dry later) keeps that period; only
    # the LEADING pre-soil warmup is stripped.
    s = _sensor(
        tmp_path,
        [
            _row(10, 3100, "air-dry"),  # leading warmup -> stripped
            _row(20, 1900, "OK"),
            _row(30, 3100, "air-dry"),  # a real later dry period -> kept
        ],
    )
    # settled = [1900, 3100]; median 2500, not dragged by the leading warmup
    assert s["raw_median"] == 2500
