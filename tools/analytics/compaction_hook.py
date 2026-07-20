"""#1292 (DX / operator) — the launcher-managed daily-compaction hook.

The one-click doctrine: the operator never runs a compaction command or sets up a
Windows scheduled task (a second surface). Instead the launcher — the running Sprout
server that already owns the collector lifecycle — calls ``maybe_compact()`` on its
cadence. This is the POLICY for Data's D3 compaction (``tier_ingest.compact``, #1241):
throttle it to at most once per interval, and ISOLATE it — a failure is logged but never
propagates, so live collection is never disrupted.

Consumes ``tier_store._TIER_ROOT`` (the ratified layout) and ``tier_ingest.compact`` —
never a second copy. ``tier_ingest`` is lazy so this hook lands ahead of / alongside D3;
the launcher call-site (a one-liner in the server loop) activates it once D3 is on main.
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


def maybe_compact(
    logs_dir: str | Path | None = None,
    root: Path | None = None,
    now: datetime | None = None,
    min_interval_s: int = 3600,
    log=print,
    _compact=None,
) -> dict:
    """Run the tier compaction if it's due — throttled, idempotent, error-isolated.

    Safe on every launcher tick: no-ops within ``min_interval_s`` of the last run, and
    D3's ``compact`` is closed-days-only + idempotent (a no-op when no appends await). A
    failure returns ``{"ran": False, "reason": "error"}`` and is logged — never raises
    into the caller. ``_compact`` is injectable for tests."""
    root = Path(root) if root else _TIER_ROOT
    now = now or datetime.now(timezone.utc)
    marker = root / _MARKER

    last = _read_marker(marker)
    if last is not None and (now - last).total_seconds() < min_interval_s:
        return {"ran": False, "reason": "throttled"}

    try:
        if _compact is None:
            import tier_ingest  # lazy: present once D3 (#1241) lands on main

            _compact = tier_ingest.compact
        logs = Path(logs_dir) if logs_dir else _HERE.parents[1] / "logs"
        stats = _compact(_source_files(logs), root, log=log)
        root.mkdir(parents=True, exist_ok=True)
        marker.write_text(now.isoformat())
        done = stats.get("compacted", []) if isinstance(stats, dict) else []
        if done:
            log(f"compaction hook: compacted {len(done)} partition(s)")
        return {"ran": True, **(stats if isinstance(stats, dict) else {})}
    except Exception as exc:  # never disrupt live collection
        log(f"compaction hook: skipped (collection unaffected): {exc}")
        return {"ran": False, "reason": "error"}
