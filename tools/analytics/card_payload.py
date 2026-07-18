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
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_COMPONENTS = _REPO / "docs" / "design" / "components"
_MOOD_MAP = _COMPONENTS / "mood-band-map.json"
_VOICE = _COMPONENTS / "voice-strings.json"

# A byMood line that asserts a watering EVENT or elapsed-since-watering TIME — the thing
# we can't know until the 0.8.0 detector. Kept deliberately tight so it only catches
# event/time claims, not soil-state feeling ("getting thirsty", "soaking it in").
_WATERING_CLAIM = re.compile(
    r"\b(last (drink|water)|just (had|been)|days? ago|hours? ago|"
    r"watered .*ago|had a (good )?drink)\b",
    re.IGNORECASE,
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


def _stable_index(seed: str, n: int) -> int:
    """A deterministic pick in ``[0, n)`` from a seed — a plant's line stays stable
    across renders (no flicker) while different plants vary. crc32, not ``hash()``
    (salted per-process, would flicker)."""
    return zlib.crc32(seed.encode("utf-8")) % n if n else 0


def pick_voice_line(
    pool: dict, mood: str | None, *, plant_id: str, last_watered_known: bool
) -> tuple[str | None, str | None]:
    """One first-person line for a mood, or ``(None, gap_reason)`` when the honest pool
    is empty. Filters watering-event claims while ``last_watered`` is unknown (they'd
    contradict the absent last-watered chip). Never invents copy."""
    if not mood:
        return None, "no mood (band absent) — bySurface state applies, not byMood"
    lines = ((pool.get("byMood") or {}).get(mood)) or []
    if not lines:
        return None, f"voice-strings.json has no byMood line for '{mood}'"
    safe = lines
    if not last_watered_known:
        safe = [ln for ln in lines if not _WATERING_CLAIM.search(ln)]
    if not safe:
        # every line for this mood asserts a watering event we can't verify yet. Don't
        # fabricate — name the hole (the refreshed-mood case, a real grill find).
        return None, (
            f"every byMood line for '{mood}' asserts a watering event; none is safe "
            "until the 0.8.0 detector — needs an event-free variant"
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
) -> dict:
    """Assemble one plant's card payload against the locked #875 contract.

    ``band`` is the current UI band word or firmware level (case-insensitive), or None
    when the plant has no live signal. ``surface`` routes a non-mood state (e.g.
    ``fault_sensor`` / ``fault_pump``) to the ``bySurface`` voice pool instead of
    ``byMood`` (the seam-map's rule: a faulted plant has no mood). ``provisional`` marks
    a band from uncalibrated/provisional cal (the surface says so). ``next_need`` is an
    already-vetted forecast boundary (inject ONLY where statistically real) or None →
    graceful absence. Raw is never included — it stays Workbench-side.
    """
    ident = _identity(plant)
    pid = ident["number"]

    # last_watered is first-class-absent for now — no detected-watering stream exists
    # (band_movement.py says so itself); it arrives with the 0.8.0 classifier.
    last_watered = _absent(
        "watering events aren't detected yet — arriving with the 0.8.0 classifier"
    )
    if next_need is None:
        next_need = _absent(
            "no validated forecast yet — a next-need estimate needs the 0.8.0 "
            "detector + a cal'd drying rate"
        )

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
        voice, gap = pick_voice_line(
            voice_pool, mood, plant_id=pid, last_watered_known=False
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
        "last_watered": last_watered,  # first-class-absent (ADR-0028)
        "next_need": next_need,  # absent, or an injected statistically-real boundary
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
    ctx: dict, *, plants_by_id: dict, mood_map: dict, voice_pool: dict
) -> list[dict]:
    """Compose the Home's card list from a built dashboard ``context`` (dashboard.py) +
    the temporal registry's plants. This is the bridge the seam-map flagged: live
    band/mood/forecast come from ``ctx['sensors']`` (the static-registry card path),
    rich identity from ``plants_by_id`` (the temporal registry). Most-thirsty leads."""
    prov = {
        d.get("device_id"): bool(d.get("cal_provisional"))
        for d in ctx.get("devices", [])
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
        card = build_card(
            _plant_for(pid, s, plants_by_id),
            band=band,
            surface=surface,
            mood_map=mood_map,
            voice_pool=voice_pool,
            provisional=prov.get(s.get("device_id"), True),
            next_need=next_need_from_forecast(s.get("forecast")),
        )
        # the Home's lead signal: the calibrated dryness index (0=wettest..1=driest), a
        # LABELLED index for "who needs water first" — never the raw value.
        card["urgency"] = s.get("dryness")
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
        cards.append(card)
    # most-thirsty leads (#715/#747): highest dryness first; no-urgency cards trail.
    cards.sort(
        key=lambda c: (c["urgency"] is not None, c["urgency"] or 0.0), reverse=True
    )
    return cards
