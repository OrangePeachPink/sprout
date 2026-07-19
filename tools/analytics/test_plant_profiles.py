"""#675 — the ADR-0029 profile dimension loader: absent-safe, honest validation,
placement referenced-never-duplicated (§3), the example template conformant.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device_registry import Device, Registry
from plant_profiles import load_profiles, placement_for, profile_for

_EXAMPLE = (
    Path(__file__).resolve().parents[2] / "config" / "plant_profiles.example.json"
)


def _write(tmp_path: Path, doc: dict) -> Path:
    p = tmp_path / "profiles.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def test_minimal_profile_is_plant_id_only_absent_safe(tmp_path: Path) -> None:
    profs, findings = load_profiles(_write(tmp_path, {"plants": [{"plant_id": "p01"}]}))
    assert profs == {"p01": {"plant_id": "p01"}} and findings == []
    assert profile_for("p01", profs) == {"plant_id": "p01"}
    assert profile_for("p99", profs) is None  # no profile = still fully monitored


def test_enum_violations_are_findings_not_crashes(tmp_path: Path) -> None:
    doc = {
        "plants": [
            {"plant_id": "p01", "pot": {"shape": "hexagonal"}},  # not a vocab shape
            {"plant_id": "p01"},  # duplicate
            {"label": "no-id"},  # missing id
        ]
    }
    profs, findings = load_profiles(_write(tmp_path, doc))
    assert "p01" in profs  # still loaded — reference data degrades honestly
    assert len(findings) == 3
    assert any("hexagonal" in f for f in findings)
    assert any("duplicate" in f for f in findings)
    assert any("missing plant_id" in f for f in findings)


def test_free_text_probe_caveat_is_legal(tmp_path: Path) -> None:
    doc = {
        "plants": [
            {
                "plant_id": "p07",
                "hydrology": {"probe_reading_caveat": "gap water hides from the probe"},
            }
        ]
    }
    _profs, findings = load_profiles(_write(tmp_path, doc))
    assert findings == []  # the ADR keeps the field open — a free note is by design


def test_placement_wired_resolves_via_the_registry_never_the_profile(tmp_path) -> None:
    # §3: wired ⇒ device-registry; the profile must NOT be consulted for a wired plant
    reg = Registry(
        devices=[
            Device(
                device_id="dev1",
                board="esp32dev",
                label="A",
                channels={"s2": {"plant_id": "p02", "plant_name": "xxl"}},
            )
        ]
    )
    profs, _ = load_profiles(
        _write(
            tmp_path,
            {
                "plants": [
                    {"plant_id": "p02"},
                    {
                        "plant_id": "p05",
                        "placement": {
                            "sensorless": True,
                            "ledge": "right",
                            "window": "kitchen",
                        },
                    },
                ]
            },
        )
    )
    wired = placement_for("p02", profs, reg)
    assert wired["source"] == "device-registry"
    assert (wired["device"], wired["channel"]) == ("dev1", "s2")
    sensorless = placement_for("p05", profs, reg)
    assert sensorless == {"source": "profile", "side": "right", "window": "kitchen"}
    assert placement_for("p99", profs, reg) == {"source": "unknown"}


def test_the_committed_example_template_validates_cleanly() -> None:
    profs, findings = load_profiles(_EXAMPLE)
    assert profs and findings == []  # the template must conform to its own schema


def test_discovery_absent_is_empty_never_a_crash(tmp_path: Path) -> None:
    profs, findings = load_profiles(tmp_path / "nope.json")
    assert profs == {} and len(findings) == 1  # honest finding, empty dimension
