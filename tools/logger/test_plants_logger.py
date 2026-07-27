"""Tests for plants_logger.py — stamping, parsing, schema, rotation (#291).

The round-trip golden test at the bottom ties plants_logger -> parse_v1
end-to-end to prove the data spine doesn't silently corrupt.
"""

from __future__ import annotations

import csv
import gzip
from datetime import datetime, timezone
from pathlib import Path

from tools.logger.plants_logger import (
    CANONICAL_COLS,
    DEVICE_COLS,
    LOGGER_VERSION,
    RotatingCsv,
    is_line_noise,
    iso_utc,
    parse_device_line,
    stamp_row,
)

_ANALYTICS = Path(__file__).resolve().parents[1] / "analytics"
from tools.analytics.parse_v1 import parse_file  # noqa: E402

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

_UTC_0 = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def _make_line(
    *,
    record_type: str = "plants.soil",
    session: str = "sess001",
    device: str = "plants_esp32_test",
    fw: str = "0.7.0",
    millis: int = 30000,
    sensor_model: str = "UMLIFE_v2_TLC555",
    sensor: str = "s3",
    position: str = "origplant",
    channel: str = "soil_moisture",
    raw: int = 1312,
    value: str = "",
    unit: str = "",
    qf: str = "OK",
    payload: str = "level=well watered;role=diag;spread=24;gpio=36",
    with_crc: bool = True,
) -> str:
    body = (
        f"{record_type},{session},{device},{fw},{millis},"
        f"{sensor_model},{sensor},{position},{channel},"
        f"{raw},{value},{unit},{qf},{payload}"
    )
    if with_crc:
        calc = 0
        for ch in body:
            calc ^= ord(ch) & 0xFF
        return f"{body}*{calc:02X}"
    return body


# --------------------------------------------------------------------------- #
# parse_device_line
# --------------------------------------------------------------------------- #


def test_parse_device_line_valid() -> None:
    line = _make_line()
    d = parse_device_line(line)
    assert d is not None
    assert d["record_type"] == "plants.soil"
    assert d["sensor_id"] == "s3"
    assert d["raw_value"] == "1312"
    assert d["value"] == ""
    assert d["unit"] == ""
    assert d["quality_flag"] == "OK"
    assert d["_crc_ok"] is True


def test_parse_device_line_null_value_unit() -> None:
    """Firmware emits ,, for value and unit (decision #38) — must survive round-trip."""
    line = _make_line(value="", unit="")
    d = parse_device_line(line)
    assert d is not None
    assert d["value"] == ""
    assert d["unit"] == ""


def test_parse_device_line_bad_checksum() -> None:
    line = _make_line() + "XX"
    # extra chars after CRC -> still parseable but corrupted
    d = parse_device_line(line[:-4] + "*00")
    assert d is not None
    assert d["_crc_ok"] is False


def test_parse_device_line_no_checksum() -> None:
    line = _make_line(with_crc=False)
    d = parse_device_line(line)
    assert d is not None
    assert d["_crc_ok"] is None


def test_parse_device_line_resync() -> None:
    """Parser re-syncs to the first known record_type prefix."""
    line = "GARBAGE_PREFIX," + _make_line()
    d = parse_device_line(line)
    assert d is not None
    assert d["record_type"] == "plants.soil"


def test_parse_device_line_wrong_field_count() -> None:
    d = parse_device_line("plants.soil,a,b,c")
    assert d is None


def test_parse_device_line_empty() -> None:
    assert parse_device_line("") is None


# --------------------------------------------------------------------------- #
# is_line_noise
# --------------------------------------------------------------------------- #


def test_is_line_noise_ascii() -> None:
    assert not is_line_noise("plants.soil,s3,1312")


def test_is_line_noise_high_bytes() -> None:
    # 0xFF run is the canonical idle-noise pattern from the firmware
    assert is_line_noise("".join(chr(0xFF) for _ in range(12)))


def test_is_line_noise_empty() -> None:
    assert not is_line_noise("")


# --------------------------------------------------------------------------- #
# iso_utc
# --------------------------------------------------------------------------- #


def test_iso_utc_format() -> None:
    ts = iso_utc(_UTC_0)
    assert ts == "2026-06-27T12:00:00.000Z"


def test_iso_utc_milliseconds() -> None:
    dt = datetime(2026, 6, 27, 12, 0, 0, 500000, tzinfo=timezone.utc)
    assert iso_utc(dt).endswith(".500Z")


# --------------------------------------------------------------------------- #
# CANONICAL_COLS vs DEVICE_COLS schema contract
# --------------------------------------------------------------------------- #


