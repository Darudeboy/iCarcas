# Download one App Store IPA with retries on HTTP 504 / timeouts.
# Passphrase: -Passphrase or env IPATOOL_KC_PASS (preferred from iCarcas).
# Progress: packages/download-progress.json (polled by iCarcas UI).
#
# Usage:
#   .\download-one.ps1 -AppId 833449999
#   .\download-one.ps1 -BundleId com.example.app -TryPurchase

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

if (-not $OutDir) {
    $OutDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'packages'
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$resultFile = Join-Path $OutDir 'download-result.json'
$progressFile = Join-Path $OutDir 'download-progress.json'
$logFile = Join-Path $OutDir 'download-ipatool.log'

function Write-Result {
    param(
        [bool]$Ok,
        [string]$ErrorText,
        [string]$IpaPath,
        [bool]$Reused = $false,
        [double]$DurationSec = 0,
        [bool]$Fresh = $false
    )
    $obj = [ordered]@{
        success     = $Ok
        error       = $ErrorText
        ipaPath     = $IpaPath
        reused      = $Reused
        fresh       = $Fresh
        durationSec = [math]::Round($DurationSec, 1)
        finishedAt  = (Get-Date).ToString('o')
    }
    $obj | ConvertTo-Json -Depth 4 | Set-Content -Path $resultFile -Encoding UTF8
}

function Write-DlProgress {
    param(
        [string]$Phase,
        [int]$Attempt,
        [long]$Bytes = 0,
        [long]$ExpectedBytes = 0,
        [string]$Message = ''
    )
    $obj = [ordered]@{
        phase         = $Phase
        attempt       = $Attempt
        maxAttempts   = $MaxAttempts
        bytes         = $Bytes
        expectedBytes = $ExpectedBytes
        message       = $Message
        appId         = $AppId
        bundleId      = $BundleId
        updatedAt     = (Get-Date).ToString('o')
    }
    $obj | ConvertTo-Json -Depth 4 | Set-Content -Path $progressFile -Encoding UTF8
}

function Strip-Ansi([string]$text) {
    if ([string]::IsNullOrEmpty($text)) { return '' }
    return [regex]::Replace($text, '\x1b\[[0-9;]*m', '')
}

function Test-Retryable([string]$text) {
    $low = (Strip-Ansi $text).ToLowerInvariant()
    if ($low -match 'http 504' -or $low -match 'gateway timeout') { return $true }
    if ($low -match 'timeout' -or $low -match 'timed out') { return $true }
    if ($low -match 'winhttp' -or $low -match 'connection reset') { return $true }
    if ($low -match 'temporarily unavailable') { return $true }
    return $false
}

function Get-PermanentFailure([string]$text) {
    $low = (Strip-Ansi $text).ToLowerInvariant()
    if ($low -match 'license' -and $low -match 'not found|no license|does not have|not owned|not purchased|missing') {
        return 'Нет лицензии на приложение для текущего Apple ID.'
    }
    if ($low -match 'not available in (your |this )?(country|region|storefront)|not available in the (app )?store|country or region') {
        return 'Приложение недоступно в текущем регионе App Store.'
    }
    if ($low -match 'authentication failed|invalid credentials|session expired|not authenticated|unauthorized|401 unauthorized') {
        return 'Не удалось подтвердить авторизацию Apple ID.'
    }
    return ''
}

function Test-SuccessText([string]$text) {
    $plain = Strip-Ansi $text
    if ($plain -match 'success[=:]?\s*false') { return $false }
    if ($plain -match '"success"\s*:\s*false') { return $false }
    if ($plain -match 'success[=:]?\s*true') { return $true }
    if ($plain -match '"success"\s*:\s*true') { return $true }
    return $false
}

function Get-NewestIpa([string]$dir, [datetime]$after) {
    Get-ChildItem -Path $dir -Filter '*.ipa' -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -ge $after.AddSeconds(-2) -and $_.Length -gt 1024 } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
}

function Get-PartialBytes([string]$dir, [string]$appId) {
    $sum = [int64]0
    Get-ChildItem -Path $dir -Force -ErrorAction SilentlyContinue | ForEach-Object {
        $n = $_.Name
        $isPartial = ($n -like '*.ipa.tmp') -or ($n -like '*.ipa.tmp.*') -or ($n -like '*.ipatool-parts*')
        if (-not $isPartial) { return }
        if ($appId -and ($n -notlike "$appId*")) { return }
        if ($_.PSIsContainer) {
            Get-ChildItem -Path $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
                ForEach-Object { $sum += [int64]$_.Length }
        }
        else {
            $sum += [int64]$_.Length
        }
    }
    return $sum
}

function Get-ExpectedBytes([string]$dir, [string]$appId) {
    if (-not $appId) { return [int64]0 }
    $prev = Get-ChildItem -Path $dir -Filter "$appId*.ipa" -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 1024 } |
        Sort-Object Length -Descending |
        Select-Object -First 1
    if ($prev) { return [int64]$prev.Length }
    return [int64]0
}

