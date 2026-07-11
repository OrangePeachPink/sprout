"""#951 three-tier cal honesty (the display half; Firmware's #952 owns the substrate).

The binary `cal_provisional` badge punished the C5 for having *real measured board
bands* (#899) — it wore `cal · provisional` for merely lacking per-channel cal. Three
tiers fix that:

  - channel-cal  — a per-channel bench cal (a verified `# cal_ch`). Top state: NO chip.
  - board-cal    — a measured board envelope in the header, distinct from the shared
                   factory default. A neutral chip, not a caveat. (The C5 after #899.)
  - uncalibrated — factory defaults, or a stated PLACEHOLDER banner. Keeps the caveat.

Tier is derived here from the cal signals already on the wire; when #952 lands a formal
cal_source the derivation swaps to read it and the tier→label mapping is unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

# a verified per-channel cal line (#507) — the top, channel-cal state
_CAL_LINE = (
    "# cal_ch s1: bounds=3123,2140,1830,1520,1150,969 "
    "src=bench_248 date=2026-06-24 confidence=calibrated scope=channel\n"
)
# the shared factory default bounds — a header that merely echoes these is NOT board-cal
_DEFAULT_BOUNDS = (
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
# the C5's own measured envelope (#899/#933): distinct from the default → board-cal
_MEASURED_BOUNDS = (
    "# cal bounds(dry>wet): 2740 1939 1666 1394 1068 980  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                channels={"s1": {"plant_id": "p01", "plant_name": "pothos"}},
                base_url="http://classic.local",
            )
        ]
    )


def _tier(
    tmp_path: Path,
    *,
    bounds_line: str = _DEFAULT_BOUNDS,
    cal_line: str = "",
    placeholder: str = "",
    wifi: bool = True,
) -> dict:
    header = (
        "# schema_version=4  fw=0.8.0  git=t  device_id=classic  session_id=sess1\n"
        + placeholder
        + bounds_line
        + cal_line
    )
    extra = "transport=wifi_poll;device_seq=1" if wifi else ""
    payload = "level=DRY;gpio=35" + (f";{extra}" if extra else "")
    row = f"plants.soil,2026-07-05T00:00:30.000Z,x,sess1,classic,s1,2400,OK,{payload}\n"
    p = tmp_path / "a.csv"
    p.write_text(header + _COLS + row, encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=_reg())["devices"][0]


def test_channel_cal_is_the_top_tier(tmp_path: Path) -> None:
    # a verified per-channel cal → channel-cal (the unlabeled top state)
    d = _tier(tmp_path, cal_line=_CAL_LINE, wifi=True)
    assert d["cal_tier"] == "channel-cal"


def test_measured_board_envelope_is_board_cal_not_provisional(tmp_path: Path) -> None:
    # the C5 after #899: real measured board bands, no per-channel cal. It must NOT be
    # dragged into the caveat — board-cal is an honest state, not "provisional".
    d = _tier(tmp_path, bounds_line=_MEASURED_BOUNDS, wifi=True)
    assert d["cal_tier"] == "board-cal"


def test_default_bounds_are_uncalibrated(tmp_path: Path) -> None:
    # a header that merely echoes the shared factory defaults is not a board cal
    d = _tier(tmp_path, bounds_line=_DEFAULT_BOUNDS, wifi=True)
    assert d["cal_tier"] == "uncalibrated"


def test_channel_cal_wins_over_board_bounds(tmp_path: Path) -> None:
    # per-channel is strictly stronger than a board envelope — the top tier wins
    d = _tier(tmp_path, bounds_line=_MEASURED_BOUNDS, cal_line=_CAL_LINE, wifi=True)
    assert d["cal_tier"] == "channel-cal"


def test_placeholder_forces_uncalibrated_even_with_board_bounds(tmp_path: Path) -> None:
    # a stated non-cal (PLACEHOLDER) wins: measured-looking bounds can't launder it
    d = _tier(
        tmp_path,
        bounds_line=_MEASURED_BOUNDS,
        placeholder="# board cal: PLACEHOLDER (not bench-verified)\n",
        wifi=False,
    )
    assert d["cal_tier"] == "uncalibrated"


def test_cal_provisional_kept_for_back_compat(tmp_path: Path) -> None:
    # #951 adds cal_tier; the legacy boolean stays so nothing downstream 500s without it
    d = _tier(tmp_path, bounds_line=_MEASURED_BOUNDS, wifi=True)
    assert "cal_provisional" in d


# --------------------------------------------------------------------------- #
# template contract: the three-tier render is wired (a pre-#951 payload without
# cal_tier still falls back to the legacy boolean, so the branches must exist)
# --------------------------------------------------------------------------- #


def test_template_renders_the_three_tiers() -> None:
    tpl = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
        encoding="utf-8"
    )
    assert "cal_tier" in tpl
    assert "cal · board-level" in tpl  # the board-cal neutral chip
    assert "cal · uncalibrated" in tpl  # the uncalibrated caveat
    # channel-cal is unlabeled; the old always-on "bench-verified" chip is gone
    assert "cal · bench-verified" not in tpl


if __name__ == "__main__":
    import tempfile

    fns = [
        test_channel_cal_is_the_top_tier,
        test_measured_board_envelope_is_board_cal_not_provisional,
        test_default_bounds_are_uncalibrated,
        test_channel_cal_wins_over_board_bounds,
        test_placeholder_forces_uncalibrated_even_with_board_bounds,
        test_cal_provisional_kept_for_back_compat,
    ]
    for fn in fns:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    test_template_renders_the_three_tiers()
    print("  PASS  test_template_renders_the_three_tiers")
    print("All checks passed.")