def test_canonical_cols_superset_of_device_cols() -> None:
    """Every DEVICE_COLS key (minus _crc_ok) must appear in CANONICAL_COLS
    or be the logger's re-mapping ('fw' -> 'firmware_version')."""
    logger_remaps = {"fw": "firmware_version"}
    for col in DEVICE_COLS:
        mapped = logger_remaps.get(col, col)
        assert mapped in CANONICAL_COLS, (
            f"DEVICE_COLS field '{col}' (maps to '{mapped}') missing from "
            "CANONICAL_COLS — schema mismatch"
        )


def test_logger_version_constant() -> None:
    assert LOGGER_VERSION.startswith("plants_logger_")


# --------------------------------------------------------------------------- #
# RotatingCsv
# --------------------------------------------------------------------------- #


def test_rotating_csv_creates_file(tmp_path: Path) -> None:
    rc = RotatingCsv(str(tmp_path))
    dev = parse_device_line(_make_line())
    rc.write(dev, sample_id=1, now=_UTC_0)
    files = list(tmp_path.glob("*.csv"))
    assert len(files) == 1


def test_rotating_csv_canonical_cols_header(tmp_path: Path) -> None:
    rc = RotatingCsv(str(tmp_path))
    dev = parse_device_line(_make_line())
    rc.write(dev, sample_id=1, now=_UTC_0)
    path = next(iter(tmp_path.glob("*.csv")))
    lines = [
        ln
        for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.startswith("#")
    ]
    header = lines[0].split(",")
    assert header == CANONICAL_COLS


def test_rotating_csv_write_row(tmp_path: Path) -> None:
    rc = RotatingCsv(str(tmp_path))
    dev = parse_device_line(_make_line(raw=1312))
    row, _ = rc.write(dev, sample_id=42, now=_UTC_0)
    assert row["raw_value"] == "1312"
    assert row["sample_id"] == 42
    assert row["timestamp_utc"] == "2026-06-27T12:00:00.000Z"
    assert row["logger_version"] == LOGGER_VERSION


def test_rotating_csv_null_value_unit_preserved(tmp_path: Path) -> None:
    """NULL value/unit from the device must reach the CSV unchanged."""
    rc = RotatingCsv(str(tmp_path))
    dev = parse_device_line(_make_line(value="", unit=""))
    row, _ = rc.write(dev, sample_id=1, now=_UTC_0)
    assert row["value"] == ""
    assert row["unit"] == ""


def test_rotating_csv_appends_host_monotonic_ms(tmp_path: Path) -> None:
    """#9: a UTC-immune relative axis, injected via a fake clock for determinism."""
    ticks = iter([100.0, 100.25, 101.0])  # t0, then two later reads
    rc = RotatingCsv(str(tmp_path), monotonic=lambda: next(ticks))
    dev = parse_device_line(_make_line())
    row1, _ = rc.write(dev, sample_id=1, now=_UTC_0)
    row2, _ = rc.write(dev, sample_id=2, now=_UTC_0)
    assert "host_monotonic_ms=250" in row1["payload"]  # (100.25 - 100.0) * 1000
    assert "host_monotonic_ms=1000" in row2["payload"]  # (101.0 - 100.0) * 1000
    # the device's own payload keys survive, untouched, ahead of the appended key
    assert row1["payload"].startswith("level=well watered;role=diag;")


def test_rotating_csv_host_monotonic_ms_with_empty_device_payload(
    tmp_path: Path,
) -> None:
    ticks = iter([50.0, 50.5])
    rc = RotatingCsv(str(tmp_path), monotonic=lambda: next(ticks))
    dev = parse_device_line(_make_line(payload=""))
    row, _ = rc.write(dev, sample_id=1, now=_UTC_0)
    assert (
        row["payload"] == "host_monotonic_ms=500"
    )  # no leading ";" with no prior keys


# --------------------------------------------------------------------------- #
# stamp_row() - the extracted row-building logic (#277), reused by DeviceAdapter
# --------------------------------------------------------------------------- #


def test_stamp_row_matches_rotating_csv_write(tmp_path: Path) -> None:
    """#277 refactor: stamp_row() must produce the exact row RotatingCsv.write()
    used to build inline, for the same inputs - proves the extraction changed
    nothing about serial-logged rows."""
    rc = RotatingCsv(str(tmp_path), monotonic=lambda: 100.0)
    dev = parse_device_line(_make_line())
    row_via_rotating_csv, _ = rc.write(dev, sample_id=7, now=_UTC_0)
    row_direct = stamp_row(dev, 7, _UTC_0, LOGGER_VERSION, host_monotonic_ms=0)
    assert row_via_rotating_csv == row_direct


