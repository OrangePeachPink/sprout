"""#921 slice 2 — the Plants & Sensors registry tab (read-only + first-run landing).

Parses the served template and pins the surface the grill ruled: a dedicated tab (its
own, not Diagnostics — Q9), plant-first naming (Q1), the first-run setup landing that
retires the launchpad, the three-tier cal chip + the ruled "Paused" lifecycle chip, and
the board=MCU taxonomy (#921). The render itself is verified visually (light + dark);
this locks the contract so a later edit can't silently regress it.
"""

from __future__ import annotations

from pathlib import Path

_H = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
    encoding="utf-8"
)


def test_plants_tab_is_its_own_tab_named_plants_and_sensors() -> None:
    # Q9: its own tab (not Diagnostics), named by Design-QA "Plants & Sensors".
    assert 'data-tab="plants"' in _H
    assert "Plants &amp; Sensors" in _H
    assert '<div id="plants"' in _H


def test_registry_renders_off_the_data_seam() -> None:
    assert "function renderRegistry(" in _H
    assert "function registryPoll(" in _H
    assert "'/registry'" in _H  # the #1000 GET seam


def test_naming_is_plant_first_not_the_machine_id() -> None:
    # Q1 + the four-question doctrine: pet name / type leads; never the device id.
    reg = _H[_H.index("function regPlantName(") : _H.index("function regSpell(")]
    assert "pet_name" in reg and "plant_type" in reg
    # spelled-vs-coded render: s01 -> "Sensor 01" in prose, s01 in grids.
    assert "regSpell" in _H and "'Sensor'" in _H


def test_first_run_landing_retires_the_launchpad() -> None:
    # Q9: an empty registry makes this tab the setup landing; boot auto-lands there.
    assert "first_run" in _H
    assert "set up your plants" in _H
    assert "__registry.first_run" in _H


def test_reuses_three_tier_cal_and_the_paused_word() -> None:
    # cal chip reuses the #951/#957 vocabulary; lifecycle uses the ruled "Paused".
    assert "cal · board-level" in _H  # board-cal tier
    assert "cal · uncalibrated" in _H  # uncalibrated tier
    assert "pausedchip" in _H and "'Paused'" in _H


def test_devices_section_uses_the_board_taxonomy() -> None:
    # #921 taxonomy board=MCU: the devices section is titled "Boards".
    assert "regSection('Boards'" in _H
