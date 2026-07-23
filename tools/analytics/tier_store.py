#!/usr/bin/env python3
"""#1239 — the D1 tier store: the written contract, implemented.

The contract is ``docs/TIER_STORE_CONTRACT.md`` (ratified #1239; Trellis PASS on the
#1238 D0 evidence, with the two D1 folds landed here):

- **Provenance columns** — every row carries ``source_file`` (the origin segment's
  basename), ``ingest_ts`` (the build instant), and ``schema_version`` (the wire schema
  that shaped it): the lineage that makes rebuild-from-immutable-raw auditable.
- **The µs invariant (§4, doctrine)** — all time-aggregation is exact integer
  MICROSECONDS, never ms-floored or float-seconds, so a DuckDB rollup equals an
  independent pure recompute exactly. The test suite carries a sub-ms fixture as the
  permanent regression net (the shape that caught D0's ms-flooring divergence).

Layout + rules as ratified: ``reports/tier/raw/date=<UTC>/device=<id>/part.parquet``,
hive partitions, wire-truth columns only (config_id never blended; no legacy %; no
plant identity — read-time joins), derived + disposable (delete-and-rebuild), the
``data`` branch never. Supersedes the throwaway-tolerant ``tier_d0`` tracer.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date as date_t
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.parse_v1 import (
    parse_file,
)

_HERE = Path(__file__).resolve().parent

_REPO = _HERE.parents[1]
_TIER_ROOT = _REPO / "reports" / "tier" / "raw"

# §5 dwell default: 2x the 30 s cadence, in MICROSECONDS (§4: integer µs everywhere).
CAP_US = 120_000_000

# §3 — the contract's column order: wire truth, then the provenance trio.
COLUMNS = (
    "timestamp_utc",
    "device_id",
    "sensor_id",
    "raw_value",
    "band",
    "quality_flag",
    "session_id",
    "config_id",
    "source_file",
    "ingest_ts",
    "schema_version",
)


def tagged_day_rows(files, device_id: str, day: date_t) -> list[tuple]:
    """Parse each file SEPARATELY (per-row ``source_file`` lineage — §3) and slice the
    device-day: soil rows for ``device_id`` whose parsed UTC timestamp falls on ``day``
    (never the filename — rotation names lie, §2). Returns (reading, source_basename)
    pairs sorted by (sensor, time)."""
    out: list[tuple] = []
    for f in files:
        base = Path(f).name
        for r in parse_file(f).readings:
            if (
                r.record_type == "plants.soil"
                and r.device_id == device_id
                and r.timestamp_utc is not None
                and r.timestamp_utc.date() == day
            ):
                out.append((r, base))
    out.sort(key=lambda p: (p[0].sensor_id, p[0].timestamp_utc))
    return out


def build_partition(
    tagged,
    device_id: str,
    day: date_t,
    out_root: Path | None = None,
    filename: str = "part.parquet",
):
    """Write one (day, device) partition per the contract; return ``(path, stats)``
    with the §6 fidelity gate computed FROM the written Parquet (rows, raw checksum,
    distinct sensors). ``ingest_ts`` is one instant for the whole batch. ``filename``
    lets D3 live ingest write ``append-*.parquet`` siblings through this same schema
    path (contract §8) — the default stays the canonical ``part.parquet``."""
    import duckdb

    ingest = datetime.now(timezone.utc).replace(tzinfo=None)  # µs, UTC-naive (§3)
    out_dir = (
        (Path(out_root) if out_root else _TIER_ROOT)
        / f"date={day.isoformat()}"
        / f"device={device_id}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / filename
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE raw_day (
            timestamp_utc TIMESTAMP, device_id VARCHAR, sensor_id VARCHAR,
            raw_value INTEGER, band VARCHAR, quality_flag VARCHAR,
            session_id VARCHAR, config_id VARCHAR,
            source_file VARCHAR, ingest_ts TIMESTAMP, schema_version INTEGER
        )
        """
    )
    con.executemany(
        "INSERT INTO raw_day VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                r.timestamp_utc.replace(tzinfo=None),
                r.device_id,
                r.sensor_id,
                r.raw_value,
                r.band,
                r.quality_flag,
                r.session_id,
                r.config_id,
                src,
                ingest,
                r.schema_version,
            )
            for r, src in tagged
        ],
    )
    con.execute(
        "COPY (SELECT * FROM raw_day ORDER BY sensor_id, timestamp_utc) "
        f"TO '{out.as_posix()}' (FORMAT PARQUET)"
    )
    n, raw_sum, sensors = con.execute(
        "SELECT COUNT(*), SUM(raw_value), COUNT(DISTINCT sensor_id) "
        f"FROM read_parquet('{out.as_posix()}')"
    ).fetchone()
    con.close()
    return out, {"rows": n, "raw_sum": raw_sum, "sensors": sensors}


