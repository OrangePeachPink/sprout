#!/usr/bin/env python3
"""Lab notes - the experiment notebook's living log (#158).

The notes (Hypothesis / Method / Findings / Conclusion) are the precious part of an
experiment: the human interpretation. Per ADR-0017 they live in the *tracked*
``docs/experiments/<experiment_id>.json`` sidecar (NOT the gitignored capture), so a
commit backs them up. This module is the load/save seam; serve.py exposes it at
``GET/POST /lab/<id>/notes`` and lab_detail.py renders + edits it.

Durability boundary (ADR-0017 §5): we write the working-tree file; **commit = backup**.
This never auto-commits.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_DOCS_EXPERIMENTS = _REPO / "docs" / "experiments"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no traversal from the URL
_FIELDS = ("hypothesis", "method", "findings", "conclusion")
# Editable-lifecycle foundation (#450 slice 1): a record is editable at any stage.
# `status` is optional (None = unset, e.g. legacy notes) — backward-compatible.
_STATUSES = ("planned", "running", "complete")


def _empty() -> dict:
    """The ADR-0017 notes shape, unsaved (+ #450: ``status`` / ``edit_log``)."""
    return {
        "hypothesis": "",
        "method": "",
        "findings": "",
        "conclusion": "",
        "status": None,  # planned | running | complete | None (unset) — #450
        "edit_log": [],  # [{at, by, fields}] edit provenance (Sage-as-author) — #450
        "saved_at": None,
        "version": 0,
    }


def _notes_path(eid: str, docs_dir: str | Path | None) -> Path | None:
    if not _ID_RE.match(eid) or ".." in eid:
        return None
    root = Path(docs_dir) if docs_dir else _DOCS_EXPERIMENTS
    return root / f"{eid}.json"


def notes_rel_path(eid: str, docs_dir: str | Path | None = None) -> str | None:
    """The save target as a repo-relative POSIX path, for the UI (#327).

    Shown on success ("saved <path>") and on failure ("couldn't write <path>") so
    the operator always knows exactly which file the save targeted."""
    p = _notes_path(eid, docs_dir)
    if p is None:
        return None
    try:
        return p.resolve().relative_to(_REPO).as_posix()
    except ValueError:
        return p.as_posix()


def load_notes(eid: str, docs_dir: str | Path | None = None) -> dict:
    """The notes object for an experiment (ADR-0017 shape), or empty defaults.

    Reads the tracked ``docs/experiments/<eid>.json`` sidecar; tolerant of a missing
    file, a bad id, or a sidecar that carries other keys (e.g. a findings report's
    anchors block - we only read its ``notes``)."""
    p = _notes_path(eid, docs_dir)
    if p is None or not p.exists():
        return _empty()
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    notes = doc.get("notes") if isinstance(doc, dict) else None
    out = _empty()
    if isinstance(notes, dict):
        out.update({k: notes.get(k, out[k]) for k in out})
    return out


def save_notes(
    eid: str,
    fields: dict,
    docs_dir: str | Path | None = None,
    *,
    status: str | None = None,
    author: str | None = None,
) -> dict:
    """Persist the four prose fields; bump ``version`` and stamp ``saved_at`` (UTC).

    Editable at any lifecycle stage (#450): an optional ``status`` (planned/running/
    complete) is carried across saves and overridden when given; every save appends an
    ``edit_log`` entry recording **who** documented it (``author`` — Sage-as-author),
    **when**, and which fields it touched. Preserves every other top-level key in the
    sidecar, so saving onto a findings report never clobbers its anchors/states.
    Writes the working-tree file; the commit is the backup (ADR-0017 §5). Raises
    ValueError on a bad id or an unknown ``status``."""
    p = _notes_path(eid, docs_dir)
    if p is None:
        raise ValueError(f"invalid experiment id: {eid!r}")
    doc: dict = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                doc = existing
        except (json.JSONDecodeError, OSError):
            doc = {}
    prev = doc.get("notes") if isinstance(doc.get("notes"), dict) else {}
    notes = _empty()
    notes.update({k: str(prev.get(k, "")) for k in _FIELDS})  # carry untouched fields
    notes.update({k: str(fields[k]) for k in _FIELDS if k in fields})
    notes["version"] = int(prev.get("version", 0) or 0) + 1
    notes["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # lifecycle status (#450): carry prev, override when given, validate the value.
    prev_status = prev.get("status")
    if status is not None and status not in _STATUSES:
        raise ValueError(f"invalid status {status!r}; expected one of {_STATUSES}")
    notes["status"] = status if status is not None else prev_status
    # edit provenance (#450): who documented this edit, when, and what it touched.
    changed = [k for k in _FIELDS if k in fields]
    if status is not None and status != prev_status:
        changed.append("status")
    notes["edit_log"] = [
        *(prev.get("edit_log") or []),
        {"at": notes["saved_at"], "by": author or "unknown", "fields": changed},
    ]
    doc.setdefault("experiment_id", eid)
    doc["notes"] = notes
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    # pure persisted notes; serve.py adds the save path to the response (#327)
    return notes


# #545 item 2 (maintainer ruling A, 2026-07-20): the capture control plane owns the
# planned -> running -> complete stamp. This ORDER is the lifecycle; status moves
# forward along it and never back.
_STATUS_ORDER = {"planned": 0, "running": 1, "complete": 2}
CONTROL_PLANE_AUTHOR = "control-plane"


def advance_status(
    eid: str,
    to_status: str,
    docs_dir: str | Path | None = None,
    *,
    author: str = CONTROL_PLANE_AUTHOR,
    create: bool = False,
) -> dict:
    """Stamp a capture's lifecycle status — the narrow seam the control plane calls
    when a run starts and finishes (#545 item 2, ruling A).

    Deliberately NOT ``save_notes(status=...)``: that seam bumps the prose ``version``
    and appends an edit-log entry describing a human documenting the experiment. A
    machine stamping "this run started" is a different event; conflating them would
    inflate the version of prose nobody wrote and credit the operator with edits they
    never made.

    Rules:

    - **Forward only** — ``planned -> running -> complete``. A backwards move is
      refused rather than silently rewriting history: a run that already completed
      cannot be un-completed by a late or duplicated signal.
    - **Idempotent** — already at the target means no write and no version bump, so a
      control-plane retry is safe.
    - **An absent sidecar is not an error** — an unplanned capture simply has no plan
      to advance (``reason="no-sidecar"``) unless ``create=True``.
    - The transition is attributed to the **control plane** in ``edit_log``, so the
      provenance trail shows what moved this and when.

    Returns ``{moved, from, to, reason?}``; never raises for an ordinary no-op.
    """
    if to_status not in _STATUS_ORDER:
        raise ValueError(f"invalid status {to_status!r}; expected one of {_STATUSES}")
    p = _notes_path(eid, docs_dir)
    if p is None:
        raise ValueError(f"invalid experiment id: {eid!r}")
    doc: dict = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                doc = existing
        except (json.JSONDecodeError, OSError):
            doc = {}
    elif not create:
        return {"moved": False, "from": None, "to": to_status, "reason": "no-sidecar"}
    notes = doc.get("notes") if isinstance(doc.get("notes"), dict) else _empty()
    current = notes.get("status")
    if current == to_status:
        return {"moved": False, "from": current, "to": to_status, "reason": "already"}
    if current is not None and _STATUS_ORDER[to_status] < _STATUS_ORDER[current]:
        return {"moved": False, "from": current, "to": to_status, "reason": "backwards"}
    stamped = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    notes["status"] = to_status
    notes["edit_log"] = [
        *(notes.get("edit_log") or []),
        {"at": stamped, "by": author, "fields": ["status"]},
    ]
    doc.setdefault("experiment_id", eid)
    doc["notes"] = notes
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"moved": True, "from": current, "to": to_status}
