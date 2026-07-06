# PlatformIO in VS Code — first-run behavior & clean-reset runbook

Sprout's firmware is a **PlatformIO** project, and the VS Code PlatformIO IDE extension is the
usual front door (see the [firmware onboarding in CONTRIBUTING](../.github/CONTRIBUTING.md#firmware--build-test-flash-no-arduino-ide)).
This page answers the one question a contributor *and* the maintainer both hit during the v0.7.0
launch: **"why is PlatformIO reinstalling on every restart?"** — plus the safe way to reset it when
it genuinely misbehaves.

TL;DR: a **one-time** re-provision after an update is normal. An **every-restart loop** is not.
The `penv.stale-*` breadcrumbs tell you which one you have.

---

## 1. "PlatformIO is reinstalling" — normal, or a loop?

The extension keeps its Python virtual environment at `~/.platformio/penv` (Windows:
`C:\Users\<you>\.platformio\penv`). On certain events it **rebuilds** that env from scratch — and
when it does, it renames the old one to `penv.stale-<date>` before creating the fresh one. That
rename is the breadcrumb.

Re-provision is **normal and healthy** after any of:

- a **PlatformIO Core update** (the extension bumped Core and rebuilt its env),
- **corruption** it detected and self-healed,
- **CLI penv surgery** (you ran `pio` commands that touched the env),
- a **Python change** underneath it (see §2 — the common trigger).

**The test — read the breadcrumb dates.** Look in `~/.platformio/`:

```text
penv/                    <- the live one
penv.stale-2026-07-01    <- an earlier rebuild
penv.stale-2026-07-03    <- a later rebuild
```

- **Distinct dates, spaced apart** (like above) → **event-driven, healthy.** Each stale dir marks a
  real event (an update, a toolchain change). This is the normal case — nothing to fix.
- **A new `penv.stale-*` every time you restart VS Code**, or several with the *same* date piling up
  in one session → **that's the loop.** Something is re-triggering the rebuild on every launch. Go
  to §2, then §3.

Windows check:

```powershell
Get-ChildItem "$env:USERPROFILE\.platformio" -Directory -Filter 'penv*' |
  Select-Object Name, CreationTime | Sort-Object CreationTime
```

---

## 2. The dual-Python trigger (the usual culprit)

The most common cause of a **repeated** re-provision is **two different Python interpreters** in
play — the extension keeps re-detecting a mismatch and rebuilding to "fix" it:

- the **CLI `pio`** (if you installed it with `pipx`) runs on one interpreter — e.g. **pipx's Python
  3.14.x** on the reference machine this was diagnosed on;
- the extension's **Core `penv`** is built on a *different* interpreter — e.g. **Python 3.11.x**.

When the CLI and the extension disagree about which Python is "PlatformIO's," a restart can look
like corruption to one of them, and it rebuilds.

**Recommended alignment — one interpreter for both.** Pick a single Python and let both the CLI and
the Core penv use it. The lowest-friction options:

- **Let the extension own PlatformIO.** If you only use PlatformIO *inside* VS Code, you don't need
  a separate `pipx`-installed `pio` at all — uninstall the `pipx` copy (`pipx uninstall platformio`)
  and use the extension's bundled Core (its penv is self-managed). One interpreter, no mismatch.
- **Or pin the CLI to the extension's interpreter.** If you want a CLI too, install/point it at the
  same Python the extension uses, so both resolve to one env.

You don't need to chase an exact version — you need **one** interpreter answering for PlatformIO, not
two.

**Related trap — don't run two PlatformIO *extensions*.** Installing **both** the official
**PlatformIO IDE** (`platformio.platformio-ide`) and the **pioarduino IDE** (`pioarduino.pioarduino-ide`,
a *fork* of it) is the same churn from a different angle: two extensions fight over the one PlatformIO
Core + `penv` and re-provision each other in circles. Keep **only** `platformio.platformio-ide` — the
pioarduino *platform* pinned in `firmware/platformio.ini` already gives you the newer-Espressif (S3/C5)
support, no fork extension needed. The repo lists the fork in `firmware/.vscode/extensions.json` →
`unwantedRecommendations`, so VS Code won't prompt you to install it; if a prompt ever slips through
(e.g. PlatformIO re-adds it on configure), **dismiss it — don't install**.

---

## 3. "PlatformIO acting weird?" — the clean-reset runbook

When the env is genuinely wedged (build errors that make no sense, a rebuild loop that §2 didn't
settle, a half-broken toolchain), rebuild it deliberately instead of fighting it:

> ⚠️ **Never do this mid-install.** If PlatformIO is *currently* downloading a platform/toolchain or
> provisioning its env, let it finish first. Deleting `penv` or pruning while an install is running
> is how you *create* the corruption you're trying to fix. Close VS Code, confirm nothing PlatformIO
> is running, *then* reset.

1. **Close VS Code** (stop the extension from re-provisioning under you).
2. **Prune PlatformIO's caches** — safe, removes downloaded-but-unused packages and temp data:

   ```powershell
   pio system prune
   ```

3. **Remove the live env** and let the extension rebuild it clean on next launch:

   ```powershell
   Remove-Item "$env:USERPROFILE\.platformio\penv" -Recurse -Force
   ```

   (The extension recreates `penv` automatically the next time it starts. Your projects,
   installed platforms, and boards are **not** in `penv` — they live elsewhere under `.platformio`,
   so this doesn't touch them.)
4. **Reopen VS Code**, let it re-provision once, then verify:

   ```powershell
   pio --version
   ```

   and a real build from the repo:

   ```powershell
   just build          # or: pio run -d firmware
   ```

   Green build = the env is healthy again.

Old `penv.stale-*` backups can be deleted once a fresh build passes — they're just PlatformIO's own
rollback copies (each is small, but they add up). See
[#695](https://github.com/OrangePeachPink/plants/issues/695) for the housekeeping pass.

---

## 4. `platform list` throws a `UnicodeEncodeError` — ignore it

On a Windows console, `pio platform list` can crash with a cosmetic `UnicodeEncodeError`. That's a
**deprecated-command artifact**, not a health problem. Use the current command instead:

```powershell
pio pkg list          # NOT: pio platform list
```

`pio pkg list` reports your installed platforms/packages without the crash. If you only ever saw the
error from `platform list`, your install is fine.

---

## See also

- [CONTRIBUTING → Firmware](../.github/CONTRIBUTING.md#firmware--build-test-flash-no-arduino-ide) — the firmware front door.
- [FLASHING.md](FLASHING.md) — first flash on a fresh board.
- [BRINGUP.md](BRINGUP.md) — board bring-up.
- [#259](https://github.com/OrangePeachPink/plants/issues/259) — firmware toolchain onboarding (the
  "no ambient compiler" front-door work this sits beside).
