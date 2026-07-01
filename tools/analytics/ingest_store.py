#!/usr/bin/env python3
"""The store-and-forward ingest boundary (#521, ADR-0018 decision #2).

Store-and-forward means the same physical reading can arrive twice: a device
buffers locally, then forwards, then a reconnect races the original send and
replays it. `parse_v1.dedupe_key()` (schema v2 §11.2, #300/#520) is the
5-tuple that identifies *this exact reading* independent of how many times its
bytes crossed the wire - but nothing consumed it at an ingest boundary until
now. `Store.ingest()` is that boundary: an exact replay (identical dedupe key)
is dropped; anything else is appended.

Honest degrade (#521's explicit AC): a v1-only row has no `device_seq`, so it
carries no dedupe signal at all. Treating it as a potential duplicate would be
a false positive that silently drops legitimate data - so a row with no
`device_seq` is *always* appended, never deduplicated.

Preserves ADR-0006 raw-is-truth (ADR-0018 decision #6): this is an
append/drop-only boundary. It never rewrites or merges a row - a dropped
replay is simply never appended in the first place, and everything appended
stays exactly as received."""

from __future__ import annotations

from parse_v1 import Reading, dedupe_key


class Store:
    """An append-only ingest boundary with store-and-forward row idempotency.

    Not a persistence layer - just the dedupe decision. Pair with whatever
    actually writes rows (a file, a future real store) by calling
    ``ingest()`` first and only appending when it returns True."""

    def __init__(self) -> None:
        self._seen: set[tuple] = set()

    def ingest(self, reading: Reading) -> bool:
        """True if this reading should be appended, False if it's an exact
        replay already ingested. A row with no ``device_seq`` (no dedupe
        signal) always returns True - it can never be identified as a
        duplicate, so it is never treated as one."""
        key = dedupe_key(reading)
        if key[2] is None:  # no device_seq -> no dedupe signal, honest append
            return True
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def __len__(self) -> int:
        """Count of distinct dedupe-keyed rows ingested so far (v2 rows only -
        v1-only rows are never tracked, since they're never deduplicated)."""
        return len(self._seen)
