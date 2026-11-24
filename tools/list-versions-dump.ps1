# Interactive dump of ipatool list-versions (+ optional metadata) for one app.
# Passphrase is typed in this console only (not stored).
#
# Usage:
#   .\list-versions-dump.ps1 -AppId 833449999
#   .\list-versions-dump.ps1 -AppId 833449999 -EnrichLimit 40

param(
    [Parameter(Mandatory = $true)]
    [string]$AppId,
    [int]$EnrichLimit = 40,
    [string]$Passphrase = ''
)

$ErrorActionPreference = 'Stop'
$ipatool = Join-Path $PSScriptRoot 'libimobiledevice\ipatool.exe'
if (-not (Test-Path $ipatool)) {
    Write-Host "ipatool not found: $ipatool"
    exit 1
}

if ($AppId -notmatch '^\d+$') {
    Write-Host "AppId must be a numeric Store ID, got: $AppId"
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

$outDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'packages'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = Join-Path $outDir ("versions-{0}.json" -f $AppId)

Write-Host "Fetching version IDs for app $AppId..."
$raw = & $ipatool --non-interactive --keychain-passphrase $pass --format json list-versions -i $AppId 2>&1
$text = ($raw | Out-String)
$jsonLine = ($text -split "`n" | Where-Object { $_.Trim().StartsWith('{') } | Select-Object -Last 1)
if (-not $jsonLine) {
    Write-Host "Failed to parse list-versions output"
    Write-Host $text
    exit 1
}

try {
    $obj = $jsonLine | ConvertFrom-Json
} catch {
    Write-Host "JSON parse error"
    Write-Host $jsonLine
    exit 1
}

if ($obj.success -eq $false) {
    Write-Host "Error: $($obj.error)"
    exit 1
}

$ids = @($obj.externalVersionIdentifiers)
# Newest first (IDs are roughly chronological numeric strings).
$ids = $ids | Sort-Object { [long]$_ } -Descending
Write-Host ("Got {0} version IDs (newest first)." -f $ids.Count)

$versions = New-Object System.Collections.Generic.List[object]
$toEnrich = [Math]::Min($EnrichLimit, $ids.Count)
Write-Host ("Enriching metadata for first {0} (get-version-metadata)..." -f $toEnrich)

for ($i = 0; $i -lt $ids.Count; $i++) {
    $vid = [string]$ids[$i]
    $entry = [ordered]@{
        externalVersionId = $vid
        displayVersion    = $null
        releaseDate       = $null
    }
    if ($i -lt $toEnrich) {
        $mraw = & $ipatool --non-interactive --keychain-passphrase $pass --format json get-version-metadata -i $AppId --external-version-id $vid 2>&1
        $mtext = ($mraw | Out-String)
        $mline = ($mtext -split "`n" | Where-Object { $_.Trim().StartsWith('{') } | Select-Object -Last 1)
        if ($mline) {
            try {
                $meta = $mline | ConvertFrom-Json
                if ($meta.displayVersion) { $entry.displayVersion = [string]$meta.displayVersion }
                if ($meta.releaseDate) { $entry.releaseDate = [string]$meta.releaseDate }
            } catch {
                # keep nulls
            }
        }
        if ((($i + 1) % 5) -eq 0 -or ($i + 1) -eq $toEnrich) {
            Write-Host ("  metadata {0}/{1}" -f ($i + 1), $toEnrich)
        }
    }
    $versions.Add([pscustomobject]$entry)
}

$result = [ordered]@{
    success                 = $true
    appId                   = $AppId
    bundleID                = $obj.bundleID
    enrichedCount           = $toEnrich
    externalVersionIdentifiers = @($ids)
    versions                = @($versions)
}
$result | ConvertTo-Json -Depth 6 | Set-Content -Path $outFile -Encoding UTF8

Write-Host ""
Write-Host "Saved $($versions.Count) versions to $outFile"
Write-Host "DONE. Then click Podhvatit versii in iCarcas."
# Window close is handled by iCarcas (cmd /c + pause).
