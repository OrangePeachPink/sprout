#!/usr/bin/env python3
"""#1335 slice 1 — the authoritative current-registry projection.

**One identity read path.** ADR-0038 §4 names the shape: a layer-1 module whose
public answer is ``resolve_plant(device_id, channel, at_time) -> plant_id | None``,
with every consumer — dashboard, fleet polling, Home, tier queries, and templates via
the payload — resolving through it. The alternative paths are deleted, not deprecated
(that deletion is slice 2; this module is the thing they migrate onto).

It exists because the two-truths condition has a casualty record, not a theory:

- **2026-07-20** — the v5 migration re-keyed the registry to ``chN`` while boards still
  emitted v4 ``sN``. The parse/tier path folded; the Home's own registry join did not,
  and the live Home lost all eight probed plants (ADR-0038's opening incident, #1315).
- **The same week** — the tier's join carried no time bounds, so every historical
  reading inherited *today's* assignment (#1331). Different axis, same root: more than
  one place answered "who is on this channel".

So this module deliberately absorbs BOTH axes rather than fixing them separately —
ADR-0038 §4: *"it is the same work as #1331's interval join and #1335's mapping UI.
Doing it three times separately is how it stays broken."*

**The three things it reconciles**

1. **Token generation** (#1315 / ADR-0036) — v4 ``sN`` and v5 ``chN`` name the same
   physical channel. Both sides of every comparison fold through
   ``parse_v1.canonical_channel``, so the projection is correct in all four
   combinations of (registry migrated or not) x (row v4 or v5).
2. **Time** (#1331 / store contract §3) — identity resolves on the assignment interval
   that COVERS the reading's own timestamp (``start_ts <= t < end_ts``), never on
   today's open assignment. A null ``start_ts`` covers grandfathered history; a null
   ``end_ts`` means still-open.
3. **Which registry** — the temporal model owns identity; the static registry is the
   fallback and the device metadata. A temporal map that covers a fleet the data has
   never seen is REFUSED (the loader falls back to the committed example on a host
   with no local instance, and non-emptiness is not proof).

**Design-QA's constraint (#1335 §7), enforced by construction**: surfaces read the
projection, never the event log. Nothing here exposes the raw assignment list; a
surface that wants "who is on this channel now" gets an answer, not a log to scan.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from parse_v1 import canonical_channel  # noqa: E402  (layer 0, the token fold)


@dataclass(frozen=True)
class Binding:
    """One (device, channel) → plant binding over an interval. Channel is stored
    ALREADY canonical, so no consumer has to remember to fold."""

    device_id: str
    channel: str  # canonical chN
    plant_id: str
    start_ts: str | None = None  # None ⇒ grandfathered: covers all earlier history
    end_ts: str | None = None  # None ⇒ still open
    plant_name: str | None = None
    plant_type: str | None = None
    pot_size: str | None = None
    probe: str | None = None

    def covers(self, at: datetime | None) -> bool:
        """Does this binding cover ``at``? ``None`` asks about *now*, which is the
        open binding. The interval is half-open: ``start <= t < end`` — a closed and
        its successor share a timestamp, so exactly one covers any instant."""
        if at is None:
            return self.end_ts is None
        t = _iso(at)
        if self.start_ts and t < self.start_ts:
            return False
        return not (self.end_ts and t >= self.end_ts)


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Projection:
    """The authoritative current-registry projection — the one identity read path."""

    bindings: tuple[Binding, ...] = ()
    source: str = "empty"  # temporal | static | empty — provenance, never hidden

    def resolve_plant(
        self, device_id: str, channel: str, at_time: datetime | None = None
    ) -> str | None:
        """ADR-0038 §4's public answer. ``None`` when nothing covers — honest, never
        a guess and never today's answer stamped onto history."""
        b = self.binding_for(device_id, channel, at_time)
        return b.plant_id if b else None

    def binding_for(
        self, device_id: str, channel: str, at_time: datetime | None = None
    ) -> Binding | None:
        """The covering binding — the richer answer surfaces need (name, probe…)
        without any of them re-deriving it from events."""
        want = canonical_channel(channel)
        for b in self.bindings:
            if b.device_id == device_id and b.channel == want and b.covers(at_time):
                return b
        return None

    def current(self) -> dict:
        """``{(device_id, canonical_channel): plant_id}`` for right now — the shape
        the existing joins want, already folded."""
        return {
            (b.device_id, b.channel): b.plant_id
            for b in self.bindings
            if b.covers(None)
        }

    def devices(self) -> set:
        return {b.device_id for b in self.bindings}


