"""#921 slice 2 — the /registry GET seam for the Plants & Sensors tab.

The blocking seam DesignQA builds the tab against: the temporal model (#996) as a JSON
payload, plus the derived current mapping + the first_run flag.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from tools.analytics.registry_model import (
    Plant,
    Profile,
    RegistryModel,
    Sensor,
    load_registry_model,
    registry_payload,
)

_SERVE = Path(__file__).resolve().parent / "serve.py"


# --------------------------------------------------------------------------- #
# registry_payload — shape the tab reads
# --------------------------------------------------------------------------- #


def test_payload_carries_entities_current_mapping_and_first_run() -> None:
    m = RegistryModel(
        plants=[Plant(plant_id="p01", pet_name="Bernie")],
        sensors=[Sensor(sensor_id="s01")],
        devices=[{"device_id": "y9d41p", "lifecycle": "active"}],
    )
    m.assign(
        plant_id="p01",
        sensor_id="s01",
        device_id="y9d41p",
        channel="s1",
        now="2026-07-11T10:00:00Z",
    )
    pay = registry_payload(m)
    assert pay["first_run"] is False
    assert pay["plants"][0]["pet_name"] == "Bernie"
    assert len(pay["current_mappings"]) == 1
    cm = pay["current_mappings"][0]
    assert (
        cm["plant_id"] == "p01" and cm["sensor_id"] == "s01" and cm["channel"] == "s1"
    )
    # it serializes to JSON cleanly (the wire contract)
    assert json.loads(json.dumps(pay))["first_run"] is False


def test_empty_registry_is_first_run() -> None:
    pay = registry_payload(RegistryModel())
    assert pay["first_run"] is True  # a fresh install lands on the setup tab (Q9)
    assert pay["plants"] == [] and pay["current_mappings"] == []


def test_a_closed_assignment_is_not_in_the_current_mapping() -> None:
    m = RegistryModel(devices=[{"device_id": "d", "lifecycle": "active"}])
    m.assign(
        plant_id="p01",
        sensor_id="s01",
        device_id="d",
        channel="s1",
        now="2026-07-11T10:00:00Z",
    )
    m.assign(
        plant_id="p02",
        sensor_id="s01",
        device_id="d",
        channel="s1",
        now="2026-07-11T11:00:00Z",
    )
    pay = registry_payload(m)
    assert len(pay["current_mappings"]) == 1  # only the open one
    assert pay["current_mappings"][0]["plant_id"] == "p02"


def test_load_missing_config_is_empty_model(tmp_path: Path) -> None:
    m = load_registry_model(tmp_path / "nope.json")
    assert m.plants == [] and registry_payload(m)["first_run"] is True


def test_config_discovery_matches_device_registry_exactly() -> None:
    # #1029: registry_model._REPO was parents[1] (= tools/), so _LOCAL pointed at a
    # nonexistent tools/config/devices.local.json -> the loader honest-emptied over a
    # fully-mapped fleet ("No boards yet" over 3 logging boards) and a Save would have
    # written a shadow config. Pin the docstring's promise ("SAME discovery as
    # device_registry") mechanically so the path can never drift off the repo root.
    from tools.analytics import device_registry as dr
    from tools.analytics import registry_model as rm

    assert rm._LOCAL == dr._LOCAL
    assert rm._EXAMPLE == dr._EXAMPLE
    assert rm._LOCAL == rm._REPO / "config" / "devices.local.json"
    # _REPO really is the repo root (the committed example config lives there)
    assert (rm._REPO / "config" / "devices.example.json").exists()


# --------------------------------------------------------------------------- #
# /registry route serves the seam
# --------------------------------------------------------------------------- #


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_registry_route_serves_json_with_the_seam_keys(tmp_path: Path) -> None:
    import os

    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            str(_SERVE),
            str(tmp_path),
            "--port",
            str(port),
            "--no-autostart",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    try:
        up = False
        for _ in range(60):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    up = True
                    break
            except OSError:
                time.sleep(0.1)
        assert up
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/registry", timeout=5
        ) as r:
            assert r.status == 200
            doc = json.loads(r.read().decode("utf-8"))
        # the tab's contract: the entity lists + the derived seam keys are all present
        for key in ("plants", "sensors", "devices", "current_mappings", "first_run"):
            assert key in doc, f"/registry payload missing {key}"
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


# --------------------------------------------------------------------------- #
# #921 taxonomy: the status line counts BOARDS (board = MCU), not "sensors"
# --------------------------------------------------------------------------- #


def test_status_line_counts_boards_not_sensors() -> None:
    tpl = (Path(__file__).resolve().parent / "dashboard_template.html").read_text(
        encoding="utf-8"
    )
    coll = tpl[tpl.index("function collDescribe(") : tpl.index("function collRender(")]
    assert "board${configured" in coll and "of ${configured} boards" in coll
    assert "sensors —" not in coll  # the old noun is gone from the count


# --------------------------------------------------------------------------- #
# #921 slice 5 — per-channel view (cal chip + the 3b free-port picker)
# --------------------------------------------------------------------------- #
def _cal_model() -> RegistryModel:
    m = RegistryModel(
        plants=[Plant("p01"), Plant("p02")],
        sensors=[Sensor("s01"), Sensor("s02")],
        devices=[{"device_id": "y9d41p", "channels": {"s1": {}, "s2": {}, "s3": {}}}],
        profiles=[
            Profile(
                "pf1", name="cap-cal", tier="channel-cal", provenance={"who": "vkh"}
            )
        ],
    )
    # s01 mapped to s1 with a cal profile; s2 mapped uncalibrated; s3 left FREE
    m.assign(
        plant_id="p01",
        sensor_id="s01",
        device_id="y9d41p",
        channel="s1",
        profile_id="pf1",
        now="2026-07-11T00:00:00Z",
    )
    m.assign(
        plant_id="p02",
        sensor_id="s02",
        device_id="y9d41p",
        channel="s2",
        now="2026-07-11T00:00:00Z",
    )
    return m


def test_channel_view_carries_occupancy_and_cal() -> None:
    dev = registry_payload(_cal_model())["devices"][0]
    by_ch = {c["channel"]: c for c in dev["channels"]}
    # s1: mapped + calibrated (cal chip reads channel-cal + provenance)
    assert by_ch["s1"]["sensor_id"] == "s01"
    assert by_ch["s1"]["cal_tier"] == "channel-cal"
    assert by_ch["s1"]["provenance"] == {"who": "vkh"}
    # s2: mapped but uncalibrated (no profile referenced)
    assert by_ch["s2"]["sensor_id"] == "s02"
    assert by_ch["s2"]["cal_tier"] == "uncalibrated"
    # s3: a FREE port — the 3b picker's candidate (sensor_id null)
    assert by_ch["s3"]["sensor_id"] is None
    assert by_ch["s3"]["cal_tier"] == "uncalibrated"


def test_a_deleted_sensors_port_reads_free() -> None:
    m = _cal_model()
    m.set_lifecycle("sensor", "s01", "deleted")
    by_ch = {c["channel"]: c for c in registry_payload(m)["devices"][0]["channels"]}
    assert by_ch["s1"]["sensor_id"] is None  # deleted -> its port is free again


if __name__ == "__main__":
    import tempfile

    test_payload_carries_entities_current_mapping_and_first_run()
    print("  PASS  payload shape")
    test_empty_registry_is_first_run()
    print("  PASS  first_run")
    test_a_closed_assignment_is_not_in_the_current_mapping()
    print("  PASS  closed not current")
    with tempfile.TemporaryDirectory() as d:
        test_load_missing_config_is_empty_model(Path(d))
        test_registry_route_serves_json_with_the_seam_keys(Path(d))
    print("  PASS  route + missing-config")
    test_status_line_counts_boards_not_sensors()
    print("All checks passed.")
