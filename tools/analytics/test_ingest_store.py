"""Tests for the store-and-forward ingest boundary (#521, ADR-0018 decision #2).

Covers the four acceptance criteria: a replay is dropped, a genuinely new row is
appended, a v1-only row (no dedupe signal) is never a false-positive duplicate,
and the boundary never rewrites - only appends or drops.
"""

from __future__ import annotations

from tools.analytics.ingest_store import Store
from tools.analytics.parse_v1 import Reading


def _reading(
    device_id="Sprout ESP32",
    session_id="63b032",
    sensor_id="s1",
    device_seq=None,
    raw_value=1500,
) -> Reading:
    payload = {}
    if device_seq is not None:
        payload["device_seq"] = str(device_seq)
        payload["time_source"] = "device_uptime"
    return Reading(
        record_type="plants.soil",
        timestamp_utc=None,
        timestamp_local=None,
        sample_id=None,
        session_id=session_id,
        device_id=device_id,
        firmware_version="0.7.0",
        logger_version="plants_logger_0_4",
        millis_ms=None,
        sensor_model="UMLIFE_v2_TLC555",
        sensor_id=sensor_id,
        sensor_position="origplant",
        channel="soil_moisture",
        raw_value=raw_value,
        value=None,
        unit="",
        quality_flag="OK",
        payload=payload,
    )


def test_first_ingest_of_a_row_is_accepted() -> None:
    store = Store()
    assert store.ingest(_reading(device_seq=1)) is True
    assert len(store) == 1


def test_exact_replay_is_dropped() -> None:
    store = Store()
    r = _reading(device_seq=1)
    assert store.ingest(r) is True
    assert store.ingest(r) is False  # the identical row again -> dropped
    assert len(store) == 1  # not double-counted


def test_genuinely_new_row_is_appended() -> None:
    store = Store()
    assert store.ingest(_reading(device_seq=1)) is True
    assert store.ingest(_reading(device_seq=2)) is True  # different device_seq
    assert len(store) == 2


def test_different_sensor_same_seq_is_not_a_duplicate() -> None:
    # device_seq is per-row-emitted, not per-sensor - but the full 5-tuple
    # (incl. sensor_id) is what defines "the same reading."
    store = Store()
    assert store.ingest(_reading(sensor_id="s1", device_seq=5)) is True
    assert store.ingest(_reading(sensor_id="s2", device_seq=5)) is True
    assert len(store) == 2


def test_v1_only_row_never_false_positives_as_duplicate() -> None:
    store = Store()
    r = _reading(device_seq=None)  # no dedupe signal at all
    assert store.ingest(r) is True
    assert store.ingest(r) is True  # the "same" row again -> still appended
    assert store.ingest(r) is True  # honest: never claims duplication it can't prove
    assert len(store) == 0  # v1-only rows are never tracked/counted


def test_v1_and_v2_rows_coexist_independently() -> None:
    store = Store()
    v1 = _reading(device_seq=None)
    v2 = _reading(device_seq=1)
    assert store.ingest(v1) is True
    assert store.ingest(v2) is True
    assert store.ingest(v2) is False  # only the v2 row is deduped
    assert store.ingest(v1) is True
