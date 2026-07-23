#!/usr/bin/env python3
"""#1468 AC1 — ``ParseCache.load()`` is concurrency-safe under ``ThreadingHTTPServer``.

serve.py holds ONE module-global cache and ``ThreadingHTTPServer`` dispatches every
request on its own thread, so two overlapping ``/data.json`` requests race ``load()``.
The mutate-in-place hazard: both threads pass the ``sig[0] > ent.offset`` growth check
before either advances it, both ``_tail`` the SAME entry from the SAME offset, and the
corpus silently gains every appended row twice — plus a double ``offset +=`` that then
points past real bytes. A reader can also observe a half-extended entry mid-``extend``.

The fixture is barrier-driven: a warm cache, a grown active file, and N threads released
through one ``threading.Barrier`` so they hit the growth check together. Against the
unlocked cache this FAILS (duplicated tail rows); with the #1468 lock it passes. The
assertion is on BOTH surfaces — what each request returned, and what the cache now
holds — because either kind of corruption poisons every later request, not just the
racing ones.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_cache import ParseCache

_HDR = (
    "# schema_version=4  fw=0.8.0  git=t  device_id=dev  session_id=s1\n"
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,sensor_id,"
    "raw_value,quality_flag,payload\n"
)


def _row(i: int) -> str:
    ts = f"2026-07-01T00:{i // 60 % 60:02d}:{i % 60:02d}.000000Z"
    return f"plants.soil,{ts},x,s1,dev,s1,{1500 + i % 300},OK,level=drying"


def _write_rows(path: Path, lo: int, hi: int, *, append: bool = False) -> None:
    body = "\n".join(_row(i) for i in range(lo, hi)) + "\n"
    if append:
        with open(path, "a", encoding="utf-8", newline="") as fh:
            fh.write(body)
    else:
        path.write_text(_HDR + body, encoding="utf-8", newline="")


BASE = 400  # rows parsed at warm time
TAIL = 4000  # rows appended before the race — a wide-enough tail window to collide in
THREADS = 8
ROUNDS = 3  # a racy bug that survives one round rarely survives three


def _race(cache: ParseCache) -> tuple[list, list]:
    """Release THREADS loads through one barrier; return (per-thread reading counts,
    raised exceptions). The barrier makes the growth-check collision reliable."""
    barrier = threading.Barrier(THREADS)
    results: list = [None] * THREADS
    errors: list = []

    def hit(slot: int) -> None:
        try:
            barrier.wait()  # released together -> all see the grown sig at once
            results[slot] = len(cache.load().readings)
        except Exception as exc:  # surfaced by the caller, never swallowed
            errors.append(exc)

    threads = [
        threading.Thread(target=hit, args=(k,), daemon=True) for k in range(THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results, errors


def test_concurrent_loads_of_a_grown_file_never_duplicate_the_tail(
    tmp_path: Path,
) -> None:
    """AC1: N threads through a barrier hit the growth check together. Every request
    must see exactly the corpus, and the cache must hold each appended row ONCE."""
    active = tmp_path / "plants_active.csv"
    _write_rows(active, 0, BASE)
    cache = ParseCache(resolve=lambda _inputs: [active])
    assert len(cache.load().readings) == BASE  # warm: the pre-growth corpus

    total = BASE
    for _ in range(ROUNDS):
        _write_rows(active, total, total + TAIL, append=True)
        total += TAIL

        results, errors = _race(cache)
        assert not errors, f"a concurrent load raised: {errors[:1]!r}"

        # Every racing request returned the exact corpus - no duplicated tail, no
        # half-extended entry observed mid-append.
        assert results == [total] * THREADS, (
            f"concurrent loads disagree with the corpus of {total}: "
            f"{sorted(set(results))}"
        )
        # And the cache itself holds each row once - corruption here would poison
        # every LATER request too, which is the truly nasty version of the bug.
        assert cache.stats()["readings"] == total, (
            f"cache holds {cache.stats()['readings']} readings for a {total}-row file "
            "- the tail was appended more than once"
        )

    # sanity: a quiet follow-up load (no growth) still serves the exact corpus
    assert len(cache.load().readings) == total


def test_concurrent_loads_of_an_unchanged_corpus_are_stable(tmp_path: Path) -> None:
    """The cheap steady-state: no growth between requests — pure cache hits must be
    identical from every thread (guards the entries-dict handling, not just _tail)."""
    active = tmp_path / "plants_active.csv"
    _write_rows(active, 0, BASE)
    cache = ParseCache(resolve=lambda _inputs: [active])
    cache.load()

    results, errors = _race(cache)
    assert not errors, f"a concurrent load raised: {errors[:1]!r}"
    assert results == [BASE] * THREADS
