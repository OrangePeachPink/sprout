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
import re
from pathlib import Path

from tools.analytics.design_assets import (
    FONTS_CSS,
    TOKENS_CSS,
)
from tools.analytics.lab_notes import (
    load_notes,
)

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DETAIL_TEMPLATE = _HERE / "lab_bench_detail_template.html"

_DATA_ROOT = _REPO / "docs" / "experiments" / "data"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no path traversal from the URL


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


def soft_wrap(escaped: str) -> str:
    """Add ``<wbr>`` break opportunities after ``_`` / ``-`` so a long experiment
    title/id wraps at token boundaries instead of mid-word (#596 flag). Input must
    already be HTML-escaped; the ``<wbr>`` tags are injected literally. Shared by the
    app-capture card (``experiments_catalog._card``) and the bench card below."""
    return escaped.replace("_", "_<wbr>").replace("-", "-<wbr>")


def bench_card(e: dict) -> str:
    """A bench-package catalog card — a sibling of the app-capture ``ecard``, with a
    ``bench`` marker class, linking to the ``/lab/bench/<id>`` detail page."""
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
    path = soft_wrap(esc(str(e.get("package_path") or "")))
    return (
        f'<a class="ecard bench" href="/lab/bench/{eid}">'
        f'<div class="ecard-h"><h3>{soft_wrap(esc(str(e["title"])))}</h3>'
        f'<span class="ewhen">{esc(str(e.get("date_local") or "—"))}</span></div>'
        f'<div class="emeta">{esc(" · ".join(bits))}</div>'
        f'<div class="echips">{chips}</div>'
        f'<div class="efoot"><span class="eid">{soft_wrap(eid)}</span>'
        f'<span class="equal mono">{path}</span></div>'
        "</a>"
    )


def _slice_files(m: dict) -> list[str]:
    """The raw CSV slice paths a package enumerates (per-window ``csv_files``)."""
    files: list[str] = []
    for w in m.get("plant_windows") or []:
        files.extend(w.get("csv_files") or [])
    return files


def _detail_body(m: dict, e: dict) -> str:
    """The read-only detail body: purpose, facts, plant windows / observations, the
    analysis-surface refs, and the raw slices — all from the manifest, never re-read."""
    esc = html.escape
    parts: list[str] = []
    if m.get("purpose"):
        parts.append(f'<p class="purpose">{esc(str(m["purpose"]))}</p>')
    plants = e.get("plants") or []
    facts = [
        ("lane", e.get("lane")),
        ("date", e.get("date_local")),
        ("rows", e.get("rows")),
        ("raw slices", e.get("raw_slices")),
        ("plants", f"{len(plants)} ({', '.join(plants)})" if plants else None),
        ("probes", ", ".join(e.get("probes") or []) or None),
    ]
    rows = "".join(
        f'<tr><td class="k">{esc(k)}</td><td>{esc(str(v))}</td></tr>'
        for k, v in facts
        if v is not None
    )
    parts.append(f'<table class="facts"><tbody>{rows}</tbody></table>')

    windows = m.get("plant_windows") or []
    if windows:
        trs = "".join(
            f"<tr><td>{esc(str(w.get('plant_id', '—')))}</td>"
            f"<td>{esc(str(w.get('phase', '—')))}</td>"
            f"<td>{esc(', '.join(w.get('valid_probe_ids') or []) or '—')}</td>"
            f"<td>{esc(str(w.get('row_count', '—')))}</td></tr>"
            for w in windows
        )
        parts.append(
            "<h2>plant windows</h2><table class='wt'><thead><tr><th>plant</th>"
            "<th>phase</th><th>valid probes</th><th>rows</th></tr></thead>"
            f"<tbody>{trs}</tbody></table>"
        )
    elif m.get("key_observations"):
        obs = "".join(f"<li>{esc(str(o))}</li>" for o in m["key_observations"])
        parts.append(f"<h2>key observations</h2><ul class='slices'>{obs}</ul>")

    refs = e.get("refs") or {}
    if refs:
        chips = "".join(
            f'<span class="lchip">{esc(str(k))}: {esc(str(v))}</span>'
            for k, v in refs.items()
        )
        parts.append(f"<h2>analysis surfaces</h2><div class='chips'>{chips}</div>")

    slices = _slice_files(m)
    if slices:
        shown = slices[:40]
        lis = "".join(f"<li>{esc(str(s))}</li>" for s in shown)
        if len(slices) > 40:
            lis += f"<li>… +{len(slices) - 40} more</li>"
        parts.append(
            f"<h2>raw slices ({len(slices)})</h2><ul class='slices'>{lis}</ul>"
        )

    parts.append(
        f'<p class="note">package: {esc(str(e.get("package_path") or ""))}</p>'
    )
    return "\n".join(parts)


