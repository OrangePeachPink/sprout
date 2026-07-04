"""Tests for device identity continuity (#602): a renamed board's history
coalesces into one card at display time - raw records untouched, provenance
preserved, the merge visible on the header (never silent).

The scenario is the real bench finding (2026-07-03): one classic board, three
identities over its life (plants_esp32_f4e9d4 -> "Sprout ESP32" -> classic),
rendering as three cards - two of them "offline" ghosts.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dashboard import build_context, filter_channels
from device_registry import Device, Registry, load_registry
from parse_v1 import parse_files

_HEADER = (
    "# fw=0.8.0  git=test123  run=identity\n"
    "# cal bounds(dry>wet): 3050 2140 1830 1520 1150 1050  [moist% 900..3400]\n"
)
_COLS = (
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _soil(ts: str, device: str, sid: str, raw: int) -> str:
    local = ts.replace("Z", "")
    return (
        f"plants.soil,{ts},{local},sess1,{device},{sid},{raw},OK,"
        "level=well watered;gpio=36\n"
    )


def _classic_three_lives(tmp_path: Path) -> Path:
    """The bench finding, verbatim: one board, three identity eras."""
    p = tmp_path / "lives.csv"
    p.write_text(
        _HEADER
        + _COLS
        + _soil("2026-06-24T00:00:30.000Z", "plants_esp32_f4e9d4", "s1", 1500)
        + _soil("2026-06-28T00:00:30.000Z", "Sprout ESP32", "s1", 1550)
        + _soil("2026-07-03T00:00:30.000Z", "classic", "s1", 1600),
        encoding="utf-8",
    )
    return p


def _registry() -> Registry:
    return Registry(
        devices=[
            Device(
                device_id="classic",
                board="esp32dev",
                label=None,
                name="the classic",
                channels={"s1": {"plant_id": "P01", "plant_name": "Monstera"}},
                previous_ids=("plants_esp32_f4e9d4", "Sprout ESP32"),
            )
        ]
    )


# --------------------------------------------------------------------------- #
# canonical_for - the remap + its guards
# --------------------------------------------------------------------------- #


def test_canonical_for_maps_prior_ids_and_passes_through_unknown() -> None:
    reg = _registry()
    assert reg.canonical_for("plants_esp32_f4e9d4") == "classic"
    assert reg.canonical_for("Sprout ESP32") == "classic"
    assert reg.canonical_for("classic") == "classic"
    assert reg.canonical_for("some-other-board") == "some-other-board"
    assert reg.canonical_for(None) is None
    assert reg.canonical_for("") == ""


def test_a_live_device_id_is_never_swallowed_as_an_alias() -> None:
    # misconfiguration guard: device B lists device A's CURRENT id as its past
    reg = Registry(
        devices=[
            Device(device_id="a", board=None, label=None, channels={}),
            Device(
                device_id="b",
                board=None,
                label=None,
                channels={},
                previous_ids=("a",),
            ),
        ]
    )
    assert reg.canonical_for("a") == "a"  # a stays itself, never becomes b


def test_duplicate_alias_claims_resolve_first_in_registry_order() -> None:
    reg = Registry(
        devices=[
            Device(
                device_id="first",
                board=None,
                label=None,
                channels={},
                previous_ids=("old",),
            ),
            Device(
                device_id="second",
                board=None,
                label=None,
                channels={},
                previous_ids=("old",),
            ),
        ]
    )
    assert reg.canonical_for("old") == "first"  # deterministic, documented


def test_previous_ids_parse_from_config_and_filter_junk(tmp_path: Path) -> None:
    import json

    p = tmp_path / "devices.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "devices": [
                    {
                        "device_id": "classic",
                        "previous_ids": ["old-1", "", 42, "old-2"],
                        "channels": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    reg = load_registry(p)
    assert reg.device("classic").previous_ids == ("old-1", "old-2")
    assert reg.canonical_for("old-1") == "classic"


# --------------------------------------------------------------------------- #
# the dashboard: one board, three lives -> ONE card with continuous history
# --------------------------------------------------------------------------- #


def test_three_identities_coalesce_to_one_card(tmp_path: Path) -> None:
    log = _classic_three_lives(tmp_path)
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    # ONE sensor entry (single coalesced device -> bare key, COLLAPSE holds)
    assert [s["id"] for s in ctx["sensors"]] == ["s1"]
    s1 = ctx["sensors"][0]
    assert s1["n"] == 3  # continuous history across all three eras
    assert s1["raw_last"] == 1600  # the newest (current-identity) reading
    assert s1["device_id"] == "classic"
    assert s1["plant_name"] == "Monstera"  # attribution through the canonical id
    # ONE device group, and the coalesce is VISIBLE, never silent
    assert len(ctx["devices"]) == 1
    d = ctx["devices"][0]
    assert d["device_id"] == "classic"
    assert d["also_reported_as"] == ["Sprout ESP32", "plants_esp32_f4e9d4"]
    assert d["last_seen_utc"] == "2026-07-03T00:00:30Z"  # from the newest era


def test_raw_rows_keep_their_truthful_device_ids(tmp_path: Path) -> None:
    """The provenance law: coalescing is display-time only - the parsed rows
    still carry exactly what the board reported on the wire at the time."""
    log = _classic_three_lives(tmp_path)
    data = parse_files([str(log)])
    build_context(data, registry=_registry())  # grouping must not mutate rows
    assert sorted({r.device_id for r in data.readings}) == [
        "Sprout ESP32",
        "classic",
        "plants_esp32_f4e9d4",
    ]


def test_unrelated_devices_do_not_coalesce(tmp_path: Path) -> None:
    log = tmp_path / "two.csv"
    log.write_text(
        _HEADER
        + _COLS
        + _soil("2026-07-03T00:00:30.000Z", "classic", "s1", 1600)
        + _soil("2026-07-03T00:00:31.000Z", "other-board", "s1", 1700),
        encoding="utf-8",
    )
    ctx = build_context(parse_files([str(log)]), registry=_registry())
    assert sorted(s["id"] for s in ctx["sensors"]) == [
        "s1@classic",
        "s1@other-board",
    ]  # the fence still fences - continuity never merges different boards


def test_scoped_channel_filter_matches_the_whole_history(tmp_path: Path) -> None:
    log = tmp_path / "mixed.csv"
    log.write_text(
        _HEADER
        + _COLS
        + _soil("2026-06-28T00:00:30.000Z", "Sprout ESP32", "s1", 1550)
        + _soil("2026-07-03T00:00:30.000Z", "classic", "s1", 1600)
        + _soil("2026-07-03T00:00:31.000Z", "other-board", "s1", 1700),
        encoding="utf-8",
    )
    reg = _registry()
    data = parse_files([str(log)])
    kept = filter_channels(data, ["s1@classic"], canonical=reg.canonical_for)
    # both eras of the classic match; the unrelated board does not
    assert sorted(r.raw_value for r in kept.readings) == [1550, 1600]


# --------------------------------------------------------------------------- #
# fleet logger: writer lineage follows the canonical identity
# --------------------------------------------------------------------------- #


def test_fleet_writer_coalesces_file_lineage_row_stays_truthful(
    tmp_path: Path,
) -> None:
    _LOGGER = Path(__file__).resolve().parents[1] / "logger"
    sys.path.insert(0, str(_LOGGER))
    from fleet_logger import FleetLogger
    from source_adapter import DeviceAdapter

    # the device still reports its OLD identity on the wire (pre-rename cache)
    body = (
        "plants.soil,sessW,Sprout ESP32,0.8.0,60000,UMLIFE_v2_TLC555,"
        "s1,shelf,soil_moisture,1900,,,OK,level=OK;gpio=4;device_seq=7"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    text = (
        "# device_cols: record_type,session_id,device_id,fw,millis_ms,"
        "sensor_model,sensor_id,sensor_position,channel,raw_value,value,unit,"
        "quality_flag,payload\n" + f"{body}*{crc:02X}\n"
    )
    reg = Registry(
        devices=[
            Device(
                device_id="classic",
                board=None,
                label=None,
                channels={},
                base_url="http://a",
                previous_ids=("Sprout ESP32",),
            )
        ]
    )
    fl = FleetLogger(
        str(tmp_path),
        registry=reg,
        adapter_factory=lambda url: DeviceAdapter(url, fetch=lambda u: text),
        log=str,
    )
    assert fl.poll_once() == 1
    files = list(tmp_path.glob("*.csv"))
    assert len(files) == 1
    assert files[0].name.startswith("classic_")  # ONE file lineage, canonical
    row = parse_files([str(files[0])]).readings[0]
    assert row.device_id == "Sprout ESP32"  # the row stays truthful (raw)
