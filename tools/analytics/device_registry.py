#!/usr/bin/env python3
"""Multi-device fleet registry (#485, epic #448).

Monitor-all-plants mode stands up 3+ ESP32 boards, each with up to 4 capacitive
channels, all reporting over WiFi. Before N devices' streams can be aggregated into
one view (#486) or de-duplicated on device-owned time (#300), the app has to know
**which devices exist** and **which plant each channel maps to** - otherwise the
streams can't be told apart or attributed. This module is that registry.

It reads a small JSON config describing the fleet: each device's identity (its
`device_id`, matching the telemetry's device-owned identity #278 / capability
descriptor #463) and, per capacitive channel (`s1`..`s4`), the plant on it. The real
fleet - which mirrors the operator's home layout - lives in the gitignored
`config/devices.local.json`; a committed `config/devices.example.json` is the shape
template and the demo/test default.

**The stable contract is this module's API** (`plant_for`, `probe_for`, `all_plants`,
`devices`), not the JSON layout: consumers depend on the functions, so the identity
re-keying (#619) is absorbed here without touching them. The `schema_version: 1` shape
is **ratified** (Trellis 2026-07-03, #583/#300) — including the per-device card-header
fields `name` (friendly identity) and `hostname` (synthetic `.local` name, ADR-0020),
and the guarantee that `devices` list order is the dashboard's first-seen card order.

**Identity re-keying (ADR-0027, Accepted; #619).** `device_id` is the board's
**stable minted id** — the registry key, opaque here (the registry never validates its
format; stable-id-ness is a wire property gated by `schema_version >= 3`, #618).
`name`/`hostname` are the mutable labels over it. A channel binding splits **Channel**
(the board port, the token key) from **Probe** (the physical sticker `s1..s12` in that
port, ADR-0027 §5) — `probe_for` answers "which probe is on this pin". W1 scope is
**labels only**: no time-versioned assignment table, no Site, no moves (ADR-0027 W2+).

Honest attribution: an unknown device or an unassigned channel returns ``None`` - the
registry never invents a plant. A missing or malformed config yields an **empty**
registry (clean offline-first degrade), so the dashboard still shows raw
device/channel streams, just without plant names.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_LOCAL = _REPO / "config" / "devices.local.json"
_EXAMPLE = _REPO / "config" / "devices.example.json"


@dataclass(frozen=True)
class Device:
    """One board in the fleet + its per-channel plant assignments."""

    # #619 (ADR-0027): device_id is the **stable minted id** — the registry key.
    # Opaque here (the registry never validates its format; stable-id-ness is a
    # wire property gated by schema_version >= 3, #618). name/hostname (#592) are
    # the mutable labels over it; renaming edits the label, never this key. A
    # pre-mint / legacy config may still key on a friendly name (bridged by
    # previous_ids/canonical_for, #602) — the key is opaque either way.
    device_id: str
    board: str | None
    label: str | None
    # channel token (the board PORT, s1..s4) -> {"probe": str|None, "plant_id":
    # str, "plant_name": str|None}. #619 splits Channel (the port) from Probe
    # (the physical sticker s1..s12 plugged into it, ADR-0027 §5): the port keys
    # the binding, `probe` is the label answering "which probe is on this pin".
    channels: dict[str, dict] = field(default_factory=dict)
    # The device's served root (#486, e.g. "http://192.168.1.42") - the live view
    # polls its GET /telemetry (#276) when set. None = tethered/serial-only.
    base_url: str | None = None
    # Per-device card-header identity (#583, ADR-0020). `name` is the friendly
    # !name/pretty identity (re-nameable, never a MAC); it falls back to `label`
    # for legacy configs. `hostname` is the synthetic `.local` name - None for a
    # tethered device (the card shows its port instead). Both are display
    # reflections; the device owns the real values (ADR-0020). Distinct from
    # `base_url`, which is an IP, not a hostname.
    name: str | None = None
    hostname: str | None = None
    # Physical placement (#713): where this board sits so the human can find the
    # plant by eye - e.g. "left"/"right" on the ledge. The maintainer named the
    # boards (ESPclassic / C5Official) and told the app which side each is on;
    # `side` carries that. Absent-safe (None when not configured).
    side: str | None = None
    # Identity continuity (#602): device_ids this board reported under BEFORE its
    # current name. Renames mint brand-new identities (no hardware anchor, #188),
    # which orphans history; listing prior ids here lets consumers coalesce a
    # board's whole history into one card AT DISPLAY/GROUPING TIME - raw records
    # are never rewritten (they truthfully say what the board reported then).
    previous_ids: tuple[str, ...] = ()
    # #683: device lifecycle. A pre-launch test rig or a decommissioned board is
    # marked `retired` in the registry so it stops rendering as a live fleet group
    # and drops out of the "N devices · N channels" summary - its data is fully
    # preserved (still in the logs / Diagnostics), just de-emphasized on the glance
    # view. Reversible: clear the flag and it returns to the live fleet.
    retired: bool = False

    def plant_for(self, channel: str) -> dict | None:
        """The plant on a channel: {plant_id, plant_name, plant_type, pot_size}, or
        None if unassigned. #713 leads with the plant, so type/pot_size ride along
        as optional plant-first enrichment - absent-safe (None when not configured)."""
        a = self.channels.get(channel)
        if not isinstance(a, dict) or not a.get("plant_id"):
            return None
        return {
            "plant_id": a["plant_id"],
            "plant_name": a.get("plant_name"),
            "plant_type": a.get("plant_type"),
            "pot_size": a.get("pot_size"),
        }

    def probe_for(self, channel: str) -> str | None:
        """The probe sticker (s1..s12, ADR-0027 §5) plugged into this port, or
        None if unassigned - the "which probe" answer, W1 labels-only (#619).
        A probe carries its own QA/cal history (W2); here it is just the label."""
        a = self.channels.get(channel)
        if not isinstance(a, dict):
            return None
        probe = a.get("probe")
        return probe if isinstance(probe, str) and probe else None


@dataclass(frozen=True)
class Registry:
    """The known fleet - a lookup over devices + their plant assignments."""

    devices: list[Device] = field(default_factory=list)
    # #679 (ADR-0028): plants that are present BY DESIGN but not probed - a tiny
    # pot, a hard rootball, a cactus that doesn't want a spike. First-class "alive,
    # not probed", never degraded / no-signal / error. Each entry: {plant_id,
    # plant_name, plant_type?, pot_size?, reason?}. Empty when none configured
    # (absent-safe) - so a fleet with every plant probed sees no change.
    sensorless: list[dict] = field(default_factory=list)

    def device_ids(self) -> list[str]:
        return [d.device_id for d in self.devices]

    def device(self, device_id: str) -> Device | None:
        for d in self.devices:
            if d.device_id == device_id:
                return d
        return None

    def plant_for(self, device_id: str, channel: str) -> dict | None:
        """The plant on (device, channel), or None if the device/channel is unknown
        or unassigned - never a guess."""
        d = self.device(device_id)
        return d.plant_for(channel) if d else None

    def probe_for(self, device_id: str, channel: str) -> str | None:
        """The probe sticker on (device, channel), or None (#619). Resolves the
        device through ``canonical_for`` so a probe binding survives a legacy
        rename the same way plant attribution does (#602/#604)."""
        d = self.device(self.canonical_for(device_id))
        return d.probe_for(channel) if d else None

    def served_devices(self) -> list[Device]:
        """Devices with a ``base_url`` - the WiFi-polled part of the fleet (#486).
        Empty when the config assigns none, so the live view stays tethered-only."""
        return [d for d in self.devices if d.base_url]

    def canonical_for(self, device_id: str | None) -> str | None:
        """The canonical identity for ``device_id`` (#602): if it is listed in
        some device's ``previous_ids``, that device's current id; otherwise the
        id unchanged (unknown ids are never remapped - no invented lineage).

        Guards, both deterministic and honest:
        - an alias that equals any REGISTERED device_id is ignored - a live
          identity can never be swallowed as someone else's past;
        - if two devices claim the same alias, the first in registry order wins
          (the config's first-seen order is already the ratified tiebreak)."""
        if not device_id:
            return device_id
        live = {d.device_id for d in self.devices}
        if device_id in live:
            return device_id  # a current identity is always itself
        for d in self.devices:  # registry order = first claim wins
            if device_id in d.previous_ids:
                return d.device_id
        return device_id

    def all_plants(self) -> list[dict]:
        """Every assigned plant across the fleet, de-duplicated by plant_id and sorted.

        Each entry carries where it lives: {plant_id, plant_name, device_id, channel}.
        A plant_id assigned on two channels keeps its first (sorted) placement."""
        seen: dict[str, dict] = {}
        for d in self.devices:
            for ch in sorted(d.channels):
                p = d.plant_for(ch)
                if p and p["plant_id"] not in seen:
                    seen[p["plant_id"]] = {
                        "plant_id": p["plant_id"],
                        "plant_name": p.get("plant_name"),
                        "device_id": d.device_id,
                        "channel": ch,
                    }
        return [seen[k] for k in sorted(seen)]

    def sensorless_plants(self) -> list[dict]:
        """The probe-less plants present by design (ADR-0028, #679), sorted by
        plant_id for a stable card order. Excludes any plant_id that IS actually
        probed on some channel - a plant can't be both probed and sensorless, and
        a real reading always wins (honest: never show a live plant as unprobed)."""
        probed = {p["plant_id"] for p in self.all_plants()}
        out: dict[str, dict] = {}
        for s in self.sensorless:
            pid = s.get("plant_id")
            if pid and pid not in probed and pid not in out:
                out[pid] = {
                    "plant_id": pid,
                    "plant_name": s.get("plant_name"),
                    "plant_type": s.get("plant_type"),
                    "pot_size": s.get("pot_size"),
                    "reason": s.get("reason"),
                }
        return [out[k] for k in sorted(out)]


def _device_from_dict(raw: dict) -> Device | None:
    did = raw.get("device_id")
    if not isinstance(did, str) or not did:
        return None  # a device with no identity can't attribute anything - skip it
    channels = raw.get("channels")
    channels = channels if isinstance(channels, dict) else {}
    base_url = raw.get("base_url")
    hostname = raw.get("hostname")
    side = raw.get("side")  # #713: physical placement (left/right)
    label = raw.get("label")
    name = raw.get("name")
    prev = raw.get("previous_ids")
    previous_ids = (
        tuple(x for x in prev if isinstance(x, str) and x)
        if isinstance(prev, list)
        else ()
    )
    return Device(
        device_id=did,
        board=raw.get("board"),
        label=label,
        channels=channels,
        base_url=base_url if isinstance(base_url, str) and base_url else None,
        # friendly name; a legacy config carrying only `label` still populates it
        name=name if isinstance(name, str) and name else label,
        hostname=hostname if isinstance(hostname, str) and hostname else None,
        side=side if isinstance(side, str) and side else None,
        previous_ids=previous_ids,
        retired=bool(raw.get("retired")),  # #683 device lifecycle
    )


def resolve_registry_path(path: str | Path | None = None) -> Path | None:
    """WHICH file ``load_registry`` would read — the same discovery ladder, exposed.

    A tool that both reads and WRITES the registry (the #1315 migration) must operate
    on one resolved path: reading via discovery and then writing via a second, separate
    resolution can silently target a different file than the one the dry-run showed.
    Returns None when no registry exists (`load_registry` yields an empty one)."""
    candidates = [Path(path)] if path is not None else [_LOCAL, _EXAMPLE]
    return next((p for p in candidates if p.exists()), None)


def load_registry(path: str | Path | None = None) -> Registry:
    """The fleet registry, preferring the local config, then the example template.

    ``path`` overrides discovery (used by tests). With no path: the gitignored
    ``config/devices.local.json`` if present, else the committed
    ``config/devices.example.json``, else an **empty** registry. A malformed or
    non-conforming file also yields an empty registry - never raises, so the
    monitor-all view degrades cleanly to raw streams."""
    candidates = [Path(path)] if path is not None else [_LOCAL, _EXAMPLE]
    src = next((p for p in candidates if p.exists()), None)
    if src is None:
        return Registry()
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return Registry()
    if not isinstance(doc, dict) or not isinstance(doc.get("devices"), list):
        return Registry()
    devices = [
        d
        for d in (_device_from_dict(x) for x in doc["devices"] if isinstance(x, dict))
        if d is not None
    ]
    # #679 (ADR-0028): the optional top-level `sensorless` roster - plants present
    # by design but not probed. Absent-safe: a config without it yields [].
    raw_sl = doc.get("sensorless")
    sensorless = (
        [x for x in raw_sl if isinstance(x, dict) and x.get("plant_id")]
        if isinstance(raw_sl, list)
        else []
    )
    return Registry(devices=devices, sensorless=sensorless)
