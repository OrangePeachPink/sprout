"""#921 slice 1 — the editable, temporal registry model (the Data foundation).

The read-only ``device_registry`` maps a channel to a plant with **static** fields, so a
re-enable / sensor-swap / plant-move / remap silently rewrites history. Grill Round 2
(Q8) ruled the fix: **record the full tuple at every boundary** — (plant, sensor,
device, profile, timestamps). The mapping stops being a field and becomes an
**append-only log**; the *current* mapping is derived from the open (``end_ts is None``)
assignments, and re-enable / swap / move / remap are all the same operation: close one
assignment, open another. Never-stitch, in the model.

This slice is pure Data — the entities, the temporal log, lifecycle, the profile store,
a JSON round-trip, and a back-compat migration from today's static ``channels{}`` so the
existing read API keeps working unchanged. No surface yet (that's slices 2+, with
Design-QA). ``now`` is injectable everywhere a boundary is stamped, so nothing hangs on
wall-clock at test time; a *migrated* assignment carries ``start_ts=None`` — honest that
we don't know when a grandfathered mapping began, never an invented chronology.

Vocabulary is the grill's: IDs are canonical (``p01`` / ``s01``), user-assignable at
creation and immutable after (enforced by the surface, slices 3+); lifecycle is the
unified ``active | paused | deleted`` (Design-QA renders "Paused"/"Delete").
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# The unified lifecycle (Q3): one concept for plants, sensors, and devices.
# active  — collecting / mapped now
# paused  — temporarily off, history preserved, trivially reversible (NOT a fault)
# deleted — permanently removed (entity + history); a real product function (Q3)
LIFECYCLE_STATES = ("active", "paused", "deleted")

# Calibration tiers (mirrors #951/#957's display vocabulary), carried on a Profile.
CAL_TIERS = ("uncalibrated", "board-cal", "channel-cal")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Plant:
    """A plant is a first-class entity (Q1/Q7), not a channel attribute. ``plant_id``
    (``p01``) is canonical + immutable post-save; the rest are optional enrichment."""

    plant_id: str
    plant_type: str | None = None
    pet_name: str | None = None  # "Bernie" is first-class (Q1)
    pot_description: str | None = None  # "the red pot" (Q7)
    pot_size: str | None = None
    location: str | None = None  # current spot; MOVES are events (see location_events)
    lifecycle: str = "active"


@dataclass
class Sensor:
    """A physical probe, identified by its printed/canonical number ``s01`` (Q1). The
    number is fixed at add-time; ``friendly_name`` is the optional human label."""

    sensor_id: str
    friendly_name: str | None = None
    lifecycle: str = "active"


@dataclass
class Profile:
    """A calibration profile — a first-class, reusable object (Q4/Q5). Channels hold a
    *reference* (``profile_id``), never a private copy, so re-characterizing a profile
    moves every channel that references it together. The unit of raw comparability is
    the **measurement system** = (this profile x a device's ADC), see ``Assignment``."""

    profile_id: str
    name: str
    sensor_type: str | None = None  # capacitive | resistive | dual-probe (Q4)
    anchors: dict | None = None  # {"air": int, "water": int}
    provenance: dict | None = None  # {"who": str, "date": str}
    tier: str = "uncalibrated"


@dataclass
class Assignment:
    """One temporal binding of the full tuple (Q8): a (plant, sensor, device, channel,
    profile) mapping with a start and an optional end. ``end_ts is None`` => the mapping
    is **current**; a closed assignment is history, never mutated. A migrated
    (grandfathered) binding carries ``start_ts=None`` — we don't know when it began."""

    plant_id: str
    sensor_id: str
    device_id: str
    channel: str  # the board port (s1..s4) the sensor is wired to
    profile_id: str | None = None
    start_ts: str | None = None
    end_ts: str | None = None

    @property
    def is_open(self) -> bool:
        return self.end_ts is None


@dataclass
class LocationEvent:
    """A plant move as a timestamped event (Q7): closes one location, opens another, so
    the bench→windowsill migration class is never silently lost. Same machinery as an
    assignment boundary."""

    plant_id: str
    location: str
    start_ts: str | None = None
    end_ts: str | None = None

    @property
    def is_open(self) -> bool:
        return self.end_ts is None


@dataclass
class RegistryModel:
    """The editable registry: entities + the append-only temporal logs. The *current*
    mapping is always derived from the open assignments — there is no separate mutable
    'current' field to drift."""

    plants: list[Plant] = field(default_factory=list)
    sensors: list[Sensor] = field(default_factory=list)
    devices: list[dict] = field(
        default_factory=list
    )  # device dicts (device_registry shape)
    profiles: list[Profile] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    location_events: list[LocationEvent] = field(default_factory=list)

    # --------------------------- derivation (read) --------------------------- #
    def open_assignments(self) -> list[Assignment]:
        """The current mapping: every open (unbounded) assignment, excluding any whose
        plant/sensor/device was deleted (a deleted entity has no current mapping)."""
        dead = self._deleted_ids()
        return [
            a
            for a in self.assignments
            if a.is_open
            and a.plant_id not in dead["plants"]
            and a.sensor_id not in dead["sensors"]
            and a.device_id not in dead["devices"]
        ]

    def current_for_channel(self, device_id: str, channel: str) -> Assignment | None:
        """The open assignment on (device, channel), or None — never a guess."""
        for a in self.open_assignments():
            if a.device_id == device_id and a.channel == channel:
                return a
        return None

    def history_for_plant(self, plant_id: str) -> list[Assignment]:
        """Every assignment a plant held, oldest-first — the derivable series (Q8)."""
        got = [a for a in self.assignments if a.plant_id == plant_id]
        return sorted(got, key=lambda a: a.start_ts or "")

    def _deleted_ids(self) -> dict:
        return {
            "plants": {p.plant_id for p in self.plants if p.lifecycle == "deleted"},
            "sensors": {s.sensor_id for s in self.sensors if s.lifecycle == "deleted"},
            "devices": {
                d.get("device_id")
                for d in self.devices
                if d.get("lifecycle") == "deleted"
            },
        }

    # --------------------------- boundaries (write) -------------------------- #
    def assign(
        self,
        *,
        plant_id: str,
        sensor_id: str,
        device_id: str,
        channel: str,
        profile_id: str | None = None,
        now: str | None = None,
    ) -> Assignment:
        """Open a new mapping, closing any open assignment already on that (device,
        channel) — the atomic boundary that unifies map / remap / swap / re-enable (Q8).
        Both records are timestamped with the same ``now`` so the seam is exact."""
        ts = now or _utc_now()
        existing = self.current_for_channel(device_id, channel)
        if existing is not None:
            existing.end_ts = (
                ts  # close the old binding (history, never mutated further)
            )
        fresh = Assignment(
            plant_id=plant_id,
            sensor_id=sensor_id,
            device_id=device_id,
            channel=channel,
            profile_id=profile_id,
            start_ts=ts,
        )
        self.assignments.append(fresh)
        return fresh

    def close_channel(
        self, device_id: str, channel: str, *, now: str | None = None
    ) -> bool:
        """Close the open assignment on a channel without opening a new one (a disable /
        unmap). Returns True if something was closed."""
        a = self.current_for_channel(device_id, channel)
        if a is None:
            return False
        a.end_ts = now or _utc_now()
        return True

    def move_plant(
        self, plant_id: str, location: str, *, now: str | None = None
    ) -> LocationEvent:
        """Record a plant move as an event (Q7): close the open spot, open the new."""
        ts = now or _utc_now()
        for ev in self.location_events:
            if ev.plant_id == plant_id and ev.is_open:
                ev.end_ts = ts
        fresh = LocationEvent(plant_id=plant_id, location=location, start_ts=ts)
        self.location_events.append(fresh)
        for p in self.plants:
            if p.plant_id == plant_id:
                p.location = location  # mirror the current spot for cheap reads
        return fresh

    def set_lifecycle(self, kind: str, entity_id: str, state: str) -> bool:
        """Transition a plant/sensor/device to active|paused|deleted (Q2/Q3). Returns
        True if an entity matched. Delete is a state here; the log/archive purge is a
        separate mechanism (slice 4) so this stays a pure in-memory transition."""
        if state not in LIFECYCLE_STATES:
            raise ValueError(f"unknown lifecycle state: {state!r}")
        pool = {"plant": self.plants, "sensor": self.sensors}.get(kind)
        if pool is not None:
            for e in pool:
                if getattr(e, f"{kind}_id") == entity_id:
                    e.lifecycle = state
                    return True
            return False
        if kind == "device":
            for d in self.devices:
                if d.get("device_id") == entity_id:
                    d["lifecycle"] = state
                    return True
        return False

    # --------------------------- serialization ------------------------------ #
    def to_dict(self) -> dict:
        return {
            "schema_version": 2,  # #921: the temporal shape (v1 = the static registry)
            "plants": [asdict(p) for p in self.plants],
            "sensors": [asdict(s) for s in self.sensors],
            "devices": self.devices,
            "profiles": [asdict(p) for p in self.profiles],
            "assignments": [asdict(a) for a in self.assignments],
            "location_events": [asdict(e) for e in self.location_events],
        }

    @classmethod
    def from_dict(cls, doc: dict) -> RegistryModel:
        if not isinstance(doc, dict):
            return cls()
        # already the temporal shape -> load directly
        if isinstance(doc.get("assignments"), list) or doc.get("schema_version") == 2:
            return cls(
                plants=[
                    Plant(**_only(Plant, p))
                    for p in doc.get("plants", [])
                    if isinstance(p, dict)
                ],
                sensors=[
                    Sensor(**_only(Sensor, s))
                    for s in doc.get("sensors", [])
                    if isinstance(s, dict)
                ],
                devices=[d for d in doc.get("devices", []) if isinstance(d, dict)],
                profiles=[
                    Profile(**_only(Profile, p))
                    for p in doc.get("profiles", [])
                    if isinstance(p, dict)
                ],
                assignments=[
                    Assignment(**_only(Assignment, a))
                    for a in doc.get("assignments", [])
                    if isinstance(a, dict)
                ],
                location_events=[
                    LocationEvent(**_only(LocationEvent, e))
                    for e in doc.get("location_events", [])
                    if isinstance(e, dict)
                ],
            )
        # the static (v1) shape -> migrate (grandfather in, start_ts unknown)
        return cls.migrate_static(doc)

    @classmethod
    def migrate_static(cls, doc: dict) -> RegistryModel:
        """Back-compat: derive the temporal model from the static ``devices[].channels``
        (device_registry's shape). Existing mappings grandfather in as OPEN assignments
        with ``start_ts=None`` — honest that we don't know when they began. The read API
        (plant_for/etc.) then works unchanged off ``open_assignments``."""
        m = cls()
        plants_seen: dict[str, Plant] = {}
        sensors_seen: dict[str, Sensor] = {}
        for raw in doc.get("devices", []):
            if not isinstance(raw, dict) or not raw.get("device_id"):
                continue
            did = raw["device_id"]
            m.devices.append({**raw, "lifecycle": "active"})
            channels = (
                raw.get("channels") if isinstance(raw.get("channels"), dict) else {}
            )
            for ch, a in channels.items():
                if not isinstance(a, dict) or not a.get("plant_id"):
                    continue
                pid = a["plant_id"]
                if pid not in plants_seen:
                    plants_seen[pid] = Plant(
                        plant_id=pid,
                        plant_type=a.get("plant_type"),
                        pet_name=a.get("plant_name"),
                        pot_size=a.get("pot_size"),
                    )
                probe = a.get("probe")  # the physical sensor sticker (#619), if any
                sid = probe or f"{did}:{ch}"  # fall back to a device:channel key
                if sid not in sensors_seen:
                    sensors_seen[sid] = Sensor(sensor_id=sid, friendly_name=probe)
                m.assignments.append(
                    Assignment(
                        plant_id=pid,
                        sensor_id=sid,
                        device_id=did,
                        channel=ch,
                        start_ts=None,  # grandfathered — unknown origin, never invented
                    )
                )
        m.plants = list(plants_seen.values())
        m.sensors = list(sensors_seen.values())
        return m


def _only(cls, raw: dict) -> dict:
    """Keep only the keys ``cls`` accepts — tolerant of extra/future JSON fields."""
    allowed = set(cls.__dataclass_fields__)
    return {k: v for k, v in raw.items() if k in allowed}


def load_model(path: str | Path) -> RegistryModel:
    """Load the registry model from JSON, migrating a static (v1) config on the way.
    Never raises — a missing/malformed file yields an empty model (honest-empty, the
    first-run signal slice 2 lands on)."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RegistryModel()
    return RegistryModel.from_dict(doc)


def save_model(model: RegistryModel, path: str | Path) -> None:
    """Persist the model as pretty JSON (classic batch commit, Q10). Writes the whole
    document atomically-ish via a temp file swap so a crash mid-write can't truncate the
    registry."""
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(
        json.dumps(model.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(p)
