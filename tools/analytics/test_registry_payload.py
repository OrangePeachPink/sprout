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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from registry_model import (
    Plant,
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
