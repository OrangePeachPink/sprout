# Sprout — repo task runner & the one place that records *how every tool here is run*.
#
# This is the common runner library (ADR-0002 #4, ADR-0005 §5). The Firmware lane owns
# this plumbing; **each lane registers its own recipes** in the sections below, so no one —
# maintainer or contributor — ever has to guess a command, a flag, or a port.
#
#   Install just once:   winget install --id Casey.Just -e   (or: scoop install just / cargo install just)
#   Then just run:       just            # lists every recipe
#                        just start      # launches Sprout (the dashboard)
#
# Python runs through uv (ADR-0002 #3): `uv run` uses the locked env and builds it from
# uv.lock on first use, so every recipe gets reproducible deps. One place to change.
#
# --frozen (#254): routine commands use the lock AS-IS and never rewrite it. Without it, a
# stray implicit re-lock (uv re-serializes uv.lock when a contributor's uv version differs
# from the lock's writer) leaves uv.lock dirty, which then silently blocks `git checkout`
# ("Aborting ... uv.lock") - a brutal, causeless first-PR trap. --frozen still BUILDS a
# missing .venv from the lock (verified), so fresh checkouts are unaffected; it only forbids
# WRITING the lock. Dependencies change intentionally via `just lock`, never as a side effect.
py  := "uv run --frozen python"
pio := "pio"

# Show the menu (every recipe + its one-line summary).
default:
    @just --list --unsorted

# ============================================================================
#  START — the single operator entry (ADR-0002 #4 / ADR-0005 §4–5).
#  Runs Data's app surface via `serve.py --open` (Data, #96), which serves AND opens the
#  browser at the fixed port 8765 and owns the in-UI stop — so the port literal lives
#  there and is never duplicated here. The double-click launcher (#86 B) is then just a
#  desktop shortcut that runs `just start`.
# ============================================================================
# Launch Sprout — serve + open the browser at the fixed port (the zero-CLI door). The one operator entry.
# --serve-or-focus (#151) is single-instance: a second launch opens the existing tab, never a 2nd server.
# For a forced fresh start over a stale server, use `just restart`.
start:
    @just serve --serve-or-focus --open

# Force-fresh launch: take over a stale server (ask it to /quit), then serve current code (#127).
restart:
    @just serve --restart --open

# ============================================================================
#  DATA / ANALYTICS lane — the host application surface (ADR-0005; Data owns serve.py).
# ============================================================================
# Serve the live dashboard on the fixed port 8765 (serve.py's own default; `just serve -p 8000` to override).
serve *ARGS:
    {{py}} tools/analytics/serve.py {{ARGS}}

# Friendly alias for `serve`.
dash *ARGS:
    @just serve {{ARGS}}

# List any live Sprout-spawned processes (Monitor logger / Experiment capture) by PID
# + role - the #493 identifiability tool. "Port busy" with no Sprout window open? Run this first.
processes:
    {{py}} tools/analytics/sprout_processes.py

# ============================================================================
#  CAPTURE lane — host-side serial capture (the device-side runtime).
# ============================================================================
# Ctrl-C is the normal way to stop the logger; it archives + exits cleanly on its own, so the
# leading `-` keeps `just` from flagging that expected interrupt as a recipe failure (#148).
# Always-on Monitor mode: the baseline logger (auto-detects the port; pin with `--port COM6`).
logger *ARGS:
    -{{py}} tools/logger/plants_logger.py {{ARGS}}

# Experiment mode: a bounded, isolated capture (never stitched into the baseline).
experiment *ARGS:
    {{py}} tools/capture/experiment_capture.py {{ARGS}}

# ============================================================================
#  FIRMWARE lane — ESP32 / PlatformIO (project lives in firmware/).
# ============================================================================
# Compile the firmware (no board needed).
build:
    {{pio}} run -d firmware

# Compile-check the ESP32-S3 env — same pinned platform as esp32dev, no new toolchain (#436).
build-s3:
    {{pio}} run -d firmware -e esp32s3

# Compile-check the ESP32-C5 env — same pinned platform as esp32dev now (#529), non-blocking CI dry-run (#442/ADR-0024).
build-c5:
    {{pio}} run -d firmware -e esp32c5

# Pin the upload port with e.g.  just flash --upload-port COM6
# Flash the firmware to the board, then open the serial monitor (needs the board connected + your OK).
flash *ARGS:
    {{pio}} run -d firmware -t upload {{ARGS}}

# Native host C unit tests for the firmware logic — no ESP32, no flash. (#260)
# Runs via PlatformIO env:native (Unity framework, host compiler).
test-native:
    {{pio}} test -d firmware -e native

