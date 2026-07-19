"""#875 — the per-plant card payload seam. Proves the locked card contract (grill
night 1): mood-colored frame from the band (never the index), identity block, an
honesty-filtered first-person line, first-class-absent last_watered/next_need, optional
photo, sensorless handling — and that raw never rides on the card.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card_payload import (
    _ELAPSED_CLAIM,
    _RECENT_DRINK,
    build_card,
    load_mood_map,
    load_voice_pool,
    pick_voice_line,
)
from registry_model import Plant

# Load the real design sources — the card must track the canonical files, not a copy.
MOOD = load_mood_map()
VOICE = load_voice_pool()


def _card(plant=None, **kw):
    plant = plant or Plant(plant_id="p01", pet_name="Bernie")
    return build_card(plant, mood_map=MOOD, voice_pool=VOICE, **kw)


# --------------------------------------------------------------------------- #
# the design sources load and are the real ones
# --------------------------------------------------------------------------- #
def test_the_canonical_design_sources_load() -> None:
    assert MOOD.get("moist", {}).get("mood") == "thriving"  # band->mood, from the file
    assert (
        MOOD.get("well watered", {}).get("mood") == "thriving"
    )  # fw level resolves too
    assert "thirsty" in VOICE["byMood"] and "empty" in VOICE["bySurface"]


# --------------------------------------------------------------------------- #
# frame = mood, from the BAND (never the index); carries the token, never raw
# --------------------------------------------------------------------------- #
def test_frame_is_the_mood_colored_state_from_the_band() -> None:
    c = _card(band="Moist")
    assert c["frame"]["mood"] == "thriving"
    assert c["frame"]["token"] == "--band-moist"  # surface paints the frame with this
    assert c["frame"]["motion"] == "breathe"
    assert c["frame"]["band"] == "Moist"
    assert c["band_word"] == "Moist"


def test_raw_is_never_on_the_card() -> None:
    # the contract: raw stays Workbench-side. No key should carry a raw ADC value.
    c = _card(band="Dry")
    flat = str(c)
    assert "raw" not in c
    assert "raw_value" not in flat


def test_a_firmware_level_resolves_the_same_as_the_ui_band() -> None:
    assert _card(band="needs water")["frame"]["mood"] == "thirsty"  # fw alias


# --------------------------------------------------------------------------- #
# identity block
# --------------------------------------------------------------------------- #
def test_identity_block_from_the_registry() -> None:
    p = Plant(
        plant_id="p03",
        pet_name="Fern",
        pot_description="the blue pot",
        location="kitchen windowsill",
        photo="config/photos/p03.jpg",
    )
    ident = _card(p, band="Ideal")["identity"]
    assert ident == {
        "name": "Fern",
        "number": "p03",
        "pot": "the blue pot",
        "location": "kitchen windowsill",
        "photo": "config/photos/p03.jpg",
    }


def test_identity_degrades_gracefully_without_a_name_or_photo() -> None:
    ident = _card(Plant(plant_id="p07"), band="Ideal")["identity"]
    assert ident["name"] == "Plant p07"  # never blank
    assert ident["photo"] is None  # absent-safe


# --------------------------------------------------------------------------- #
# the honesty filter — voice reconciles with the last-watered truth (#875 Q2)
# --------------------------------------------------------------------------- #
def test_an_elapsed_number_line_is_always_filtered_until_templated() -> None:
    # An elapsed-number claim never renders from the static byMood pool (a static
    # line can't be honest by luck). The elapsed copy now lives in byMoodElapsed as
    # {ago} templates (the voice-strings batch) — byMood picks stay number-free.
    for recent in (False, True):
        line, gap = pick_voice_line(
            VOICE, "thriving", plant_id="p01", recent_water=recent
        )
        assert gap is None
        assert "days ago" not in line
        assert not _ELAPSED_CLAIM.search(line)


def test_refreshed_without_a_recent_rewater_speaks_soil_state() -> None:
    # #875 Q1 CLOSED (the voice-strings batch): 'refreshed' now carries an event-free
    # line, so with no recent detected re-water the plant still speaks — but only in
    # soil-state terms, never a drink claim it can't back.
    line, gap = pick_voice_line(VOICE, "refreshed", plant_id="p01", recent_water=False)
    assert gap is None and line is not None
    assert not _RECENT_DRINK.search(line) and not _ELAPSED_CLAIM.search(line)
    c = _card(band="Wet")  # Wet -> refreshed, no last_watered
    assert c["voice"] is not None and c["voice_gap"] is None
    assert not _RECENT_DRINK.search(c["voice"])


def test_a_recent_detected_rewater_unlocks_the_refreshed_line() -> None:
    # #875 Q2 (maintainer's call): the detected re-water is real — a recent one makes
    # "just had a good drink" honest, closing the refreshed gap.
    # the recent-drink line is IN the honest pool now (alongside the event-free
    # variant); the stable pick may land on either — both are honest with a recent
    # detected re-water, and no gap remains.
    pool = VOICE["byMood"]["refreshed"]
    honest = [ln for ln in pool if not _ELAPSED_CLAIM.search(ln)]
    assert any(_RECENT_DRINK.search(ln) for ln in honest)  # the unlock is real
    line, gap = pick_voice_line(VOICE, "refreshed", plant_id="p01", recent_water=True)
    assert gap is None and line in honest
    fresh = {"known": True, "source": "detected", "recent": True, "ago": "3h ago"}
    c = _card(band="Wet", last_watered=fresh, recent_water=True)
    assert c["voice"] in honest and c["voice_gap"] is None


def test_the_voice_pick_is_stable_per_plant_but_varies_across_plants() -> None:
    # content has two safe lines. Same plant -> same line every render (no flicker);
    # different plant ids can land on different lines.
    a1, _ = pick_voice_line(VOICE, "content", plant_id="p01", recent_water=False)
    a2, _ = pick_voice_line(VOICE, "content", plant_id="p01", recent_water=False)
    assert a1 == a2  # stable
    picks = {
        pick_voice_line(VOICE, "content", plant_id=f"p{i:02d}", recent_water=False)[0]
        for i in range(12)
    }
    assert len(picks) > 1  # varies across the fleet


# --------------------------------------------------------------------------- #
# #875 Q2 — the detected re-water as the last-watered cue
# --------------------------------------------------------------------------- #
def test_last_watered_from_a_detected_rewater_is_labelled_and_glanceable() -> None:
    from datetime import datetime, timezone

    from card_payload import last_watered_from_rewater

    now = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    lw = last_watered_from_rewater(
        {"ts": "2026-07-12T12:00:00+00:00", "source": "detected"}, now
    )
    assert lw["known"] is True
    assert lw["source"] == "detected"  # honest: heuristic, never claims a logged event
    assert lw["ago"] == "6d ago"  # the maintainer's glance cue: "it's been 6 days"
    assert lw["recent"] is False  # 6 days > 48h — chip shows it, voice stays soil-state
    assert last_watered_from_rewater(None, now) is None  # absence -> graceful


def test_a_logged_manual_watering_outranks_the_detected_guess() -> None:
    # #1137: a record the operator made is ground truth; a detection is a guess.
    from datetime import datetime, timezone

    from card_payload import resolve_last_watered

    now = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    detected = {"ts": "2026-07-12T12:00:00+00:00", "source": "detected"}  # 6d ago
    manual = {"plant_id": "p01", "source": "manual", "ts": "2026-07-18T09:00:00Z"}  # 3h
    lw = resolve_last_watered(detected, manual, now)
    assert lw["source"] == "manual"  # the logged event wins — it's more recent + real
    assert lw["ago"] == "3h ago"
    # but an OLDER manual log doesn't override a fresher detection (newest wins)
    older_manual = {"plant_id": "p01", "source": "manual", "ts": "2026-07-01T00:00:00Z"}
    assert resolve_last_watered(detected, older_manual, now)["source"] == "detected"


def test_a_glug_and_a_detection_in_window_pair_keeping_the_earlier_time() -> None:
    # #1229 (live-observed): a catch-up glug + a same-watering detection are ONE event.
    # Keep the human FACT (source=manual) but adopt the detector's EARLIER soil time —
    # the glug records a button-press that lagged the soil-change by ~18 min.
    from datetime import datetime, timezone

    from card_payload import resolve_last_watered

    now = datetime(2026, 7, 19, 18, 30, tzinfo=timezone.utc)
    detected = {"ts": "2026-07-19T18:04:00Z", "source": "detected"}  # soil moved
    glug = {"plant_id": "p01", "source": "manual", "ts": "2026-07-19T18:22:00Z"}  # +18m
    lw = resolve_last_watered(detected, glug, now)
    assert lw["source"] == "manual"  # the human fact is preserved
    assert lw["ts"] == "2026-07-19T18:04:00Z"  # ...but the earlier soil time is adopted


def test_a_glug_far_after_the_last_detection_is_a_new_watering() -> None:
    # #1229: if the detector's last re-water was days ago (a plant it didn't catch this
    # time, e.g. the Bromeliad), a glug now is a NEW watering — its own time stands.
    from datetime import datetime, timezone

    from card_payload import resolve_last_watered

    now = datetime(2026, 7, 19, 18, 30, tzinfo=timezone.utc)
    old_detected = {"ts": "2026-07-16T18:00:00Z", "source": "detected"}  # 3 days ago
    glug = {"plant_id": "p07", "source": "manual", "ts": "2026-07-19T18:22:00Z"}  # now
    lw = resolve_last_watered(old_detected, glug, now)
    assert lw["source"] == "manual"
    assert lw["ts"] == "2026-07-19T18:22:00Z"  # the glug's OWN time — a new event


def test_manual_or_detected_alone_and_neither_are_all_graceful() -> None:
    from datetime import datetime, timezone

    from card_payload import resolve_last_watered

    now = datetime(2026, 7, 18, 12, tzinfo=timezone.utc)
    manual = {"plant_id": "p01", "source": "manual", "ts": "2026-07-18T10:00:00Z"}
    assert resolve_last_watered(None, manual, now)["source"] == "manual"  # manual only
    det = {"ts": "2026-07-18T06:00:00+00:00", "source": "detected"}
    assert resolve_last_watered(det, None, now)["source"] == "detected"  # detected only
    assert resolve_last_watered(None, None, now) is None  # neither -> honest absence


def test_a_stale_rewater_shows_the_chip_but_keeps_the_voice_soil_state() -> None:
    old = {"known": True, "source": "detected", "recent": False, "ago": "6d ago"}
    c = _card(band="Wet", last_watered=old, recent_water=False)
    assert c["last_watered"]["ago"] == "6d ago"  # the cue is shown
    # "just had a drink" isn't honest 6 days on — the voice falls back to the
    # event-free soil-state line (the Q1 batch), never the stale drink claim.
    assert c["voice"] is not None
    assert not _RECENT_DRINK.search(c["voice"])


# --------------------------------------------------------------------------- #
# #875 Q3 — the exception lane (air-dry / fault / no-signal off the normal grid)
# --------------------------------------------------------------------------- #
def test_faint_is_an_in_soil_mood_not_an_exception() -> None:
    # #1218 (the #995/#1174 ratified ladder): Faint (old air-dry) is the driest IN-SOIL
    # band — it leads the thirst grid like any mood, it does NOT leave the ladder. The
    # probe-in-air exception (a raw past the off-ladder air anchor) is the #1152 layer.
    c = _card(band="Parched")  # air-dry -> Faint
    assert c["exception"]["is"] is False
    assert c["exception"]["kind"] is None
    assert c["frame"]["mood"] == "faint"  # a real mood on the ladder


def test_a_normal_soil_reading_is_not_an_exception() -> None:
    for b in ("Moist", "Ideal", "Drying", "Dry", "Wet"):
        assert _card(band=b)["exception"]["is"] is False


def test_fault_and_no_signal_are_exceptions() -> None:
    assert _card(band="Dry", surface="fault_sensor")["exception"]["kind"] == "fault"
    assert _card(band=None)["exception"]["kind"] == "no_signal"


# --------------------------------------------------------------------------- #
# first-class absence (ADR-0028)
# --------------------------------------------------------------------------- #
def test_last_watered_and_next_need_are_first_class_absent_by_default() -> None:
    c = _card(band="Moist")
    assert c["last_watered"]["known"] is False and c["last_watered"]["reason"]
    assert c["next_need"]["known"] is False and c["next_need"]["reason"]


def test_a_statistically_real_next_need_is_carried_through_when_injected() -> None:
    real = {
        "known": True,
        "when": "in ~2 days",
        "basis": "forecast",
        "confidence": "low",
    }
    c = _card(band="Drying", next_need=real)
    assert c["next_need"] == real  # the seam surfaces a vetted boundary verbatim


# --------------------------------------------------------------------------- #
# sensorless + no-signal + asleep
# --------------------------------------------------------------------------- #
def test_sensorless_is_alive_not_probed_never_fake_degraded() -> None:
    c = _card(Plant(plant_id="p05", pet_name="Cutting"), sensorless=True)
    assert c["frame"]["state"] == "sensorless"
    assert c["frame"]["mood"] is None and c["frame"]["token"] is None
    assert c["voice"] is None and "not probed" in c["voice_gap"]


def test_no_band_is_a_no_signal_frame_not_a_crash() -> None:
    c = _card(band=None)
    assert c["frame"]["state"] == "no_signal"
    assert c["frame"]["mood"] is None


def test_a_fault_routes_to_bysurface_voice_not_bymood() -> None:
    # seam-map rule: a faulted plant has mood=="" and uses bySurface, never byMood.
    c = _card(band="Dry", surface="fault_sensor")  # surface wins over the band
    assert c["frame"]["state"] == "fault_sensor"
    assert c["frame"]["mood"] is None  # no mood color on a fault
    assert c["voice"] == VOICE["bySurface"]["fault_sensor"][0]
    assert c["voice_gap"] is None


def test_asleep_overlay_stills_motion_and_flags_the_night_state() -> None:
    c = _card(band="Moist", asleep=True)
    assert c["frame"]["asleep"] is True
    assert c["frame"]["motion"] == "none"  # night stills the mark


def test_no_per_card_provisional_chip() -> None:
    # #1039 ruling: cal-provisional is NOT a per-card flag — it's system-level.
    assert "provisional" not in _card(band="Dry")["frame"]


def test_system_cal_state_is_settled_after_the_interior_brackets_ratify() -> None:
    from card_payload import system_cal_state

    # #1039 -> RESOLVED (#995/#1174, #1218): the interior-bracket ratification landed,
    # so the system cal chip is settled — anchors AND interior brackets ratified, with
    # nothing left to clear. No longer derived from per-device cal (the #1153 decouple:
    # a board still lacking verified cal is the cal chain's fact, not this system chip).
    s = system_cal_state()
    assert s["provisional"] is False
    assert s["anchors"] == "ratified"
    assert s["interior_brackets"] == "ratified"
    assert s["clears_when"] is None


# --------------------------------------------------------------------------- #
# next_need gate — statistically real only
# --------------------------------------------------------------------------- #
def test_next_need_is_known_only_on_a_reachable_forecast() -> None:
    from card_payload import next_need_from_forecast

    real = {"thirsty": {"reachable": True, "hours": 40, "hours_lo": 30, "hours_hi": 55}}
    nn = next_need_from_forecast(real)
    assert nn["known"] is True and nn["hours"] == 40
    assert nn["confidence"] == "provisional"


def test_next_need_is_absent_with_a_reason_when_not_statistically_real() -> None:
    from card_payload import next_need_from_forecast

    weak = {"thirsty": {"reachable": False, "reason": "no significant drying"}}
    nn = next_need_from_forecast(weak)
    assert nn["known"] is False and "no significant drying" in nn["reason"]
    assert next_need_from_forecast(None) is None  # no forecast -> generic absence


# --------------------------------------------------------------------------- #
# cards_from_context — the registry bridge + most-thirsty-leads ordering
# --------------------------------------------------------------------------- #
def test_cards_from_context_bridges_identity_and_leads_with_thirst() -> None:
    from card_payload import cards_from_context

    ctx = {
        "devices": [{"device_id": "y9d41p", "cal_provisional": True}],
        "sensors": [
            {  # a comfy plant, low urgency
                "plant_id": "p01",
                "device_id": "y9d41p",
                "plant_name": "static-name",
                "band_fw": "OK",
                "dryness": 0.2,
                "forecast": None,
            },
            {  # the thirstiest — must lead
                "plant_id": "p02",
                "device_id": "y9d41p",
                "band_fw": "needs water",
                "dryness": 0.85,
                "forecast": {"thirsty": {"reachable": True, "hours": 12}},
            },
        ],
        "sensorless": [{"plant_id": "p05", "plant_name": "Cutting"}],
    }
    # the temporal registry knows p01 by a nicer name than the static sensor did
    plants_by_id = {"p01": Plant(plant_id="p01", pet_name="Bernie", location="sill")}
    cards = cards_from_context(
        ctx, plants_by_id=plants_by_id, mood_map=MOOD, voice_pool=VOICE
    )
    assert [c["plant_id"] for c in cards] == ["p02", "p01", "p05"]  # thirsty leads
    assert cards[1]["identity"]["name"] == "Bernie"  # temporal registry won the bridge
    assert cards[1]["identity"]["location"] == "sill"
    assert cards[0]["frame"]["mood"] == "thirsty"
    assert cards[0]["next_need"]["known"] is True  # reachable forecast surfaced
    assert "provisional" not in cards[0]["frame"]  # #1039: no per-card cal chip
    assert cards[2]["frame"]["state"] == "sensorless"  # not-probed trails, alive


def test_manual_watering_reaches_both_probed_and_sensorless_cards() -> None:
    # #1137: the manual log is the ONLY last_watered a sensorless plant can have (no
    # sensor -> no detection), and it must also feed a probed plant's card.
    from datetime import datetime, timezone

    from card_payload import cards_from_context

    ctx = {
        "devices": [],
        "sensors": [
            {"plant_id": "p01", "device_id": "d", "band_fw": "OK", "dryness": 0.3}
        ],
        "sensorless": [{"plant_id": "p05", "plant_name": "Cutting"}],
    }
    manual = {
        "p01": {"plant_id": "p01", "source": "manual", "ts": "2026-07-18T10:00:00Z"},
        "p05": {"plant_id": "p05", "source": "manual", "ts": "2026-07-18T09:00:00Z"},
    }
    cards = cards_from_context(
        ctx,
        plants_by_id={},
        mood_map=MOOD,
        voice_pool=VOICE,
        manual_by_plant=manual,
        now=datetime(2026, 7, 18, 12, tzinfo=timezone.utc),
    )
    by_id = {c["plant_id"]: c for c in cards}
    assert by_id["p01"]["last_watered"]["source"] == "manual"  # probed card
    assert by_id["p05"]["last_watered"]["source"] == "manual"  # sensorless card too
    assert by_id["p05"]["last_watered"]["ago"] == "3h ago"


def test_cards_from_context_routes_a_fault_to_bysurface() -> None:
    from card_payload import cards_from_context

    ctx = {
        "devices": [],
        "sensors": [
            {"plant_id": "p01", "device_id": "d", "sensor_fault": True, "dryness": None}
        ],
    }
    cards = cards_from_context(ctx, plants_by_id={}, mood_map=MOOD, voice_pool=VOICE)
    assert cards[0]["frame"]["state"] == "fault_sensor"
    assert cards[0]["voice"] == VOICE["bySurface"]["fault_sensor"][0]
