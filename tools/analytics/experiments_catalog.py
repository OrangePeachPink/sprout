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
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_EXPERIMENTS = _REPO / "experiments"
_TEMPLATE = _HERE / "lab_template.html"

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from bench_packages import (  # noqa: E402  (landed bench packages, #444)
    bench_card,
    load_bench_packages,
    soft_wrap,
)
from dashboard import FONTS_CSS, TOKENS_CSS  # noqa: E402  (reuse the one token source)
from timefmt import local_first_system  # noqa: E402  (local-first lab labels, #328)


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


def load_combined(
    experiments_dir: str | Path | None = None,
    bench_dir: str | Path | None = None,
) -> list[dict]:
    """App captures + landed bench packages (#444), newest first — the ``/lab`` source.
    Bench entries carry ``kind == "bench"`` so the renderer picks ``bench_card``."""
    entries = load_catalog(experiments_dir) + load_bench_packages(bench_dir)
    entries.sort(key=lambda e: e.get("started_utc") or "", reverse=True)
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
            bench_card(e) if e.get("kind") == "bench" else _card(e) for e in entries
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
