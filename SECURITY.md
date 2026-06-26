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

## Supported versions

Sprout is pre-1.0 and ships from `main`; fixes land on `main`. There are no
long-term-support branches yet.
