#!/usr/bin/env python3
"""#827: parse once, serve from memory.

``serve.py`` re-parsed the **entire** log corpus on every ``/data.json`` request -
~20 s at ~230k readings, growing ~23k rows/day, and range filtering happened *after*
the full parse (so a 3 h view cost the same as ``all``). This module holds the parsed
corpus in memory and re-touches only what actually changed on disk.

The mechanism is deliberately simple so it can never serve a stale snapshot as live:

* **Per-file cache keyed on ``(size, mtime_ns)``.** Each file is parsed by the real
  :func:`parse_v1.parse_file` (no duplicated parsing logic -> no drift), and the
  resulting readings/segments are cached under the file's size+mtime signature.
* **Unchanged file -> reuse.** The immutable historical corpus (rotated
  ``*.csv`` / ``*.csv.gz`` segments) is parsed **once per server start**.
* **Changed file -> re-parse just that file.** The active log grows every poll, so its
  signature changes and it alone is re-read - a small tail relative to the corpus, so
  new rows are picked up cheaply and freshness is bounded by the request cadence
  (never a frozen snapshot: every request re-``stat``s the files).
* **Rotation / new session -> parsed once** (a new path is a cache miss); a
  **truncated / shrunk** file is a signature change -> re-parsed, never silently
  half-read; a **vanished** file is evicted so memory tracks the live file set.

Memory: the cache holds every ``Reading`` once (~230k objects today, a few tens of MB;
fine on the NUC). It scales with the on-disk corpus, so the ceiling assumption is
"the logs fit in RAM" - true by a wide margin for a single-home appliance.

The cache is instance-based (``serve.py`` holds one module-global); tests get a fresh
instance with no cross-test leakage.
"""

from __future__ import annotations

import os
from pathlib import Path

from parse_v1 import LogData, parse_file
from parse_v1 import _resolve as _resolve_inputs


def _file_sig(path: Path) -> tuple[int, int] | None:
    """``(size, mtime_ns)`` - the cheap change signal. ``None`` if the file vanished
    between discovery and stat (a rotation race); the caller skips it."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


class _Entry:
    __slots__ = ("readings", "segments", "sig")

    def __init__(self, sig: tuple[int, int], readings: list, segments: list) -> None:
        self.sig = sig
        self.readings = readings
        self.segments = segments


class ParseCache:
    """Parse-once, mtime-aware corpus cache (#827). ``load`` is a drop-in for
    ``parse_files`` (same inputs, same merged :class:`LogData`), but reuses unchanged
    files from memory instead of re-reading them."""

    def __init__(self, parse_one=parse_file, resolve=_resolve_inputs) -> None:
        # injectable for tests (stub the parser to count real reads; stub resolve to
        # avoid touching the filesystem).
        self._parse_one = parse_one
        self._resolve = resolve
        self._entries: dict[Path, _Entry] = {}

    def load(self, inputs: list | None = None) -> LogData:
        resolved = self._resolve(inputs or [])
        out = LogData()
        seen: set[Path] = set()
        for path in resolved:
            sig = _file_sig(path)
            if sig is None:
                continue  # vanished mid-request (rotation race) - skip, never guess
            seen.add(path)
            ent = self._entries.get(path)
            if ent is None or ent.sig != sig:
                # miss, growth, rotation, or truncation -> re-parse just this file.
                frag = self._parse_one(path)
                ent = _Entry(sig, frag.readings, frag.segments)
                self._entries[path] = ent
            out.readings.extend(ent.readings)
            out.segments.extend(ent.segments)
            out.sources.append(str(path))
        # evict files that are no longer in the resolved set (archived / deleted) so
        # the cache footprint tracks the live corpus, not every file ever seen.
        for gone in [p for p in self._entries if p not in seen]:
            del self._entries[gone]
        return out

    def stats(self) -> dict:
        """Introspection for the warmup log / tests: how much is held in memory."""
        return {
            "files": len(self._entries),
            "readings": sum(len(e.readings) for e in self._entries.values()),
        }
