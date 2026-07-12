#!/usr/bin/env python3
"""
archive_logs.py - B8: archive closed log segments to the Git LFS `data` branch.

Reconciliation-based and idempotent (NOT timer-based): scans <repo>/logs for any
*closed* CSV segment that has no matching .gz in the data-archive worktree, gzips
it byte-exact, and commits + pushes it to the orphan `data` branch via Git LFS.
Safe to run any time and from the logger on startup / rotation / shutdown - it
self-heals one missed rollover or twenty.

"Closed" = any logs/*.csv that is not the currently-open segment. The logger passes
its open file via exclude=/--exclude; standalone, the newest file is treated as
possibly-open unless --all is given.

Usage (standalone):
  python archive_logs.py            # archive all closed segments, commit + push
  python archive_logs.py --all      # include the newest too (logger is stopped)
  python archive_logs.py --no-push  # commit locally only

Requires: a one-time setup of the `data` worktree (see tools/archive/README.md).
"""

import argparse
import gzip
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
DEFAULT_LOGS = os.path.join(REPO, "logs")
DEFAULT_WORKTREE = os.path.join(REPO, ".data-worktree")
# #1035: keep this many days of closed segments UNCOMPRESSED in logs/ for the dashboard
# hot path (parse_cache tails a live .csv incrementally; a .gz is an immutable full
# re-parse). Older archived segments are evicted from logs/ - still fully readable from
# the archive (gather_inputs de-dupes archive+live by stem, reads .gz directly). The age
# gate doubles as durability: a segment this old was committed + pushed days ago.
DEFAULT_RETENTION_DAYS = 14


def _git(worktree, *args, check=True):
    return subprocess.run(
        ["git", "-C", worktree, *args], check=check, capture_output=True, text=True
    )


def _gzip_to(src, dst):
    """Gzip src -> dst byte-exact and deterministic (mtime=0), via a temp + atomic
    rename so an interrupted run never leaves a partial .gz."""
    with open(src, "rb") as fi:
        raw = fi.read()
    tmp = dst + ".tmp"
    with open(tmp, "wb") as fo:
        fo.write(gzip.compress(raw, mtime=0))
    os.replace(tmp, dst)


def _data_ahead(worktree):
    """True if the local data branch has commits not on origin/data (unpushed)."""
    r = _git(worktree, "rev-list", "--count", "origin/data..data", check=False)
    return r.returncode == 0 and r.stdout.strip() not in ("", "0")


def closed_segments(logs_dir, exclude=None, include_all=False):
    """Closed logs/*.csv (newest treated as possibly-open unless include_all)."""
    if not os.path.isdir(logs_dir):
        return []
    files = sorted(
        os.path.join(logs_dir, f) for f in os.listdir(logs_dir) if f.endswith(".csv")
    )
    open_path = None
    if exclude:
        open_path = os.path.abspath(exclude)
    elif not include_all and files:
        open_path = os.path.abspath(max(files, key=os.path.getmtime))
    return [f for f in files if os.path.abspath(f) != open_path]


