#!/usr/bin/env python3
"""#1452 — the extracted route table pins the route census and stays in lock-step with
serve.py's dispatch.

The extraction's contract is *zero behavior change*: the set of routes, their match
kinds, and their precedence must be identical before and after. Two guards enforce that
here so a future edit can't silently drift them apart:

1. the census is pinned to an exact ordered table (a reorder or dropped/added route is
   a visible diff), and
2. every id in the table has exactly one dispatch arm in serve.py, and vice-versa — so a
   route can never be declared-but-unserved or served-but-undeclared. That check is
   the "route census identical before/after" AC made real: the table IS the census,
   and serve.py is proven to honor exactly it.

Plus the order-sensitive matches (the whole reason order is preserved) are asserted
directly, because a prefix that out-ran its specific sibling would be a regression a
census count alone would miss.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import serve_routes
from serve_routes import EXACT, NOTES, PREFIX, census, match

_SERVE = (Path(__file__).resolve().parent / "serve.py").read_text(encoding="utf-8")


# The pinned census: (method, kind, key, id) in exact source order. This is the
# authoritative route table — a diff here is a deliberate route change, reviewed as one.
_EXPECTED_GET = [
    ("GET", EXACT, ("/", "/index.html"), "home"),
    ("GET", EXACT, ("/trial/data.json",), "trial_data"),
    ("GET", EXACT, ("/trial",), "trial"),
    ("GET", EXACT, ("/classic",), "classic"),
    ("GET", EXACT, ("/data.json",), "data_json"),
    ("GET", EXACT, ("/capture/status",), "capture_status"),
    ("GET", EXACT, ("/monitor/status",), "monitor_status"),
    ("GET", EXACT, ("/fleet/status",), "fleet_status"),
    ("GET", EXACT, ("/collection/status",), "collection_status"),
    ("GET", EXACT, ("/location/status",), "location_status"),
    ("GET", EXACT, ("/registry",), "registry"),
    ("GET", EXACT, ("/watering/precision",), "watering_precision"),
    ("GET", EXACT, ("/sensor/health",), "sensor_health"),
    ("GET", EXACT, ("/cards.json",), "cards_json"),
    ("GET", PREFIX, ("/photo/",), "photo"),
    ("GET", EXACT, ("/serial/owner",), "serial_owner"),
    ("GET", PREFIX, ("/docs/",), "docs"),
    ("GET", EXACT, ("/lab",), "lab"),
    ("GET", EXACT, ("/lab/experiments.json",), "lab_experiments"),
    ("GET", EXACT, ("/lab/drafts",), "lab_drafts"),
    ("GET", PREFIX, ("/lab/draft/",), "lab_draft"),
    ("GET", EXACT, ("/lab/studies",), "lab_studies"),
    ("GET", PREFIX, ("/lab/study/",), "lab_study"),
    ("GET", NOTES, ("/lab/",), "lab_notes"),
    ("GET", PREFIX, ("/lab/bench/",), "lab_bench"),
    ("GET", PREFIX, ("/lab/",), "lab_detail"),
]
_EXPECTED_POST = [
    ("POST", EXACT, ("/capture/start",), "capture_start"),
    ("POST", EXACT, ("/capture/stop",), "capture_stop"),
    ("POST", EXACT, ("/monitor/start",), "monitor_start"),
    ("POST", EXACT, ("/monitor/stop",), "monitor_stop"),
    ("POST", EXACT, ("/fleet/start",), "fleet_start"),
    ("POST", EXACT, ("/fleet/stop",), "fleet_stop"),
    ("POST", EXACT, ("/collection/start",), "collection_start"),
    ("POST", EXACT, ("/collection/stop",), "collection_stop"),
    ("POST", EXACT, ("/location",), "location"),
    ("POST", EXACT, ("/watering/log",), "watering_log"),
    ("POST", EXACT, ("/watering/verdict",), "watering_verdict"),
    ("POST", PREFIX, ("/photo/",), "photo"),
    ("POST", EXACT, ("/registry/apply",), "registry_apply"),
    ("POST", EXACT, ("/serial/owner/clear",), "serial_owner_clear"),
    ("POST", PREFIX, ("/lab/study/",), "lab_study"),
    ("POST", NOTES, ("/lab/bench/",), "lab_bench_notes"),
    ("POST", NOTES, ("/lab/",), "lab_notes"),
    ("POST", EXACT, ("/quit",), "quit"),
]


def _as_tuple(route) -> tuple:
    return (route.method, route.kind, route.key, route.rid)


def test_get_census_is_the_pinned_ordered_table() -> None:
    assert [_as_tuple(r) for r in census("GET")] == _EXPECTED_GET


def test_post_census_is_the_pinned_ordered_table() -> None:
    assert [_as_tuple(r) for r in census("POST")] == _EXPECTED_POST


def test_full_census_is_get_then_post() -> None:
    assert [_as_tuple(r) for r in census()] == _EXPECTED_GET + _EXPECTED_POST


def _dispatch_ids(method: str) -> list[str]:
    """The route ids serve.py actually dispatches on for a method — read from the source
    between ``def do_GET`` / ``def do_POST`` (POST up to ``def _body``). This is
    the running server's real route set; the census must equal it exactly."""
    g = _SERVE.index("def do_GET")
    p = _SERVE.index("def do_POST")
    b = _SERVE.index("def _body")
    body = _SERVE[g:p] if method == "GET" else _SERVE[p:b]
    return re.findall(r'route == "([a-z_]+)"', body)


