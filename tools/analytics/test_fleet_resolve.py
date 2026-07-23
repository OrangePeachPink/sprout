"""#676 (host half) — address the WiFi fleet by mDNS hostname (sprout-<device_id>
.local), IP fallback, and self-heal the registry when a board answers at a fresh
address. A board that reboots to a new DHCP IP stays reachable without a registry
hand-edit; discovery keys on stable identity (the device_id-derived name).
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.analytics.device_registry import Device
from tools.analytics.fleet_resolve import (
    candidate_base_urls,
    heal_base_url,
    make_healer,
    mdns_host,
    resolve_ip,
)
from tools.analytics.source_adapter import DeviceAdapter

_TELEM = (
    "plants.soil,sess1,y9d41p,0.7.0,30000,UMLIFE_v2_TLC555,s1,origplant,"
    "soil_moisture,2400,,,OK,level=DRY;gpio=34"
)


def _line_with_crc(body: str) -> str:
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    return f"{body}*{crc:02X}"


# --------------------------------------------------------------------------- #
# candidate resolution — hostname first, IP fallback
# --------------------------------------------------------------------------- #
def test_last_good_ip_is_tried_before_the_hostname() -> None:
    # #953: IP-first so an online board answers in <100ms instead of burning a ~2s
    # mDNS `.local` timeout on every poll; the hostname is the rediscovery fallback.
    d = Device(
        device_id="y9d41p", board="esp32", label=None, base_url="http://192.168.1.9"
    )
    assert candidate_base_urls(d) == [
        "http://192.168.1.9",  # last-good IP, tried FIRST (fast common case)
        "http://sprout-y9d41p.local",  # stable identity, rediscovery fallback
    ]
    assert mdns_host("y9d41p") == "sprout-y9d41p.local"


def test_online_board_answers_on_ip_without_an_mdns_attempt() -> None:
    # #953 the whole point: an online board at its last-good IP answers on candidate 1,
    # so the slow `.local` lookup is never even attempted — no ~2s stall per poll.
    d = Device(
        device_id="y9d41p", board="esp32", label=None, base_url="http://192.168.1.9"
    )
    tried = []

    def fetch(url):
        tried.append(url)
        return _line_with_crc(_TELEM)

    a = DeviceAdapter(
        "http://192.168.1.9", candidates=candidate_base_urls(d), fetch=fetch
    )
    data = a.load()
    assert [r.raw_value for r in data.readings] == [2400]
    assert tried == ["http://192.168.1.9/telemetry"]  # IP answered; mDNS never tried
    assert not any(".local" in u for u in tried)


def test_candidates_dedupe_and_absent_safe() -> None:
    assert candidate_base_urls(Device("z", "b", None)) == ["http://sprout-z.local"]
    # a device with neither id nor url has nothing to reach
    assert candidate_base_urls(Device("", "b", None, base_url=None)) == []


def test_resolve_ip_never_raises() -> None:
    assert (
        resolve_ip("nope.local", resolver=lambda h: (_ for _ in ()).throw(OSError()))
        is None
    )
    assert resolve_ip("ok.local", resolver=lambda h: "10.0.0.5") == "10.0.0.5"


def test_resolve_ip_uses_getaddrinfo_by_default(monkeypatch) -> None:
    # #953: the default resolver is getaddrinfo (resolves a .local mDNS name on Windows
    # where gethostbyname fails), so the healer can finally persist the numeric IP.
    import socket as _socket

    monkeypatch.setattr(
        _socket,
        "getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("192.168.1.42", 0))],
    )
    assert resolve_ip("sprout-y9d41p.local") == "192.168.1.42"


def test_resolve_ip_getaddrinfo_failure_is_none(monkeypatch) -> None:
    import socket as _socket

    def _boom(*a, **k):
        raise OSError("unresolvable")

    monkeypatch.setattr(_socket, "getaddrinfo", _boom)
    assert resolve_ip("nope.local") is None  # honest offline, never a raise


# --------------------------------------------------------------------------- #
# the adapter tries candidates in order and uses the first that answers
# --------------------------------------------------------------------------- #
def test_adapter_falls_through_to_the_first_reachable_address() -> None:
    tried = []

    def fetch(url):
        tried.append(url)
        if url.startswith("http://sprout-y9d41p.local"):
            raise OSError("stale mDNS / no responder")  # hostname unreachable
        return _line_with_crc(_TELEM)  # the IP fallback answers

    seen_working = []
    a = DeviceAdapter(
        "http://192.168.1.9",
        candidates=["http://sprout-y9d41p.local", "http://192.168.1.9"],
        fetch=fetch,
        on_resolved=seen_working.append,
    )
    data = a.load()
    assert [r.raw_value for r in data.readings] == [2400]
    # it tried the hostname FIRST, then fell back to the IP
    assert tried == [
        "http://sprout-y9d41p.local/telemetry",
        "http://192.168.1.9/telemetry",
    ]
    assert data.sources == ["http://192.168.1.9"]  # the address that worked
    assert seen_working == ["http://192.168.1.9"]


def test_adapter_reaches_a_rebooted_board_by_hostname_when_ip_is_stale() -> None:
    # #953 IP-first order: the board grabbed a new DHCP IP, so the last-good IP (tried
    # FIRST now) is dead — but the mDNS hostname fallback resolves to the new one and
    # answers, so #676's DHCP-robustness is preserved even with IP-first.
    def fetch(url):
        if url.startswith("http://sprout-y9d41p.local"):
            return _line_with_crc(_TELEM)
        raise OSError("stale IP - board moved")

    a = DeviceAdapter(
        "http://192.168.1.9",
        candidates=["http://192.168.1.9", "http://sprout-y9d41p.local"],  # IP-first
        fetch=fetch,
    )
    data = a.load()
    assert [r.raw_value for r in data.readings] == [2400]
    assert data.sources == ["http://sprout-y9d41p.local"]  # reached by NAME fallback


def test_all_candidates_unreachable_is_honest_empty() -> None:
    a = DeviceAdapter(
        "http://192.168.1.9",
        candidates=["http://sprout-y9d41p.local", "http://192.168.1.9"],
        fetch=lambda u: (_ for _ in ()).throw(OSError()),
    )
    assert a.load().readings == []  # never a crash


# --------------------------------------------------------------------------- #
# registry self-heal
# --------------------------------------------------------------------------- #
def test_heal_rewrites_the_base_url(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.local.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "devices": [
                    {"device_id": "y9d41p", "base_url": "http://192.168.1.9"},
                    {"device_id": "other", "base_url": "http://192.168.1.5"},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert heal_base_url("y9d41p", "http://192.168.1.42", path=cfg) is True
    doc = json.loads(cfg.read_text(encoding="utf-8"))
    urls = {d["device_id"]: d["base_url"] for d in doc["devices"]}
    assert urls["y9d41p"] == "http://192.168.1.42"  # healed
    assert urls["other"] == "http://192.168.1.5"  # untouched


def test_heal_logs_the_change_never_silent(tmp_path: Path) -> None:
    # #676 AC: a registry rewritten under the operator is announced, not silent.
    cfg = tmp_path / "devices.local.json"
    cfg.write_text(
        json.dumps(
            {"devices": [{"device_id": "y9d41p", "base_url": "http://192.168.1.9"}]}
        ),
        encoding="utf-8",
    )
    lines: list[str] = []
    assert heal_base_url("y9d41p", "http://192.168.1.42", path=cfg, log=lines.append)
    assert lines == [
        "self-heal (#676): y9d41p base_url http://192.168.1.9 → http://192.168.1.42"
    ]


def test_heal_noop_emits_no_log(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.local.json"
    cfg.write_text(
        json.dumps({"devices": [{"device_id": "y9d41p", "base_url": "http://a"}]}),
        encoding="utf-8",
    )
    lines: list[str] = []
    assert heal_base_url("y9d41p", "http://a", path=cfg, log=lines.append) is False
    assert lines == []  # nothing written -> nothing announced


def test_heal_is_a_noop_when_unchanged(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.local.json"
    cfg.write_text(
        json.dumps({"devices": [{"device_id": "y9d41p", "base_url": "http://a"}]}),
        encoding="utf-8",
    )
    assert heal_base_url("y9d41p", "http://a", path=cfg) is False  # nothing to write


def test_heal_never_raises_on_bad_config(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert heal_base_url("y9d41p", "http://x", path=missing) is False


def test_healer_writes_fresh_ip_when_board_answered_by_hostname(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.local.json"
    cfg.write_text(
        json.dumps(
            {"devices": [{"device_id": "y9d41p", "base_url": "http://192.168.1.9"}]}
        ),
        encoding="utf-8",
    )
    d = Device("y9d41p", "esp32", None, base_url="http://192.168.1.9")
    healer = make_healer(
        d,
        resolver=lambda host: "192.168.1.42",  # mDNS now resolves to the new IP
        path=cfg,
    )
    healer("http://sprout-y9d41p.local")  # the board answered by NAME
    healed = {
        dev["device_id"]: dev["base_url"]
        for dev in json.loads(cfg.read_text(encoding="utf-8"))["devices"]
    }
    assert healed["y9d41p"] == "http://192.168.1.42"  # fresh IP persisted


def test_healer_noop_when_board_answered_at_configured_ip(tmp_path: Path) -> None:
    cfg = tmp_path / "devices.local.json"
    original = json.dumps(
        {"devices": [{"device_id": "y9d41p", "base_url": "http://192.168.1.9"}]}
    )
    cfg.write_text(original, encoding="utf-8")
    d = Device("y9d41p", "esp32", None, base_url="http://192.168.1.9")
    healer = make_healer(d, resolver=lambda h: "x", path=cfg)
    healer("http://192.168.1.9")  # answered at the configured IP — nothing to heal
    assert cfg.read_text(encoding="utf-8") == original  # untouched
