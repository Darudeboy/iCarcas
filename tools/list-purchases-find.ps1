# Interactive dump of ipatool purchases; filter Sber / Zvuk candidates.
# Passphrase is asked once in this console and not written to disk.

$ErrorActionPreference = 'Stop'
$ipatool = Join-Path $PSScriptRoot 'libimobiledevice\ipatool.exe'
if (-not (Test-Path $ipatool)) {
    Write-Host "ipatool not found: $ipatool"
    exit 1
}

$pass = Read-Host 'Keychain passphrase (NOT Apple ID password)'
if ([string]::IsNullOrWhiteSpace($pass)) {
    Write-Host 'Empty passphrase, abort.'
    exit 1
}

$outDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'packages'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$outFile = Join-Path $outDir 'purchases-all.jsonl'
Remove-Item $outFile -ErrorAction SilentlyContinue

$pageSize = 50
$page = 1
$total = $null
$all = New-Object System.Collections.Generic.List[object]

Write-Host "Fetching purchases (page size $pageSize)..."
while ($true) {
    $raw = & $ipatool --non-interactive --keychain-passphrase $pass --format json list-purchases -l $pageSize -p $page 2>&1
    $text = ($raw | Out-String)
    # Prefer last JSON object in output
    $jsonLine = ($text -split "`n" | Where-Object { $_.Trim().StartsWith('{') } | Select-Object -Last 1)
    if (-not $jsonLine) {
        Write-Host "Failed to parse page $page"
        Write-Host $text
        break
    }
    try {
        $obj = $jsonLine | ConvertFrom-Json
    } catch {
        Write-Host "JSON parse error on page $page"
        Write-Host $jsonLine
        break
    }
    if ($obj.success -eq $false) {
        Write-Host "Error: $($obj.error)"
        break
    }
    if ($null -eq $total) { $total = [int]$obj.totalCount }
    $apps = @($obj.apps)
    Write-Host ("Page {0}: got {1} apps (total {2})" -f $page, $apps.Count, $total)
    foreach ($a in $apps) {
        $all.Add($a)
        ($a | ConvertTo-Json -Compress) | Add-Content -Path $outFile -Encoding UTF8
    }
    if ($apps.Count -eq 0) { break }
    if ($all.Count -ge $total) { break }
    $page++
    if ($page -gt 200) { break }
}

Write-Host ""
Write-Host "Saved $(($all).Count) apps to $outFile"
Write-Host ""
Write-Host "=== Matches: Sber / SBOL / Online / Zvuk / Zvooq ==="
$rx = 'сбер|sber|sbol|онлайн|online|звук|zvuk|zvooq|финанс|бюджет|актив|семейный|учёт|умный'
$hits = $all | Where-Object {
    ("$($_.name) $($_.bundleID)" -match $rx)
}
if (-not $hits -or $hits.Count -eq 0) {
    Write-Host 'No matches in purchase history for those keywords.'
    Write-Host 'Sber/Zvuk were likely never downloaded on THIS Apple ID, or under a very different name.'
} else {
    $hits | ForEach-Object {
        Write-Host ("id={0}  bundle={1}  name={2}  ver={3}" -f $_.id, $_.bundleID, $_.name, $_.version)
    }
}

Write-Host ""
Write-Host 'DONE. You can close this window.'
pause
