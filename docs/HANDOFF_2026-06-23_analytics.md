# Plants — Night Handoff & Analytics Roadmap

**Written:** 2026-06-23 late evening (Chicago, CDT) · **For:** morning of 2026-06-24
**Author:** Claude (Opus 4.8), analytics / data / dashboards thread
**Companion:** [`HANDOFF_2026-06-23.md`](HANDOFF_2026-06-23.md) (firmware / tooling thread)

> Good morning. The analytics toolchain shipped today and is pushed. This is the data-side roadmap —
> what to improve, harden, and build next — plus how today's all-day 4-probe capture (with the
> ~13:00–14:00 skylight shaft) is the dataset that finally turns the forecasts on.

---

## Status at a glance

- [x] Analytics work shipped and **pushed** to `main` (E6 → E7 → E1 → E3 → single-plant view)
- [x] Every panel verified against the live v0.7.0 CSV; every forecast is **gated** (no fake ETAs)
- [x] Sprout **design v2** (brand world + expanded source) landed by the core/design team (`a882334`),
      **additive** — v1 stays the dashboard source of truth; tokens are byte-identical, so the dashboard
      needs no change
- [x] Backlog + the firmware team's work reviewed (§3)
- [x] Temp / scratch cleaned; nothing of mine left dirty (§6)
- [>] **Today: 4 co-located probes capture a full day, incl. the ~13:00–14:00 skylight transient**
- [ ] Next data moves: **tests (robustness)** → channel isolation + event annotation → A2 boundary editor

---

## 1. What shipped (my lane)

The host-side analytics toolchain now lives in [`tools/analytics/`](../tools/analytics/) (see its
[`README.md`](../tools/analytics/README.md)):

| Commit | Backlog | What |
| --- | --- | --- |
| `81ac98e` | E6 | `parse_v1.py` — schema-v1 reader (multi-segment, gzip archive, schema-version tolerant) |
| `0c08660` | E7 | `dashboard.py` + template — self-contained, offline, Sprout-styled 4-channel dashboard |
| `6c58ae9` | E1 | `serve.py` — live `/data.json` + in-page Refresh / Auto |
| `a7d12af` | E3 | `forecast.py` — per-probe drying rate, time-to-band / time-to-thirsty, diurnal, next-day |
| `cd8b72e` | E3 | single-plant detail view — drill-in: gauge, trend chart, forecast cards, rate table, stats |

Two principles held end-to-end: **raw + band are the truth** (the legacy moist% `value` is never
plotted — B2/C2), and **forecasts are statistically gated** — they show *"no estimate yet"* with the
reason until drying is real, instead of inventing a number.

---

## 2. Today's capture — the analytics view

Coordinated with the firmware handoff §2: **do not reset the board** (no COM6 monitor / reflash /
logger restart — that severs the day, B5). To watch live without touching the capture:

```text
python tools/analytics/serve.py     # http://127.0.0.1:8765 — read-only, re-parses logs/ on Refresh
```

**Why today matters for the data side — it unblocks the gated work:**

- **First drying signal.** A warm south-window afternoon should finally produce a real drying *angle*.
  The moment the 6 h slope clears the noise floor (>2·se and ≥4 c/h), the forecast cards flip from
  "no estimate yet" to live ETAs + ranges — visible immediately in the single-plant view via Auto.
- **The skylight transient on 4 probes at once** (~13:00–14:00) is the cleanest possible read on
  **cross-probe agreement** (C1) — four probes, identical soil, one light/heat step. It also gives a
  **known-time light event** to annotate (the dashboard deliberately omits day/night shading for lack
  of a light schedule — this is the first concrete schedule input).
- **First (partial) diurnal day.** Diurnal/next-day stay gated until ≥2 days, but today is day one and
  the skylight event can be analysed as a sub-day transient without waiting.

---

## 3. Analytics roadmap — improve · harden · build · complete

Ordering principle: **make the instrument trustworthy, then make the forecasts real as data arrives.**
Single list, priority-tagged; cross-team seams follow.

1. **[P0 · robustness] Automated tests for the analytics modules.** Today there are **zero** — the
   firmware team has 27 passing FSM checks; my Python has none. Add `pytest` over `parse_v1`
   (multi-segment, gzip, schema-version bump, payload explode, partial sweeps), `forecast` (gating
   logic, ETA math + sign convention, divide-by-near-zero, single-band history, sparse data), and a
   `dashboard` / `forecast_payload` smoke test against `docs/sample_log.csv`. The #1 robustness debt —
   host-side, no reflash, safe to do during today's capture.
2. **[P1 · feature] Channel isolation on the overview** — legend / checkboxes to view 1, 2, or 3 probes
   at a time. The "see one at a time" ask; cheap, and useful the moment the skylight splits the four.
