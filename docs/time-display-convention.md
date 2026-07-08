# Time display convention — local-first (#328, #840)

Bench work is tied to **local** time. Watering, skylight position, thermal context, and
physical interventions all happen on Veronica's clock (Chicago, currently CDT / UTC-05:00).
UTC remains the join key for machine correlation *in the data*, but a human reading a chart
axis, a lab note, or a monitor row should see **clean local time** — UTC is not a human
clock (#720).

## The rule

Every bench-facing surface renders timestamps **local-first**. On the human header/date/axis
fields the UTC secondary is **dropped** (#840) so the label reads as one's own clock:

```text
2026-06-28 13:14:30 CDT          ← header, "data as of", "Nh since", chart axis (#840)
2026-06-28 13:14 CDT · UTC 18:14Z ← the `utc_secondary=True` form, for machine/audit surfaces
```

- **Local first**, with an explicit zone label so a reading is never ambiguous.
- **No UTC clutter on the glance surfaces** — `local_first(..., utc_secondary=False)` (the
  default stays `True` for any surface that still wants the UTC tail). The UTC *date* in the
  tail is shown only on a midnight crossing, to keep it terse.
- Intervention markers and chart hover text default to local time.
- Reproducibility is preserved by the **data**, not the label: every row keeps both
  `timestamp_utc` and `timestamp_local`.

## One formatter

All surfaces call the **`tools/analytics/timefmt`** formatters — one implementation so the
convention stays consistent across the dashboard, monitor, lab notebook, and chart labels:

- `local_first(utc_dt, tz_name=…, tz_offset_hours=…, utc_secondary=…)` — local from a
  reading's own offset (portable across viewers).
- `local_first_system(utc_dt, utc_secondary=…)` — local in the **host's** zone, for
  rig-viewed surfaces (the live dashboard); this is what the header/date/axis fields use so
  they show the crisp abbreviation. The stored data is unchanged (see
  [`TELEMETRY_SCHEMA.md`](TELEMETRY_SCHEMA.md)); this is a *display* convention.

## Honest zone labels

The zone label is only ever a **true** label, never a guess:

| Source | Zone label rendered |
|---|---|
| `tz_name` (IANA, e.g. `America/Chicago`) | the real DST-correct abbreviation — `CDT` / `CST` (via stdlib `zoneinfo`) |
| the **host** OS zone (rig-viewed surfaces) | the OS abbreviation, or a verbose OS name abbreviated to initials — `Central Daylight Time` → `CDT` (#840) |
| only a numeric `tz_offset_hours` | the offset — `UTC-05:00` |
| neither | `UTC` |

A bare offset cannot determine `CDT` vs `CST`, so we render the offset rather than fabricate
an abbreviation — consistent with the project's honest-data posture. On the rig host the
verbose OS name (`Central Daylight Time`) is abbreviated by its initials, which *is* the true
label; anything non-standard falls back to the offset.
