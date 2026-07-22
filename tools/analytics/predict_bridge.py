#!/usr/bin/env python3
"""#1243 — D5: the Predict bridge. The tier's last slice and Predict's first stone:
**one segment shape** that the classifier (#863) writes and the predictor (#25) reads,
plus the dry-down-rate view derived from it.

The shape (one row per classified segment, per plant)::

    plant_id · kind · t0 · t1 · n · raw_first · raw_last · duration_us
             · rate_c_per_h · valid_for_trend · identity_source · caveat

Rules it carries, so no consumer re-derives them:

- **The mask binds here, once** (taxonomy contract §2): ``valid_for_trend`` is true
  only for ``steady-drying``. A consumer filtering on that column cannot accidentally
  fit a watering transient — the guarantee lives in the view, not in each caller.
- **Rates are exact integer µs** (store contract §4): the least-squares slope is fit
  over µs offsets and reported in counts/hour at the boundary. A segment too thin to
  fit honestly reports ``rate_c_per_h = None`` — never a fabricated zero.
- **Caveats travel** (ADR-0029 §6): a plant whose profile carries
  ``probe_reading_caveat`` stamps it on every one of its rows, so a predictor cannot
  consume the rate without also seeing why that channel's raw is distrusted.
- **Identity is resolved once, and the view says how** — the two-registries seam
  (below) is answered in one place with its provenance recorded, never guessed
  per-consumer.
- **Derived + disposable** (ADR-0031 §1): materializes to ``reports/tier/views/``,
  rebuilt whole from the raw tier; delete-and-rebuild, never patch.

**The two-registries resolution (the D5 entry decision).** Identity can resolve two
ways: the *temporal* ``registry_model`` (open assignments — the store contract §3
reference) or the *static* ``device_registry`` (what the live host actually runs). On
a host with no local temporal instance the temporal ladder falls back to the committed
example and maps a fleet that never logged a row — the failure C2 surfaced.

The bridge resolves **temporal-first, static-fallback, validated, provenance-stamped**:

1. Temporal wins only if its pairs **intersect the devices actually present in the
   tier**. Non-emptiness is not proof — that check is the whole guard, and it has a
   regression test built from the live failure.
2. Otherwise the static registry answers.
3. The series is then built **from the resolved pairs** (``series_from_pairs``), so
   ``identity_source`` is true *by construction* — not a label applied beside a
   different code path that did the real mapping.

No consumer has to know the seam exists; the day the temporal model is populated the
bridge switches by itself, and the switch is visible in the data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from channel_identity import (  # noqa: E402  (#1454 — the one S1-seam join)
    build_plant_index,
    channel_key,
)
from device_registry import load_registry  # noqa: E402
from plant_profiles import load_profiles  # noqa: E402
from segment_classifier import segments  # noqa: E402
from segment_history import TierRow  # noqa: E402
from tier_store import _TIER_ROOT  # noqa: E402

VIEWS_ROOT = _TIER_ROOT.parent / "views"
_US = timedelta(microseconds=1)
_US_PER_H = 3_600_000_000

# A segment thinner than this cannot carry an honest least-squares slope.
FIT_MIN_ROWS = 3

COLUMNS = (
    "plant_id",
    "kind",
    "t0",
    "t1",
    "n",
    "raw_first",
    "raw_last",
    "duration_us",
    "rate_c_per_h",
    "valid_for_trend",
    "identity_source",
    "caveat",
)


def resolve_identity(
    registry=None,
    registry_path: str | None = None,
    devices_in_tier: set | None = None,
) -> tuple[dict, str]:
    """The two-registries answer, in one place: ``({(device_id, channel): plant_id},
    source)`` where source is ``"temporal"`` or ``"static"``.

    Temporal first (the store contract §3 reference) — but **only if it resolves the
    fleet that actually exists in the tier**. A non-empty temporal map is not proof:
    on a host with no local temporal instance the loader falls back to the committed
    EXAMPLE, which returns plausible-looking pairs for devices that never logged a
    row (verified live: example ids vs the real boards, zero overlap). Preferring it
    on non-emptiness alone would stamp ``temporal`` on rows the static registry
    actually mapped — a provenance field that lies. So the test is intersection with
    ``devices_in_tier``, never mere presence."""
    try:
        from tier_store import registry_plant_map

        pairs = registry_plant_map(registry_path)
        if pairs and (
            devices_in_tier is None or {d for d, _c in pairs} & set(devices_in_tier)
        ):
            return pairs, "temporal"
    except Exception:  # a missing/unreadable temporal instance is not a crash
        pass
    reg = registry if registry is not None else load_registry(registry_path)
    # #1454: the one S1-seam join. Keep pairs as {key: plant_id} (the temporal branch
    # above builds the same shape) but derive it from the shared index, so both
    # branches and the lookup below fold the token through one function.
    pairs = {k: pl["plant_id"] for k, pl in build_plant_index(reg).items()}
    return pairs, "static"


def _tier_devices(root: Path | None = None) -> set:
    """The device ids that actually appear in the raw tier — the reality check the
    identity resolution is validated against."""
    import duckdb

    r = Path(root) if root is not None else _TIER_ROOT
    con = duckdb.connect()
    try:
        got = con.execute(
            "SELECT DISTINCT device_id FROM "
            f"read_parquet('{r.as_posix()}/*/*/*.parquet', hive_partitioning=false)"
        ).fetchall()
    except Exception:
        return set()
    finally:
        con.close()
    return {d for (d,) in got}


def series_from_pairs(pairs: dict, root: Path | None = None) -> dict:
    """Build the per-plant series using the RESOLVED pairs — the single resolution
    path, so ``identity_source`` is true by construction rather than by convention."""
    import duckdb

    r = Path(root) if root is not None else _TIER_ROOT
    con = duckdb.connect()
    rows = con.execute(
        "SELECT device_id, sensor_id, timestamp_utc, raw_value, quality_flag "
        f"FROM read_parquet('{r.as_posix()}/*/*/*.parquet', hive_partitioning=false) "
        "ORDER BY timestamp_utc"
    ).fetchall()
    con.close()
    from datetime import timezone

    series: dict[str, list[TierRow]] = {}
    for device_id, sensor_id, ts, raw, flag in rows:
        pid = pairs.get(channel_key(device_id, sensor_id))
        if pid is None:
            continue  # unmapped rows are C2's readout job, not the bridge's
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        series.setdefault(pid, []).append(TierRow(ts, raw, flag))
    return series


def _naive_utc(v):
    """Persist timestamps as TIMESTAMP (µs, UTC-naive) — the store contract §3 shape,
    the same coercion ``tier_store.build_partition`` applies.

    Why not TIMESTAMPTZ: the one clock is UTC (§3/§4), so a stored offset carries no
    information — it only drags DuckDB's timezone catalogue (and a `pytz` dependency)
    into a path whose whole invariant is exact integer µs. The in-memory rows stay
    tz-aware for the classifier; only the persisted view is naive."""
    return v.replace(tzinfo=None) if getattr(v, "tzinfo", None) is not None else v


def _slope_c_per_h(rows) -> float | None:
    """Least-squares counts/hour over exact integer µs offsets (§4). None when the
    run is too thin or degenerate — an honest absence, never a fabricated 0.0."""
    pts = [(r.timestamp_utc, r.raw_value) for r in rows if r.raw_value is not None]
    if len(pts) < FIT_MIN_ROWS:
        return None
    t0 = pts[0][0]
    xs = [(t - t0) // _US for t, _ in pts]
    ys = [float(v) for _, v in pts]
    n = len(pts)
    mx, my = sum(xs) / n, sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    slope_per_us = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return slope_per_us * _US_PER_H


def segment_rows(
    series: dict, identity_source: str, profiles: dict | None = None
) -> list[dict]:
    """THE shape — every classified segment of every plant as one flat row list.
    Written by the classifier's own ``segments()`` so the classifier and predictor
    can never drift apart on what a segment is."""
    profiles = profiles if profiles is not None else {}
    out: list[dict] = []
    for plant_id, rows in sorted(series.items()):
        prof = profiles.get(plant_id) or {}
        caveat = ((prof.get("hydrology") or {}).get("probe_reading_caveat")) or None
        for seg in segments(rows):
            span = rows[seg.i0 : seg.i1 + 1]
            valid = seg.kind == "steady-drying"
            out.append(
                {
                    "plant_id": plant_id,
                    "kind": seg.kind,
                    "t0": seg.t0.isoformat(),
                    "t1": seg.t1.isoformat(),
                    "n": seg.n,
                    "raw_first": span[0].raw_value,
                    "raw_last": span[-1].raw_value,
                    "duration_us": (seg.t1 - seg.t0) // _US,
                    # the rate is only meaningful on a valid arc; an invalid segment
                    # gets None rather than a slope nobody may use (mask binds once)
                    "rate_c_per_h": _slope_c_per_h(span) if valid else None,
                    "valid_for_trend": valid,
                    "identity_source": identity_source,
                    "caveat": caveat,
                }
            )
    return out


def current_arc(rows_for_plant: list[dict]) -> dict | None:
    """The predictor's direct read (#25): the plant's LATEST valid arc — the newest
    steady-drying segment, with its rate. None when the plant has no valid arc yet
    (freshly watered, or nothing but transients) — an honest abstain input."""
    valid = [r for r in rows_for_plant if r["valid_for_trend"]]
    if not valid:
        return None
    last = max(valid, key=lambda r: r["t1"])
    return {
        "plant_id": last["plant_id"],
        "t0": last["t0"],
        "t1": last["t1"],
        "n": last["n"],
        "raw_last": last["raw_last"],
        "rate_c_per_h": last["rate_c_per_h"],
        "identity_source": last["identity_source"],
        "caveat": last["caveat"],
    }


def build_views(
    root: Path | None = None,
    out_root: Path | None = None,
    registry_path: str | None = None,
    registry=None,
) -> dict:
    """Materialize the bridge whole from the raw tier: ``views/segments.parquet``
    (the shape) + ``views/current_arc.parquet`` (the predictor's read). Returns
    ``{segments, valid_segments, plants, identity_source, current_arcs}``. Pass
    ``registry`` to resolve against a specific fleet (the CLI passes a path)."""
    import duckdb

    out = Path(out_root) if out_root else VIEWS_ROOT
    out.mkdir(parents=True, exist_ok=True)
    if registry is None and registry_path:
        registry = load_registry(registry_path)
    pairs, source = resolve_identity(registry, registry_path, _tier_devices(root))
    series = series_from_pairs(pairs, root)
    profiles, _findings = load_profiles()
    rows = segment_rows(series, source, profiles)
    by_plant: dict[str, list[dict]] = {}
    for r in rows:
        by_plant.setdefault(r["plant_id"], []).append(r)
    arcs = [a for a in (current_arc(v) for v in by_plant.values()) if a]

    con = duckdb.connect()
    con.execute(
        "CREATE TABLE seg (plant_id VARCHAR, kind VARCHAR, t0 TIMESTAMP,"
        " t1 TIMESTAMP, n INTEGER, raw_first DOUBLE, raw_last DOUBLE,"
        " duration_us BIGINT, rate_c_per_h DOUBLE, valid_for_trend BOOLEAN,"
        " identity_source VARCHAR, caveat VARCHAR)"
    )
    if rows:
        con.executemany(
            "INSERT INTO seg VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [tuple(_naive_utc(r[c]) for c in COLUMNS) for r in rows],
        )
    con.execute(
        f"COPY (SELECT * FROM seg ORDER BY plant_id, t0) "
        f"TO '{(out / 'segments.parquet').as_posix()}' (FORMAT PARQUET)"
    )
    con.execute(
        "CREATE TABLE arc (plant_id VARCHAR, t0 TIMESTAMP, t1 TIMESTAMP,"
        " n INTEGER, raw_last DOUBLE, rate_c_per_h DOUBLE,"
        " identity_source VARCHAR, caveat VARCHAR)"
    )
    if arcs:
        con.executemany(
            "INSERT INTO arc VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    a["plant_id"],
                    _naive_utc(a["t0"]),
                    _naive_utc(a["t1"]),
                    a["n"],
                    a["raw_last"],
                    a["rate_c_per_h"],
                    a["identity_source"],
                    a["caveat"],
                )
                for a in arcs
            ],
        )
    con.execute(
        f"COPY (SELECT * FROM arc ORDER BY plant_id) "
        f"TO '{(out / 'current_arc.parquet').as_posix()}' (FORMAT PARQUET)"
    )
    con.close()
    return {
        "segments": len(rows),
        "valid_segments": sum(1 for r in rows if r["valid_for_trend"]),
        "plants": len(by_plant),
        "identity_source": source,
        "current_arcs": len(arcs),
        "pairs_resolved": len(pairs),
    }


def read_segments(
    plant_id: str | None = None, valid_only: bool = False, root: Path | None = None
) -> list[dict]:
    """Read the shape back — the consumer seam (#863 writes it, #25 reads it)."""
    import duckdb

    src = (Path(root) if root else VIEWS_ROOT) / "segments.parquet"
    where, args = [], []
    if plant_id is not None:
        where.append("plant_id = ?")
        args.append(plant_id)
    if valid_only:
        where.append("valid_for_trend")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    con = duckdb.connect()
    got = con.execute(
        f"SELECT {', '.join(COLUMNS)} FROM read_parquet('{src.as_posix()}')"
        f"{clause} ORDER BY plant_id, t0",
        args,
    ).fetchall()
    con.close()
    return [dict(zip(COLUMNS, r)) for r in got]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="#1243 D5: build the Predict bridge views")
    ap.add_argument("--root", default=None, help="tier raw root")
    ap.add_argument(
        "--out", default=None, help="views root (default reports/tier/views)"
    )
    ap.add_argument("--registry", default=None)
    ap.add_argument("--json", dest="json_out", default=None)
    args = ap.parse_args(argv)
    stats = build_views(
        Path(args.root) if args.root else None,
        Path(args.out) if args.out else None,
        args.registry,
    )
    print(
        f"bridge: {stats['segments']} segments "
        f"({stats['valid_segments']} valid-for-trend) · {stats['plants']} plants · "
        f"{stats['current_arcs']} current arcs · identity={stats['identity_source']}"
    )
    arcs = sorted(
        read_segments(valid_only=True, root=Path(args.out) if args.out else None),
        key=lambda r: r["plant_id"],
    )
    seen = set()
    print("plant     latest valid arc            n   rate c/h   caveat")
    for r in sorted(arcs, key=lambda r: (r["plant_id"], r["t1"]), reverse=True):
        if r["plant_id"] in seen:
            continue
        seen.add(r["plant_id"])
        rate = "—" if r["rate_c_per_h"] is None else f"{r['rate_c_per_h']:+.1f}"
        print(
            f"{r['plant_id']:<8}  {str(r['t0'])[:16]} → {str(r['t1'])[11:16]}"
            f"  {r['n']:>4}  {rate:>8}   {r['caveat'] or ''}"
        )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(stats, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
