"""#1042 / ADR-0036 — the v5 chN boundary, host side: version-gated meaning, both
vocabularies indexed correctly, and v4 rows never rewritten."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import _channel_idx
from parse_v1 import CHANNEL_ID_SCHEMA_VERSION, parse_file

_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _seg(tmp_path: Path, version: int, sid: str) -> Path:
    f = tmp_path / f"dev_v{version}.csv"
    f.write_text(
        f"# schema_version={version}  fw=0.8.0  git=t  device_id=dev1  session_id=s1\n"
        + _COLS
        + f"plants.soil,2026-07-20T00:00:00.000000Z,x,s1,dev1,{sid},1500,OK,level=OK\n",
        encoding="utf-8",
    )
    return f


def test_v5_rows_mean_channel_and_v4_rows_do_not(tmp_path: Path) -> None:
    assert CHANNEL_ID_SCHEMA_VERSION == 5
    v5 = parse_file(str(_seg(tmp_path, 5, "ch2"))).readings[0]
    assert v5.sensor_id_is_channel is True
    assert v5.sensor_id == "ch2"  # carried verbatim, never translated
    v4 = parse_file(str(_seg(tmp_path, 4, "s3"))).readings[0]
    assert v4.sensor_id_is_channel is False
    assert v4.sensor_id == "s3"  # the historical row is NEVER rewritten


def test_a_row_with_no_schema_version_is_legacy_never_guessed(tmp_path: Path) -> None:
    f = tmp_path / "bare.csv"
    f.write_text(
        _COLS
        + "plants.soil,2026-07-20T00:00:00.000000Z,x,s1,dev1,s2,1500,OK,level=OK\n",
        encoding="utf-8",
    )
    r = parse_file(str(f)).readings[0]
    assert r.sensor_id_is_channel is False  # absent version => legacy, not a channel


def test_both_vocabularies_index_from_zero_despite_different_bases() -> None:
    # the bug this guards: reading digits alone maps ch0 -> -1 and shifts every
    # channel by one, so a fleet would silently re-colour the day it flashes v5
    assert [_channel_idx(t) for t in ("s1", "s2", "s3", "s4")] == [0, 1, 2, 3]
    assert [_channel_idx(t) for t in ("ch0", "ch1", "ch2", "ch3")] == [0, 1, 2, 3]
    assert _channel_idx("ch0") >= 0
    assert _channel_idx("") == 0  # unparseable stays benign, never negative


def test_the_uniqueness_key_is_unchanged_across_the_boundary(tmp_path: Path) -> None:
    # (device_id, sensor_id) stays the tuple — the rename changes the token's
    # MEANING, never the key's shape
    a = parse_file(str(_seg(tmp_path, 5, "ch0"))).readings[0]
    b = parse_file(str(_seg(tmp_path, 4, "s1"))).readings[0]
    assert (a.device_id, a.sensor_id) != (b.device_id, b.sensor_id)
    assert a.device_id == b.device_id  # same board, different contract epoch