def archive(
    logs_dir=DEFAULT_LOGS,
    worktree=DEFAULT_WORKTREE,
    exclude=None,
    include_all=False,
    push=True,
    log=print,
    retention_days=DEFAULT_RETENTION_DAYS,
):
    """Gzip + commit (+ push) any not-yet-archived closed segments. Returns the
    list of newly archived basenames. Best-effort: never raises on git/push
    failure (the next run reconciles)."""
    archive_dir = os.path.join(worktree, "data", "archive")
    if not os.path.isdir(worktree):
        log(f"[archive] data worktree missing: {worktree} (run setup); skipping")
        return []
    os.makedirs(archive_dir, exist_ok=True)

    new = []
    for src in closed_segments(logs_dir, exclude, include_all):
        dst = os.path.join(archive_dir, os.path.basename(src) + ".gz")
        if os.path.exists(dst):
            continue
        _gzip_to(src, dst)
        new.append(os.path.basename(dst))

    try:
        if new:
            _git(worktree, "add", "data/archive")
            _git(
                worktree,
                "commit",
                "-m",
                f"archive {len(new)} segment(s): {', '.join(new)}",
            )
            log(f"[archive] committed: {', '.join(new)}")
        if push and _data_ahead(worktree):
            r = _git(worktree, "push", "origin", "data", check=False)
            if r.returncode == 0:
                log("[archive] pushed to origin/data")
            else:
                log(f"[archive] push failed (retry next run): {r.stderr.strip()[:120]}")
    except subprocess.CalledProcessError as e:
        log(f"[archive] git error (retry next run): {(e.stderr or '').strip()[:120]}")

    # #1035: eviction — the bounded-growth half. Runs AFTER the commit/push above, so a
    # freshly-written .gz that hasn't committed yet is still protected by the age gate.
    evict_archived(
        logs_dir, worktree, retention_days=retention_days, exclude=exclude, log=log
    )
    return new


def evict_archived(
    logs_dir=DEFAULT_LOGS,
    worktree=DEFAULT_WORKTREE,
    *,
    retention_days=DEFAULT_RETENTION_DAYS,
    exclude=None,
    now=None,
    log=print,
):
    """Remove logs/ segment originals whose ``.gz`` is confirmed in the archive AND that
    are older than ``retention_days`` - B8's bounded-growth half (#1035). The read path
    de-dupes archive+live by stem, live winning (``gather_inputs``), and parses ``.gz``
    directly, so an evicted segment stays fully readable from the archive; only its
    hot-path speed changes (tail-cache vs full gz re-parse). NEVER evicts the open
    segment, and NEVER an un-archived one (an unbacked segment is kept, never lost).
    Loud on eviction failure (the #1019 pattern) so ``logs/`` never grows silently.
    Returns the evicted basenames."""
    archive_dir = os.path.join(worktree, "data", "archive")
    if not os.path.isdir(archive_dir):
        return []
    cutoff = (now if now is not None else time.time()) - retention_days * 86400
    evicted = []
    for src in closed_segments(logs_dir, exclude=exclude, include_all=False):
        gz = os.path.join(archive_dir, os.path.basename(src) + ".gz")
        if not os.path.exists(gz):
            continue  # not archived yet — NEVER evict an unbacked segment
        try:
            if os.path.getmtime(src) > cutoff:
                continue  # within the local retention window — keep it for the hot path
        except OSError:
            continue
        try:
            os.remove(src)
            evicted.append(os.path.basename(src))
        except OSError as e:
            name = os.path.basename(src)
            print(
                f"[archive] EVICTION FAILED (non-fatal) for {name}: {e}"
                " - logs/ keeps growing until this clears",
                file=sys.stderr,
                flush=True,
            )
    if evicted:
        log(
            f"[archive] evicted {len(evicted)} archived segment(s) from logs/ "
            f"(older than {retention_days}d; still readable from the archive)"
        )
    return evicted


def main():
    ap = argparse.ArgumentParser(
        description="Archive closed log segments to the data branch (B8)."
    )
    ap.add_argument("--logs", default=DEFAULT_LOGS, help="logs dir")
    ap.add_argument("--worktree", default=DEFAULT_WORKTREE, help="data worktree")
    ap.add_argument("--exclude", help="path to the open segment to skip")
    ap.add_argument("--all", action="store_true", help="include the newest too")
    ap.add_argument("--no-push", dest="push", action="store_false", help="commit only")
    ap.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help="keep this many days of segments local; evict older archived ones (#1035)",
    )
    args = ap.parse_args()
    done = archive(
        args.logs,
        args.worktree,
        args.exclude,
        args.all,
        args.push,
        retention_days=args.retention_days,
    )
    print(f"[archive] {len(done)} new segment(s) archived")


if __name__ == "__main__":
    main()