def hours_per_band_duckdb(
    parquet: Path, assignments: list[tuple], cap_us: int = CAP_US
) -> dict:
    """The duration-shaped answer from the STORE via DuckDB, under the §4 µs invariant:
    ``{(plant_id, band): dwell_us}``.

    ``assignments``: the temporal intervals from ``registry_assignments`` —
    ``(device_id, port, plant_id, start_ts, end_ts)``. **The join is temporal**
    (#1331, §3): a reading resolves to the assignment whose interval COVERS its own
    timestamp, so a probe move relabels only the readings taken after it."""
    import duckdb

    con = duckdb.connect()
    con.execute(
        "CREATE TABLE plant_map (device_id VARCHAR, port VARCHAR, plant_id VARCHAR,"
        " start_ts TIMESTAMP, end_ts TIMESTAMP)"
    )
    con.executemany(
        "INSERT INTO plant_map VALUES (?, ?, ?, ?, ?)",
        [
            (d, s, p, _as_naive_utc(st), _as_naive_utc(en))
            for d, s, p, st, en in assignments
        ],
    )
    got = con.execute(
        f"""
        WITH seq AS (
            SELECT device_id, sensor_id, band, quality_flag, timestamp_utc,
                   epoch_us(timestamp_utc) AS us,
                   lead(epoch_us(timestamp_utc)) OVER (
                       PARTITION BY device_id, sensor_id ORDER BY timestamp_utc
                   ) AS next_us
            FROM read_parquet('{parquet.as_posix()}')
        )
        SELECT m.plant_id, s.band,
               CAST(SUM(CASE WHEN s.next_us IS NULL THEN 0
                             ELSE LEAST(s.next_us - s.us, {cap_us}) END) AS BIGINT)
        FROM seq s
        JOIN plant_map m
          ON m.device_id = s.device_id
         AND m.port = s.sensor_id
         -- the covering interval, never the open one (§3): a null start_ts covers
         -- grandfathered history, a null end_ts is still-open
         AND (m.start_ts IS NULL OR m.start_ts <= s.timestamp_utc)
         AND (m.end_ts   IS NULL OR s.timestamp_utc <  m.end_ts)
        WHERE s.band IS NOT NULL AND s.quality_flag <> 'NO_SIGNAL'
        GROUP BY m.plant_id, s.band
        """
    ).fetchall()
    con.close()
    return {(p, b): int(us) for p, b, us in got}


def _as_naive_utc(ts):
    """An ISO string or datetime -> UTC-naive datetime (the §3 stored shape). None
    stays None: a null bound is 'unbounded on that side', not a moment."""
    if ts in (None, ""):
        return None
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return ts.replace(tzinfo=None) if ts.tzinfo is not None else ts


def resolve_plant_at(assignments: list[tuple], device_id, port, when) -> str | None:
    """The plant on ``(device_id, port)`` **at the reading's own instant** — the
    covering interval, never the open one (§3).

    This is the oracle's resolution, and it is deliberately a DIFFERENT
    implementation from the SQL join it verifies: a linear scan per row rather than a
    relational join. An independent verifier must not share the premise it verifies —
    the whole reason #1331 existed is that the oracle inherited the flat-map premise
    from the same helper the implementation used, so both were wrong in agreement and
    the fidelity gate still passed."""
    when = _as_naive_utc(when)
    for dev, prt, plant, start, end in assignments:
        if dev != device_id or prt != port:
            continue
        start, end = _as_naive_utc(start), _as_naive_utc(end)
        if (start is None or start <= when) and (end is None or when < end):
            return plant
    return None


