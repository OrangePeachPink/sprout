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

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from parse_v1 import parse_file  # noqa: E402  (the ONE parse boundary, ADR-0021)

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


def build_partition(tagged, device_id: str, day: date_t, out_root: Path | None = None):
    """Write one (day, device) partition per the contract; return ``(path, stats)``
    with the §6 fidelity gate computed FROM the written Parquet (rows, raw checksum,
    distinct sensors). ``ingest_ts`` is one instant for the whole batch."""
    import duckdb

    ingest = datetime.now(timezone.utc).replace(tzinfo=None)  # µs, UTC-naive (§3)
    out_dir = (
        (Path(out_root) if out_root else _TIER_ROOT)
        / f"date={day.isoformat()}"
        / f"device={device_id}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "part.parquet"
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


def hours_per_band_duckdb(parquet: Path, plant_map: dict, cap_us: int = CAP_US) -> dict:
    """The duration-shaped answer from the STORE via DuckDB, under the §4 µs invariant:
    {(plant_id, band): dwell_us}. ``plant_map``: (device_id, port) -> plant_id."""
    import duckdb

    con = duckdb.connect()
    con.execute(
        "CREATE TABLE plant_map (device_id VARCHAR, port VARCHAR, plant_id VARCHAR)"
    )
    con.executemany(
        "INSERT INTO plant_map VALUES (?, ?, ?)",
        [(d, s, p) for (d, s), p in plant_map.items()],
    )
    got = con.execute(
        f"""
        WITH seq AS (
            SELECT device_id, sensor_id, band, quality_flag,
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
        JOIN plant_map m ON m.device_id = s.device_id AND m.port = s.sensor_id
        WHERE s.band IS NOT NULL AND s.quality_flag <> 'NO_SIGNAL'
        GROUP BY m.plant_id, s.band
        """
    ).fetchall()
    con.close()
    return {(p, b): int(us) for p, b, us in got}


def hours_per_band_truth(tagged, plant_map: dict, cap_us: int = CAP_US) -> dict:
    """The independent pure recompute (§4's other half) — Python over the parsed rows,
    exact integer µs. The store answer must equal this EXACTLY."""
    by_sensor: dict = defaultdict(list)
    for r, _src in tagged:
        by_sensor[(r.device_id, r.sensor_id)].append(r)
    tally: dict = defaultdict(int)
    for key, rs in by_sensor.items():
        plant = plant_map.get(key)
        rs.sort(key=lambda r: r.timestamp_utc)
        for i, r in enumerate(rs):
            if i + 1 < len(rs):
                gap = rs[i + 1].timestamp_utc - r.timestamp_utc
                dwell = min(gap // timedelta(microseconds=1), cap_us)  # exact int µs
            else:
                dwell = 0
            if plant and r.band is not None and r.quality_flag != "NO_SIGNAL":
                tally[(plant, r.band)] += dwell
    return dict(tally)


def registry_plant_map(registry_path: str | None = None) -> dict:
    """(device_id, port) -> plant_id from the temporal registry's open assignments —
    identity resolves at READ time (§3); the store stays board-true."""
    from registry_model import load_model, load_registry_model

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
