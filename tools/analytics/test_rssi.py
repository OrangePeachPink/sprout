"""#814 render live WiFi RSSI per device (the display half of #669).

`rssi=<dbm>` rides every WiFi-polled telemetry row's payload (firmware emit #754 /
parse #759); the dashboard surfaces the latest value per device as a real dBm + a
labeled band — never a fabricated quality %. Honest-absent (ADR-0028): a serial /
tethered row carries no `rssi=`, so the surface shows absence as absence, never a
stale or 0 dBm value.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import _rssi_band, build_context
from device_registry import Device, Registry
from parse_v1 import parse_files

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


def _device(tmp_path: Path, *, payload: str) -> dict:
    header = "# schema_version=4  fw=0.8.0  git=t  device_id=classic  session_id=s1\n"
    row = f"plants.soil,2026-07-05T00:00:30.000Z,x,s1,classic,s1,2400,OK,{payload}\n"
    p = tmp_path / "a.csv"
    p.write_text(header + _COLS + row, encoding="utf-8")
    return build_context(parse_files([str(p)]), registry=_reg())["devices"][0]


# --------------------------------------------------------------------------- #
# _rssi_band — the honest bucket, not a quality %
# --------------------------------------------------------------------------- #


def test_rssi_band_thresholds() -> None:
    assert _rssi_band(-50) == "strong"
    assert _rssi_band(-67) == "strong"  # boundary
    assert _rssi_band(-68) == "fair"
    assert _rssi_band(-75) == "fair"  # boundary
    assert _rssi_band(-76) == "weak"
    assert _rssi_band(-90) == "weak"


def test_rssi_band_none_is_none() -> None:
    # ADR-0028 honest-absent: no signal -> no band to invent
    assert _rssi_band(None) is None


# --------------------------------------------------------------------------- #
# build_context surfaces the latest per-device RSSI + band
# --------------------------------------------------------------------------- #


def test_wifi_device_surfaces_rssi_and_band(tmp_path: Path) -> None:
    d = _device(tmp_path, payload="level=DRY;gpio=35;transport=wifi_poll;rssi=-72")
    assert d["rssi"] == -72
    assert d["rssi_band"] == "fair"


def test_weak_signal_lands_in_the_weak_band(tmp_path: Path) -> None:
    d = _device(tmp_path, payload="level=DRY;gpio=35;transport=wifi_poll;rssi=-81")
    assert d["rssi"] == -81
    assert d["rssi_band"] == "weak"  # the placement / dropout cue


def test_tethered_row_is_honestly_absent(tmp_path: Path) -> None:
    # a serial/tethered row omits rssi entirely -> None -> no chip, never a fake 0 dBm
    d = _device(tmp_path, payload="level=DRY;gpio=35")
    assert d["rssi"] is None
    assert d["rssi_band"] is None


# --------------------------------------------------------------------------- #
# template contract: the chip is absent-guarded and shows the real unit
# --------------------------------------------------------------------------- #


def test_template_guards_and_labels_the_rssi_chip() -> None:
    tpl = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
        encoding="utf-8"
    )
    assert "d.rssi != null" in tpl  # honest-absent: no chip when rssi is absent
    assert "dBm" in tpl  # the real unit, never a fabricated %
    # the rendered chip carries dBm + the band, not a percentage — the render line
    # itself is `d.rssi + ' dBm · ' + (d.rssi_band||'')`, no '%' on it.
    render = next(ln for ln in tpl.splitlines() if "' dBm" in ln)
    assert "%" not in render


if __name__ == "__main__":
    import tempfile

    for fn in (test_rssi_band_thresholds, test_rssi_band_none_is_none):
        fn()
        print(f"  PASS  {fn.__name__}")
    for fn in (
        test_wifi_device_surfaces_rssi_and_band,
        test_weak_signal_lands_in_the_weak_band,
        test_tethered_row_is_honestly_absent,
    ):
        with tempfile.TemporaryDirectory() as d:
            fn(Path(d))
        print(f"  PASS  {fn.__name__}")
    test_template_guards_and_labels_the_rssi_chip()
    print("  PASS  test_template_guards_and_labels_the_rssi_chip")
    print("All checks passed.")