def hours_per_band_truth(
    tagged, assignments: list[tuple], cap_us: int = CAP_US
) -> dict:
    """The independent pure recompute (§4's other half) — Python over the parsed rows,
    exact integer µs, resolving identity **per row at that row's own timestamp**
    (#1331). The store answer must equal this EXACTLY."""
    by_sensor: dict = defaultdict(list)
    for r, _src in tagged:
        by_sensor[(r.device_id, r.sensor_id)].append(r)
    tally: dict = defaultdict(int)
    for (device_id, port), rs in by_sensor.items():
        rs.sort(key=lambda r: r.timestamp_utc)
        for i, r in enumerate(rs):
            if i + 1 < len(rs):
                gap = rs[i + 1].timestamp_utc - r.timestamp_utc
                dwell = min(gap // timedelta(microseconds=1), cap_us)  # exact int µs
            else:
                dwell = 0
            # per ROW, at that row's instant — not once per channel (#1331)
            plant = resolve_plant_at(assignments, device_id, port, r.timestamp_utc)
            if plant and r.band is not None and r.quality_flag != "NO_SIGNAL":
                tally[(plant, r.band)] += dwell
    return dict(tally)


def registry_assignments(registry_path: str | None = None) -> list[tuple]:
    """Every assignment as a temporal INTERVAL — ``(device_id, port, plant_id,
    start_ts, end_ts)``, closed and open alike (#1331, contract §3).

    Not "the open assignments". Resolving every row against *today's* assignment is
    exactly how history gets stitched onto the present: move a probe from ``p01`` to
    ``p02`` and every reading it ever took is retroactively relabelled ``p02``. The
    join must be temporal, or the never-stitch guarantee is inverted rather than
    upheld. ``start_ts=None`` covers grandfathered history; ``end_ts=None`` is
    still-open."""
    from tools.analytics.registry_model import load_model, load_registry_model

    model = load_model(registry_path) if registry_path else load_registry_model()
    return [
        (a.device_id, a.channel, a.plant_id, a.start_ts, a.end_ts)
        for a in model.assignments
    ]


def registry_plant_map(registry_path: str | None = None) -> dict:
    """(device_id, port) -> plant_id for the CURRENT moment only.

    **Not for resolving stored readings** — use ``registry_assignments`` and join on
    the interval (§3). Kept for callers that legitimately ask "what is on this channel
    right now" (a live card, a fleet glance), where today's answer IS the question."""
    from tools.analytics.registry_model import load_model, load_registry_model

    model = load_model(registry_path) if registry_path else load_registry_model()
    return {(a.device_id, a.channel): a.plant_id for a in model.open_assignments()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1239 D1 store: build one partition")
    ap.add_argument("--logs", default=str(_REPO / "logs"))
    ap.add_argument("--device", default="y9d41p")
    ap.add_argument("--date", default="2026-07-18", help="UTC day YYYY-MM-DD")
    ap.add_argument("--registry", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    day = date_t.fromisoformat(args.date)
    files = sorted(str(p) for p in Path(args.logs).glob(f"{args.device}_*.csv"))
    tagged = tagged_day_rows(files, args.device, day)
    if not tagged:
        print(f"no soil rows for {args.device} on {day} under {args.logs}")
        return 1

    parquet, stats = build_partition(
        tagged, args.device, day, Path(args.out) if args.out else None
    )
    pmap = registry_plant_map(args.registry)
    sql = hours_per_band_duckdb(parquet, pmap)
    truth = hours_per_band_truth(tagged, pmap)

    import duckdb

    con = duckdb.connect()
    srcs, vers = con.execute(
        "SELECT COUNT(DISTINCT source_file), COUNT(DISTINCT schema_version) "
        f"FROM read_parquet('{parquet.as_posix()}')"
    ).fetchone()
    con.close()
    print(f"partition: {parquet}")
    print(
        f"fidelity: rows {stats['rows']} (parsed {len(tagged)}) · "
        f"raw_sum {stats['raw_sum']} · sensors {stats['sensors']} · "
        f"provenance: {srcs} source files, {vers} schema version(s)"
    )
    verdict = "EXACT MATCH" if sql == truth else "MISMATCH"
    print(f"µs-invariant equality (store vs pure recompute): {verdict}")
    return 0 if sql == truth else 2


if __name__ == "__main__":
    sys.exit(main())
