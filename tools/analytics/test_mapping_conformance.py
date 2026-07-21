"""#1335 — the mapping-UI conformance contract (spec §8).

The ratified test bar, in the spec's own words: **apply → save → reload → assert the new
attribution AND the preserved old history.** Everything here goes through the real
seams — ``apply_operations`` to mutate, ``save_registry_model``/``load_registry_model``
to round-trip, ``identity.resolve_plant`` to read — because a conformance test that
stubs the middle proves only that the stubs agree.

The failure this guards is the one the epic exists to prevent: a probe moves, and the
readings taken *before* the move quietly re-attribute to whoever is on the channel now.
That loss is silent and unrecoverable — nothing in the data says it happened.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from identity import build_projection
from registry_model import (
    RegistryModel,
    apply_operations,
    load_registry_model,
    save_registry_model,
)

BEFORE = "2026-07-05T00:00:00Z"
MOVE = "2026-07-10T00:00:00Z"
AFTER = "2026-07-15T00:00:00Z"


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _seeded() -> RegistryModel:
    """Big Green on dev/ch0 since before the window — the pre-move world."""
    m = RegistryModel()
    # entities first: apply_operations validates the whole batch against the CURRENT
    # model, so a mapping cannot reference a device created in the same batch.
    r = apply_operations(
        m,
        {
            "plants": {"add": [{"plant_id": "p01", "pet_name": "Big Green"}]},
            "sensors": {"add": [{"sensor_id": "s01"}]},
            "devices": {
                "add": [
                    {
                        "device_id": "dev",
                        "base_url": "http://d",
                        # #1027 §5.2: a board declares its channels to be adoptable
                        "channels": [36, 39, 34, 35],
                    }
                ]
            },
        },
        now=BEFORE,
    )
    assert r["ok"], r
    r = apply_operations(
        m,
        {
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p01",
                        "sensor_id": "s01",
                        "device_id": "dev",
                        "channel": "ch0",
                    }
                ]
            }
        },
        now=BEFORE,
    )
    assert r["ok"], r
    return m


def _reload(model: RegistryModel, tmp_path: Path) -> RegistryModel:
    """The round-trip the contract insists on — nothing is proven in memory alone."""
    cfg = tmp_path / "registry.json"
    save_registry_model(model, cfg)
    return load_registry_model(cfg)


# --------------------------------------------------------------------------- #
# The headline contract
# --------------------------------------------------------------------------- #
def test_reassignment_survives_a_reload_with_history_intact(tmp_path: Path) -> None:
    """apply → save → reload → new attribution AND preserved old history."""
    m = _seeded()
    r = apply_operations(
        m,
        {
            "plants": {"add": [{"plant_id": "p02", "pet_name": "Gertrude"}]},
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p02",
                        "sensor_id": "s01",
                        "device_id": "dev",
                        "channel": "ch0",
                    }
                ]
            },
        },
        now=MOVE,
    )
    assert r["ok"], r

    reloaded = _reload(m, tmp_path)
    proj = build_projection(model=reloaded)

    # the new attribution
    assert proj.resolve_plant("dev", "ch0") == "p02"
    assert proj.resolve_plant("dev", "ch0", _dt(AFTER)) == "p02"
    # the preserved history — the reading taken before the move still belongs to p01
    assert proj.resolve_plant("dev", "ch0", _dt(BEFORE)) == "p01"


def test_the_move_boundary_resolves_once_across_a_reload(tmp_path: Path) -> None:
    """close-then-open share an instant; exactly one binding may cover it — otherwise a
    reading landing on the boundary belongs to two plants or to none."""
    m = _seeded()
    apply_operations(
        m,
        {
            "plants": {"add": [{"plant_id": "p02", "pet_name": "Gertrude"}]},
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p02",
                        "sensor_id": "s01",
                        "device_id": "dev",
                        "channel": "ch0",
                    }
                ]
            },
        },
        now=MOVE,
    )
    proj = build_projection(model=_reload(m, tmp_path))
    assert proj.resolve_plant("dev", "ch0", _dt(MOVE)) == "p02"


def test_reassignment_writes_exactly_one_closed_and_one_open(tmp_path: Path) -> None:
    """No gap, no overlap, and the seam is exact — the two records share the instant."""
    m = _seeded()
    apply_operations(
        m,
        {
            "plants": {"add": [{"plant_id": "p02", "pet_name": "Gertrude"}]},
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p02",
                        "sensor_id": "s01",
                        "device_id": "dev",
                        "channel": "ch0",
                    }
                ]
            },
        },
        now=MOVE,
    )
    reloaded = _reload(m, tmp_path)
    on_channel = [
        a for a in reloaded.assignments if a.device_id == "dev" and a.channel == "ch0"
    ]
    closed = [a for a in on_channel if a.end_ts is not None]
    open_ = [a for a in on_channel if a.end_ts is None]
    assert len(closed) == 1 and len(open_) == 1
    assert closed[0].end_ts == open_[0].start_ts  # exact seam, no gap


# --------------------------------------------------------------------------- #
# Rename is NOT reassignment — the spec's §2 distinction, enforced
# --------------------------------------------------------------------------- #
def test_a_rename_emits_no_assignment_event(tmp_path: Path) -> None:
    """The whole §2 ruling in one assertion: renaming changes a string and nothing
    else. If a rename ever starts writing assignment events, history silently splits
    on a typo correction."""
    m = _seeded()
    before = [(a.plant_id, a.start_ts, a.end_ts) for a in m.assignments]

    r = apply_operations(
        m, {"plants": {"edit": [{"plant_id": "p01", "pet_name": "Gertrude"}]}}, now=MOVE
    )
    assert r["ok"], r

    reloaded = _reload(m, tmp_path)
    after = [(a.plant_id, a.start_ts, a.end_ts) for a in reloaded.assignments]
    assert after == before, "a rename must not touch the assignment chain"

    # the label moved; the attribution did not
    proj = build_projection(model=reloaded)
    assert proj.resolve_plant("dev", "ch0", _dt(BEFORE)) == "p01"
    assert proj.resolve_plant("dev", "ch0") == "p01"
    assert [p.pet_name for p in reloaded.plants if p.plant_id == "p01"] == ["Gertrude"]


# --------------------------------------------------------------------------- #
# Backdating — the spec's §3 step 3
# --------------------------------------------------------------------------- #
def test_a_backdated_move_attributes_the_in_between_readings_correctly(
    tmp_path: Path,
) -> None:
    """A probe swapped Tuesday and recorded Friday: without backdating, three days of
    readings attribute to the wrong plant. The window between the real move and the
    record must belong to the NEW plant once backdated."""
    m = _seeded()
    real_move = "2026-07-08T00:00:00Z"
    apply_operations(
        m,
        {
            "plants": {"add": [{"plant_id": "p02", "pet_name": "Gertrude"}]},
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p02",
                        "sensor_id": "s01",
                        "device_id": "dev",
                        "channel": "ch0",
                    }
                ]
            },
        },
        now=real_move,  # backdated to when it actually happened
    )
    proj = build_projection(model=_reload(m, tmp_path))
    assert proj.resolve_plant("dev", "ch0", _dt("2026-07-07T00:00:00Z")) == "p01"
    assert proj.resolve_plant("dev", "ch0", _dt("2026-07-09T00:00:00Z")) == "p02"


# --------------------------------------------------------------------------- #
# Displaced-plant disposition — §3 step 2, "still growing" is the ruled default
# --------------------------------------------------------------------------- #
def test_the_displaced_plant_keeps_its_history_and_its_existence(
    tmp_path: Path,
) -> None:
    """The ruled default is that the displaced plant survives as sensorless. It must
    keep its past readings and must NOT resolve on the channel any more."""
    m = _seeded()
    apply_operations(
        m,
        {
            "plants": {"add": [{"plant_id": "p02", "pet_name": "Gertrude"}]},
            "mappings": {
                "assign": [
                    {
                        "plant_id": "p02",
                        "sensor_id": "s01",
                        "device_id": "dev",
                        "channel": "ch0",
                    }
                ]
            },
        },
        now=MOVE,
    )
    reloaded = _reload(m, tmp_path)
    proj = build_projection(model=reloaded)

    assert "p01" in [p.plant_id for p in reloaded.plants]  # still exists
    assert proj.resolve_plant("dev", "ch0", _dt(BEFORE)) == "p01"  # keeps its past
    assert proj.resolve_plant("dev", "ch0") == "p02"  # no longer on the channel
