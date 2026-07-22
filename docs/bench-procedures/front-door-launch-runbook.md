# Runbook — v0.8.1 front-door launch session (#1069)

**For:** the maintainer, at the bench session. **Prepared by:** DX.
**Covers:** #1232 (search console) · #1076 (maker build posts) · #1508 (profile README) · #1069
(epic closeout). **Milestone:** v0.8.1.

This is the sit-down runbook for the front-door launch surfaces — the account actions and public
posts that only you can do. Every desk-side dependency below is already built and merged; this sheet
is the order to work them in, what each needs in hand, and where the public pointer goes after.

## Before you sit down — prerequisites

- **Logins in hand:** the Google account (same one as vkhogue.com), Bing Webmaster, Hackaday.io,
  Hackster.io. GitHub is already you.
- **A board + a build to photograph**, if a maker log wants a fresh in-progress shot. The post
  drafts stand on their own narrative, but a build session is the natural time to grab any missing
  bench photo.
- **Brand assets** (avatar + header) are already live on the maker profiles (#1066) — nothing to
  re-upload.

### The four standing rules (they gate every step below)

1. **Promotion gate is separate.** *Building and posting* these surfaces is allowed now. *Driving
   an audience to them* (the "Follow the build" README row, teaser/motion FD-7 #1077) waits until
   the character/voice ships in the app. So: post the build logs, don't launch a campaign.
2. **Pointer-only public trail.** The platform copy is canonical. After you post, only the live URL
   goes on the tracking issue + the crosslink checklist — never the prose (no dupe-content, no
   deflated publication moment).
3. **Nothing internal in a public paste.** Issue numbers, local paths, device ids, MACs never reach
   a maker-site body. (DX leakage-scanned the current post drafts — clean — but re-verify anything
   you edit.)
4. **Your hand only, rules re-verified live.** Nothing external posts without you, and platform
   posting mechanics get a quick live re-check at each tick (the #1202 ground rule).

## The sequence

Work them in this order — #1232 first because it starts the recrawl clock the voice pass
(#1496 / #1499) is timed against; the maker posts and profile are independent and can follow.

### 1 · #1232 — Search console, both engines

Full step-by-step is in the companion sheet:
[`search-deployment-run-sheet.md`](search-deployment-run-sheet.md). In brief:

- [ ] **GSC:** generate the verification token → it goes in the `<head>` of `docs/index.html`
      (the FD-3 TODO marks the exact spot; DX can land the one-line commit once you have the token,
      or you paste it — no placeholder is committed until it's the real one).
- [ ] **GSC:** add the URL-prefix property `https://orangepeachpink.github.io/sprout/`, verify,
      submit `sitemap.xml`, URL-inspect → Request Indexing (this also flushes the stale "Honest"
      SERP cache).
- [ ] **Bing:** Import from GSC (carries verification + sitemap), submit the sitemap, submit the URL.
- **Remember:** only the Pages URL can be a console property — the two `github.com` URLs are
  structurally ineligible (see the run sheet's URL matrix). Their optimization is content, tracked
  under the voice pass (#1496), not here.
- **Done when:** both engines show the Sprout property with the sitemap accepted and indexing
  requested. Log the outcome on #1232; it closes when both engines are serving.

### 2 · #1076 — Maker build posts (Hackaday.io + Hackster.io)

The build-log drafts are written and reviewed-ready in your private drafting area (external-posts
convention — the repo holds pointers, not the prose). The maker-site voice is deliberately the
**maker's own first-person register**, distinct from Sprout's plant-character voice, which lives
only on Sprout's own surfaces (epic locked-decision 8). Per venue:

- [ ] **Hackaday.io** — post the project logs (native chronological logs; paste as rich text in the
      WYSIWYG editor). Grab any missing in-progress build photo while the board is out.
- [ ] **Hackster.io** — post the project writeup; slot Things-Used / Code / Schematics into
      Hackster's own fields rather than the story body (it's structured differently from Hackaday).
- [ ] After each post: **freeze the as-posted copy** beside the draft with a header block
      (`published_url` · `published_date` · `venue` · one-line delta-vs-draft) — the snapshot is the
      record.
- [ ] **Pointer trail:** the live URLs go on **#1076** and
      [`../community/crosslink-checklist.md`](../community/crosslink-checklist.md) — URLs only.
- **Done when:** both maker profiles carry real build-log content, as-posted snapshots are frozen,
  and the live URLs are on #1076 + the checklist. (The "Follow the build" README row stays HELD for
  0.9.x per the promotion gate — do not add it now.)

### 3 · #1508 — Maker-profile README voice pass (`OrangePeachPink/OrangePeachPink`)

- **Cross-repo + personal surface** — no agent edits it autonomously; Design drafts proposed copy
  **on issue #1508** for your review, you apply it (or direct the Portfolio agent to).
- **Sequences after** the Pages re-voice (#1499) lands, so the profile matches the same voice line.
- [ ] Confirm Design has posted draft copy on #1508; review it; apply on the profile repo.
- [ ] Cross-link the profile with the Person-entity work (the `@id` mirror from #1232 / #1496).
- **Done when:** the profile README is on the shared voice line and cross-linked. Bench-readiness
  note: this one is only actionable once Design's draft is on the issue — if it isn't yet, it waits
  on that, not on you.

### 4 · #1069 — Front-door epic closeout

- 6 of 8 slices are already closed (FD-0…FD-5). The v0.8.1-remaining slices are **#1076 and #1232
  above**; **FD-7** (#1077, teaser/motion) is v0.9.0 and gated on the promotion gate — out of scope
  for this session.
- **Done when:** #1076 and #1232 close. The epic then has met its v0.8.1 obligations; it stays open
  only to carry FD-7 into v0.9.0 (note that on the epic so it isn't mistaken for stalled).

## One flag for the voice pass (not a blocker)

The maker-post drafts describe their register as maker-to-maker candid technical writing
("technical + honest"). <!-- voice-guard: allow -->
That is the *maker's* own voice, not the retired Sprout "honesty" brand hook <!-- voice-guard: allow -->
— two different things, and the split is intentional (the voice pivot ends at Sprout's edges).
Worth a glance during the #1496 / #1499 pass to confirm that's the line you want, but it does not
gate posting.
