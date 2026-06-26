#!/usr/bin/env bash
# Sprout devcontainer setup (#110) — installs the runner + reproduces the env, so a
# Codespace is ready to `just check` / `just start` with no manual steps. Idempotent.
set -euo pipefail

mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"

# uv — the Python env manager (the same one local + CI use).
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# just — the task runner.
if ! command -v just >/dev/null 2>&1; then
  curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to "$HOME/.local/bin"
fi

# Reproduce the locked env and wire the commit hooks.
uv sync
uv run pre-commit install

echo
echo "Sprout devcontainer ready 🌱  —  try:  just start   (or:  just check)"
