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
setlocal enabledelayedexpansion
title Sprout
REM repo root = two levels up from tools\launch\ (works no matter where you launch from)
cd /d "%~dp0..\.."

REM Self-update so the icon never serves stale code (#127). Non-fatal: offline / a
REM non-fast-forward tree / a detached root just launches what's on disk. But it says
REM so, with the running sha, instead of implying success (#975 - a silent skip served
REM stale code 3x). GIT_TERMINAL_PROMPT=0 means a credential prompt FAILS FAST instead of
REM hanging - a launcher must never block entry (Firmware review catch, #132).
echo [sprout] checking for updates...
set GIT_TERMINAL_PROMPT=0
set "OLD=unknown"
for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set "OLD=%%i"
git pull --ff-only >nul 2>nul
set "PULL_RC=%errorlevel%"
set "SHA=%OLD%"
for /f "delims=" %%i in ('git rev-parse --short HEAD 2^>nul') do set "SHA=%%i"
if "%PULL_RC%"=="0" (
  if "!OLD!"=="!SHA!" (
    echo [sprout] up to date - running !SHA!
  ) else (
    echo [sprout] updated to !SHA!
  )
) else (
  REM Say WHY the pull couldn't happen. A detached root - the agent-parked case that
  REM served stale code - is the common culprit; offline / non-ff share the generic line.
  set "WHY=offline, or a non-fast-forward tree"
  git symbolic-ref -q HEAD >nul 2>nul || set "WHY=detached HEAD - the repo root isn't on a branch"
  echo [sprout] update skipped ^(!WHY!^) - running !SHA!
)

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
