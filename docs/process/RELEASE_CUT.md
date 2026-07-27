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

## 1. Sync the version constants — **and the dates**

> **The lesson of the v0.8.1 cut: every place we declare a *version* is guarded, and every place we
> declare a *date* is not.** `version-sync-guard` (#1407) checks the version sites against canonical
> `pyproject.toml` and reports green — while the JSON-LD's `dateModified` sat two releases stale and
> `CITATION.cff` had no `date-released` at all. A green guard is evidence about versions only.
>
> **Mostly closed since.** `uv.lock` is now a guarded version site (#1633), and **both** date rows —
> `date-released` and `dateModified` — are checked for presence, format, not-in-the-future, and
> **agreement with each other** (#1637). That last one exists because correcting one row and
> forgetting the other is the mistake that produced this whole thread.
>
> What the guard still *cannot* know is whether a date matches the release that actually published —
> that needs the API, which a pre-commit hook has no business calling. Note the asymmetry: a date in
> the **future** is detectable from today's date alone, but a date in the **past** is indistinguishable
> from a correct one. **Treat a green guard as evidence the dates are well-formed and consistent, never
> that they are right.**

- [ ] `pyproject.toml` → `version` = the release version. This is the **single product version line**
      (ADR-0009 §1) — everything else syncs to it (§3). *(Missed at the v0.7.2 cut — #1080; hence this
      list now names every target explicitly.)*
- [ ] `CITATION.cff` → `version` matches `pyproject.toml`.
- [ ] `docs/index.html` → the JSON-LD `version` matches (the structured-data footprint, #1221).
- [ ] `firmware/include/config.h` → `PLANTS_FW_VERSION` matches the release version (ADR-0009 §3).
      If firmware didn't change this release, the constant still bumps at the next firmware release —
      note per-component reality in the notes instead.
- [ ] `uv.lock` → the `sprout` package entry matches. **Fix by regenerating (`just lock`), never by
      hand** — it is generated state. Guarded since #1633; before that a stale lock was the
      `uv run --frozen` trap the justfile calls *"a brutal, causeless first-PR trap"* (#254): it lands
      on whoever runs the next command, with an error naming none of this.

**The date rows — set them in ONE edit; the guard proves they are well-formed and agree, not that
they are right:**

- [ ] `CITATION.cff` → `date-released` = the cut date, **in UTC** (`date -u +%F`). It is what makes a
      citation resolvable to a point in time, and GitHub's "Cite this repository" widget renders it
      (#1637).
- [ ] `docs/index.html` → the JSON-LD `dateModified` = **the same date**. **Found two releases stale at
      the v0.8.1 cut** while `version` beside it was correct — machine-readable, publicly consumed, and
      silently wrong. (`datePublished` is first publication and does **not** move; the guard ignores it
      on purpose, because checking it against the cut date would demand the wrong edit every release.)

*Both dates are a prediction until the publish click. Set them here anyway — a date stale by hours
beats an absent or two-release-old one — but **write them in UTC**, and the reason is not pedantry:*

> **v0.8.1 got this wrong on the first try.** `date-released` was set to `2026-07-25` at §1 and the
> release published at `2026-07-26T01:20:53Z`. Nothing went slowly; the cut simply ran on a US evening,
> which is already the next day in UTC. An evening cut is the normal case here, so "same-day" in local
> time is a **whole calendar day** wrong in the timestamp everyone else reads. `date -u +%F` costs
> nothing and removes the entire class.

*If a cut starts before midnight UTC and publishes after it, the date written at §1 will be a day
early no matter how carefully it was typed. That is the one case worth a post-publish correction —
the guard will not catch it, because a past date is not suspicious.*

### 1.1 Reconcile the milestone against the tag line — both directions

**The tag is the line, and the line moves.** A milestone is a plan made days earlier; the tag is the
fact. Whatever is merged when you tag *ships in this release* no matter which milestone it carries,
and whatever is still open *doesn't* no matter how confidently it was planned. Reconcile the record to
the fact **before** closing the milestone (§2) — once it's closed you're editing history rather than
recording it. This runs at every cut, not just when something looks wrong.

**What the milestone is and isn't.** It does **not** generate the notes — those are auto-generated
**tag-to-tag from commits** (§2), so a wrong milestone won't corrupt the release text. What it *is* is
the traceability surface: the milestone page is the answer to "what shipped in this version," and it
is where the maintainer's PR queue and contributors' credited work both resolve to a release. A
milestone that disagrees with the tree misstates the record on the one page people consult to check
it.

**Milestone PRs, not just issues** *(maintainer's ruling, v0.8.1 cut)*: PRs get the version milestone
as a rule. The work is traced through the PR queue and contributors are credited on PRs, so a PR that
links to its release is the useful artifact. Prior releases were inconsistent about this — v0.7.3
milestoned 14 PRs, v0.8.0 only 6 — which is exactly the ambiguity this line removes.

Both directions, and the second one is the one that gets skipped:

- [ ] **Under the line → pull in.** Anything **merged or closed** that carries a *later* milestone (or
      none) gets re-milestoned to **this** version. Its bytes are in the tag; the record must say so.
      Late-cycle work is the usual source — an item planned for next release, built early, merged
      before the cut.
- [ ] **Over the line → push out.** Anything **still open** on this milestone moves to the next
      version or a later wave, each with a one-line reason. Scope is a decision, not an accident
      (§0) — and **milestone placement for bench / hardware / scope is the maintainer's call**, never
      a lane's default.

Find both sets by query, never by memory (ADR-0003 §11):

      # under the line — merged since the previous tag but carrying the wrong milestone, or none.
      # The previous tag's publish date is the boundary; anything merged after it is in this release.
      PREV=$(gh release view --repo OrangePeachPink/sprout --json publishedAt --jq .publishedAt)
      gh pr list --repo OrangePeachPink/sprout --state merged --limit 200 \
        --json number,title,milestone,mergedAt \
        --jq --arg prev "$PREV" '.[] | select(.mergedAt > $prev)
              | select((.milestone.title // "none") != "v0.8.1")
              | "\(.number) [\(.milestone.title // "NONE")] \(.title)"'

      # under the line — closed issues pointed at a later release
      gh issue list --repo OrangePeachPink/sprout --state closed --milestone "v0.8.2" --json number,title

      # over the line — still open on the milestone being cut
      gh issue list --repo OrangePeachPink/sprout --state open --milestone "v0.8.1" --json number,title

**Use the previous tag as the boundary, not "everything unmilestoned."** Merged PRs from earlier
releases are also unmilestoned; sweeping without the date filter back-dates them into this version.

*(Ruled by the maintainer at the v0.8.1 cut, after a manual reconciliation moved 29 issues and 10 PRs
that had been built and merged under a next-release label. It was not a labelling slip — it is what
always happens when a release's last days go well, which is why it is a standing step rather than a
correction.)*

### 1.2 Reconcile the contributors — by query, never from the week's impression

**Ask: did anyone outside the maintainer land a change in this window, and does the record say so?**
Both halves matter, and they fail in opposite directions — a merged contributor who never gets listed
is an uncredited person, and a *listed* contribution that never merged is a false claim about someone
else's work in a public file.

- [ ] Run the query. External human merges since the previous tag:

            PREV=$(gh release view --repo OrangePeachPink/sprout --json publishedAt --jq .publishedAt)
            gh pr list --repo OrangePeachPink/sprout --state merged --limit 200 \
              --json number,title,author,mergedAt \
              --jq --arg prev "$PREV" '.[] | select(.mergedAt > $prev)
                    | select(.author.login != "OrangePeachPink")
                    | select(.author.login | startswith("app/") | not)
                    | "#\(.number) @\(.author.login) \(.title)"'

- [ ] Every name it returns has an entry in `CONTRIBUTORS.md`, citing the **merged PR** (the file's own
      convention — not the tracking issue).
- [ ] Nothing in the release notes or CHANGELOG credits a contribution that **has not merged**. An open
      PR at the tag is credited when it merges, which is the rule `CONTRIBUTORS.md` states for itself.
- [ ] Bot authors (`app/dependabot`) are not contributors and get no entry.

*(Added after the v0.8.1 CHANGELOG shipped the line "Sprout's first external contribution merged" —
false twice: nothing external merged that release, and four community contributors already predated it.
It was written from an impression of the week rather than from output, in the file whose entire purpose
is to be the record. The maintainer caught it before the tag by asking this question.)*

## 2. Close the milestone → the draft appears

- [ ] **Run the preflight FIRST — this is the last cheap moment:**

          just release-preflight vX.Y.Z

      One pass/fail table over §0/§1/§1.1/§1.2/§4: the version and date sites, a `CHANGELOG` section
      for this tag, the milestone empty of open issues and PRs, and the contributors merged since the
      previous tag. At the v0.8.1 cut these were ~15 separate manual queries across an hour, and
      **four of them did not exist as checks at all** — they surfaced because the maintainer asked, not
      because a gate ran. Once §2 completes the draft exists; after §6 the assets are immutable (#1661).

      *Rows it reports but does not decide are marked `SKIP`. Contributor reconciliation is a
      judgement about crediting a person — a gate that guessed would fail on a correct release, and
      §1.2 is where the judgement belongs.*

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

- [ ] **@-mention scan on the generated list — before publish.** Auto-generated notes embed **PR
      titles verbatim**, and PR titles are prose nobody writes with GitHub's mention parser in mind.
      Any `@` in a title becomes a **live mention of whoever owns that handle**: a schema property, an
      email fragment, a decorator, `@media`. Scan the composed body and backtick anything that is not
      a real participant — then fix the **PR title at the source**, or the next regeneration
      reintroduces it.

      ```
      gh release view <tag> --repo OrangePeachPink/sprout --json body --jq .body \
        | grep -oE '(^|[^`[:alnum:]/])@[A-Za-z0-9][-A-Za-z0-9]*' | sort -u
      ```

      *(Caught at the v0.8.1 cut: `Person @id mirror` — the schema.org `@id` property in PR #1495's
      title — rendered as a mention of an unrelated GitHub user, who was then **listed as a release
      contributor** on the draft. Only two authors existed in the entire tag range. This is worse than
      cosmetic: the stranger gets notified, the credit is false and public, and while a release body
      stays editable, **the notification fires once**. Same failure as crediting a contribution that
      never merged (§1.2), arriving through a door nobody typed.)*

- [ ] **Register sweep** (#1161) — run `just voice-guard --all` and attach the delta (or "clean")
      to the release evidence; the retired register (PR #1099's wash) never migrates back silently.
      **Include repo metadata**: the GitHub description, topics, and About fields live in Settings,
      outside every tree sweep — read them by eye (the 2026-07-19 "Honest…" description hid there
      through every wash).

## 4. CHANGELOG

- [ ] Add the version section to [`CHANGELOG.md`](../../CHANGELOG.md) (same content, per-component,
      Keep-a-Changelog form) — move items out of `[Unreleased]`, add the compare links. PR it (docs PR,
      normal gate).
- [ ] **Check for missed prior sections** (maintainer-ruled 2026-07-24, the #1534 fold): confirm every
      tagged release back to the last recorded section has its own `[x.y.z]` entry. Precedent: v0.8.0
      shipped and `[Unreleased]` still read "Next cycle: v0.8.0" — the canonical in-repo record denied
      a tagged release for days (ADR-0009 §6.3). The v0.8.1 cut writes **both `[0.8.0]` and `[0.8.1]`**.

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
- [ ] **VERIFY the artifact contract — this is the gate, not a nicety:**

          just release-verify vX.Y.Z

      **`assets > 0` is not the check**, and it is what this step asked for until #1662 — it passes on
      a release missing a signature. `release-verify` downloads the assets and asserts the **exact**
      inventory per board class, that `SHA256SUMS` covers all of them, that the real bytes / the sums /
      the manifest's own `sha256` all agree, that `provenance.git` is the draft's target, and that the
      body carries no unintended `@mention` (#1639). Non-zero exit means **do not publish**.

      *(At the v0.8.1 cut this was done by hand with ad-hoc Python three times, once per signing
      cycle.)*

- [ ] **If anything fails, re-sign as ONE transaction rather than by hand:**

          just release-resign vX.Y.Z            # --dry-run reports the plan and stops

      It refuses to start while another signer run is live (the v0.8.1 collision — see §5.0), confirms
      the target, clears the existing assets (`gh release upload` has no `--clobber`, by design),
      dispatches once, waits out the ~4 minute build, and finishes by running `release-verify` (#1663).
- [ ] **VERIFY the manifest is not labelled `-alpha` — the other thing that cannot be fixed after
      publish** (#1630):

          gh release download vX.Y.Z --repo OrangePeachPink/sprout \
            --pattern 'manifest*.json' --dir /tmp/relcheck --clobber
          jq -r '.version, .provenance.channel' /tmp/relcheck/manifest*.json

      must print the bare version and `stable` — **`X.Y.Z-alpha` or `channel: alpha` means STOP.**
      A release build labels itself from the tag it is signed for (#1399); if it says alpha, the
      build could not see its tag and the manifest is describing an unreleased build. Publishing
      seals it: the fleet pulls that manifest and the flasher reads it, and neither can be corrected
      in place — only re-cut under a new tag. *(The §5.1 dry-run walk cannot catch this: a throwaway
      tag is legitimately alpha, so this gate exists precisely because the walk is blind to it.)*

      **`release-verify` above asserts this too** — the manual `jq` is kept as the by-hand fallback and
      as the explanation of *what* is being asserted. The blindness itself is now rehearsed offline
      (#1664, `tools/release/test_release_rehearsal.py`): a real tagged checkout must label itself
      bare, an untagged one must say alpha, and the signer workflow must still tag its own checkout.
      **"The §5.1 walk was green" is not evidence that a release will label itself correctly.**
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
- [ ] **OTA feed (#1524 / #1284 AC5): `just ota-feed vX.Y.Z --write`** → review the diff
      (`docs/ota/feed.txt` now points every board class at this release's signed assets) → commit.
      The feed is the Pages-served pointer fielded boards poll — **this commit, not the release,
      is what makes the fleet see the update**. It refuses to emit if any board's `.bin`/`.sig`
      is missing (fail-closed); later hand-edits (curation, #1258) are checked by ota-feed-guard.
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
