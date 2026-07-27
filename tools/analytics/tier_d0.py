#!/usr/bin/env python3
"""#1238 — D0 TRACER: one CSV device-day → one Parquet file → one DuckDB answer.

Status: legacy — superseded by ``docs/TIER_STORE_CONTRACT.md`` (#1239), which names
this module as the historical evidence it cites. Kept rather than deleted so that
citation resolves; not a maintained path (ADR-0038 §7).

The thinnest end-to-end proof of the ADR-0031 tier pipe (Accepted; DuckDB/Parquet ruled
#915): map one real device-day of schema-v3/v4 rows into ONE Parquet file in the
candidate layout, then answer ONE Predict-shaped question in DuckDB — **hours-per-band
per plant that day** — with the same question computed independently from the parsed CSV
rows (pure Python) and asserted EQUAL. Deliberately throwaway-tolerant: the output is
evidence for the #1239 D1 store contract, not the store itself.

Candidate layout (D0's proposal for D1 to review):
    reports/tier/raw/date=<UTC-date>/device=<device_id>/part.parquet
- Hive-style ``date=`` / ``device=`` partitions — the per-board-only rule (ADR-0031 §2)
  is visible in the path; nothing ever rolls up across boards.
- Columns are wire truth, per-channel: ``timestamp_utc`` (UTC-naive TIMESTAMP),
  ``device_id``, ``sensor_id`` (the board port), ``raw_value``, ``band`` (the
  device-emitted level — ground truth), ``quality_flag``, ``session_id``,
  ``config_id`` (ADR-0025 — a COLUMN, never blended; a day spanning a config change
  keeps both fingerprints distinguishable).
- No legacy ``value`` %% (ADR-0031 §2: over raw + band, never the index). No plant
  names — identity resolves at READ time via a registry join (raw stays wire truth).
- Derived + disposable (ADR-0031 §1): lives under gitignored ``reports/``; delete and
  rebuild, never patch.

The question's dwell rule (D0's cut; D1 refines): each reading owns the time to the
NEXT physical sample on its (device, sensor), capped at ``CAP_US`` (2x the 30 s cadence
— a logging gap never inflates a band's hours); the day's last reading owns 0. Hours
tally only band-bearing rows (a real band, not NO_SIGNAL) mapped to a plant.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date as date_t
from datetime import timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.parse_v1 import parse_files  # noqa: E402

_REPO = _HERE.parents[1]
_TIER_ROOT = _REPO / "reports" / "tier" / "raw"

# Dwell cap: 2x the 30 s soil cadence, in MICROSECONDS. A gap (reboot, WiFi drop)
# attributes at most this much time to the band before it — never the silent stretch.
# Microseconds because both clocks are natively us-precision (DuckDB TIMESTAMP and
# Python datetime), so the two answer paths are exactly equal by construction — an
# ms-floored comparison drifts off-by-one on real sub-ms timestamps.
CAP_US = 120_000_000

_COLUMNS = (
    "timestamp_utc",
    "device_id",
    "sensor_id",
    "raw_value",
    "band",
    "quality_flag",
    "session_id",
    "config_id",
)


def day_rows(readings, device_id: str, day: date_t) -> list:
    """The device-day slice: soil rows for ``device_id`` whose UTC timestamp falls on
    ``day``. Filters by the PARSED timestamp, never the filename (rotation names lie
    across midnight)."""
    return sorted(
        (
            r
            for r in readings
            if r.record_type == "plants.soil"
            and r.device_id == device_id
            and r.timestamp_utc is not None
            and r.timestamp_utc.date() == day
        ),
        key=lambda r: (r.sensor_id, r.timestamp_utc),
    )


def build_parquet(rows, device_id: str, day: date_t, out_root: Path | None = None):
    """Write the device-day to ONE Parquet file in the candidate layout; return
    ``(path, stats)`` where stats carry the fidelity trio (row count, raw sum,
    distinct sensors) computed FROM THE PARQUET by DuckDB."""
    import duckdb

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
            session_id VARCHAR, config_id VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO raw_day VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                r.timestamp_utc.replace(tzinfo=None),  # stored UTC-naive, named _utc
                r.device_id,
                r.sensor_id,
                r.raw_value,
                r.band,
                r.quality_flag,
                r.session_id,
                r.config_id,
            )
            for r in rows
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
    """The Predict-shaped answer, from the PARQUET via DuckDB: {(plant_id, band):
    dwell_us}. ``plant_map`` maps (device_id, port sensor_id) -> plant_id."""
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


def hours_per_band_truth(rows, plant_map: dict, cap_us: int = CAP_US) -> dict:
    """The SAME question computed independently from the parsed CSV rows (pure Python,
    no Parquet, no SQL) — the fidelity oracle the DuckDB answer must equal exactly."""
    by_sensor: dict = defaultdict(list)
    for r in rows:
        by_sensor[(r.device_id, r.sensor_id)].append(r)
    tally: dict = defaultdict(int)
    for key, rs in by_sensor.items():
        plant = plant_map.get(key)
        rs.sort(key=lambda r: r.timestamp_utc)
        for i, r in enumerate(rs):
            if i + 1 < len(rs):
                gap = rs[i + 1].timestamp_utc - r.timestamp_utc
                dwell = min(gap // timedelta(microseconds=1), cap_us)  # exact int us
            else:
                dwell = 0  # the day's last reading owns nothing it can't prove
            if plant and r.band is not None and r.quality_flag != "NO_SIGNAL":
                tally[(plant, r.band)] += dwell
    return dict(tally)


def registry_plant_map(registry_path: str | None = None) -> dict:
    """(device_id, port) -> plant_id from the temporal registry's open assignments.
    Identity is resolved at read time — the Parquet stays wire truth."""
    from tools.analytics.registry_model import load_model, load_registry_model

    model = load_model(registry_path) if registry_path else load_registry_model()
    return {(a.device_id, a.channel): a.plant_id for a in model.open_assignments()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="#1238 D0 tracer: CSV day -> Parquet -> DuckDB"
    )
    ap.add_argument("--logs", default=str(_REPO / "logs"), help="log dir to read")
    ap.add_argument("--device", default="y9d41p")
    ap.add_argument("--date", default="2026-07-18", help="UTC day YYYY-MM-DD")
    ap.add_argument("--registry", default=None, help="registry json (else: discover)")
    ap.add_argument("--out", default=None, help="tier root (default: reports/tier/raw)")
    args = ap.parse_args(argv)

    day = date_t.fromisoformat(args.date)
    files = sorted(str(p) for p in Path(args.logs).glob(f"{args.device}_*.csv"))
    data = parse_files(files)
    rows = day_rows(data.readings, args.device, day)
    if not rows:
        print(f"no soil rows for {args.device} on {day} under {args.logs}")
        return 1

    parquet, stats = build_parquet(
        rows, args.device, day, Path(args.out) if args.out else None
    )
    pmap = registry_plant_map(args.registry)
    sql = hours_per_band_duckdb(parquet, pmap)
    truth = hours_per_band_truth(rows, pmap)

    print(f"device-day: {args.device} {day}  ({len(files)} files scanned)")
    print(f"parquet: {parquet}")
    print(
        f"fidelity: rows {stats['rows']} (parsed {len(rows)}) · "
        f"raw_sum {stats['raw_sum']} (parsed "
        f"{sum(r.raw_value for r in rows if r.raw_value is not None)}) · "
        f"sensors {stats['sensors']}"
    )
    match = sql == truth
    verdict = "EXACT MATCH" if match else "MISMATCH"
    print(f"answer equality (DuckDB vs CSV-truth): {verdict}")
    print("\nhours-per-band per plant:")
    for (plant, band), us in sorted(sql.items()):
        print(f"  {plant:5s} {band:14s} {us / 3_600_000_000:7.2f} h")
    return 0 if match else 2


if __name__ == "__main__":
    sys.exit(main())
