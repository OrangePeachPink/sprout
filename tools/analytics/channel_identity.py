#!/usr/bin/env python3
"""The resolved-identity join — one closure for the S1 seam (#1454).

**The seam.** A v5 flash bisects the raw tier: v4 ``sN`` rows sit beside v5 ``chN`` rows
in one query window, and ADR-0036 §4 forbids rewriting the old ones. Any surface that
keys on the *raw* wire token therefore sees one physical channel under two names —
``s1@dev`` and ``ch2@dev`` are the same port — and does the wrong thing with it:

- the card builder groups by raw token, so it renders **two cards** for one plant
  (#1432 — the Home claimed 19 plants for 11);
- an analysis join keyed on the raw token matches only half the window, silently
  **dropping** the other generation (#1435's shape, the quiet inverse).

Same seam, opposite symptoms. This module is the single place both symptoms are cured:
every consuming surface folds a row's ``(device_id, sensor_id)`` through
:func:`parse_v1.canonical_channel` before it groups or joins, so both generations
collapse to one identity **at read time**, with not one stored row rewritten
(never-stitch intact).

**Why one module and not four inline copies.** ``multiplant_history``,
``segment_history`` and ``predict_bridge`` each built this exact index by hand —
loop the registry, ``plant_for(channel)``, key on ``(device_id, canonical_channel)``.
Four copies of a join is four chances for one to drift back to the raw token, which is
exactly how #1315 shipped: the fix lived in some paths and not others. The register (S1)
names this seam; this is its closure.

**Scope, deliberately narrow.** This resolves the *token-generation* seam only — the
``sN``↔``chN`` fold over the static registry, matching what the surfaces already did.
It does **not** unify the static-registry vs temporal-projection question (that is
identity.py / #1335 slice 2); dragging that in here would widen a bug fix into a
model change. The registry is taken duck-typed (anything with ``.devices`` whose entries
expose ``.device_id``, ``.channels`` and ``.plant_for(channel)``) so this module imports
only the fold, never the registry types — one downward dependency, no sideways reach.
"""

from __future__ import annotations

from tools.analytics.parse_v1 import canonical_channel

# The join key type: a device plus its channel folded to the canonical chN namespace.
# Both (device, "s1") and (device, "ch2") produce the SAME key — that identity is the
# whole point, and it is why grouping/joining on this key dedupes the two generations.
ChannelKey = tuple[str, "str | None"]


def channel_key(device_id: str, token: str | None) -> ChannelKey:
    """The canonical join/group key for a row or a registry channel.

    Fold both the wire token and the registry channel through this and they meet:
    ``channel_key(d, "s1") == channel_key(d, "ch2")`` for the port that emits both.
    An unknown token passes through unfolded (``canonical_channel``'s honest default) —
    it still gets a stable key, it simply won't collide with a known channel.
    """
    return (device_id, canonical_channel(token))


def build_plant_index(registry) -> dict[ChannelKey, dict]:
    """Every registered channel → its plant record, keyed canonically.

    One builder, replacing the hand-rolled ``pair_to_plant`` in every analysis surface.
    When a mid-migration registry carries both an ``s1`` key and a ``ch2`` key for one
    channel, both fold to the same :func:`channel_key` and resolve to the same plant —
    so a half-migrated registry is not a source of doubles, which a raw-token index
    could not promise. The value is the **whole** plant dict (``plant_id`` +
    ``plant_name`` + …), so a card can name the plant and an analysis surface can take
    just the id via :func:`resolve_plant_id` — one index, both needs.
    """
    index: dict[ChannelKey, dict] = {}
    for dev in registry.devices:
        for channel in dev.channels or {}:
            plant = dev.plant_for(channel)
            if plant:
                index[channel_key(dev.device_id, channel)] = plant
    return index


def resolve_plant(index: dict[ChannelKey, dict], device_id: str, token: str | None):
    """The plant record on ``(device_id, token)`` — folding the token first — or None.

    ``None`` is a real answer (ADR-0028): an unregistered channel, or a device the
    registry has never seen, resolves to no plant rather than a guessed one.
    """
    return index.get(channel_key(device_id, token))


def resolve_plant_id(
    index: dict[ChannelKey, dict], device_id: str, token: str | None
) -> str | None:
    """The plant *id* on ``(device_id, token)`` — the analysis surfaces' need."""
    plant = resolve_plant(index, device_id, token)
    return plant["plant_id"] if plant else None
