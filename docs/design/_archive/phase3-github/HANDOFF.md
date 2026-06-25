# Design-lane handoff — Phase 3 (batch 1): the GitHub-facing surface

**From:** Design lane · **Date:** 2026-06-24 · **Re:** README hero, social preview, label palette, Discussions
&amp; release-notes voice
**Flow:** I zip → Veronica relays to a proxy → the proxy places each file per the manifest, applies the repo
edits, commits after review.

> This is the **independent batch** of Phase 3 — everything that doesn't depend on the Workflow lane's
> scaffolding. The **label palette is the priority**: it feeds label creation, so apply it first/as labels are
> stood up. The issue-form and PR/CONTRIBUTING voice passes are **held** until the Workflow lane hands me the
> YAML/skeletons (see bottom). Backlog/issues stay no-fly. No binaries over ~1 MB; the two PNGs are ~40–80 KB.

---

## Manifest — place every file exactly here

| In this zip | → Destination in repo | What / why | Who consumes |
|---|---|---|---|
| `.github/labels.yml` | `.github/labels.yml` | **DELIVER FIRST.** ~16 brand-colored labels (type/area/layer/community/meta), colors from `sprout-tokens.css`, voiced descriptions. Compatible with a label-sync action. | **Workflow** (at label creation) |
| `README.md` | `README.md` | The repo's face: hero banner, first-person intro, what/how, honesty principles, brand links, layout, status. **Updates the existing README** — see reconcile note. | everyone |
| `docs/design/brand/readme-hero.png` | `docs/design/brand/readme-hero.png` | 1280×400 hero banner (dark / soil mode) — README default + dark theme. | README |
| `docs/design/brand/readme-hero-light.png` | `docs/design/brand/readme-hero-light.png` | 1280×400 hero banner (light mode) — served to light-theme viewers via `<picture>`. | README |
| `docs/design/brand/social-preview.png` | `docs/design/brand/social-preview.png` | 1280×640 social card (dark) — the recommended upload (works on both GitHub themes). | maintainer (Settings upload) |
| `docs/design/brand/social-preview-light.png` | `docs/design/brand/social-preview-light.png` | 1280×640 social card (light) — alternative if a light card is preferred. | maintainer (optional) |
| `docs/community/discussions.md` | `docs/community/discussions.md` | Voiced category descriptions (Announcements / Ideas / Q&A / Show &amp; tell) + the pinned welcome post. | **Workflow** (enabling Discussions) |
| `docs/community/release-notes-voice.md` | `docs/community/release-notes-voice.md` | Voiced header/footer template + tone for generated release notes. | **Workflow** (releases) |

## Repo edits / actions to apply

1. **Labels (priority):** apply `.github/labels.yml` when standing labels up (e.g. a label-sync action or
   `gh label create`), so they're on-brand from creation.
2. **README:** replace the current `README.md` with this one. The hero banner is a theme-responsive
   `<picture>` (dark on dark GitHub themes, light on light). **Reconcile note —** I kept technical depth
   light and linked out to lane-owned docs (`firmware/`, `tools/`, `docs/`, the ADRs); if the existing README
   has detail worth keeping (wiring specifics, build steps), fold it under the matching section rather than
   losing it. Firmware/Data lanes can extend their sections.
3. **Social preview:** upload `docs/design/brand/social-preview.png` (dark) at **Settings → General →
   Social preview** — it reads well on both GitHub themes. `social-preview-light.png` is provided as an
   alternative. (Social preview is a single uploaded image; it can't be theme-responsive like the README
   banner.) The files are also committed for versioning.
4. **Discussions:** when the Workflow lane enables Discussions, seed the four category descriptions and pin
   the welcome post from `docs/community/discussions.md`.
5. **Release notes:** when wiring `.github/release.yml`, adopt the header/footer + tone from
   `docs/community/release-notes-voice.md`.

Suggested commit: `docs(brand): add README hero, social preview, label palette, community voice (Phase 3)`.

## For-lanes notes

- **Workflow:** labels.yml, discussions.md, and release-notes-voice.md are yours to apply; structure stays
  yours, voice/colors are mine. The label colors map to tokens (commented in the file) — keep them as-is so
  the board stays on-brand.
- **All lanes:** the README links to your areas; extend your own section rather than reworking the hero/brand.
- **Boundary held:** label/issue tooling copy is intentionally **not** in Sprout's first-person voice (that's
  for plant-facing surfaces, ADR-0007 §6). The one in-character public greeting is the Discussions welcome
  post.

## Held — awaiting Workflow-lane skeletons (then I do the voice pass)

- **Issue-form content &amp; voice** — needs the `feature` / `bug` / `task` YAML form structures to voice
  against.
- **PR template + `CONTRIBUTING.md` voice** — needs the Workflow lane's structure; I do the voice pass on top.

Send those skeletons whenever they're ready and I'll turn the voice pass around as Phase 3 batch 2. After
Phase 3 lands, I hold for the no-fly lift + assigned issues.
