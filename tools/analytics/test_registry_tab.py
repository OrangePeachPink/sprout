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


def test_pot_size_and_location_are_editable_in_app() -> None:
    # #833: the two fields that used to force config-file surgery. pot_size must be
    # settable (it was nowhere in the UI); location must be EDITABLE (it was add-only).
    add = _H[_H.index("function regAddControl(") : _H.index("function regStageAdd(")]
    assert "'pot_size'" in add and "'location'" in add  # both offered at add-time
    edit = _H[_H.index("function regEditForm(") : _H.index("function regStageEdit(")]
    assert "'pot_size'" in edit  # pot size now settable after creation
    assert "mk('location', 'location'" in edit  # location now changeable, not add-only


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


# --------------------------------------------------------------------------- #
# slice 3a — add + classic review-then-save (Q10)
# --------------------------------------------------------------------------- #


def test_pending_batch_matches_the_apply_seam_shape() -> None:
    # the client's pending batch must be exactly what /registry/apply accepts, so a Save
    # never round-trips a shape the server rejects (the #1021 contract).
    pend = _H[_H.index("function regPendNew(") : _H.index("function regPend(")]
    for key in (
        "plants:{add:[],edit:[]}",
        "sensors:{add:[],edit:[]}",
        "devices:{edit:[]}",
        "mappings:{assign:[],close:[]}",
        "lifecycle:[]",
    ):
        assert key in pend


def test_add_controls_and_server_next_id_prefill() -> None:
    assert "function regAddControl(" in _H
    assert "+ Add a plant" in _H and "+ Add a sensor" in _H
    # server owns id allocation — the form prefills from /registry's next_ids (Q1/Q2).
    assert "__registry.next_ids" in _H
    # a sensor number is required at add (Q1/Q11); a plant number is server-allocated.
    assert "A sensor number is required." in _H


def test_classic_save_posts_the_batch_and_handles_structured_errors() -> None:
    save = _H[_H.index("async function regSave(") : _H.index("function regDirty(")]
    assert "'/registry/apply'" in save and "method: 'POST'" in save
    assert "data.errors" in save  # structured 400 errors rendered inline (Q3)
    assert "data.registry" in save  # re-renders from the fresh state, no 2nd GET


def test_dirty_state_bar_and_dont_browse_away_guards() -> None:
    # unmistakable dirty state (Q10) + both leave-guards.
    assert "function regDirtyBar(" in _H
    assert "unsaved change" in _H
    assert "beforeunload" in _H  # browser-level guard
    assert "Leave without saving?" in _H  # in-app tab-switch guard (showTab)


# --------------------------------------------------------------------------- #
# slice 3c — lifecycle UI (Pause/Resume + loud Delete), surface for #1022 purge
# --------------------------------------------------------------------------- #


def test_lifecycle_controls_pause_resume_delete() -> None:
    ctl = _H[_H.index("function regLifeCtl(") : _H.index("function renderRegistry(")]
    assert "'Pause'" in ctl and "'Resume'" in ctl and "'Delete'" in ctl
    # applies to all three kinds (plant, sensor, device=board) via regLifecycle.
    assert "regLifeCtl('plant'" in _H
    assert "regLifeCtl('sensor'" in _H
    assert "regLifeCtl('device'" in _H  # the board delete (yyvvpd)


def test_delete_is_loud_and_double_confirmed() -> None:
    # Q3: delete is loud + double-confirmed — a two-step arm, never a one-click purge.
    assert "__regArmDelete" in _H
    assert "Permanently delete" in _H and "This can" in _H  # "...can't be undone"
    assert "Yes, delete" in _H and "Keep it" in _H
    assert "willdelete" in _H  # the staged-for-deletion marker


def test_lifecycle_stages_the_apply_shape() -> None:
    # regStageLifecycle emits {kind, entity_id, state} into pending.lifecycle — the
    # exact op apply_operations validates against LIFECYCLE_STATES (#1022).
    fn = _H[_H.index("function regStageLifecycle(") : _H.index("function regLifeCtl(")]
    assert "entity_id: id" in fn and "state}" in fn
    assert "p.lifecycle.push" in fn


