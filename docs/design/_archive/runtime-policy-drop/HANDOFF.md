# Design-lane handoff — runtime policy doc

**From:** Design lane · **Date:** 2026-06-24 · **Re:** durable runtime-coherence policy for `docs/design/`

The standalone policy reference the intake thread asked for. Captures the adopted model (a) — self-contained
per version — and the invariant intake enforces.

## Manifest

| In this zip | → Destination in repo | What / why |
|---|---|---|
| `docs/design/RUNTIME.md` | `docs/design/RUNTIME.md` | The runtime policy: per-folder ownership, root = current shared runtime, the enforced invariant, current state, the one converge case, and manifest practice. |

## Repo edit

- Add a link from `docs/design/README.md` so it's discoverable, e.g. under a short heading:
  `**Runtime:** how `support.js` is versioned across these folders → [RUNTIME.md](RUNTIME.md).`

## Notes

- Reflects the corrected lineage: `sprout-v2/` is the only folder on the older runtime (`ac3b4f23`); root,
  `brand/`, and `sprout-v3/` are on the newer one (`a37fec98`).
- No code or runtime files change — this is documentation only. Not backlog/issues (no-fly).

Suggested commit: `docs(design): record support.js runtime policy (self-contained per version)`.
