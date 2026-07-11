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
import re
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

    def purge(
        self,
        *,
        devices: tuple[str, ...] = (),
        plants: tuple[str, ...] = (),
        sensors: tuple[str, ...] = (),
    ) -> dict:
        """Permanently REMOVE entities + every assignment that references them from the
        model (#921 Q3: delete = entity AND history, out of the records - not a
        lifecycle flag). A purged device also drops from the poll set the moment it
        leaves ``devices`` (device_registry serves only what's in the file). Returns
        removal counts. The filesystem scrub of the device's log rows is a separate step
        (:func:`purge_device_files`, the caller's) - the model stays pure."""
        dset, pset, sset = set(devices), set(plants), set(sensors)
        before_a = len(self.assignments)
        self.assignments = [
            a
            for a in self.assignments
            if a.device_id not in dset
            and a.plant_id not in pset
            and a.sensor_id not in sset
        ]
        self.location_events = [
            e for e in self.location_events if e.plant_id not in pset
        ]
        n_dev = sum(1 for d in self.devices if d.get("device_id") in dset)
        n_pl = sum(1 for p in self.plants if p.plant_id in pset)
        n_se = sum(1 for s in self.sensors if s.sensor_id in sset)
        self.devices = [d for d in self.devices if d.get("device_id") not in dset]
        self.plants = [p for p in self.plants if p.plant_id not in pset]
        self.sensors = [s for s in self.sensors if s.sensor_id not in sset]
        return {
            "devices": n_dev,
            "plants": n_pl,
            "sensors": n_se,
            "assignments": before_a - len(self.assignments),
        }

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


_REPO = Path(__file__).resolve().parents[1]
_LOCAL = _REPO / "config" / "devices.local.json"
_EXAMPLE = _REPO / "config" / "devices.example.json"


def load_registry_model(path: str | Path | None = None) -> RegistryModel:
    """Load the registry model with the SAME config discovery as ``device_registry``
    (#921 slice 2): the gitignored local config, else the committed example, else an
    empty model (the first-run signal). A static (v1) config migrates on read."""
    if path is not None:
        return load_model(path)
    for p in (_LOCAL, _EXAMPLE):
        if p.exists():
            return load_model(p)
    return RegistryModel()


def registry_payload(model: RegistryModel) -> dict:
    """The /registry GET seam for the Plants & Sensors tab (#921 slice 2). The model as
    JSON, plus two derived conveniences the surface needs: the **current mapping** (the
    open assignments, resolved) and a **first_run** flag (an empty registry means this
    tab is the fresh-install setup landing, Q9). DesignQA builds the tab on this."""
    doc = model.to_dict()
    doc["current_mappings"] = [
        {
            "plant_id": a.plant_id,
            "sensor_id": a.sensor_id,
            "device_id": a.device_id,
            "channel": a.channel,
            "profile_id": a.profile_id,
            "start_ts": a.start_ts,
        }
        for a in model.open_assignments()
    ]
    doc["first_run"] = not (model.plants or model.sensors or model.devices)
    # #921 slice 3 Q2: the server owns id allocation - the client prefills the next
    # number from here instead of computing it (one source of truth, no add-race).
    doc["next_ids"] = {"plant": next_plant_id(model), "sensor": next_sensor_id(model)}
    return doc


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


# --------------------------------------------------------------------------- #
# #921 slice 3 — the /registry/apply write path (classic-save a batch of ops)
# --------------------------------------------------------------------------- #
# The top-level keys the temporal model OWNS. A save preserves every other top-level key
# (e.g. `sensorless`, ADR-0028) so committing the registry never silently drops another
# subsystem's data — devices.local.json is shared with device_registry.
_MODEL_KEYS = {
    "schema_version",
    "plants",
    "sensors",
    "devices",
    "profiles",
    "assignments",
    "location_events",
}
_PLANT_ID_RE = re.compile(r"p\d{2,}")
_SENSOR_ID_RE = re.compile(r"s\d{2,}")
# what a plant edit may change - never `plant_id` (canonical, immutable post-save)
_PLANT_FIELDS = ("plant_type", "pet_name", "pot_description", "pot_size", "location")


