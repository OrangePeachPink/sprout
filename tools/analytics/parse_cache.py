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
* **Grown active file -> byte-offset tail-append (#859).** The active log grows every
  poll; instead of re-parsing the whole file, the cache remembers the byte offset it
  parsed to and folds in **only the appended bytes** through the same per-line rule the
  full parser uses (``parse_v1._consume_line`` -> no drift). So a request landing right
  after a poll re-reads a handful of new rows, not the whole active file — sub-1s even
  then. Freshness stays bounded by the request cadence (every request re-``stat``s).
* **Correctness fence.** A tail resumes only from a clean newline boundary; a
  **truncated / shrunk** file, an **mtime that went backward** (a same-name rewrite), a
  **corrupt/undecodable** tail, or a ``.gz`` archive all fall back to a full re-parse —
  never a silently half-read or stale result. A new session path is a cache miss
  (parsed once); a **vanished** file is evicted so memory tracks the live file set.

Memory: the cache holds every ``Reading`` once (~230k objects today, a few tens of MB;
fine on the NUC). It scales with the on-disk corpus, so the ceiling assumption is
"the logs fit in RAM" - true by a wide margin for a single-home appliance.

The cache is instance-based (``serve.py`` holds one module-global); tests get a fresh
instance with no cross-test leakage.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from tools.analytics.parse_v1 import LogData, _consume_line, _ParseState, parse_file
from tools.analytics.parse_v1 import _resolve as _resolve_inputs


def _file_sig(path: Path) -> tuple[int, int] | None:
    """``(size, mtime_ns)`` - the cheap change signal. ``None`` if the file vanished
    between discovery and stat (a rotation race); the caller skips it."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_size, st.st_mtime_ns)


def _tail_anchor(path: Path, frag: LogData) -> tuple[int | None, _ParseState | None]:
    """The (byte offset, resume state) a later tail-append starts from (#859), or
    ``(None, None)`` when the file can't be safely tailed: a ``.gz`` archive (immutable,
    never grows), a file with no segment yet, or one whose last byte isn't a newline (a
    partial trailing line — defer it, never resume mid-row). The resume state carries
    the last segment's columns + the segment itself, so appended rows attach exactly as
    a full parse would; a header appended later is handled by ``_consume_line``."""
    if path.suffix == ".gz" or not frag.segments:
        return None, None
    try:
        size = path.stat().st_size
        if size == 0:
            return None, None
        with open(path, "rb") as fh:
            fh.seek(size - 1)
            last = fh.read(1)
    except OSError:
        return None, None
    if last != b"\n":
        return None, None  # a partial trailing line — resume only from a clean boundary
    st = _ParseState()
    st.cols = list(frag.segments[-1].columns)
    st.current = frag.segments[-1]
    st.header_buf = []
    return size, st


class _Entry:
    __slots__ = ("offset", "readings", "segments", "sig", "state")

    def __init__(
        self,
        sig: tuple[int, int],
        readings: list,
        segments: list,
        *,
        offset: int | None = None,
        state: _ParseState | None = None,
    ) -> None:
        self.sig = sig
        self.readings = readings
        self.segments = segments
        # #859: byte offset parsed to + the resume state, for a tail-append on growth.
        # None => not tailable (gz / partial line); such a file full-reparses on change.
        self.offset = offset
        self.state = state


class ParseCache:
    """Parse-once, mtime-aware corpus cache (#827). ``load`` is a drop-in for
    ``parse_files`` (same inputs, same merged :class:`LogData`), but reuses unchanged
    files from memory instead of re-reading them. On a grown active file it
    **tail-appends** only the new bytes (#859) instead of re-parsing the whole file."""

    def __init__(self, parse_one=parse_file, resolve=_resolve_inputs) -> None:
        # injectable for tests (stub the parser to count real reads; stub resolve to
        # avoid touching the filesystem).
        self._parse_one = parse_one
        self._resolve = resolve
        self._entries: dict[Path, _Entry] = {}
        # #1468 AC1: serve.py holds ONE cache and ThreadingHTTPServer runs every
        # request on its own thread. The mutate-in-place paths (_tail's extend +
        # offset advance, the entries dict, eviction) race without exclusion: two
        # requests that both see a grown file both tail the SAME bytes and the corpus
        # silently doubles its tail — poisoning every later request, not just the
        # racing ones. One coarse lock over load() is the boring, provable fix: loads
        # are cache-hits in the steady state (cheap), and serializing a cold parse is
        # strictly better than two threads doing the same 20 s parse concurrently.
        self._lock = threading.Lock()

    def _full(self, path: Path, sig: tuple[int, int]) -> _Entry:
        """Full (re)parse via the canonical parser, plus the tail anchor for later."""
        frag = self._parse_one(path)
        offset, state = _tail_anchor(path, frag)
        return _Entry(sig, frag.readings, frag.segments, offset=offset, state=state)

    def _tail(self, path: Path, ent: _Entry, sig: tuple[int, int]) -> _Entry | None:
        """Append only the bytes past ``ent.offset`` (#859), sharing the exact per-line
        rule with the full parser via ``_consume_line``. Returns ``None`` (=> full
        reparse) if the new tail can't be decoded — the 'never serve stale' fence."""
        try:
            with open(path, "rb") as fh:
                fh.seek(ent.offset)
                chunk = fh.read()
        except OSError:
            return None
        nl = chunk.rfind(b"\n")
        if nl == -1:
            ent.sig = sig  # grew, but no complete new line yet — nothing to add
            return ent
        complete = chunk[: nl + 1]
        try:
            text = complete.decode("utf-8")
        except UnicodeDecodeError:
            return None  # a corrupt tail — fall back to a full, honest re-parse
        src = str(path)
        tail = LogData()
        for raw in text.split("\n"):
            _consume_line(raw.rstrip("\r"), tail, src, ent.state)
        ent.readings.extend(tail.readings)
        ent.segments.extend(tail.segments)
        ent.offset += len(complete)
        ent.sig = sig
        return ent

    def load(self, inputs: list | None = None) -> LogData:
        with self._lock:  # #1468 AC1 — one loader mutates at a time, see __init__
            return self._load_locked(inputs)

    def _load_locked(self, inputs: list | None) -> LogData:
        resolved = self._resolve(inputs or [])
        out = LogData()
        seen: set[Path] = set()
        for path in resolved:
            sig = _file_sig(path)
            if sig is None:
                continue  # vanished mid-request (rotation race) - skip, never guess
            seen.add(path)
            ent = self._entries.get(path)
            if ent is not None and ent.sig == sig:
                pass  # unchanged -> reuse from memory
            elif (
                ent is not None
                and ent.offset is not None
                and sig[0] > ent.offset  # genuinely grew past what we parsed
                and sig[1] >= ent.sig[1]  # mtime didn't go backward (rewrite guard)
            ):
                tailed = self._tail(path, ent, sig)
                ent = tailed if tailed is not None else self._full(path, sig)
                self._entries[path] = ent
            else:
                # miss, truncation/shrink, mtime anomaly, or non-tailable -> full parse
                ent = self._full(path, sig)
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
        """Introspection for the warmup log / tests: how much is held in memory.
        Locked so a stat never reads a half-extended entry mid-append (#1468)."""
        with self._lock:
            return {
                "files": len(self._entries),
                "readings": sum(len(e.readings) for e in self._entries.values()),
            }
