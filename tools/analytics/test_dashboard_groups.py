"""Tests for per-device grouping (#583) - the #575 spec's eight rules at the
data layer: FENCE (device+channel identity, never merged), ORDER (registry
first-seen, state never re-sorts), COLLAPSE (single device = today's exact
keys), PER-DEVICE header fields, STATES (viewer-clock inputs, not baked ages),
IDENTITY (registry name, no MAC/IP leakage), HONESTY (NO_SIGNAL gates the
band). NO % needs no new test - nothing here emits a percentage.
"""

from __future__ import annotations

from pathlib import Path

from tools.analytics.dashboard import build_context, filter_channels
from tools.analytics.device_registry import Device, Registry
from tools.analytics.parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=test123  run=grouptest\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _soil(
    ts: str,
    device: str,
    sid: str,
    raw: int,
    *,
    quality: str = "OK",
    payload: str = "level=well watered;gpio=36",
) -> str:
    local = ts.replace("Z", "")
    return f"plants.soil,{ts},{local},sess1,{device},{sid},{raw},{quality},{payload}\n"


def _write(tmp_path: Path, rows: list[str], name: str = "a.csv") -> Path:
    p = tmp_path / name
    p.write_text(_HEADER + _COLS + "".join(rows), encoding="utf-8")
    return p


def _two_device_rows() -> list[str]:
    return [
        _soil("2026-07-03T00:00:30.000Z", "sprout-classic-01", "s1", 1500),
        _soil("2026-07-03T00:00:30.000Z", "sprout-classic-01", "s2", 1600),
        _soil("2026-07-03T00:00:35.000Z", "sprout-s3-01", "s1", 1900),
    ]


def _registry() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="sprout-classic-01",
                board="esp32dev",
                label="the classic (living room)",
                channels={"s1": {"plant_id": "P01", "plant_name": "Monstera"}},
            ),
            Device(
                device_id="sprout-s3-01",
                board="esp32-s3-devkitc-1",
                label="the S3 (shelf)",
                channels={},
                base_url="http://sprout-s3.local",
            ),
        ]
    )


# --------------------------------------------------------------------------- #
# FENCE: (device, channel) identity - two devices' s1 never merge
# --------------------------------------------------------------------------- #


def test_fence_two_devices_same_channel_are_two_cards(tmp_path: Path) -> None:
    log = _write(tmp_path, _two_device_rows())
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    ids = sorted(s["id"] for s in ctx["sensors"])
    assert ids == ["s1@sprout-classic-01", "s1@sprout-s3-01", "s2@sprout-classic-01"]
    s1_classic = next(s for s in ctx["sensors"] if s["id"] == "s1@sprout-classic-01")
    s1_s3 = next(s for s in ctx["sensors"] if s["id"] == "s1@sprout-s3-01")
    assert s1_classic["raw_last"] == 1500 and s1_s3["raw_last"] == 1900
    assert s1_classic["sensor_id"] == s1_s3["sensor_id"] == "s1"
    # attribution still binds to the REAL channel token, per device
    assert s1_classic["plant_name"] == "Monstera" and s1_s3["plant_name"] is None
    # distinct colours: they're different plants on one chart
    assert s1_classic["color"] != s1_s3["color"]


def test_collapse_single_device_keys_are_unchanged(tmp_path: Path) -> None:
    """COLLAPSE: today's one-Sprout dashboard is the single-device case -
    bare sensor-id keys, byte-identical to the pre-#583 contract."""
    log = _write(
        tmp_path,
        [
            _soil("2026-07-03T00:00:30.000Z", "sprout-classic-01", "s1", 1500),
            _soil("2026-07-03T00:00:30.000Z", "sprout-classic-01", "s2", 1600),
        ],
    )
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    assert sorted(s["id"] for s in ctx["sensors"]) == ["s1", "s2"]
    assert len(ctx["devices"]) == 1


# --------------------------------------------------------------------------- #
# ORDER + PER-DEVICE + IDENTITY: the group headers
# --------------------------------------------------------------------------- #


def test_groups_keep_registry_order_and_registry_identity(tmp_path: Path) -> None:
    # data order is s3-first here; the registry lists classic first -> ORDER wins
    rows = list(reversed(_two_device_rows()))
    log = _write(tmp_path, rows)
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    devs = ctx["devices"]
    assert [d["device_id"] for d in devs] == ["sprout-classic-01", "sprout-s3-01"]
    classic, s3 = devs
    assert classic["name"] == "the classic (living room)"  # IDENTITY: friendly name
    assert s3["hostname"] == "sprout-s3.local"  # from base_url, scheme stripped
    assert classic["hostname"] is None  # tethered: no hostname claimed
    assert s3["board"] == "esp32-s3-devkitc-1"
    assert classic["sensors"] == ["s1@sprout-classic-01", "s2@sprout-classic-01"]
    assert s3["sensors"] == ["s1@sprout-s3-01"]