function Get-IpaSnapshot([string]$dir) {
    $map = @{}
    Get-ChildItem -Path $dir -Filter '*.ipa' -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 1024 } |
        ForEach-Object { $map[$_.Name] = @{ mtime = $_.LastWriteTimeUtc.Ticks; size = $_.Length } }
    return $map
}

function Test-FreshIpa($file, $snapshot) {
    if (-not $file) { return $false }
    $prev = $snapshot[$file.Name]
    if (-not $prev) { return $true }
    if ($file.Length -ne $prev.size) { return $true }
    if ($file.LastWriteTimeUtc.Ticks -gt ($prev.mtime + 5000000)) { return $true }
    return $false
}

if (-not (Test-Path $ipatool)) {
    Write-Host ("ipatool not found: {0}" -f $ipatool)
    Write-DlProgress -Phase 'failed' -Attempt 0 -Message 'ipatool not found'
    Write-Result -Ok $false -ErrorText 'ipatool not found' -IpaPath ''
    exit 1
}

if (-not $Passphrase) { $Passphrase = $env:IPATOOL_KC_PASS }
if ([string]::IsNullOrWhiteSpace($Passphrase)) {
    $Passphrase = Read-Host 'Keychain passphrase (NOT Apple ID password)'
}
if ([string]::IsNullOrWhiteSpace($Passphrase)) {
    Write-Host 'Empty passphrase, abort.'
    Write-DlProgress -Phase 'failed' -Attempt 0 -Message 'Empty passphrase'
    Write-Result -Ok $false -ErrorText 'empty passphrase' -IpaPath ''
    exit 1
}

if (-not $AppId -and -not $BundleId) {
    Write-Host 'Need -AppId or -BundleId'
    Write-DlProgress -Phase 'failed' -Attempt 0 -Message 'Need AppId or BundleId'
    Write-Result -Ok $false -ErrorText 'missing app id' -IpaPath ''
    exit 1
}

$expected = Get-ExpectedBytes $OutDir $AppId
$snapshot = Get-IpaSnapshot $OutDir
$attempt = 0
$lastOut = ''
$startedAt = Get-Date

Write-DlProgress -Phase 'starting' -Attempt 0 -ExpectedBytes $expected -Message 'Preparing download'
if ($expected -gt 0) {
    Write-Host ("Note: existing IPA ~{0:N1} MB on disk" -f ($expected / 1MB))
}

