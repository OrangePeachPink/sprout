"""#698 offline/stale gate — a device with no reading within the staleness window
is de-emphasized, its last value labelled 'last seen Nh ago' (never the live
reading), and it drops out of the live/fleet count. Restores automatically when
it comes back. Threshold is the documented, tunable STALE_AFTER_S.

The 0.7.0 install view was cluttered by spare boards (last heard 9-12h ago) still
presenting stale numbers at full prominence - a quiet lie on a monitoring product.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.analytics.dashboard import STALE_AFTER_S, build_context
from tools.analytics.device_registry import Device, Registry
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# schema_version=3  fw=0.7.0  git=abc  session_id={sess}\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "millis_ms,sensor_id,raw_value,quality_flag,payload\n"
)
_NOW = datetime(2026, 7, 5, 12, 0, 0, tzinfo=timezone.utc)


def _row(dev: str, sess: str, ts: datetime, raw: int, sensor: str = "s1") -> str:
    u = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    lo = ts.strftime("%Y-%m-%d %H:%M:%S.000")
    ms = int(ts.timestamp() * 1000) % 10_000_000
    return (
        f"plants.soil,{u},{lo},{sess},{dev},{ms},{sensor},{raw},OK,"
        f"transport=wifi_poll;level=DRY\n"
    )


def _reg() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="live1",
                board="esp32dev",
                label="Live",
                channels={"s1": {"plant_id": "p01", "plant_name": "fern"}},
            ),
            Device(
                device_id="spare9",
                board="esp32dev",
                label="Spare",
                channels={"s1": {"plant_id": "p02", "plant_name": "pothos"}},
            ),
        ]
    )


def _write(tmp_path: Path, sess: str, rows: str) -> str:
    p = tmp_path / f"{sess}.csv"
    p.write_text(_HEADER.format(sess=sess) + _COLS + rows, encoding="utf-8")
    return str(p)


def _build(tmp_path: Path, spare_age: timedelta):
    """Live board reported 20s ago; spare board's last reading is `spare_age` old."""
    live = "".join(
        _row("live1", "sLive", _NOW - timedelta(seconds=s), 2400) for s in (80, 50, 20)
    )
    spare_last = _NOW - spare_age
    spare = "".join(
        _row("spare9", "sSpare", spare_last - timedelta(seconds=s), 3000)
        for s in (40, 20, 0)
    )
    ctx = build_context(
        parse_files(
            [_write(tmp_path, "sLive", live), _write(tmp_path, "sSpare", spare)]
        ),
        registry=_reg(),
        now=_NOW,
    )
    devs = {g["device_id"]: g for g in ctx["devices"]}
    sens = {s["device_id"]: s for s in ctx["sensors"]}
    return ctx, devs, sens


def test_threshold_is_a_documented_tunable_constant(tmp_path: Path) -> None:
    assert isinstance(STALE_AFTER_S, int) and STALE_AFTER_S > 0
    # exposed so the client derives against the ONE canonical window. Use tmp_path
    # (not "."): _build writes fixture CSVs, which must never land in the repo root.
    ctx, _d, _s = _build(tmp_path, timedelta(hours=9))
    assert ctx["meta"]["stale_after_s"] == STALE_AFTER_S
    assert ctx["fleet_health"]["stale_after_s"] == STALE_AFTER_S


def test_long_offline_device_is_stale_and_labeled(tmp_path: Path) -> None:
    _ctx, devs, sens = _build(tmp_path, spare_age=timedelta(hours=9))
    assert devs["spare9"]["stale"] is True
    assert devs["spare9"]["age_s"] >= 9 * 3600
    # its last value carries the age + last_seen stamp (the label source), so the
    # UI can say "last seen 9h ago" instead of showing it as the live reading
    assert sens["spare9"]["stale"] is True
    assert sens["spare9"]["age_s"] >= 9 * 3600
    assert sens["spare9"]["last_seen_utc"] is not None
    assert sens["spare9"]["raw_last"] == 3000  # value preserved, not hidden


def test_live_device_is_not_stale(tmp_path: Path) -> None:
    _ctx, devs, sens = _build(tmp_path, spare_age=timedelta(hours=9))
    assert devs["live1"]["stale"] is False
    assert sens["live1"]["stale"] is False
    assert devs["live1"]["age_s"] < STALE_AFTER_S


def test_just_stale_boundary(tmp_path: Path) -> None:
    # one second past the window -> stale; well within -> live (restore path)
    _c, devs_over, _s = _build(tmp_path, spare_age=timedelta(seconds=STALE_AFTER_S + 1))
    assert devs_over["spare9"]["stale"] is True
    _c, devs_under, _s = _build(
        tmp_path, spare_age=timedelta(seconds=STALE_AFTER_S - 30)
    )
    assert devs_under["spare9"]["stale"] is False  # came back -> full presentation


def test_stale_device_excluded_from_online_count(tmp_path: Path) -> None:
    ctx, _d, _s = _build(tmp_path, spare_age=timedelta(hours=12))
    fh = ctx["fleet_health"]
    assert fh["devices_total"] == 2
    assert fh["devices_online"] == 1  # only the live board
    assert fh["devices_stale"] == 1  # the spare drops out of the live count


def test_raw_rows_untouched(tmp_path: Path) -> None:
    data = parse_files(
        [
            _write(
                tmp_path,
                "sSpare",
                _row("spare9", "sSpare", _NOW - timedelta(hours=9), 3000),
            )
        ]
    )
    assert len(data.readings) == 1
    assert data.readings[0].raw_value == 3000  # the gate reads, never rewrites
