# Time display convention — local-first, UTC secondary (#328)

Bench work is tied to **local** time. Watering, skylight position, thermal context, and
physical interventions all happen on Veronica's clock (Chicago, currently CDT / UTC-05:00).
UTC remains the join key for machine correlation, but a human reading a chart axis, a lab
note, or a monitor row should see **local time first**.

## The rule

Every bench-facing surface renders timestamps **local-first, with UTC as secondary
metadata**:

```text
2026-06-28 13:14 CDT · UTC 18:14Z
```

- **Local first**, with an explicit zone label so a reading is never ambiguous.
- **UTC secondary** — always present for reproducibility; the UTC *date* is shown only when
  it differs from the local date (a midnight crossing), to keep the label terse.
- Intervention markers and chart hover text default to local time.

## One formatter

All surfaces call **`tools/analytics/timefmt.local_first(utc_dt, tz_name=…, tz_offset_hours=…)`**
— one implementation so the convention stays consistent across the dashboard, monitor,
lab notebook, and chart labels. The stored data is unchanged: rows keep both
`timestamp_utc` and `timestamp_local` (see [`TELEMETRY_SCHEMA.md`](TELEMETRY_SCHEMA.md));
this is a *display* convention, not a schema change.

## Honest zone labels

The zone label is only ever a **true** label, never a guess:

| What the location config provides | Zone label rendered |
|---|---|
| `tz_name` (IANA, e.g. `America/Chicago`) | the real DST-correct abbreviation — `CDT` / `CST` (via stdlib `zoneinfo`) |
| only `tz_offset_hours` (today's config) | the numeric offset — `UTC-05:00` |
| neither | `UTC` |

To show the abbreviation (`CDT`) the location config needs a **`tz_name`** field; today it
carries only `tz_offset_hours` (#365), so surfaces show the offset until that lands. A bare
offset cannot determine `CDT` vs `CST`, so we render the offset rather than fabricate an
abbreviation — consistent with the project's honest-data posture.
