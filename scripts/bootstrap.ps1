<#
Sprout bootstrap (#1557) - from a fresh clone to a ready dev environment.

Installs the two tools this project needs (uv, just) if they are missing, then
syncs the locked environment and wires the pre-commit hooks. Safe to re-run:
every step checks first and skips what is already there.

    .\scripts\bootstrap.ps1               install what's missing, then sync + hooks
    .\scripts\bootstrap.ps1 -ToolsOnly    stop after uv + just

macOS / Linux: use ./scripts/bootstrap.sh instead.

It never installs git. Getting version control and a GitHub account is its own
step with its own choices, and a bootstrap script is the wrong thing to make
them for you - so it checks, reports, and points at the docs.

Written for Windows PowerShell 5.1 as well as pwsh 7: 5.1 is what a fresh
Windows box actually has, so this file uses no 7-only syntax (no '&&', no
ternary, no null-coalescing). A bootstrap that needs the thing you are
bootstrapping is not a bootstrap.
#>
[CmdletBinding()]
param([switch]$ToolsOnly)

$ErrorActionPreference = 'Stop'

function Say($msg) { Write-Host "`n>> $msg" }
function Have($name) {
    $null -ne (Get-Command $name -ErrorAction SilentlyContinue)
}
function Refresh-Path {
    # A freshly-installed tool lands in a PATH this process has not re-read.
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user;$env:USERPROFILE\.local\bin"
}

# ---------------------------------------------------------------- git (check only)
if (Have 'git') {
    Say "git $((git --version).Split(' ')[2]) - ok"
}
else {
    Write-Host @'

bootstrap: git is not installed, and this script will not install it for you.

  winget install Git.Git        (or download from https://git-scm.com/downloads)

Then open a NEW terminal and re-run this script.
See docs/contributing/your-first-pr.md.
'@ -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------- uv
if (Have 'uv') {
    Say "uv $((uv --version).Split(' ')[1]) - already installed"
}
else {
    if (Have 'winget') {
        Say 'uv is missing - installing with winget (astral-sh.uv)'
        winget install --id astral-sh.uv --source winget --accept-package-agreements --accept-source-agreements
    }
    else {
        Say 'uv is missing - installing from Astral''s published installer:'
        Write-Host '     https://astral.sh/uv/install.ps1'
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    }
    Refresh-Path
    if (-not (Have 'uv')) {
        Write-Host 'bootstrap: uv installed but is not on PATH. Open a NEW terminal and re-run.' -ForegroundColor Red
        exit 1
    }
    Say "uv $((uv --version).Split(' ')[1]) - installed"
}

# -------------------------------------------------------------------------- just
if (Have 'just') {
    Say "just $((just --version).Split(' ')[1]) - already installed"
}
else {
    if (Have 'winget') {
        Say 'just is missing - installing with winget (Casey.Just)'
        winget install --id Casey.Just --source winget --accept-package-agreements --accept-source-agreements
    }
    else {
        Say 'just is missing - installing from the project''s published installer:'
        Write-Host "     https://just.systems/install.ps1 -> $env:USERPROFILE\.local\bin"
        $dest = Join-Path $env:USERPROFILE '.local\bin'
        if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Force -Path $dest | Out-Null }
        Invoke-RestMethod https://just.systems/install.ps1 | Invoke-Expression
    }
    Refresh-Path
    if (-not (Have 'just')) {
        Write-Host 'bootstrap: just installed but is not on PATH. Open a NEW terminal and re-run.' -ForegroundColor Red
        exit 1
    }
    Say "just $((just --version).Split(' ')[1]) - installed"
}

if ($ToolsOnly) {
    Say 'Tools ready. Next: uv sync; uv run pre-commit install; just start'
    exit 0
}

# ------------------------------------------------------- the environment + hooks
Set-Location (Join-Path $PSScriptRoot '..')

Say 'Syncing the locked environment (uv sync)'
uv sync
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Say 'Wiring the pre-commit hooks (uv run pre-commit install)'
uv run pre-commit install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# ------------------------------------------------------------------------ verify
# Say what is true, having just proven it - not "done!" on faith.
Say 'Ready. Verified on this machine:'
Write-Host "     git   $((git --version).Split(' ')[2])"
Write-Host "     uv    $((uv --version).Split(' ')[1])"
Write-Host "     just  $((just --version).Split(' ')[1])"
$py = (uv run python --version 2>$null)
if (-not $py) { $py = 'uv sync did not produce a Python' }
Write-Host "     env   $py"

Write-Host @'

Next:
     just start     run Sprout - opens the dashboard in your browser
     just           list every command
     just check     your local gate (lint, format, host tests - no compiler needed)
'@