def test_delete_wires_to_purge_not_a_lifecycle_flag() -> None:
    # #1024 gate fix: a staged 'deleted' emits #1022's real purge:{...}, NOT
    # lifecycle:state=deleted (a flag-flip leaving the entity in devices[] + the
    # poll set — Delete would promise "and its history" and remove nothing).
    save = _H[_H.index("async function regSave(") : _H.index("function regDirty(")]
    assert "purge" in save
    assert "l.state === 'deleted'" in save and "purge[sec].push" in save
    assert "else lifecycle.push(l)" in save  # pause/resume still ride lifecycle
    # the purge receipt (files.removed) is the honest surface for what delete reached.
    assert "data.files" in save and "regreceipt" in _H


# slice 3b — the mapping picker (plant-first, no hand-typed channels)
# --------------------------------------------------------------------------- #


def test_map_affordance_is_plant_first_not_dropdown_soup() -> None:
    assert "function regSensorPicker(" in _H
    assert "Assign a sensor" in _H and "Change sensor" in _H
    # the picker reads the merged #1025 channel occupancy, never a hand-typed channel.
    assert "d.channels" in _H or "(d.channels" in _H
    assert "Which sensor watches" in _H  # plant-first header


def test_picker_uses_channel_occupancy_free_and_remap() -> None:
    # a free port (sensor_id null, #1025) places a sensor; an occupied port remaps.
    assert "free — place a sensor" in _H
    assert "ch.sensor_id" in _H  # occupied vs free comes from the channel view


def test_assign_stages_the_full_tuple_no_hand_typing() -> None:
    fn = _H[
        _H.index("function regStageAssign(") : _H.index("function regSensorPicker(")
    ]
    assert "mappings.assign.push" in fn
    # device_id + channel come from the chosen port, never typed (Data's answer).
    for k in ("plant_id:", "sensor_id:", "device_id:", "channel:"):
        assert k in fn


def test_regview_overlays_staged_mappings() -> None:
    # a staged assign shows on the card before Save (server resolves truth on Save).
    view = _H[_H.index("function regView(") : _H.index("function regStageAssign(")]
    assert "pend.mappings.assign" in view and "pend.mappings.close" in view
    assert "_staged: true" in view


# --------------------------------------------------------------------------- #
# #1038 — inline field-edit (rename plants / sensors / boards); completes #600 UI
# --------------------------------------------------------------------------- #


def test_inline_edit_pencil_and_form_exist() -> None:
    assert "function regEditPencil(" in _H and "function regEditForm(" in _H
    assert "✎ Rename" in _H  # the pencil affordance on every entity
    assert "regEditPencil('plant'" in _H
    assert "regEditPencil('sensor'" in _H
    assert "regEditPencil('device'" in _H  # the board rename — #600's UI half


def test_edit_form_offers_editable_fields_only() -> None:
    fn = _H[_H.index("function regEditForm(") : _H.index("function regStageEdit(")]
    # plant: the mutable description fields; sensor + board: the label.
    for field in ("'pet_name'", "'plant_type'", "'pot_description'", "'friendly_name'"):
        assert field in fn
    # the form's inputs (mk calls) are the editable fields only — the id is never a
    # form input (#1021 edit-not-identity is enforced server-side; the id rides as the
    # target key in regStageEdit, not an editable field).
    assert "mk('pet name', 'pet_name'" in fn
    assert "mk('board name', 'friendly_name'" in fn


def test_edit_stages_into_the_edit_section_not_add() -> None:
    fn = _H[_H.index("function regStageEdit(") : _H.index("function regDirtyBar(")]
    assert "p[sec].edit" in fn and ".push(rec)" in fn
    assert "one staged edit per entity" in fn  # replace-not-append per id


def test_regview_overlays_edits_and_devicename_reads_name() -> None:
    view = _H[_H.index("function regView(") : _H.index("regStageAssign")]
    assert "pend.plants.edit" in view and "pend.devices.edit" in view
    # a board rename writes `name` server-side (#583); the label render must read it.
    assert "d.name || d.friendly_name" in _H
