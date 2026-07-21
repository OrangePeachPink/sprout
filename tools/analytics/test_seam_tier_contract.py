#!/usr/bin/env python3
"""#1338 seam 1 (document half) — **tier contract ↔ the store that implements it**.

Seam 1's *identity* axis is covered next door in ``test_seam_registry_identity.py``:
registry ↔ tier ↔ read paths, one answer to "who is on this channel". This file is the
other half — the **document** side, the direct analogue of seam 2 (wire schema ↔ parser)
and seam 3 (ADR claims ↔ shipped behaviour).

**Why the document needs its own suite.** ``TIER_STORE_CONTRACT.md`` is not commentary
on the store; it is the specification two independent things are built against — the
writer (``tier_store.build_partition``) and every reader that queries the Parquet. The
store's own tests check the writer against itself and pass. They would keep passing if
the document said something different, because nothing reads the document.

That is not hypothetical here. **#1331 is the recorded case**: the contract's §3 said
identity resolved against *open* assignments and called that the never-stitch
guarantee. It was the exact inversion of the guarantee — and the implementation and its
"independent" verification oracle both faithfully inherited the error *from the
sentence*. Two implementations agreed, the fidelity gate passed, and the answer was
wrong, because the thing they agreed with was the document and the document was wrong.
The contract now carries that correction inline, dated. This suite exists so the next
such divergence is caught by a test instead of by a maintainer noticing a wrong plant.

**Method, per the epic's constraint.** Executable claims with citations. The document is
checked by **presence** — never parsed as a grammar, which would make the suite a
brittle Markdown linter instead of a conformance check. Each test names the section it
enforces, so a failure points at the sentence, not just at a line of code.

**How to read a failure.** Not "the store is broken". It means the store and its
published contract have diverged, and someone is trusting whichever one they read
first. Fix by deciding which is right and moving the other deliberately — the #1331
correction is what that looks like done properly.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import parse_file
from tier_store import COLUMNS, build_partition, tagged_day_rows

_REPO = Path(__file__).resolve().parents[2]
_CONTRACT = _REPO / "docs" / "TIER_STORE_CONTRACT.md"

_HEADER = (
    "# schema_version=4  fw=0.8.0  git=t  device_id=devA  session_id=s1\n"
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _doc() -> str:
    assert _CONTRACT.is_file(), (
        "TIER_STORE_CONTRACT.md is missing — the contract is gone"
    )
    return _CONTRACT.read_text(encoding="utf-8", errors="replace")


def _segment(tmp: Path, name: str, stamps: list[datetime]) -> Path:
    """A raw segment whose FILENAME is deliberately unrelated to its row timestamps —
    §2's "rotation names lie across midnight" made concrete."""
    rows = "".join(
        f"plants.soil,{t.strftime('%Y-%m-%dT%H:%M:%S.%f')}Z,x,s1,devA,"
        f"s1,{1500 + i},OK,level=OK\n"
        for i, t in enumerate(stamps)
    )
    p = tmp / name
    p.write_text(_HEADER + rows, encoding="utf-8")
    return p


# --------------------------------------------------------------------------- #
# §3 — the columns, and the two things that must never be among them
# --------------------------------------------------------------------------- #
def test_t1_every_written_column_is_a_documented_column() -> None:
    """§3's table is the schema contract. A column the document has never heard of is
    a column no reader can be expected to interpret."""
    doc = _doc()
    for column in COLUMNS:
        assert f"`{column}`" in doc, (
            f"the store writes {column!r}; the contract does not"
        )


def test_t1b_the_provenance_trio_is_present_and_named_as_provenance() -> None:
    """§3 — the trio is *"the auditable-rebuild guarantee"* (#1239 fold 2)."""
    doc = _doc()
    for column in ("source_file", "ingest_ts", "schema_version"):
        assert column in COLUMNS, f"{column} is the rebuild guarantee and is missing"
    assert "provenance" in doc


def test_t1c_the_retired_percent_index_never_returns() -> None:
    """§3 — *"No legacy `value` %  … the tier never resurrects the index."* The band
    ladder replaced it; a `value` column reappearing would quietly re-legitimise a
    number the product decided is not a reading."""
    assert "value" not in COLUMNS  # exact, not substring: raw_value is fine
    assert "raw_value" in COLUMNS


def test_t1d_no_plant_identity_is_stored() -> None:
    """§3 — *"No plant identity in the store."* Identity resolves at read time on the
    covering interval; a stored plant_id is the never-stitch guarantee pre-broken."""
    for forbidden in ("plant_id", "plant_name", "plant"):
        assert forbidden not in COLUMNS


