#!/usr/bin/env python3
"""#1456 - a session of repeated renders does not degrade.

The reported signature (#1429): after a wide query, subsequent small queries ran ~3.5x
slower until restart - "one 30d click degrades the app." Design was explicit that this
was "a signature, not a diagnosis" and asked for RSS-per-request to tell "the data got
bigger" from "the process is leaking".

**What the controlled measurement actually shows.** Twenty consecutive 14d renders over
a fixed synthetic corpus are *flat* (drift ~0.9x) and RSS is stable - the parse cache
holds one bounded working set and does not grow per render. The 3.5x could not be
reproduced in isolation; it lived in the live request path over the real ~715k corpus,
and its trigger (the wide build's allocation churn) was cut ~49% by the #1457 dedup.

So this suite pins the property that *is* true and would catch a real leak if one were
introduced: **RSS does not climb, and render time does not drift, across a session of
fixed-window renders.** The RSS check is the deterministic leak detector (a retained
per-render payload would show as a monotonic climb); the timing check carries a generous
tolerance because wall-clock is noisy, but a 3.5x regression is far outside it.
"""

from __future__ import annotations

import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

try:
    import psutil as _psutil
except Exception:
    _psutil = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card_context import build_context
from dashboard import filter_since
from device_registry import Device, Registry
from parse_cache import ParseCache

T0 = datetime(2026, 5, 1, tzinfo=timezone.utc)
_HDR = (
    "# schema_version=4  fw=0.8.0  git=t  device_id=dev  session_id=s1\n"
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,sensor_id,"
    "raw_value,quality_flag,payload\n"
)


def _corpus(tmp: Path, days: int = 20, per_day: int = 720) -> list[str]:
    """Daily CSV segments (immutable, cache-once) so a 14d render is a real subset."""
    files = []
    for day in range(days):
        p = tmp / f"plants_2026-05-{day + 1:02d}.csv"
        rows = []
        for i in range(per_day):
            ts = (T0 + timedelta(days=day, seconds=120 * i)).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )
            rows.append(
                f"plants.soil,{ts}Z,x,s1,dev,s1,{1500 + i % 400},OK,level=drying"
            )
        p.write_text(_HDR + "\n".join(rows) + "\n", encoding="utf-8")
        files.append(str(p))
    return files


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="dev",
                board="esp32-classic",
                label="A",
                channels={"s1": {"plant_id": "p01", "plant_name": "Corn"}},
            )
        ]
    )


def _render(cache: ParseCache, files: list[str], days: int) -> None:
    data = filter_since(cache.load(files), days * 24)
    build_context(data, registry=_reg(), now=T0 + timedelta(days=20))


def test_the_parse_cache_working_set_does_not_grow_per_render(tmp_path: Path) -> None:
    """The deterministic leak detector: the cache holds one bounded corpus; a session of
    renders must not grow its footprint. A per-render retention (the leak shape) would
    show as `readings` climbing across the loop."""
    files = _corpus(tmp_path)
    cache = ParseCache()
    _render(cache, files, 14)
    baseline = cache.stats()["readings"]
    for _ in range(30):
        _render(cache, files, 14)
    assert cache.stats()["readings"] == baseline, (
        "the parse-cache working set grew across a fixed-window session - a leak"
    )


@pytest.mark.skipif(_psutil is None, reason="psutil not available")
def test_rss_does_not_climb_across_a_session(tmp_path: Path) -> None:
    """RSS after 40 fixed-window renders is within a small band of RSS after warmup - a
    retained-per-render leak would push it monotonically up. Generous band (Python
    arenas don't return promptly); a real leak is far larger than this."""
    files = _corpus(tmp_path)
    cache = ParseCache()
    proc = _psutil.Process()
    _render(cache, files, 14)  # warm the cache
    for _ in range(3):
        _render(cache, files, 14)
    warm = proc.memory_info().rss
    for _ in range(40):
        _render(cache, files, 14)
    grew_mb = (proc.memory_info().rss - warm) / (1024 * 1024)
    assert grew_mb < 40, f"RSS climbed {grew_mb:.0f} MB across a fixed session - a leak"


def test_render_time_is_flat_across_a_session(tmp_path: Path) -> None:
    """The AC, with a generous tolerance for wall-clock noise. The last-5 mean must not
    be materially slower than the first-5 - a 3.5x degradation is nowhere near 2x."""
    files = _corpus(tmp_path)
    cache = ParseCache()
    _render(cache, files, 14)  # warmup (cold parse) excluded from the samples
    ts = []
    for _ in range(20):
        t = time.perf_counter()
        _render(cache, files, 14)
        ts.append(time.perf_counter() - t)
    early, late = statistics.mean(ts[:5]), statistics.mean(ts[-5:])
    assert late < early * 2.0, (
        f"render time drifted {late / early:.1f}x across the session "
        f"(early {early * 1000:.0f}ms -> late {late * 1000:.0f}ms) - degradation"
    )
