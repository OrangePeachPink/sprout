"""Identity resolution — THE one implementation (ADR-0038 §3/§4).

    resolve_plant(device_id, channel, at_time) -> plant_id | None

Every consumer resolves through this: dashboard, fleet polling, Home, tier queries,
and **templates via the payload**. A template, a SQL query, a JS fragment or a notebook
that maps ``(device, channel) -> plant`` is a *second implementation* and is a defect,
however small (ADR-0038 §3). Templates may **consume** a resolved identity; they may
never **compute** one.

The defect this forecloses (ADR-0038 §6 requires naming it): #1315. The v5 channel-key
migration ran clean on the parse and tier paths, and the live Home still lost all eight
probed plants — because the Home joined cards on the payload's raw ``sensor_id`` inside
``home_template.html``. That join was a second identity path, living where no import
graph reaches, so the host fold could not cover it. One function, consumed everywhere,
is what makes that class structurally impossible rather than merely fixed.

Layer 1 (domain) per the ADR's layer table: this module imports from layer 0 and the
registry only — never from analysis, application or delivery.

**Time is a first-class argument, not a convenience.** The registry is temporal: an
assignment is an interval (``start_ts`` .. ``end_ts``), closed-then-opened on a probe
move (#1335 §3). Asking "who is on this channel" without saying *when* is exactly how a
reading gets attributed to whoever happens to be there now, rather than to whoever was
there when it was taken. ``at_time=None`` means "now" and is a deliberate choice by the
caller, never a default that hides the question.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # pragma: no cover - path surgery, ADR-0038 §5 stage 4
    sys.path.insert(0, str(_HERE))

from registry_model import RegistryModel, load_registry_model  # noqa: E402

__all__ = ["IdentityProjection", "current_projection", "resolve_plant"]


def _covers(assignment, at_time: str | None) -> bool:
    """Does this assignment's interval cover ``at_time``?

    Grandfathered bindings carry ``start_ts=None`` — ADR-0027's "it WAS there, we don't
    know since when" — so an absent start is treated as open-to-the-past rather than as
    a reason to refuse the answer. An absent end means still open.
    """
    if at_time is None:
        return assignment.end_ts is None
    if assignment.start_ts is not None and at_time < assignment.start_ts:
        return False
    return assignment.end_ts is None or at_time < assignment.end_ts


def resolve_plant(
    device_id: str,
    channel: str,
    at_time: str | None = None,
    *,
    model: RegistryModel | None = None,
) -> str | None:
    """The plant bound to ``(device_id, channel)`` at ``at_time``, or None.

    ``at_time`` is an ISO-8601 UTC string; None means the current binding. Returns None
    rather than guessing when nothing covers that instant — an unmapped channel is a
    real state (a declared-but-unplanted port, ADR-0028), not an error to paper over.

    ``model`` is injectable so callers batching many lookups load the registry once;
    omitted, it loads the live registry.
    """
    m = model if model is not None else load_registry_model()
    if at_time is None:
        a = m.current_for_channel(device_id, channel)
        return a.plant_id if a else None

    # A historical instant: scan the intervals. Deleted entities have no binding at any
    # time, so the open-assignment exclusion set applies to closed assignments too.
    dead = m._deleted_ids()
    best = None
    for a in m.assignments:
        if a.device_id != device_id or a.channel != channel:
            continue
        if a.plant_id in dead["plants"] or a.device_id in dead["devices"]:
            continue
        if not _covers(a, at_time):
            continue
        # Overlapping intervals should not exist (assign() closes before it opens), but
        # if one ever does, prefer the latest start — never silently pick the first.
        if best is None or (a.start_ts or "") >= (best.start_ts or ""):
            best = a
    return best.plant_id if best else None


class IdentityProjection:
    """A batch view over one loaded registry — the shape payload builders consume.

    This is how a **template** gets identity without computing it: the payload carries
    already-resolved values produced here, and the surface renders what it is handed.
    """

    def __init__(self, model: RegistryModel | None = None, at_time: str | None = None):
        self.model = model if model is not None else load_registry_model()
        self.at_time = at_time

    def plant_for(self, device_id: str, channel: str) -> str | None:
        """One resolution, same rules as the module function."""
        return resolve_plant(device_id, channel, self.at_time, model=self.model)

    def as_map(self) -> dict[tuple[str, str], str]:
        """``{(device_id, channel): plant_id}`` for every binding covering ``at_time``.

        Channels resolving to nothing are **absent from the map** rather than present
        with a None — a caller iterating it never has to distinguish "unmapped" from
        "mapped to nothing".
        """
        out: dict[tuple[str, str], str] = {}
        seen: set[tuple[str, str]] = set()
        for a in self.model.assignments:
            key = (a.device_id, a.channel)
            if key in seen:
                continue
            seen.add(key)
            pid = self.plant_for(a.device_id, a.channel)
            if pid is not None:
                out[key] = pid
        return out


def current_projection(model: RegistryModel | None = None) -> IdentityProjection:
    """The authoritative *current* projection — the common case, named."""
    return IdentityProjection(model=model, at_time=None)
