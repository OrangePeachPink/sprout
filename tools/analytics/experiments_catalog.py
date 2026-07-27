#!/usr/bin/env python3
"""Experiment catalog - the Lab Notebook's read-only front page (#154, epic #153).

Lists every ``experiments/<id>/`` from its ``manifest.json`` - title, date, duration,
sample count, probe labels, quality - without re-parsing the capture CSV. serve.py
serves the page at ``/lab`` and the data at ``/lab/experiments.json``.

    python tools/analytics/experiments_catalog.py        # print the catalog
    python tools/analytics/experiments_catalog.py --html # write reports/lab.html

Read-only: it never touches a capture. The polished visual system is Design's (#156);
this is a token-faithful tracer bullet.
"""

from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timezone
from pathlib import Path

from tools.analytics.bench_packages import (
    bench_card,
    load_bench_packages,
    soft_wrap,
)
from tools.analytics.design_assets import (
    FONTS_CSS,
    TOKENS_CSS,
)
from tools.analytics.timefmt import (
    local_first_system,
)

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_TEMPLATE = _HERE / "lab_template.html"

_EXPERIMENTS = _REPO / "experiments"


def load_catalog(experiments_dir: str | Path | None = None) -> list[dict]:
    """Every capture as a catalog entry, newest first. Missing/partial manifests
    degrade gracefully (skipped if unreadable; absent fields become None)."""
    root = Path(experiments_dir) if experiments_dir else _EXPERIMENTS
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
        t = m.get("transport") or {}
        entries.append(
            {
                "experiment_id": m.get("experiment_id", d.name),
                "title": m.get("title") or m.get("subject") or d.name,
                "subject": m.get("subject"),
                "started_utc": m.get("started_utc"),
                "ended_utc": m.get("ended_utc"),
                "duration_s": m.get("duration_s"),
                "sample_rate_s": m.get("sample_rate_s"),
                "stopped_by": m.get("stopped_by"),
                "labels": m.get("labels") or {},
                "sweeps": t.get("sweeps"),
                "rows": t.get("rows"),
                "dropped": t.get("dropped"),
                "crc_fail": t.get("crc_fail"),
            }
        )
    entries.sort(key=lambda e: e.get("started_utc") or "", reverse=True)
    return entries


