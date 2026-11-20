# Verify local ipatool / libimobiledevice binaries for personal portable use.

$ErrorActionPreference = 'Continue'
$root = Split-Path $PSScriptRoot -Parent
$tools = Join-Path $root 'tools\libimobiledevice'

$needed = @(
    'ipatool.exe',
    'idevice_id.exe',
    'ideviceinfo.exe',
    'ideviceinstaller.exe',
    'idevicepair.exe'
)

if (-not (Test-Path $tools)) {
    Write-Host "Нет каталога tools\libimobiledevice"
    Write-Host "Положите Windows-сборку libimobiledevice + ipatool.exe туда."
    exit 1
}

$missing = @()
foreach ($name in $needed) {
    $path = Join-Path $tools $name
    if (Test-Path $path) {
        Write-Host "OK  $name"
    } else {
        Write-Host "НЕТ $name"
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Не хватает: $($missing -join ', ')"
    Write-Host "Скачайте community suite / ipatool и положите exe в:"
    Write-Host "  $tools"
    exit 1
}

Write-Host "Все CLI на месте."
exit 0
