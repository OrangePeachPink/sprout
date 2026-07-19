"""#875 — the per-plant CARD PAYLOAD seam (Data structure half of the Sprout Voice UI).

The locked card contract (2026-07-18 grill, night 1): a plant card is a **mood-colored
frame** (state, never identity) · an **identity block** (name/number, pot descriptor,
location chip, optional photo) · a **band word + first-person line** · **last-watered +
next-need** as graceful-absence placeholders (until the 0.8.0 detected-watering
classifier + validated forecasts) · **raw stays Workbench-side** (never on the card).

This module is the pure, dependency-free seam that turns (a registry ``Plant`` + its
current band + optional forecast) into that card object. It computes NOTHING about the
soil itself — band comes from the existing calibrated-band path, a forecast (where
statistically real) is injected — so it stays a unit-testable formatter, and Design-QA's
Home grid renders the object without re-deriving anything (one truth, ADR-0008).

**Honesty laws it enforces (ADR-0007/§3, ADR-0028):**
- Mood is a 1:1 function of the calibrated *band*, never the 0-100 index (via
  ``mood-band-map.json``); the card carries the ``--band-*`` token, never a raw value.
- Copy is sourced ONLY from ``voice-strings.json`` — no hard-coded lines, no second
  mapping (INCORPORATION.md). The picker never *invents* a line.
- Absence is first-class: ``last_watered`` / ``next_need`` are ``{"known": false,
  "reason": ...}`` structures, never nulls pretending to be data.
- **The voice can't claim what the instrument can't prove.** Until the 0.8.0 watering
  detector exists, a byMood line that asserts a watering *event/time* ("my last drink
  was two days ago") would contradict the honest ``last_watered: unknown`` chip — so the
  picker filters those lines out. Where that empties a mood's pool, the card reports a
  ``voice_gap`` (a named hole for the grill) rather than fabricating a line.
"""

from __future__ import annotations

import json
import re
import zlib
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_COMPONENTS = _REPO / "docs" / "design" / "components"
_MOOD_MAP = _COMPONENTS / "mood-band-map.json"
_VOICE = _COMPONENTS / "voice-strings.json"

# A detected re-water within this many hours is "recent" enough to unlock a recent-drink
# voice line (#875 Q2). Beyond it, the event is still shown on the last-watered chip
# ("~6 days ago") — the maintainer's #1 watering cue — but the voice stays soil-state.
WATERING_RECENT_H = 48.0

# Two classes of watering claim in a byMood line (both are soil-state-independent, so
# they must reconcile with the last-watered truth, not just the band):
#
# _ELAPSED_CLAIM — a line hard-coding a SPECIFIC elapsed time ("my last drink was two
#   days ago"). The number is baked into the copy, so it's honest only by luck. We can't
#   template it from a static pool, so it stays filtered until voice-strings.json makes
#   the number dynamic (a Design-QA enhancement) — flagged, never guessed.
# _RECENT_DRINK — a line asserting a recent-but-UNQUANTIFIED drink ("just had a good
#   drink"). This one IS honest the moment we have a recent detected re-water (#875 Q2,
#   the maintainer's call: the detected event is the #1 watering cue, stop hiding it),
#   so it unlocks when `recent_water` is true.
_ELAPSED_CLAIM = re.compile(
    r"\b(last (drink|water)|(one|two|three|four|five|\d+)\s+(days?|hours?)\s+ago|"
    r"\d+\s*[dh]\s+ago|watered\b.*\bago)\b",
    re.IGNORECASE,
)
_RECENT_DRINK = re.compile(
    r"\b(just (had|been)|had a (good )?drink|just watered)\b", re.IGNORECASE
)


def load_mood_map(path: str | Path | None = None) -> dict:
    """The canonical band→mood map (``mood-band-map.json``), keyed by lowercase UI band
    (``moist``) AND firmware level (``well watered``) so either resolves. Empty on a
    missing/broken file — the card then degrades to a no-mood frame, never crashes."""
    p = Path(path) if path else _MOOD_MAP
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict = {}
    for b in doc.get("bands", []):
        entry = {
            "uiBand": b.get("uiBand"),
            "mood": b.get("mood"),
            "token": b.get("token"),
            "motion": b.get("motion", "none"),
            "diagnostic": bool(b.get("diagnostic")),
        }
        for key in (b.get("uiBand"), b.get("fwLevel")):
            if key:
                out[str(key).strip().lower()] = entry
    return out


def load_voice_pool(path: str | Path | None = None) -> dict:
    """The first-person voice pool (``voice-strings.json``): ``{"byMood": {...},
    "bySurface": {...}}``. Empty on a missing/broken file."""
    p = Path(path) if path else _VOICE
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {"byMood": doc.get("byMood", {}), "bySurface": doc.get("bySurface", {})}


