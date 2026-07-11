# Security Policy

Sprout is a small, local-first hobby/portfolio project — a soil-moisture logger
and (eventually) a small-pump waterer. It runs on your own hardware and network;
there's no hosted service. Still, if you find a vulnerability, we'd like to know.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** Instead, report it
privately:

- Preferred: open a **private vulnerability report** via GitHub
  (the repository's **Security → Report a vulnerability** tab), or
- contact the maintainer at
  [@OrangePeachPink](https://github.com/OrangePeachPink) with a private message.

Please include what you found, how to reproduce it, and the potential impact.
We'll acknowledge your report, investigate, and keep you posted on a fix.

## Scope

Most security-relevant surface is small and local: the host logger / dashboard
binds to `127.0.0.1` (localhost only), and the firmware has no network services
enabled by default. Secrets (e.g. any WiFi credentials) are kept out of git
(`.gitignore`). Reports about credential handling, the localhost control
endpoints, or dependency vulnerabilities are all welcome.

## Hardware & physical safety

Sprout will eventually switch water near electronics, so a few safety expectations
are part of the design — not afterthoughts:

- **Low-voltage DC only — never mains.** The pumps are small DC units (~2.5–6 V),
  and the relays in this build switch only that low-voltage pump power. Do not wire
  mains voltage through this project.
- **Water near electronics.** Keep the ESP32, relay board, and wiring above and away
  from the reservoir; use drip loops; only the rated submersible pump goes in water.
- **Fail-safe actuation.** Pumps default **off** at boot, on reset, and on watchdog
  timeout — a power loss or hung controller returns to "no water flowing," never
  "pump stuck on" (see #93, #181).
- **Watering is operator-gated, not autonomous.** Manual operator commands (`!water` / `!stop`)
  are wired through the actuation supervisor but the relay path is **bench-unverified** (#191).
  No autonomous dosing runs until per-probe calibration and the safety bench pass
  (#94 / #191 / #93).
- **Not a safety-certified product.** This is a hobby / portfolio build with no UL/CE
  listing; don't rely on it unattended for anything that matters, and supervise early
  pump testing.

Report a hardware or physical-safety concern the same private way as a security
issue (above): a private vulnerability report, or a private message to
[@OrangePeachPink](https://github.com/OrangePeachPink).

## Supported versions

Sprout is pre-1.0 and ships from `main`; fixes land on `main`. There are no
long-term-support branches yet.
