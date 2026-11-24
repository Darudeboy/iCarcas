# Create Desktop shortcut to iCarcas.exe next to this script's parent (portable folder).
# Usage (from unpacked ZIP):
#   .\scripts\create-desktop-shortcut.ps1
# Or double-click «Ярлык на рабочий стол.bat» if present.

param(
    [string]$ExePath = ''
)

$ErrorActionPreference = 'Stop'

if (-not $ExePath) {
    $root = Split-Path $PSScriptRoot -Parent
    $candidate = Join-Path $root 'iCarcas.exe'
    if (-not (Test-Path $candidate)) {
        $candidate = Join-Path (Get-Location) 'iCarcas.exe'
    }
    $ExePath = $candidate
}

if (-not (Test-Path $ExePath)) {
    Write-Host "iCarcas.exe not found: $ExePath"
    exit 1
}

$exe = (Resolve-Path $ExePath).Path
$workdir = Split-Path $exe -Parent
$desktop = [Environment]::GetFolderPath('Desktop')
$linkPath = Join-Path $desktop 'iCarcas.lnk'
$icon = Join-Path $workdir 'assets\favicon.ico'
if (-not (Test-Path $icon)) { $icon = $exe }

$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($linkPath)
$s.TargetPath = $exe
$s.WorkingDirectory = $workdir
$s.IconLocation = $icon
$s.Description = 'iCarcas — свои приложения на iPhone'
$s.Save()

Write-Host "Shortcut created: $linkPath"
