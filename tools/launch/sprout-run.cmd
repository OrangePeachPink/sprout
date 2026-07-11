@echo off
REM ============================================================================
REM  Sprout launcher body (#1005). The stub (sprout.cmd) self-updates, then CALLs
REM  this file - so this file is never the one git rewrites mid-run. Launcher
REM  logic changes freely HERE, not in the stub. Run via sprout.cmd (or the
REM  desktop shortcut), not directly; the caller's CWD is the repo root.
REM
REM  Single-instance (#151): a second launch opens the existing tab, never a 2nd
REM  server/window (serve.py --serve-or-focus). Falls back to the Python entrypoint
REM  if `just` isn't installed. Stop from the dashboard's "Stop server" button, or
REM  just close the window.
REM ============================================================================
setlocal
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