def _from_temporal(model) -> list[Binding]:
    plants = {p.plant_id: p for p in getattr(model, "plants", [])}
    # #1335 fork 1 (Trellis, Option A + the all-bindings precision): a DELETED entity
    # is gone — `deleted` means "entity + history", and `paused` is the tombstone that
    # keeps history. So a deleted plant resolves to None at EVERY instant, not merely
    # now: "history gone" means gone at all instants.
    #
    # Deliberately NOT open_assignments()' filter, which does two things — excludes
    # dead entities AND narrows to open bindings. Lifting it whole would drop every
    # closed binding and break historical resolution, producing a THIRD behaviour
    # instead of removing one. Only the dead-entity half is lifted; closed bindings
    # stay, so a probe's earlier plant still resolves for readings from that interval.
    #
    # Never-stitch is untouched: deleting a plant does not delete readings. The tier
    # stays board-true; those rows simply resolve to no plant, which is the honest
    # answer once the entity is gone.
    dead = model._deleted_ids() if hasattr(model, "_deleted_ids") else {}
    dead_plants = dead.get("plants", set())
    dead_sensors = dead.get("sensors", set())
    dead_devices = dead.get("devices", set())
    out = []
    for a in getattr(model, "assignments", []):
        if (
            a.plant_id in dead_plants
            or a.sensor_id in dead_sensors
            or a.device_id in dead_devices
        ):
            continue
        p = plants.get(a.plant_id)
        out.append(
            Binding(
                device_id=a.device_id,
                channel=canonical_channel(a.channel),
                plant_id=a.plant_id,
                start_ts=a.start_ts,
                end_ts=a.end_ts,
                plant_name=getattr(p, "pet_name", None) if p else None,
                plant_type=getattr(p, "plant_type", None) if p else None,
                pot_size=getattr(p, "pot_size", None) if p else None,
                probe=a.sensor_id,
            )
        )
    return out


def _from_static(registry) -> list[Binding]:
    out = []
    for dev in getattr(registry, "devices", []) or []:
        for channel in dev.channels or {}:
            p = dev.plant_for(channel)
            if not p:
                continue
            out.append(
                Binding(
                    device_id=dev.device_id,
                    channel=canonical_channel(channel),
                    plant_id=p["plant_id"],
                    plant_name=p.get("plant_name"),
                    plant_type=p.get("plant_type"),
                    pot_size=p.get("pot_size"),
                    probe=dev.probe_for(channel),
                )
            )
    return out


def build_projection(
    model=None, registry=None, devices_in_data: set | None = None
) -> Projection:
    """Reconcile the two registries into one projection.

    The temporal model owns identity when it plausibly describes the real fleet. The
    ghost-fleet guard is the reason for ``devices_in_data``: the temporal loader falls
    back to the committed EXAMPLE on a host with no local instance and returns
    entirely plausible bindings for devices that never logged a row. Non-emptiness is
    not proof, so when the caller can say which devices the data actually contains and
    the temporal map overlaps none of them, the static registry wins and the source
    says so."""
    temporal = _from_temporal(model) if model is not None else []
    static = _from_static(registry) if registry is not None else []
    if (
        temporal
        and devices_in_data
        and not ({b.device_id for b in temporal} & set(devices_in_data))
    ):
        return Projection(tuple(static), "static") if static else Projection()
    if temporal:
        return Projection(tuple(temporal), "temporal")
    if static:
        return Projection(tuple(static), "static")
    return Projection()


def load_projection(
    registry_path: str | Path | None = None, devices_in_data: set | None = None
) -> Projection:
    """Load both registries from the same path and project them. Absent-safe: a
    missing config yields an empty projection (first-run), never a crash."""
    from device_registry import load_registry
    from registry_model import load_model, load_registry_model

    if registry_path:
        model = load_model(str(registry_path))
        registry = load_registry(str(registry_path))
    else:
        model = load_registry_model()
        registry = load_registry()
    return build_projection(model, registry, devices_in_data)


def resolve_plant(
    device_id: str,
    channel: str,
    at_time: datetime | None = None,
    *,
    projection: Projection | None = None,
) -> str | None:
    """ADR-0038 §4's one public function, module-level for the consumers that want it
    that way. Pass a ``projection`` to avoid re-loading per call in a hot path."""
    proj = projection if projection is not None else load_projection()
    return proj.resolve_plant(device_id, channel, at_time)
