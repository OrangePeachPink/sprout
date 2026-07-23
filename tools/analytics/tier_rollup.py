#!/usr/bin/env python3
"""#1242 — D4: the ADR-0031 rollup tiers (Accepted #915; all forks ruled). Aged
read-models over the immutable raw tier: full-fidelity recent stays on raw (#827's
cache path); month/year windows read coarser buckets that scale with buckets, not
rows. #978's sub-linear long-range acceptance rides this.

The ruled contract, implemented:

- **Envelope, never smooth** (§2/§4): per bucket per (device, sensor) — ``mean`` /
  ``min`` / ``max`` / ``spread`` / ``n``; every read answer is LABELED (``tier``,
  ``bucket_seconds``, ``n``) so a rollup can never masquerade as raw samples.
- **Quality carried, never averaged** (§2): ``n_flagged`` + the distinct non-OK
  tokens ride each bucket; a fault never dissolves into a mean.
- **``config_id`` carried on the bucket + never blended** (fork 4 as ruled): the
  bucket key includes ``config_id``, so a gain/itime change splits buckets by
  construction. Cross-board rollups don't exist (per-device partitions, ADR-0019).
- **Over ``raw_value`` (+ band endpoints), never the legacy %** (§2 / ADR-0006 §4).
- **Events are never downsampled** (§3): a first-class sparse event table —
  band transitions, quality-flip run starts, session boundaries, config changes —
  at EXACT timestamps, derived deterministically from the stored rows (rebuildable
  like every tier). Watering/pass events join additively when the C-arc lands
  (the ``kind`` column is open by design).
- **Granularities are config, not hardcoded** (fork 2): 1-min → 15-min → hourly is
  the ruled starting map; re-tuning re-materializes tiers, never touches consumers.
- **Bucket math is exact integer µs** (store contract §4): bucket floor =
  ``epoch_us // (g·10⁶) · (g·10⁶)`` — BIGINT division in DuckDB, ``//`` in Python.
- **Derived + disposable** (§1): ``reports/tier/rollup`` + ``reports/tier/events``
  rebuild whole from the raw tier (full-rebuild-available as ruled); delete-and-
  rebuild, never patch. Readers glob ``*.parquet`` (live appends included, §8).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent

from tools.analytics.tier_store import _TIER_ROOT  # noqa: E402

_TIER_HOME = _TIER_ROOT.parent  # reports/tier
ROLLUP_ROOT = _TIER_HOME / "rollup"
EVENTS_ROOT = _TIER_HOME / "events"

# Fork 2 (ruled): the starting granularity map — seconds per bucket, config.
GRANULARITIES: dict[str, int] = {"t1": 60, "t2": 900, "t3": 3600}

# §5's range→source switch (starting map): spans up to the bound (hours) read the
# named source; raw = #827's cache path, not this module.
RANGE_TIER: tuple[tuple[float | None, str], ...] = (
    (48.0, "raw"),
    (7 * 24.0, "t1"),
    (30 * 24.0, "t2"),
    (None, "t3"),
)


def pick_tier(span_hours: float) -> str:
    """The one range→source switch (§5): which source serves a window this wide."""
    for bound, tier in RANGE_TIER:
        if bound is None or span_hours <= bound:
            return tier
    return "t3"  # pragma: no cover — the None bound is the catch-all


def _raw_glob(raw_root: Path | None) -> str:
    root = Path(raw_root) if raw_root else _TIER_ROOT
    return f"{root.as_posix()}/*/*/*.parquet"


def build_rollups(
    raw_root: Path | None = None,
    out_root: Path | None = None,
    granularities: dict[str, int] | None = None,
) -> dict:
    """Materialize every tier, whole, from the raw tier (full rebuild — cheap, and
    the ruled always-available path). One SQL pass per tier; hive-partitioned
    ``tier=<t>/date=<UTC>/device=<id>``. Returns {tier: bucket_rows}."""
    import duckdb

    out = Path(out_root) if out_root else ROLLUP_ROOT
    grans = granularities or GRANULARITIES
    stats: dict[str, int] = {}
    con = duckdb.connect()
    for tier, secs in grans.items():
        g_us = secs * 1_000_000
        tier_dir = out / f"tier={tier}"
        tier_dir.mkdir(parents=True, exist_ok=True)
        con.execute(
            f"""
            COPY (
                WITH b AS (
                    SELECT device_id, sensor_id, config_id,
                           (epoch_us(timestamp_utc) // {g_us}) * {g_us} AS bucket_us,
                           raw_value, band, quality_flag, timestamp_utc
                    FROM read_parquet('{_raw_glob(raw_root)}', hive_partitioning=false)
                )
                SELECT device_id, sensor_id, config_id, bucket_us,
                       {secs} AS bucket_seconds,
                       COUNT(*) AS n,
                       AVG(raw_value) AS mean,
                       MIN(raw_value) AS min,
                       MAX(raw_value) AS max,
                       MAX(raw_value) - MIN(raw_value) AS spread,
                       COUNT(*) FILTER (quality_flag <> 'OK') AS n_flagged,
                       COALESCE(string_agg(DISTINCT quality_flag, '+'
                                           ORDER BY quality_flag)
                                FILTER (quality_flag <> 'OK'), '') AS flags,
                       arg_min(band, timestamp_utc) AS band_first,
                       arg_max(band, timestamp_utc) AS band_last,
                       strftime(to_timestamp(bucket_us / 1000000), '%Y-%m-%d') AS date,
                       device_id AS device
                FROM b
                GROUP BY device_id, sensor_id, config_id, bucket_us
                ORDER BY device_id, sensor_id, bucket_us
            ) TO '{tier_dir.as_posix()}'
            (FORMAT PARQUET, PARTITION_BY (date, device), OVERWRITE_OR_IGNORE)
            """
        )
        stats[tier] = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{tier_dir.as_posix()}/*/*/*.parquet')"
        ).fetchone()[0]
    con.close()
    return stats


def build_events(raw_root: Path | None = None, out_root: Path | None = None) -> int:
    """Materialize the sparse event table, whole (§3): band transitions, quality-flip
    run starts, session boundaries, config changes — exact timestamps, derived
    deterministically per (device, sensor) from the stored rows. Returns row count."""
    import duckdb

    out = Path(out_root) if out_root else EVENTS_ROOT
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "part.parquet"
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (
            WITH seq AS (
                SELECT timestamp_utc, device_id, sensor_id, band, quality_flag,
                       session_id, config_id,
                       lag(band) OVER w AS p_band,
                       lag(quality_flag) OVER w AS p_flag,
                       lag(session_id) OVER w AS p_session,
                       lag(config_id) OVER w AS p_config
                FROM read_parquet('{_raw_glob(raw_root)}', hive_partitioning=false)
                WINDOW w AS (PARTITION BY device_id, sensor_id ORDER BY timestamp_utc)
            )
            SELECT timestamp_utc, device_id, sensor_id, 'band' AS kind,
                   COALESCE(p_band, '') || '->' || band AS detail
            FROM seq WHERE p_band IS NOT NULL AND band IS DISTINCT FROM p_band
            UNION ALL
            SELECT timestamp_utc, device_id, sensor_id, 'quality',
                   quality_flag
            FROM seq WHERE quality_flag <> 'OK'
                  AND (p_flag IS NULL OR p_flag = 'OK')
            UNION ALL
            SELECT timestamp_utc, device_id, sensor_id, 'session',
                   COALESCE(p_session, '') || '->' || session_id
            FROM seq WHERE p_session IS NOT NULL
                  AND session_id IS DISTINCT FROM p_session
            UNION ALL
            SELECT timestamp_utc, device_id, sensor_id, 'config',
                   COALESCE(p_config, '') || '->' || config_id
            FROM seq WHERE p_config IS NOT NULL
                  AND config_id IS DISTINCT FROM p_config
            ORDER BY timestamp_utc, device_id, sensor_id, kind
        ) TO '{dest.as_posix()}' (FORMAT PARQUET)
        """
    )
    n = con.execute(
        f"SELECT COUNT(*) FROM read_parquet('{dest.as_posix()}')"
    ).fetchone()[0]
    con.close()
    return n


