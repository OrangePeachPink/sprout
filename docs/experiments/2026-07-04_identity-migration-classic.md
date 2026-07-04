# Identity migration record — the classic's legacy epochs → its minted id (#620)

**Date:** 2026-07-04 · **ADR:** [0027 §9](../adr/0027-identity-model.md) · **Refs:** #601 (mint), #604 (the
`previous_ids`/`canonical_for` mechanism this uses), #632 (the mint landed).

This is the 2nd-epoch legacy migration: a one-time, **non-destructive** mapping of the classic board's
three historical `device_id` identities onto its now-minted stable id. Per ADR-0027 §8/§9 the **raw wire
records are never rewritten** — they truthfully say what the board reported at the time. This record + the
`previous_ids` successor list are the mapping; the coalesce happens at display time (#604).

## The map

The classic board's minted stable id (live-verified on COM6, #632): **`y9d41p`**.

| Legacy `device_id` | Epoch | Where it lives | → canonical |
|---|---|---|---|
| `plants_esp32_f4e9d4` | 2026-06-23 → 06-26 | committed archive (`.data-worktree`, 10 segments) + local `logs/` | `y9d41p` |
| `Sprout ESP32` | 2026-06-28 → 06-29 | local `logs/` (not archived) | `y9d41p` |
| `classic` | 2026-07-03 → 07-04 (pre-mint) | local `logs/` | `y9d41p` |

Registry successor list (the classic's entry in the gitignored `config/devices.local.json`):

```json
"previous_ids": ["plants_esp32_f4e9d4", "Sprout ESP32", "classic"]
```

Firmware already seated `["classic"]` at the mint (#632); this adds the two earlier epochs.

## The deliberate call on `Sprout ESP32` — evidence, not a blind coalesce

Firmware correctly flagged that `Sprout ESP32` is the **shared default** every ESP32-family board derived
(the exact collision #601 exists to kill) — so mapping it blindly could misattribute another board's history
to the classic. That risk was checked against the records, and it does **not** apply here:

1. **No other board was alive during the `Sprout ESP32` epoch.** The S3 (`s3-n8r2-01`) first came up
   2026-07-02 evening; the C5 later still (`docs/evidence/2026-07-03-esp32-s3-bringup-wifi/`). Every
   `Sprout ESP32` record predates them — only the classic existed 06-28 → 06-29.
2. **The committed archive contains no ambiguous segment.** `git ls-tree origin/data` holds only
   `plants_esp32_f4e9d4_2026062{3..6}` segments — zero `Sprout ESP32` segments, and **none dated on/after
   the 07-02 S3/C5 bring-up.** The `Sprout ESP32` rows exist only in the maintainer's local `logs/`, all
   dated in the classic-only window (the 06-28 bench log names `Sprout ESP32_20260628_*.csv` on the same
   board that logged `plants_esp32_f4e9d4_20260628_183018.csv` earlier that day — one board, a mid-day
   reflash that changed the default naming).
3. **The ambiguity is closed going forward.** Post-#601 no board ever emits `device_id="Sprout ESP32"` —
   the friendly default now rides `name=` and `device_id` is the minted nonce (or empty pre-mint, which
   `canonical_for` leaves unmapped). So the only rows a `Sprout ESP32` alias can ever match are the
   historical classic-era ones.

**Conclusion:** all three legacy identities map to `y9d41p` safely. The #604 guards remain permanent
invariants — a live id is never swallowed (`canonical_for("y9d41p") → "y9d41p"`), raw records are never
rewritten, and the coalesce is visible on the card (`history coalesced from: …`).

## The one thing only the maintainer can confirm (local logs)

The committed archive proves no post-06-29 `Sprout ESP32` segment exists, but the maintainer's **local**
`logs/` are theirs to eyeball: if any stray `Sprout ESP32_2026070[2-3]_*.csv` exists (an S3/C5 first-boot
row emitted before it was named `s3-1`/`c5off1`), those specific rows are *not* the classic's and should be
excluded. Firmware's rollup says the S3/C5 were named at bring-up (`s3-n8r2-01`/`s3-1`, `c5off1`), so none is
expected — but the check is a one-line `ls logs/ | grep -i sprout` before applying the map.

## What this migration does NOT do

- **No raw record is rewritten** (§8/§9) — the archived `plants_esp32_f4e9d4` segments stay byte-for-byte.
- **The #604 runtime coalescing does not "retire"** as a deletion — under ADR-0027 §9 it *is* the permanent
  mapping mechanism now (the `previous_ids` successor list); there was no separate machinery to remove.
- **The S3/C5** stay on their named ids until their post-merge reflash mints their own nonces (Firmware).
