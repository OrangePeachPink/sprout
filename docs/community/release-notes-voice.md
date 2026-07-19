# Release-notes voice & template

Phase 3 (Design lane). GitHub generates release notes from merged PRs, categorized by `type:` label via
`.github/release.yml` (the Workflow lane owns that file and the categories). This supplies the **voiced
header and footer** that wrap the generated body, and the tone to keep.

## The template

When cutting a release (a closed milestone = a build, SemVer per ADR-0003 §9), wrap the auto-generated notes
like this:

```markdown
## Sprout {version} — "{codename}"

Hi, it's Sprout. Here's what changed this time — short version: {one plain sentence}.

<!-- GitHub's generated, type:-categorized notes go here -->

—
**Tend well.** Full detail in the commits; questions in [Discussions](https://github.com/OrangePeachPink/sprout/discussions).
```

## Tone

- **Speak as Sprout, first person** — the header/footer are plant-facing, so they follow the voice rules
  (calm, fond, plain, one short line; no hype, no emoji, no invented metrics). See
  [ADR-0007 §3](../adr/0007-brand-guidelines.md).
- **The generated body stays plain.** The per-PR lines are technical and factual — don't rewrite them in
  character. Sprout only frames the release (the header + footer); the changelog itself is just the work.
- **One plain sentence up top.** What actually changed and why it matters — no "exciting", no "huge".
  *"I can finally tell three plants apart by their drying speed."* beats *"Massive analytics update!"*

## Codenames (optional, light)

If you want a codename, use **plant cultivars or windowsill herbs** — `Basil`, `Monstera`, `Thyme`,
`Pothos`. Keep it a small wink, never a gate; a release is fine with no codename at all.

## Examples

- **Patch:** `## Sprout v0.7.1 — "Basil"` · *"Hi, it's Sprout. Small one: I stopped double-counting a dropped
  sweep, so the integrity panel is honest again."*
- **Minor:** `## Sprout v0.8.0 — "Monstera"` · *"Hi, it's Sprout. I can now forecast a next-day drying curve
  per plant — still gated until the trend is statistically real, so no made-up ETAs."*
