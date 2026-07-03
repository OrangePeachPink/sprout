#!/usr/bin/env python3
"""Interior-ambient context fill (#562, ADR-0023 v2) - the host-side layer that
makes a soil row ambient-aware join-free: as ``plants.env`` rows stream past,
remember the freshest interior-ambient reading; when a soil row is written,
fill its reserved ``temp_context_c`` / ``rh_context_pct`` columns from it and
tag the fill with ``context_source`` (payload k=v, per the #559 review - never
a new positional column, so the HotBoxAQ shared core stays byte-identical).

**Two families, fenced (ADR-0023 v2 decision).** Interior ambient - the air the
plant actually lives in - fills only from the two proximity classes:

* ``plant_local`` - a sensor in the plant's own microclimate: on-rig,
  in-canopy, or immediately adjacent. **The class boundary (absorbing the old
  Sage placement question): if the sensor shares the plant's shelf/rig such
  that moving the plant would mean moving the sensor, it is plant-local; if it
  measures the room the plant happens to be in (wall/thermostat/shelf across
  the room), it is room-class.** The current rig's SHT45 at
  ``breadboard_near_esp32`` qualifies as plant_local - maintainer call,
  2026-07-02 (#562).
* ``room`` - smart-home ambient for the room (Zigbee/Thread/Matter/Ecobee/HA).
  **Built here as a seam**: the class exists in the source map and the
  precedence logic (plant_local beats room; room fills when no plant_local is
  fresh), so a future integration (#563) only adds a map entry + its transport
  - no filler changes.

A weather feed never fills interior temperature or humidity - empty is honest;
projected weather is not. The one exception is **pressure** (ADR-0023 §3):
buildings are not pressure vessels, so ``pressure_context_hpa`` may fill from
the exterior family, tagged with its own per-quantity
``pressure_context_source`` (mixed-source rows are the common case - the SHT45
has no pressure - which is exactly why the tags are per-quantity, per the
#559 review). The pressure source is injectable; live weather wiring is a
separate slice (the #367 ingestion doesn't fetch pressure yet, and the logger
is offline-first - R9 - so it must come from a local cache, never a fetch).

**ESP32 die temperature never fills context - structurally, not by
convention** (ADR-0023 §5): the exclusion is a hard identity check that runs
*before* the source map is consulted, so even a misconfigured map entry cannot
turn the chip's self-heated junction temperature into "ambient".

Exactly one source fills a given row's interior columns - never a blend
(ADR-0022 posture). Concurrent sources remain their own plants.env rows,
fully queryable. A context value never travels without its tag.
"""

from __future__ import annotations

import time

# Interior proximity classes (ADR-0023 v2 §1). Only these may fill interior
# temp/RH. "exterior" exists in the vocabulary solely so the pressure tag can
# resolve a class - it is never legal in the interior source map.
INTERIOR_CLASSES = ("plant_local", "room")

# Default interior source map: instrument identity (sensor_model, as emitted on
# the wire) -> (proximity class, context_source tag). One real instance today;
# room-class integrations (#563) add entries here + their transport, nothing
# else. Deployment config may override per ADR-0023 §4 - deliberate and logged,
# never adaptive.
DEFAULT_SOURCE_MAP: dict[str, tuple[str, str]] = {
    "SHT45": ("plant_local", "sht45_onrig"),
}

# The die-temp identity, excluded before any map lookup (ADR-0023 §5). Matches
# the firmware's own emission (#345/#536): a self-heated board proxy, honestly
# labeled - and never ambient.
_DIE_TEMP_SENSOR_IDS = ("esp32_die",)
_DIE_TEMP_CHANNELS = ("die_temp",)
_DIE_TEMP_PAYLOAD_MARK = "cal=uncalibrated_board_proxy"

# Freshness: an interior reading older than this never fills (the plant's air
# NOW, not minutes ago). 120 s = the repo's existing interruption threshold
# (dashboard GAP_THRESHOLD_S), ~4x the default 30 s sweep cadence.
DEFAULT_FRESHNESS_S = 120.0


def _is_die_temp(dev: dict) -> bool:
    return (
        dev.get("sensor_id") in _DIE_TEMP_SENSOR_IDS
        or dev.get("channel") in _DIE_TEMP_CHANNELS
        or _DIE_TEMP_PAYLOAD_MARK in (dev.get("payload") or "")
    )


