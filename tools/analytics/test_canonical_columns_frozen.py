"""Freeze-test: the CANONICAL_COLUMNS positional contract must not drift (#927).

``parse_v1.CANONICAL_COLUMNS`` is the schema-v1 positional column order
(docs/TELEMETRY_SCHEMA.md §2) — the single parse boundary (ADR-0021) and the
byte-identical shared shape the companion air-quality project joins on (ADR-0006's
``{raw_value, value, unit}`` + ``quality_flag``). Every telemetry addition since —
``config_id``, ``rssi``, ``SENSOR_FAULT``, … — rides ``payload`` k=v or a ``#`` header,
NEVER a new positional column, precisely so this list stays frozen and the cross-project
join never breaks.

Before this test the invariant was only a docstring claim (in test_parse_v4); a
0.8.0 parser-touch could add a column and silently break the join — now a red gate.

A deliberate positional-column change is a **breaking wire change**: it needs a
``schema_version`` bump and a companion-project heads-up. Update the frozen snapshot
below in the SAME PR so review sees it for what it is, not a quiet diff.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse_v1

# The frozen positional contract. Do NOT edit this to "make the test pass" — see the
# module docstring: a change here is a breaking wire change, reviewed as such.
FROZEN_CANONICAL_COLUMNS = [
    "record_type",
    "timestamp_utc",
    "timestamp_local",
    "sample_id",
    "session_id",
    "device_id",
    "firmware_version",
    "logger_version",
    "millis_ms",
    "sensor_model",
    "sensor_id",
    "sensor_position",
    "channel",
    "raw_value",
    "value",
    "unit",
    "quality_flag",
    "temp_context_c",
    "rh_context_pct",
    "pressure_context_hpa",
    "event_id",
    "payload",
    "notes",
]


def test_canonical_columns_are_frozen() -> None:
    # exact list AND order — a reorder breaks the join as surely as an add or remove.
    assert parse_v1.CANONICAL_COLUMNS == FROZEN_CANONICAL_COLUMNS


def test_canonical_columns_count() -> None:
    # a redundant guard so an accidental add/remove reads clearly in the failure.
    assert len(parse_v1.CANONICAL_COLUMNS) == len(FROZEN_CANONICAL_COLUMNS) == 23


def test_no_duplicate_columns() -> None:
    cols = parse_v1.CANONICAL_COLUMNS
    assert len(cols) == len(set(cols))


def test_extension_seam_and_join_keys_present() -> None:
    # `payload` is the additive extension seam (new fields ride it, not a new column);
    # the four shared-shape keys are what the cross-project join needs present.
    cols = parse_v1.CANONICAL_COLUMNS
    assert "payload" in cols
    for join_key in ("raw_value", "value", "unit", "quality_flag"):
        assert join_key in cols
