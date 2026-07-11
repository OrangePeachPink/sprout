"""#952/#957 the cal_tier wire token — the emission that makes #951's tier chip true on
the LIVE WiFi fleet.

#957's tier is derived from header signals (cal_bounds_source / cal_ch) that ride the
serial boot header only — so over WiFi the C5 wore the wrong chip. Firmware emits
`cal_tier=` on every WiFi soil row (the additive rssi= pattern), from the resolver. The
parser reads it and the display treats it as authoritative, falling back to the header
derivation when it's absent (tethered / pre-emission rows).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_DEFAULT_BOUNDS = (
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_MEASURED = "# cal bounds(dry>wet): 2740 1939 1666 1394 1068 980  [moist% 900..3400]\n"


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


def _rows(payloads: list[tuple[str, str]]) -> str:
    out = ""
    for i, (sid, payload) in enumerate(payloads):
        ts = f"2026-07-05T00:{i:02d}:30.000Z"
        out += f"plants.soil,{ts},x,s1,classic,{sid},2400,OK,{payload}\n"
    return out


def _device(tmp_path: Path, *, bounds=_DEFAULT_BOUNDS, payloads) -> dict:
    header = "# schema_version=4  fw=0.8.0  git=t  device_id=classic  session_id=s1\n"
    p = tmp_path / "a.csv"
    p.write_text(header + bounds + _COLS + _rows(payloads), encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=_reg())["devices"][0]


# --------------------------------------------------------------------------- #
# parser: Reading.cal_tier / cal_src (additive, validated)
# --------------------------------------------------------------------------- #


def test_reading_reads_and_validates_cal_tier(tmp_path: Path) -> None:
    p = tmp_path / "a.csv"
    p.write_text(
        "# schema_version=4  device_id=classic  session_id=s1\n"
        + _COLS
        + _rows(
            [
                ("s1", "level=DRY;transport=wifi_poll;cal_tier=board-cal"),
                (
                    "s2",
                    "level=DRY;transport=wifi_poll;cal_tier=bogus",
                ),  # garbled -> None
                ("s3", "level=DRY;transport=wifi_poll"),  # absent -> None
            ]
        ),
        encoding="utf-8",
    )
    by_sid = {r.sensor_id: r for r in parse_files([str(p)]).readings}
    assert by_sid["s1"].cal_tier == "board-cal"
    assert by_sid["s2"].cal_tier is None  # unknown value rejected, never passed through
    assert by_sid["s3"].cal_tier is None  # absent


def test_reading_reads_cal_src_provenance(tmp_path: Path) -> None:
    p = tmp_path / "a.csv"
    p.write_text(
        "# schema_version=4  device_id=classic  session_id=s1\n"
        + _COLS
        + _rows(
            [("s1", "level=DRY;cal_tier=board-cal;cal_src=board_envelope_20260710")]
        ),
        encoding="utf-8",
    )
    r = parse_files([str(p)]).readings[0]
    assert r.cal_src == "board_envelope_20260710"


# --------------------------------------------------------------------------- #
# display: the wire tier is authoritative on WiFi; else fall back to derivation
# --------------------------------------------------------------------------- #


def test_wire_tier_is_authoritative_on_the_live_wifi_fleet(tmp_path: Path) -> None:
    # the exact bug: a WiFi board with default bounds + no cal_ch derives 'uncalibrated'
    # (header signals are tethered-only), but the wire cal_tier=board-cal is the truth.
    d = _device(
        tmp_path,
        bounds=_DEFAULT_BOUNDS,  # no board-cal signal in the (WiFi-absent) header
        payloads=[("s1", "level=DRY;transport=wifi_poll;cal_tier=board-cal")],
    )
    assert d["cal_tier"] == "board-cal"  # the C5 finally wears the right chip over WiFi


def test_absent_wire_tier_falls_back_to_header_derivation(tmp_path: Path) -> None:
    # tethered / pre-emission: no cal_tier= on the wire -> the header derivation governs
    d = _device(tmp_path, bounds=_MEASURED, payloads=[("s1", "level=DRY;gpio=35")])
    assert (
        d["cal_tier"] == "board-cal"
    )  # from the measured-envelope header, as #951 did


def test_wire_aggregation_takes_the_best_tier(tmp_path: Path) -> None:
    # a device whose channels report different tiers shows its BEST (channel-cal wins),
    # matching #951's any()-precedence for the device-level chip.
    d = _device(
        tmp_path,
        payloads=[
            ("s1", "level=DRY;transport=wifi_poll;cal_tier=uncalibrated"),
            ("s2", "level=DRY;transport=wifi_poll;cal_tier=channel-cal"),
        ],
    )
    assert d["cal_tier"] == "channel-cal"


if __name__ == "__main__":
    import tempfile

    fns = [
        test_reading_reads_and_validates_cal_tier,
        test_reading_reads_cal_src_provenance,
        test_wire_tier_is_authoritative_on_the_live_wifi_fleet,
        test_absent_wire_tier_falls_back_to_header_derivation,
        test_wire_aggregation_takes_the_best_tier,
    ]
    for fn in fns:
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
