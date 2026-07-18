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
# the honesty filter — voice can't claim what the instrument can't prove
# --------------------------------------------------------------------------- #
def test_voice_line_filters_watering_claims_while_last_watered_unknown() -> None:
    # thriving has two lines; one asserts "my last drink was two days ago" (an event we
    # can't detect yet), one is event-free. The event one must be filtered.
    line, gap = pick_voice_line(
        VOICE, "thriving", plant_id="p01", last_watered_known=False
    )
    assert gap is None
    assert "days ago" not in line
    assert line == "Feeling great today, thanks for asking."


def test_a_mood_with_only_event_lines_reports_a_named_gap_not_a_fabrication() -> None:
    # 'refreshed' has ONE line and it asserts "just had a good drink" — nothing safe
    # remains. The seam must name the hole, never invent copy.
    line, gap = pick_voice_line(
        VOICE, "refreshed", plant_id="p01", last_watered_known=False
    )
    assert line is None
    assert gap and "refreshed" in gap
    c = _card(band="Wet")  # Wet -> refreshed
    assert c["voice"] is None and c["voice_gap"] is not None


def test_when_last_watered_is_known_the_event_line_is_allowed() -> None:
    # forward-looking: once the 0.8.0 detector lands, the richer line is honest again.
    line, gap = pick_voice_line(
        VOICE, "thriving", plant_id="p01", last_watered_known=True
    )
    assert gap is None
    assert line in VOICE["byMood"]["thriving"]  # either line is now fair game


def test_the_voice_pick_is_stable_per_plant_but_varies_across_plants() -> None:
    # content has two safe lines. Same plant -> same line every render (no flicker);
    # different plant ids can land on different lines.
    a1, _ = pick_voice_line(VOICE, "content", plant_id="p01", last_watered_known=False)
    a2, _ = pick_voice_line(VOICE, "content", plant_id="p01", last_watered_known=False)
    assert a1 == a2  # stable
    picks = {
        pick_voice_line(
            VOICE, "content", plant_id=f"p{i:02d}", last_watered_known=False
        )[0]
        for i in range(12)
    }
    assert len(picks) > 1  # varies across the fleet


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


def test_provisional_cal_is_flagged_for_the_surface() -> None:
    assert _card(band="Dry", provisional=True)["frame"]["provisional"] is True


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
    assert cards[0]["frame"]["provisional"] is True  # device cal_provisional bridged
    assert cards[2]["frame"]["state"] == "sensorless"  # not-probed trails, alive


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
