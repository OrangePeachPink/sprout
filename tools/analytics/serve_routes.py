#!/usr/bin/env python3
"""#1452 — the extracted serve.py route table (ADR-0038 layer 0, a leaf).

The declarative routing map for the dashboard HTTP server: every GET and POST path,
its match kind, and the STABLE id ``serve.py`` dispatches on. Pulling it out of the
1500-line ``do_GET``/``do_POST`` if/elif (the #1336 rung) makes the route census one
auditable list, and gives the S4 certification a single before/after surface — you read
the routes here, not by tracing two long methods.

**This module owns WHICH route a path is; ``serve.py`` owns what each route DOES.** The
handler bodies stay in ``serve.py`` — deeply coupled to the request handler and its
module globals (controllers, renderers, the parse cache) — so moving them here would
drag the whole server with them. What moves is the *table*: the patterns, the kinds, and
the order.

Pure string matching: no I/O, no import of ours at all — a layer-0 LEAF (Trellis-
ratified on #1452: §2 forbids sideways within layer 4 and ``serve`` imports this table,
so it cannot sit at 4; ``serve (4) → serve_routes (0)`` is the legal downward edge).
**Order is significant and preserved exactly** —
``match`` returns the FIRST matching spec's id, so a specific prefix must precede its
catch-all (``/lab/study/`` before ``/lab/``) and a ``…/notes`` spec must precede
the generic ``/lab/`` it would otherwise be swallowed by. The ids are the contract
``serve.py`` switches on; ``census`` is the enumeration the route-drift test pins.
"""

from __future__ import annotations

from dataclasses import dataclass

# Match kinds. EXACT: the path is one of a fixed set. PREFIX: the path startswith the
# key. NOTES: startswith the key AND endswith "/notes" (the Lab notes sub-route, which
# must out-rank the generic detail prefix it shares a stem with).
EXACT = "exact"
PREFIX = "prefix"
NOTES = "notes"


@dataclass(frozen=True)
class Route:
    """One route spec. ``key`` holds the exact paths (EXACT) or the single prefix
    (PREFIX / NOTES). ``rid`` is the stable dispatch id — the string ``serve.py``
    matches on, decoupled from URL so a path can change without touching two files."""

    method: str  # "GET" | "POST"
    kind: str  # EXACT | PREFIX | NOTES
    key: tuple[str, ...]
    rid: str

    def matches(self, path: str) -> bool:
        if self.kind == EXACT:
            return path in self.key
        if self.kind == PREFIX:
            return path.startswith(self.key[0])
        if self.kind == NOTES:
            return path.startswith(self.key[0]) and path.endswith("/notes")
        return False


# The GET table, in exact source order. Every id is unique within the method.
GET_ROUTES: tuple[Route, ...] = (
    Route("GET", EXACT, ("/", "/index.html"), "home"),
    Route("GET", EXACT, ("/trial/data.json",), "trial_data"),
    Route("GET", EXACT, ("/trial",), "trial"),
    Route("GET", EXACT, ("/classic",), "classic"),
    Route("GET", EXACT, ("/data.json",), "data_json"),
    Route("GET", EXACT, ("/capture/status",), "capture_status"),
    Route("GET", EXACT, ("/monitor/status",), "monitor_status"),
    Route("GET", EXACT, ("/fleet/status",), "fleet_status"),
    Route("GET", EXACT, ("/collection/status",), "collection_status"),
    Route("GET", EXACT, ("/location/status",), "location_status"),
    Route("GET", EXACT, ("/registry",), "registry"),
    Route("GET", EXACT, ("/watering/precision",), "watering_precision"),
    Route("GET", EXACT, ("/sensor/health",), "sensor_health"),
    Route("GET", EXACT, ("/cards.json",), "cards_json"),
    Route("GET", PREFIX, ("/photo/",), "photo"),
    Route("GET", EXACT, ("/serial/owner",), "serial_owner"),
    Route("GET", PREFIX, ("/docs/",), "docs"),
    Route("GET", EXACT, ("/lab",), "lab"),
    Route("GET", EXACT, ("/lab/experiments.json",), "lab_experiments"),
    Route("GET", EXACT, ("/lab/drafts",), "lab_drafts"),
    Route("GET", PREFIX, ("/lab/draft/",), "lab_draft"),
    Route("GET", EXACT, ("/lab/studies",), "lab_studies"),
    Route("GET", PREFIX, ("/lab/study/",), "lab_study"),
    Route("GET", NOTES, ("/lab/",), "lab_notes"),
    Route("GET", PREFIX, ("/lab/bench/",), "lab_bench"),
    Route("GET", PREFIX, ("/lab/",), "lab_detail"),
)

# The POST (control-plane) table, in exact source order. The two compound `/notes`
# specs are order-critical: bench-notes must precede the generic notes, which would
# otherwise mis-read "bench/<id>".
POST_ROUTES: tuple[Route, ...] = (
    Route("POST", EXACT, ("/capture/start",), "capture_start"),
    Route("POST", EXACT, ("/capture/stop",), "capture_stop"),
    Route("POST", EXACT, ("/monitor/start",), "monitor_start"),
    Route("POST", EXACT, ("/monitor/stop",), "monitor_stop"),
    Route("POST", EXACT, ("/fleet/start",), "fleet_start"),
    Route("POST", EXACT, ("/fleet/stop",), "fleet_stop"),
    Route("POST", EXACT, ("/collection/start",), "collection_start"),
    Route("POST", EXACT, ("/collection/stop",), "collection_stop"),
    Route("POST", EXACT, ("/location",), "location"),
    Route("POST", EXACT, ("/watering/log",), "watering_log"),
    Route("POST", EXACT, ("/watering/verdict",), "watering_verdict"),
    Route("POST", PREFIX, ("/photo/",), "photo"),
    Route("POST", EXACT, ("/registry/apply",), "registry_apply"),
    Route("POST", EXACT, ("/serial/owner/clear",), "serial_owner_clear"),
    Route("POST", PREFIX, ("/lab/study/",), "lab_study"),
    Route("POST", NOTES, ("/lab/bench/",), "lab_bench_notes"),
    Route("POST", NOTES, ("/lab/",), "lab_notes"),
    Route("POST", EXACT, ("/quit",), "quit"),
)

_TABLES = {"GET": GET_ROUTES, "POST": POST_ROUTES}


def match(method: str, path: str) -> str | None:
    """The id of the first route whose spec matches ``path`` for ``method``, or None
    (the caller's 404). First-match-wins, exactly as the if/elif fell through — so the
    table order IS the routing precedence."""
    for route in _TABLES.get(method, ()):
        if route.matches(path):
            return route.rid
    return None


def census(method: str | None = None) -> tuple[Route, ...]:
    """The route enumeration for the before/after certification and the drift test.
    ``method`` None returns GET then POST; a method returns just that table."""
    if method is None:
        return (*GET_ROUTES, *POST_ROUTES)
    return _TABLES.get(method, ())
