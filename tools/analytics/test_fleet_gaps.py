#!/usr/bin/env python3
"""#1431 - the dropout comparison instrument reproduces Firmware's method.

The load-bearing property is the SHARED-vs-UNIQUE split: a host/logger outage stops
every board at once and is NOT a board's fault, so subtracting it is what leaves the
board-unique dropout count - the number the before/after experiment turns on. A tool
that counted a shared outage against the C5 would inflate its dropouts and could fake a
"fix" when the band change did nothing.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_gaps import partition_shared, report, summarize, sweep_gaps

T0 = datetime(2026, 7, 8, tzinfo=timezone.utc)


class _Row:
    def __init__(self, device_id, minute):
        self.device_id = device_id
        self.sensor_id = "s1"
        self.timestamp_utc = T0 + timedelta(minutes=minute)


def _sweeps(device_id, minutes):
    return [_Row(device_id, m) for m in minutes]


def test_a_clean_30s_cadence_has_no_gaps() -> None:
    rows = [_Row("dev", 0.5 * i) for i in range(20)]  # every 30 s
    assert sweep_gaps(rows) == {"dev": []}


def test_a_gap_over_the_threshold_is_found_under_it_is_not() -> None:
    # sweeps at 0, then 3 min (a gap), then 3.5 (fine), then 6 (another gap)
    rows = _sweeps("dev", [0, 3, 3.5, 6])
    gaps = sweep_gaps(rows)["dev"]
    assert len(gaps) == 2  # the two >2min jumps; the 0.5min step is not a gap


def test_a_shared_host_outage_is_not_charged_to_either_board() -> None:
    """Both boards stop at the same instant - a host outage. It must land in `shared`,
    and in NEITHER board's unique count."""
    minutes = [0, 3, 3.5]  # one identical gap (0 -> 3) on both boards
    dg = sweep_gaps(_sweeps("classic", minutes) + _sweeps("c5", minutes))
    part = partition_shared(dg)
    assert len(part["shared"]) == 1
    assert part["unique"]["classic"] == []
    assert part["unique"]["c5"] == []


def test_a_board_unique_dropout_is_charged_only_to_that_board() -> None:
    """The C5 drops out while the classic keeps logging - the #1431 signature. It is
    the C5's unique gap, not shared."""
    classic = _sweeps("classic", [0.5 * i for i in range(20)])  # clean
    c5 = _sweeps("c5", [0, 3, 3.5])  # one 3-min dropout, classic has none there
    part = partition_shared(sweep_gaps(classic + c5))
    assert part["shared"] == []
    assert len(part["unique"]["c5"]) == 1
    assert part["unique"]["classic"] == []


def test_the_split_matches_firmwares_shape_shared_big_plus_c5_only_small() -> None:
    """The exact #1431 shape in miniature: a big shared host outage on both boards PLUS
    several small C5-only dropouts. The verdict number is the C5-unique count, and the
    shared outage must not pad it."""
    big = [0, 60]  # a 60-min host outage both boards share
    classic = _sweeps("classic", [*big, *[60.5 + 0.5 * i for i in range(20)]])
    # the C5 shares the big one, then adds three ~3-min dropouts of its own
    c5 = _sweeps("c5", [*big, 60.5, 63.5, 67, 70.5])
    part = partition_shared(sweep_gaps(classic + c5))
    assert len(part["shared"]) == 1  # the host outage, counted once
    assert summarize(part["shared"])["max_min"] >= 60
    assert len(part["unique"]["c5"]) == 3  # the C5-only dropouts
    assert part["unique"]["classic"] == []  # the classic's only gap was the shared one


def test_summarize_bands_the_durations_the_way_the_verdict_reads() -> None:
    gaps = [
        (T0, T0 + timedelta(minutes=3), 3.0),
        (T0, T0 + timedelta(minutes=4), 4.0),
        (T0, T0 + timedelta(minutes=8), 8.0),
        (T0, T0 + timedelta(minutes=90), 90.0),
    ]
    s = summarize(gaps)
    assert s["count"] == 4
    assert s["bands"] == {"2-5m": 2, "5-15m": 1, "15-60m": 0, ">60m": 1}
    assert s["max_min"] == 90.0


def test_report_is_shaped_for_the_before_after_comparison() -> None:
    classic = _sweeps("classic", [0.5 * i for i in range(20)])
    c5 = _sweeps("c5", [0, 3, 3.5])
    r = report(classic + c5)
    assert "shared_outages" in r and "per_device_unique" in r
    assert r["per_device_unique"]["c5"]["count"] == 1
    assert r["per_device_unique"]["classic"]["count"] == 0