def _next_numbered(existing: set[str], prefix: str) -> str:
    n = 0
    for x in existing:
        m = re.fullmatch(rf"{prefix}(\d+)", x or "")
        if m:
            n = max(n, int(m.group(1)))
    return f"{prefix}{n + 1:02d}"


def next_plant_id(model: RegistryModel) -> str:
    """The next free ``p0N`` = max existing + 1. Counts paused/deleted too, so a retired
    number is never reused (an id is stable identity). Server owns allocation."""
    return _next_numbered({p.plant_id for p in model.plants}, "p")


def next_sensor_id(model: RegistryModel) -> str:
    """The next free ``s0N`` (never reuses a retired number)."""
    return _next_numbered({s.sensor_id for s in model.sensors}, "s")


def apply_operations(
    model: RegistryModel, ops: dict, *, now: str | None = None
) -> dict:
    """Apply a classic-save BATCH (Q10) to the temporal model - the slice-3 seam.

    Shape (all sections optional)::

        {"plants":  {"add": [...], "edit": [...]},
         "sensors": {"add": [...], "edit": [...]},
         "devices": {"edit": [...]},
         "mappings":{"assign": [{plant_id, sensor_id, device_id, channel, profile_id?}],
                     "close":  [{device_id, channel}]},
         "lifecycle":[{kind, entity_id, state}]}

    ATOMIC + validate-first: the whole batch is checked against the current model before
    anything mutates; on any error nothing changes and structured ``errors`` come back
    for the client to render inline (Q3 - the server is the one validator). ``assign``
    runs the temporal close-old-open-new boundary, so never-stitch stays server-side
    (Q8); a channel already held is not an error (that IS a remap). Returns
    ``{"ok": True, "applied": {...counts}}`` or ``{"ok": False, "errors": [...]}``."""
    ops = ops or {}
    now = now or _utc_now()
    errors: list[dict] = []

    def err(op: str, message: str, field: str | None = None) -> None:
        errors.append({"op": op, "field": field, "message": message})

    plants = ops.get("plants") or {}
    sensors = ops.get("sensors") or {}
    devices = ops.get("devices") or {}
    mappings = ops.get("mappings") or {}
    lifecycle = ops.get("lifecycle") or []

    existing_p = {p.plant_id for p in model.plants}
    existing_s = {s.sensor_id for s in model.sensors}
    existing_d = {d.get("device_id") for d in model.devices}
    staged_p: set[str] = (
        set()
    )  # explicit ids added in THIS batch (intra-batch dup guard)
    staged_s: set[str] = set()

    # ---- validate: adds (explicit id must be well-formed + free; else auto-allocated)
    for i, rec in enumerate(plants.get("add") or []):
        tag = f"plants.add[{i}]"
        pid = (rec.get("plant_id") or "").strip()
        if not pid:
            continue  # server allocates at apply-time — cannot collide
        if not _PLANT_ID_RE.fullmatch(pid):
            err(tag, f"plant id must look like p01, got {pid!r}", "plant_id")
        elif pid in existing_p or pid in staged_p:
            err(tag, f"plant {pid} already exists", "plant_id")
        else:
            staged_p.add(pid)
    for i, rec in enumerate(sensors.get("add") or []):
        tag = f"sensors.add[{i}]"
        sid = (rec.get("sensor_id") or "").strip()  # fixed at add (Q1/Q11), required
        if not sid:
            err(tag, "sensor number is required at add", "sensor_id")
        elif not _SENSOR_ID_RE.fullmatch(sid):
            err(tag, f"sensor id must look like s01, got {sid!r}", "sensor_id")
        elif sid in existing_s or sid in staged_s:
            err(tag, f"sensor {sid} already exists", "sensor_id")
        else:
            staged_s.add(sid)

    known_p = existing_p | staged_p
    known_s = existing_s | staged_s

    # ---- validate: edits target an existing entity (id is immutable — no rename) ----
    for i, rec in enumerate(plants.get("edit") or []):
        if (rec.get("plant_id") or "") not in existing_p:
            err(
                f"plants.edit[{i}]",
                f"no such plant {rec.get('plant_id')!r}",
                "plant_id",
            )
    for i, rec in enumerate(sensors.get("edit") or []):
        if (rec.get("sensor_id") or "") not in existing_s:
            err(
                f"sensors.edit[{i}]",
                f"no such sensor {rec.get('sensor_id')!r}",
                "sensor_id",
            )
    for i, rec in enumerate(devices.get("edit") or []):
        if (rec.get("device_id") or "") not in existing_d:
            err(
                f"devices.edit[{i}]",
                f"no such device {rec.get('device_id')!r}",
                "device_id",
            )

    # ---- validate: assign refs resolve (a channel already held is a remap, not error)
    for i, mp in enumerate(mappings.get("assign") or []):
        tag = f"mappings.assign[{i}]"
        if (mp.get("plant_id") or "") not in known_p:
            err(tag, f"no such plant {mp.get('plant_id')!r}", "plant_id")
        if (mp.get("sensor_id") or "") not in known_s:
            err(tag, f"no such sensor {mp.get('sensor_id')!r}", "sensor_id")
        if (mp.get("device_id") or "") not in existing_d:
            err(tag, f"no such device {mp.get('device_id')!r}", "device_id")
        if not (mp.get("channel") or "").strip():
            err(tag, "a channel (board port) is required", "channel")

    # ---- validate: lifecycle ----
    for i, lc in enumerate(lifecycle):
        tag = f"lifecycle[{i}]"
        kind, eid, state = lc.get("kind"), lc.get("entity_id"), lc.get("state")
        if state not in LIFECYCLE_STATES:
            err(tag, f"state must be one of {LIFECYCLE_STATES}, got {state!r}", "state")
        pool = {"plant": existing_p, "sensor": existing_s, "device": existing_d}.get(
            kind
        )
        if pool is None:
            err(tag, f"kind must be plant|sensor|device, got {kind!r}", "kind")
        elif eid not in pool:
            err(tag, f"no such {kind} {eid!r}", "entity_id")

    # ---- validate: purge (Q3 delete). A delete is irreversible, so an unknown target
    # is an ERROR, never a silent success - a typo'd id must not quietly delete nothing.
    purge = ops.get("purge") or {}
    for kind, pool in (
        ("devices", existing_d),
        ("plants", existing_p),
        ("sensors", existing_s),
    ):
        for eid in purge.get(kind) or []:
            if eid not in pool:
                err(f"purge.{kind}", f"no such {kind[:-1]} {eid!r}", kind)

    if errors:  # atomic: validated-whole-or-nothing, nothing mutated yet
        return {"ok": False, "errors": errors}

    # ---- apply (all validated) — order: entities, then mappings, then lifecycle ----
    applied = {
        "plants_added": 0,
        "sensors_added": 0,
        "edited": 0,
        "mapped": 0,
        "closed": 0,
        "lifecycle": 0,
        "purged": {"devices": 0, "plants": 0, "sensors": 0, "assignments": 0},
    }
    for rec in plants.get("add") or []:
        pid = (rec.get("plant_id") or "").strip() or next_plant_id(model)
        model.plants.append(
            Plant(
                plant_id=pid,
                **{k: rec[k] for k in _PLANT_FIELDS if rec.get(k) is not None},
            )
        )
        applied["plants_added"] += 1
    for rec in sensors.get("add") or []:
        model.sensors.append(
            Sensor(
                sensor_id=(rec.get("sensor_id") or "").strip(),
                friendly_name=rec.get("friendly_name"),
            )
        )
        applied["sensors_added"] += 1
    for rec in plants.get("edit") or []:
        p = next(x for x in model.plants if x.plant_id == rec.get("plant_id"))
        for k in _PLANT_FIELDS:
            if k in rec:
                setattr(p, k, rec[k])
        applied["edited"] += 1
    for rec in sensors.get("edit") or []:
        s = next(x for x in model.sensors if x.sensor_id == rec.get("sensor_id"))
        if "friendly_name" in rec:
            s.friendly_name = rec["friendly_name"]
        applied["edited"] += 1
    for rec in devices.get("edit") or []:
        d = next(x for x in model.devices if x.get("device_id") == rec.get("device_id"))
        if "friendly_name" in rec:
            d["name"] = rec[
                "friendly_name"
            ]  # `name` is the device's mutable label (#583)
        applied["edited"] += 1
    for mp in mappings.get("assign") or []:
        model.assign(
            plant_id=mp["plant_id"],
            sensor_id=mp["sensor_id"],
            device_id=mp["device_id"],
            channel=mp["channel"],
            profile_id=mp.get("profile_id"),
            now=now,
        )
        applied["mapped"] += 1
    for c in mappings.get("close") or []:
        if model.close_channel(c.get("device_id"), c.get("channel"), now=now):
            applied["closed"] += 1
    for lc in lifecycle:
        if model.set_lifecycle(lc["kind"], lc["entity_id"], lc["state"]):
            applied["lifecycle"] += 1
    if purge:  # Q3 delete — LAST, so a same-batch remap can't reference a purged entity
        applied["purged"] = model.purge(
            devices=tuple(purge.get("devices") or []),
            plants=tuple(purge.get("plants") or []),
            sensors=tuple(purge.get("sensors") or []),
        )

    return {"ok": True, "applied": applied}