def load_planned(
    docs_dir: str | Path | None = None,
    experiments_dir: str | Path | None = None,
) -> list[dict]:
    """#545 item 1 — PLANNED records as catalog entries.

    A planned experiment (#450) is a notes sidecar carrying ``status="planned"``
    written *before* the bench runs, so it has no ``manifest.json`` and was
    therefore invisible in the catalog — the operator could write a plan and then
    not find it anywhere. It appears here instead, marked ``kind="planned"`` so the
    renderer can treat it as an intention rather than a capture.

    A planned record whose capture has since landed (a manifest now exists under
    the same id) is **dropped from this list** — the real capture supersedes it, and
    showing both would double-count one experiment. Nothing is deleted on disk; this
    is a read-time view.
    """
    from tools.analytics.lab_notes import _DOCS_EXPERIMENTS  # the sidecar home

    root = Path(docs_dir) if docs_dir else _DOCS_EXPERIMENTS
    if not root.is_dir():
        return []
    captured = {e["experiment_id"] for e in load_catalog(experiments_dir)}
    out: list[dict] = []
    for f in sorted(root.glob("*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # a hand-edited/torn sidecar never breaks the catalog
        if not isinstance(doc, dict) or doc.get("status") != "planned":
            continue
        eid = doc.get("experiment_id") or f.stem
        if eid in captured:
            continue  # the capture landed — it supersedes its own plan
        out.append(
            {
                "kind": "planned",
                "experiment_id": eid,
                "title": doc.get("title") or doc.get("subject") or eid,
                "subject": doc.get("subject"),
                # a plan has no run window; sort it by when it was written so it
                # sits with the work it belongs to, never faking a start time
                "started_utc": None,
                "planned_at": doc.get("saved_at"),
                "ended_utc": None,
                "duration_s": None,
                "labels": doc.get("labels") or {},
            }
        )
    return out


def load_combined(
    experiments_dir: str | Path | None = None,
    bench_dir: str | Path | None = None,
    docs_dir: str | Path | None = None,
) -> list[dict]:
    """App captures + landed bench packages (#444) + planned records (#545), newest
    first — the ``/lab`` source. Entries carry ``kind`` so the renderer picks the
    right card (``bench`` / ``planned`` / absent = a real capture)."""
    entries = (
        load_catalog(experiments_dir)
        + load_bench_packages(bench_dir)
        + load_planned(docs_dir, experiments_dir)
    )
    # a plan has no started_utc, so it sorts by planned_at instead — an intention
    # sits in the timeline where it was written, never pretending to be a run
    entries.sort(
        key=lambda e: e.get("started_utc") or e.get("planned_at") or "", reverse=True
    )
    return entries


def _fmt_when(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return iso
    return local_first_system(dt)  # local-first, UTC secondary (#328)


def _fmt_dur(seconds: object) -> str:
    if seconds is None:
        return "—"
    s = round(float(seconds))
    return f"{s}s" if s < 60 else f"{s // 60}m {s % 60}s"


def planned_card(e: dict) -> str:
    """#545: a PLANNED record's card — an intention, not a capture.

    It deliberately shows no duration, sweep count, or quality figures: a plan has
    none, and rendering em-dashes where a real capture shows data would read as a
    failed run rather than an unstarted one. It says what it is ("planned"), when it
    was written, and links to the same detail route the notes already serve."""
    esc = html.escape
    chips = "".join(
        f'<span class="lchip">{esc(str(k))}: {esc(str(v))}</span>'
        for k, v in (e.get("labels") or {}).items()
    )
    eid = esc(str(e["experiment_id"]))
    when = esc(_fmt_when(e.get("planned_at")))
    return (
        f'<a class="ecard ecard-planned" href="/lab/{eid}">'
        f'<div class="ecard-h"><h3>{soft_wrap(esc(str(e["title"])))}</h3>'
        f'<span class="ewhen">planned {when}</span></div>'
        f'<div class="emeta">planned — not yet run</div>'
        f'<div class="echips">{chips}</div>'
        f"</a>"
    )


def _card(e: dict) -> str:
    esc = html.escape
    samples = f"{e['sweeps']} sweeps" if e.get("sweeps") is not None else "—"
    if e.get("rows") is not None:
        samples += f" · {e['rows']} rows"
    rate = f" @ {e['sample_rate_s']}s" if e.get("sample_rate_s") is not None else ""
    dur = esc(_fmt_dur(e.get("duration_s")))
    chips = "".join(
        f'<span class="lchip">{esc(str(k))}: {esc(str(v))}</span>'
        for k, v in (e.get("labels") or {}).items()
    )
    quality = []
    if e.get("dropped") is not None:
        quality.append(f"{e['dropped']} dropped")
    if e.get("crc_fail") is not None:
        quality.append(f"{e['crc_fail']} crc")
    if e.get("stopped_by"):
        quality.append(esc(str(e["stopped_by"])))
    eid = esc(str(e["experiment_id"]))
    return (
        f'<a class="ecard" href="/lab/{eid}">'  # click -> detail (#157)
        f'<div class="ecard-h"><h3>{soft_wrap(esc(str(e["title"])))}</h3>'
        f'<span class="ewhen">{esc(_fmt_when(e.get("started_utc")))}</span></div>'
        f'<div class="emeta">{dur} · {esc(samples)}{esc(rate)}</div>'
        f'<div class="echips">{chips}</div>'
        f'<div class="efoot"><span class="eid">{soft_wrap(eid)}</span>'
        f'<span class="equal">{esc(" · ".join(quality))}</span></div>'
        "</a>"
    )


def render_catalog(entries: list[dict]) -> str:
    """The full /lab page: the template shell with tokens/fonts + the cards injected."""
    template = _TEMPLATE.read_text(encoding="utf-8")
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    cards = (
        "\n".join(
            bench_card(e)
            if e.get("kind") == "bench"
            else planned_card(e)
            if e.get("kind") == "planned"
            else _card(e)
            for e in entries
        )
        if entries
        else '<p class="empty">No experiments yet — run one from the dashboard\'s '
        "Experiment Capture panel.</p>"
    )
    return (
        template.replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)
        .replace("<!--__CARDS__-->", cards)
        .replace("<!--__COUNT__-->", str(len(entries)))
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Print or render the experiment catalog.")
    ap.add_argument("--html", action="store_true", help="write reports/lab.html")
    ap.add_argument("--dir", help="experiments dir (default: repo experiments/)")
    args = ap.parse_args(argv)
    entries = load_combined(args.dir)  # app captures + landed bench packages (#444)
    if args.html:
        out = _REPO / "reports" / "lab.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_catalog(entries), encoding="utf-8", newline="\n")
        print(f"wrote {out} ({len(entries)} experiment(s))")
    else:
        for e in entries:
            dur = _fmt_dur(e.get("duration_s"))
            print(f"{e['experiment_id']}  {e['title']!r}  {dur}")
        print(f"{len(entries)} experiment(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
