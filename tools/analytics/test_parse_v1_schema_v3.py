"""Tests for schema-v3 recognition (#618, ADR-0027): version-aware device_id
provenance. The `device_id` column stays a string; `schema_version >= 3` gates
its *meaning* (stable minted id vs friendly name). `name=` in payload is the v3
friendly label + pre-mint degrade identifier. Pre-bump logs parse unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import STABLE_ID_SCHEMA_VERSION, parse_file, parse_files

_LOGGER = Path(__file__).resolve().parents[1] / "logger"
sys.path.insert(0, str(_LOGGER))
from datetime import datetime, timezone  # noqa: E402

from plants_logger import RotatingCsv, parse_device_line  # noqa: E402

_UTC = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _log(tmp_path: Path, *, schema_version: int, device: str, payload: str) -> Path:
    header = (
        f"# plants telemetry  schema_version={schema_version}\n"
        "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
    )
    ts = "2026-07-04T00:00:30.000Z"
    row = f"plants.soil,{ts},{ts[:-1]},sess1,{device},s1,1500,OK,{payload}\n"
    p = tmp_path / f"v{schema_version}.csv"
    p.write_text(header + _COLS + row, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# the constant + the version gate
# --------------------------------------------------------------------------- #


def test_the_bump_is_three_not_two() -> None:
    # 2 is already live-emitted by experiment_capture (device_id=name); reusing
    # it would misclassify every shipped experiment row (ADR-0027 §1b).
    assert STABLE_ID_SCHEMA_VERSION == 3


def test_v3_row_device_id_is_the_stable_id(tmp_path: Path) -> None:
    log = _log(
        tmp_path,
        schema_version=3,
        device="k7m2rt",  # a 6-char Crockford base32 stable id
        payload="level=well watered;gpio=36;name=the classic",
    )
    r = parse_file(log).readings[0]
    assert r.schema_version == 3
    assert r.device_id_is_stable_id is True
    assert r.device_id == "k7m2rt"  # the column value, unchanged as a string
    assert r.device_name == "the classic"  # the friendly label rides payload
    assert r.device_display_name == "the classic"  # human name, epoch-agnostic


def test_v1_row_device_id_is_a_name(tmp_path: Path) -> None:
    log = _log(
        tmp_path,
        schema_version=1,
        device="Sprout ESP32",
        payload="level=well watered;gpio=36",
    )
    r = parse_file(log).readings[0]
    assert r.device_id_is_stable_id is False  # legacy epoch
    assert r.device_name is None  # no payload name= pre-v3
    assert r.device_display_name == "Sprout ESP32"  # the id column IS the name


def test_v2_experiment_capture_row_is_still_a_name(tmp_path: Path) -> None:
    # the exact reason the bump is 3, not 2: v2 rows keep device_id=name
    log = _log(
        tmp_path,
        schema_version=2,
        device="Sprout ESP32",
        payload="level=OK;gpio=36",
    )
    r = parse_file(log).readings[0]
    assert r.device_id_is_stable_id is False
    assert r.device_display_name == "Sprout ESP32"


def test_no_schema_version_is_treated_as_legacy_never_stable(tmp_path: Path) -> None:
    p = tmp_path / "bare.csv"
    ts = "2026-07-04T00:00:30.000Z"
    p.write_text(
        "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
        + _COLS
        + f"plants.soil,{ts},{ts[:-1]},sess1,legacy-board,s1,1500,OK,level=OK\n",
        encoding="utf-8",
    )
    r = parse_file(p).readings[0]
    assert r.device_id_is_stable_id is False  # unknown version -> never guessed stable


def test_pre_mint_v3_row_degrades_to_the_name(tmp_path: Path) -> None:
    """The pre-mint degrade path (ADR-0027 rider): a v3 row emitted before the
    UUID is minted has no valid device_id, and `name=` is the only identity it
    carries - device_display_name falls back to it, never blank."""
    log = _log(
        tmp_path,
        schema_version=3,
        device="",  # not yet minted
        payload="level=OK;gpio=36;name=fresh board",
    )
    r = parse_file(log).readings[0]
    assert r.device_id == ""  # honestly empty - the mint hasn't happened
    assert r.device_display_name == "fresh board"  # name= is the fallback identity


# --------------------------------------------------------------------------- #
# the logger propagates the device's schema_version (correct-by-construction)
# --------------------------------------------------------------------------- #


def _device_line(schema_hdr: str, device: str, payload: str) -> tuple[list[str], dict]:
    body = (
        f"plants.soil,sess1,{device},0.8.0,60000,UMLIFE_v2_TLC555,"
        f"s1,shelf,soil_moisture,1500,,,OK,{payload}"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    dev = parse_device_line(f"{body}*{crc:02X}")
    return [schema_hdr], dev


def test_logger_reflects_a_v3_device_schema_version(tmp_path: Path) -> None:
    """A v3 device must log AS v3 - not silently stamped v1 by a hardcoded
    logger claim. Correct-by-construction, not by which line comes last."""
    hdr, dev = _device_line(
        "# plants telemetry  schema_version=3",
        "k7m2rt",
        "level=OK;gpio=36;name=the classic",
    )
    rc = RotatingCsv(str(tmp_path))
    rc.set_header(hdr)
    rc.write(dev, sample_id=1, now=_UTC)
    path = next(iter(Path(tmp_path).glob("*.csv")))
    # the logger's OWN header line now says schema_version=3
    head = path.read_text(encoding="utf-8").splitlines()[0]
    assert "schema_version=3" in head
    # ...and end-to-end, parse_v1 classifies device_id as the stable id
    r = parse_file(path).readings[0]
    assert r.device_id_is_stable_id is True
    assert r.device_name == "the classic"


def test_logger_defaults_to_v1_when_device_declares_none(tmp_path: Path) -> None:
    hdr, dev = _device_line(
        "# fw=0.7.0  git=t  run=r",  # no schema_version at all
        "Sprout ESP32",
        "level=OK;gpio=36",
    )
    rc = RotatingCsv(str(tmp_path))
    rc.set_header(hdr)
    rc.write(dev, sample_id=1, now=_UTC)
    path = next(iter(Path(tmp_path).glob("*.csv")))
    assert "schema_version=1" in path.read_text(encoding="utf-8").splitlines()[0]
    assert parse_file(path).readings[0].device_id_is_stable_id is False


def test_mixed_epoch_log_dir_classifies_each_correctly(tmp_path: Path) -> None:
    # a v1 legacy file and a v3 file in the same dir - each read on its own terms
    _log(tmp_path, schema_version=1, device="Sprout ESP32", payload="level=OK")
    _log(
        tmp_path,
        schema_version=3,
        device="k7m2rt",
        payload="level=OK;name=the classic",
    )
    data = parse_files([str(tmp_path)])
    by_stable = {r.device_id: r.device_id_is_stable_id for r in data.readings}
    assert by_stable == {"Sprout ESP32": False, "k7m2rt": True}