def read_envelope(
    device_id: str,
    sensor_id: str,
    t0,
    t1,
    tier: str | None = None,
    root: Path | None = None,
) -> list[dict]:
    """Labeled envelope buckets for one channel in [t0, t1) — every point carries
    ``tier`` / ``bucket_seconds`` / ``n`` (§4: a rollup never masquerades as raw)."""
    import duckdb

    if tier is None:
        tier = pick_tier((t1 - t0).total_seconds() / 3600.0)
    if tier == "raw":
        raise ValueError("raw windows ride the #827 cache path, not the rollup tier")
    out = Path(root) if root else ROLLUP_ROOT
    con = duckdb.connect()
    rows = con.execute(
        "SELECT bucket_us, bucket_seconds, n, mean, min, max, spread, "
        "n_flagged, flags, config_id, band_first, band_last "
        f"FROM read_parquet('{(out / f'tier={tier}').as_posix()}/*/*/*.parquet', "
        "hive_partitioning=false) "
        "WHERE device_id = ? AND sensor_id = ? "
        "AND bucket_us >= epoch_us(CAST(? AS TIMESTAMP)) "
        "AND bucket_us < epoch_us(CAST(? AS TIMESTAMP)) "
        "ORDER BY bucket_us",
        [device_id, sensor_id, t0.replace(tzinfo=None), t1.replace(tzinfo=None)],
    ).fetchall()
    con.close()
    cols = (
        "bucket_us",
        "bucket_seconds",
        "n",
        "mean",
        "min",
        "max",
        "spread",
        "n_flagged",
        "flags",
        "config_id",
        "band_first",
        "band_last",
    )
    return [dict(zip(cols, r), tier=tier) for r in rows]


