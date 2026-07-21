#!/usr/bin/env python3
"""Where the host's data lives — a layer-0 leaf (ADR-0038 §1, §5.1).

**Zero imports of ours, by construction.** That is what makes a leaf a leaf: it can be
imported from any layer without dragging anything behind it, so the import graph stays
a DAG no matter who needs a path.

**The pathology this ends.** `serve.py` imported the ~2,000-line `dashboard` module to
obtain two `Path` constants — the identical shape the `design_assets` leaf fixed for CSS
(#1336 / PR #1387), where four modules imported that same module for two constants and
three wanted nothing else from it. Importing a large module for a small value is not
merely untidy: it means a change to the dashboard's analytics can break a caller that
only ever wanted to know where `logs/` is, and it forces an import direction that
ADR-0038 §2 would otherwise forbid.

It is also the precondition for the `build_context` extraction (#1336 §5.3). These two
paths are the *only* constants shared between the card-payload cluster and the rest of
`dashboard.py`. With them here, the seam between those two halves is clean; without
them, the extracted module would have to import upward — or, worse, keep its own second
copy of a path, which is how two halves of one program start disagreeing about where
the data is.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# B8 gzip archive of closed segments (read for deep history once they leave logs/).
ARCHIVE_DIR = REPO / ".data-worktree" / "data" / "archive"
LOGS_DIR = REPO / "logs"