def test_unregistered_device_shows_its_device_id_honestly(tmp_path: Path) -> None:
    log = _write(
        tmp_path,
        [
            _soil("2026-07-03T00:00:30.000Z", "mystery-esp32", "s1", 1500),
            _soil("2026-07-03T00:00:31.000Z", "sprout-classic-01", "s1", 1501),
        ],
    )
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    # registry devices first, then unregistered in data order
    assert [d["device_id"] for d in ctx["devices"]] == [
        "sprout-classic-01",
        "mystery-esp32",
    ]
    mystery = ctx["devices"][1]
    assert mystery["name"] == "mystery-esp32"  # honest: no invented friendly name
    assert mystery["board"] is None and mystery["hostname"] is None


def test_states_inputs_are_viewer_clock_ready(tmp_path: Path) -> None:
    """STATES: the server exposes last_seen_utc + raw time_source; the client
    derives online/offline/syncing and stamps ages with ITS clock - no baked
    server-side age that would go stale in a static snapshot."""
    log = _write(
        tmp_path,
        [
            _soil(
                "2026-07-03T00:00:35.000Z",
                "sprout-s3-01",
                "s1",
                1900,
                payload="level=OK;gpio=4;transport=wifi_poll;"
                "device_seq=9;time_source=device_uptime",
            ),
            _soil("2026-07-03T00:00:30.000Z", "sprout-classic-01", "s1", 1500),
        ],
    )
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    s3 = next(d for d in ctx["devices"] if d["device_id"] == "sprout-s3-01")
    assert s3["last_seen_utc"] == "2026-07-03T00:00:35Z"
    assert s3["time_source"] == "device_uptime"  # raw vocabulary, client maps it
    assert s3["transport"] == "wifi"  # from the persisted transport marker
    classic = next(d for d in ctx["devices"] if d["device_id"] == "sprout-classic-01")
    assert classic["time_source"] is None  # host-stamped
    assert classic["transport"] == "serial"


def test_no_ip_or_mac_in_the_header_payload(tmp_path: Path) -> None:
    """IDENTITY: never a MAC; and an IP-shaped base_url passes through only as
    the operator configured it - nothing invents or fabricates one."""
    reg = Registry(
        devices=[
            Device(
                device_id="sprout-s3-01",
                board=None,
                label=None,
                channels={},
                base_url="http://192.168.1.42",
            )
        ]
    )
    log = _write(
        tmp_path, [_soil("2026-07-03T00:00:30.000Z", "sprout-s3-01", "s1", 1500)]
    )
    ctx = build_context(parse_files([str(log)]), registry=reg)
    d = ctx["devices"][0]
    assert d["hostname"] == "192.168.1.42"  # exactly what the operator wrote
    assert "mac" not in {k.lower() for k in d}  # no MAC field exists at all


# --------------------------------------------------------------------------- #
# HONESTY: NO_SIGNAL gates the band; cal_provisional from the device's own claim
# --------------------------------------------------------------------------- #


def test_no_signal_earns_no_band(tmp_path: Path) -> None:
    log = _write(
        tmp_path,
        [
            _soil(
                "2026-07-03T00:00:30.000Z",
                "sprout-s3-01",
                "s1",
                1234,  # floating-pin noise - present in data, gated on the card
                quality="NO_SIGNAL",
                payload="gpio=4",
            )
        ],
    )
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    s = ctx["sensors"][0]
    assert s["no_signal"] is True
    assert s["band_ui"] == "no signal" and s["mood"] == "Unwired"
    assert s["band_color"] == "#9A8480"  # q-nosignal grey, never a band colour


def test_cal_provisional_comes_from_the_devices_own_header(tmp_path: Path) -> None:
    header = (
        "# fw=0.8.0  git=t  run=r\n"
        "# board cal: PLACEHOLDER (classic endpoints, not bench-verified "
        "for this board - #443)\n"
        "# device_id=sprout-s3-01\n"
        "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
    )
    p = tmp_path / "s3.csv"
    p.write_text(
        header + _COLS + _soil("2026-07-03T00:00:30.000Z", "sprout-s3-01", "s1", 1500),
        encoding="utf-8",
    )
    q = _write(
        tmp_path,
        [_soil("2026-07-03T00:00:30.000Z", "sprout-classic-01", "s1", 1500)],
        name="classic.csv",
    )
    ctx = build_context(parse_files([str(p), str(q)]), registry=_registry())
    by_id = {d["device_id"]: d for d in ctx["devices"]}
    assert by_id["sprout-s3-01"]["cal_provisional"] is True
    assert by_id["sprout-classic-01"]["cal_provisional"] is False


