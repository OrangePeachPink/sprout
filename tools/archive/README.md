# plants - log archive to Git LFS (B8)

Durably back up the raw capture so data survives a machine crash / move, without bloating the code repo.
Closed log segments are gzipped and stored on the orphan **`data`** branch via **Git LFS**, separate from
the code on `main`.

## How it works

- `archive_logs.py` is **reconciliation-based**: it scans `logs/` for any *closed* segment (`*.csv`) lacking
  a matching `.gz` in the archive, gzips it byte-exact, and commits + pushes it to the `data` branch.
  Idempotent - safe to run anytime; self-heals one missed rollover or twenty.
- The host logger calls it automatically on **startup**, each **rotation**, and a clean **shutdown**
  (best-effort - a git/network failure never disrupts logging).
- The live `logs/*.csv` stay gitignored; only the frozen `.gz` are tracked (LFS). The `.data-worktree/`
  worktree is gitignored on `main`.

## Manual use

```text
python tools/archive/archive_logs.py            # archive closed segments + push
python tools/archive/archive_logs.py --all      # include the newest too (logger stopped)
python tools/archive/archive_logs.py --no-push  # commit locally only
```

## One-time setup (fresh clone / new machine)

Git LFS must be installed (`git lfs version`), then attach the `data` worktree:

```text
git lfs install
git fetch origin data
git worktree add .data-worktree data      # data branch already exists on origin
```

First-ever setup only (if the `data` branch does not exist yet): `git worktree add --orphan -b data
.data-worktree`, add a `.gitattributes` tracking `data/archive/*.csv.gz` via LFS, commit, and
`git push -u origin data`.

## Recovery on a new machine

```text
git clone <repo>                       # main = code
git fetch origin data
git worktree add ../plants-data data   # or: git checkout data
git -C ../plants-data lfs pull         # fetch the .gz objects
# gunzip data/archive/*.csv.gz; rebuild any derived DB (BACKLOG E5)
```

The archived CSV schema is `docs/TELEMETRY_SCHEMA.md` on `main` (sample: `docs/sample_log.csv`).
