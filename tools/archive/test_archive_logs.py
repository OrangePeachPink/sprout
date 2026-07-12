"""Tests for the B8 log archiver's reconciliation + byte-exact gzip (#12).

The git commit/push is best-effort and caught, so these exercise the pure,
data-integrity-critical parts — which closed segment gets archived, idempotency
(the missed-rollover self-heal), and byte-exact/deterministic gzip — against a
plain temp "worktree" (no real git repo needed; the git step no-ops via its
caught failure).

    python tools/archive/test_archive_logs.py
"""

from __future__ import annotations

import gzip
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import archive_logs


def _mklogs(d: Path, names: list[str]) -> None:
    """Create CSV segments with strictly increasing mtimes (last = newest = open)."""
    for i, name in enumerate(names):
        p = d / name
        p.write_text(f"raw,data,for,{name}\n", encoding="utf-8")
        os.utime(p, (1_000_000 + i * 100, 1_000_000 + i * 100))


def test_closed_segments_excludes_newest() -> None:
    d = Path(tempfile.mkdtemp())
    try:
        _mklogs(d, ["seg1.csv", "seg2.csv", "seg3.csv"])
        closed = {os.path.basename(p) for p in archive_logs.closed_segments(str(d))}
        assert closed == {"seg1.csv", "seg2.csv"}, closed  # seg3 = newest = open
        # include_all overrides: every segment is closed
        all_ = {
            os.path.basename(p)
            for p in archive_logs.closed_segments(str(d), include_all=True)
        }
        assert all_ == {"seg1.csv", "seg2.csv", "seg3.csv"}, all_
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_closed_segments_explicit_exclude() -> None:
    d = Path(tempfile.mkdtemp())
    try:
        _mklogs(d, ["a.csv", "b.csv"])
        # exclude the named open file regardless of mtime
        closed = {
            os.path.basename(p)
            for p in archive_logs.closed_segments(str(d), exclude=str(d / "a.csv"))
        }
        assert closed == {"b.csv"}, closed
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_closed_segments_empty_or_missing() -> None:
    assert (
        archive_logs.closed_segments(str(Path(tempfile.gettempdir()) / "no_such_xyz"))
        == []
    )
    d = Path(tempfile.mkdtemp())
    try:
        assert archive_logs.closed_segments(str(d)) == []  # empty dir
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_archive_reconciles_and_is_idempotent() -> None:
    logs = Path(tempfile.mkdtemp())
    wt = Path(tempfile.mkdtemp())  # a plain dir stands in for the data worktree
    try:
        _mklogs(logs, ["seg1.csv", "seg2.csv", "seg3.csv"])
        # first run: archives the two closed segments (seg3 is the open/newest)
        new = archive_logs.archive(
            logs_dir=str(logs), worktree=str(wt), push=False, log=lambda *_: None
        )
        assert set(new) == {"seg1.csv.gz", "seg2.csv.gz"}, new
        arch = wt / "data" / "archive"
        assert (arch / "seg1.csv.gz").exists() and (arch / "seg2.csv.gz").exists()
        assert not (arch / "seg3.csv.gz").exists(), (
            "the open segment must not be archived"
        )
        # second run: nothing new — the missed-rollover self-heal is idempotent
        again = archive_logs.archive(
            logs_dir=str(logs), worktree=str(wt), push=False, log=lambda *_: None
        )
        assert again == [], again
    finally:
        shutil.rmtree(logs, ignore_errors=True)
        shutil.rmtree(wt, ignore_errors=True)


def test_archive_catches_up_a_late_segment() -> None:
    # the robustness ask: a segment that closed while the host was off is caught later
    logs = Path(tempfile.mkdtemp())
    wt = Path(tempfile.mkdtemp())
    try:
        _mklogs(logs, ["seg1.csv", "seg2.csv"])
        archive_logs.archive(
            logs_dir=str(logs), worktree=str(wt), push=False, log=lambda *_: None
        )
        # a new segment opens (so seg2 is now closed and due); add seg3 as newest
        _mklogs(logs, ["seg1.csv", "seg2.csv", "seg3.csv"])
        new = archive_logs.archive(
            logs_dir=str(logs), worktree=str(wt), push=False, log=lambda *_: None
        )
        assert new == ["seg2.csv.gz"], (
            new
        )  # seg2 caught up; seg1 already done; seg3 open
    finally:
        shutil.rmtree(logs, ignore_errors=True)
        shutil.rmtree(wt, ignore_errors=True)


