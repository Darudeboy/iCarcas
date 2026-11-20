# Download one App Store IPA with retries on HTTP 504 / timeouts.
# Passphrase: -Passphrase or env IPATOOL_KC_PASS (preferred from iCarcas).
#
# Usage:
#   .\download-one.ps1 -AppId 833449999
#   .\download-one.ps1 -BundleId com.example.app -TryPurchase
#   .\download-one.ps1 -AppId 833449999 -ExternalVersionId 123 -MaxAttempts 5

param(
    [string]$AppId = '',
    [string]$BundleId = '',
    [string]$ExternalVersionId = '',
    [switch]$TryPurchase,
    [int]$MaxAttempts = 5,
    [string]$Passphrase = '',
    [string]$OutDir = ''
)

$ErrorActionPreference = 'Continue'
$ipatool = Join-Path $PSScriptRoot 'libimobiledevice\ipatool.exe'
if (-not (Test-Path $ipatool)) {
    Write-Host "ipatool not found: $ipatool"
    exit 1
}

if (-not $Passphrase) { $Passphrase = $env:IPATOOL_KC_PASS }
if ([string]::IsNullOrWhiteSpace($Passphrase)) {
    $Passphrase = Read-Host 'Keychain passphrase (NOT Apple ID password)'
}
if ([string]::IsNullOrWhiteSpace($Passphrase)) {
    Write-Host 'Empty passphrase, abort.'
    exit 1
}

if (-not $OutDir) {
    $OutDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'packages'
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$resultFile = Join-Path $OutDir 'download-result.json'

function Write-Result([bool]$ok, [string]$errorText, [string]$ipaPath) {
    $obj = [ordered]@{
        success   = $ok
        error     = $errorText
        ipaPath   = $ipaPath
        finishedAt = (Get-Date).ToString('o')
    }
    $obj | ConvertTo-Json -Depth 4 | Set-Content -Path $resultFile -Encoding UTF8
}

function Test-Retryable([string]$text) {
    $low = $text.ToLowerInvariant()
    if ($low -match 'http 504' -or $low -match 'gateway timeout') { return $true }
    if ($low -match 'timeout' -or $low -match 'timed out') { return $true }
    if ($low -match 'winhttp' -or $low -match 'connection reset') { return $true }
    if ($low -match 'temporarily unavailable') { return $true }
    return $false
}

if (-not $AppId -and -not $BundleId) {
    Write-Host 'Need -AppId or -BundleId'
    Write-Result $false 'missing app id' ''
    exit 1
}

$attempt = 0
$lastOut = ''
while ($attempt -lt $MaxAttempts) {
    $attempt++
    Write-Host ("===== download attempt {0}/{1} =====" -f $attempt, $MaxAttempts)

    $args = @(
        '--non-interactive',
        '--keychain-passphrase', $Passphrase,
        'download',
        '-o', $OutDir
    )
    if ($BundleId) { $args += @('--bundle-identifier', $BundleId) }
    elseif ($AppId) { $args += @('-i', $AppId) }
    if ($ExternalVersionId) { $args += @('--external-version-id', $ExternalVersionId) }
    if ($TryPurchase) { $args += '--purchase' }

    $raw = & $ipatool @args 2>&1
    $lastOut = ($raw | Out-String)
    Write-Host $lastOut

    $okLine = ($lastOut -split "`n" | Where-Object { $_.Trim() -match 'success[=:]?\s*true' -or $_.Trim() -match '"success"\s*:\s*true' } | Select-Object -Last 1)
    $errLine = ($lastOut -split "`n" | Where-Object { $_.Trim() -match 'success[=:]?\s*false' -or $_.Trim() -match '"success"\s*:\s*false' -or $_.Trim().StartsWith('ERR') } | Select-Object -Last 1)

    if ($LASTEXITCODE -eq 0 -and $okLine -and -not ($lastOut -match 'success[=:]?\s*false')) {
        $ipa = Get-ChildItem -Path $OutDir -Filter '*.ipa' -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        $path = if ($ipa) { $ipa.FullName } else { '' }
        Write-Result $true '' $path
        Write-Host "DONE success attempt=$attempt"
        exit 0
    }

    if (Test-Retryable $lastOut) {
        $delay = [Math]::Min(60, 5 * $attempt)
        Write-Host ("Retryable error (504/timeout). Sleep {0}s..." -f $delay)
        Start-Sleep -Seconds $delay
        continue
    }

    Write-Host 'Non-retryable failure.'
    break
}

Write-Result $false $lastOut ''
Write-Host "DONE failed after $attempt attempt(s)"
exit 1