def save_registry_model(model: RegistryModel, path: str | Path | None = None) -> Path:
    """Commit the model to the LOCAL config (never the committed example), preserving
    every top-level key the temporal model doesn't own (``sensorless``, etc.) so a save
    can't silently drop another subsystem's data. Atomic temp-swap. Returns the path."""
    target = Path(path) if path is not None else _LOCAL
    extra: dict = {}
    if target.exists():
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                extra = {k: v for k, v in raw.items() if k not in _MODEL_KEYS}
        except (OSError, json.JSONDecodeError):
            extra = {}
    doc = {**extra, **model.to_dict()}
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    tmp.replace(target)
    return target


# A per-device segment file: `<device_id>_<YYYYMMDD>_<HHMMSS>.csv[.gz]` (#582). The
# device_id may contain underscores, so the date/time suffix is matched greedily.
_SEGMENT_RE = re.compile(r"^(.+)_\d{8}_\d{6}\.csv(?:\.gz)?$")


def purge_device_files(
    device_ids, *, logdir: str | Path, archive_dir: str | Path | None = None
) -> dict:
    """The filesystem half of a device delete (#921 Q3: history out of the records).

    DELETES the purged devices' active log segments from ``logdir`` (their
    ``<device_id>_*.csv`` files) and REPORTS — never touches — any ``.csv.gz`` segments
    still in the B8 archive. Scrubbing the archive means gz decompress/filter/recompress
    across the read-only data-branch records store; that's deferred design work (a
    v0.8.0 #921-s4 follow-on), so the delete is HONEST about what it reached rather than
    silently leaving archived rows. Irreversible, so scoped tight: only a file whose
    device-id prefix EXACTLY matches a purged id (canonical segment naming) is
    removed. Never raises — a missing dir is an empty result. Returns
    ``{"removed": [paths], "archived_remaining": int}``."""
    ids = set(device_ids)
    removed: list[str] = []
    try:
        for f in Path(logdir).glob("*.csv"):
            m = _SEGMENT_RE.match(f.name)
            if m and m.group(1) in ids:
                try:
                    f.unlink()
                    removed.append(str(f))
                except OSError:
                    continue
    except OSError:
        pass
    archived_remaining = 0
    if archive_dir:
        try:
            for f in Path(archive_dir).glob("*.csv.gz"):
                m = _SEGMENT_RE.match(f.name)
                if m and m.group(1) in ids:
                    archived_remaining += 1
        except OSError:
            pass
    return {"removed": removed, "archived_remaining": archived_remaining}
