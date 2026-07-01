@echo off
REM ============================================================================
REM  Sprout launcher - double-click to start Sprout with zero terminal commands.
REM  Self-updates (git pull --ff-only), then runs `just start` (-> serve.py
REM  --serve-or-focus --open): single-instance (#151) - a second double-click just
REM  opens the existing tab, never a second server or window. Falls back to the
REM  Python entrypoint if `just` isn't installed.
REM
REM  Public-clean: every path is relative to this script - no user path, no port
REM  literal. Stop Sprout from the dashboard's "Stop server" button; you can just
REM  close this window too.
REM ============================================================================
setlocal
title Sprout
REM repo root = two levels up from tools\launch\ (works no matter where you launch from)
cd /d "%~dp0..\.."

REM Self-update so the icon never serves stale code (#127). Non-fatal: offline / a
REM non-fast-forward tree just launches what's on disk. GIT_TERMINAL_PROMPT=0 means a
REM credential prompt FAILS FAST instead of hanging - a launcher must never block entry
REM (Firmware review catch, #132).
echo [sprout] checking for updates...
set GIT_TERMINAL_PROMPT=0
git pull --ff-only 2>nul

where just >nul 2>nul
if %errorlevel%==0 (
  just start
) else (
  echo [sprout] 'just' is not on your PATH - using the Python entrypoint directly.
  echo [sprout] For the full runner library, install just:  winget install --id Casey.Just -e
  echo.
  python tools\analytics\serve.py --serve-or-focus --open
)

REM If we reach here the server stopped (the in-UI Stop button, or Ctrl-C).
endlocal
