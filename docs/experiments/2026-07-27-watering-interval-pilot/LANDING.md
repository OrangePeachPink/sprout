# Landing note — 2026-07-28, Workflow gate

Landed from the bench packet for issue #1646 (the antecedent-interval experiment),
classified per the bench ruling as **annotated pilot/reference evidence** — the 6.07-day
antecedent interval is neither Arm A (3-4 days) nor Arm B (10-12 days), so #1646 stays open.

**Two files named in `FILELIST.sha256.tsv` are deliberately absent from this landing:**
`WORKFLOW_HANDOFF.md` and `ISSUE_COMMENT_DRAFT.md`. Both are routing artifacts addressed
to the project's internal process, and one carries agent-facing instructions — the class
audience-scoped out of the public repo after the #1117 incident. Their hashes remain in the
checksum list for completeness; the originals stay in the local scratch packet.

Raw slices are byte-preserving UTC-window extracts (two exceed 2 MB and are landed whole —
byte preservation outranks the historical split convention, which existed for far larger
parts). Gate-run PII scan clean; no MAC/USB identifiers, hostnames, or non-RFC1918
addresses; per ADR-0015 nothing here required genericizing.

**Split note (2026-07-28):** three raw slices exceeded the repo's 1024 KB large-file hook and are
landed as lossless `_partNN.csv` splits (line-boundary cuts; `split -C`). Concatenating a file's
parts in order restores it byte-exact, and the original's SHA-256 in `FILELIST.sha256.tsv` is the
verification target: `cat name_part*.csv > name.csv && sha256sum -c`. This — not any GitHub limit —
is what the split convention is for.
