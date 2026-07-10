<!-- markdownlint-disable -->

# Sprout — Clean-Machine Setup Log

Purpose: record every place the documented setup steps break on a **fresh
Windows install**, and what needs to be added so any new community member —
simple user or software developer — can get running.

Portability note: paths are written as `<user-home>` / `<repo-root>`; no real
account or folder names, so this doc is safe to share or fold into the repo.

## ⏩ CURRENT STATE — RESUME HERE (handoff for a Claude Code session in VS Code)

**If you are a fresh session picking this up:** read this whole file, then
continue from here. Working machine = the **ledge PC next to the plants**
(Windows 11), repo cloned at `<user-home>\sprout`.

**Done so far:**
- Clean-machine setup of the repo COMPLETE — dashboard runs at
  http://127.0.0.1:8765 (see findings #1–#5 for the 5 gaps a fresh Windows box
  hits). git/uv/just installed via winget; `sh` provided from Git's `bin`.
- VS Code freshly installed. **PlatformIO IDE extension install may be in
  progress** — verify it finished before building firmware.

**Doing now — firmware flash, IN PLACE (boards not pulled):** land
**OTA-capable firmware** on the **ESP32 classic** (CP2102) and **ESP32-C5**
(CH340). Full playbook in the "Firmware flashing" section below.

**Immediate next actions (in order):**
1. Confirm `platformio.platformio-ide` (official ONLY) finished bootstrapping;
   do NOT add pio-CLI via pipx or the pioarduino fork extension.
2. Install USB-UART drivers: **CP210x ≥11.5.0.417** (classic) + **CH340** (C5).
3. Device Manager → Ports → confirm the board's COM entry (data cable!).
4. Flash the **classic first** (`just build` → `just flash`), verify serial,
   then the **C5** (`just build-c5` → `pio -e esp32c5 -t upload`).
5. **Before flashing, pull `STATUS.md`** — it supersedes the historical
   BRINGUP.md (0.2-era) for the current 0.7.0 firmware / C5 steps.

**Known pain point:** past serial-connection trouble is most likely the
two-different-drivers split (CP2102 vs CH340) + data-cable. Fix drivers first.

---

## ⚠️ FLEET REFLASH — live findings (2026-07-09, brief from session 98a32080)

