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
| `just collection status` | List every live **logical** collector — grouped by launch tree (#811), **role + tree pids** (monitor / fleet / capture). Same view as `just processes`. |
| `just collection start` | Start all collection — parity with the dashboard's **▶ Start all collection** (ADR-0014). Needs a running server (`just start` first). |
| `just collection stop` | Stop **every** live collector — graceful first, hard-kill any that don't exit. No dashboard needed. |
| `just stop-collection` | Shortcut for `just collection stop`. |

Useful flags on `stop`: `--dry-run` (show what *would* stop, kill nothing), `--role monitor|fleet`
(scope to one path), `--grace <seconds>` (how long to wait before the hard-kill).

## One collector, two PIDs — the launch tree (#811)

Every collector runs as a **2-process launch tree**: a parent launcher and its worker child, and
on the OS process table *both* carry the script name in their command line (the Python-launcher
double-process). So one logical **fleet** appears as **two `python.exe` rows** — parent →
child, e.g. `39692 → 24608`.

`just collection status` and `just processes` **group by launch tree** and report the *logical*
collector — `fleet  pids 39692->24608`, **not** two `fleet` rows. Read the two PIDs as one
collector, not a duplicate: that miscount is exactly what produced #691's false "4 zombie
collectors" finding (and burned a live reclaim). The server's `/collection/status` is the
independent cross-check and agrees by construction.

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

## Fleet addressing — name, not IP (#676)

The WiFi fleet is reached **by name**, not by a hardcoded IP. Each board advertises an mDNS
hostname `sprout-<device_id>.local` (the `device_id` nonce, ADR-0020 §2 / #760), stable across
DHCP churn. The dashboard server (`serve.py`) tries that hostname **first** and the registry's
configured `base_url` IP only as a fallback, and **self-heals** the registry (`config/devices.local.json`)
when a board answers at a fresh IP — so a board that power-cycles onto a new DHCP lease stays
reachable with **no registry hand-edit** (the install-day subnet-scan friction is gone).

Low-tech complement: if your network has no working mDNS responder, set a **DHCP reservation**
per board on the router (pin each `device_id`'s MAC to a fixed IP) and keep the `base_url` IPs in
`config/devices.local.json`. mDNS and reservations are independent — either alone suffices.

## What DX owns vs Data owns

DX owns this headless **stop/reclaim** surface + the `just` recipes; **Data** owns the
data/session-handling side (the collector's session tolerance, #712) and the `start_all` control
policy the dashboard button and `just collection start` both post to (`collection_control`,
ADR-0014). See #689 for the lane split.
