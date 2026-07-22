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

## 5. Sign the draft — attach the assets BEFORE publishing (the #1438 guard)

**This is the step whose absence shipped v0.8.0 asset-less.** GitHub *immutable releases* lock a
release's assets at the Publish click; `sign-release.yml` therefore attaches to the **draft** and the
maintainer's Publish then seals it immutable *with* its assets. **Publishing before this step seals an
empty release, and it cannot be fixed after — only re-cut.** Never skip to §6 without a green draft here.

- [ ] **Dispatch the signer against the draft tag.** The `release-draft` workflow's success notice
      prints the exact command; it is:
      `gh workflow run sign-release.yml -f tag=vX.Y.Z`
      *(Why manual: a `GITHUB_TOKEN`-created draft does not fire `release: created` — the recursion
      guard. A human-created draft auto-signs and this dispatch is a no-op. Either way, confirm the run.)*
- [ ] **The signer must pass its own fail-closed gates** (watch the run): signing key present (no key →
      it refuses, by design), builds the draft's `target_commitish` (the commit that becomes the tag —
      the tag does not exist yet), both boards `[SUCCESS]`, `.sig` files produced.
- [ ] **VERIFY the draft now carries assets — this is the gate, not a nicety:**
      `gh release view vX.Y.Z --json isDraft,assets -q '"draft=\(.isDraft) assets=\(.assets|length)"'`
      must print `draft=true` and a **non-zero** asset count (the per-board bins + their `.sig` + the
      `SHA256SUMS`). **`assets=0` means STOP** — the signer failed or was never dispatched; do not publish.
- [ ] **Record the receipt** on the release-cut evidence: the asset list and the `SHA256SUMS`, so the
      flasher's stable channel (#1334) has verifiable bytes to point at.

### 5.1 The dry-run seam walk — do this ONCE before a lane's first real cut, and any time the pipeline changes

The asset-less cut happened because no one walked draft → sign → verify → publish end-to-end before it
mattered. Walk it on a **throwaway pre-release tag** (e.g. `v0.0.0-cuttest`) so a mistake costs nothing:

1. Draft a release on the test tag (Actions → release-draft, or `gh release create v0.0.0-cuttest --draft --notes test`).
2. Dispatch `sign-release.yml -f tag=v0.0.0-cuttest`; watch every gate fire.
3. Run the §5 verify — confirm `assets>0` on the draft.
4. Publish the test draft; confirm it seals immutable **with** its assets (`assets>0`, `isDraft=false`).
5. Point a local flasher build at the test release; confirm the stable manifest resolves the released
   bytes' SHA (the #1334 seam).
6. **Delete the test release + tag.** The walk's only output is the confidence that the real cut works.

If any step surprises you, the real cut is not ready — fix the pipeline, re-walk, then cut for real.

## 6. Publish

- [ ] **Do not publish until §5 is green** — re-confirm the draft shows `assets>0`. Publishing seals
      the release immutable *with whatever assets it has*; an empty draft becomes a permanent
      asset-less release (the v0.8.0 failure, #1438).
- [ ] **Publishing the release creates the tag** — final look, then Publish. Verify:
      `git ls-remote origin refs/tags/vX.Y.Z` returns the ship commit, **and**
      `gh release view vX.Y.Z --json isDraft,assets -q '"published=\(.isDraft==false) assets=\(.assets|length)"'`
      prints `published=true` with a non-zero asset count.
- [ ] Card sweep, mechanized (#732): **`just board-hygiene`** must print *clean* (zero
      closed-not-Done) before the milestone closes; fix any findings, rerun to green. *(Fallback if
      the recipe or the ProjectV2 token is ever unavailable: eye-sweep the milestone's merged PRs
      and closed issues to Done.)*

## 7. Open the next cycle

- [ ] Create the next milestone(s) per the version roadmap (ADR-0009 §5); triage carry-overs into them.
- [ ] **Good-first shelf: intentional growth only** (maintainer's ruling, 2026-07-19 — supersedes the
      #1088 keep-6-8 rule). **No automatic restock**: contributor waves are paced by the maintainer,
      who seeds the next batch deliberately (her UI-review hour with DX) when she wants one. At the
      cut: absorb any still-unclaimed shelf items into lanes (each close linking its implementing PR —
      completed good-firsts are teaching artifacts), and leave the shelf as she set it.
- [ ] Post the release link where the team coordinates; the retro (per-release, DesignQA chunk-a) keys
      off the shipped version.

*Owned by Workflow (ADR-0009: "the Workflow lane cuts releases"). First exercised for v0.7.1.*

## 8. If a shipped release goes bad — feed curation (ADR-0009 §7)

*Not part of the normal cut — the break-glass step when the SBOM / dependency audit (or any
confirmed report) names a shipped release as carrying a known-vulnerable package. Executes
ADR-0026's amended Decision 4: remediation at the source, never a device-side counter.*

- [ ] Confirm which shipped release(s) are affected; link the evidence (audit run / advisory).
- [ ] **With the maintainer's confirm** (public-facing status change): mark the affected release
      **pre-release** (demotes it from Latest — the record itself is never deleted) and prepend the
      SECURITY note to its notes: *affected component + versions · the fixed version · evidence link*.
- [ ] Verify the fixed release exists and is the **Latest** being offered (cut it first if needed —
      the normal checklist above applies).
- [ ] *(Activates with the #302 Phase-1 pull feed)*: remove the curated-out version from the served
      manifest so OTA devices are only ever offered good builds.
- [ ] Log the curation on the release record + the cycle's digest thread.

*Owned by Workflow; the maintainer confirms the pull.*
