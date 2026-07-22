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

# Headless collection lifecycle (#689): see/start/stop collection without the dashboard.
# `just collection status|start|stop` - parity with the dashboard's one-action "Start all
# collection" (ADR-0014). `status` reuses `just processes`; `start` posts to a running server.
collection ACTION="status" *ARGS:
    {{py}} tools/dx/collection.py {{ACTION}} {{ARGS}}

# Stop every running collector (monitor + fleet) headlessly - graceful, then hard-kill (#689).
# The recourse when a browser tab closed or a collector orphaned and there's no Stop button.
stop-collection *ARGS:
    {{py}} tools/dx/collection.py stop {{ARGS}}

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

# Flash the ALPHA channel — the CLI counterpart of the web flasher's alpha (#1334): current main,
# the dev-team build, unversioned and unproven. It flashes your CHECKED-OUT tree over USB, labeled
# by exact COMMIT — never a release version string (that would be a lie about unreleased bytes,
# the drift the channel split exists to end). It does NOT checkout/pull — that would mutate a lane
# worktree (AGENTS §2.5); it fetches read-only and WARNS if you're behind origin/main or off it, so
# "latest main" is a `git pull` you choose, not a surprise. Stable, by contrast, is a cut release:
# flash that from the web flasher, or check out its tag and `just flash`. Firmware's bench byte-path;
# same USB prereqs as `just flash` (board connected + your OK). Args pass through to the uploader.

# Flash the alpha channel (current main, dev-team, commit-labeled) over USB — the CLI alpha (#1334).
flash-alpha *ARGS:
    #!/usr/bin/env sh
    set -u
    git fetch --quiet origin main 2>/dev/null || true
    commit="$(git rev-parse --short HEAD)"
    branch="$(git branch --show-current)"; [ -n "$branch" ] || branch="detached"
    behind="$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)"
    printf '>> ALPHA channel - current build, NOT a release (commit=%s branch=%s)\n' "$commit" "$branch"
    printf '>> Unversioned + unproven, the dev-team channel - expect the unexpected.\n'
    [ "$branch" != "main" ] && printf '>> NOTE: alpha = current main; you are on "%s", so this flashes THAT.\n' "$branch"
    [ "$behind" -gt 0 ] && printf '>> NOTE: origin/main is %s commit(s) ahead - `git pull` first for the latest alpha.\n' "$behind"
    just flash {{ARGS}}

