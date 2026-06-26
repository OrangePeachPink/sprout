<#
  Install-SproutShortcut.ps1 - put a branded "Sprout" shortcut on your Desktop that
  double-click-launches the app with no terminal. Run once (re-run any time to refresh):

      pwsh tools\launch\Install-SproutShortcut.ps1

  It only creates/updates the one shortcut; it removes nothing else. The shortcut
  launches sprout.cmd minimized, so Sprout starts without a terminal in your face.
#>
[CmdletBinding()]
param(
  # Where to drop the shortcut (default: your Desktop). Handy for testing elsewhere.
  [string]$DestinationDir = [Environment]::GetFolderPath('Desktop')
)
$ErrorActionPreference = 'Stop'

$repo   = (Resolve-Path "$PSScriptRoot\..\..").Path
$target = Join-Path $repo 'tools\launch\sprout.cmd'
$icon   = Join-Path $repo 'tools\launch\sprout.ico'
$link   = Join-Path $DestinationDir 'Sprout.lnk'

if (-not (Test-Path $target)) { throw "launcher not found: $target" }

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($link)
$sc.TargetPath       = $target
$sc.WorkingDirectory = $repo
$sc.WindowStyle      = 7      # 7 = minimized: starts without a terminal in your face
$sc.Description      = 'Start Sprout - opens the dashboard in your browser'
if (Test-Path $icon) { $sc.IconLocation = "$icon,0" }
$sc.Save()

Write-Host "Created shortcut: $link"
Write-Host "  -> $target"
if (-not (Test-Path $icon)) {
  Write-Warning "No sprout.ico yet - the shortcut uses the default icon. Drop a sprout.ico in tools\launch\ and re-run."
}
Write-Host "Double-click 'Sprout' to launch. Stop it from the dashboard's Stop button."
