"""#1315 — the v5 channel-key migration: the STATED mapping, fail-closed anomalies,
the GPIO cross-check as a hard gate, idempotence, and dry-run-writes-nothing."""

from __future__ import annotations

import json
from pathlib import Path

from tools.analytics.device_registry import Device, Registry
from tools.analytics.registry_v5_migrate import (
    KEY_TO_CHANNEL,
    SENSOR_NAMES,
    apply_migration,
    is_writable,
    plan_migration,
    render_dry_run,
    validate_against_gpio,
)


def _reg(channels, board="esp32dev", device_id="devA", extra=()):
    devs = [Device(device_id=device_id, board=board, label="A", channels=channels)]
    devs.extend(extra)
    return Registry(devices=devs)


def _chans(**kw):
    return {k: {"plant_id": v, "plant_name": f"plant {v}"} for k, v in kw.items()}


def test_the_mapping_is_the_stated_constant_and_is_not_sequential() -> None:
    # the whole point of #1315: positional inference gives s1->ch0, wrong x4
    assert SENSOR_NAMES == ("s3", "s4", "s1", "s2")
    assert KEY_TO_CHANNEL == {"s3": "ch0", "s4": "ch1", "s1": "ch2", "s2": "ch3"}
    assert KEY_TO_CHANNEL["s1"] != "ch0"  # the exact error the refusal prevented


def test_plan_renames_every_key_in_channel_order_carrying_the_plant() -> None:
    reg = _reg(_chans(s1="p11", s2="p02", s3="p06", s4="p04"))
    plan = plan_migration(reg)
    (dev,) = plan["devices"]
    assert dev["status"] == "ok" and not dev["anomalies"]
    assert [(r["from"], r["to"], r["plant_id"]) for r in dev["renames"]] == [
        ("s3", "ch0", "p06"),
        ("s4", "ch1", "p04"),
        ("s1", "ch2", "p11"),
        ("s2", "ch3", "p02"),
    ]


def test_gpio_cross_check_passes_on_the_real_shape_and_catches_a_swap() -> None:
    reg = _reg(_chans(s1="p11", s2="p02", s3="p06", s4="p04"))
    good = {"devA": {"s3": {"36"}, "s4": {"39"}, "s1": {"34"}, "s2": {"35"}}}
    assert validate_against_gpio(reg, good) == []
    swapped = {"devA": {"s3": {"34"}, "s4": {"39"}, "s1": {"36"}, "s2": {"35"}}}
    findings = validate_against_gpio(reg, swapped)
    assert any(f.startswith("MISMATCH") for f in findings)
    # a mismatch outranks the stated table — it must block the write
    assert is_writable(plan_migration(reg), findings) is False


def test_c5_uses_its_own_pins_on_the_same_channel_order() -> None:
    reg = _reg(
        _chans(s3="p01", s4="p03", s1="p10", s2="p07"), board="esp32-c5-devkitc-1"
    )
    obs = {"devA": {"s3": {"1"}, "s4": {"4"}, "s1": {"5"}, "s2": {"6"}}}
    assert validate_against_gpio(reg, obs) == []


def test_no_gpio_evidence_is_reported_unverified_never_a_silent_pass() -> None:
    reg = _reg(_chans(s1="p11"))
    findings = validate_against_gpio(reg, {})
    assert findings and findings[0].startswith("unverified")
    # unverified does not block (a board may have no GPIO in the supplied logs)
    assert is_writable(plan_migration(reg), findings) is True


def test_anomalies_fail_closed_per_device_never_half_migrated() -> None:
    reg = _reg({**_chans(s1="p11"), "s9": {"plant_id": "pX"}})  # s9 not in the table
    plan = plan_migration(reg)
    assert plan["devices"][0]["status"] == "blocked"
    assert plan["blocked"] == ["devA"]
    assert is_writable(plan, []) is False


def test_already_migrated_is_idempotent_and_mixed_is_blocked() -> None:
    done = _reg({"ch0": {"plant_id": "p06"}, "ch1": {"plant_id": "p04"}})
    assert plan_migration(done)["devices"][0]["status"] == "already-migrated"
    mixed = _reg({"ch0": {"plant_id": "p06"}, "s4": {"plant_id": "p04"}})
    assert plan_migration(mixed)["devices"][0]["status"] == "blocked"


def test_dry_run_writes_nothing_and_apply_refuses_without_approval(tmp_path) -> None:
    src = tmp_path / "devices.local.json"
    doc = {
        "devices": [
            {
                "device_id": "devA",
                "board": "esp32dev",
                "channels": {"s1": {"plant_id": "p11"}, "s3": {"plant_id": "p06"}},
            }
        ]
    }
    src.write_text(json.dumps(doc), encoding="utf-8")
    before = src.read_text(encoding="utf-8")
    reg = _reg(_chans(s1="p11", s3="p06"))
    plan = plan_migration(reg)
    render_dry_run(plan, [])  # rendering is pure
    assert src.read_text(encoding="utf-8") == before  # untouched
    r = apply_migration(src, plan, [], approved=False)
    assert r["written"] is False and "not approved" in r["reason"]
    assert src.read_text(encoding="utf-8") == before  # still untouched


def test_approved_apply_renames_keys_verbatim_and_backs_up(tmp_path) -> None:
    src = tmp_path / "devices.local.json"
    doc = {
        "devices": [
            {
                "device_id": "devA",
                "board": "esp32dev",
                "channels": {
                    "s1": {"plant_id": "p11", "probe": "s5"},
                    "s3": {"plant_id": "p06", "probe": "s7"},
                },
            }
        ]
    }
    src.write_text(json.dumps(doc), encoding="utf-8")
    reg = _reg(_chans(s1="p11", s3="p06"))
    plan = plan_migration(reg)
    r = apply_migration(src, plan, [], approved=True)
    assert r["written"] is True and Path(r["backup"]).is_file()
    after = json.loads(src.read_text(encoding="utf-8"))
    chans = after["devices"][0]["channels"]
    assert set(chans) == {"ch0", "ch2"}
    # values carried VERBATIM — only keys move (the probe rides along untouched)
    assert chans["ch0"] == {"plant_id": "p06", "probe": "s7"}
    assert chans["ch2"] == {"plant_id": "p11", "probe": "s5"}
    # the backup preserves the pre-migration truth
    assert json.loads(Path(r["backup"]).read_text(encoding="utf-8")) == doc
