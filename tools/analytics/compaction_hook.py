"""#1292 (DX / operator) — the launcher-managed daily tier-maintenance hook.

The one-click doctrine: the operator never runs a tier command or sets up a Windows
scheduled task (a second surface). Instead the launcher — the running Sprout server that
already owns the collector lifecycle — calls ``maybe_ingest_and_compact()`` on launch.
This is the POLICY for Data's D3 tier maintenance (``tier_ingest``, #1241): throttle it
to at most once per interval, ISOLATE it (a failure is logged but never propagates, so
live collection is never disrupted), and — since **#1466** — **fill before compacting**.

**#1466, named so it is not re-broken:** the hook originally called only ``compact``,
which rebuilds *existing* partitions. On a store nobody had ingested there were no
partitions, so it was a permanent no-op and every tier reader saw an empty store on live
data. The fill path (``ingest_once``) was never wired to the launcher. The tick now
ingests then compacts.

Consumes ``tier_store._TIER_ROOT`` (the ratified layout) and ``tier_ingest`` — never a
second copy. ``tier_ingest`` is lazy so DuckDB stays off the dashboard startup path.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# _TIER_ROOT is the ratified store layout (single source); consume it, don't copy it.
from tier_store import _TIER_ROOT  # noqa: E402

_MARKER = ".last-compact"  # under the gitignored tier root; regenerable like the store


def _read_marker(marker: Path) -> datetime | None:
    try:
        return datetime.fromisoformat(marker.read_text().strip())
    except (OSError, ValueError):
        return None


def _source_files(logs_dir: Path) -> list[str]:
    return sorted(str(p) for pat in ("*.csv", "*.csv.gz") for p in logs_dir.glob(pat))


def _store_is_empty(root: Path) -> bool:
    """No parquet anywhere under the tier root — the dark-store condition (#1466)."""
    return not any(root.glob("date=*/device=*/*.parquet"))


def maybe_ingest_and_compact(
    logs_dir: str | Path | None = None,
    root: Path | None = None,
    now: datetime | None = None,
    min_interval_s: int = 3600,
    log=print,
    _ingest=None,
    _compact=None,
) -> dict:
    """Fill the tier from source, then compact — throttled, idempotent, error-isolated.

    **#1466 — the bug this fixes.** The launcher only ever called ``compact``, which
    iterates *existing* ``append-*.parquet`` files and rebuilds them. On a store that
    was never ingested there are no appends, so compaction is a permanent no-op and the
    store stays **empty forever** — every tier reader (multiplant/segment/predict, and
    therefore /trial) then sees zero rows and reports "no readings" over live data. The
    fill path, ``tier_ingest.ingest_once``, was never wired to the launcher at all; the
    store only existed on the machine where a developer ran ingest by hand.

    So the tick now **ingests first** (``ingest_once`` is store-watermarked: on an
    empty store it backfills the whole corpus, afterwards it appends only unseen rows —
    cheap), then compacts closed days. Both are idempotent, safe on every launch.

    **An empty store bypasses the throttle.** The hourly throttle must never be the
    reason a dark store stays dark — if there is no parquet at all we always try to fill
    it, even within the interval. ``ingest`` / ``compact`` are injectable for tests."""
    root = Path(root) if root else _TIER_ROOT
    now = now or datetime.now(timezone.utc)
    marker = root / _MARKER
    empty = _store_is_empty(root)

    last = _read_marker(marker)
    if not empty and last is not None and (now - last).total_seconds() < min_interval_s:
        return {"ran": False, "reason": "throttled"}

    try:
        if _ingest is None or _compact is None:
            import tier_ingest  # lazy: keeps DuckDB off the dashboard startup path

            _ingest = _ingest or tier_ingest.ingest_once
            _compact = _compact or tier_ingest.compact
        logs = Path(logs_dir) if logs_dir else _HERE.parents[1] / "logs"
        files = _source_files(logs)
        ingested = _ingest(files, root, log=log)
        appended = ingested.get("appended_rows", 0) if isinstance(ingested, dict) else 0
        if empty and appended:
            # AC3: a dark store filling is LOUD — the #1428 constitution. Silence here
            # is exactly how #1435 hid ("no readings" over a store nobody had filled).
            log(
                f"tier store was EMPTY — backfilled {appended} rows from "
                f"{len(files)} source segment(s). Tier readers are lit."
            )
        stats = _compact(files, root, log=log)
        root.mkdir(parents=True, exist_ok=True)
        marker.write_text(now.isoformat())
        done = stats.get("compacted", []) if isinstance(stats, dict) else []
        if done:
            log(f"tier hook: compacted {len(done)} partition(s)")
        return {"ran": True, "appended_rows": appended, "empty_before": empty, **stats}
    except Exception as exc:  # never disrupt live collection
        log(f"tier hook: skipped (collection unaffected): {exc}")
        return {"ran": False, "reason": "error"}


# #1466: the old name, kept so nothing that imports it breaks mid-release. It now
# ingests-then-compacts — a compaction-only tick was the bug. Prefer the honest name.
maybe_compact = maybe_ingest_and_compact