def read_events(
    device_id: str | None = None,
    kind: str | None = None,
    root: Path | None = None,
) -> list[dict]:
    """The exact-timestamp event record, filterable — never downsampled (§3)."""
    import duckdb

    dest = (Path(root) if root else EVENTS_ROOT) / "part.parquet"
    where, args = [], []
    if device_id is not None:
        where.append("device_id = ?")
        args.append(device_id)
    if kind is not None:
        where.append("kind = ?")
        args.append(kind)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    con = duckdb.connect()
    rows = con.execute(
        "SELECT timestamp_utc, device_id, sensor_id, kind, detail "
        f"FROM read_parquet('{dest.as_posix()}'){clause} "
        "ORDER BY timestamp_utc",
        args,
    ).fetchall()
    con.close()
    cols = ("timestamp_utc", "device_id", "sensor_id", "kind", "detail")
    return [dict(zip(cols, r)) for r in rows]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1242 D4: build the rollup + event tiers")
    ap.add_argument(
        "--raw", default=None, help="raw tier root (default reports/tier/raw)"
    )
    ap.add_argument(
        "--out", default=None, help="rollup root (default reports/tier/rollup)"
    )
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    stats = build_rollups(
        Path(args.raw) if args.raw else None, Path(args.out) if args.out else None
    )
    n_events = build_events(Path(args.raw) if args.raw else None)
    dt = time.perf_counter() - t0
    per_tier = " · ".join(f"{t}={n}" for t, n in stats.items())
    print(f"rollups: {per_tier} buckets · events: {n_events} · {dt:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# --------------------------------------------------------------------------- #
# #978 — the long-range trajectory reader (the tier's answer to O(window rows))
# --------------------------------------------------------------------------- #

# A bucket gap wider than this many bucket-widths is a real logging interruption,
# not sampling noise — the series BREAKS there rather than drawing across it.
GAP_BUCKETS = 2


def trajectory_series(
    device_id: str,
    sensor_id: str,
    t0,
    t1,
    tier: str | None = None,
    root: Path | None = None,
) -> dict:
    """One channel's long-range trajectory read from the rollup tier — the #978
    substitute for re-parsing every raw row in the window.

    Returns a **labeled envelope**, never a smoothed line (ADR-0031 §4 / ADR-0006 §4):

        {tier, bucket_seconds, n_points, n_readings, points: [
            {x, mean, min, max, n, flagged} | {x, mean: None}  # a gap BREAK
        ]}

    Honesty fence, inherited and enforced here:

    - **min/max ride every point** — a spike is truth; a mean-only long-range line
      would erase exactly the events the operator is looking for.
    - **Gaps are surfaced, never bridged** — a run of missing buckets emits an
      explicit break point (``mean: None``), so the chart cannot draw a straight
      line across an outage (E9's rule, on the bucket axis).
    - **``n`` per point** — a 2-sample bucket is not a 60-sample bucket, and the
      render is required to be able to say so.
    - **`flagged`** carries the bucket's non-OK count; quality is never averaged
      away (contract §2).
    """
    if tier is None:
        tier = pick_tier((t1 - t0).total_seconds() / 3600.0)
    if tier == "raw":
        raise ValueError("short windows ride the raw path (#827 cache), not the tier")
    buckets = read_envelope(device_id, sensor_id, t0, t1, tier=tier, root=root)
    secs = GRANULARITIES.get(tier, 3600)
    gap_us = GAP_BUCKETS * secs * 1_000_000
    points: list[dict] = []
    prev_us = None
    for b in buckets:
        if prev_us is not None and (b["bucket_us"] - prev_us) > gap_us:
            # an outage: an explicit break so no line is drawn across it
            points.append({"x": (prev_us + b["bucket_us"]) / 2e6, "mean": None})
        points.append(
            {
                "x": b["bucket_us"] / 1e6,
                "mean": b["mean"],
                "min": b["min"],
                "max": b["max"],
                "n": b["n"],
                "flagged": b["n_flagged"],
            }
        )
        prev_us = b["bucket_us"]
    return {
        "tier": tier,
        "bucket_seconds": secs,
        "n_points": len(points),
        "n_readings": sum(b["n"] for b in buckets),
        "points": points,
    }
