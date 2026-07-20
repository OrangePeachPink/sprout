"""#1315 — the read-path translation: v4 `sN` folds to `chN` at JOIN time, so a v5
flash never bisects the analysis store. Rows are untouched (never-stitch, ADR-0036 §4);
only the join key is normalised, and it is retroactively correct because `s1` always
meant "the port that emitted s1" — which IS ch2."""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from parse_v1 import LEGACY_CHANNEL_TOKENS, canonical_channel
from segment_history import plant_series


def test_the_stated_mapping_is_not_sequential() -> None:
    # the whole reason inference was refused: s1 is ch2, not ch0
    assert LEGACY_CHANNEL_TOKENS == ("s3", "s4", "s1", "s2")
    assert canonical_channel("s3") == "ch0"
    assert canonical_channel("s4") == "ch1"
    assert canonical_channel("s1") == "ch2"
    assert canonical_channel("s2") == "ch3"


def test_canonical_is_idempotent_and_honest_about_the_unknown() -> None:
    for t in ("ch0", "ch1", "ch2", "ch3"):
        assert canonical_channel(t) == t  # already canonical
    assert canonical_channel(canonical_channel("s1")) == "ch2"  # idempotent
    assert canonical_channel("s9") == "s9"  # unknown passes through, never guessed
    assert canonical_channel(None) is None and canonical_channel("") == ""


def _tier(root: Path, sensor_token: str) -> None:
    d = root / "date=2026-07-10" / "device=devA"
    d.mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        "CREATE OR REPLACE TABLE t (device_id VARCHAR, sensor_id VARCHAR,"
        " timestamp_utc TIMESTAMP, raw_value DOUBLE, quality_flag VARCHAR)"
    )
    con.executemany(
        "INSERT INTO t VALUES (?, ?, ?, ?, ?)",
        [
            ("devA", sensor_token, "2026-07-10 00:00:00", 1500.0, "OK"),
            ("devA", sensor_token, "2026-07-10 00:00:30", 1502.0, "OK"),
        ],
    )
    con.execute(f"COPY t TO '{(d / 'part.parquet').as_posix()}' (FORMAT PARQUET)")


def _reg(channel_key: str) -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="devA",
                board="esp32dev",
                label="A",
                channels={channel_key: {"plant_id": "p11", "plant_name": "corn"}},
            )
        ]
    )


def test_all_four_combinations_resolve(tmp_path: Path) -> None:
    """registry (migrated | not) x rows (v5 chN | v4 sN) — all four must attribute.

    The pre-fix failure was the v4-rows-vs-migrated-registry cell, which Firmware's
    harness scored 0/8: post-flash the tier holds both vocabularies and the join
    matched only the new half, so ALL pre-flash history silently lost its plant.
    """
    cases = [
        ("ch2", "ch2", "post-migration registry, v5 row"),
        ("ch2", "s1", "post-migration registry, v4 row  <- the bisect case"),
        ("s1", "s1", "pre-migration registry, v4 row"),
        ("s1", "ch2", "pre-migration registry, v5 row  <- flashed before migrating"),
    ]
    for i, (reg_key, row_token, label) in enumerate(cases):
        root = tmp_path / f"case{i}"
        _tier(root, row_token)
        series, unmapped = plant_series(root, _reg(reg_key))
        assert series.get("p11"), f"unattributed: {label}"
        assert len(series["p11"]) == 2, label
        assert unmapped == {}, f"leaked to unmapped: {label}"


def test_rows_are_never_rewritten_only_the_join_key(tmp_path: Path) -> None:
    # never-stitch (ADR-0036 §4): the stored token stays exactly as the board said
    root = tmp_path / "t"
    _tier(root, "s1")
    plant_series(root, _reg("ch2"))
    con = duckdb.connect()
    got = con.execute(
        "SELECT DISTINCT sensor_id FROM "
        f"read_parquet('{root.as_posix()}/*/*/*.parquet')"
    ).fetchall()
    con.close()
    assert got == [("s1",)]  # untouched on disk


def test_an_unknown_channel_still_reports_unmapped(tmp_path: Path) -> None:
    # the translation must not paper over a genuinely unresolvable channel
    root = tmp_path / "t"
    _tier(root, "s9")
    series, unmapped = plant_series(root, _reg("ch2"))
    assert series == {} and unmapped == {("devA", "s9"): 2}
