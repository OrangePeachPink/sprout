@echo off
REM ============================================================================
REM  Sprout launcher STUB (#1005) - double-click to start Sprout, zero terminal.
REM
REM  *** THIS FILE MUST STAY MINIMAL AND BYTE-STABLE - DO NOT ADD LAUNCHER LOGIC. ***
REM  cmd.exe reads a RUNNING .cmd by byte offset. The `git pull` below updates
REM  files in place - and if it rewrote THIS running file, execution would resume
REM  at a shifted offset and run garbage (the #1005 bug the maintainer hit:
REM  "'launcher' is not recognized", a literal !SHA!, a double update pass). So
REM  this stub does ONLY the self-update, then hands off (call) to sprout-run.cmd,
REM  which the pull is free to change because it isn't running yet. Put every
REM  launcher change in sprout-run.cmd - editing THIS file re-opens the
REM  self-overwrite bug on the one launch that pulls the change.
REM ============================================================================
setlocal enabledelayedexpansion
title Sprout
REM repo root = two levels up from tools\launch\ (works no matter where you launch from)
cd /d "%~dp0..\.."

REM Self-update (#127) + report the running sha / skip reason (#975). Non-fatal:
REM offline / non-ff / a detached root just launches what's on disk, and says so.
REM GIT_TERMINAL_PROMPT=0 -> a credential prompt fails fast, never hangs (#132).
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

REM Hand off to the real launcher - freshly updated by the pull above, and NOT the
REM file we're running, so it's safe to have just changed (#1005). CWD = repo root.
call "%~dp0sprout-run.cmd"
endlocal