# OTA-flash a board over WiFi by its mDNS device_id (#302 Phase-0, LAN-only). No USB.
#   e.g.  just ota k7m2rt                       (classic esp32dev — targets sprout-k7m2rt.local)
#         just ota n3jhsp esp32c5               (C5 board — uses the esp32c5_ota env)
#         just ota n3jhsp esp32c5 192.168.1.42  (multi-homed host: pin the LAN callback IP)
# Board-aware: the optional 2nd arg selects the <board>_ota env (default esp32dev).
# host_ip (optional 3rd arg, #1227): pins the espota UDP ack-callback interface for a multi-homed
#   host (LAN + VPN + WSL). Setting PLATFORMIO_UPLOAD_FLAGS *replaces* the ini's upload_flags, so we
#   repeat --auth, newline-joined (space-joined arrives as one argv token and breaks auth; see #1225).
#   The --auth value is resolved like the ini would (#1268): the gitignored platformio_local.ini
#   override (#1260) wins, else the in-tree placeholder — so a rotated password still authenticates here.
# Truth check (#1227): espota's UDP ack can time out even after a healthy flash on a multi-homed host,
#   exiting FAILED on success. So after upload we poll the board's status page for git= and report
#   reality — VERIFIED on the sha when it's back on the expected commit; a real failure only if it
#   never returns (which also catches a genuine half-flash).
# Prereqs: the board already runs OTA firmware (>= this build) + has WiFi creds set.
# Honest limits: a DEAD or NEW/unprovisioned board has no OTA receiver — flash it WIRED
# (just flash). Password is the Phase-0 placeholder in the <board>_ota env. See docs/OTA_FLASH.md.
ota device board="esp32dev" host_ip="":
    #!/usr/bin/env sh
    set -u
    host="sprout-{{device}}.local"
    expected="$(git rev-parse --short HEAD)"
    printf '>> ota: flashing %s (env %s_ota) — expecting git=%s\n' "$host" "{{board}}" "$expected"
    if [ -n "{{host_ip}}" ]; then
        # env var REPLACES the ini upload_flags → repeat --auth; newline-joined, not space (#1225).
        # Resolve --auth like the ini (#1268): the gitignored platformio_local.ini override (#1260)
        # wins, else the in-tree placeholder — so a rotated password still authenticates on this path.
        auth="sprout-phase0"; auth_src="in-tree placeholder"
        if [ -f firmware/platformio_local.ini ]; then
            la="$(awk -v want="[env:{{board}}_ota]" '
                $0 == want { inenv = 1; next } /^\[/ { inenv = 0 }
                inenv && match($0, /--auth=[^[:space:]]+/) { print substr($0, RSTART + 7, RLENGTH - 7); exit }
            ' firmware/platformio_local.ini)"
            [ -z "$la" ] && la="$(awk 'match($0, /--auth=[^[:space:]]+/) { print substr($0, RSTART + 7, RLENGTH - 7); exit }' firmware/platformio_local.ini)"
            [ -n "$la" ] && { auth="$la"; auth_src="platformio_local.ini"; }
        fi
        PLATFORMIO_UPLOAD_FLAGS="$(printf -- '--auth=%s\n--host_ip=%s' "$auth" "{{host_ip}}")"
        export PLATFORMIO_UPLOAD_FLAGS
        # never echo the password — report only its SOURCE (#1268).
        printf '>> host_ip pinned to %s (auth from %s, repeated in the upload flags)\n' "{{host_ip}}" "$auth_src"
    fi
    {{pio}} run -d firmware -e {{board}}_ota -t upload --upload-port "$host" \
        || printf '>> espota exit was non-zero — checking the board itself before believing it (#1227)\n'
    printf '>> verifying via http://%s/ (board reboots + re-announces mDNS; polling ~60s)...\n' "$host"
    got=""
    i=0
    while [ "$i" -lt 20 ]; do
        got="$(curl -fs --max-time 3 "http://$host/" 2>/dev/null | sed -n 's/.*git=\([0-9A-Fa-f][0-9A-Fa-f]*\).*/\1/p' | head -n1)"
        [ -n "$got" ] && break
        i=$((i + 1)); sleep 3
    done
    if [ -z "$got" ]; then
        printf '>> FAILED: %s never answered after upload — mDNS/WiFi down, or a genuine bad flash.\n' "$host"
        exit 1
    fi
    if [ "$got" = "$expected" ]; then
        printf '>> VERIFIED on %s — the board is running the expected commit.\n' "$got"
    else
        printf '>> FAILED: board reports git=%s but expected %s (half-flash or a stale image).\n' "$got" "$expected"
        exit 1
    fi

# Native host C unit tests for the firmware logic — no ESP32, no flash. (#260)
# Runs via PlatformIO env:native (Unity framework, host compiler).
test-native:
    {{pio}} test -d firmware -e native

# ============================================================================
#  TEST — the whole harness (ADR-0002 #11). Lanes plug their suites in here.
# ============================================================================
# Run everything: firmware logic (native C) + the host Python tests + the DX + analytics suites.
test: test-native test-host test-dx test-analytics

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

# ADR register hygiene (#928): every ADR file's `**Status:**` must match its row in the
# register (0000), and no ADR may appear twice. Trellis caught this drift by hand twice
# (0025; then a merge-ordering collision left two 0029 rows at different statuses). File-based
# + deterministic — same check runs here, in pre-commit, and in CI (red on mismatch).
lint-adr:
    {{py}} tools/dx/lint_adr_register_status.py

# Run every pre-commit hook across the repo — the single definition of lint/format/hygiene.
pre-commit:
    uv run --frozen pre-commit run --all-files

# THE DEFAULT GATE (#1337) — needs exactly two tools: `uv` and `just`.
#
# This runs everything a docs / dashboard / Python / graphics contribution can break: every
# pre-commit hook plus the host, DX and analytics suites. Most arrivals touch one of those, so
# the default is the door most people walk through, and the two-tool promise in the README is
# TRUE for it rather than true-with-a-correction.
#
# It deliberately does NOT run the native C firmware tests — those need PlatformIO and a host
# compiler, which is a real install we do not ask a docs contributor to do. The recipe SAYS SO
# when it finishes: a gate that quietly runs less than you think it does is indistinguishable
# from one that passed (the #1327 lesson), so the omission is announced, never implied.

# The default gate: pre-commit + host/DX/analytics tests. Needs only uv + just (#1337).
check: pre-commit test-host test-dx test-analytics
    @echo ""
    @echo "  check PASSED - pre-commit + host + DX + analytics."
    @echo "  NOT run: test-native (the native C firmware tests; they need PlatformIO + a compiler)."
    @echo "  Touched firmware/ ? run:  just check-firmware"
    @echo "  Either way CI runs the full battery on every PR - this is your local gate, not the gate."
    @{{py}} tools/dx/untracked_notice.py

# THE FIRMWARE GATE (#1337): the default gate PLUS the native C tests. Needs PlatformIO and a
# host compiler on top of uv + just — named honestly on its own path rather than hidden inside
# the default, so the bigger install belongs to the smaller door.

# The firmware gate: everything `check` runs PLUS the native C tests (needs PlatformIO).
check-firmware: check test-native

# Back-compat alias (#1189 shipped this name; `check` now means the same thing). Kept so muscle
# memory and existing docs/scripts keep working — safe to use, nothing to change.

# Alias for `check` — the old #1189 name, kept working.
check-host: check

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
#   just identifier-guard --deny-host H # add hostname H to the committed hash denylist (#865)
identifier-guard *ARGS:
    {{py}} tools/dx/identifier_guard.py {{ARGS}}

# Internal-link gate (#913): every relative / GitHub-self link in md+html resolves to a tracked
# file, and no self-link carries a broken ref (the /blob/HEAD/ class behind #908). Offline; runs
# in every commit via pre-commit (blocking). External links are the weekly battery's lychee job.
# Known debt (each owing a ticket): tools/dx/link_check_allowlist.txt.
#   just link-check          # report + non-zero on any active finding
link-check *ARGS:
    {{py}} tools/dx/link_check.py --check {{ARGS}}

# Voice register sweep (#1161): changed-lines guard is a pre-commit hook (advisory); this
# recipe is the manual/release entry point.
#   just voice-guard --all                        # full-tree sweep (the RELEASE_CUT §3 backstop)
#   just voice-guard --diff-range origin/main...HEAD   # a PR's delta
voice-guard *ARGS:
    {{py}} tools/dx/voice_guard.py {{ARGS}}

# Board-hygiene lint (#732): the board must tell the truth. Sweeps every card for
# closed-not-Done drift (blocking), stale In-Progress (advisory, --stale-days 4), and
# oversized milestones (advisory, --milestone-warn 40). Event-driven: run at the release
# cut + on demand; needs the local gh login (ProjectV2 scope — not a per-PR CI job).
#   just board-hygiene              # sweep + non-zero on closed-not-Done drift
#   just board-hygiene --advisory   # report only
board-hygiene *ARGS:
    {{py}} tools/dx/board_hygiene.py {{ARGS}}

# ---- Board field self-service (#1443, ADR-0003 §5) -------------------------------------
# Read/write the five Project-#2 planning fields in one line, so an attribute is never
# skipped because writing it was annoying (how velocity: drifted to 7-of-69). Every WRITE
# re-queries and prints what the board now reports — the mutation's "ok" is not trusted
# (#519/#522). Needs the local gh login (ProjectV2 scope); works from any worktree.
#   just board 1443                 # read all five fields for issue 1443
#   just owner 1443 dx              # firmware|data|design|dx|trellis|workflow|maintainer
#   just velocity 1443 v2           # v1|v2
#   just size 1443 s                # xs|s|m|l|xl
#   just priority 1443 p1           # p0|p1|p2|p3
#   just status 1443 verify         # backlog|progress|verify|ready|done

# Read all five board fields for issue N (owner/velocity/size/priority/status).
board N:
    {{py}} tools/dx/board_field.py read {{N}}
owner N VALUE:
    {{py}} tools/dx/board_field.py owner {{N}} {{VALUE}}
velocity N VALUE:
    {{py}} tools/dx/board_field.py velocity {{N}} {{VALUE}}
size N VALUE:
    {{py}} tools/dx/board_field.py size {{N}} {{VALUE}}
priority N VALUE:
    {{py}} tools/dx/board_field.py priority {{N}} {{VALUE}}
status N VALUE:
    {{py}} tools/dx/board_field.py status {{N}} {{VALUE}}

# DX tool tests (pytest — identifier-guard + link-check suites; new DX suites land here too).
test-dx:
    {{py}} -m pytest tools/dx/ -q

# Analytics / dashboard tests (pytest — parse, serve, dashboard correctness; 465 tests). Wired into
# `just check` per #853: was ungated (`test` skipped it); now also CI-gated per-PR (#905 public posture).
# ~70s — the real cost of the compensating control actually running.
test-analytics:
    {{py}} -m pytest tools/analytics/ -q

# --- The DuckDB/Parquet analysis-store tier (#828 / #1239; DX ergonomics #1249) --------------
# Analytics-only path — none of these need a firmware toolchain (pairs with `just check-host`).
#
# Build: backfill every historical logs/*.csv -> reports/tier/raw (gitignored + regenerable, per
# docs/TIER_STORE_CONTRACT.md). Idempotent + resumable (--skip-existing), fidelity-checked per
# partition (§6). Re-running converges to the same bytes; delete reports/tier to rebuild clean.
store-rebuild *ARGS:
    {{py}} tools/analytics/tier_backfill.py {{ARGS}}

# Verify the store is contract-compliant: (re)builds one reference partition and asserts its DuckDB
# rollup EXACTLY equals an independent integer-us recompute (the s4 invariant) + prints the provenance
# lineage (source_file / schema_version). Non-zero exit on any mismatch. Consumes tier_store, not a copy.
store-verify device="y9d41p" date="2026-07-18":
    {{py}} tools/analytics/tier_store.py --device {{device}} --date {{date}}

# Ad-hoc SQL over the store (registered as the `store` view; date/device are hive-partition columns):
#   just store-query "SELECT device, band, COUNT(*) FROM store GROUP BY 1, 2 ORDER BY 3 DESC"
store-query sql:
    {{py}} tools/analytics/tier_query.py "{{sql}}"

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
