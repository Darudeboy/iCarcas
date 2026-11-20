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

function Write-SetupHints {
    Write-Host ""
    Write-Host "These files are NOT in git clone (tools/libimobiledevice is gitignored)."
    Write-Host "1) libimobiledevice Windows suite:"
    Write-Host "   https://github.com/L1ghtmann/libimobiledevice/releases/tag/suite-exe-21d57a9"
    Write-Host "   Unpack exe+dll into: $tools"
    Write-Host "2) ipatool (Windows amd64) as $tools\ipatool.exe"
    Write-Host "   https://github.com/majd/ipatool/releases"
    Write-Host "3) Windows: Apple Mobile Device Support"
    Write-Host "   winget install --id Apple.AppleMobileDeviceSupport -e"
    Write-Host "See docs\setup.md and README.md"
}

if (-not (Test-Path $tools)) {
    Write-Host "Missing directory tools\libimobiledevice"
    Write-SetupHints
    exit 1
}

$missing = @()
foreach ($name in $needed) {
    $path = Join-Path $tools $name
    if (Test-Path $path) {
        Write-Host "OK  $name"
    } else {
        Write-Host "MISSING $name"
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Missing: $($missing -join ', ')"
    Write-SetupHints
    exit 1
}

Write-Host "All CLI tools present."

$amds = Get-Service -Name 'Apple Mobile Device Service' -ErrorAction SilentlyContinue
if ($null -eq $amds) {
    Write-Host "Warning: Apple Mobile Device Service not found."
    Write-Host "Install: winget install --id Apple.AppleMobileDeviceSupport -e"
} elseif ($amds.Status -ne 'Running') {
    Write-Host "Warning: Apple Mobile Device Service status=$($amds.Status) (expected Running)."
} else {
    Write-Host "OK  Apple Mobile Device Service"
}

exit 0