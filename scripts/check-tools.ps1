# Check that ipatool / libimobiledevice are present for iCarcas.

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
    Write-Host "These tools are NOT in git. Do this:"
    Write-Host "1) Download libimobiledevice suite, unpack into:"
    Write-Host "   $tools"
    Write-Host "   https://github.com/L1ghtmann/libimobiledevice/releases/tag/suite-exe-21d57a9"
    Write-Host "2) Put ipatool.exe there too:"
    Write-Host "   https://github.com/majd/ipatool/releases"
    Write-Host "3) Install Apple drivers:"
    Write-Host "   winget install --id Apple.AppleMobileDeviceSupport -e"
    Write-Host "See README.md"
}

if (-not (Test-Path $tools)) {
    Write-Host "Missing folder: tools\libimobiledevice"
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
    Write-Host "Warning: Apple Mobile Device Service is $($amds.Status) (need Running)."
} else {
    Write-Host "OK  Apple Mobile Device Service"
}

exit 0