"""Tests for schema v2 §11.1/§11.2 read-support (#300/#278) - device_seq,
time_source, device_timestamp_utc, and the dedupe_key() helper.

Fixtures use the *real* payload shape #278's firmware slice emits
(``level=X;role=Y;spread=N;gpio=P;device_seq=N;time_source=S[;device_timestamp_utc=T]``),
not a guessed one - device_timestamp_utc is OMITTED entirely when unsynced, never an
empty key (the honest-NULL rule, §11.1).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import dedupe_key, parse_file

_COLS = "record_type,timestamp_utc,session_id,sensor_id,raw_value,quality_flag,payload"
_HEADER = "# log_start_utc=2026-07-01T00:00:00Z  tz_offset=-05:00\n"


def _row(payload: str, seq_id: str = "sess001") -> str:
    return f"plants.soil,2026-07-01T00:00:30.000Z,{seq_id},s1,1312,OK,{payload}"


def _write(tmp_path: Path, rows: list[str]) -> Path:
    p = tmp_path / "one.csv"
    p.write_text(_HEADER + _COLS + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return p


def test_unsynced_row_reads_device_seq_and_time_source_honest_null(
    tmp_path: Path,
) -> None:
    # The real #278 emission today: time_source=device_uptime, no timestamp key at all.
    csv = _write(
        tmp_path,
        [
            _row(
                "level=OK;role=diag;spread=38;gpio=34;device_seq=42;time_source=device_uptime"
            )
        ],
    )
    r = parse_file(csv).readings[0]
    assert r.device_seq == 42
    assert r.time_source == "device_uptime"
    assert r.device_timestamp_utc is None  # honest NULL, not a guess


def test_synced_row_reads_the_real_utc_stamp(tmp_path: Path) -> None:
    # The future #21-wired shape (ready-but-not-emitted-yet, per #278's own PR).
    csv = _write(
        tmp_path,
        [
            _row(
                "level=OK;role=diag;spread=38;gpio=34;device_seq=7;"
                "time_source=device_synced;device_timestamp_utc=2026-07-01T00:00:29Z"
            )
        ],
    )
    r = parse_file(csv).readings[0]
    assert r.time_source == "device_synced"
    assert r.device_seq == 7
    assert r.device_timestamp_utc is not None
    assert r.device_timestamp_utc.year == 2026 and r.device_timestamp_utc.month == 7


def test_v1_only_row_has_no_v2_fields(tmp_path: Path) -> None:
    csv = _write(tmp_path, [_row("level=OK;role=diag;spread=38;gpio=34")])
    r = parse_file(csv).readings[0]
    assert r.device_seq is None
    assert r.time_source is None
    assert r.device_timestamp_utc is None


def test_dedupe_key_is_the_five_tuple(tmp_path: Path) -> None:
    csv = _write(
        tmp_path,
        [
            _row(
                "level=OK;role=diag;spread=38;gpio=34;device_seq=42;time_source=device_uptime"
            )
        ],
    )
    r = parse_file(csv).readings[0]
    key = dedupe_key(r)
    assert key == (r.device_id, r.session_id, 42, "plants.soil", "s1")


def test_dedupe_key_with_no_device_seq_reports_none_not_a_guess(tmp_path: Path) -> None:
    csv = _write(tmp_path, [_row("level=OK;role=diag;spread=38;gpio=34")])
    r = parse_file(csv).readings[0]
    key = dedupe_key(r)
    assert key[2] is None  # a v1-only row has no dedupe signal - honestly reported
