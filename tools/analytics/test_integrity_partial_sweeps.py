#!/usr/bin/env python3
"""#1597 — "partial sweeps" is judged per DEVICE, not against the greenhouse total.

From the maintainer's #1431 bench evidence: a 7-day summary read **130,420 rows ·
32,605 sweeps · all 32,605 partial** — while 130420/32605 is exactly 4. Every sweep was
complete, and every sweep was flagged as missing a sensor.

`_integrity` compared each sweep's row count against the count of ALL sensors across ALL
devices. A sweep belongs to one board, so with two 4-channel boards `4 < 8` was true for
every complete sweep. Structurally wrong since the fleet went multi-device; the
single-board case masked it, which is why these tests are deliberately MULTI-device — a
one-device fixture passes against the broken code and proves nothing.

The panel renders this as "⚠ N sweep(s) are missing a sensor. Real dropped samples,
surfaced not smoothed." Asserting loss that didn't happen is the falsehood family, and
an over-reported warning trains the operator to ignore the real one.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tools.analytics.card_context import _integrity
from tools.analytics.parse_v1 import Reading, Sweep

T0 = datetime(2026, 7, 20, tzinfo=timezone.utc)


def _r(device_id: str, sensor_id: str, tick: int, raw: int | None = 1500) -> Reading:
    return Reading(
        "plants.soil",
        T0 + timedelta(seconds=30 * tick),
        T0 + timedelta(seconds=30 * tick),
        None,
        f"sess-{device_id}",
        device_id,
        "0.8.0",
        "x",
        30_000 * tick,
        "UMLIFE_v2_TLC555",
        sensor_id,
        "",
        sensor_id,
        raw,
        None,
        "",
        "OK",
        {"level": "OK"},
    )


def _sweep(rows: list[Reading]) -> Sweep:
    return Sweep(
        session_id=rows[0].session_id,
        millis_ms=rows[0].millis_ms,
        timestamp_utc=rows[0].timestamp_utc,
        by_sensor={r.sensor_id: r for r in rows},
    )


def _fixture(devices: dict[str, list[str]], ticks: int = 5):
    """Every sweep COMPLETE for its own device. `devices` maps device_id -> channels."""
    soil: list[Reading] = []
    sweeps: list[Sweep] = []
    for tick in range(ticks):
        for dev, chans in devices.items():
            rows = [_r(dev, ch, tick) for ch in chans]
            soil.extend(rows)
            sweeps.append(_sweep(rows))
    by_sensor: dict[str, list] = {}
    for r in soil:
        by_sensor.setdefault(f"{r.sensor_id}@{r.device_id}", []).append(r)
    return soil, sweeps, by_sensor, sorted(by_sensor)


def test_two_complete_boards_report_zero_partial_sweeps() -> None:
    """The reported defect, in miniature. Two 4-channel boards, every sweep complete:
    the old code scored every one `4 < 8` and called all of them partial."""
    soil, sweeps, by_sensor, sids = _fixture(
        {"y9d41p": ["s1", "s2", "s3", "s4"], "8gtt1h": ["s1", "s2", "s3", "s4"]}
    )
    out = _integrity(soil, sweeps, by_sensor, sids, sessions=[])
    assert out["sweeps"] == 10  # 5 ticks x 2 boards
    assert out["total"] == 40
    assert out["partial_sweeps"] == 0  # was 10 before the fix


def test_boards_with_DIFFERENT_channel_counts_are_each_judged_on_their_own() -> None:
    """A 4-channel board and a 2-channel board. The 2-channel board's sweeps are
    complete for IT — judging them against 6 (or against 4) would be the same error in a
    subtler shape."""
    soil, sweeps, by_sensor, sids = _fixture(
        {"y9d41p": ["s1", "s2", "s3", "s4"], "n3jhsp": ["s1", "s2"]}
    )
    out = _integrity(soil, sweeps, by_sensor, sids, sessions=[])
    assert out["partial_sweeps"] == 0


def test_a_genuinely_short_sweep_is_still_caught() -> None:
    """The counter must keep working: drop one row from one board's sweep and it
    reports exactly one partial — the warning has to remain true when loss is real."""
    soil, sweeps, by_sensor, sids = _fixture(
        {"y9d41p": ["s1", "s2", "s3", "s4"], "8gtt1h": ["s1", "s2", "s3", "s4"]}
    )
    victim = next(
        sw for sw in sweeps if next(iter(sw.by_sensor.values())).device_id == "y9d41p"
    )
    victim.by_sensor.pop("s4")
    out = _integrity(soil, sweeps, by_sensor, sids, sessions=[])
    assert out["partial_sweeps"] == 1


def test_a_null_raw_counts_as_missing_not_present() -> None:
    """Partiality is about rows that carry a reading; a present-but-null row is a hole
    the same as an absent one (unchanged behaviour, pinned so the rewrite kept it)."""
    soil, sweeps, by_sensor, sids = _fixture({"y9d41p": ["s1", "s2", "s3", "s4"]})
    sweeps[0].by_sensor["s3"].raw_value = None
    out = _integrity(soil, sweeps, by_sensor, sids, sessions=[])
    assert out["partial_sweeps"] == 1


def test_the_single_board_case_is_unchanged() -> None:
    """The case that masked the bug must still behave — this is the regression guard in
    the other direction."""
    soil, sweeps, by_sensor, sids = _fixture({"y9d41p": ["s1", "s2", "s3", "s4"]})
    out = _integrity(soil, sweeps, by_sensor, sids, sessions=[])
    assert out["partial_sweeps"] == 0 and out["sweeps"] == 5


def test_count_gap_stays_per_sensor_and_is_zero_when_boards_are_even() -> None:
    """AC4: cross-check the same-shaped assumption elsewhere. `count_min`/`count_max`
    are per-SENSOR row counts, which are legitimately greenhouse-wide — two boards
    sweeping evenly give every sensor the same count, so count_gap is 0 and the panel's
    other warning does not inherit the same defect."""
    soil, sweeps, by_sensor, sids = _fixture(
        {"y9d41p": ["s1", "s2", "s3", "s4"], "8gtt1h": ["s1", "s2", "s3", "s4"]}
    )
    out = _integrity(soil, sweeps, by_sensor, sids, sessions=[])
    assert out["count_min"] == out["count_max"] == 5
    assert out["count_gap"] == 0