def test_t1e_the_contract_carries_the_1331_correction_not_the_original_error() -> None:
    """The seam's own memory. §3 once said identity resolved against *open*
    assignments — the inversion that shipped #1331. If that sentence ever returns, the
    next implementation will inherit it exactly as the last one did."""
    doc = _doc()
    assert "start_ts <= reading_ts < end_ts" in doc, (
        "the covering-interval rule is gone"
    )
    assert "Never the open assignment." in doc, "the #1331 correction has been dropped"


# --------------------------------------------------------------------------- #
# §2 — the partition layout, and which fact decides it
# --------------------------------------------------------------------------- #
def test_t2_rows_land_by_their_timestamp_never_by_the_filename(tmp_path: Path) -> None:
    """§2 — *"Rows are selected into a partition by the parsed `timestamp_utc`, never
    the filename — rotation names lie across midnight."* The fixture is a segment named
    for one day holding rows from another; the partition must follow the rows."""
    pytest.importorskip("duckdb")
    day = datetime(2026, 7, 12, tzinfo=timezone.utc)
    seg = _segment(
        tmp_path,
        "plants-2026-07-11.csv",  # the name lies
        [day.replace(hour=2) + timedelta(minutes=i) for i in range(4)],
    )
    tagged = tagged_day_rows([str(seg)], "devA", day.date())
    assert tagged, "the day's rows were not found — the filename won, which is the bug"
    out, _stats = build_partition(
        tagged, "devA", day.date(), out_root=tmp_path / "tier"
    )
    assert "date=2026-07-12" in str(out)  # the rows' day
    assert "date=2026-07-11" not in str(out)  # not the filename's
    assert "device=devA" in str(out)


def test_t2b_the_documented_path_shape_is_the_written_one(tmp_path: Path) -> None:
    """§2's code block is the path contract other tools glob against."""
    pytest.importorskip("duckdb")
    assert "date=<UTC-date>/device=<device_id>/part.parquet" in _doc()
    day = datetime(2026, 7, 12, tzinfo=timezone.utc)
    seg = _segment(tmp_path, "a.csv", [day.replace(hour=1)])
    tagged = tagged_day_rows([str(seg)], "devA", day.date())
    out, _ = build_partition(tagged, "devA", day.date(), out_root=tmp_path / "tier")
    assert out.name == "part.parquet"
    assert out.parent.name.startswith("device=")
    assert out.parent.parent.name.startswith("date=")


# --------------------------------------------------------------------------- #
# §4 — the µs invariant, against the fixture class that first caught it
# --------------------------------------------------------------------------- #
def test_t4_duckdb_and_a_pure_recompute_agree_exactly_on_sub_ms_data(
    tmp_path: Path,
) -> None:
    """§4 — *"computed in exact integer microseconds — never ms-floored, never
    float-seconds, so any DuckDB rollup equals an independent pure recompute exactly."*

    The fixture carries sub-millisecond timestamps on purpose: the D0 tracer's first
    real-data run showed ms-flooring and float-seconds diverging off-by-one on exactly
    these, and clean synthetic timestamps never trip it. *Exactly* means ``==``, not
    ``approx`` — a tolerance here would let the defect back in wearing a green tick.
    """
    duckdb = pytest.importorskip("duckdb")
    base = datetime(2026, 7, 12, 3, 0, 0, 123_456, tzinfo=timezone.utc)
    stamps = [base + timedelta(microseconds=333_777 * i) for i in range(12)]
    seg = _segment(tmp_path, "a.csv", stamps)
    tagged = tagged_day_rows([str(seg)], "devA", base.date())
    out, _ = build_partition(tagged, "devA", base.date(), out_root=tmp_path / "tier")

    engine_us = (
        duckdb.connect()
        .execute(
            "SELECT CAST(date_diff('microsecond', MIN(timestamp_utc), "
            "MAX(timestamp_utc)) "
            f"AS BIGINT) FROM read_parquet('{out.as_posix()}')"
        )
        .fetchone()[0]
    )

    parsed = sorted(r.timestamp_utc for r in parse_file(str(seg)).readings)
    delta = parsed[-1] - parsed[0]
    pure_us = (
        delta.days * 86_400_000_000 + delta.seconds * 1_000_000 + delta.microseconds
    )

    assert engine_us == pure_us, (
        "the engine and a pure integer-µs recompute disagree — §4 is the invariant "
        "that makes every tier-1+ rollup trustworthy, and it is broken"
    )


def test_t4b_the_invariant_is_stated_as_doctrine_not_as_a_detail() -> None:
    doc = _doc()
    assert "never ms-floored" in doc and "never float-seconds" in doc


