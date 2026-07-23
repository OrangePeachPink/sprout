"""#1191 — the 14d range chip: the sawtooth-finder window (maintainer ask). A new token
between 7d and 30d that reuses the existing range machinery exactly (no bespoke logic),
driving every surface that reads the range (the server RANGE_HOURS window, the client
RANGE_H map, the selectable chip). A maintainer-ruled bridge on parity-then-retire
Classic (ADR-0033) until the rollup tier lands.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.dashboard import RANGE_HOURS, TEMPLATE, filter_since
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id=s1\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)
_EDGE = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


def _row(ts: datetime, raw: int) -> str:
    u = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return f"plants.soil,{u},{u[:-1]},s1,dev1,s1,{raw},OK,level=OK\n"


def test_14d_token_value() -> None:
    assert RANGE_HOURS["14d"] == 24.0 * 14  # 336 h, hours like every other window


def test_14d_sits_between_7d_and_30d() -> None:
    keys = list(RANGE_HOURS)
    assert keys.index("7d") < keys.index("14d") < keys.index("30d")


def test_14d_catches_a_nine_day_old_sawtooth_that_7d_misses(tmp_path: Path) -> None:
    # the whole point: an 8-10-day watering cycle. A re-water 9 days ago is INSIDE the
    # 14d window and OUTSIDE 7d — the same filter_since path every window uses.
    rows = (
        _row(_EDGE, 2400)
        + _row(_EDGE - timedelta(days=9), 1200)  # the re-water edge, 9 days back
        + _row(_EDGE - timedelta(days=20), 2600)  # older than 14d, dropped
    )
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + rows, encoding="utf-8")
    data = parse_files([str(p)])
    kept_14 = [r.raw_value for r in filter_since(data, RANGE_HOURS["14d"]).readings]
    kept_7 = [r.raw_value for r in filter_since(data, RANGE_HOURS["7d"]).readings]
    assert 1200 in kept_14  # the sawtooth edge is visible at 14d
    assert 1200 not in kept_7  # ...but 7d just misses it (the operational gap)
    assert 2600 not in kept_14  # the >14d reading is outside the window


def test_every_range_surface_carries_14d() -> None:
    # the client map + the chip must both exist so the server window, the JS RANGE_H
    # (static-zoom), and the selectable chip all drive off one token.
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "'14d': 336" in html  # RANGE_H client map
    assert 'data-r="14d"' in html  # the selectable chip
    # ordered between the 7d and 30d chips, matching the server map + directive
    assert (
        html.index('data-r="7d"')
        < html.index('data-r="14d"')
        < html.index('data-r="30d"')
    )
