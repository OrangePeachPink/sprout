# Cutting a release — the turnkey checklist

**What this is:** the per-release ritual (ADR-0009 §6), written so a first-time releaser — or the
maintainer at midnight — can cut a version end-to-end with zero tribal knowledge. Run it top to
bottom for every `vX.Y.Z`.

**Not this doc:** the *go-public* checklist (secrets/PII/license/visibility) is
[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) — that runs once, before v1.0.0. This one runs every release.

## 0. Preconditions

- [ ] The version's **milestone** is complete — every issue closed, or explicitly re-milestoned with a
      one-line reason (scope is a decision, not an accident).
- [ ] `main` is green (sprint posture: the slim gate + a fresh **weekly-battery dispatch** run —
      trigger it manually from Actions before cutting, since per-PR CI skips firmware).
- [ ] No open PR is targeted at this version (check the milestone's linked PRs).

## 1. Sync the version constants

- [ ] `pyproject.toml` → `version` = the release version. This is the **single product version line**
      (ADR-0009 §1) — everything else syncs to it (§3). *(Missed at the v0.7.2 cut — #1080; hence this
      list now names every target explicitly.)*
- [ ] `CITATION.cff` → `version` matches `pyproject.toml`.
- [ ] `docs/index.html` → the JSON-LD `version` matches (the structured-data footprint, #1221).
- [ ] `firmware/include/config.h` → `PLANTS_FW_VERSION` matches the release version (ADR-0009 §3).
      If firmware didn't change this release, the constant still bumps at the next firmware release —
      note per-component reality in the notes instead.

## 2. Close the milestone → the draft appears

- [ ] Close the milestone (Issues → Milestones → Close). The `release-draft` workflow drafts the
      GitHub Release with **auto-generated, tag-to-tag notes** grouped by `type:` label.
      *(Fallback: Actions → "release draft on milestone close" → Run workflow with the version.)*

## 3. Curate the notes — the quality bar (ADR-0009 §6)

Notes are a per-version **changelog, not product documentation**. Approve against five checks — never
exhaustiveness:

- [ ] **Accurate** — every claim true; no "complete/validated/compliant" unless verified; limitations disclosed.
- [ ] **At altitude** — a 30-second skim says what this version delivers and what it doesn't.
- [ ] **Version-framed** — a delta since the previous tag (only a first release is a baseline snapshot).
- [ ] **No invented history** — never reconstruct notes for versions that didn't exist.
- [ ] **Points to the record** — link issues/docs for the how-and-why instead of duplicating them.

Then: add a 2–4 line human lede above the generated list (what this release *means*), and state
**per-component reality** (firmware / host / docs — what actually changed, ADR-0009 §3).

- [ ] **Register sweep** (#1161) — run `just voice-guard --all` and attach the delta (or "clean")
      to the release evidence; the retired register (PR #1099's wash) never migrates back silently.
      **Include repo metadata**: the GitHub description, topics, and About fields live in Settings,
      outside every tree sweep — read them by eye (the 2026-07-19 "Honest…" description hid there
      through every wash).

## 4. CHANGELOG

- [ ] Add the version section to [`CHANGELOG.md`](../../CHANGELOG.md) (same content, per-component,
      Keep-a-Changelog form) — move items out of `[Unreleased]`, add the compare links. PR it (docs PR,
      normal gate).

## 5. Publish

- [ ] **Publishing the release creates the tag** — final look, then Publish. Verify:
      `git ls-remote origin refs/tags/vX.Y.Z` returns the ship commit.
- [ ] Card sweep, mechanized (#732): **`just board-hygiene`** must print *clean* (zero
      closed-not-Done) before the milestone closes; fix any findings, rerun to green. *(Fallback if
      the recipe or the ProjectV2 token is ever unavailable: eye-sweep the milestone's merged PRs
      and closed issues to Done.)*

## 6. Open the next cycle

- [ ] Create the next milestone(s) per the version roadmap (ADR-0009 §5); triage carry-overs into them.
- [ ] **Good-first shelf: intentional growth only** (maintainer's ruling, 2026-07-19 — supersedes the
      #1088 keep-6-8 rule). **No automatic restock**: contributor waves are paced by the maintainer,
      who seeds the next batch deliberately (her UI-review hour with DX) when she wants one. At the
      cut: absorb any still-unclaimed shelf items into lanes (each close linking its implementing PR —
      completed good-firsts are teaching artifacts), and leave the shelf as she set it.
- [ ] Post the release link where the team coordinates; the retro (per-release, DesignQA chunk-a) keys
      off the shipped version.

*Owned by Workflow (ADR-0009: "the Workflow lane cuts releases"). First exercised for v0.7.1.*
