"""Tests for the bench-package adapter + catalog integration (#444).

Covers both landed manifest shapes (per-window plant data #419 · top-level row_count
#428), graceful degradation, the card marker, the combined catalog merge, and a
read-only check against the actually-landed packages (AC #4).
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.analytics import bench_packages as bp
from tools.analytics import experiments_catalog as cat

_DATA = Path(__file__).resolve().parents[1] / "docs" / "experiments" / "data"


def _mk_pkg(root: Path, name: str, manifest: dict | None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    if manifest is not None:
        (d / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return d


def test_maps_plant_window_package(tmp_path: Path) -> None:
    _mk_pkg(
        tmp_path,
        "20260629_arc",
        {
            "experiment_id": "20260629_arc",
            "date_local": "2026-06-29",
            "lane": "Sage",
            "purpose": "recover the arc",
            "refs": {"data_issue": "#380"},
            "plant_windows": [
                {
                    "plant_id": "P01",
                    "valid_probe_ids": ["s1", "s2"],
                    "row_count": 100,
                    "csv_files": ["a.csv", "b.csv"],
                },
                {
                    "plant_id": "P02",
                    "valid_probe_ids": ["s2", "s3"],
                    "row_count": 50,
                    "csv_files": ["c.csv"],
                },
            ],
        },
    )
    (e,) = bp.load_bench_packages(tmp_path)
    assert e["kind"] == "bench" and e["title"] == "arc"
    assert e["plants"] == ["P01", "P02"] and e["probes"] == ["s1", "s2", "s3"]
    assert e["rows"] == 150 and e["raw_slices"] == 3
    assert e["started_utc"] == "2026-06-29T00:00:00Z"
    assert e["refs"] == {"data_issue": "#380"}


def test_maps_toplevel_rowcount_package(tmp_path: Path) -> None:
    _mk_pkg(
        tmp_path,
        "20260630_skylight_env",
        {
            "experiment_id": "20260630_skylight_env",
            "date_local": "2026-06-30",
            "lane": "Sage",
            "row_count": 35292,
            "raw_slice_count": 17,
        },
    )
    (e,) = bp.load_bench_packages(tmp_path)
    assert e["title"] == "skylight env"
    assert e["rows"] == 35292 and e["raw_slices"] == 17
    assert e["plants"] == [] and e["probes"] == []  # env baseline: no per-plant windows


def test_missing_and_unreadable_are_skipped(tmp_path: Path) -> None:
    _mk_pkg(tmp_path, "nomanifest", None)
    bad = _mk_pkg(tmp_path, "bad", {"x": 1})
    (bad / "manifest.json").write_text("{not json", encoding="utf-8")
    assert bp.load_bench_packages(tmp_path) == []


def test_bench_card_renders_marker_and_refs(tmp_path: Path) -> None:
    _mk_pkg(
        tmp_path,
        "20260629_arc",
        {
            "experiment_id": "20260629_arc",
            "date_local": "2026-06-29",
            "lane": "Sage",
            "refs": {"data_issue": "#380"},
            "plant_windows": [
                {"plant_id": "P01", "valid_probe_ids": ["s1"], "row_count": 9}
            ],
        },
    )
    (e,) = bp.load_bench_packages(tmp_path)
    card = bp.bench_card(e)
    assert 'class="ecard bench"' in card
    assert "Bench &#183; Sage" in card or "Bench · Sage" in card
    assert "data_issue: #380" in card
    assert "20260629_arc" in card


def test_load_combined_merges_and_sorts(tmp_path: Path) -> None:
    exp = tmp_path / "experiments"
    exp.mkdir()
    _mk_pkg(
        exp,
        "20260101_000000_cap",
        {
            "experiment_id": "20260101_000000_cap",
            "title": "app cap",
            "started_utc": "2026-01-01T00:00:00Z",
        },
    )
    data = tmp_path / "data"
    data.mkdir()
    _mk_pkg(
        data,
        "20260629_arc",
        {"experiment_id": "20260629_arc", "date_local": "2026-06-29", "lane": "Sage"},
    )
    combined = cat.load_combined(str(exp), str(data))
    assert [e["experiment_id"] for e in combined] == [
        "20260629_arc",  # 2026-06-29 sorts before the January capture
        "20260101_000000_cap",
    ]
    assert combined[0]["kind"] == "bench"
    assert combined[1].get("kind") != "bench"  # an app capture has no bench marker


def test_bench_card_links_to_detail(tmp_path: Path) -> None:
    _mk_pkg(
        tmp_path,
        "20260629_arc",
        {"experiment_id": "20260629_arc", "date_local": "2026-06-29", "lane": "Sage"},
    )
    (e,) = bp.load_bench_packages(tmp_path)
    assert 'href="/lab/bench/20260629_arc"' in bp.bench_card(e)


def test_render_bench_detail(tmp_path: Path) -> None:
    _mk_pkg(
        tmp_path,
        "20260629_arc",
        {
            "experiment_id": "20260629_arc",
            "date_local": "2026-06-29",
            "lane": "Sage",
            "purpose": "recover the arc from samples",
            "refs": {"data_issue": "#380"},
            "plant_windows": [
                {
                    "plant_id": "P01",
                    "phase": "watering",
                    "valid_probe_ids": ["s1", "s2"],
                    "row_count": 100,
                    "csv_files": ["windows/p01.csv"],
                }
            ],
        },
    )
    page = bp.render_bench_detail("20260629_arc", tmp_path)
    assert page is not None and page.startswith("<!doctype html>")
    assert "recover the arc from samples" in page  # purpose
    assert "P01" in page and "watering" in page  # plant window
    assert "data_issue: #380" in page  # analysis surface
    assert "windows/p01.csv" in page  # raw slice
    assert "plant windows" in page


def test_render_bench_detail_missing_returns_none(tmp_path: Path) -> None:
    assert bp.render_bench_detail("nope", tmp_path) is None


def test_render_bench_detail_rejects_traversal(tmp_path: Path) -> None:
    # The id is validated before any filesystem access — no traversal from the URL.
    assert bp.render_bench_detail("../secrets", tmp_path) is None
    assert bp.render_bench_detail("a/b", tmp_path) is None


def test_bench_detail_has_backfill_notes_section(tmp_path: Path) -> None:
    # #450 slice 3: the detail page carries a findings/conclusion back-fill form that
    # POSTs to /lab/bench/<id>/notes.
    _mk_pkg(
        tmp_path,
        "20260629_arc",
        {"experiment_id": "20260629_arc", "date_local": "2026-06-29", "lane": "Sage"},
    )
    page = bp.render_bench_detail("20260629_arc", tmp_path)
    assert page is not None
    assert "findings &amp; notes (back-fill)" in page
    assert 'class="benchnotes" data-pkg="20260629_arc"' in page
    assert 'id="bn-findings"' in page and 'id="bn-save"' in page
    assert "/lab/bench/" in page  # the POST target lives in the inline script


def test_real_landed_packages_load() -> None:
    # AC #4: works for the actually-landed packages (read-only, deterministic).
    if not _DATA.exists():
        return
    ids = {e["experiment_id"] for e in bp.load_bench_packages()}
    assert "20260629_greenhouse_bench_arc_recovery" in ids
    arc = next(
        e
        for e in bp.load_bench_packages()
        if e["experiment_id"].endswith("arc_recovery")
    )
    assert len(arc["plants"]) == 11 and arc["probes"] == ["s1", "s2", "s3", "s4"]
