# Personal portable launcher for iCarcas (Windows).
# Usage (from repo root):  .\scripts\run-icarcas.ps1
# Optional: .\scripts\run-icarcas.ps1 -Light

param(
    [switch]$Light,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$venvPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host 'Creating .venv ...'
    py -3.13 -m venv .venv
    if (-not (Test-Path $venvPython)) {
        python -m venv .venv
    }
}

if (-not $SkipInstall) {
    Write-Host 'Ensuring package install ...'
    & $venvPython -m pip install -U pip
    & $venvPython -m pip install -e '.[dev]'
}

Write-Host 'Checking tools ...'
& (Join-Path $PSScriptRoot 'check-tools.ps1')

$argsList = @('-m', 'ios_restore')
if ($Light) { $argsList += '--light' }
Write-Host 'Starting iCarcas ...'
& $venvPython @argsList