while ($attempt -lt $MaxAttempts) {
    $attempt++
    Write-Host ("===== download attempt {0}/{1} =====" -f $attempt, $MaxAttempts)
    Write-DlProgress -Phase 'downloading' -Attempt $attempt -Bytes 0 -ExpectedBytes $expected `
        -Message ("Attempt {0}/{1}: starting ipatool" -f $attempt, $MaxAttempts)

    $argList = @(
        '--non-interactive',
        '--keychain-passphrase', $Passphrase,
        'download',
        '-o', $OutDir
    )
    if ($BundleId) { $argList += @('--bundle-identifier', $BundleId) }
    elseif ($AppId) { $argList += @('-i', $AppId) }
    if ($ExternalVersionId) { $argList += @('--external-version-id', $ExternalVersionId) }
    if ($TryPurchase) { $argList += '--purchase' }

    $before = Get-Date
    if (Test-Path $logFile) { Remove-Item $logFile -Force -ErrorAction SilentlyContinue }
    $errFile = "$logFile.err"
    if (Test-Path $errFile) { Remove-Item $errFile -Force -ErrorAction SilentlyContinue }

    $argString = ($argList | ForEach-Object {
            $a = [string]$_
            if ($a -match '[\s"]') { '"' + ($a.Replace('"', '\"')) + '"' } else { $a }
        }) -join ' '

    $proc = Start-Process -FilePath $ipatool `
        -ArgumentList $argString `
        -WorkingDirectory (Split-Path $ipatool -Parent) `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError $errFile `
        -PassThru `
        -WindowStyle Hidden

    if (-not $proc) {
        Write-DlProgress -Phase 'failed' -Attempt $attempt -ExpectedBytes $expected -Message 'Failed to start ipatool'
        Write-Result -Ok $false -ErrorText 'failed to start ipatool' -IpaPath ''
        exit 1
    }

    while (-not $proc.HasExited) {
        $bytes = Get-PartialBytes $OutDir $AppId
        $mb = [math]::Round($bytes / 1MB, 1)
        if ($bytes -gt 0) {
            $msg = ("Attempt {0}/{1}: downloaded {2} MB" -f $attempt, $MaxAttempts, $mb)
        }
        else {
            $msg = ("Attempt {0}/{1}: waiting for Apple data" -f $attempt, $MaxAttempts)
        }
        Write-DlProgress -Phase 'downloading' -Attempt $attempt -Bytes $bytes -ExpectedBytes $expected -Message $msg
        Start-Sleep -Milliseconds 700
        $proc.Refresh()
    }

    $exitCode = $proc.ExitCode
    $stdout = if (Test-Path $logFile) { Get-Content $logFile -Raw -ErrorAction SilentlyContinue } else { '' }
    $stderr = if (Test-Path $errFile) { Get-Content $errFile -Raw -ErrorAction SilentlyContinue } else { '' }
    $lastOut = "$stdout`n$stderr"
    Write-Host (Strip-Ansi $lastOut)

    $ipa = Get-NewestIpa $OutDir $before
    # Never attribute another application's IPA to this download.
    if ($ipa -and $AppId -and $ipa.Name -notlike "${AppId}_*.ipa") {
        $ipa = $null
    }
    if ($ipa -and -not (Test-FreshIpa $ipa $snapshot)) {
        Write-Host ("Ignoring pre-existing IPA (not rewritten): {0}" -f $ipa.Name)
        $ipa = $null
    }
    $path = if ($ipa) { $ipa.FullName } else { '' }
    $finalBytes = if ($ipa) { [int64]$ipa.Length } else { Get-PartialBytes $OutDir $AppId }
    $okText = Test-SuccessText $lastOut
    $duration = ((Get-Date) - $startedAt).TotalSeconds
    $fresh = [bool]$ipa

    if (($exitCode -eq 0 -and $okText) -or ($okText -and $path) -or ($exitCode -eq 0 -and $path)) {
        if (-not $path) {
            $existing = $null
            if ($AppId) {
                $existing = Get-ChildItem -Path $OutDir -Filter "$AppId*.ipa" -ErrorAction SilentlyContinue |
                    Where-Object { $_.Length -gt 1024 } |
                    Sort-Object LastWriteTime -Descending |
                    Select-Object -First 1
            }
            if ($existing) {
                $path = $existing.FullName
                $finalBytes = [int64]$existing.Length
                $msg = ("File already on disk ({0:N1} MB), not re-downloaded from Apple" -f ($finalBytes / 1MB))
                Write-DlProgress -Phase 'done' -Attempt $attempt -Bytes $finalBytes -ExpectedBytes $expected -Message $msg
                Write-Result -Ok $true -ErrorText '' -IpaPath $path -Reused $true -DurationSec $duration -Fresh $false
                Write-Host ("DONE reused existing ipa={0} duration={1}s" -f $path, $duration)
                exit 0
            }
        }
        if (-not $expected -and $finalBytes -gt 0) { $expected = $finalBytes }
        $speed = if ($duration -gt 1 -and $finalBytes -gt 0) { $finalBytes / 1MB / $duration } else { 0 }
        if ($fresh) {
            $msg = ("Downloaded {0} in {1:N0}s ({2:N1} MB/s)" -f (Split-Path $path -Leaf), $duration, $speed)
        }
        else {
            $msg = 'Done'
        }
        Write-DlProgress -Phase 'done' -Attempt $attempt -Bytes $finalBytes -ExpectedBytes $expected -Message $msg
        Write-Result -Ok $true -ErrorText '' -IpaPath $path -Reused (-not $fresh) -DurationSec $duration -Fresh $fresh
        Write-Host ("DONE success attempt={0} ipa={1} fresh={2} duration={3}s" -f $attempt, $path, $fresh, $duration)
        exit 0
    }

    # Permanent Apple responses win over incidental network errors in the same log.
    $permanentFailure = Get-PermanentFailure $lastOut
    if ($permanentFailure) {
        Write-Host ("Permanent failure: {0}" -f $permanentFailure)
        Write-DlProgress -Phase 'failed' -Attempt $attempt -ExpectedBytes $expected -Message $permanentFailure
        Write-Result -Ok $false -ErrorText $permanentFailure -IpaPath '' -DurationSec $duration -Fresh $false
        exit 1
    }

    if (Test-Retryable $lastOut) {
        $delay = [Math]::Min(60, 5 * $attempt)
        Write-Host ("Retryable error (504/timeout). Sleep {0}s..." -f $delay)
        $left = $delay
        while ($left -gt 0) {
            Write-DlProgress -Phase 'retry_wait' -Attempt $attempt -Bytes $finalBytes -ExpectedBytes $expected `
                -Message ("Network/504 error. Retry in {0}s" -f $left)
            Start-Sleep -Seconds 1
            $left--
        }
        continue
    }

    Write-Host ("Non-retryable failure (exit={0})." -f $exitCode)
    break
}

$duration = ((Get-Date) - $startedAt).TotalSeconds
Write-DlProgress -Phase 'failed' -Attempt $attempt -ExpectedBytes $expected -Message 'Download failed'
Write-Result -Ok $false -ErrorText (Strip-Ansi $lastOut) -IpaPath '' -DurationSec $duration -Fresh $false
Write-Host ("DONE failed after {0} attempt(s)" -f $attempt)
exit 1