_NOTES_SCRIPT = """<script>
(function () {
  var el = document.querySelector('.benchnotes');
  if (!el) return;
  var pkg = el.getAttribute('data-pkg');
  var btn = document.getElementById('bn-save');
  var st = document.getElementById('bn-status');
  btn.addEventListener('click', function () {
    btn.disabled = true; st.textContent = 'saving...';
    fetch('/lab/bench/' + encodeURIComponent(pkg) + '/notes', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        findings: document.getElementById('bn-findings').value,
        conclusion: document.getElementById('bn-conclusion').value
      })
    }).then(function (r) { return r.json(); })
      .then(function (d) {
        st.textContent = d.error ? ('error: ' + d.error)
          : ('saved ' + (d.path || '') + ' \\u00b7 v' + (d.version || '?'));
        btn.disabled = false;
      }).catch(function () {
        st.textContent = 'save failed - your text is kept'; btn.disabled = false;
      });
  });
})();
</script>"""


def _notes_section(pkg_id: str, notes: dict) -> str:
    """Back-fill findings/conclusion onto a landed package (#450 slice 3). Notes persist
    to the ADR-0017 sidecar keyed by the package id, so a bench day's interpretation is
    attached to its evidence — status/edit_log provenance rides once #473 lands."""
    esc = html.escape
    saved = (
        f"v{notes.get('version')} · saved {esc(str(notes.get('saved_at')))}"
        if notes.get("saved_at")
        else "not yet saved"
    )
    return (
        "<h2>findings &amp; notes (back-fill)</h2>"
        f'<div class="benchnotes" data-pkg="{esc(pkg_id)}">'
        '<label>findings<textarea id="bn-findings" rows="4">'
        f"{esc(str(notes.get('findings') or ''))}</textarea></label>"
        '<label>conclusion<textarea id="bn-conclusion" rows="3">'
        f"{esc(str(notes.get('conclusion') or ''))}</textarea></label>"
        '<div class="bn-actions">'
        '<button id="bn-save" type="button">Save notes</button>'
        f'<span id="bn-status" class="note">{esc(saved)}</span>'
        "</div></div>" + _NOTES_SCRIPT
    )


def render_bench_detail(pkg_id: str, data_dir: str | Path | None = None) -> str | None:
    """The ``/lab/bench/<id>`` page for one landed package, or None (-> 404) if it
    doesn't exist. Read-only; path-traversal-safe (the id is validated)."""
    root = Path(data_dir) if data_dir else _DATA_ROOT
    if not _ID_RE.match(pkg_id or "") or not root.exists():
        return None
    pkg_dir = root / pkg_id
    manifest = pkg_dir / "manifest.json"
    if not (pkg_dir.is_dir() and manifest.exists()):
        return None
    try:
        m = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    e = _entry(m, pkg_dir)
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    sub = f"Bench package · {e.get('lane') or 'bench'} · {e.get('date_local') or ''}"
    body = _detail_body(m, e) + "\n" + _notes_section(pkg_id, load_notes(pkg_id))
    return (
        _DETAIL_TEMPLATE.read_text(encoding="utf-8")
        .replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)
        .replace("<!--__TITLE__-->", html.escape(str(e["title"])))
        .replace("<!--__SUB__-->", html.escape(sub))
        .replace("<!--__BODY__-->", body)
    )
