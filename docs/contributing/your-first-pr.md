# Your first contribution to Sprout

Welcome — genuinely glad you're here. This is the *friendly* walkthrough: it carries you from "I'd like to help"
to a merged pull request, one calm step at a time, explaining the *why* as it goes. (The terse command reference
lives in the [README](../../README.md) and [`CONTRIBUTING.md`](../../.github/CONTRIBUTING.md); this is the
narrated version for a first-timer.)

However you arrive — fixing a typo, wiring up a sensor, or just curious — there's a place for you. Let's go.

## Who this is for

Anyone making their first change here, whether or not you've opened a pull request before. If you've never used
`uv` or `just`, that's fine — we'll install them and say what they do. If a word is new, it's explained the first
time it appears.

## Step 0 — Three small installs (about five minutes)

You need three tools. Each does one job:

- **Git** — version control; how code travels. If `git --version` prints a number, you already have it.
- **uv** — a fast Python environment manager (from Astral). It reads the project's lockfile and gives you the
  *exact* Python and packages every other contributor has — no "works on my machine." See the
  [uv docs](https://docs.astral.sh/uv/) to install.
- **just** — a tiny command runner. Instead of memorizing long commands, you run short recipes like
  `just check`. Install with `winget install Casey.Just` (Windows), `brew install just` (macOS), or see the
  [just docs](https://just.systems).

> **The zero-install path:** the repo ships a devcontainer, so you can open it in **GitHub Codespaces** and skip
> Step 0 entirely — the environment builds itself in the browser.

## Step 1 — Get Sprout running

```text
git clone https://github.com/OrangePeachPink/plants && cd plants
uv sync                     # reproduce the exact, locked dev environment
uv run pre-commit install   # the quality checks auto-run on every commit
just start                  # launch Sprout — opens the dashboard in your browser
```

`uv sync` builds a local environment with the right Python and tools. `pre-commit install` wires up the hooks
that auto-format and lint your work *as you commit*, so you never have to remember to. `just start` opens the
dashboard — if a browser tab appears, you're running Sprout. 🌱

## Step 2 — Find something to work on

- A question or a loose idea? → **[Discussions](https://github.com/OrangePeachPink/plants/discussions)**, the
  idea inbox. No setup question is too small.
- A concrete, shippable piece of work? → an **Issue**. Browse the
  [Sprout board](https://github.com/users/OrangePeachPink/projects/2) and look for the **`good first issue`**
  label — those are chosen to be a welcoming start.

When you pick one up, a maintainer can assign it to you and move its card to *In Progress*.

## Step 3 — Make your change

1. **Branch** from `main`, named `type/short-desc` — e.g. `fix/banner-spacing` or `docs/typo`. (Outside
   collaborator? Fork first, then branch.)
2. Keep the change small and focused — one reviewable idea per branch.
3. **Run the checks before you push:**

   ```text
   just check        # the full gate: pre-commit (lint + format + hygiene) + tests — exactly what CI runs
   ```

   `just check` is the *same* thing CI runs, so green locally means you're in good shape. If a hook reformats a
   file, that's normal — it fixed it for you; just `git add` and commit again.

> **Honest note:** `just check` also runs the native C firmware tests, which need a C compiler (`gcc`) on your
> PATH. If you're only touching docs or Python, you can run the lighter pieces directly (`just lint`,
> `just test-host`) and let the rest ride.

## Step 4 — Commit, the Sprout way

We use [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject`, where `type` is one
of `feat | fix | docs | refactor | chore`. State the *result* when that's the point. One example:

```text
git commit -m "docs: fix the broken link in the wiring guide"
```

## Step 5 — Open the pull request

Push your branch and open a PR. Fill in the template — a one-line Summary, the linked issue, and how you verified
it.

**Link the issue with `Refs #N` or `Part of #N` — not `Closes #N`.** That's deliberate (see the next step). Then
say how you checked your change; that evidence is what a reviewer looks at.

PRs are **squash-merged** — your branch becomes one clean commit, and it auto-deletes after merge. Tidy.

## Step 6 — The verification gate (why your issue stays open)

Here's the one thing that surprises newcomers: **merging your PR does not close its issue.** That's on purpose.
After merge, the implementer posts evidence on the issue and moves it to *Needs Verification*; then a **reviewer**
checks the change against what the issue actually asked for and — as a separate, deliberate step — closes it. The
human confirmation *is* the gate, which is why PRs say `Refs #N`, not `Closes #N`.

It isn't bureaucracy — it's how Sprout stays honest about what's *really* done versus merely merged.

## A note on the green check

You may notice the CI badge isn't green yet — that's a known, temporary billing pause on Actions, not anything
about your change. Your local `just check` is the real signal today; the badge lights up on the first PR after
the reset. Don't chase it.

## That's it

You've gone from "I'd like to help" to a reviewed, merged change. However you arrived, you found a place. Thank
you for tending Sprout. 🌱

*New to the mechanics behind any of this — `uv`, `pre-commit`, the gate? The [README](../../README.md) and
[`CONTRIBUTING.md`](../../.github/CONTRIBUTING.md) are the reference; this guide is the warm path through them.*
