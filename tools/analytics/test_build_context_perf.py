#!/usr/bin/env python3
"""#1457 - the classic build stays off the superlinear cliff for wide windows.

The measured defect (#1429): ``build_context`` dominated the /data.json response
(85-90%), and on the full 30d/`all` corpus it went superlinear - 33 s for ~715k rows,
so those views never rendered before the client gave up. The profile named the biggest
avoidable cost: the segment classifier ran **twice** over every plant's full window,
because ``valid_for_trend`` calls ``classify`` internally and the mask-window pass
called it again on the identical rows. Deduping cut the single-build ~49% (10.8s ->
5.5s at 700k rows; measurements in the issue).

A wall-clock assertion would be flaky in CI, so this pins the **structural** property
that produced the win instead: ``classify`` runs once per plant, not twice. That is
deterministic, and it is the specific regression that would quietly return the 2x cost.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics import segment_classifier
from tools.analytics.device_registry import Device, Registry
from tools.analytics.parse_v1 import LogData, Reading

T0 = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _fixture(n: int, plants: int = 1) -> tuple[LogData, Registry]:
    devs, rows = [], []
    for p in range(plants):
        dev = f"dev{p}"
        devs.append(
            Device(
                device_id=dev,
                board="esp32-classic",
                label=f"B{p}",
                channels={"s1": {"plant_id": f"p0{p}", "plant_name": f"P{p}"}},
            )
        )
        for i in range(n):
            rows.append(
                Reading(
                    "plants.soil",
                    T0 + timedelta(seconds=30 * i),
                    None,
                    None,
                    "s1",
                    dev,
                    "0.8.0",
                    "x",
                    None,
                    "UMLIFE_v2_TLC555",
                    "s1",
                    "",
                    "s1",
                    1500 + (i % 600),
                    None,
                    "",
                    "OK",
                    {"level": "drying"},
                )
            )
    return LogData(readings=rows, segments=[], sources=["s"]), Registry(devices=devs)


def test_classify_runs_once_per_plant_not_twice(monkeypatch) -> None:
    """The #1457 dedup, pinned. Two plants => classify is called at most once each on
    the trajectory path; the old valid_for_trend()+classify() double would show 4."""
    calls = {"n": 0}
    real = segment_classifier.classify

    def counting(rows):
        calls["n"] += 1
        return real(rows)

    from tools.analytics import (
        card_context,  # it did: from segment_classifier import classify
    )

    monkeypatch.setattr(card_context, "classify", counting)

    data, reg = _fixture(500, plants=2)
    card_context.build_context(data, registry=reg, now=T0 + timedelta(seconds=30 * 500))

    assert calls["n"] <= 2, (
        f"classify ran {calls['n']}x for 2 plants - the #1457 dedup regressed "
        "(valid_for_trend + classify on the same rows is the 2x)"
    )


def test_valid_for_trend_is_not_imported_back_into_card_context() -> None:
    """The dedup replaced valid_for_trend() with a comprehension over the kinds classify
    already returned. Importing valid_for_trend back is the trap - it re-runs classify
    internally. The import line is the comment-safe signal; the counter test above
    guards the call count, this guards the import that would enable it."""
    src = (Path(__file__).resolve().parent / "card_context.py").read_text(
        encoding="utf-8"
    )
    assert "    valid_for_trend,\n" not in src, (
        "valid_for_trend is imported into card_context again - it re-runs classify "
        "internally; derive the mask from the kinds already computed (#1457)"
    )
