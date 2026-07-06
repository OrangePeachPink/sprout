"""Tests for the fleet logger (#582) - the poll->persist wire.

Pins the four named design decisions: persistence through the shared writer,
cadence-loop mechanics, restart dedupe seeded from disk, and provenance
(fleet logger_version + transport=wifi_poll payload marker, no IP on disk).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fleet_logger import FLEET_LOGGER_VERSION, FleetLogger, seed_store_from_disk

_ANALYTICS = Path(__file__).resolve().parents[1] / "analytics"
sys.path.insert(0, str(_ANALYTICS))
from device_registry import Device, Registry  # noqa: E402
from ingest_store import Store  # noqa: E402
from parse_v1 import parse_file, parse_files  # noqa: E402
from source_adapter import DeviceAdapter  # noqa: E402

_DEVICE_COLS = (
    "# device_cols: record_type,session_id,device_id,fw,millis_ms,sensor_model,"
    "sensor_id,sensor_position,channel,raw_value,value,unit,quality_flag,payload"
)


def _line(
    *,
    device: str = "sprout-s3-01",
    sensor: str = "s1",
    raw: int = 1900,
    millis: int = 60000,
    seq: int | None = 101,
    session: str = "sessW",
) -> str:
    payload = "level=needs water;gpio=4"
    if seq is not None:
        payload += f";device_seq={seq};time_source=device_uptime"
    body = (
        f"plants.soil,{session},{device},0.8.0,{millis},UMLIFE_v2_TLC555,"
        f"{sensor},shelf,soil_moisture,{raw},,,OK,{payload}"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    return f"{body}*{crc:02X}"


def _served(text_by_url: dict[str, str]):
    """(registry, adapter_factory) serving canned /telemetry text per base_url."""
    registry = Registry(
        devices=[
            Device(
                device_id=f"dev-{i}",
                board="esp32-s3-devkitc-1",
                label=None,
                channels={},
                base_url=url,
            )
            for i, url in enumerate(text_by_url)
        ]
    )

    def factory(base_url: str):
        return DeviceAdapter(base_url, fetch=lambda url, b=base_url: text_by_url[b])

    return registry, factory


def _env_line(
    *,
    device: str = "sprout-s3-01",
    channel: str = "ambient_temp",
    value: str = "21.5",
    unit: str = "degC",
    model: str = "SHT45",
    millis: int = 60000,
) -> str:
    """One served plants.env row (the on-board SHT45's ambient reading)."""
    body = (
        f"plants.env,sessW,{device},0.8.0,{millis},{model},"
        f"sht45,shelf,{channel},,{value},{unit},OK,"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    return f"{body}*{crc:02X}"


def _response(*lines: str) -> str:
    return _DEVICE_COLS + "\n" + "\n".join(lines) + "\n"


def _soil_rows(logdir: Path) -> list:
    return [
        r
        for r in parse_files([str(logdir)]).readings
        if r.record_type.startswith("plants.soil")
    ]


# --------------------------------------------------------------------------- #
# #701: the fleet logger fills soil rows with the board's plant-local SHT45
# --------------------------------------------------------------------------- #


def test_fleet_fills_soil_rows_from_the_onboard_sht45(tmp_path: Path) -> None:
    resp = _response(
        _env_line(device="dev-0", channel="ambient_temp", value="21.5"),
        _env_line(device="dev-0", channel="ambient_rh", value="55.0", unit="pct"),
        _line(device="dev-0", sensor="s1", raw=1900),
    )
    reg, factory = _served({"http://a": resp})
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    assert fl.poll_once() >= 1
    soil = _soil_rows(tmp_path)
    assert soil
    r = soil[-1]
    # the join-free ADR-0023 fill now reaches the untethered spine
    assert r.temp_context_c == 21.5
    assert r.rh_context_pct == 55.0
    assert r.context_source == "sht45_onrig"  # payload tag (k=v, no new column)


# --------------------------------------------------------------------------- #
# #712: host session-tolerance — a reset-driven session change is not churn
# --------------------------------------------------------------------------- #


def test_reset_driven_session_change_stays_one_file_lineage(tmp_path: Path) -> None:
    # the reconnect storm's host half (#712): a device resets mid-run (port-reopen
    # auto-reset / crash loop - the firmware fix is #566) -> a NEW session_id + a
    # device_seq reset. The host must TOLERATE it, not churn: ONE file lineage per
    # device (the writer keys on device, never session - RotatingCsv rolls on
    # size/UTC-day, never a session change), and BOTH reboot epochs preserved
    # (session_id is load-bearing in the dedupe key - #703).
    responses = iter(
        [
            _response(_line(device="dev-0", raw=1900, seq=5, session="sessA")),
            _response(_line(device="dev-0", raw=1950, seq=1, session="sessB")),  # reset
        ]
    )
    reg = Registry(
        devices=[
            Device(device_id="dev-0", board=None, label=None, channels={}, base_url="u")
        ]
    )
    fl = FleetLogger(
        str(tmp_path),
        registry=reg,
        adapter_factory=lambda url: DeviceAdapter(url, fetch=lambda u: next(responses)),
        log=str,
    )
    fl.poll_once()  # session A
    fl.poll_once()  # session B — the reset
    assert len(list(tmp_path.glob("*.csv"))) == 1  # no per-session file churn
    soil = _soil_rows(tmp_path)
    assert {r.session_id for r in soil} == {"sessA", "sessB"}  # both epochs kept
    assert len(soil) == 2  # neither reboot reading dropped


def test_a_within_session_replay_is_still_deduped(tmp_path: Path) -> None:
    # the tolerance must not weaken dedupe: the SAME (session, device_seq) served
    # again (a store-and-forward replay) is still dropped exactly once.
    responses = iter(
        [
            _response(_line(device="dev-0", raw=1900, seq=5, session="sessA")),
            _response(
                _line(device="dev-0", raw=1900, seq=5, session="sessA")
            ),  # replay
        ]
    )
    reg = Registry(
        devices=[
            Device(device_id="dev-0", board=None, label=None, channels={}, base_url="u")
        ]
    )
    fl = FleetLogger(
        str(tmp_path),
        registry=reg,
        adapter_factory=lambda url: DeviceAdapter(url, fetch=lambda u: next(responses)),
        log=str,
    )
    fl.poll_once()
    fl.poll_once()  # exact replay
    assert len(_soil_rows(tmp_path)) == 1  # the replay is dropped, not churned


def test_soil_rows_stay_honestly_empty_with_no_env(tmp_path: Path) -> None:
    resp = _response(_line(device="dev-0", sensor="s1", raw=1900))
    reg, factory = _served({"http://a": resp})
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    fl.poll_once()
    r = _soil_rows(tmp_path)[-1]
    assert r.temp_context_c is None and r.rh_context_pct is None
    assert r.context_source is None  # nothing fresh -> honestly empty


def test_context_never_cross_fills_between_boards(tmp_path: Path) -> None:
    # device A has an SHT45; device B does not. B's soil must NOT borrow A's
    # ambient - the per-device fillers keep each board's context its own.
    reg, factory = _served(
        {
            "http://a": _response(
                _env_line(device="dev-0", channel="ambient_temp", value="21.5"),
                _line(device="dev-0", sensor="s1", raw=1900),
            ),
            "http://b": _response(_line(device="dev-1", sensor="s1", raw=2000)),
        }
    )
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    fl.poll_once()
    by_dev = {r.device_id: r for r in _soil_rows(tmp_path)}
    assert by_dev["dev-0"].temp_context_c == 21.5  # its own SHT45 filled it
    assert by_dev["dev-1"].temp_context_c is None  # no cross-fill from dev-0


# --------------------------------------------------------------------------- #
# poll -> persist (decisions 1 + 4)
# --------------------------------------------------------------------------- #


def test_poll_persists_rows_with_fleet_provenance(tmp_path: Path) -> None:
    reg, factory = _served({"http://a": _response(_line(sensor="s1"))})
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    assert fl.poll_once() == 1

    files = list(tmp_path.glob("*.csv"))
    assert len(files) == 1
    assert files[0].name.startswith("sprout-s3-01_")  # device_id names the file
    r = parse_file(files[0]).readings[0]
    # decision 4, all three provenance surfaces:
    assert r.logger_version == FLEET_LOGGER_VERSION  # who wrote the file
    assert r.payload.get("transport") == "wifi_poll"  # how the bytes arrived
    header_blob = "\n".join(parse_file(files[0]).segments[0].raw_lines)
    assert "transport=wifi_poll" in header_blob
    assert f"logger={FLEET_LOGGER_VERSION}" in header_blob
    assert "http://" not in header_blob  # no base_url/IP persisted, ever
    # the reading itself is intact
    assert r.raw_value == 1900 and r.sensor_id == "s1" and r.device_seq == 101
    # the honesty bound is stated in the segment itself, not fine print
    assert "collected-while-host-runs" in header_blob


def test_multiple_devices_get_their_own_files(tmp_path: Path) -> None:
    reg, factory = _served(
        {
            "http://a": _response(_line(device="sprout-s3-01", seq=1)),
            "http://b": _response(_line(device="sprout-c5-01", seq=1)),
        }
    )
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    assert fl.poll_once() == 2
    names = sorted(p.name.split("_")[0] for p in tmp_path.glob("*.csv"))
    assert names == ["sprout-c5-01", "sprout-s3-01"]


def test_unreachable_device_never_breaks_the_sweep(tmp_path: Path) -> None:
    reg, _ = _served({"http://a": "", "http://b": _response(_line(seq=7))})

    def factory(base_url: str):
        if base_url == "http://a":

            def _boom(url: str) -> str:
                raise OSError("Connection refused")

            return DeviceAdapter(base_url, fetch=_boom)
        return DeviceAdapter(base_url, fetch=lambda url: _response(_line(seq=7)))

    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    assert fl.poll_once() == 1  # the healthy device still persisted


# --------------------------------------------------------------------------- #
# dedupe within a run (decision 2's "cadence = resolution" consequence)
# --------------------------------------------------------------------------- #


def test_same_device_seq_across_polls_persists_once(tmp_path: Path) -> None:
    reg, factory = _served({"http://a": _response(_line(seq=101))})
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    assert fl.poll_once() == 1
    assert fl.poll_once() == 0  # same latest row re-served -> Store drops it
    assert len(parse_files([str(tmp_path)]).readings) == 1


def test_new_device_seq_appends(tmp_path: Path) -> None:
    texts = {"http://a": _response(_line(seq=101))}
    reg, factory = _served(texts)
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    fl.poll_once()
    texts["http://a"] = _response(_line(seq=102, raw=1888, millis=90000))
    assert fl.poll_once() == 1
    raws = sorted(r.raw_value for r in parse_files([str(tmp_path)]).readings)
    assert raws == [1888, 1900]


def test_no_device_seq_repeats_visibly_not_silently(tmp_path: Path) -> None:
    """Store's honest degrade (#521): no device_seq = no dedupe signal = always
    append. A pre-schema-v2 device therefore repeats its latest row at poll
    cadence - detectable (identical millis_ms), never silently dropped."""
    reg, factory = _served({"http://a": _response(_line(seq=None))})
    fl = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    fl.poll_once()
    fl.poll_once()
    rs = parse_files([str(tmp_path)]).readings
    assert len(rs) == 2
    assert rs[0].millis_ms == rs[1].millis_ms  # the repeat is detectable


# --------------------------------------------------------------------------- #
# restart dedupe (decision 3)
# --------------------------------------------------------------------------- #


def test_restart_does_not_reappend_rows_already_on_disk(tmp_path: Path) -> None:
    reg, factory = _served({"http://a": _response(_line(seq=101))})
    first = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    first.poll_once()

    # a fresh process: new Store, seeded from disk before the first poll
    second = FleetLogger(str(tmp_path), registry=reg, adapter_factory=factory, log=str)
    seeded = seed_store_from_disk(second.store, str(tmp_path))
    assert seeded >= 1
    assert second.poll_once() == 0  # the device's latest row is already on disk
    assert len(parse_files([str(tmp_path)]).readings) == 1


def test_seed_ignores_files_outside_the_window(tmp_path: Path) -> None:
    reg, factory = _served({"http://a": _response(_line(seq=101))})
    FleetLogger(
        str(tmp_path), registry=reg, adapter_factory=factory, log=str
    ).poll_once()
    store = Store()
    # pretend "now" is far in the future: every file is outside the window
    assert (
        seed_store_from_disk(store, str(tmp_path), window_s=60.0, now=9_999_999_999.0)
        == 0
    )


def test_seed_missing_dir_is_zero_not_crash(tmp_path: Path) -> None:
    assert seed_store_from_disk(Store(), str(tmp_path / "nope")) == 0


# --------------------------------------------------------------------------- #
# the loop (run/max_polls/--once mechanics)
# --------------------------------------------------------------------------- #


def test_run_polls_on_cadence_and_stops_at_max(tmp_path: Path) -> None:
    reg, factory = _served({"http://a": _response(_line(seq=101))})
    sleeps: list[float] = []
    fl = FleetLogger(
        str(tmp_path),
        cadence_s=30.0,
        registry=reg,
        adapter_factory=factory,
        sleep=sleeps.append,
        log=str,
    )
    fl.run(max_polls=3)
    assert fl.polls == 3
    assert sleeps == [30.0, 30.0]  # sleeps BETWEEN polls, none after the last
    assert len(parse_files([str(tmp_path)]).readings) == 1  # deduped across ticks


# --------------------------------------------------------------------------- #
# End-to-end: a real http.server serving #276's exact bytes -> disk -> parse
# --------------------------------------------------------------------------- #


def test_end_to_end_over_real_http(tmp_path: Path) -> None:
    import http.server
    import threading

    line = _line(seq=555, raw=1777)

    class _H(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            raw = _response(line).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, fmt: str, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), _H)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        reg = Registry(
            devices=[
                Device(
                    device_id="sprout-s3-01",
                    board=None,
                    label=None,
                    channels={},
                    base_url=f"http://127.0.0.1:{port}",
                )
            ]
        )
        fl = FleetLogger(str(tmp_path), registry=reg, log=str)  # REAL adapter path
        fl.run(max_polls=1)
        r = parse_files([str(tmp_path)]).readings[0]
        assert r.raw_value == 1777 and r.device_seq == 555
        assert r.logger_version == FLEET_LOGGER_VERSION
        assert r.payload.get("transport") == "wifi_poll"
    finally:
        server.shutdown()
        thread.join(timeout=5)


# --------------------------------------------------------------------------- #
# RotatingCsv extensions (#582): write_row + honest header identity
# --------------------------------------------------------------------------- #


def test_rotating_csv_header_names_its_real_writer(tmp_path: Path) -> None:
    from datetime import datetime, timezone

    from plants_logger import LOGGER_VERSION, RotatingCsv

    now = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
    fleet = RotatingCsv(str(tmp_path / "a"), logger_version=FLEET_LOGGER_VERSION)
    fleet.write_row({"device_id": "d1", "record_type": "plants.soil"}, now)
    head = next(iter((tmp_path / "a").glob("*.csv"))).read_text(encoding="utf-8")
    assert f"logger={FLEET_LOGGER_VERSION}" in head
    # ...and the default stays the serial logger's own identity (pinned)
    serial = RotatingCsv(str(tmp_path / "b"))
    serial.write_row({"device_id": "d1", "record_type": "plants.soil"}, now)
    head_b = next(iter((tmp_path / "b").glob("*.csv"))).read_text(encoding="utf-8")
    assert f"logger={LOGGER_VERSION}" in head_b