Task: reflash the two installed boards to the latest firmware (classic `y9d41p`
@192.168.68.87; official C5 `8gtt1h` @192.168.68.85; both on fw string 0.7.0).
Prep done: repo `main`, clean, `git pull` = already up to date. Version string
`PLANTS_FW_VERSION="0.7.0"` (config.h:8) — the "reads 0.7.0 after flash" caveat
is REAL/expected (ADR-0030/#831); `git=` is truth. `SERIAL_BAUD=19200`.

**BLOCKERS / DISCREPANCIES found before flashing — resolve first:**

1. **`pio` not available** — not in `~/.platformio/penv`; PlatformIO IDE
   extension not finished (or not installed). Cannot flash until it is. AND the
   justfile calls bare `pio`, which the extension does NOT put on the system
   PATH — run flashes from **VS Code → PlatformIO Core CLI** terminal (penv
   activated), not plain PowerShell. (Or add `penv\Scripts` to PATH.)

2. **C5 "proven env" in the brief CONTRADICTS `platformio.ini`.** The
   `[env:esp32c5]` block still says *"placeholder classic map — do NOT flash to
   a C5 until #436 lands + bench-verified."* → **That comment is STALE.**
   `board_capability.h:113` now carries an *anticipated* C5 map on valid GPIOs
   (0–28) that replaced the nonexistent classic pins (bench finding 2026-07-03).
   Building `-e esp32c5` compiles that branch, and `.85` already runs 0.7.0 — so
   a reflash is OK to boot/WiFi/OTA. BUT the C5 map is `cal_verified=false`
   (bench-pending) → **C5 sensor readings remain provisional.**
   ACTION: fix the stale platformio.ini comment (doc bug); it directly conflicts
   with board_capability.h and the live fleet.

3. **Driver/port detail in the brief looks wrong for the OFFICIAL C5.**
   BOARDS.md: the official `c5-official-01` (DevKitC-1-**N8R8**) enumerates as
   **CP210x (UART port, COM11) + native USB (COM12)** — NOT CH340. CH340 is the
   **yellow clone** (`c5-yellow-01`). `8gtt1h` is called "official," so expect a
   CP210x/native-USB COM port, not "USB-SERIAL CH340." Confirm which physical
   board `8gtt1h` is before trusting the recover-mode/CH340 guidance.

4. **Possible bug in `esp32c5_recover`:** `upload_flags` uses `--before` value
   `no-reset` (hyphen, platformio.ini:134). esptool's choice is `no_reset`
   (underscore) — a hyphen may be rejected. VERIFY before relying on the
   recovery path; if it errors on the value, that's why.

Classic (`esp32dev`) is the unambiguous KNOWN-GOOD baseline — safe to flash as
written once `pio` is available:
`pio run -d firmware -e esp32dev -t upload --upload-port COMx`

## Test environment

- OS: Windows 11 (fresh install)
- Account: brand-new **admin** account, nothing else installed yet
- Default shell: **Windows PowerShell 5.1** (the built-in blue `powershell.exe`)
- TODO: repeat this whole run on a brand-new **non-admin / standard** account
  — installers and PATH behavior may differ.

## What the README tells you to run

```text
git clone https://github.com/OrangePeachPink/sprout && cd sprout
uv sync
uv run pre-commit install
just start
```

Prereqs it names: `uv` and `just` (or use GitHub Codespaces).

---

## Top recommendation: restructure setup into two phases

The single biggest friction in this run was **reopening the terminal after every
tool install** (uv, then just) because winget updates PATH and an already-open
shell won't see it. The current instructions interleave "install a tool" with
"use a tool," forcing a reopen each time.

**Fix — split the doc into two clear phases:**

1. **Phase 1 — install prerequisites (once):** git, uv, just, all back to back.
   ```powershell
   winget install --id=Git.Git -e            # only if git missing
   winget install --id=astral-sh.uv -e
   winget install --id=Casey.Just -e
   ```
2. **Reopen the terminal ONE time** (or refresh PATH in place — see below).
3. **Phase 2 — the four quick-start lines:** clone / `cd` / `uv sync` /
   `pre-commit install` / `just start`.

**PATH-refresh alternative (avoids reopening at all):** instead of a new
terminal, reload PATH into the current PowerShell session:
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
```
Worth putting in the doc as the "don't want to reopen?" one-liner.

This one change removes 2 of the 3 terminal reopens experienced in this run.

## Findings

### 2. `uv` not installed — `uv sync` fails (prereq has no inline install step)

- **Step:** line 2, `uv sync`
- **Command:** `uv sync`
- **What happened:**
  ```
  uv : The term 'uv' is not recognized as the name of a cmdlet, function,
  script file, or operable program.
  ... CommandNotFoundException
  ```
- **Root cause:** `uv` is not present on a fresh machine. The README lists it
  under Prerequisites but the quick-start block does not include a copy-paste
  command to install it — so anyone following the steps top-to-bottom hits a
  wall here.
- **Fix (Windows, pick one):**
  - Official installer (adds `uv` to PATH):
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
  - Or via winget:
    ```powershell
    winget install --id=astral-sh.uv -e
    ```
  - **Then open a NEW terminal** (PATH changes don't apply to the shell that
    was already open) and re-run `uv sync`. TODO: confirm whether a new shell
    is actually required or if the installer refreshes the current session.
- **README action:** add an explicit "install uv" command to the setup steps
  (per-OS), not just a prose prerequisite. Same will apply to `just`.
- **Install-method decision (for the doc):** prefer the platform-native
  package manager as the PRIMARY step for typical users — `winget` (Windows) /
  `brew` (macOS) — because it's a trusted, built-in source, updatable
  (`winget upgrade` / `brew upgrade`), usually no admin, and avoids the
  scary-looking `-ExecutionPolicy ByPass ... irm | iex` line. Keep the official
  Astral installer as the FALLBACK (no package manager present, want exact
  upstream, or want one uniform cross-OS instruction).
- **This run:** tested the **winget** path — `winget install --id=astral-sh.uv -e`.
- **winget result — SUCCESS:**
  - **winget is present** on this Win11 box (via App Installer). No separate
    install needed here; still note it as a possible gap on stripped/older images.
  - **ID `astral-sh.uv` is correct** — resolved to `uv [astral-sh.uv]`.
  - **First-ever winget run prompted a one-time source agreement:**
    `The 'msstore' source requires that you view the following agreements...
    Do you agree to all the source agreements terms? [Y] Yes [N] No` — must
    answer **Y** to proceed. DOC NOTE: a first-time user WILL hit this prompt;
    call it out so they don't think something's wrong. (`--accept-source-agreements`
    can pre-accept it non-interactively.)
  - Installed **uv version 0.11.26**.
  - **Pulled a dependency:** `Microsoft.VCRedist.2015+.x64` (winget handled it
    automatically — no manual step).
  - **No admin elevation prompt observed** — installed to the user profile.
    Good sign for the non-admin rerun.
  - **PATH note (confirms earlier TODO):** installer printed
    *"Path environment variable modified; restart your shell to use the new
    value."* → a **new terminal is required**; the current shell won't see `uv`.
  - Aliases added: `uv`, `uvx`, `uvw`.
- **Status:** uv INSTALLED. Next: open a fresh shell, `cd sprout`, re-run `uv sync`.

### 2b. After installing uv: MUST open a new shell + re-`cd` (explicit step)

- **Confirmed real step:** after the winget install, the original terminal
  can't see `uv`. Opened a **new** PowerShell window and had to **`cd sprout`
  again** before `uv sync` would run. This "close terminal, reopen, cd back in"
  step is invisible in the current README and trips people up.
- **README action:** add an explicit note after the uv-install line:
  *"Close and reopen your terminal, then `cd sprout` again before continuing."*

### 2c. `uv sync` — SUCCESS (with a UX note)

- **Command:** `uv sync` (in the fresh shell, inside `sprout`)
- **Result — WORKS:**
  - uv auto-selected/downloaded **CPython 3.12.13** — no separate Python
    install required (uv manages the toolchain). One fewer prereq than expected.
  - Created the `.venv`, resolved 27 / installed **25 packages**
    (ruff, pytest, pre-commit, pandas, numpy, duckdb, pyserial, clang-format,
    nodeenv, etc.).
  - **No C compiler / Visual Studio Build Tools needed** — all deps installed
    from prebuilt wheels. (Good; a source build would have been a real blocker.)
  - Total time **< 30 seconds**.
- **UX note worth documenting:** for the first ~5 seconds there was **no output
  and no progress bar** — just a blank prompt — before the TUI progress bars
  appeared. A new user might think it hung. DOC NOTE: mention that `uv sync`
  may sit silently for a few seconds before showing progress; this is normal.
- **Status:** RESOLVED. Environment built. Next original step:
  `uv run pre-commit install`.

### 3. `uv run pre-commit install` — SUCCESS (no changes needed)

- **Command:** `uv run pre-commit install`
- **Result:** `pre-commit installed at .git\hooks\pre-commit`. Clean, instant,
  no prereqs missing. Line 3 of the quick start works as written.
- **Not yet exercised:** the hook *environments* (clang-format, markdownlint,
  ruff) are built on the first actual commit or `just check`, not here — so a
  missing runtime (e.g. Node for markdownlint) could still surface later.
- **Status:** RESOLVED. Next original step: `just start` — but `just` is not
  yet installed (expected finding #4).

### 4. `just` not installed — `just start` fails (prereq has no inline install step)

- **Step:** line 4, `just start`
- **Command:** `just start`
- **What happened:**
  ```
  just : The term 'just' is not recognized ... CommandNotFoundException
  ```
- **Root cause:** same as uv — `just` is a named prerequisite but a fresh
  machine has none, and the quick start has no inline install command.
- **Fix (Windows, primary — same pattern chosen for uv):**
  ```powershell
  winget install --id=Casey.Just -e
  ```
  then **open a new terminal + `cd sprout`** before re-running `just start`.
  (TODO: confirm the exact winget ID `Casey.Just` on the machine; fallback
  installers exist — cargo/scoop/choco, or the GitHub release binary.)
- **README action:** add an explicit per-OS "install just" step alongside the
  "install uv" step. `winget` (Win) / `brew` (mac) as primary.
- **winget result — SUCCESS:**
  - ID `Casey.Just` is correct → `Just [Casey.Just]` **v1.55.1**.
  - **No source-agreement prompt this time** — the msstore agreement accepted
    during the uv install is remembered, so it's a **once-per-machine** prompt,
    not once-per-package. (Reinforces documenting it at the *first* install.)
  - **No extra dependencies**, ~2.11 MB download, **no admin prompt**.
  - Same PATH message: *"restart your shell to use the new value."* → new
    terminal required again. Alias added: `just`.
- **Status:** just INSTALLED. Next: new shell, `cd sprout`, run `just start`.

### 5. `just start` fails on Windows — justfile has no shell for Windows (`sh` not found)

- **Step:** line 4, `just start` (after `just` was installed)
- **Command:** `just start`
- **What happened:**
  ```
  error: recipe 'start' could not be run because just could not find the
  shell 'sh': program not found
  ```
- **Root cause:** `just` runs every recipe's commands through **`sh`** by
  default on ALL platforms, including Windows. Windows has no `sh`. The Sprout
  `justfile` contains **no `set windows-shell` / `set windows-powershell`
  directive** (confirmed by reading the justfile on GitHub), so on Windows it
  looks for `sh`, doesn't find it, and every recipe dies before running. This
  is a **repo-side cross-platform gap**, not a user mistake or a missing
  general prereq — it will hit EVERY Windows user.
- **Note:** the `start` recipe is just `@just serve --serve-or-focus --open`
  (→ `tools/analytics/serve.py`, dashboard on **port 8765**). It's not
  sh-specific, so any working shell would run it.
- **Fix — immediate workaround (unblocks this run):** Git for Windows (already
  installed as the git prereq) ships a POSIX `sh`. Put its `bin` on PATH so
  `just` can find `sh`:
  ```powershell
  $env:Path += ";C:\Program Files\Git\bin"   # session-only; sh.exe lives here
  ```
  then re-run `just start`. (Verify first with `sh --version`.)
- **Fix — proper repo-side options (for the doc / a PR):**
  1. Document that **Windows users need Git-for-Windows' `sh` on PATH** (they
     already have git as a prereq) — or simply **run the commands from Git
     Bash** instead of PowerShell, where `sh` and `&&` both exist. Lowest-risk
     because recipes run exactly as authored.
  2. OR add a `set windows-shell := [...]` directive to the justfile — BUT only
     safe if every recipe's body is compatible with the chosen shell; recipes
     using `&&` / unix tools would break under `powershell.exe`. Needs a
     per-recipe audit. Option 1 is safer for a mixed C/Python/firmware repo.
- **Workaround RESULT — SUCCESS:** after `$env:Path += ";C:\Program Files\Git\bin"`,
  `sh --version` → `GNU bash 5.3.9 (x86_64-pc-cygwin)`, and `just start` then
  ran `uv run --frozen python tools/analytics/serve.py --serve-or-focus --open`.
  Dashboard opened automatically at **http://127.0.0.1:8765** showing
  *"No readings yet - this is a fresh checkout with nothing logged. Press Start
  all collection..."*
- **Confirmed:** the app **runs standalone with NO ESP32 hardware** — a brand-new
  user can boot the dashboard with nothing plugged in. Good for onboarding.
- **Caveat:** the PATH edit above is **session-only**. It must be re-applied
  every new terminal, OR the proper repo-side fix (finding #5 options) should be
  adopted so Windows users don't need it at all.
- **Status:** RESOLVED via workaround. FULL SETUP REACHED — dashboard live.

---

## Outcome: setup completes on a clean Windows machine

All four documented lines eventually work, but a fresh Windows user hits **5
gaps** the current README does not cover. The corrected, copy-pasteable
sequence for Windows:

```powershell
# --- Phase 1: prerequisites (once per machine) ---
winget install --id=Git.Git -e        # only if git is missing
winget install --id=astral-sh.uv -e   # first winget use: accept source terms [Y]
winget install --id=Casey.Just -e
# reopen terminal ONCE here (or refresh PATH in-session)

# --- Phase 2: the project ---
git clone https://github.com/OrangePeachPink/sprout
cd sprout
uv sync                     # auto-installs Python 3.12; ~30s, silent for first ~5s
uv run pre-commit install
$env:Path += ";C:\Program Files\Git\bin"   # give `just` an sh (until repo fix lands)
just start                  # dashboard → http://127.0.0.1:8765 ; Ctrl+C to stop
```

### Gap summary (what to fix in the README / repo)

| # | Gap | Fix location |
|---|-----|--------------|
| 1 | `&&` breaks in Windows PowerShell 5.1 | README: split line 1 / add Windows note |
| 2 | `uv` not installed, no inline install cmd | README: add per-OS uv install (winget/brew) |
| 3 | (`pre-commit install` — worked, no change) | — |
| 4 | `just` not installed, no inline install cmd | README: add per-OS just install (winget/brew) |
| 5 | `just` finds no `sh` on Windows | **Repo:** justfile `set windows-shell`, or doc "use Git Bash / Git sh on PATH" |

### Cross-cutting recommendations
- **Two-phase structure** (install all prereqs → reopen once → run project) to
  kill repeated terminal reopens.
- **Consider telling Windows users to use Git Bash** for the whole flow — it
  would have avoided BOTH finding #1 (`&&`) and finding #5 (`sh`) at once.
  Trade-off: `winget` still runs fine from either shell; test this path.
- **Document the first-run winget msstore agreement** ([Y], once per machine).
- **Warn that `uv sync` sits silent ~5s** before showing progress.

## Product / design observations (beyond clean-machine setup)

These surfaced during the run but are NOT setup-instruction gaps — they're
design/roadmap items to route to the project board.

### A. No data/dashboard portability between machines

- **Observation:** a fresh checkout starts empty ("No readings yet - fresh
  checkout with nothing logged"). There's no path to connect to an existing
  dashboard or pull in previously-logged data when moving to a new machine.
- **Assessment:** *probably the right default* — few users migrate machine-to-
  machine to onboard devices, so building sync/import may not be worth it.
- **Worth considering anyway:** whether some minimal portability (export/import
  of logged data, or pointing a new instance at existing storage) is desirable
  for users who DO switch machines. Low priority; flag for discussion, not a
  blocker.

### B. No device onboarding after startup  — BIGGER ISSUE, needs a roadmap item

- **Observation:** once `just start` is running, there's no flow to onboard /
  register a new device from the dashboard. The landing page says "Press Start
  all collection to begin polling every registered device" — but nothing
  guides a fresh user through *registering* a device in the first place.
- **Assessment:** this is a real gap for new users, bigger than the portability
  note above. Should already exist on the project board as an **issue or epic**
  — verify it's tracked; if not, create it.
- **Action:** confirm/create a project-board item for post-startup device
  onboarding. (Not a setup-doc fix.)

### C. Blank startup screen == the whole first-run experience (ties to UI epic)

- **Observation:** the "No readings yet — fresh checkout with nothing logged"
  page (with a single "Start all collection" button) is **the entirety of what
  a new user sees** after a successful setup. There is no guided next step,
  no device onboarding, no data.
- **Related tracked epic — GitHub issue #875:**
  *"Epic: the Sprout Voice UI — build the user surface we designed first; tuck
  the workbench behind it"* (labels: epic, area:design, for:design, type:feat).
  https://github.com/OrangePeachPink/sprout/issues/875
- **Note for that epic:** this blank first-run screen is the concrete artifact
  of the problem #875 describes — the "user surface" isn't built yet, so the
  fresh-install experience dead-ends here. Worth linking this finding to #875
  and to observation B (device onboarding) as the first-run UX gap.

### Still TODO
- [ ] **Re-run on a brand-new NON-ADMIN / standard account** — verify winget
      installs (uv, just) work without elevation, and whether system-wide git is
      still visible. Expected fine (all user-scope), but must confirm.
- [ ] Verify the `just check` / first-commit path (builds clang-format,
      markdownlint, ruff hook envs — may need Node for markdownlint).
- [ ] Test firmware recipes (`just build`, `just flash`) — need PlatformIO +
      an ESP32; out of scope for a "simple user," relevant for developers.
- [ ] Decide repo fix for #5 (windows-shell directive vs. Git-Bash guidance).
- [ ] **Follow-on session — developer onboarding test:** from this clean
      machine, see whether a new contributor can (a) find/pull a **starter
      issue**, and (b) actually make and **commit a change to the repo** within
      a reasonable amount of time. Separate test from this setup run; queue it
      up. (Will also exercise the pre-commit hook envs / `just check` path from
      TODO above.)

---

# Firmware flashing — in-place on the ledge PC (Windows)

**Context:** flashing 2 boards **in place** (USB reaches them; NOT pulling them
out of the plant rig). Boards: **ESP32 classic** (`esp32dev`, CP2102 bridge) and
**ESP32-C5 dev kit** (`esp32-c5-devkitc-1`, CH340 bridge). Goal: land
**OTA-capable firmware** so future flashes are wireless and no board ever has to
be pulled again. Current firmware streams sensor data over WiFi but has **no OTA
and no live serial** — so this flash must go over **USB**.

**Toolchain is pinned (good news):** `firmware/platformio.ini` pins the platform
to a git ref — `platform = https://github.com/pioarduino/platform-espressif32.git#55.03.39`
(the pioarduino community fork, which is what enables C5 support). The C5 env
`extends = env:esp32dev`, so it inherits the same pin. PlatformIO fetches the
identical toolchain on any machine → C5 build reproducibility is basically
solved; only PlatformIO Core itself is unpinned (install a recent one).

Relevant docs: `docs/FLASHING.md`, `docs/BRINGUP.md`,
`docs/PLATFORMIO_TROUBLESHOOTING.md`, `firmware/platformio.ini`,
`firmware/include/config.h`, `WIRING.md`, `STATUS.md` (current fw state, 0.7.0).
Related issues: #442 (C5 experimental), #259 (fw toolchain onboarding),
#695 (stale-penv housekeeping).

## Step-by-step (this machine)

### 1. Install PlatformIO — let the VS Code extension OWN it
- VS Code → Extensions → install **`platformio.platformio-ide`** (official) —
  and ONLY that. Let it bootstrap its bundled Python + PIO Core (≥6.1.19); wait
  for it to finish (minutes).
- **DO NOT** `pipx install platformio` / install the CLI separately → dual-Python
  mismatch → rebuild-every-restart loop (PLATFORMIO_TROUBLESHOOTING §2).
- **DO NOT** install the `pioarduino.pioarduino-ide` fork extension → duplicate
  provisioning. The pioarduino *platform* is already pinned in platformio.ini;
  the fork *extension* is redundant/conflicting. Official extension only.
- The bundled Python avoids the **Python 3.14 landmine** (PIO 6.1.19 can't build
  its `penv` under 3.14 — uv exit 106; happy path is Python ≤3.13).
- (Optional, from BRINGUP) disable the STM32 clangd extension if present, to
  avoid IntelliSense conflicts.

### 2. USB-UART drivers (the likely root of past serial pain — two DIFFERENT bridges)
- **ESP32 classic → CP2102:** Silicon Labs **CP210x** VCP driver, **≥ v11.5.0.417**
  (verify version in Device Manager).
- **ESP32-C5 → CH340:** **WCH CH340** driver.
- A fresh Windows machine may have neither. Installing both up front is likely
  what fixes the recurring "COM port won't show up" problem.

### 3. Confirm the PC can see the board (BRINGUP Rung 1)
- Plug board in with a **USB *data* cable** (not charge-only — a classic gotcha).
- Device Manager → **Ports (COM & LPT)** → board appears as:
  - classic: "CP2102 USB to UART Bridge" / "Silicon Labs CP210x"
  - C5: "USB-SERIAL CH340"
- COM number **shifts between reconnects** — don't hardcode it.

### 4. First flash — do the CLASSIC first (proven path) (BRINGUP Rung 2)
- Open the **`firmware/`** folder in VS Code (first build caches the toolchain).
- Build: `pio run` (or `just build` → `pio run -d firmware`). ~10s.
- Upload: `pio run --target upload` (or `just flash`). ~15s; board auto-resets,
  no manual BOOT/RST hold on genuine boards (some clones need BOOT held).
- Serial Monitor: telemetry runs at **19200 baud** (platformio.ini
  `monitor_speed = 19200`); the 0.0.1 bring-up banner in BRINGUP was 115200 —
  **watch for a baud mismatch**, try both. Expect a version banner + GPIO2 LED
  blink ~1 Hz.

### 5. Then the ESP32-C5
- Build/upload via the C5 env: `just build-c5` (→ `pio run -d firmware -e esp32c5`)
  then upload with `-e esp32c5 -t upload`.
- **The browser web-flasher does NOT work for the C5** — `factory_bin.py`
  hardcodes `chipFamily: "ESP32"`, so ESP Web Tools is classic-only today. Use
  the direct `pio ... -t upload` path for the C5.
- Recovery net exists: **`esp32c5_recover`** env if the C5 gets wedged.
- C5 is officially **experimental (#442)** — if its toolchain misbehaves on this
  machine despite the pin, fallback is to pull ONLY the C5 to the bench (classic
  already done in place).

### 6. OTA (the payoff, once this firmware lands)
- OTA env exists per board: `pio run -d firmware -e {board}_ota -t upload
  --upload-port sprout-{device}.local`. Not usable until the OTA-capable
  firmware from THIS flash is on the device; today "repeat the flash for updates."

## Flashing troubleshooting quick-refs (from PLATFORMIO_TROUBLESHOOTING.md)
- **Rebuilds every VS Code restart** → dual-Python. Fix: `pipx uninstall platformio`
  (let extension own it) OR `pipx reinstall platformio --python 3.12`.
- **Wedged / weird build errors** → clean reset (only when NOT mid-install):
  close VS Code → `pio system prune` →
  `Remove-Item "$env:USERPROFILE\.platformio\penv" -Recurse -Force` → reopen VS
  Code (it recreates penv) → `pio --version` → `just build` to confirm green.
- **`pio platform list` crashes (UnicodeEncodeError on Windows)** → use
  `pio pkg list` instead (the crash is a deprecated-command artifact, not ill health).

## New findings to fold into the setup docs
- [ ] `platformio.ini` lives in **`firmware/`**, not repo root (the README's
      stack blurb implied root — minor doc accuracy fix).
- [ ] The **CP210x + CH340 driver split** and the **data-cable** requirement
      belong in FLASHING/BRINGUP prominently for Windows users — likely the #1
      cause of "can't get serial."
- [ ] BRINGUP.md is flagged historical (0.2-era); **STATUS.md supersedes it for
      ≥0.7.0** — confirm current C5 steps against STATUS.md before flashing.
- [ ] Baud inconsistency (19200 in platformio.ini vs 115200 in BRINGUP) — verify
      and document the correct monitor speed.

### 1. `&&` fails in Windows PowerShell 5.1 — very first line breaks

- **Step:** clone + cd (line 1 of the quick start)
- **Command:** `git clone https://github.com/OrangePeachPink/sprout && cd sprout`
- **What happened:**
  ```
  The token '&&' is not a valid statement separator in this version.
  ```
- **Root cause:** The `&&` chain operator only exists in **PowerShell 7+**
  (`pwsh`) and in bash. The Windows default shell is **Windows PowerShell 5.1**,
  which does not support it. A brand-new machine has only 5.1.
- **Fix (any of):**
  - Run the two commands on separate lines:
    ```powershell
    git clone https://github.com/OrangePeachPink/sprout
    cd sprout
    ```
  - Or use `;` (note: `;` runs `cd` even if the clone fails, so separate
    lines are safer).
  - Or install PowerShell 7 (`winget install --id Microsoft.PowerShell -e`)
    and use `pwsh`, where `&&` works as written.
- **README action:** the quick-start block is written in bash/pwsh7 syntax.
  Add a Windows note, or split line 1 into two lines so it is copy-paste-safe
  in the default shell every Windows user starts with.
- **Minimal fix used in this run:** dropped the ` && cd sprout` portion and
  ran `git clone https://github.com/OrangePeachPink/sprout` alone. Clone
  succeeded (4342 objects, ~19.7 MiB). `cd sprout` then run as its own line.
- **Status:** RESOLVED with the two-line workaround. README should split
  line 1 so the default Windows shell can copy-paste it as-is.

---

## Prerequisite gaps found so far

(Filled in as the run continues. Expect `git`, `uv`, and `just` to each need a
documented Windows install step, since a fresh machine has none of them.)

- `git` — **PRESENT, but system-wide / pre-existing — NOT provided by the test
  account.** `(Get-Command git).Source` → `C:\Program Files\Git\cmd\git.exe`,
  i.e. a machine-scope install visible to every account, including this
  freshly-created one. Windows ships no git by default, so a *truly* bare
  machine would need `winget install --id Git.Git -e`. Caveat: this test box is
  therefore not pure-clean for git. (Diagnostic run in a separate window to
  keep the main setup transcript unaltered.) Confirm on the non-admin run —
  git should still appear there, proving it's inherited, not account-provided.
- `uv` — **INSTALLED via winget** (`astral-sh.uv`, v0.11.26). Not present on a
  fresh machine; needs a documented install step. winget path works, no admin,
  requires a new shell afterward. See finding #2.
- `just` — **INSTALLED via winget** (`Casey.Just`, v1.55.1). Not present on a
  fresh machine; needs a documented install step. No deps, no admin, new shell
  required. See finding #4.