def test_every_get_route_is_dispatched_exactly_once() -> None:
    """The census-identical AC, mechanized: the ids serve.py switches on are exactly the
    census ids, in the same order, with no duplicate and no orphan."""
    assert _dispatch_ids("GET") == [rid for *_, rid in _EXPECTED_GET]


def test_every_post_route_is_dispatched_exactly_once() -> None:
    assert _dispatch_ids("POST") == [rid for *_, rid in _EXPECTED_POST]


def test_serve_imports_the_extracted_table() -> None:
    """The extraction is real: serve.py imports serve_routes and no longer carries the
    route strings in its dispatch conditions (only ``route == …`` arms remain)."""
    assert "import serve_routes" in _SERVE
    assert 'serve_routes.match("GET"' in _SERVE
    assert 'serve_routes.match("POST"' in _SERVE
    # the two legitimate parsed.path survivors: the /debug/slow test hook and the
    # NoDataYet /data.json branch. No dispatch elif should test parsed.path anymore.
    assert "elif parsed.path" not in _SERVE


def test_match_resolves_exact_prefix_and_compound() -> None:
    assert match("GET", "/") == "home"
    assert match("GET", "/index.html") == "home"
    assert match("GET", "/data.json") == "data_json"
    assert match("GET", "/photo/abc123") == "photo"  # prefix
    assert match("GET", "/docs/reference/x.md") == "docs"  # prefix
    assert match("POST", "/quit") == "quit"
    assert match("POST", "/registry/apply") == "registry_apply"


def test_order_sensitive_lab_paths_pick_the_specific_route() -> None:
    """The reason order is preserved: a specific prefix must out-rank the /lab/
    catch-all, and the compound /notes must out-rank the generic detail."""
    assert match("GET", "/lab/study/s1") == "lab_study"  # not lab_detail
    assert match("GET", "/lab/bench/pkg/notes") == "lab_notes"  # endswith wins (GET)
    assert match("GET", "/lab/exp42/notes") == "lab_notes"
    assert match("GET", "/lab/exp42") == "lab_detail"  # the catch-all, last
    # POST orders bench-notes BEFORE generic notes (it would else mis-read "bench/<id>")
    assert match("POST", "/lab/bench/pkg/notes") == "lab_bench_notes"
    assert match("POST", "/lab/exp42/notes") == "lab_notes"
    assert match("POST", "/lab/study/s1") == "lab_study"


def test_unknown_path_and_unknown_method_are_none() -> None:
    assert match("GET", "/nope") is None  # → the caller's 404
    assert match("POST", "/nope") is None
    assert match("GET", "/quit") is None  # a POST route is not a GET route
    assert match("DELETE", "/") is None  # unknown method, empty table


def test_route_ids_are_unique_within_each_method() -> None:
    for method in ("GET", "POST"):
        ids = [r.rid for r in census(method)]
        assert len(ids) == len(set(ids)), f"duplicate route id in {method}"


def test_module_is_a_pure_leaf_no_repo_imports() -> None:
    """serve_routes is layer 0 (a leaf): it must import nothing from this package, so
    serve (4) → serve_routes is a legal downward edge (ADR-0038 §2)."""
    src = (Path(serve_routes.__file__)).read_text(encoding="utf-8")
    # only stdlib: __future__ and dataclasses. No sibling-module import.
    assert "from dataclasses import" in src
    assert "import parse_v1" not in src and "import card_context" not in src
