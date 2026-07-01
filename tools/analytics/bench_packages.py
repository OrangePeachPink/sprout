#!/usr/bin/env python3
"""Bench-package adapter for the Lab Notebook catalog (#444, child of #153).

Sage lands durable **evidence packages** by hand under
``docs/experiments/data/<session>/`` (each a ``manifest.json`` + raw CSV slices) —
e.g. the P01-P11 arc recovery (#419) and the skylight env baseline (#428). The
app-capture catalog (``experiments_catalog``) has no idea they exist. This reads each
package's manifest and maps it to a catalog **entry** in the shape the catalog renders,
so bench sessions appear beside app-captured experiments with links to their analysis
surfaces and raw slices.

Honest-data: it reads the manifest only — never re-parsing the CSVs or re-interpreting
the evidence. Absent fields degrade to ``None`` / empty; an unreadable manifest is
skipped. Package-shape-agnostic: it maps the common fields (``experiment_id``,
``date_local``, ``lane``, ``purpose``, ``refs``) and pulls a plant/probe/row summary
from whichever package-specific keys are present, so a future package just works.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DATA_ROOT = _REPO / "docs" / "experiments" / "data"


def _title(experiment_id: str) -> str:
    """Human label from the session id, dropping a leading ``YYYYMMDD`` date stamp."""
    parts = experiment_id.split("_")
    while parts and parts[0].isdigit():
        parts.pop(0)
    return " ".join(parts) if parts else experiment_id


def _started_utc(date_local: str | None) -> str | None:
    """A sortable/displayable stamp from a package's ``date_local`` (date only)."""
    if not date_local:
        return None
    return f"{date_local}T00:00:00Z"


def _plants_and_probes(m: dict) -> tuple[list[str], list[str]]:
    windows = m.get("plant_windows") or []
    plants = sorted({w.get("plant_id") for w in windows if w.get("plant_id")})
    probes = sorted({p for w in windows for p in (w.get("valid_probe_ids") or []) if p})
    return plants, probes


def _row_count(m: dict) -> int | None:
    if m.get("row_count") is not None:  # #428-style top-level count
        return m["row_count"]
    windows = m.get("plant_windows") or []
    total = sum(w.get("row_count") or 0 for w in windows)  # #419-style per-window
    return total or None


def _raw_slices(m: dict) -> int | None:
    if m.get("raw_slice_count") is not None:  # #428 declares it
        return m["raw_slice_count"]
    windows = m.get("plant_windows") or []
    total = sum(len(w.get("csv_files") or []) for w in windows)  # #419 lists per window
    return total or None


def _entry(m: dict, pkg_dir: Path) -> dict:
    eid = m.get("experiment_id", pkg_dir.name)
    plants, probes = _plants_and_probes(m)
    try:
        rel = str(pkg_dir.relative_to(_REPO)).replace("\\", "/")
    except ValueError:  # a test/tmp dir outside the repo
        rel = pkg_dir.name
    return {
        "experiment_id": eid,
        "title": _title(eid),
        "kind": "bench",  # marks a Sage bench package vs an app capture
        "lane": m.get("lane"),
        "purpose": m.get("purpose"),
        "started_utc": _started_utc(m.get("date_local")),
        "date_local": m.get("date_local"),
        "plants": plants,
        "probes": probes,
        "rows": _row_count(m),
        "raw_slices": _raw_slices(m),
        # The manifest's own issue/PR refs are the analysis surfaces — never invented.
        "refs": m.get("refs") or {},
        "package_path": rel,
    }


def load_bench_packages(data_dir: str | Path | None = None) -> list[dict]:
    """Catalog entries for every ``docs/experiments/data/<session>/`` package, newest
    first. Missing/unreadable manifests are skipped (graceful degradation)."""
    root = Path(data_dir) if data_dir else _DATA_ROOT
    entries: list[dict] = []
    if not root.exists():
        return entries
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        manifest = d / "manifest.json"
        if not manifest.exists():
            continue
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        entries.append(_entry(m, d))
    entries.sort(key=lambda e: e.get("started_utc") or "", reverse=True)
    return entries


def bench_card(e: dict) -> str:
    """A catalog card for a bench package — visually a sibling of the app-capture card
    (``ecard``) with a ``bench`` marker class. Not an ``<a>``: a package has no capture
    detail route; its analysis refs + raw-slice path are surfaced inline instead."""
    esc = html.escape
    bits = [f"Bench · {esc(str(e.get('lane') or 'bench'))}"]
    if e.get("plants"):
        bits.append(f"{len(e['plants'])} plants")
    if e.get("probes"):
        bits.append(f"{len(e['probes'])} probes")
    if e.get("rows") is not None:
        bits.append(f"{e['rows']} rows")
    if e.get("raw_slices") is not None:
        bits.append(f"{e['raw_slices']} slices")
    chips = "".join(
        f'<span class="lchip">{esc(str(k))}: {esc(str(v))}</span>'
        for k, v in (e.get("refs") or {}).items()
    )
    eid = esc(str(e["experiment_id"]))
    return (
        '<div class="ecard bench">'
        f'<div class="ecard-h"><h3>{esc(str(e["title"]))}</h3>'
        f'<span class="ewhen">{esc(str(e.get("date_local") or "—"))}</span></div>'
        f'<div class="emeta">{esc(" · ".join(bits))}</div>'
        f'<div class="echips">{chips}</div>'
        f'<div class="efoot"><span class="eid">{eid}</span>'
        f'<span class="equal mono">{esc(str(e.get("package_path") or ""))}</span></div>'
        "</div>"
    )
