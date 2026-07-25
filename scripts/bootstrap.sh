#!/usr/bin/env sh
# Sprout bootstrap (#1557) - from a fresh clone to a ready dev environment.
#
# Installs the two tools this project needs (uv, just) if they are missing, then
# syncs the locked environment and wires the pre-commit hooks. Safe to re-run:
# every step checks first and skips what is already there.
#
#   ./scripts/bootstrap.sh               install what's missing, then sync + hooks
#   ./scripts/bootstrap.sh --tools-only  stop after uv + just
#
# Windows: use scripts\bootstrap.ps1 instead.
#
# It never installs git. Getting version control and a GitHub account is its own
# step with its own choices, and a bootstrap script is the wrong thing to make
# them for you - so it checks, reports, and points at the docs.

set -eu

TOOLS_ONLY=0
CHECK_ONLY=0
for arg in "$@"; do
    case "$arg" in
    --tools-only) TOOLS_ONLY=1 ;;
    --check-only) CHECK_ONLY=1 ;;
    -h | --help)
        sed -n '2,15p' "$0" | sed 's/^#\{1,\} \{0,1\}//'
        exit 0
        ;;
    *)
        echo "bootstrap: unknown option '$arg' (try --help)" >&2
        exit 2
        ;;
    esac
done

say() { printf '\n>> %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --check-only: say what IS and ISN'T here, install nothing, exit 0. Two callers want
# this. A human asking "what is this about to do to my machine?" deserves an answer
# before it does it. And the onboarding guard (#1562) has to prove the toolless path
# works from a shell that genuinely lacks uv and just — which it cannot do by running
# the real installers, because a guard that reaches the network and mutates the machine
# it is grading is not a guard.
if [ "$CHECK_ONLY" -eq 1 ]; then
    printf 'bootstrap --check-only (nothing will be installed)\n'
    for tool in git uv just; do
        if have "$tool"; then
            printf '  present  %s\n' "$tool"
        else
            printf '  MISSING  %s\n' "$tool"
        fi
    done
    exit 0
fi

# ---------------------------------------------------------------- git (check only)
if have git; then
    say "git $(git --version | awk '{print $3}') - ok"
else
    cat >&2 <<'EOF'

bootstrap: git is not installed, and this script will not install it for you.

  macOS    xcode-select --install     (or: brew install git)
  Linux    sudo apt install git       (or your distro's package manager)
  Windows  winget install Git.Git     (then use scripts\bootstrap.ps1)

Then re-run this script. See docs/contributing/your-first-pr.md.
EOF
    exit 1
fi

# ---------------------------------------------------------------------------- uv
if have uv; then
    say "uv $(uv --version | awk '{print $2}') - already installed"
else
    say "uv is missing - installing it from Astral's published installer:"
    echo "     https://astral.sh/uv/install.sh"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # The installer drops uv in ~/.local/bin, which this shell may not have on PATH yet.
    have uv || { PATH="$HOME/.local/bin:$PATH" && export PATH; }
    have uv || {
        echo "bootstrap: uv installed but is not on PATH. Open a new shell, re-run." >&2
        exit 1
    }
    say "uv $(uv --version | awk '{print $2}') - installed"
fi

# -------------------------------------------------------------------------- just
if have just; then
    say "just $(just --version | awk '{print $2}') - already installed"
else
    if have brew; then
        say "just is missing - installing with Homebrew (brew install just)"
        brew install just
    else
        say "just is missing - installing from the project's published installer:"
        echo "     https://just.systems/install.sh -> ~/.local/bin"
        mkdir -p "$HOME/.local/bin"
        curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh |
            bash -s -- --to "$HOME/.local/bin"
        have just || { PATH="$HOME/.local/bin:$PATH" && export PATH; }
    fi
    have just || {
        echo "bootstrap: just installed but is not on PATH. Open a new shell, re-run." >&2
        exit 1
    }
    say "just $(just --version | awk '{print $2}') - installed"
fi

if [ "$TOOLS_ONLY" -eq 1 ]; then
    say "Tools ready. Next: uv sync && uv run pre-commit install && just start"
    exit 0
fi

# ------------------------------------------------------- the environment + hooks
cd "$(dirname "$0")/.."

say "Syncing the locked environment (uv sync)"
uv sync

say "Wiring the pre-commit hooks (uv run pre-commit install)"
uv run pre-commit install

# ------------------------------------------------------------------------ verify
# Say what is true, having just proven it - not "done!" on faith.
say "Ready. Verified on this machine:"
printf '     git   %s\n' "$(git --version | awk '{print $3}')"
printf '     uv    %s\n' "$(uv --version | awk '{print $2}')"
printf '     just  %s\n' "$(just --version | awk '{print $2}')"
printf '     env   %s\n' "$(uv run python --version 2>/dev/null || echo 'uv sync did not produce a Python')"

cat <<'EOF'

Next:
     just start     run Sprout - opens the dashboard in your browser
     just           list every command
     just check     your local gate (lint, format, host tests - no compiler needed)
EOF