def _absent(reason: str) -> dict:
    """A first-class-absent field (ADR-0028): a reason, not a data-pretending null."""
    return {"known": False, "reason": reason}


def humanize_ago(hours: float) -> str:
    """A glanceable relative time: 'just now' / '18h ago' / '6d ago'. The maintainer's
    watering cue reads at a glance, not as a timestamp."""
    if hours < 1:
        return "just now"
    if hours < 36:
        return f"{round(hours)}h ago"
    return f"{round(hours / 24)}d ago"


def last_watered_from_rewater(rewater: dict | None, now: datetime) -> dict | None:
    """Turn a band_movement DETECTED re-water (``{ts, source:'detected'}``) into a
    last_watered field (#875 Q2): ``{known, source:'detected', ts, hours_ago, ago,
    recent}``. Always labelled ``detected`` — never a logged event (that stays 0.8.0).
    Returns None when there's no detected re-water (→ build_card's graceful absence)."""
    if not isinstance(rewater, dict) or not rewater.get("ts"):
        return None
    try:
        ts = datetime.fromisoformat(str(rewater["ts"]).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    hours_ago = max(0.0, (now - ts).total_seconds() / 3600.0)
    return {
        "known": True,
        "source": rewater.get("source", "detected"),  # honest: heuristic, not logged
        "ts": rewater["ts"],
        "hours_ago": round(hours_ago, 1),
        "ago": humanize_ago(hours_ago),
        "recent": hours_ago <= WATERING_RECENT_H,
    }


def _exception(state: str, diagnostic: bool) -> dict:
    """#875 Q3: is this reading OUTSIDE the normal soil range, so it belongs in the
    exceptions lane rather than the normal thirst grid? Air-dry (the diagnostic band —
    the probe may be out of soil) and hard states (fault / no-signal) are exceptions;
    a normal in-soil reading is not. Keeps the glanceable grid readable — the
    maintainer's point: extremes shouldn't compress the meaningful middle."""
    kind = None
    if state in ("fault_sensor", "fault_pump"):
        kind = "fault"
    elif state == "no_signal":
        kind = "no_signal"
    elif diagnostic:  # air-dry: the mood-band-map diagnostic band (probe may slip)
        kind = "air_dry"
    reasons = {
        "fault": "sensor fault — reading can't be trusted",
        "no_signal": "no recent reading — is it plugged in?",
        "air_dry": "reads air-dry — the probe may be out of soil (check placement)",
    }
    return {"is": kind is not None, "kind": kind, "reason": reasons.get(kind)}


def _stable_index(seed: str, n: int) -> int:
    """A deterministic pick in ``[0, n)`` from a seed — a plant's line stays stable
    across renders (no flicker) while different plants vary. crc32, not ``hash()``
    (salted per-process, would flicker)."""
    return zlib.crc32(seed.encode("utf-8")) % n if n else 0


def _line_ok(line: str, *, recent_water: bool) -> bool:
    """Whether a byMood line is honest to show given the watering truth. An elapsed-time
    claim is never OK from a static pool (needs templating); a recent-drink claim is OK
    only with a recent detected re-water; a pure soil-state line is always OK."""
    if _ELAPSED_CLAIM.search(line):
        return False
    if _RECENT_DRINK.search(line):
        return recent_water
    return True


def pick_voice_line(
    pool: dict, mood: str | None, *, plant_id: str, recent_water: bool = False
) -> tuple[str | None, str | None]:
    """One first-person line for a mood, or ``(None, gap_reason)`` when the honest pool
    is empty. Filters watering claims that would contradict the last-watered truth
    (#875 Q2): elapsed-number lines stay out until templated; recent-drink lines unlock
    on a recent detected re-water. Never invents copy."""
    if not mood:
        return None, "no mood (band absent) — bySurface state applies, not byMood"
    lines = ((pool.get("byMood") or {}).get(mood)) or []
    if not lines:
        return None, f"voice-strings.json has no byMood line for '{mood}'"
    safe = [ln for ln in lines if _line_ok(ln, recent_water=recent_water)]
    if not safe:
        # nothing honest remains — the refreshed case with no recent re-water. Name the
        # hole rather than fabricate; the detected re-water (when recent) unlocks it.
        return None, (
            f"every byMood line for '{mood}' asserts a watering event, and no recent "
            "detected re-water makes one honest — needs an event-free variant"
        )
    return safe[_stable_index(plant_id, len(safe))], None


def _identity(plant) -> dict:
    """The identity block: name / number / pot descriptor / location / optional photo.
    Accepts a ``Plant`` dataclass or a plain dict (the served registry payload shape).
    """

    def g(attr: str):
        if isinstance(plant, dict):
            return plant.get(attr)
        return getattr(plant, attr, None)

    pid = g("plant_id") or ""
    return {
        "name": g("pet_name") or (f"Plant {pid}" if pid else "Unnamed plant"),
        "number": pid,
        "pot": g("pot_description") or g("pot_size"),
        "location": g("location"),
        "photo": g("photo"),  # a local, gitignored path or None (absent-safe)
    }


def _surface_line(
    voice_pool: dict, surface: str, pid: str
) -> tuple[str | None, str | None]:
    """A ``bySurface`` line (fault / empty / loading / onboarding), stable per plant."""
    lines = ((voice_pool.get("bySurface") or {}).get(surface)) or []
    if not lines:
        return None, f"voice-strings.json has no bySurface line for '{surface}'"
    return lines[_stable_index(pid, len(lines))], None


def _frame(**kw) -> dict:
    """A frame with every key present (the surface never guesses a missing one)."""
    base = {
        "band": None,
        "mood": None,
        "token": None,
        "motion": "none",
        "asleep": False,
        "provisional": False,
        "state": "no_signal",
    }
    base.update(kw)
    return base


def build_card(
    plant,
    *,
    band: str | None = None,
    mood_map: dict,
    voice_pool: dict,
    sensorless: bool = False,
    surface: str | None = None,
    asleep: bool = False,
    provisional: bool = False,
    next_need: dict | None = None,
    last_watered: dict | None = None,
    recent_water: bool = False,
) -> dict:
    """Assemble one plant's card payload against the locked #875 contract.

    ``band`` is the current UI band word or firmware level (case-insensitive), or None
    when the plant has no live signal. ``surface`` routes a non-mood state (e.g.
    ``fault_sensor`` / ``fault_pump``) to the ``bySurface`` voice pool instead of
    ``byMood`` (the seam-map's rule: a faulted plant has no mood). ``provisional`` marks
    a band from uncalibrated/provisional cal (the surface says so). ``next_need`` is an
    already-vetted forecast boundary (inject ONLY where statistically real) or None →
    graceful absence. ``last_watered`` is an already-formatted detected-re-water field
    (#875 Q2) or None → graceful absence; ``recent_water`` says that re-water is recent
    enough to unlock a recent-drink voice line. Raw is never included — Workbench-side.
    """
    ident = _identity(plant)
    pid = ident["number"]

    # last_watered: a DETECTED re-water when we have one (#875 Q2, the #1 cue),
    # else first-class-absent. The logged/classified event is still 0.8.0; this is the
    # honest heuristic, always labelled source="detected" by the caller.
    if last_watered is None:
        last_watered = _absent(
            "no watering detected in this window — a logged event arrives with 0.8.0"
        )
    if next_need is None:
        next_need = _absent(
            "no validated forecast yet — a next-need estimate needs the 0.8.0 "
            "detector + a cal'd drying rate"
        )

    diagnostic = False
    if surface:  # a fault / non-mood state — bySurface voice, no mood on the frame
        voice, gap = _surface_line(voice_pool, surface, pid)
        frame = _frame(asleep=asleep, state=surface)
    elif sensorless:  # ADR-0028: present by design, not probed — never fake-degraded
        voice = None
        gap = "alive, not probed — no byMood line for the sensorless state"
        frame = _frame(asleep=asleep, state="sensorless")
    else:
        entry = mood_map.get((band or "").strip().lower()) if band else None
        mood = entry["mood"] if entry else None
        diagnostic = bool(entry and entry.get("diagnostic"))  # air-dry (#875 Q3)
        voice, gap = pick_voice_line(
            voice_pool, mood, plant_id=pid, recent_water=recent_water
        )
        frame = _frame(
            band=entry["uiBand"] if entry else None,
            mood=mood,
            token=entry["token"] if entry else None,
            motion="none" if asleep else (entry["motion"] if entry else "none"),
            asleep=asleep,
            provisional=provisional,
            state="live" if entry else "no_signal",
        )

    return {
        "plant_id": pid,
        "identity": ident,
        # mood-colored FRAME — state, never identity (the color-roles charter)
        "frame": frame,
        "voice": voice,  # one first-person line (honesty-filtered), or None
        "voice_gap": gap,  # why voice is None — a named hole, never a fabricated line
        "band_word": frame["band"],  # the plain band word (raw stays Workbench-side)
        "last_watered": last_watered,  # detected re-water (#875 Q2) or absent
        "next_need": next_need,  # absent, or an injected statistically-real boundary
        "exception": _exception(frame["state"], diagnostic),  # #875 Q3 lane
    }


# --------------------------------------------------------------------------- #
# composition — turn a built dashboard context into the Home's ordered card list
# --------------------------------------------------------------------------- #
def next_need_from_forecast(forecast: dict | None) -> dict | None:
    """Map a ``forecast_payload``'s ``thirsty`` ETA to a next_need field — surfaced as
    KNOWN only where **statistically real** (a significant drying fit, so ``reachable``
    is true). Otherwise first-class-absent with the forecast's own reason. None when no
    forecast exists at all (``build_card`` then supplies the generic absence)."""
    if not forecast:
        return None
    thirsty = forecast.get("thirsty") or {}
    if thirsty.get("reachable") and thirsty.get("hours") is not None:
        return {
            "known": True,
            "hours": thirsty["hours"],
            "hours_lo": thirsty.get("hours_lo"),
            "hours_hi": thirsty.get("hours_hi"),
            "basis": "forecast (significant drying fit)",
            "confidence": "provisional",  # honest: pre-cal, the rate is provisional
        }
    reason = thirsty.get("reason") or "no significant drying trend yet"
    return _absent(f"forecast not reliable yet — {reason}")


def _plant_for(pid, sensor: dict, plants_by_id: dict):
    """The richest identity available for a plant id: the temporal registry ``Plant``
    (name/pot/location/photo) if present, else a dict from the live sensor's static
    fields — so the card is never blank just because the temporal registry lags."""
    if pid and pid in plants_by_id:
        return plants_by_id[pid]
    return {
        "plant_id": pid,
        "pet_name": sensor.get("plant_name"),
        "plant_type": sensor.get("plant_type"),
        "pot_size": sensor.get("pot_size"),
    }


def cards_from_context(
    ctx: dict,
    *,
    plants_by_id: dict,
    mood_map: dict,
    voice_pool: dict,
    now: datetime | None = None,
) -> list[dict]:
    """Compose the Home's card list from a built dashboard ``context`` (dashboard.py) +
    the temporal registry's plants. This is the bridge the seam-map flagged: live
    band/mood/forecast come from ``ctx['sensors']`` (the static-registry card path),
    rich identity from ``plants_by_id`` (the temporal registry). Most-thirsty leads."""
    now = now or datetime.now(timezone.utc)
    prov = {
        d.get("device_id"): bool(d.get("cal_provisional"))
        for d in ctx.get("devices", [])
    }
    # #875 Q2: the DETECTED re-water per plant (band_movement heuristic), by plant.
    rewater = {
        e.get("plant_id"): e.get("rewater")
        for e in ctx.get("band_history", [])
        if e.get("plant_id") and e.get("rewater")
    }
    cards: list[dict] = []
    for s in ctx.get("sensors", []):
        pid = s.get("plant_id")
        if s.get("sensor_fault"):
            surface, band = "fault_sensor", None
        elif s.get("no_signal") or s.get("unassigned"):
            surface, band = None, None  # a no-signal / unassigned frame, not a mood
        else:
            surface, band = None, s.get("band_fw")
        lw = last_watered_from_rewater(rewater.get(pid), now)
        card = build_card(
            _plant_for(pid, s, plants_by_id),
            band=band,
            surface=surface,
            mood_map=mood_map,
            voice_pool=voice_pool,
            provisional=prov.get(s.get("device_id"), True),
            next_need=next_need_from_forecast(s.get("forecast")),
            last_watered=lw,
            recent_water=bool(lw and lw.get("recent")),
        )
        # the Home's lead signal: the calibrated dryness index (0=wettest..1=driest), a
        # LABELLED index for "who needs water first" — never the raw value.
        card["urgency"] = s.get("dryness")
        # #875 hero: the JOIN KEY to the served context (trajectory dataset id) so
        # the pulse chart can find its series even when no plant is registered
        # (plant_id None). Plumbing, never rendered.
        card["sensor_id"] = s.get("id")
        cards.append(card)
    for sl in ctx.get("sensorless", []):
        pid = sl.get("plant_id")
        card = build_card(
            _plant_for(pid, sl, plants_by_id),
            sensorless=True,
            mood_map=mood_map,
            voice_pool=voice_pool,
        )
        card["urgency"] = None  # a not-probed plant has no urgency to sort on
        card["sensor_id"] = None  # not probed — no series to join (first-class-absent)
        cards.append(card)
    # most-thirsty leads (#715/#747): highest dryness first; no-urgency cards trail.
    cards.sort(
        key=lambda c: (c["urgency"] is not None, c["urgency"] or 0.0), reverse=True
    )
    return cards