def test_stamp_row_honors_a_distinct_logger_version() -> None:
    """A non-serial caller (the WiFi DeviceAdapter) names itself honestly,
    never borrows the serial logger's own identity."""
    dev = parse_device_line(_make_line())
    row = stamp_row(dev, 1, _UTC_0, "device_adapter_v1")
    assert row["logger_version"] == "device_adapter_v1"


def test_stamp_row_omits_host_monotonic_ms_by_default() -> None:
    """No fabricated monotonic axis when the caller has no meaningful single
    start reference (a per-poll adapter, unlike the persistent serial logger)."""
    dev = parse_device_line(_make_line(payload=""))
    row = stamp_row(dev, 1, _UTC_0, "device_adapter_v1")
    assert "host_monotonic_ms" not in row["payload"]
    assert row["payload"] == ""


def test_rotating_csv_rolls_on_new_day(tmp_path: Path) -> None:
    rc = RotatingCsv(str(tmp_path))
    dev = parse_device_line(_make_line())
    day1 = _UTC_0
    day2 = datetime(2026, 6, 28, 0, 0, 1, tzinfo=timezone.utc)
    rc.write(dev, sample_id=1, now=day1)
    rc.write(dev, sample_id=2, now=day2)
    assert len(list(tmp_path.glob("*.csv"))) == 2


# --------------------------------------------------------------------------- #
# Golden round-trip: device line -> RotatingCsv -> parse_v1 -> Reading
# --------------------------------------------------------------------------- #


_CAL_HEADER = "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]"


def test_golden_roundtrip(tmp_path: Path) -> None:
    """A known device line survives the full data spine with no field corruption."""
    logdir = tmp_path / "logs"
    logdir.mkdir()
    rc = RotatingCsv(str(logdir))
    rc.set_header(
        [
            "# fw=0.7.0  git=test0000  run=roundtrip-test",
            "# session_id=rt001  cadence_ms=30000",
            "# sensors: ch0=GPIO36/s3  (model=UMLIFE_v2_TLC555 pos=origplant)",
            _CAL_HEADER,
        ]
    )

    raw_line = _make_line(
        session="rt001",
        device="plants_esp32_test",
        sensor="s3",
        raw=1312,
        value="",
        unit="",
    )
    dev = parse_device_line(raw_line)
    assert dev is not None
    rc.write(dev, sample_id=1, now=_UTC_0)

    csv_path = next(iter(logdir.glob("*.csv")))
    data = parse_file(csv_path)

    assert len(data.readings) == 1
    r = data.readings[0]

    # field integrity
    assert r.raw_value == 1312
    assert r.value is None  # NULL — firmware never emits pct (#38)
    assert r.unit == ""
    assert r.quality_flag == "OK"
    assert r.sensor_id == "s3"
    assert r.session_id == "rt001"
    assert r.timestamp_utc is not None

    # cal bounds from header — present once #295 merges
    seg = data.segments[0]
    assert seg.cal_bounds == [3050, 2140, 1830, 1520, 1150, 1050]
    if hasattr(seg, "cal_bounds_source"):  # added by #295
        assert seg.cal_bounds_source == "header"

    # band from device payload is ground truth
    assert r.band == "well watered"


def test_golden_roundtrip_gzip(tmp_path: Path) -> None:
    """parse_v1 reads a gzip-compressed segment identically to the plain CSV."""
    logdir = tmp_path / "logs"
    logdir.mkdir()
    rc = RotatingCsv(str(logdir))
    rc.set_header([_CAL_HEADER])

    dev = parse_device_line(_make_line(raw=1400, sensor="s4"))
    rc.write(dev, sample_id=1, now=_UTC_0)

    csv_path = next(iter(logdir.glob("*.csv")))
    # compress the CSV to .gz and parse it
    gz_path = tmp_path / "segment.csv.gz"
    with gz_path.open("wb") as fgz:
        fgz.write(gzip.compress(csv_path.read_bytes()))

    data = parse_file(gz_path)
    assert len(data.readings) == 1
    assert data.readings[0].raw_value == 1400
    assert data.readings[0].sensor_id == "s4"


def test_golden_roundtrip_by_name_column_mapping(tmp_path: Path) -> None:
    """parse_v1 maps columns by name — a CSV with columns in a different order
    (or with extra columns) must still produce correct Reading fields."""
    # Write a CSV with shuffled columns: raw_value last, extra unknown col
    cols = ["record_type", "session_id", "raw_value", "quality_flag", "payload"]
    row = [
        "plants.soil",
        "byname001",
        "2048",
        "OK",
        "level=needs water;gpio=36",
    ]
    csv_path = tmp_path / "byname.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerow(row)

    data = parse_file(csv_path)
    assert len(data.readings) == 1
    r = data.readings[0]
    assert r.raw_value == 2048
    assert r.quality_flag == "OK"
    assert r.band == "needs water"
