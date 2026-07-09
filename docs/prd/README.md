# Product Requirements Docs (`docs/prd/`)

A PRD captures **what we're building and why**, before the how — for work that's bigger than a single
issue. It's the level between a loose idea (a [Discussion](https://github.com/OrangePeachPink/sprout/discussions))
and the shippable slices that implement it (Issues). See
[ADR-0003 §4](../adr/0003-work-pipeline.md).

## When to write one

Write a PRD when the work is **bigger than a few issues**, or it:

- has several acceptance criteria, or spans multiple areas, or needs design input;
- needs shared understanding *before* building, to avoid building the wrong thing.

A single, shippable change does **not** need a PRD — it's just an issue.

## How it flows

```text
idea (Discussion) → PRD (here) → epic (parent issue + sub-issues) → issues → PR → release
```

1. Copy [`TEMPLATE.md`](TEMPLATE.md) to `docs/prd/NNN-short-title.md`.
2. Fill it in and open it as a pull request — a PRD is reviewed like code.
3. Once **Accepted**, break it into vertical-slice issues (each a thin end-to-end piece of value),
   grouped under an epic parent issue.

## Status

A PRD carries a status in its header: **Draft → Accepted → Implemented**. Link it to the epic/issues it
spawns, and link those back to it.
