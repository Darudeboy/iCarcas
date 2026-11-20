# Interactive bulk download of owned App Store IPAs by numeric Store IDs.
# Passphrase is typed once in this console (not stored).
#
# Usage:
#   .\bulk-download.ps1 -IdsFile ..\packages\bulk-ids.txt
#   .\bulk-download.ps1 -AppIds 833449999,1497865709

param(
    [string]$IdsFile = '',
    [string]$AppIds = '',
    [switch]$TryPurchase,
    [string]$Passphrase = '',
    [int]$MaxAttempts = 4
)

$ErrorActionPreference = 'Stop'
$ipatool = Join-Path $PSScriptRoot 'libimobiledevice\ipatool.exe'
if (-not (Test-Path $ipatool)) {
    Write-Host "ipatool not found: $ipatool"
    exit 1
}

$ids = New-Object System.Collections.Generic.List[string]
if ($IdsFile -and (Test-Path $IdsFile)) {
    Get-Content -Path $IdsFile -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^\d+$') { $ids.Add($line) }
        elseif ($line -match '(\d{6,})') { $ids.Add($Matches[1]) }
    }
}
if ($AppIds) {
    foreach ($part in ($AppIds -split '[,;\s]+')) {
        $p = $part.Trim()
        if ($p -match '^\d+$') { $ids.Add($p) }
    }
}

$unique = $ids | Select-Object -Unique
if ($unique.Count -eq 0) {
    Write-Host 'No numeric App Store IDs provided.'
    exit 1
}

if (-not $Passphrase) { $Passphrase = $env:IPATOOL_KC_PASS }
$pass = $Passphrase
if ([string]::IsNullOrWhiteSpace($pass)) {
    $pass = Read-Host 'Keychain passphrase (NOT Apple ID password)'
}
if ([string]::IsNullOrWhiteSpace($pass)) {
    Write-Host 'Empty passphrase, abort.'
    exit 1
}

function Test-Retryable([string]$text) {
    $low = $text.ToLowerInvariant()
    return ($low -match 'http 504' -or $low -match 'gateway timeout' -or $low -match 'timeout' -or $low -match 'winhttp')
}

$outDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'packages'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host ("Downloading {0} app(s) into {1}" -f $unique.Count, $outDir)
Write-Host 'Needs a license on this Apple ID for each ID. license is required = skip.'
Write-Host ''

$ok = 0
$fail = 0
$n = 0
foreach ($id in $unique) {
    $n++
    Write-Host ("===== [{0}/{1}] app-id {2} =====" -f $n, $unique.Count, $id)
    $done = $false
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        Write-Host ("  attempt {0}/{1}" -f $attempt, $MaxAttempts)
        $args = @(
            '--non-interactive',
            '--keychain-passphrase', $pass,
            'download',
            '-i', $id,
            '-o', $outDir
        )
        if ($TryPurchase) { $args += '--purchase' }
        $raw = & $ipatool @args 2>&1
        $text = ($raw | Out-String)
        Write-Host $text
        if ($LASTEXITCODE -eq 0 -and ($text -match 'success[=:]?\s*true') -and -not ($text -match 'success[=:]?\s*false')) {
            $ok++
            Write-Host "OK: $id"
            $done = $true
            break
        }
        if (Test-Retryable $text) {
            Start-Sleep -Seconds ([Math]::Min(40, 5 * $attempt))
            continue
        }
        break
    }
    if (-not $done) {
        $fail++
        Write-Host "FAIL: $id"
    }
    Write-Host ''
}

# Rename leftover .ipa.tmp if any
Get-ChildItem -Path $outDir -Filter '*.ipa.tmp' -ErrorAction SilentlyContinue | ForEach-Object {
    $dest = $_.FullName -replace '\.ipa\.tmp$', '.ipa'
    if (Test-Path $dest) { Remove-Item $dest -Force }
    Rename-Item $_.FullName -NewName ([IO.Path]::GetFileName($dest))
}

Write-Host "DONE. ok=$ok fail=$fail"
Write-Host 'Close this window, then click «Подхватить IPA» in iCarcas if needed.'
pause
