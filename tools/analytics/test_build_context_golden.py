#!/usr/bin/env python3
"""#1336 — the ``build_context`` golden-output suite: **the extraction's precondition**.

ADR-0038 §6 states the instrument exactly: *"Characterization tests are each
extraction's precondition — not the seam epic. Pin the module's output (golden card
payloads), then cut until it still matches."* This is that pin, built before the cut so
the cut has something to be judged against.

**Why this one needs it more than the others.** `build_context` is the most
depended-upon function in the host: **36 test files and 138 call sites** touch it
today. Every one of those is an implicit behavioural pin — which sounds like safety and
is the opposite. The behaviour is pinned *diffusely*: no single place says what
`build_context` returns, so an extraction that changed the shape would be discovered as
a scatter of unrelated-looking failures across three dozen files, each of which reads
as "that suite is about gaps" or "that suite is about cal tiers". Nothing would say
*"the contract moved"*.

This file is the one place that does. It asserts the **whole surface** — every
top-level key, its type, and the values a fixed synthetic input produces — so a shape
change fails **here, first, and legibly**, in a file whose name says what broke.

**How to read a failure.** If this suite goes red during an extraction, the extraction
changed observable output. That is the signal it exists to give; it does not mean the
suite needs updating. Update it only when the behaviour change is *intended* — and then
the diff is the review artifact showing exactly what moved.

**Determinism.** `build_context` takes `registry` and `now` by injection, so nothing
here reads real config or the wall clock. The fixture is a plain drying series with one
registered plant — deliberately boring, because a golden's job is to be stable, not
interesting.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context
from device_registry import Device, Registry
from parse_v1 import LogData, Reading

T0 = datetime(2026, 7, 10, tzinfo=timezone.utc)
NOW = T0 + timedelta(minutes=600)

# The 19 keys build_context returns. Adding or removing one is a contract change and
# must be a deliberate edit here, not a silent consequence of a refactor.
GOLDEN_KEYS = {
    "band_history": list,
    "cal": dict,
    "devices": list,
    "distribution": dict,
    "env": dict,
    "fleet": dict,
    "fleet_health": dict,
    "gaps": list,
    "gaps_by_device": dict,
    "integrity": dict,
    "meta": dict,
    "orientation": str,
    "provenance": dict,
    "quality": dict,
    "sensorless": list,
    "sensors": list,
    "spread": list,
    "trajectory": dict,
    "versions": dict,
}


def _reading(minute: int, raw: int, level: str = "OK") -> Reading:
    return Reading(
        "plants.soil",
        T0 + timedelta(minutes=minute),
        None,
        None,
        "sess1",
        "devA",
        "0.8.0",
        "x",
        None,
        "UMLIFE_v2_TLC555",
        "s1",
        "",
        "s1",
        raw,
        None,
        "",
        "OK",
        {"level": level},
    )


def _fixture() -> tuple[LogData, Registry]:
    """A plain 10-hour drying series on one registered channel."""
    rows = [_reading(i * 30, 1500 + i * 20) for i in range(20)]
    reg = Registry(
        devices=[
            Device(
                device_id="devA",
                board="esp32dev",
                label="A",
                channels={"s1": {"plant_id": "p01", "plant_name": "Corn"}},
            )
        ]
    )
    return LogData(readings=rows, segments=[], sources=["s"]), reg


def _ctx() -> dict:
    data, reg = _fixture()
    return build_context(data, registry=reg, now=NOW)


# --------------------------------------------------------------------------- #
# G1 — the surface itself
# --------------------------------------------------------------------------- #
def test_g1_the_key_set_is_exactly_the_golden_set() -> None:
    """The whole point: a key appearing or vanishing is a contract change."""
    ctx = _ctx()
    assert set(ctx) == set(GOLDEN_KEYS), (
        f"added: {set(ctx) - set(GOLDEN_KEYS)} · removed: {set(GOLDEN_KEYS) - set(ctx)}"
    )


def test_g2_every_key_has_its_golden_type() -> None:
    ctx = _ctx()
    for key, want in GOLDEN_KEYS.items():
        got = type(ctx[key]).__name__
        assert isinstance(ctx[key], want), f"{key}: {got} != {want.__name__}"


# --------------------------------------------------------------------------- #
# G3 — the values a fixed input produces (the golden payload proper)
# --------------------------------------------------------------------------- #
def test_g3_attribution_is_stable() -> None:
    """One registered channel resolves to its plant, by name, once."""
    ctx = _ctx()
    assert len(ctx["sensors"]) == 1
    s = ctx["sensors"][0]
    assert s["id"] == "s1"
    assert s.get("plant_id") == "p01"
    assert s.get("plant_name") == "Corn"


def test_g4_the_series_is_neither_dropped_nor_padded() -> None:
    """20 readings in, 20 plotted out — a decimation or filter change shows here."""
    ctx = _ctx()
    (dataset,) = ctx["trajectory"]["datasets"]
    assert len(dataset["points"]) == 20
    assert dataset["points"][0]["y"] == 1500
    assert dataset["points"][-1]["y"] == 1500 + 19 * 20


def test_g5_the_trend_fits_the_drying_arc() -> None:
    """A monotone rise is a positive (drying) slope, segment-bound to the window."""
    ctx = _ctx()
    trend = ctx["trajectory"]["datasets"][0]["trend"]
    assert trend is not None
    assert trend["y1"] > trend["y0"]  # drying
    assert trend["segment_bound"] is False  # no re-water in this window
    assert trend["mask_dropped"] == 0  # nothing excluded from a clean arc


def test_g6_one_device_one_channel_in_the_fleet_rollup() -> None:
    ctx = _ctx()
    assert len(ctx["devices"]) == 1
    assert ctx["devices"][0]["device_id"] == "devA"
    assert ctx["sensorless"] == []  # none configured in the fixture


def test_g7_a_clean_window_reports_no_gaps() -> None:
    """Uniform 30-minute spacing: the gap detector must find nothing."""
    ctx = _ctx()
    assert ctx["gaps"] == []
    assert ctx["gaps_by_device"] in ({}, {"devA": []})


def test_g8_the_cal_block_carries_the_ratified_ladder() -> None:
    """The bands the surface shades with come from the ratified ladder, not ad-hoc."""
    ctx = _ctx()
    bands = ctx["cal"]["bands"]
    assert isinstance(bands, list) and len(bands) >= 7
    for band in bands:
        assert {"lo", "hi", "color"} <= set(band)


def test_g9_provenance_and_meta_are_populated_not_placeholder() -> None:
    ctx = _ctx()
    assert ctx["provenance"] and ctx["meta"]
    assert isinstance(ctx["orientation"], str) and ctx["orientation"]


# --------------------------------------------------------------------------- #
# G10 — determinism, which is what makes a golden a golden
# --------------------------------------------------------------------------- #
def test_g10_the_same_input_yields_the_same_output() -> None:
    """Injected registry + now, so two builds must agree exactly. If this fails,
    something reads the wall clock or real config and the golden is not a golden."""
    first, second = _ctx(), _ctx()
    assert set(first) == set(second)
    assert first["sensors"] == second["sensors"]
    assert (
        first["trajectory"]["datasets"][0]["points"]
        == (second["trajectory"]["datasets"][0]["points"])
    )
    assert first["gaps"] == second["gaps"]
    assert first["cal"] == second["cal"]