# --------------------------------------------------------------------------- #
# §8 — appends, and the reader rule they impose
# --------------------------------------------------------------------------- #
def test_t8_an_append_sibling_is_written_through_the_same_schema_path(
    tmp_path: Path,
) -> None:
    """§8 — appends are *"same §3 schema, written through the same one schema path
    (build_partition)"*. Two schema paths is how a store starts disagreeing with itself.
    """
    duckdb = pytest.importorskip("duckdb")
    day = datetime(2026, 7, 12, tzinfo=timezone.utc)
    seg = _segment(
        tmp_path,
        "a.csv",
        [day.replace(hour=1) + timedelta(minutes=i) for i in range(3)],
    )
    tagged = tagged_day_rows([str(seg)], "devA", day.date())
    root = tmp_path / "tier"
    canonical, _ = build_partition(tagged, "devA", day.date(), out_root=root)
    append, _ = build_partition(
        tagged, "devA", day.date(), out_root=root, filename="append-1.parquet"
    )
    con = duckdb.connect()

    def cols_of(p: Path) -> list[str]:
        src = f"read_parquet('{p.as_posix()}', hive_partitioning=1)"
        sql = f"DESCRIBE SELECT * FROM {src}"
        return [r[0] for r in con.execute(sql).fetchall()]

    # The partition keys ride along as columns - that is §2's own claim ("the
    # per-board-only rule is visible in the path and queryable on read"), not drift, so
    # it gets pinned rather than filtered away silently.
    for path in (canonical, append):
        got = cols_of(path)
        assert [c for c in got if c not in ("date", "device")] == list(COLUMNS), (
            f"{path.name} drifted from the §3 column contract"
        )
        assert {"date", "device"} <= set(got), (
            "§2 promises the partition keys are queryable on read; they are not"
        )


def test_t8b_readers_must_glob_all_parquet_not_the_canonical_name_alone() -> None:
    """§8 — *"Readers therefore glob `*.parquet` within a partition, never
    `part.parquet` alone."* A reader that names the canonical file silently omits every
    row ingested since the last compaction: fresh data, invisible, with no error."""
    assert (
        "never\n  `part.parquet` alone" in _doc()
        or "never `part.parquet` alone" in _doc()
    )
    source = (Path(__file__).resolve().parent / "tier_ingest.py").read_text(
        encoding="utf-8"
    )
    assert 'glob("date=*/device=*/*.parquet")' in source, (
        "the ingest watermark stopped globbing all parquet — appends would go uncounted"
    )


def test_t8c_the_store_is_its_own_watermark_no_sidecar_state(tmp_path: Path) -> None:
    """§8 — *"No side-car state exists to lose, drift, or contradict the store."*
    A written partition tree must contain Parquet and nothing else; a state file here
    would be a second source of truth about what has been ingested."""
    pytest.importorskip("duckdb")
    day = datetime(2026, 7, 12, tzinfo=timezone.utc)
    seg = _segment(tmp_path, "a.csv", [day.replace(hour=1)])
    tagged = tagged_day_rows([str(seg)], "devA", day.date())
    root = tmp_path / "tier"
    build_partition(tagged, "devA", day.date(), out_root=root)
    stray = [p.name for p in root.rglob("*") if p.is_file() and p.suffix != ".parquet"]
    assert stray == [], f"side-car state appeared in the store: {stray}"


# --------------------------------------------------------------------------- #
# §1 / §6 — where the store lives, and what may write it
# --------------------------------------------------------------------------- #
def test_t1f_the_store_home_is_gitignored_and_off_the_data_branch() -> None:
    """§1 — the store is derived, disposable, and *"Parquet never lands"* on the `data`
    branch. If `reports/` ever stopped being ignored, a regenerable multi-MB store
    would start arriving in review diffs and, worse, in history."""
    ignore = (_REPO / ".gitignore").read_text(encoding="utf-8")
    assert any(line.strip().rstrip("/") == "reports" for line in ignore.splitlines()), (
        "reports/ is no longer gitignored — the derived store would become tracked"
    )
    assert "never the `data` branch" in _doc()


def test_t6_parse_v1_is_the_only_reader_of_raw() -> None:
    """§6 / ADR-0021 — *"The only reader of raw is `parse_v1`"*; the store is written
    from parsed readings, never by re-splitting CSV text. A second parser is how the
    tier and the dashboard start disagreeing about what a row said."""
    source = (Path(__file__).resolve().parent / "tier_store.py").read_text(
        encoding="utf-8"
    )
    assert "from parse_v1 import" in source
    for smell in ("csv.reader", "csv.DictReader", ".split(',')", '.split(",")'):
        assert smell not in source, (
            f"tier_store re-splits raw text ({smell}) — §6 says it must not"
        )
