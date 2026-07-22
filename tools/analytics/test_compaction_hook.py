"""Tests for the #1292 launcher compaction hook.

Runs under `just test-analytics`. The hook is the POLICY (throttle + error-isolation)
around D3's compaction; the compaction is D3's own tested code, so these inject a fake
`_compact` and assert only the policy — no dependency on tier_ingest being present."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import compaction_hook

_NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


def test_runs_when_no_marker(tmp_path: Path) -> None:
    calls: list = []
    r = compaction_hook.maybe_compact(
        logs_dir=tmp_path,
        root=tmp_path,
        now=_NOW,
        _compact=lambda f, root, log: (
            calls.append(1) or {"compacted": ["2026-07-18 dev1"]}
        ),
    )
    assert r["ran"] is True
    assert calls == [1]
    assert (tmp_path / ".last-compact").exists()  # marker written for the throttle


def test_throttled_within_interval(tmp_path: Path) -> None:
    # #1466: the throttle applies to a NON-EMPTY store; an empty one bypasses it — a
    # dark store never stays dark because the gate skipped. So give it a partition.
    part = tmp_path / "date=2026-07-10" / "device=devA"
    part.mkdir(parents=True)
    (part / "part.parquet").write_bytes(b"PAR1")
    (tmp_path / ".last-compact").write_text((_NOW - timedelta(minutes=30)).isoformat())
    calls: list = []
    r = compaction_hook.maybe_ingest_and_compact(
        logs_dir=tmp_path,
        root=tmp_path,
        now=_NOW,
        min_interval_s=3600,
        _ingest=lambda f, root, log: calls.append(1),
        _compact=lambda f, root, log: calls.append(1),
    )
    assert r["ran"] is False
    assert r["reason"] == "throttled"
    assert calls == []  # never touched ingest or compaction


def test_runs_after_interval(tmp_path: Path) -> None:
    (tmp_path / ".last-compact").write_text((_NOW - timedelta(hours=2)).isoformat())
    calls: list = []
    r = compaction_hook.maybe_compact(
        logs_dir=tmp_path,
        root=tmp_path,
        now=_NOW,
        min_interval_s=3600,
        _compact=lambda f, root, log: calls.append(1) or {"compacted": []},
    )
    assert r["ran"] is True
    assert calls == [1]


def test_error_is_isolated_not_raised(tmp_path: Path) -> None:
    def boom(f, root, log):
        raise RuntimeError("compaction blew up")

    r = compaction_hook.maybe_compact(
        logs_dir=tmp_path, root=tmp_path, now=_NOW, _compact=boom
    )
    assert r["ran"] is False
    assert r["reason"] == "error"  # logged + swallowed; live collection unaffected


def test_launcher_call_site_invokes_the_hook(monkeypatch) -> None:
    """The wire itself (#1292): a hook nobody calls is the failure mode this guards."""
    import serve

    calls: list = []
    monkeypatch.setattr(
        compaction_hook, "maybe_ingest_and_compact", lambda *a, **k: calls.append(1)
    )
    serve._tier_tick()
    assert calls == [1]


def test_hook_matches_d3_compact_signature() -> None:
    """Contract test against Data's real `tier_ingest.compact` (#1241 D3).

    `maybe_compact` isolates failures, so a signature drift would otherwise degrade to a
    permanently silent "skipped" instead of a red test. Bind the call shape the hook
    actually uses — positional (files, root) + keyword log — against the live D3."""
    import inspect

    import tier_ingest

    inspect.signature(tier_ingest.compact).bind(["a.csv"], Path("root"), log=print)


# --------------------------------------------------------------------------- #
# #1466 — the tick must FILL the store, not only compact it
# --------------------------------------------------------------------------- #
_HDR = (
    "# schema_version=4  fw=0.8.0  git=t  device_id=devA  session_id=s1\n"
    "record_type,timestamp_utc,timestamp_local,session_id,device_id,"
    "sensor_id,raw_value,quality_flag,payload\n"
)


def _log(tmp: Path, name: str, rows: list[tuple[str, str, int]]) -> None:
    body = "".join(
        f"plants.soil,{ts},x,s1,dev,{sensor},{raw},OK,level=OK\n"
        for ts, sensor, raw in rows
    )
    (tmp / name).write_text(_HDR + body, encoding="utf-8")


def test_the_tick_ingests_not_only_compacts(tmp_path: Path) -> None:
    """#1466's core: on an empty store the tick must call ingest, not just compact.
    A compaction-only tick was the bug — it left the store empty forever."""
    calls = {"ingest": 0, "compact": 0}
    r = compaction_hook.maybe_ingest_and_compact(
        logs_dir=tmp_path,
        root=tmp_path / "tier",
        _ingest=lambda f, root, log: (
            calls.__setitem__("ingest", calls["ingest"] + 1) or {"appended_rows": 0}
        ),
        _compact=lambda f, root, log: (
            calls.__setitem__("compact", calls["compact"] + 1) or {"compacted": []}
        ),
    )
    assert calls["ingest"] == 1, "the tick MUST ingest — a compact-only tick was #1466"
    assert calls["compact"] == 1
    assert r["ran"] is True


def test_an_empty_store_bypasses_the_throttle(tmp_path: Path) -> None:
    """A dark store must never stay dark because the hourly throttle skipped it. Even
    with a fresh marker, an empty store still ingests."""
    root = tmp_path / "tier"
    root.mkdir(parents=True)
    (root / ".last-compact").write_text(
        datetime.now(timezone.utc).isoformat()
    )  # just ran
    ingested = []
    r = compaction_hook.maybe_ingest_and_compact(
        logs_dir=tmp_path,
        root=root,
        _ingest=lambda f, root, log: ingested.append(1) or {"appended_rows": 5},
        _compact=lambda f, root, log: {"compacted": []},
    )
    assert ingested == [1], "an empty store must ingest despite a fresh throttle marker"
    assert r["ran"] is True


def test_a_filled_store_still_respects_the_throttle(tmp_path: Path) -> None:
    """The bypass is only for EMPTY stores — a populated one still throttles, so the
    tick stays cheap on rapid relaunches."""
    root = tmp_path / "tier" / "date=2026-07-10" / "device=devA"
    root.mkdir(parents=True)
    (root / "part.parquet").write_bytes(b"PAR1")  # store is non-empty
    (tmp_path / "tier" / ".last-compact").write_text(
        datetime.now(timezone.utc).isoformat()
    )
    calls = []
    r = compaction_hook.maybe_ingest_and_compact(
        logs_dir=tmp_path,
        root=tmp_path / "tier",
        _ingest=lambda f, root, log: calls.append(1),
        _compact=lambda f, root, log: calls.append(1),
    )
    assert r == {"ran": False, "reason": "throttled"}
    assert calls == [], "a filled store within the interval must not do work"


def test_filling_an_empty_store_is_loud(tmp_path: Path) -> None:
    """AC3: a dark store filling says so — silence over empty is how #1435 hid."""
    msgs: list[str] = []
    compaction_hook.maybe_ingest_and_compact(
        logs_dir=tmp_path,
        root=tmp_path / "tier",
        log=msgs.append,
        _ingest=lambda f, root, log: {"appended_rows": 700},
        _compact=lambda f, root, log: {"compacted": []},
    )
    assert any("EMPTY" in m and "backfilled" in m for m in msgs), (
        f"the backfill must be loud; got {msgs}"
    )


def test_end_to_end_fill_lights_the_readers(tmp_path: Path) -> None:
    """The real path, no injection: a source log with v4 and v5 rows for one plant.
    The tick fills the store; the tier reader then resolves that plant — the empty
    store lit, the S1 join (#1454) handling both tokens."""
    import pytest

    pytest.importorskip("duckdb")
    _log(
        tmp_path,
        "seg.csv",
        [
            ("2026-07-10T00:00:00.000000Z", "s1", 1500),  # v4 token
            ("2026-07-10T00:30:00.000000Z", "ch2", 1520),  # v5 token, same channel
        ],
    )
    root = tmp_path / "tier"
    r = compaction_hook.maybe_ingest_and_compact(logs_dir=tmp_path, root=root)
    assert r["ran"] and r["appended_rows"] == 2
    assert list(root.glob("date=*/device=*/*.parquet")), (
        "the store must have parquet now"
    )

    # the reader resolves both tokens to the one plant via the #1454 join
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parent))
    from device_registry import Device, Registry
    from segment_history import plant_series

    reg = Registry(
        devices=[
            Device(
                device_id="dev",
                board="esp32-classic",
                label="A",
                channels={"ch2": {"plant_id": "p11", "plant_name": "Fern"}},
            )
        ]
    )
    series, _unmapped = plant_series(root=root, registry=reg)
    assert "p11" in series, (
        "the reader must resolve the plant from the now-filled store"
    )
    assert len(series["p11"]) == 2, "both the v4 and the v5 row resolve (the S1 join)"
