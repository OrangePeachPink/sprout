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
    # #875 card contract: an optional plant photo for the identity block. A LOCAL-only,
    # gitignored path (never committed; EXIF-strip applies if a share path is ever added
    # — same fence as the operator's home coordinates). Absent-safe: the card renders a
    # clean no-photo identity block when None. The path convention / allowed formats /
    # size cap are a grill question; the field itself is decided and additive here.
    photo: str | None = None
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


#: How a channel's pin came to be recorded (#1027 §5.2, Design-QA's sixth need).
#: ``stated`` — she told us this pin. ``recommended`` — she accepted Sprout's default
#: for the board class. The distinction is the same one the cal receipt draws between
#: ``stored`` and ``confirmed``: **a default we assumed and a fact she stated are
#: different claims**, and a record that flattens them makes the surface either
#: overclaim ("your board is wired to GPIO 34") or nag (re-asking what she already told
#: us). Flattening is the easy mistake here because both produce the same integer.
DECLARATION_SOURCES = ("stated", "recommended")


@dataclass
class ChannelDeclaration:
    """What a board declares it *has* — a channel and the pin it is wired to.

    **Trellis's ruling (#1027, Option A), and why it is a regression fix rather than a
    new feature.** ADR-0036 §1 already names *channel* as ``(device_id, port/GPIO)``,
    firmware-owned: the board lane the firmware actually reads. The firmware declares
    channels on **every telemetry row** — a board with zero plants mapped still emits
    ``ch0..ch3``, because a channel is a pin with a probe on it, not a relationship to
    a plant. The static registry's ``devices[].channels{}`` got this right; the temporal
    model replaced it with derived assignments and dropped the declaration on the way.

    **Different owners, different lifetimes.** A channel lives from adoption until the
    board is rewired or retired; an assignment lives from mapping until the probe moves.
    Modelling the longer-lived thing as a by-product of the shorter-lived one is
    backwards, and it is what made the empty-channel teaching state (§5.3)
    *structurally* unrepresentable: you cannot render "this channel has no plant yet"
    if the channel exists only because a plant is on it.

    **Temporal, like every other fact here.** A rewire — *"I took two of the sensors
    off and moved them to my esp32"* — is an **edit event**, not a re-adoption: it
    closes the old declaration and opens a new one, so the wiring reads as history. Same
    machinery as an assignment boundary or a location event, deliberately: one temporal
    pattern in this model, not three.
    """

    device_id: str
    # canonical chN (ADR-0036) — consumed via canonical_channel, never minted here
    channel: str
    pin: int | None = None  # the GPIO; None = declared but pin unknown
    source: str = "stated"
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
    channel_declarations: list[ChannelDeclaration] = field(default_factory=list)

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

    # ------------------------ channel declarations (#1027) ------------------------ #
    def declared_channels(
        self, device_id: str, at_time: str | None = None
    ) -> list[ChannelDeclaration]:
        """This board's declared channels — the open set, or the set in force at
        ``at_time``.

        Resolved on the **covering interval** (``start_ts <= t < end_ts``), the same
        rule identity resolution uses, so a question about the past gets the wiring
        the board actually had then. Answering a historical question with today's
        wiring is the #1331 mistake in another field; no reason to make it twice.
        """
        out = [d for d in self.channel_declarations if d.device_id == device_id]
        if at_time is None:
            out = [d for d in out if d.is_open]
        else:
            out = [
                d
                for d in out
                if (d.start_ts is None or d.start_ts <= at_time)
                and (d.end_ts is None or at_time < d.end_ts)
            ]
        return sorted(out, key=lambda d: d.channel)

    def declared_channel_count(self, device_id: str) -> int:
        """§5.2's gate in one number: *"could have one sensor, could have 4, could have
        6"*. Zero means the board has declared nothing — which is not an adoptable
        board, not a board with no plants."""
        return len(self.declared_channels(device_id))

    def unassigned_channels(self, device_id: str) -> list[ChannelDeclaration]:
        """Declared channels carrying no open assignment — §5.3's calm-empty set.

        **A real query, deliberately.** Design-QA's fourth need: if this were only
        derivable by diffing declared-against-assigned in a template, it would be a
        policy living in a template — the exact thing ADR-0038 §3 forbids and slice 2
        spent its effort removing. The surface asks a question; it does not compute an
        answer.
        """
        return [
            d
            for d in self.declared_channels(device_id)
            if self.current_for_channel(device_id, d.channel) is None
        ]

    def declaration_history(self, device_id: str) -> list[ChannelDeclaration]:
        """Every declaration this board has carried, oldest first — the rewire record.
        A grandfathered first entry has ``start_ts=None`` (it was wired that way; we
        don't know since when) rather than an invented start date."""
        evs = [d for d in self.channel_declarations if d.device_id == device_id]
        return sorted(evs, key=lambda d: (d.start_ts or "", d.channel, d.end_ts or "~"))

    def declare_channels(
        self,
        device_id: str,
        pins: list[int | None],
        *,
        source: str = "stated",
        now: str | None = None,
    ) -> list[ChannelDeclaration]:
        """Declare (or re-declare) this board's channels — the adopt and rewire path.

        ``pins`` is positional: index *i* is channel ``ch{i}``, which is ADR-0036's own
        ordering and the order the firmware emits. The count is therefore implicit in
        the list, exactly as §5.2 frames it — *"could have one sensor, could have 4,
        could have 6"*.

        **A re-declaration is a rewire, not a re-adoption.** Every open declaration is
        closed at ``now`` and a fresh set opened, so the board's wiring reads as history
        and the two-probes-moved-to-the-esp32 case is an edit event. Nothing is
        overwritten and nothing is deleted — the same close-and-open shape as
        :meth:`move_plant` and an assignment boundary.
        """
        ts = now or _utc_now()
        for d in self.channel_declarations:
            if d.device_id == device_id and d.is_open:
                d.end_ts = ts
        fresh = [
            ChannelDeclaration(
                device_id=device_id,
                channel=f"ch{i}",
                pin=pin,
                source=source,
                start_ts=ts,
            )
            for i, pin in enumerate(pins)
        ]
        self.channel_declarations.extend(fresh)
        return fresh

    def location_history(self, plant_id: str) -> list[LocationEvent]:
        """#1188: every spot this plant has occupied, oldest first — the move record
        the editor renders and the confidence re-evaluation reads. A grandfathered
        first entry carries ``start_ts=None`` (it was there; we don't know since
        when) rather than inventing a start."""
        evs = [ev for ev in self.location_events if ev.plant_id == plant_id]
        return sorted(evs, key=lambda e: (e.start_ts or "", e.end_ts or "~"))

    def move_boundaries(self, plant_id: str) -> list[str]:
        """#1188: the timestamps at which this plant CHANGED location — the context
        boundaries. Readings either side of one are not a continuous context (the
        micro-climate changed), so a trend/forecast that spans a boundary is
        comparing two different situations. Consumers gate on these."""
        return [
            ev.end_ts for ev in self.location_history(plant_id) if ev.end_ts is not None
        ]

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
        open_evs = [
            ev for ev in self.location_events if ev.plant_id == plant_id and ev.is_open
        ]
        if not open_evs:
            # #1188: the FIRST move of a grandfathered plant. Its current spot was
            # set without an event (migrated / created directly), so closing "the
            # open event" would close nothing and the old location would vanish from
            # history. Synthesize the prior spot with start_ts=None — the ADR-0027
            # grandfathered convention: it WAS there, we don't know since when — and
            # close it at the move instant. History gains a hole-free chain.
            prior = next(
                (pl.location for pl in self.plants if pl.plant_id == plant_id), None
            )
            if prior:
                self.location_events.append(
                    LocationEvent(
                        plant_id=plant_id, location=prior, start_ts=None, end_ts=ts
                    )
                )
        for ev in open_evs:
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
        # A purged board's wiring history goes with it — the declaration is the
        # board's own fact, so it cannot outlive the board (#1027).
        self.channel_declarations = [
            d for d in self.channel_declarations if d.device_id not in dset
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
            "channel_declarations": [asdict(d) for d in self.channel_declarations],
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
                channel_declarations=[
                    ChannelDeclaration(**_only(ChannelDeclaration, d))
                    for d in doc.get("channel_declarations", [])
                    if isinstance(d, dict)
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
            # #1036: honor the raw off-by-choice flag - a `retired: true` device (the
            # fleet excludes it via _active_served) migrates to `paused`, not `active`,
            # so the tab's truth matches the fleet's and it renders a calm Paused chip.
            lifecycle = "paused" if raw.get("retired") else "active"
            m.devices.append({**raw, "lifecycle": lifecycle})
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
        # #1027: the top-level `sensorless` roster (ADR-0028) — plants present by design
        # but not probed — migrate to first-class Plant entities too, so they're
        # lifecycle-manageable in the registry ("alive · not probed") rather than a
        # Monitor-only block the tab can't see. A plant that is ALSO probed on some
        # channel is already a Plant (a live reading wins) — skip the dup. No assignment
        # is opened: having no open mapping is exactly what "not probed" means.
        for raw in doc.get("sensorless", []):
            if not isinstance(raw, dict):
                continue
            pid = raw.get("plant_id")
            if not pid or pid in plants_seen:
                continue
            plants_seen[pid] = Plant(
                plant_id=pid,
                plant_type=raw.get("plant_type"),
                pet_name=raw.get("plant_name"),
                pot_size=raw.get("pot_size"),
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
    Never raises — a missing/malformed file yields an empty model (calm-empty, the
    first-run signal slice 2 lands on)."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RegistryModel()
    return RegistryModel.from_dict(doc)


# #1029: this file is tools/analytics/registry_model.py, so the repo root is parents[2]
# (parents[1] is tools/ - an off-by-one that pointed _LOCAL at a nonexistent
# tools/config/devices.local.json, so the loader honest-emptied over a fully-mapped
# fleet and a Save would have shadowed it). Matches dashboard.py's _HERE.parents[1].
_REPO = Path(__file__).resolve().parents[2]
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
    # #1188: the move record per plant — the editor renders "moved on X" from this,
    # and a mover's context boundaries are queryable without a second round trip.
    doc["location_history"] = {
        p.plant_id: [
            {"location": ev.location, "start_ts": ev.start_ts, "end_ts": ev.end_ts}
            for ev in model.location_history(p.plant_id)
        ]
        for p in model.plants
        if model.location_history(p.plant_id)
    }
    doc["first_run"] = not (model.plants or model.sensors or model.devices)
    # #921 slice 3 Q2: the server owns id allocation - the client prefills the next
    # number from here instead of computing it (one source of truth, no add-race).
    doc["next_ids"] = {"plant": next_plant_id(model), "sensor": next_sensor_id(model)}
    # #921 slice 5: per-CHANNEL view on each device - the port's occupancy (which sensor
    # is mapped, null = FREE) + its cal tier/provenance. Serves BOTH the s5 cal chip AND
    # the 3b free-port picker (an unmapped sensor's port is chosen from the free ports),
    # one shape. Replaces the raw static `channels` dict with this derived array.
    doc["devices"] = [
        {**d, "channels": _channel_view(model, d)} for d in doc["devices"]
    ]
    return doc


def _channel_view(model: RegistryModel, device: dict) -> list[dict]:
    """Each of a device's ports as ``{channel, sensor_id, cal_tier, provenance}``. Ports
    come from the device's static ``channels{}`` keys (its config port inventory) plus
    any channel that carries an assignment. ``sensor_id`` is the currently-mapped sensor
    or ``None`` (a FREE port - the 3b picker's candidate); cal tier/provenance come from
    the open assignment's referenced profile, else uncalibrated. A deleted entity drops
    out via :meth:`open_assignments`, so its port reads free."""
    dev_id = device.get("device_id")
    static = device.get("channels")
    ports = list(static.keys()) if isinstance(static, dict) else []
    # #1027: declared channels are ports in their own right — that is the whole point
    # of the declaration. Without this a board that has declared four channels and
    # mapped none would render as having no ports at all, which is exactly the
    # empty-channel state (§5.3) failing to be representable.
    declared = {d.channel: d for d in model.declared_channels(dev_id)}
    for ch in declared:
        if ch not in ports:
            ports.append(ch)
    for a in model.assignments:
        if a.device_id == dev_id and a.channel not in ports:
            ports.append(a.channel)
    profiles = {p.profile_id: p for p in model.profiles}
    view: list[dict] = []
    for ch in sorted(ports):
        a = model.current_for_channel(dev_id, ch)
        prof = profiles.get(a.profile_id) if (a and a.profile_id) else None
        view.append(
            {
                "channel": ch,
                "sensor_id": a.sensor_id
                if a
                else None,  # None = free port (3b candidate)
                "cal_tier": prof.tier if prof else "uncalibrated",
                "provenance": prof.provenance if prof else None,
                # #1027 — the board's own facts, beside the registry's meaning.
                # `declared` False on a port that carries an assignment but no
                # declaration is a legitimate reading (a grandfathered board that
                # predates the declaration), not an error: absence stays first-class.
                "declared": ch in declared,
                "pin": declared[ch].pin if ch in declared else None,
                "pin_source": declared[ch].source if ch in declared else None,
            }
        )
    return view


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
    "channel_declarations",
}
_PLANT_ID_RE = re.compile(r"p\d{2,}")
_SENSOR_ID_RE = re.compile(r"s\d{2,}")
# what a plant edit may change - never `plant_id` (canonical, immutable post-save)
_PLANT_FIELDS = (
    "plant_type",
    "pet_name",
    "pot_description",
    "pot_size",
    "location",
    "photo",  # #875: the optional identity-block photo path (local-only, gitignored)
)


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


def _validate_channel_declaration(rec: dict, tag: str, err) -> None:
    """The §5.2 gate: a board must declare its channels to be adoptable (#1027).

    Accepts ``channels: [pin, ...]`` — positional, index *i* being ``ch{i}`` per
    ADR-0036 — or the same list of ``{"pin": int}`` dicts, whichever the surface finds
    natural. A pin may be ``None`` (declared, pin not known yet); the *count* is the
    part §5.2 gates on, because the count is what makes the board a known config.

    Rejects an empty or absent declaration by design. A board that answers but has
    declared nothing is precisely the state the ruling calls non-adoptable, and
    accepting it here would let the record exist in a shape the surface then has to
    apologise for.
    """
    raw = rec.get("channels")
    if raw is None:
        err(
            tag,
            "a board must declare its channels to be adopted — how many probes and "
            "what pins they are wired to (#1027 §5.2). No plants yet is fine; no "
            "pin config is not an adoptable board.",
            "channels",
        )
        return
    if not isinstance(raw, list) or not raw:
        err(tag, "channels must be a non-empty list of pins", "channels")
        return
    source = rec.get("channel_source", "stated")
    if source not in DECLARATION_SOURCES:
        err(
            tag,
            f"channel_source must be one of {DECLARATION_SOURCES} — a default we "
            "assumed and a pin she stated are different claims, and the record has "
            "to keep them apart",
            "channel_source",
        )
    for j, entry in enumerate(raw):
        pin = entry.get("pin") if isinstance(entry, dict) else entry
        if pin is None:
            continue  # declared, pin unknown — legitimate
        if not isinstance(pin, int) or isinstance(pin, bool) or pin < 0:
            err(tag, f"channel {j} pin must be a non-negative GPIO number", "channels")


def _declared_pins(rec: dict) -> list[int | None]:
    """The pin list from an accepted declaration, in channel order."""
    return [
        (entry.get("pin") if isinstance(entry, dict) else entry)
        for entry in (rec.get("channels") or [])
    ]


def _validate_profile_fields(rec: dict, tag: str, err) -> None:
    """Shared profile validation for add/edit (#963).

    The anchor check is the load-bearing one. Higher raw = drier, so a capacitive
    probe's AIR anchor must read higher than its WATER anchor. A wizard that captures
    them in the wrong order — probe into the cup before the air reading — would
    otherwise store an inverted calibration that looks perfectly well-formed and makes
    every downstream band wrong in a way nothing else detects. Refusing here is the
    only place that catches it before it becomes the plant's truth."""
    tier = rec.get("tier")
    if tier is not None and tier not in CAL_TIERS:
        err(tag, f"tier {tier!r} not in {CAL_TIERS}", "tier")
    anchors = rec.get("anchors")
    if anchors is None:
        return
    if not isinstance(anchors, dict):
        err(tag, "anchors must be an object with air/water", "anchors")
        return
    air, water = anchors.get("air"), anchors.get("water")
    for name, val in (("air", air), ("water", water)):
        if val is not None and not isinstance(val, int):
            err(tag, f"anchors.{name} must be a whole raw count", f"anchors.{name}")
    if isinstance(air, int) and isinstance(water, int) and air <= water:
        err(
            tag,
            f"anchors inverted: air {air} must read DRIER (higher raw) than "
            f"water {water} — captured in the wrong order?",
            "anchors",
        )


def apply_operations(
    model: RegistryModel, ops: dict, *, now: str | None = None
) -> dict:
    """Apply a classic-save BATCH (Q10) to the temporal model - the slice-3 seam.

    Shape (all sections optional)::

        {"plants":  {"add": [...], "edit": [...]},
         "sensors": {"add": [...], "edit": [...]},
         "devices": {"add": [{device_id, base_url, channels: [pin,...],
                             channel_source?, board?, name?}],
                     "edit": [...],
                     "rewire": [{device_id, channels: [pin,...], channel_source?}]},
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
    profiles_ops = ops.get("profiles") or {}  # #963: the owner-cal write path
    lifecycle = ops.get("lifecycle") or []

    existing_prof = {p.profile_id for p in model.profiles}
    staged_prof: set[str] = set()
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

    # ---- validate: device adds (#1027 adopt) — a board answering at an address with an
    # id the registry never registered. Needs its self-reported id (free) + a base_url
    # to poll. The id comes FROM the board (#1026 mismatch / discovery), so it's taken
    # as-is, only checked non-empty + not-already-registered; adopting a known id is an
    # error (edit the label instead), not a silent duplicate device row.
    staged_d: set[str] = set()
    for i, rec in enumerate(devices.get("add") or []):
        tag = f"devices.add[{i}]"
        did = (rec.get("device_id") or "").strip()
        if not did:
            err(tag, "a device id is required to adopt a board", "device_id")
        elif did in existing_d or did in staged_d:
            err(tag, f"device {did} is already registered", "device_id")
        elif not (rec.get("base_url") or "").strip():
            err(tag, "a base_url (the board's address) is required", "base_url")
        else:
            # #1027 §5.2, ruled: **adoption REQUIRES a physical-config declaration.**
            # "a new board needs to declare how many probes and what pins they are
            # wired to, or else it isn't a known board config." No-plants-yet is
            # legitimate; no-pin-config is not an adoptable board — so this is a hard
            # gate at the seam, not a nudge on the surface. Enforced here because a
            # surface-only check leaves the API able to mint the unadoptable board
            # the ruling exists to forbid.
            _validate_channel_declaration(rec, tag, err)
            staged_d.add(did)

    known_p = existing_p | staged_p
    known_s = existing_s | staged_s
    known_d = existing_d | staged_d  # adopt-then-map in one batch resolves

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
    # #1027 §5.2: a rewire is an EDIT EVENT, not a re-adoption — "I took two of the
    # sensors off and moved them to my esp32" changes what the board has, and must read
    # as that board's history rather than as a new board. Same declaration gate as
    # adoption: a rewire that declares nothing would leave a board in the very state the
    # ruling forbids, reached by a different door.
    for i, rec in enumerate(devices.get("rewire") or []):
        tag = f"devices.rewire[{i}]"
        if (rec.get("device_id") or "") not in existing_d | staged_d:
            err(tag, f"no such device {rec.get('device_id')!r}", "device_id")
        else:
            _validate_channel_declaration(rec, tag, err)

    # ---- validate: profiles (#963 — the owner-cal record, ratified option 1) -----
    # The host owns cal VALUES; the device NVS slot is the projection (Trellis, #963;
    # Firmware ack). A profile is a first-class reusable object: channels reference it
    # by profile_id and never hold a private copy, so re-characterizing a probe moves
    # every channel that references it together.
    for i, rec in enumerate(profiles_ops.get("add") or []):
        tag = f"profiles.add[{i}]"
        pid = (rec.get("profile_id") or "").strip()
        if not pid:
            err(tag, "profile_id is required", "profile_id")
        elif pid in existing_prof or pid in staged_prof:
            err(tag, f"profile {pid} already exists", "profile_id")
        else:
            staged_prof.add(pid)
        _validate_profile_fields(rec, tag, err)
    for i, rec in enumerate(profiles_ops.get("edit") or []):
        tag = f"profiles.edit[{i}]"
        if (rec.get("profile_id") or "") not in existing_prof:
            err(tag, f"no such profile {rec.get('profile_id')!r}", "profile_id")
        _validate_profile_fields(rec, tag, err)

    # ---- validate: assign refs resolve (a channel already held is a remap, not error)
    for i, mp in enumerate(mappings.get("assign") or []):
        tag = f"mappings.assign[{i}]"
        if (mp.get("plant_id") or "") not in known_p:
            err(tag, f"no such plant {mp.get('plant_id')!r}", "plant_id")
        if (mp.get("sensor_id") or "") not in known_s:
            err(tag, f"no such sensor {mp.get('sensor_id')!r}", "sensor_id")
        if (mp.get("device_id") or "") not in known_d:
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
        "devices_added": 0,
        "channels_declared": 0,
        "rewired": 0,
        "profiles_added": 0,
        "edited": 0,
        "mapped": 0,
        "closed": 0,
        "lifecycle": 0,
        "purged": {"devices": 0, "plants": 0, "sensors": 0, "assignments": 0},
    }
    for rec in devices.get("add") or []:  # #1027 adopt — register the answering board
        entry = {
            "device_id": (rec.get("device_id") or "").strip(),
            "base_url": (rec.get("base_url") or "").strip(),
            "lifecycle": "active",
        }
        if rec.get("name"):
            entry["name"] = rec["name"]  # the mutable human label (#583), optional
        if rec.get("board"):
            entry["board"] = rec["board"]  # board class — what the pinout keys off
        model.devices.append(entry)
        model.declare_channels(  # #1027: the board declares what it HAS, at adoption
            entry["device_id"],
            _declared_pins(rec),
            source=rec.get("channel_source", "stated"),
            now=now,
        )
        applied["devices_added"] += 1
        applied["channels_declared"] += len(rec.get("channels") or [])
    for rec in devices.get("rewire") or []:  # #1027 — close the old set, open the new
        model.declare_channels(
            (rec.get("device_id") or "").strip(),
            _declared_pins(rec),
            source=rec.get("channel_source", "stated"),
            now=now,
        )
        applied["rewired"] += 1
        applied["channels_declared"] += len(rec.get("channels") or [])
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
    for rec in profiles_ops.get("add") or []:
        model.profiles.append(
            Profile(
                profile_id=rec["profile_id"],
                name=rec.get("name") or rec["profile_id"],
                sensor_type=rec.get("sensor_type"),
                anchors=rec.get("anchors"),
                provenance=rec.get("provenance"),
                tier=rec.get("tier") or "uncalibrated",
            )
        )
        applied["profiles_added"] += 1
    for rec in profiles_ops.get("edit") or []:
        prof = next(p for p in model.profiles if p.profile_id == rec["profile_id"])
        for k in ("name", "sensor_type", "anchors", "provenance", "tier"):
            if k in rec:
                setattr(prof, k, rec[k])
        applied["edited"] += 1
    for rec in plants.get("edit") or []:
        p = next(x for x in model.plants if x.plant_id == rec.get("plant_id"))
        for k in _PLANT_FIELDS:
            if k not in rec:
                continue
            # #1188 (the #921 "c" ruling): a LOCATION edit is a MOVE, not a text
            # field write. Route it through move_plant so the old spot CLOSES and a
            # new one opens — history is never lost, and the boundary is queryable
            # by the consumers that must re-evaluate across it (a plant that moved
            # is in a different micro-climate; readings either side are not one
            # continuous context). Every other field is a plain edit.
            if k == "location" and (rec[k] or None) != (p.location or None):
                model.move_plant(p.plant_id, rec[k], now=now)
            else:
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
