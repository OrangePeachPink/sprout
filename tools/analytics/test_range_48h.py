"""#821 — the 48h range chip: a new token between 1 day and 7 days that reuses the
existing range machinery exactly (no bespoke logic), driving every surface that
reads the range (the server RANGE_HOURS window, the client RANGE_H map, the chip).
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
_EDGE = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def _row(ts: datetime, raw: int) -> str:
    u = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return f"plants.soil,{u},{u[:-1]},s1,dev1,s1,{raw},OK,level=OK\n"


def test_48h_token_value() -> None:
    assert RANGE_HOURS["48h"] == 48.0  # 2 days, hours like every other window


def test_48h_sits_between_24h_and_7d() -> None:
    keys = list(RANGE_HOURS)
    assert keys.index("24h") < keys.index("48h") < keys.index("7d")


def test_48h_windows_with_the_shared_semantics(tmp_path: Path) -> None:
    # rows at now, -30h, -60h; the 48h window keeps the first two, drops the -60h
    # one — the SAME filter_since path 24h/7d use, no special-casing.
    rows = (
        _row(_EDGE, 2400)
        + _row(_EDGE - timedelta(hours=30), 2500)
        + _row(_EDGE - timedelta(hours=60), 2600)
    )
    p = tmp_path / "a.csv"
    p.write_text(_HEADER + _COLS + rows, encoding="utf-8")
    data = parse_files([str(p)])
    kept = filter_since(data, RANGE_HOURS["48h"])
    raws = sorted(r.raw_value for r in kept.readings)
    assert raws == [2400, 2500]  # the -60h reading is outside the 48h window


def test_every_range_surface_carries_48h() -> None:
    # the client map + the chip must both exist, so the server window, the JS
    # RANGE_H (static-zoom), and the selectable chip all drive off one token.
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "'48h': 48" in html  # RANGE_H client map
    assert 'data-r="48h"' in html  # the selectable chip
    # ordered between the 24h and 7d chips, matching the server map + directive
    assert (
        html.index('data-r="24h"')
        < html.index('data-r="48h"')
        < html.index('data-r="7d"')
    )
