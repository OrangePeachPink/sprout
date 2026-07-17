# GitHub Discussions — categories & welcome (voiced copy)

Phase 3 (Design lane). Voiced copy for the Discussions tab the Workflow lane enables (ADR-0003 §3). The
Workflow lane owns the *structure* (which categories, their formats); this file supplies the **descriptions
and the welcome post**. Category descriptions are clear and lightly warm — not Sprout's first-person voice
(internal/contributor-facing). The **welcome announcement** is the one place that speaks as Sprout, because
it's a public greeting.

> Apply: **Settings → General → Features → Discussions** (maintainer toggle), then seed these categories and
> pin the welcome post.

## Categories

| Category | Format | Description (paste into the category) |
| --- | --- | --- |
| **📣 Announcements** | Announcement | Releases, direction, and news. Maintainers post; everyone's welcome to chime in. |
| **🌱 Ideas** | Open-ended | The inbox for not-yet-actionable ideas, goals, and "should we…?" When one's ready to build, it becomes an issue. |
| **❓ Q&A** | Question / Answer | Stuck on setup, calibration, or the code? Ask here — answered questions help the next person too. |
| **🪴 Show &amp; tell** | Open-ended | Built your own Sprout, or wired it your own way? Show it off — we'd love to see your windowsill. |

*(Emoji are used only as small category wayfinding glyphs here — not in product copy, per the voice rules.)*

## Welcome post (pin in Announcements)

**Title:** Welcome — I'm Sprout 🌱

> Hi, I'm Sprout. I keep a windowsill of plants properly watered, and I speak for them, in plain words.
>
> This is where the project talks things through:
>
> - **🌱 Ideas** — toss in a thought or a "what if." No idea's too small; the good ones grow into issues.
> - **❓ Q&A** — getting set up, calibrating a probe, reading the bands? Ask away.
> - **🪴 Show &amp; tell** — built your own? Share it. I like meeting other plants.
> - **📣 Announcements** — I'll post releases and news here.
>
> A couple of house values, so you know how I work: **I read from the raw value and the calibrated band** (I
> won't invent a percentage), and I'd always rather surface a gap than smooth it over. Same goes for how we
> talk here — kind, honest, plain.
>
> Make yourself at home. **Tend well.**

## Notes for the Workflow lane

- "Create issue from discussion" is the path from an **Idea** to tracked work (ADR-0003 §3); the discussion
  stays as the rationale trail.
- If a **Q&A** answer turns out to be a doc gap, it's a `type:docs` issue — link it back.
- Keep category descriptions to one or two plain lines; the warmth is in the welcome post, not every label.
