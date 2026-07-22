#!/usr/bin/env python3
"""The calm discovery set - answering boards we have never registered (#1027 §5.1).

Design's adopt flow needs a *candidate board* to operate on: §5.1 (the discovery card)
-> §5.5 (show-id confirm) -> §5.2 (declaration). This is that candidate source, and it
is deliberately **not** #1026's mismatch alarm.

**Why the distinction is load-bearing, in Design's words.** #1026
(``active_mismatches``) fires when a board answers at an **already-registered**
``base_url`` with a ``device_id`` the registry never heard of - a re-flashed board on a
neighbour's DHCP lease, self-signing an unadopted identity, *"it must surface loudly."*
That is an **alarm**: a possible hijack of a known address. §5.1's card is *"calm, not
an alarm; a guest, never a fault."* Building the calm card on the alarm set would dress
a security-flavoured takeover up as a friendly new board - exactly wrong. So an alarming
device is **excluded** here, by identity, not merely deprioritised.

**What the calm set is.** A ``device_id`` that appears in the telemetry, is **not** in
the registry, and is **not** currently firing a #1026 alarm - a board that logged
legitimately (a serial capture, or a board polled before it was formally adopted, or one
whose registry entry was removed) and is simply waiting to be declared. Each entry
carries what the card and the §5.2 declaration need:

``{device_id, board_class, first_seen, last_seen, channels_seen}``

- ``board`` is the raw board string the telemetry carried - the honest display value,
  never parsed as a token (ADR-0036 §6: the display label must never be machine-read).
- ``board_class`` is the legacy host token from :func:`parse_v1.board_class`
  (``classic`` / ``c5``). **Known gap, flagged on #1027/#1433:** §6 ratified the
  qualified tokens (``esp32-classic`` / ``esp32-c5``) and ``recommended_pins`` keys off
  *those*, but the firmware does not emit ``board_class`` on the wire yet, so the host
  has only the display string and this legacy parse. So the discovery card can show the
  board, but §5.2's one-tap pin default is **gated on the §6 reconciliation** (firmware
  emitting the token, or a single ratified host map) - not on this module. Consuming the
  one existing host vocabulary here rather than authoring a second is the deliberate
  choice; the reconciliation is a Trellis/§6-migration decision, not a quiet bridge.
- ``channels_seen`` are the **canonical** channels the board actually reported, so the
  declaration starts from the real wiring, not a guess.

Read-only over the telemetry: this discovers, it never adopts. Adoption is the
maintainer's one-click through §5.2's ``devices.add`` (which the #1027 structural half
already gates on a channel declaration).
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from parse_v1 import board_class, canonical_channel


def discover_undeclared(
    readings: Iterable,
    registered_ids: set[str],
    *,
    alarm_ids: Iterable[str] = (),
) -> list[dict]:
    """The calm discovery set from telemetry: unregistered, non-alarming boards.

    ``readings`` is any iterable of parsed rows (duck-typed: ``device_id``,
    ``sensor_id``, ``timestamp_utc``, ``board``). ``registered_ids`` is the set of
    ``device_id`` the registry already knows (``{d["device_id"] for d in
    model.devices}``). ``alarm_ids`` is the #1026 mismatch set - excluded by identity so
    a possible hijack is never offered as a calm adoption.

    Returned newest-activity-first (the board that just answered is the one she is most
    likely adopting), each entry a plain dict ready for the payload.
    """
    reg = set(registered_ids)
    alarms = set(alarm_ids)
    seen: dict[str, dict] = {}
    for r in readings:
        dev = getattr(r, "device_id", None)
        if not dev or dev in reg or dev in alarms:
            continue  # registered, or an alarm - neither is a calm candidate
        ts = getattr(r, "timestamp_utc", None)
        if ts is None:
            continue  # no time signal -> not placeable on the "answering recently" axis
        ch = canonical_channel(getattr(r, "sensor_id", None))
        entry = seen.get(dev)
        if entry is None:
            board = getattr(r, "board", None)
            entry = seen[dev] = {
                "device_id": dev,
                "board": board,  # raw display string (never machine-read, §6)
                "board_class": board_class(board),  # legacy token; see the §6 gap
                "first_seen": ts,
                "last_seen": ts,
                "_channels": set(),
            }
        if ts < entry["first_seen"]:
            entry["first_seen"] = ts
        if ts > entry["last_seen"]:
            entry["last_seen"] = ts
        if ch:
            entry["_channels"].add(ch)

    out = []
    for e in sorted(seen.values(), key=lambda e: e["last_seen"], reverse=True):
        out.append(
            {
                "device_id": e["device_id"],
                "board": e["board"],
                "board_class": e["board_class"],
                "first_seen": _iso(e["first_seen"]),
                "last_seen": _iso(e["last_seen"]),
                "channels_seen": sorted(e["_channels"]),
            }
        )
    return out


def _iso(ts) -> str:
    """A timestamp as ISO-8601, whatever aware/naive shape the parser produced."""
    try:
        return ts.isoformat()
    except AttributeError:
        return str(ts)
