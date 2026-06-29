"""Tests for the #324 bench-provenance panel: the server/app helper + the
build_context provenance block (server / device / contract / calibration).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import provenance
from dashboard import build_context
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.7.0  git=test123  built=Jun 28 2026 00:00:00  run=testrun\n"
    "# device_id=plants_esp32_test  schema_version=1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,session_id,device_id,firmware_version,"
    "sensor_id,raw_value,value,unit,quality_flag,payload\n"
)


def _row(ts: str, sid: str, raw: int, *, value: str = "", unit: str = "") -> str:
    return (
        f"plants.soil,{ts},sess1,plants_esp32_test,0.7.0,"
        f"{sid},{raw},{value},{unit},OK,level=well watered;gpio=36\n"
    )


def _write_log(path: Path, *, value: str = "", unit: str = "") -> None:
    rows = [
        _row("2026-06-28T00:00:30.000Z", "s1", 1500, value=value, unit=unit),
        _row("2026-06-28T00:00:31.000Z", "s2", 1550),
        _row("2026-06-28T00:01:00.000Z", "s1", 1510),
        _row("2026-06-28T00:01:01.000Z", "s2", 1560),
    ]
    path.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")


# --------------------------------------------------------------------------- #
# provenance.server_provenance()
# --------------------------------------------------------------------------- #


def test_server_provenance_shape() -> None:
    s = provenance.server_provenance()
    for key in ("app_git_sha", "head_git_sha", "branch", "dirty", "start_utc", "stale"):
        assert key in s, f"missing {key}: {s}"
    assert isinstance(s["dirty"], bool)
    assert isinstance(s["stale"], bool)


def test_server_start_utc_iso_z() -> None:
    # captured at import; ISO-8601 with millisecond Z suffix (matches the log style)
    assert provenance.SERVER_START_UTC.endswith("Z")
    assert "T" in provenance.SERVER_START_UTC


def test_stale_false_when_boot_equals_head() -> None:
    # boot SHA is frozen at import; with no commit in between, head == boot -> not stale
    s = provenance.server_provenance()
    if "nogit" not in (s["app_git_sha"], s["head_git_sha"]):
        assert s["app_git_sha"] == s["head_git_sha"]
        assert s["stale"] is False


# --------------------------------------------------------------------------- #
# build_context provenance block (#324)
# --------------------------------------------------------------------------- #


def test_build_context_has_provenance(tmp_path: Path) -> None:
    log = tmp_path / "log.csv"
    _write_log(log)
    ctx = build_context(parse_files([str(log)]))
    p = ctx["provenance"]
    assert "server" in p and "device" in p and "contract" in p and "calibration" in p
    assert p["device"]["fw"] == "0.7.0"
    assert p["device"]["device_id"] == "plants_esp32_test"


def test_contract_raw_only_true_for_clean_log(tmp_path: Path) -> None:
    log = tmp_path / "clean.csv"
    _write_log(log)  # value/unit empty -> contract holds
    ctx = build_context(parse_files([str(log)]))
    c = ctx["provenance"]["contract"]
    assert c["raw_only"] is True
    assert "raw counts + band only" in c["label"]


def test_contract_violation_surfaced(tmp_path: Path) -> None:
    log = tmp_path / "dirty.csv"
    _write_log(log, value="42", unit="pct")  # a populated value violates #38
    ctx = build_context(parse_files([str(log)]))
    c = ctx["provenance"]["contract"]
    assert c["raw_only"] is False
    assert "VIOLATION" in c["label"]


def test_calibration_is_uncalibrated_no_percent(tmp_path: Path) -> None:
    log = tmp_path / "cal.csv"
    _write_log(log)
    ctx = build_context(parse_files([str(log)]))
    cal = ctx["provenance"]["calibration"]
    assert "uncalibrated" in cal
    # honest-data law: the panel never implies a calibrated percentage
    assert "%" not in cal
