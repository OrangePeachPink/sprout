"""#963 — the owner-cal write path (option 1 ratified) + the projection receipt."""

from __future__ import annotations

from tools.analytics.cal_receipt import CONFIRMED, PUSHED, STORED, evaluate
from tools.analytics.registry_model import Profile, RegistryModel, apply_operations

AIR, WATER = 3137, 1052  # the classic's measured envelope


def _ops(**anchors):
    return {
        "profiles": {
            "add": [
                {
                    "profile_id": "cal-s1",
                    "name": "probe s1 (owner)",
                    "sensor_type": "capacitive",
                    "anchors": anchors or {"air": AIR, "water": WATER},
                    "provenance": {"who": "owner", "date": "2026-07-20"},
                    "tier": "channel-cal",
                }
            ]
        }
    }


def test_an_owner_profile_is_written_through_the_batch_path() -> None:
    m = RegistryModel()
    r = apply_operations(m, _ops())
    assert r["ok"] and len(m.profiles) == 1
    p = m.profiles[0]
    assert p.anchors == {"air": AIR, "water": WATER}
    assert p.tier == "channel-cal" and p.provenance["who"] == "owner"


def test_inverted_anchors_are_REFUSED_and_nothing_is_written() -> None:
    # the load-bearing guard: probe into the cup before the air reading produces a
    # well-formed record that makes every downstream band wrong, detectable nowhere else
    m = RegistryModel()
    r = apply_operations(m, _ops(air=WATER, water=AIR))
    assert r["ok"] is False
    assert any("inverted" in e["message"] for e in r["errors"])
    assert m.profiles == []  # validate-first: the batch is atomic


def test_an_unknown_tier_is_refused() -> None:
    ops = _ops()
    ops["profiles"]["add"][0]["tier"] = "owner-cal"  # not in the closed enum
    r = apply_operations(RegistryModel(), ops)
    assert r["ok"] is False and any("tier" in (e["field"] or "") for e in r["errors"])


def test_a_duplicate_profile_id_is_refused() -> None:
    m = RegistryModel(profiles=[Profile(profile_id="cal-s1", name="x")])
    r = apply_operations(m, _ops())
    assert r["ok"] is False and len(m.profiles) == 1


def test_editing_recharacterises_every_channel_that_references_it() -> None:
    # reference semantics: channels hold a profile_id, never a private copy
    m = RegistryModel(
        profiles=[
            Profile(profile_id="cal-s1", name="p", anchors={"air": 3000, "water": 1000})
        ]
    )
    m.assign(
        plant_id="p01",
        sensor_id="s1",
        device_id="d1",
        channel="ch0",
        profile_id="cal-s1",
    )
    m.assign(
        plant_id="p02",
        sensor_id="s2",
        device_id="d1",
        channel="ch1",
        profile_id="cal-s1",
    )
    r = apply_operations(
        m,
        {
            "profiles": {
                "edit": [
                    {"profile_id": "cal-s1", "anchors": {"air": AIR, "water": WATER}}
                ]
            }
        },
    )
    assert r["ok"]
    assert m.profiles[0].anchors == {"air": AIR, "water": WATER}
    # both channels moved together because neither held a copy
    assert [a.profile_id for a in m.open_assignments()] == ["cal-s1", "cal-s1"]


def test_editing_an_unknown_profile_is_refused() -> None:
    r = apply_operations(
        RegistryModel(), {"profiles": {"edit": [{"profile_id": "nope"}]}}
    )
    assert r["ok"] is False


# ---- the receipt: what you sent vs what is running -------------------------- #


def _prof(who="owner"):
    return Profile(
        profile_id="cal-s1", name="p", provenance={"who": who} if who else None
    )


def test_stored_is_reachable_with_no_board_at_all() -> None:
    # the offline bench flow: cal survives the wizard even if nothing is reachable
    r = evaluate(_prof(), pushed=False, observed_cal_src=None)
    assert r.state == STORED and r.is_live is False


def test_pushed_is_not_confirmed_on_a_classic_where_tier_never_moves() -> None:
    # Firmware's finding: a lost projection is SILENT on the tier axis for the classic
    r = evaluate(_prof(), pushed=True, observed_cal_src="bench")
    assert r.state == PUSHED and r.is_live is False
    assert "did not land" in r.detail


def test_confirmed_requires_telemetry_to_report_the_owner_provenance() -> None:
    r = evaluate(_prof(), pushed=True, observed_cal_src="owner")
    assert r.state == CONFIRMED and r.is_live is True


def test_a_serial_only_board_never_confirms_and_says_why() -> None:
    # cal_src is gated on rssi_present — WiFi rows only (stated, not discovered)
    r = evaluate(_prof(), pushed=True, observed_cal_src=None)
    assert r.state == PUSHED and "serial-only" in r.detail


def test_a_profile_with_no_provenance_cannot_be_confirmed_and_admits_it() -> None:
    r = evaluate(_prof(who=None), pushed=True, observed_cal_src="anything")
    assert r.state == PUSHED and "nothing to confirm against" in r.detail