class ContextFiller:
    """Watches the parsed device stream; answers "what fills this soil row's
    context columns right now?".

    Pure logic, injectable ``clock`` (the house pattern - StallWatchdog,
    RotatingCsv) so freshness expiry unit-tests without waiting on a wall
    clock. ``pressure_source`` is a callable returning ``(hpa, tag)`` or
    ``None`` - the ADR-0023 §3 exception's seam."""

    def __init__(
        self,
        source_map: dict[str, tuple[str, str]] | None = None,
        *,
        freshness_s: float = DEFAULT_FRESHNESS_S,
        clock=time.monotonic,
        pressure_source=None,
    ) -> None:
        the_map = dict(DEFAULT_SOURCE_MAP) if source_map is None else dict(source_map)
        for model, (cls, tag) in the_map.items():
            if cls not in INTERIOR_CLASSES:
                raise ValueError(
                    f"interior source map entry {model!r} declares class {cls!r} - "
                    f"only {INTERIOR_CLASSES} may fill interior context "
                    "(a weather/exterior source in the interior map is exactly "
                    "the projection ADR-0023 fences out)"
                )
            if not tag:
                raise ValueError(f"source map entry {model!r} has an empty tag")
        self._map = the_map
        self._freshness_s = freshness_s
        self._clock = clock
        self._pressure_source = pressure_source
        # (class, tag) -> {"temp_c": str|None, "rh_pct": str|None, "at": float}
        self._latest: dict[tuple[str, str], dict] = {}

    def observe(self, dev: dict) -> None:
        """Feed one parsed device row (DEVICE_COLS dict). Env rows from a mapped
        interior source update the freshest-reading cache; everything else -
        soil rows, unmapped instruments, non-OK quality, and die temp (always,
        checked first) - is ignored."""
        if not str(dev.get("record_type", "")).startswith("plants.env"):
            return
        if _is_die_temp(dev):  # structural exclusion - before ANY map lookup
            return
        entry = self._map.get(dev.get("sensor_model", ""))
        if entry is None:
            return
        if dev.get("quality_flag") != "OK":
            return  # a SUSPECT/NO_SIGNAL reading must not become context
        value = dev.get("value", "")
        channel = dev.get("channel", "")
        if not value:
            return
        slot = self._latest.setdefault(
            entry, {"temp_c": None, "rh_pct": None, "at": None}
        )
        if channel == "ambient_temp":
            slot["temp_c"] = value
        elif channel == "ambient_rh":
            slot["rh_pct"] = value
        else:
            return  # not an interior-ambient quantity (e.g. NIR bands)
        slot["at"] = self._clock()

    def context_for(self) -> dict:
        """The fill for one soil row, as CANONICAL_COLS column values + payload
        tags: ``temp_context_c`` / ``rh_context_pct`` + ``context_source`` from
        the freshest in-class source (plant_local beats room), and
        ``pressure_context_hpa`` + ``pressure_context_source`` from the
        pressure seam. Empty dict = nothing fresh = columns stay honestly
        empty. A value never appears without its tag, and vice versa."""
        out: dict[str, str] = {}
        now = self._clock()
        for cls in INTERIOR_CLASSES:  # precedence: plant_local, then room
            candidates = [
                (slot, tag)
                for (c, tag), slot in self._latest.items()
                if c == cls
                and slot["at"] is not None
                and (now - slot["at"]) <= self._freshness_s
                and (slot["temp_c"] or slot["rh_pct"])
            ]
            if not candidates:
                continue
            # freshest within the class; exactly ONE source fills - never a blend
            slot, tag = max(candidates, key=lambda st: st[0]["at"])
            if slot["temp_c"]:
                out["temp_context_c"] = slot["temp_c"]
            if slot["rh_pct"]:
                out["rh_context_pct"] = slot["rh_pct"]
            out["context_source"] = tag
            break
        if self._pressure_source is not None:
            got = self._pressure_source()
            if got is not None:
                hpa, tag = got
                out["pressure_context_hpa"] = str(hpa)
                out["pressure_context_source"] = tag
        return out