# ============================================================================
#  TEST — the whole harness (ADR-0002 #11). Lanes plug their suites in here.
# ============================================================================
# Run everything: firmware logic (native C) + the host Python tests + the DX tool suite.
test: test-native test-host test-dx

# Host Python tests (the control-plane seam test today; pytest is the harness for new suites).
test-host:
    {{py}} tools/capture/test_control.py

# ============================================================================
#  QUALITY — lint + the pre-merge gate (ADR-0002 #10/#12; harness here, lanes plug in).
# ============================================================================
# Quick Python lint (fast inner loop); the full gate runs every hook via `just check`.
lint:
    {{py}} -m ruff check .

# Check the C/C++ *changed lines* on this branch vs main (clang-format v22.1.5 — the
# changed-LINES gate, #352). git-clang-format formats only the lines you touched, so
# hand-aligned columns survive. Report-only; non-zero if a touched line needs
# formatting (run `just format-fw` to fix). Same wrapper CI runs, so local == CI.
#   just lint-fw              # vs origin/main
#   just lint-fw <base-ref>   # vs another base (e.g. a fork point)
lint-fw base="origin/main":
    {{py}} tools/clang_format_changed_lines.py --base {{base}} --check

# Apply changed-LINES clang-format in place (the fix for what `just lint-fw` reports),
# then review the diff and commit. Touches only the lines changed vs <base> (#352).
format-fw base="origin/main":
    {{py}} tools/clang_format_changed_lines.py --base {{base}}

# Epic sub-issue hygiene (ADR-0003 §2): warn on `epic`-labelled issues that track children
# as `- [ ] #N` prose checkboxes instead of native sub-issues. Reads live issue data via your
# authenticated `gh` (same script CI's epic-hygiene workflow runs, so local == CI).
#   just lint-epics            # warn-only
#   just lint-epics --strict   # non-zero exit if any finding
lint-epics *ARGS:
    {{py}} tools/dx/lint_epic_subissues.py {{ARGS}}

# Run every pre-commit hook across the repo — the single definition of lint/format/hygiene.
pre-commit:
    uv run --frozen pre-commit run --all-files

# The pre-merge gate: all hooks + the tests. Exactly what CI runs (mirrors #89).
check: pre-commit test

# Everything else runs --frozen; commit pyproject.toml + uv.lock together as a deliberate change.
# Update uv.lock after a pyproject.toml dependency change — the ONE command allowed to rewrite it (#254).
lock:
    uv lock

# Release ritual — not wired until the first release (see ADR-0009 versioning & release policy).
ship:
    @echo "ship: not wired yet — see ADR-0009 (versioning & release policy)."

# ============================================================================
#  DX lane — developer experience tooling.
# ============================================================================
# Serve a .dc.html design page over http so its components load (file:// blocks fetch).
# Usage: just preview "docs/design/motion/Sprout Welcome.dc.html"
# Opens the browser automatically; Ctrl-C to stop.  --no-open to skip the browser.
preview *ARGS:
    {{py}} tools/preview.py {{ARGS}}

# Clean-machine onboarding validation (#186) — scripts the exact README/CONTRIBUTING
# Quick Start (uv sync, pre-commit install, dashboard serves, clean shutdown, gate
# passes) with explicit pass criteria per step. Run on a genuinely clean checkout for
# the real test; safe to re-run on an already-set-up machine too.
validate-onboarding:
    {{py}} tools/dx/validate_onboarding.py

# Hardware/network PII scan (#558): image metadata (EXIF/XMP/IPTC) + MAC/USB-ID/SSID
# text greps over the tracked tree. Runs in every commit via pre-commit (blocking).
#   just identifier-guard --history     # one-time audit of every blob ever committed
#   just identifier-guard --strip F...  # remove metadata from image files, byte-level
identifier-guard *ARGS:
    {{py}} tools/dx/identifier_guard.py {{ARGS}}

# DX tool tests (pytest — identifier-guard suite; new DX suites land here too).
test-dx:
    {{py}} -m pytest tools/dx/ -q

# ============================================================================
#  LANES: register your recipes in your section above. Pattern:
#     # One-line summary (this exact line shows in `just --list`).
#     <verb> *ARGS:
#         {{py}} path/to/tool.py {{ARGS}}
#
#  Slots other lanes will likely fill — kept as a checklist, not stubs that lie:
#   • #10 lint lane : lint-md (markdownlint-cli2), lint-spell (cspell)  [lint-fw done — QUALITY above]
#   • Design lane   : token build (design-library CSS output)
#   • Data lane     : analytics/forecast batch jobs, the DuckDB/parquet build, archive tooling
#  Add each as a real recipe once that lane confirms the command + args.
# ============================================================================
