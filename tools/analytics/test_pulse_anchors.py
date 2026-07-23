"""#1235 — the pulse envelope spans the anchors so all 7 moods draw.

Two halves: the serve-side bridge (``attach_pulse_anchors`` — profiled per-channel
anchors first, else the ratified per-board-class rails, keyed by the dataset id the
render joins on) and the template wiring (anchor envelope + the bounded-interior
fallback). The board-class floor is what fires on today's fleet, whose registry
profile chain is still empty — a profile-only bridge would have shipped a no-op.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.parse_v1 import BOARD_CLASS_ANCHORS, board_class
from tools.analytics.registry_model import Plant, Profile, RegistryModel, Sensor
from tools.analytics.serve import attach_pulse_anchors

_H = (Path(__file__).resolve().parent / "home_template.html").read_text(
    encoding="utf-8"
)


def _model(anchors=None, board="esp32dev") -> RegistryModel:
    m = RegistryModel(
        plants=[Plant(plant_id="p01")],
        sensors=[Sensor(sensor_id="s01")],
        devices=[{"device_id": "dev1", "base_url": "http://x", "board": board}],
        profiles=[Profile(profile_id="pr1", name="bench", anchors=anchors)],
    )
    m.assign(
        plant_id="p01",
        sensor_id="s01",
        device_id="dev1",
        channel="s1",  # the board PORT — what the wire rows carry
        profile_id="pr1",
    )
    return m


def _ctx() -> dict:
    # the served context shape the bridge reads: dataset id + device + port
    return {"sensors": [{"id": "s1@dev1", "device_id": "dev1", "sensor_id": "s1"}]}


def test_a_profiled_per_channel_anchor_wins() -> None:
    # ADR-0019: per-channel cal beats the board class when the chain has it
    ctx = attach_pulse_anchors(_ctx(), _model(anchors={"air": 3200, "water": 1080}))
    assert ctx["anchors"] == {"s1@dev1": {"air": 3200, "water": 1080}}


def test_no_profile_falls_back_to_the_board_class_rails() -> None:
    # today's fleet: zero profiles in the registry — the ratified per-board-class
    # rails (the firmware board_capability sibling) are what actually fire.
    classic = attach_pulse_anchors(_ctx(), _model(anchors=None))
    assert classic["anchors"]["s1@dev1"] == BOARD_CLASS_ANCHORS["classic"]
    c5 = attach_pulse_anchors(
        _ctx(), _model(anchors=None, board="esp32-c5-devkitc-1 (official)")
    )
    assert c5["anchors"]["s1@dev1"] == BOARD_CLASS_ANCHORS["c5"]


def test_malformed_profiled_anchors_fall_back_never_ship_junk() -> None:
    # inverted or partial profiled anchors -> the class rails, never garbage out
    inverted = attach_pulse_anchors(_ctx(), _model(anchors={"air": 900, "water": 3000}))
    assert inverted["anchors"]["s1@dev1"] == BOARD_CLASS_ANCHORS["classic"]
    partial = attach_pulse_anchors(_ctx(), _model(anchors={"air": 3137}))
    assert partial["anchors"]["s1@dev1"] == BOARD_CLASS_ANCHORS["classic"]


def test_an_unmapped_sensor_still_gets_its_board_rails() -> None:
    # the envelope is a BOARD fact, not an assignment fact — a bench probe with no
    # plant mapped still draws its full board envelope.
    ctx = {"sensors": [{"id": "s9@dev1", "device_id": "dev1", "sensor_id": "s9"}]}
    got = attach_pulse_anchors(ctx, _model(anchors={"air": 3200, "water": 1080}))
    assert got["anchors"]["s9@dev1"] == BOARD_CLASS_ANCHORS["classic"]


def test_board_class_resolution() -> None:
    assert board_class("esp32dev") == "classic"
    assert board_class("esp32-c5-devkitc-1 (official)") == "c5"
    assert board_class("esp32-c5 (KITC-A yellow clone, CH340)") == "c5"
    assert board_class(None) == "classic"  # the project's primary/default class


def test_the_rails_are_the_ratified_995_values() -> None:
    # the one definition (#1152 keys off the SAME rails): the #995/#1174 measured
    # envelope medians — classic water 1052 / air 3137, C5 982 / 2754.
    assert BOARD_CLASS_ANCHORS == {
        "classic": {"air": 3137, "water": 1052},
        "c5": {"air": 2754, "water": 982},
    }


# --------------------------------------------------------------------------- #
# the template wiring — anchor envelope + the honest fallback
# --------------------------------------------------------------------------- #
def test_the_pulse_envelope_reads_the_served_anchors() -> None:
    assert "ctx.anchors" in _H
    assert "anc.water" in _H and "anc.air" in _H  # the full in-soil envelope


def test_all_seven_zones_with_anchors_and_five_without() -> None:
    # with anchors every cut is interior (7 zones = the whole mood ladder); without,
    # the pre-#1235 interior span stays (5 zones — degradation, not invention).
    assert "bounds.slice()" in _H  # all 6 cuts interior under the anchor envelope
    assert "bounds.slice(1, -1)" in _H  # the fallback keeps the old honest span
