#!/usr/bin/env python3
"""#1137 slice 1 — the manual watering journal (the "glug glug" half of the loop).

The maintainer is the release's only operator, and her real waterings are the only
ground truth that exists at meaningful volume. This is the *logged* half of the
watering-event loop: a one-tap "I just poured some water in its mouth" writes a
``source="manual"`` event here, and it becomes the authoritative ``last_watered`` for
that plant — a logged event beats the detected heuristic (band_movement's re-water
guess), because a record the operator actually made is truth, not inference.

**Store:** an append-only JSONL journal at ``config/watering_log.local.jsonl`` — the
same local-operator-data class as ``config/location.local.json`` and the registry's
local config: gitignored, never committed, machine-local. One JSON object per line so a
high-volume stream (many waterings per plant over a season) appends cheaply and is
trivially tailed; a bad line is skipped, never crashes a read (forward-compatible with
fields a later slice adds). The journal is **derived operator input, not telemetry** —
it never touches the raw soil log (ADR-0006: raw stays raw).

**Absence is first-class (ADR-0028):** no journal, or none for a plant, means the card
falls back to the detected re-water (or honest "unknown") exactly as before. Logging is
always optional; nothing here ever blocks the detector or the dashboard.

**Scope (slice 1):** the manual log + read-back only. The detection *confirm/reject*
reaction and the precision-so-far metric ride the 0.8.0 detector arc (#1137 items 2/4);
this is the foundation they will read.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
# Local operator data — gitignored, same class as location.local.json (never committed).
_JOURNAL = _REPO / "config" / "watering_log.local.jsonl"

_PLANT_ID_OK = 64  # a sane cap so a malformed id can't bloat a line


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_manual(
    plant_id: str,
    *,
    ts: datetime | None = None,
    ml: float | None = None,
    note: str | None = None,
    path: str | Path | None = None,
) -> dict:
    """Append one manual watering event and return it. ``source`` is always ``manual``
    (the honest label the last-watered chip distinguishes from ``detected``). ``ml`` and
    ``note`` are optional operator annotations. Raises on a missing/oversized plant_id —
    a watering with no plant is not a loggable event."""
    pid = (plant_id or "").strip()
    if not pid:
        raise ValueError("a plant_id is required to log a watering")
    if len(pid) > _PLANT_ID_OK:
        raise ValueError("plant_id is implausibly long")
    event: dict = {
        "plant_id": pid,
        "source": "manual",
        "ts": _iso(ts or _utc_now()),
    }
    if ml is not None:
        event["ml"] = float(ml)
    if note:
        event["note"] = str(note)[:280]  # a short operator note, never a blob
    dest = Path(path) if path else _JOURNAL
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def load_events(path: str | Path | None = None) -> list[dict]:
    """Every logged event, in file (append) order. A blank or malformed line is skipped
    (forward-compatible + corruption-tolerant), never fatal. Missing journal -> []."""
    src = Path(path) if path else _JOURNAL
    if not src.is_file():
        return []
    out: list[dict] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue  # a torn/partial line never breaks the read
        if isinstance(rec, dict) and rec.get("plant_id") and rec.get("ts"):
            out.append(rec)
    return out


def latest_by_plant(path: str | Path | None = None) -> dict[str, dict]:
    """The most recent manual event per plant_id, keyed by plant_id. 'Most recent' is by
    the event ``ts`` (not file order — a back-dated correction should still win if it is
    the latest wall-clock watering)."""
    latest: dict[str, dict] = {}
    for rec in load_events(path):
        pid = rec["plant_id"]
        prev = latest.get(pid)
        if prev is None or str(rec["ts"]) > str(prev["ts"]):
            latest[pid] = rec
    return latest


# --------------------------------------------------------------------------- #
# #1203 glug phase 2 — the verdict layer (detector QA, append-only)
# --------------------------------------------------------------------------- #
# Design-QA's pre-ruling asks the payload to carry `event_id` + `detection_state`
# per last-watered entry, with the naming left to Data. These are those names.
#
# `event_id` is DERIVED, never allocated: ``<plant_id>@<ISO-minute of the onset>``.
# A detected event has a natural identity — which plant, at which minute — so the id
# survives a full detector rebuild (delete-and-rebuild is doctrine everywhere else in
# the tier; a verdict keyed to a serial number would be orphaned by the first rebuild).
# Same minute-granular convention as the C1 contract's `pass_id`.
#
# A verdict is an APPEND, never an edit: rejecting an event keeps it in the journal
# marked rejected, because the rejection IS the detector's training signal (the issue's
# stated point). Nothing is ever deleted or rewritten — the newest verdict for an
# event_id wins, and the whole verdict history stays readable.

STATES = ("proposed", "confirmed", "rejected")


def event_id_for(plant_id: str, onset) -> str:
    """The derived, rebuild-stable id for a detected watering event."""
    ts = onset if isinstance(onset, str) else _iso(onset)
    return f"{(plant_id or '').strip()}@{ts[:16]}"  # minute granularity


def log_verdict(
    event_id: str,
    state: str,
    *,
    ts: datetime | None = None,
    path: str | Path | None = None,
) -> dict:
    """Append the operator's verdict on a detected event (``confirmed``/``rejected``).
    Append-only: the prior record stays, and a later verdict supersedes an earlier one
    without erasing it."""
    eid = (event_id or "").strip()
    if not eid:
        raise ValueError("an event_id is required to record a verdict")
    if state not in ("confirmed", "rejected"):
        raise ValueError(f"state must be confirmed|rejected, got {state!r}")
    rec = {
        "kind": "verdict",
        "event_id": eid,
        "state": state,
        "ts": _iso(ts or _utc_now()),
    }
    dest = Path(path) if path else _JOURNAL
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def verdicts(path: str | Path | None = None) -> dict:
    """``{event_id: state}`` — the newest verdict per event. Reads the same journal;
    manual watering records (no ``kind``) are ignored here."""
    out: dict[str, str] = {}
    src = Path(path) if path else _JOURNAL
    if not src.is_file():
        return out
    for line in src.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (ValueError, TypeError):
            continue
        if (
            isinstance(rec, dict)
            and rec.get("kind") == "verdict"
            and rec.get("event_id")
            and rec.get("state") in ("confirmed", "rejected")
        ):
            out[rec["event_id"]] = rec["state"]  # file order = newest wins
    return out


def detection_state(event_id: str, path: str | Path | None = None) -> str:
    """``proposed`` until the operator rules on it — never a silent default of
    'confirmed' (an unreviewed detection is not ground truth)."""
    return verdicts(path).get(event_id, "proposed")


def precision_so_far(detected_ids: list[str], path: str | Path | None = None) -> dict:
    """The Workbench-Diagnostics readout: how the detector is actually doing against
    the operator's own rulings. **Both numerals are returned** — a bare percentage
    over 3 events would read like a measurement it is not; the surface is required to
    show ``confirmed / ruled`` alongside any ratio.

    ``precision`` is over RULED events only (confirmed + rejected). Unreviewed
    detections are counted separately as ``proposed`` and never held against the
    detector — absence of a verdict is not evidence of a wrong call (ADR-0028)."""
    v = verdicts(path)
    confirmed = sum(1 for e in detected_ids if v.get(e) == "confirmed")
    rejected = sum(1 for e in detected_ids if v.get(e) == "rejected")
    ruled = confirmed + rejected
    return {
        "detected": len(detected_ids),
        "confirmed": confirmed,
        "rejected": rejected,
        "proposed": len(detected_ids) - ruled,
        "ruled": ruled,
        # None, not 0.0 or 1.0, when nothing has been ruled yet — honest absence
        "precision": (confirmed / ruled) if ruled else None,
    }