# --------------------------------------------------------------------------- #
# the device-scoped channel filter (FENCE at the toggle layer)
# --------------------------------------------------------------------------- #


def test_filter_channels_device_scoped_tokens(tmp_path: Path) -> None:
    log = _write(tmp_path, _two_device_rows())
    data = parse_files([str(log)])
    scoped = filter_channels(data, ["s1@sprout-s3-01"])
    assert len(scoped.readings) == 1
    assert scoped.readings[0].device_id == "sprout-s3-01"
    plain = filter_channels(data, ["s1"])  # plain token still matches all devices
    assert len(plain.readings) == 2


# --------------------------------------------------------------------------- #
# #1432 — the v5 token generations of one channel collapse to ONE card
# --------------------------------------------------------------------------- #
def _mixed_generation_rows() -> list[str]:
    """One physical channel across the flash: v4 `s1` rows, then v5 `ch2` rows.
    s1 folds to ch2 (parse_v1.canonical_channel), so these are the SAME channel."""
    # contiguous (one run, no multi-day gap) so all four sit in the plot window —
    # the flash lands mid-run: the first two rows are v4, the last two v5.
    return [
        _soil("2026-07-21T00:00:30.000Z", "sprout-classic-01", "s1", 1500),
        _soil("2026-07-21T02:00:30.000Z", "sprout-classic-01", "s1", 1560),
        _soil("2026-07-21T04:00:30.000Z", "sprout-classic-01", "ch2", 1620),
        _soil("2026-07-21T06:00:30.000Z", "sprout-classic-01", "ch2", 1680),
    ]


def test_a_channel_spanning_the_flash_renders_one_card_not_two(tmp_path: Path) -> None:
    """#1432: the Home claimed 19 plants for 11 because s1@dev and ch2@dev — the same
    channel — each made a card. They must collapse to one."""
    reg = Registry(
        devices=[
            Device(
                device_id="sprout-classic-01",
                board="esp32-classic",
                label="the classic",
                channels={"ch2": {"plant_id": "P11", "plant_name": "Fern"}},
            ),
            Device(
                device_id="sprout-s3-01",
                board="esp32-s3",
                label="the S3",
                channels={},
                base_url="http://x",
            ),
        ]
    )
    data = parse_files([str(_write(tmp_path, _mixed_generation_rows()))])
    ctx = build_context(data, registry=reg)
    fern = [s for s in ctx["sensors"] if s.get("plant_id") == "P11"]
    assert len(fern) == 1, (
        f"one physical channel must be one card; got {len(fern)} "
        f"({[s['sensor_id'] for s in fern]}) — the #1432 double"
    )
    # the survivor shows the CURRENT identity (the latest token, ch2 post-flash)
    assert fern[0]["sensor_id"] == "ch2"
    # and it carries BOTH generations' readings, not just the latest group's
    (dataset,) = [d for d in ctx["trajectory"]["datasets"] if d["id"] == fern[0]["id"]]
    assert len(dataset["points"]) == 4, "all four readings (both generations), one card"


def test_a_single_generation_channel_is_unchanged(tmp_path: Path) -> None:
    """The merge must fire ONLY when two generations coexist — a plain window keeps its
    raw token and its exact prior shape (the #583 COLLAPSE rule intact)."""
    rows = [
        _soil("2026-07-21T00:00:30.000Z", "sprout-classic-01", "s1", 1500),
        _soil("2026-07-21T06:00:30.000Z", "sprout-classic-01", "s1", 1560),
    ]
    reg = Registry(
        devices=[
            Device(
                device_id="sprout-classic-01",
                board="esp32-classic",
                label="c",
                channels={"s1": {"plant_id": "P01", "plant_name": "Monstera"}},
            )
        ]
    )
    ctx = build_context(parse_files([str(_write(tmp_path, rows))]), registry=reg)
    (s,) = [s for s in ctx["sensors"] if s.get("plant_id") == "P01"]
    assert s["sensor_id"] == "s1"  # untouched — no second generation to merge
