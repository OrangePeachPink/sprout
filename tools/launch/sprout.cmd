@echo off
REM ============================================================================
REM  Sprout launcher - double-click to start Sprout with zero terminal commands.
REM  Self-updates (git pull --ff-only), then runs `just start` (-> serve.py --open ->
REM  opens the browser at the fixed port). Falls back to the Python entrypoint if
REM  `just` isn't installed.
REM
REM  Public-clean: every path is relative to this script - no user path, no port
REM  literal. Stop Sprout from the dashboard's "Stop server" button; you can just
REM  close this window too.
REM ============================================================================
setlocal
title Sprout
REM repo root = two levels up from tools\launch\ (works no matter where you launch from)
cd /d "%~dp0..\.."

REM Self-update so the icon always launches the CURRENT code - this is what stops the
REM "icon serves a stale dashboard" problem. Non-fatal: if you're offline or the tree
REM isn't fast-forwardable, we just launch whatever is already on disk.
echo [sprout] checking for updates...
git pull --ff-only
echo.

where just >nul 2>nul
if %errorlevel%==0 (
  just start
) else (
  echo [sprout] 'just' is not on your PATH - using the Python entrypoint directly.
  echo [sprout] For the full runner library, install just:  winget install --id Casey.Just -e
  echo.
  python tools\analytics\serve.py --open
)

REM If we reach here the server stopped (the in-UI Stop button, or Ctrl-C).
endlocal
