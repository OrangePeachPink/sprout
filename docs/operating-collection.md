# Operating collection — start, stop, and reclaim without the dashboard

Sprout collects in the background: a **monitor** logger (the serial/USB path) and a **fleet** logger
(the untethered Wi-Fi pollers). Normally you drive them from the dashboard's one button — **▶ Start
all collection** — and stop them by closing the served app. This page is the **headless** path: the
same lifecycle from the terminal, for when there's no browser tab open, a collector orphaned, or
you're scripting.

> **Audience:** operator / maintainer running a live Sprout. Not needed to *contribute* code — see
> [CONTRIBUTING](../.github/CONTRIBUTING.md) for that.

## The three commands

| Command | Does |
| --- | --- |
| `just collection status` | List every live collector by **pid + role** (monitor / fleet / capture). Same view as `just processes`. |
| `just collection start` | Start all collection — parity with the dashboard's **▶ Start all collection** (ADR-0014). Needs a running server (`just start` first). |
| `just collection stop` | Stop **every** live collector — graceful first, hard-kill any that don't exit. No dashboard needed. |
| `just stop-collection` | Shortcut for `just collection stop`. |

Useful flags on `stop`: `--dry-run` (show what *would* stop, kill nothing), `--role monitor|fleet`
(scope to one path), `--grace <seconds>` (how long to wait before the hard-kill).

## Why this exists — the orphan problem

Since v0.7.0 runs 24/7, a collector can outlive its trigger: close the browser tab (or a session
crashes) and the logger keeps running with **nothing visible in Task Manager** to identify it as
Sprout's — and it holds the COM port or the fleet lock. Before this, a **reboot was the only
recourse** (see the #691 resilience log; the identifiability half is #493). `just stop-collection`
is that recourse, headless.

## Is it safe to stop mid-write?

**Yes.** The loggers **flush every CSV row** (`plants_logger.RotatingCsv.write` →
`writer.writerow` + `fh.flush`), so each session file is always complete **up to its last row**.
`stop` sends a **graceful** stop first (which lets the logger finish and exit cleanly), and only
**hard-kills** a process that ignores it — and even a hard-kill loses at most the sub-millisecond
in-flight row, never a truncated one. The next start's archive step catches up any unbacked-up
segment.

## Manual fallback

If a process refuses to stop, `just stop-collection` reports its pid and the exact manual command:

```powershell
powershell -Command "Stop-Process -Id <pid> -Force"
```

## What DX owns vs Data owns

DX owns this headless **stop/reclaim** surface + the `just` recipes; **Data** owns the
data/session-handling side (the collector's session tolerance, #712) and the `start_all` control
policy the dashboard button and `just collection start` both post to (`collection_control`,
ADR-0014). See #689 for the lane split.
