@echo off
REM ============================================================================
REM  Sprout launcher - double-click to start Sprout with zero terminal commands.
REM  Runs `just start` (-> serve.py --open -> opens the browser at the fixed port).
REM  Falls back to the Python entrypoint if `just` isn't installed.
REM
REM  Public-clean: every path is relative to this script - no user path, no port
REM  literal. Stop Sprout from the dashboard's "Stop server" button; you can just
REM  close this window too.
REM ============================================================================
setlocal
title Sprout
REM repo root = two levels up from tools\launch\ (works no matter where you launch from)
cd /d "%~dp0..\.."

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
