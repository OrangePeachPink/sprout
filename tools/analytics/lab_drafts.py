#!/usr/bin/env python3
"""Agent-prepared experiment drafts (#326).

Sage/Data can prepare a bench run *before* Veronica touches plants/probes/water:
the subject, cadence, duration, source, probe labels, and the lab-note plan
(hypothesis / method / findings / conclusion) + planned intervention markers. The
operator still physically presses Start — **a draft never starts acquisition.**

File-backed (the simplest agent API): a draft is tracked JSON at
``docs/experiments/drafts/<name>.json``. serve.py lists/serves them; the Experiment
Capture form loads one to prefill its fields. Planned interventions are written as
``@t+180s remove shade`` lines inside the method note, so once the notes are saved
to the run they render as chart markers via the #325 convention — one mechanism,
not two.

Usage (agent path)::

    python tools/analytics/lab_drafts.py --name shade-recovery \\
        --subject "s1 shade removal recovery" --rate-s 1 --duration-s 600 \\
        --source serial --port COM6 --label s1="under shade" \\
        --hypothesis "removing shade raises ADC (drying) within minutes" \\
        --method "@t+0s baseline; @t+180s remove shade; watch s1"

Draft -> lifecycle bridge (#450 "slice 3" / pre-run registration):
``save_draft`` also writes a ``status=planned`` lifecycle record (the ADR-0017
notes model, #158/#473) at ``docs/experiments/<name>.json``, seeded from the
draft's hypothesis/method — so the plan is visible in the Lab Notebook catalog
*before* the bench starts, satisfying "create a planned experiment before it
runs." This is the thin Data-only half of the bridge scoped on #450: the draft's
name doubles as the pre-run record's id. **Not built here** (a separate,
cross-lane decision, #450's own routing): what advances ``planned -> running ->
complete`` when a capture actually starts/finishes, and whether the run's real
``experiment_id`` gets linked back to this draft's planned record — that touches
the capture-start/stop control plane (``experiment_capture``/``control``),
Firmware-adjacent operator-plane territory, not pure Data. Until that lands, a
planned record from a draft that never runs stays visibly `planned` — an honest,
not a silent, gap.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DRAFTS_DIR = _REPO / "docs" / "experiments" / "drafts"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no traversal from the URL
_NOTE_FIELDS = ("hypothesis", "method", "findings", "conclusion")

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from lab_notes import save_notes  # noqa: E402  (the draft->planned bridge, #450)


def _draft_path(name: str, drafts_dir: str | Path | None) -> Path | None:
    if not _NAME_RE.match(name) or ".." in name:
        return None
    root = Path(drafts_dir) if drafts_dir else _DRAFTS_DIR
    return root / f"{name}.json"


def draft_rel_path(name: str, drafts_dir: str | Path | None = None) -> str | None:
    p = _draft_path(name, drafts_dir)
    if p is None:
        return None
    try:
        return p.resolve().relative_to(_REPO).as_posix()
    except ValueError:
        return p.as_posix()


def _empty(name: str) -> dict:
    return {
        "name": name,
        "subject": "",
        "rate_s": 1.0,
        "duration_s": 60.0,
        "source": "serial",
        "port": "",
        "labels": {},
        "notes": dict.fromkeys(_NOTE_FIELDS, ""),
        "saved_at": None,
    }


def save_draft(
    name: str,
    fields: dict,
    drafts_dir: str | Path | None = None,
    *,
    docs_dir: str | Path | None = None,
    author: str | None = None,
    sync_planned: bool = True,
) -> dict:
    """Write an experiment draft. Returns the persisted draft. Raises on a bad name.

    This only writes a plan file — it never touches the serial port or starts a
    capture (the operator-start guarantee, #326).

    Pre-run registration bridge (#450): also writes/updates a ``status=planned``
    lifecycle record (``lab_notes``) at the draft's name, seeded from its
    hypothesis/method, so the plan is visible in the Lab Notebook *before* the
    bench starts. ``sync_planned=False`` skips this (e.g. a caller that only
    wants the plan file, or a test isolating draft-only behavior).
    ``docs_dir``/``author`` pass straight through to ``lab_notes.save_notes``."""
    p = _draft_path(name, drafts_dir)
    if p is None:
        raise ValueError(f"invalid draft name: {name!r}")
    draft = _empty(name)
    for k in ("subject", "source", "port"):
        if k in fields and fields[k] is not None:
            draft[k] = str(fields[k])
    for k in ("rate_s", "duration_s"):
        if k in fields and fields[k] is not None:
            draft[k] = float(fields[k])
    if isinstance(fields.get("labels"), dict):
        draft["labels"] = {str(j): str(v) for j, v in fields["labels"].items()}
    notes = fields.get("notes")
    if isinstance(notes, dict):
        draft["notes"] = {k: str(notes.get(k, "")) for k in _NOTE_FIELDS}
    draft["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(draft, indent=2) + "\n", encoding="utf-8", newline="\n")
    if sync_planned:
        save_notes(
            name,
            draft["notes"],
            docs_dir,
            status="planned",
            author=author or "Sage",
        )
    return draft


def load_draft(name: str, drafts_dir: str | Path | None = None) -> dict | None:
    """The draft, or None if absent / unreadable / bad name."""
    p = _draft_path(name, drafts_dir)
    if p is None or not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return doc if isinstance(doc, dict) else None


def list_drafts(drafts_dir: str | Path | None = None) -> list[dict]:
    """All drafts as ``{name, subject}``, newest-name first — for the UI selector."""
    root = Path(drafts_dir) if drafts_dir else _DRAFTS_DIR
    if not root.is_dir():
        return []
    out: list[dict] = []
    for p in sorted(root.glob("*.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(d, dict):
            out.append({"name": d.get("name", p.stem), "subject": d.get("subject", "")})
    return out


def _parse_label(pairs: list[str] | None) -> dict:
    out: dict = {}
    for pair in pairs or []:
        key, _, val = pair.partition("=")
        if val:
            out[key.strip()] = val.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Create an experiment draft (no capture).")
    ap.add_argument("--name", required=True, help="draft name (folder-safe token)")
    ap.add_argument("--subject", default="")
    ap.add_argument("--rate-s", type=float, default=1.0)
    ap.add_argument("--duration-s", type=float, default=60.0)
    ap.add_argument("--source", default="serial", choices=("serial", "synthetic"))
    ap.add_argument("--port", default="")
    ap.add_argument("--label", action="append", help="probe label k=v (repeatable)")
    ap.add_argument("--hypothesis", default="")
    ap.add_argument("--method", default="", help="incl. @t+180s markers (#325)")
    ap.add_argument("--findings", default="")
    ap.add_argument("--conclusion", default="")
    args = ap.parse_args(argv)
    save_draft(
        args.name,
        {
            "subject": args.subject,
            "rate_s": args.rate_s,
            "duration_s": args.duration_s,
            "source": args.source,
            "port": args.port,
            "labels": _parse_label(args.label),
            "notes": {
                "hypothesis": args.hypothesis,
                "method": args.method,
                "findings": args.findings,
                "conclusion": args.conclusion,
            },
        },
    )
    print(f"wrote draft {draft_rel_path(args.name)} (no capture started)")
    print(f"registered as a planned experiment: docs/experiments/{args.name}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
