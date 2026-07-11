"""Address the WiFi fleet by NAME, not by a fixed IP (#676, host half).

## Why

The fleet is configured by IP in the registry (`config/devices.local.json`
`base_url`s). On install day every board grabbed a new DHCP IP on power-cycle, so
the IPs went stale and the boards became unfindable without a repeated subnet
scan — the single biggest operational friction of the day.

Firmware now advertises an **mDNS hostname** per board, `sprout-<device_id>.local`
(the nonce = the minted `device_id`; ADR-0020 §2 / #760). That name is stable
across DHCP churn. This module resolves each device to an **ordered list of
addresses to try** — the configured / last-good IP **first** (#953: an online board
answers in <100 ms instead of stalling ~2 s on a `.local` mDNS lookup every poll), the
stable mDNS hostname **as the rediscovery fallback** — and, once a board answers at a
fresh mDNS-resolved address, **self-heals** the registry so the fast IP path stays
current across DHCP churn.

Discovery keys on **stable identity** (the device_id-derived hostname), never on a
fixed IP (the two acceptance criteria). Zero new dependencies: the OS resolver
(Bonjour on macOS/Windows, avahi on Linux) resolves `.local` names; a board with
no name advertised simply falls through to its configured IP (honest degrade).
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_LOCAL_CONFIG = _REPO / "config" / "devices.local.json"


def mdns_host(device_id: str) -> str:
    """The board's advertised mDNS name (#760): ``sprout-<device_id>.local``."""
    return f"sprout-{device_id}.local"


def candidate_base_urls(device) -> list[str]:
    """Ordered addresses to try for ``device``. The configured / last-good IP
    ``base_url`` goes **first** (#953); the stable mDNS hostname is the **rediscovery
    fallback**, second. Deduped, order-preserving; a device with neither a
    ``device_id`` nor a ``base_url`` yields ``[]`` (nothing to reach).

    Why IP-first (was mDNS-first, #676): a dashboard request fetches every served
    device **synchronously on the request path**, on every poll. Resolving a ``.local``
    name on Windows stalls ~2 s per attempt, so mDNS-first burned a flat ~4.7 s fetch
    tax on *every* request even when the board was online (the #953 [perf] evidence).
    An online board at a stable IP now answers on the first candidate in <100 ms.

    #676's DHCP-robustness is preserved: when a board moves and its stored IP goes
    stale, the first candidate fails and the mDNS fallback rediscovers it — then
    :func:`make_healer` writes the freshly-resolved IP back to ``base_url``, so the very
    next poll is fast again. The rare move pays one stale-IP timeout once; the
    poll-constant common case is instant."""
    urls: list[str] = []
    base_url = (getattr(device, "base_url", None) or "").rstrip("/")
    if base_url:
        urls.append(base_url)
    device_id = getattr(device, "device_id", None)
    if device_id:
        urls.append(f"http://{mdns_host(device_id)}")
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def resolve_ip(host: str, *, resolver=None) -> str | None:
    """The current IPv4 for a hostname, or ``None`` if unresolvable. Never raises — an
    absent mDNS responder is a normal offline state, not an error.

    #953: uses ``getaddrinfo``, NOT ``gethostbyname``. On Windows ``gethostbyname``
    often FAILS for a ``.local`` mDNS name even when the HTTP fetch to that name
    succeeds (``create_connection`` resolves via ``getaddrinfo``). That mismatch is why
    the healer could never turn a ``.local`` ``base_url`` into a numeric IP - so
    "IP-first" (#981) stayed stuck on the slow name and the ~4.7s fetch tax never moved.
    Matching the fetch's resolver here lets the heal fire, persist the IP, and kill the
    tax next poll. ``resolver`` stays injectable for tests."""
    if resolver is not None:
        try:
            return resolver(host)
        except OSError:
            return None
    try:
        infos = socket.getaddrinfo(
            host, None, family=socket.AF_INET, type=socket.SOCK_STREAM
        )
        return infos[0][4][0] if infos else None
    except (OSError, IndexError):
        return None


def _is_mdns_url(url: str, device_id: str | None) -> bool:
    return bool(device_id) and url.rstrip("/") == f"http://{mdns_host(device_id)}"


def heal_base_url(
    device_id: str,
    new_base_url: str,
    *,
    path: Path | None = None,
    reader=None,
    writer=None,
    log=None,
) -> bool:
    """Best-effort: rewrite the local registry so ``device_id``'s ``base_url`` is
    ``new_base_url`` (self-heal after a board moved). Matches on ``device_id`` or
    any of its ``previous_ids`` (#602). Returns True if a device was updated and
    written, and **logs the change** — a registry file rewritten under the operator
    is announced, never silent (#676 AC: honestly logged, no mystery-meat edit).
    **Never raises** — a read-only or absent config just isn't healed, so a poll
    never crashes on a self-heal attempt. ``reader``/``writer``/``log`` are
    injectable for tests (default: read/write the local JSON config, print to the
    console in serve.py's style)."""
    cfg = path or _LOCAL_CONFIG
    emit = log if log is not None else print
    try:
        text = reader(cfg) if reader else cfg.read_text(encoding="utf-8")
        doc = json.loads(text)
        devices = doc.get("devices")
        if not isinstance(devices, list):
            return False
        heals: list[tuple[str, str]] = []  # (matched device_id, old base_url)
        for d in devices:
            if not isinstance(d, dict):
                continue
            ids = {d.get("device_id"), *(d.get("previous_ids") or [])}
            if device_id in ids and d.get("base_url") != new_base_url:
                heals.append((d.get("device_id") or device_id, d.get("base_url")))
                d["base_url"] = new_base_url
        if not heals:
            return False
        out = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        if writer:
            writer(cfg, out)
        else:
            cfg.write_text(out, encoding="utf-8")
        # announce the edit AFTER it persists (never claim a heal that didn't land)
        for did, old in heals:
            emit(
                f"self-heal (#676): {did} base_url {old or '(unset)'} → {new_base_url}"
            )
        return True
    except (OSError, ValueError, TypeError):
        return False


def make_healer(device, *, resolver=None, path: Path | None = None, writer=None):
    """A ``on_resolved(working_url)`` callback for :class:`DeviceAdapter` that
    self-heals the registry (#676). When the board answered at its **mDNS
    hostname**, resolve that name to the current IP and, if it differs from the
    stored ``base_url``, write the fresh ``http://<ip>`` back — so the IP fallback
    stays current even if mDNS later fails. Answering at the configured IP heals
    nothing (already correct). Never raises."""
    device_id = getattr(device, "device_id", None)
    configured = (getattr(device, "base_url", None) or "").rstrip("/")

    def _on_resolved(working_url: str) -> None:
        if not device_id or not _is_mdns_url(working_url, device_id):
            return
        ip = resolve_ip(mdns_host(device_id), resolver=resolver)
        if not ip:
            return
        fresh = f"http://{ip}"
        if fresh != configured:
            heal_base_url(device_id, fresh, path=path, writer=writer)

    return _on_resolved
