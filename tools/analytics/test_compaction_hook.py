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
    (tmp_path / ".last-compact").write_text((_NOW - timedelta(minutes=30)).isoformat())
    calls: list = []
    r = compaction_hook.maybe_compact(
        logs_dir=tmp_path,
        root=tmp_path,
        now=_NOW,
        min_interval_s=3600,
        _compact=lambda f, root, log: calls.append(1),
    )
    assert r["ran"] is False
    assert r["reason"] == "throttled"
    assert calls == []  # never touched the compaction


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
        compaction_hook, "maybe_compact", lambda *a, **k: calls.append(1)
    )
    serve._compaction_tick()
    assert calls == [1]


def test_hook_matches_d3_compact_signature() -> None:
    """Contract test against Data's real `tier_ingest.compact` (#1241 D3).

    `maybe_compact` isolates failures, so a signature drift would otherwise degrade to a
    permanently silent "skipped" instead of a red test. Bind the call shape the hook
    actually uses — positional (files, root) + keyword log — against the live D3."""
    import inspect

    import tier_ingest

    inspect.signature(tier_ingest.compact).bind(["a.csv"], Path("root"), log=print)
