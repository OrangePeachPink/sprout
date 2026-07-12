"""#1026 — a board answering at a registered address with an id the registry never heard
of must surface LOUDLY, not accumulate rows under a ghost. The DeviceAdapter compares
the self-reported device_id to the registry's expectation (canonical + previous_ids) and
a mismatch; serve.py surfaces it (dashboard notice + /fleet/status count).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from source_adapter import DeviceAdapter, IdentityMismatchLog


def _telem(device_id: str, raw: int = 2400) -> str:
    body = (
        f"plants.soil,sess1,{device_id},0.7.0,30000,UMLIFE_v2_TLC555,"
        f"s1,origplant,soil_moisture,{raw},,,OK,level=DRY;gpio=34"
    )
    crc = 0
    for ch in body:
        crc ^= ord(ch) & 0xFF
    return f"{body}*{crc:02X}"


def _adapter(device_id_seen, *, expected_id, previous_ids=(), log=None):
    return DeviceAdapter(
        "http://192.168.1.89",
        fetch=lambda _u: _telem(device_id_seen),
        candidates=["http://192.168.1.89"],
        expected_id=expected_id,
        previous_ids=previous_ids,
        mismatch_log=log,
    )


# --------------------------------------------------------------------------- #
# detection in the fetch path
# --------------------------------------------------------------------------- #
def test_a_ghost_identity_is_recorded_loudly() -> None:
    # the live case: .89 answered as n3jhsp, expected yyvvpd, and nothing said a word.
    log = IdentityMismatchLog()
    data = _adapter("n3jhsp", expected_id="yyvvpd", log=log).load()
    assert [r.raw_value for r in data.readings] == [2400]  # rows parsed, not dropped
    active = log.active(time.time())
    assert len(active) == 1
    assert active[0] == {
        "base_url": "http://192.168.1.89",
        "expected": "yyvvpd",
        "got": "n3jhsp",
    }


def test_the_expected_id_never_alarms() -> None:
    log = IdentityMismatchLog()
    _adapter("yyvvpd", expected_id="yyvvpd", log=log).load()
    assert log.active(time.time()) == []


def test_a_previous_id_is_an_accepted_rename_not_a_ghost() -> None:
    # #602: previous_ids model legitimate renames — a board that renamed is not a ghost.
    log = IdentityMismatchLog()
    _adapter("yyvvpd", expected_id="newid", previous_ids=("yyvvpd",), log=log).load()
    assert log.active(time.time()) == []


def test_a_match_clears_a_prior_mismatch() -> None:
    log = IdentityMismatchLog()
    _adapter("n3jhsp", expected_id="yyvvpd", log=log).load()  # ghost
    assert len(log.active(time.time())) == 1
    _adapter("yyvvpd", expected_id="yyvvpd", log=log).load()  # adopted / fixed
    assert log.active(time.time()) == []  # cleared automatically, no lingering alarm


def test_no_expectation_means_no_alarm() -> None:
    # a bare/test DeviceAdapter with no expected_id must never alarm (opt-in check).
    log = IdentityMismatchLog()
    DeviceAdapter(
        "http://d",
        fetch=lambda _u: _telem("whoever"),
        candidates=["http://d"],
        mismatch_log=log,
    ).load()
    assert log.active(time.time()) == []


# --------------------------------------------------------------------------- #
# the log's freshness + shape
# --------------------------------------------------------------------------- #
def test_a_stale_mismatch_drops_from_active() -> None:
    # a board that went offline mid-mismatch shouldn't alarm forever.
    log = IdentityMismatchLog(ttl_s=100.0)
    log.record("http://d", expected="a", got="b", now=0.0)
    assert len(log.active(50.0)) == 1  # within the window
    assert log.active(200.0) == []  # gone stale -> dropped