3. **[P1 · feature] Event annotation** — mark a known-time window (today's 13:00–14:00 skylight) on the
   trajectory and detail charts. Foundation for day/night shading (C5) once a light schedule exists.
4. **[P1 · design] Reconcile the v2 per-channel line-color guidance.** The v2 system source prescribes
   CH1 `--leaf`, CH2 `--st-watering`, CH3 `--st-dry` — but those are *band-palette* colors that collide
   with the band shading behind the trajectory lines (why I chose distinct blues/purples). Decide:
   adopt the v2 colors (and drop/relocate band shading on that chart) or keep the distinct series
   colors. Tokens are otherwise unchanged, so no other dashboard change is implied by v2.
5. **[P2 · analysis] Skylight + single-day analysis.** After the event, quantify the 4-probe response:
   do they move together (coherent light/thermal excursion) or diverge (per-probe ADC noise)? First
   real cross-probe coherence number for C1; first diurnal-shape read.
6. **[P2 · feature] A2 boundary editor (the E1 high-value piece).** Drag the 7 band boundaries on a
   chart of real readings and emit the values to paste into firmware. The tool that makes the firmware
   team's **P0 (A2 reconciliation)** tractable — set the dry-edge and wet-floor visually against the
   actual dry-down. Directly unblocks their top priority.
7. **[P3] E2 per-cycle feature table** — one row per watering cycle (dry-down rate, time-to-needs-water,
   field-capacity reading, post-water recovery, ambient means). The substrate E2/E3 lean on; needs
   cycle boundaries (dry-down → rewet), which arrive with a real dry-down and pump events (D1).
8. **[P3] E3 predicted-vs-actual loop** — once pump logging (D1, firmware lane) exists, track forecast
   error and let it refine the per-plant model. Turns the engine from a one-shot estimate into a learner.
9. **[P3] E5 parquet / DuckDB tier** — defer until multi-day volume justifies it; CSV re-parse is
   sub-second for a day. Worth it for fast multi-day / cross-project (the sibling air-quality project) queries.

### Cross-team seams to keep aligned

- **A2 thirsty threshold ↔ firmware's actual watering trigger.** My time-to-thirsty uses the A2
  needs-water edge as a proxy; when the supervisor defines the real trigger, the forecast must match it.
- **`value=pct` column (B2/C2).** Producer-side fix is the firmware team's (they lean toward emitting a
  band index). My consumer side already ignores it — no change needed on my end once they decide.
- **C5 calendar/derived fields** (day/night/season) — my lane, derive-at-analysis; folds into the event
  annotation + diurnal work above.

---

## 4. What I'd do first tomorrow

1. Let today's capture run clean (watch via `serve.py` + Auto — read-only).
2. **Write the tests** (#1) — pure host-side, doesn't touch the live capture; the robustness debt that
   should not grow.
3. Add **channel isolation + event annotation** (#2/#3) — cheap, host-side, makes the skylight legible.
4. After ~13:00–14:00, analyse the **skylight transient** across the four probes.
5. When a real dry-down begins (after the firmware team reconciles A2 and wires pumps), the forecast
   cards light up on their own — verify they read sensibly and start the **A2 boundary editor**.

None of (2)–(4) require a reflash, so all are safe to do *during* today's capture.

## 5. Open decisions for you (analytics)

1. **Build order:** tests-first (my lean — one focused session pays down the robustness gap) vs.
   features-first (channel isolation + event annotation give immediate value on today's data).
2. **A2 boundary editor:** want me to build it as *the* tool to do the A2 reconciliation visually? It
   directly serves the firmware team's P0 and is the highest-leverage new feature I see.
3. **v2 per-channel colors (#4):** adopt the design system's prescribed series colors, or keep the
   distinct ones that don't collide with band shading? My lean: keep distinct, and instead apply the
   `--leaf`/`--st-watering`/`--st-dry` accents in contexts without band shading (cards, sparklines).

## 6. Housekeeping (done tonight)

- All analytics work in **atomic, one-per-backlog-item commits** with the standard trailer, pushed.
- **Design v2:** confirmed the core team's additive delivery (`a882334`) is correctly landed. I had
  begun ingesting the same bundle before noticing their commit; I **reverted** an accidental overwrite
  of v1's `sprout-design-system.dc.html` and removed a redundant `brand/` copy. `docs/design/` is clean
  (v1 untouched + their tracked `sprout-v2/`); I did **not** touch `sprout-v2/`.
- **Removed (mine, regenerable):** `.claude/launch.json` (preview config), `reports/` (dashboard output —
  rebuild with `python tools/analytics/dashboard.py`), `tools/analytics/__pycache__`, and the
  `dev/_scratch` zip extract.
- **Did NOT touch / leave running:** the live logger (PID 45828, COM6) and the firmware thread's files.
  Killing the logger or opening COM6 resets the capture — see firmware handoff §2.1.
