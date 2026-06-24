# plants - data archive branch

This **orphan** branch is the data vault for the `plants` project (BACKLOG **B8**). It holds the
gzipped, byte-exact raw log segments under `data/archive/*.csv.gz`, stored via **Git LFS**.

- Written **only** by the host logger's archive step (`tools/archive/archive_logs.py` on `main`): each
  closed/rotated `logs/*.csv` segment is gzipped here, committed once (immutable, uniquely named), and
  pushed automatically. LFS therefore stores each segment exactly once.
- The **code** lives on `main`; this branch is intentionally code-free (orphan), so it never races with
  code commits and keeps `main`'s history clean.

## Recovery on a new machine

1. `git clone <repo>` - gets `main` (the code).
2. `git fetch origin data` then `git worktree add ../plants-data data` (or `git checkout data`).
3. `git lfs pull` - fetches the `.gz` objects.
4. `gunzip` the segments; rebuild any derived DB from them (BACKLOG E5).

The archived CSV schema is `docs/TELEMETRY_SCHEMA.md` on `main` (sample: `docs/sample_log.csv`).
