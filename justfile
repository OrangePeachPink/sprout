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
# Python runs through uv (ADR-0002 #3): `uv run python` uses the locked env and
# auto-syncs it on first use, so every recipe gets reproducible deps. One place to change.

py  := "uv run python"
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
# --restart (#127) takes over a stale server so the icon always opens a fresh dashboard.
start:
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
# Run everything: firmware logic (native C) + the host Python tests.
test: test-native test-host

# Host Python tests (the control-plane seam test today; pytest is the harness for new suites).
test-host:
    {{py}} tools/capture/test_control.py

# ============================================================================
#  QUALITY — lint + the pre-merge gate (ADR-0002 #10/#12; harness here, lanes plug in).
# ============================================================================
# Quick Python lint (fast inner loop); the full gate runs every hook via `just check`.
lint:
    {{py}} -m ruff check .

# Format the C/C++ files changed on this branch vs main (clang-format v22.1.5 — the
# changed-scope gate, #120). Routes through the pinned pre-commit hook, so there's no
# C toolchain to install; it applies the formatting in place, then reports — review the
# diff and commit. Same invocation CI runs, so local == CI.
#   just lint-fw              # vs origin/main
#   just lint-fw <base-ref>   # vs another base (e.g. a fork point)
lint-fw base="origin/main":
    uv run pre-commit run clang-format --from-ref {{base}} --to-ref HEAD --show-diff-on-failure

# Run every pre-commit hook across the repo — the single definition of lint/format/hygiene.
pre-commit:
    uv run pre-commit run --all-files

# The pre-merge gate: all hooks + the tests. Exactly what CI runs (mirrors #89).
check: pre-commit test

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