def test_gzip_is_byte_exact_and_deterministic() -> None:
    d = Path(tempfile.mkdtemp())
    try:
        src = d / "seg.csv"
        payload = b"plants.soil,raw,1312\n" * 50
        src.write_bytes(payload)
        dst1, dst2 = str(d / "a.gz"), str(d / "b.gz")
        archive_logs._gzip_to(str(src), dst1)
        archive_logs._gzip_to(str(src), dst2)
        # byte-exact: decompress matches the original
        assert gzip.decompress(Path(dst1).read_bytes()) == payload
        # deterministic (mtime=0): identical input -> identical archive bytes
        assert Path(dst1).read_bytes() == Path(dst2).read_bytes()
    finally:
        shutil.rmtree(d, ignore_errors=True)


# --------------------------------------------------------------------------- #
# #1035 — eviction: bounded-growth half. Evict archived + old segments from logs/,
# never an unbacked one, never the open one, loud on failure.
# --------------------------------------------------------------------------- #
def _archived_gz(wt: Path, csv_name: str) -> None:
    arch = wt / "data" / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / (csv_name + ".gz")).write_bytes(b"gz")


def test_evict_removes_archived_and_old_only() -> None:
    logs = Path(tempfile.mkdtemp())
    wt = Path(tempfile.mkdtemp())
    try:
        now = 2_000_000_000
        for name, age_days in [
            ("old.csv", 30),  # archived + old  -> EVICT
            ("recent.csv", 1),  # archived + recent -> keep (hot path)
            ("unbacked.csv", 30),  # old but NOT archived -> keep (never lose)
            ("open.csv", 0),  # newest = open -> keep
        ]:
            p = logs / name
            p.write_text(f"raw,{name}\n", encoding="utf-8")
            os.utime(p, (now - age_days * 86400, now - age_days * 86400))
        _archived_gz(wt, "old.csv")
        _archived_gz(wt, "recent.csv")  # unbacked.csv intentionally has NO .gz
        evicted = archive_logs.evict_archived(
            str(logs), str(wt), retention_days=14, now=now, log=lambda *_: None
        )
        assert evicted == ["old.csv"], evicted
        assert not (logs / "old.csv").exists()  # archived + old -> gone
        assert (logs / "recent.csv").exists()  # within retention window
        assert (logs / "unbacked.csv").exists()  # NEVER evict an unbacked segment
        assert (logs / "open.csv").exists()  # never the open one
    finally:
        shutil.rmtree(logs, ignore_errors=True)
        shutil.rmtree(wt, ignore_errors=True)


def test_evict_is_loud_on_failure(monkeypatch, capsys) -> None:
    logs = Path(tempfile.mkdtemp())
    wt = Path(tempfile.mkdtemp())
    try:
        now = 2_000_000_000
        for name in ("old.csv", "open.csv"):  # old is evictable; open is newest
            p = logs / name
            p.write_text("x", encoding="utf-8")
        os.utime(logs / "old.csv", (now - 30 * 86400, now - 30 * 86400))
        os.utime(logs / "open.csv", (now, now))
        _archived_gz(wt, "old.csv")
        monkeypatch.setattr(
            archive_logs.os,
            "remove",
            lambda *_: (_ for _ in ()).throw(OSError("locked")),
        )
        evicted = archive_logs.evict_archived(
            str(logs), str(wt), retention_days=14, now=now, log=lambda *_: None
        )
        assert evicted == []  # nothing removed
        err = capsys.readouterr().err
        assert "EVICTION FAILED" in err and "old.csv" in err  # loud on stderr (#1019)
    finally:
        shutil.rmtree(logs, ignore_errors=True)
        shutil.rmtree(wt, ignore_errors=True)


if __name__ == "__main__":
    for fn in (
        test_closed_segments_excludes_newest,
        test_closed_segments_explicit_exclude,
        test_closed_segments_empty_or_missing,
        test_archive_reconciles_and_is_idempotent,
        test_archive_catches_up_a_late_segment,
        test_gzip_is_byte_exact_and_deterministic,
        test_evict_removes_archived_and_old_only,
    ):
        fn()
        print(f"  PASS  {fn.__name__}")
    print("All checks passed.")
