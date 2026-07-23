"""#1020 — a negative cache / circuit breaker in the fleet fetch path.

#953's durable half: a permanently- or transiently-offline board burned its full fetch
timeout (x2 candidates) on EVERY request, and the pool is parallel, so one dead board
set the dashboard's wall-clock. The breaker skips a device that failed its last N
fetches for a cooldown, then retries. A skip is an empty return, like a real miss, so
it surfaces as "not answering" (ADR-0028), never "no data by design".
"""

from __future__ import annotations

from tools.analytics.source_adapter import DeviceAdapter, FetchBreaker


def _dead_adapter(calls, br, mono):
    def fetch(url):
        calls.append(url)
        raise OSError("offline")

    return DeviceAdapter(
        "http://d", fetch=fetch, candidates=["http://d"], breaker=br, mono=mono
    )


def test_breaker_skips_after_consecutive_failures_then_retries() -> None:
    calls: list[str] = []
    br = FetchBreaker(trip_after=3, cooldown_s=30.0)
    clock = [0.0]

    def mono():
        return clock[0]

    # three real attempts trip the breaker (one candidate = one fetch each)
    for _ in range(3):
        assert _dead_adapter(calls, br, mono).load().readings == []
    tripped_at = len(calls)
    assert tripped_at == 3

    # a fetch WITHIN the cooldown is SKIPPED — the timeout is never paid
    assert _dead_adapter(calls, br, mono).load().readings == []
    assert len(calls) == tripped_at  # no new network attempt
    assert br.should_skip("http://d", clock[0]) is True

    # after the cooldown, exactly one real retry runs (half-open)
    clock[0] = 31.0
    assert br.should_skip("http://d", clock[0]) is False
    assert _dead_adapter(calls, br, mono).load().readings == []
    assert len(calls) == tripped_at + 1  # one retry, not a skipped no-op


def test_a_transient_single_failure_does_not_trip() -> None:
    calls: list[str] = []
    br = FetchBreaker(trip_after=3, cooldown_s=30.0)
    _dead_adapter(calls, br, lambda: 0.0).load()  # one blip
    assert br.should_skip("http://d", 0.0) is False  # below threshold — still fetched
    assert len(calls) == 1


def test_a_success_closes_the_breaker() -> None:
    n = [0]

    def fetch(url):
        n[0] += 1
        if n[0] <= 2:
            raise OSError("blip")
        return "plants.soil,connected"  # the board answered (text not None -> ok)

    br = FetchBreaker(trip_after=3, cooldown_s=30.0)
    a = DeviceAdapter(
        "http://d", fetch=fetch, candidates=["http://d"], breaker=br, mono=lambda: 0.0
    )
    a.load()  # fail 1
    a.load()  # fail 2
    a.load()  # success -> close
    # the two prior failures are cleared; it takes three FRESH failures to trip again
    assert br.should_skip("http://d", 0.0) is False


def test_breaker_state_is_shared_across_adapter_instances() -> None:
    # the whole point: state must persist across the per-request adapter builds serve.py
    # makes, so a dead board tripped on one request stays tripped on the next.
    calls: list[str] = []
    br = FetchBreaker(trip_after=2, cooldown_s=30.0)
    for _ in range(2):  # two SEPARATE adapters, same shared breaker
        _dead_adapter(calls, br, lambda: 0.0).load()
    assert br.should_skip("http://d", 0.0) is True  # tripped by the pair, not one
    before = len(calls)
    _dead_adapter(calls, br, lambda: 0.0).load()  # a third, brand-new adapter
    assert len(calls) == before  # skipped — the shared breaker held across instances
