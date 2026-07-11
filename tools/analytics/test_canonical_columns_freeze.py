"""#927 - freeze CANONICAL_COLUMNS: the enforcing gate the schema never had.

The canonical schema-v1 column set + order is a cross-project contract: the companion
air-quality project joins on ``timestamp_utc``, and every downstream consumer maps
columns by name off this set (``docs/TELEMETRY_SCHEMA.md``). Before this test the only
guard was a docstring claim - a 0.8.0 parser-touch could add a positional column,
reorder one, or drop one and silently break the join.

This test freezes the exact set + order. Changing it is a deliberate, reviewed schema
change: update ``_FROZEN`` here AND ``docs/TELEMETRY_SCHEMA.md`` AND bump the
``schema_version``, in one change - never a silent edit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import CANONICAL_COLUMNS

# The frozen canonical order (schema_version=1, docs/TELEMETRY_SCHEMA.md §2). DO NOT
# edit to make a test pass - a diff here is a schema change; see the module docstring.
_FROZEN = [
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
    assert CANONICAL_COLUMNS == _FROZEN, (
        "CANONICAL_COLUMNS changed — this is a cross-project schema change (the "
        "companion project joins on these columns). If intentional, update _FROZEN "
        "here + docs/TELEMETRY_SCHEMA.md + bump schema_version, in one reviewed change."
    )


def test_column_count_is_stable() -> None:
    # a bare count guard, so an accidental add/remove is caught even if a rename slips
    assert len(CANONICAL_COLUMNS) == len(_FROZEN) == 23


def test_no_duplicate_columns() -> None:
    assert len(set(CANONICAL_COLUMNS)) == len(CANONICAL_COLUMNS)


def test_cross_project_join_key_positions_are_pinned() -> None:
    # the join key + its provenance neighbours must not drift (the companion join,
    # #TELEMETRY_SCHEMA): record_type first, timestamp_utc second, device_id sixth.
    assert CANONICAL_COLUMNS[0] == "record_type"
    assert CANONICAL_COLUMNS[1] == "timestamp_utc"
    assert CANONICAL_COLUMNS[5] == "device_id"
