#!/usr/bin/env python3
"""Tests for the experiment catalog (Lab Notebook #154).

python tools/analytics/test_experiments_catalog.py
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import experiments_catalog as cat  # noqa: E402


def _mk(root: Path, name: str, manifest: dict | None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    if manifest is not None:
        (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return d


def test_load_sorts_and_maps() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        _mk(
            tmp,
            "20260101_000000_old",
            {
                "experiment_id": "20260101_000000_old",
                "subject": "old",
                "started_utc": "2026-01-01T00:00:00Z",
                "duration_s": 30,
                "sample_rate_s": 1.0,
                "stopped_by": "duration",
                "labels": {"s1": "a"},
                "transport": {"rows": 10, "sweeps": 3, "dropped": 0, "crc_fail": 0},
            },
        )
        _mk(
            tmp,
            "20260626_120000_new",
            {
                "experiment_id": "20260626_120000_new",
                "title": "open bench",
                "subject": "open_bench",
                "started_utc": "2026-06-26T12:00:00Z",
                "duration_s": 60,
                "transport": {"rows": 20, "sweeps": 5},
            },
        )
        c = cat.load_catalog(tmp)
        assert len(c) == 2
        assert c[0]["experiment_id"] == "20260626_120000_new"  # newest first
        assert c[0]["title"] == "open bench"  # title preferred over subject
        assert c[1]["title"] == "old"  # falls back to subject when no title
        assert c[0]["sweeps"] == 5 and c[1]["rows"] == 10
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_skips_missing_and_bad() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        _mk(tmp, "no_manifest", None)  # dir without a manifest -> skipped
        bad = _mk(tmp, "bad", {"x": 1})
        (bad / "manifest.json").write_text("{not json", encoding="utf-8")
        _mk(tmp, "partial", {"subject": "p", "started_utc": "2026-06-26T00:00:00Z"})
        c = cat.load_catalog(tmp)
        ids = [e["experiment_id"] for e in c]
        assert "no_manifest" not in ids and "bad" not in ids
        partial = next(e for e in c if e["subject"] == "p")
        assert partial["sweeps"] is None and partial["duration_s"] is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_empty_and_missing_dir() -> None:
    assert cat.load_catalog(Path(tempfile.mkdtemp())) == []
    assert cat.load_catalog(Path(tempfile.mkdtemp()) / "nope") == []


def test_render_smoke() -> None:
    tmp = Path(tempfile.mkdtemp())
    try:
        _mk(
            tmp,
            "20260626_120000_x",
            {
                "experiment_id": "20260626_120000_x",
                "title": "my <test>",
                "subject": "x",
                "started_utc": "2026-06-26T12:00:00Z",
                "duration_s": 60,
                "transport": {"rows": 20, "sweeps": 5},
            },
        )
        out = cat.render_catalog(cat.load_catalog(tmp))
        assert "__SPROUT_TOKENS__" not in out  # token placeholder filled
        assert "__CARDS__" not in out and "__COUNT__" not in out
        assert "my &lt;test&gt;" in out  # title html-escaped
        assert "1 capture(s)" in out
        assert "No experiments yet" in cat.render_catalog([])  # empty state
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_load_sorts_and_maps,
        test_skips_missing_and_bad,
        test_empty_and_missing_dir,
        test_render_smoke,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")


# --------------------------------------------------------------------------- #
# #545 item 1 — planned records appear in the catalog
# --------------------------------------------------------------------------- #


def _planned(docs: Path, eid: str, **extra) -> None:
    doc = {"experiment_id": eid, "status": "planned", "title": f"plan {eid}"}
    doc.update(extra)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / f"{eid}.json").write_text(json.dumps(doc), encoding="utf-8")


def _captured(root: Path, eid: str, started: str) -> None:
    d = root / eid
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.json").write_text(
        json.dumps({"experiment_id": eid, "title": eid, "started_utc": started}),
        encoding="utf-8",
    )


def test_a_planned_record_reaches_the_catalog(tmp_path: Path) -> None:
    from experiments_catalog import load_planned

    docs, exp = tmp_path / "docs", tmp_path / "exp"
    _planned(docs, "plan-a", saved_at="2026-07-19T10:00:00Z")
    got = load_planned(docs, exp)
    assert [e["experiment_id"] for e in got] == ["plan-a"]
    e = got[0]
    assert e["kind"] == "planned"
    assert e["started_utc"] is None  # a plan never fakes a run window
    assert e["planned_at"] == "2026-07-19T10:00:00Z"


def test_a_landed_capture_supersedes_its_own_plan(tmp_path: Path) -> None:
    from experiments_catalog import load_planned

    docs, exp = tmp_path / "docs", tmp_path / "exp"
    _planned(docs, "run-1")
    _captured(exp, "run-1", "2026-07-19T12:00:00Z")
    # the capture landed under the same id -> the plan drops out (no double-count)
    assert load_planned(docs, exp) == []


def test_only_planned_status_qualifies_and_junk_never_breaks_it(tmp_path: Path) -> None:
    from experiments_catalog import load_planned

    docs, exp = tmp_path / "docs", tmp_path / "exp"
    _planned(docs, "plan-ok")
    (docs / "complete.json").write_text(
        json.dumps({"experiment_id": "complete", "status": "complete"}),
        encoding="utf-8",
    )
    (docs / "unset.json").write_text(json.dumps({"notes": "legacy"}), encoding="utf-8")
    (docs / "torn.json").write_text("{not json", encoding="utf-8")
    assert [e["experiment_id"] for e in load_planned(docs, exp)] == ["plan-ok"]


def test_combined_orders_plans_by_when_they_were_written(tmp_path: Path) -> None:
    from experiments_catalog import load_combined

    docs, exp, bench = tmp_path / "docs", tmp_path / "exp", tmp_path / "bench"
    _captured(exp, "old-run", "2026-07-01T00:00:00Z")
    _captured(exp, "new-run", "2026-07-20T00:00:00Z")
    _planned(docs, "mid-plan", saved_at="2026-07-10T00:00:00Z")
    ids = [e["experiment_id"] for e in load_combined(exp, bench, docs)]
    assert ids == ["new-run", "mid-plan", "old-run"]  # the plan sits by planned_at


def test_the_planned_card_says_planned_and_shows_no_fake_figures() -> None:
    from experiments_catalog import planned_card

    html_out = planned_card(
        {
            "kind": "planned",
            "experiment_id": "plan-a",
            "title": "dry-down #2",
            "planned_at": "2026-07-19T10:00:00Z",
            "labels": {"board": "classic"},
        }
    )
    assert "planned — not yet run" in html_out
    assert 'href="/lab/plan-a"' in html_out
    assert "sweeps" not in html_out and "rows" not in html_out  # no empty run stats
