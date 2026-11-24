# Dump of ALL ipatool purchases into packages/purchases-dump.json.
# Passphrase: typed interactively, or -Passphrase / env IPATOOL_KC_PASS from iCarcas.

param(
    [string]$Passphrase = ''
)

$ErrorActionPreference = 'Stop'
$ipatool = Join-Path $PSScriptRoot 'libimobiledevice\ipatool.exe'
if (-not (Test-Path $ipatool)) {
    Write-Host "ipatool not found: $ipatool"
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
$outFile = Join-Path $outDir 'purchases-dump.json'

$pageSize = 50
$page = 1
$total = $null
$all = New-Object System.Collections.Generic.List[object]

Write-Host "Fetching purchases (page size $pageSize)..."
while ($true) {
    $raw = & $ipatool --non-interactive --keychain-passphrase $pass --format json list-purchases -l $pageSize -p $page 2>&1
    $text = ($raw | Out-String)
    $jsonLine = ($text -split "`n" | Where-Object { $_.Trim().StartsWith('{') } | Select-Object -Last 1)
    if (-not $jsonLine) {
        Write-Host "Failed to parse page $page"
        Write-Host $text
        exit 1
    }
    try {
        $obj = $jsonLine | ConvertFrom-Json
    } catch {
        Write-Host "JSON parse error on page $page"
        Write-Host $jsonLine
        exit 1
    }
    if ($obj.success -eq $false) {
        Write-Host "Error: $($obj.error)"
        exit 1
    }
    if ($null -eq $total) { $total = [int]$obj.totalCount }
    $apps = @($obj.apps)
    Write-Host ("Page {0}: got {1} apps (total {2})" -f $page, $apps.Count, $total)
    foreach ($a in $apps) { $all.Add($a) }
    if ($apps.Count -eq 0) { break }
    if ($all.Count -ge $total) { break }
    $page++
    if ($page -gt 200) { break }
}

$json = $all | ConvertTo-Json -Depth 6
# UTF-8 without wrong OEM conversion — Cyrillic app names stay readable in iCarcas.
[System.IO.File]::WriteAllText($outFile, $json, (New-Object System.Text.UTF8Encoding $false))
Write-Host ""
Write-Host "Saved $($all.Count) apps to $outFile"
Write-Host "DONE. Then click Podhvatit arhiv in iCarcas."
# Window close is handled by iCarcas (cmd /c + pause).
