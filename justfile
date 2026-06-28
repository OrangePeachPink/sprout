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

# Needs a host C compiler: gcc on PATH, or  CC=/path/to/gcc just test-native  (e.g. a winget MinGW gcc.exe).
# Native host C unit tests for the firmware logic — no ESP32, no flash.
test-native:
    sh tests/native/build_and_run.sh

# C/C++ format check via clang-format v22.1.5 (pinned by pre-commit, #120).
# Applies fixes in place; exits non-zero if any file was changed (re-stage + recommit).
# Identical to what CI runs — local == CI.
lint-fw:
    uv run pre-commit run clang-format --all-files

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

# Run every pre-commit hook across the repo — the single definition of lint/format/hygiene.
pre-commit:
    uv run pre-commit run --all-files

# The pre-merge gate: all hooks + the tests. Exactly what CI runs (mirrors #89).
check: pre-commit test

# Release ritual — not wired until the first release (see ADR-0009 versioning & release policy).
ship:
    @echo "ship: not wired yet — see ADR-0009 (versioning & release policy)."

# ============================================================================
#  LANES: register your recipes in your section above. Pattern:
#     # One-line summary (this exact line shows in `just --list`).
#     <verb> *ARGS:
#         {{py}} path/to/tool.py {{ARGS}}
#
#  Slots other lanes will likely fill — kept as a checklist, not stubs that lie:
#   • #10 lint lane : lint-md (markdownlint-cli2), lint-spell (cspell), lint-fw (clang-format --dry-run)
#   • Design lane   : token build / design-library preview runner
#   • Data lane     : analytics/forecast batch jobs, the DuckDB/parquet build, archive tooling
#  Add each as a real recipe once that lane confirms the command + args.
# ============================================================================
