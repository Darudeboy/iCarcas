# Build Windows portable onedir ZIP (run on Windows).
# Usage (from repo root):
#   .\scripts\build-windows.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  throw "No .venv — create it and pip install -e .[dev] first"
}

& $Py -m pip install -U pip
& $Py -m pip install "pyinstaller>=6.0"

$Dist = Join-Path $Root "dist\windows"
$Build = Join-Path $Root "build\windows"
$Name = "iCarcas"
Remove-Item -Recurse -Force $Dist, $Build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Dist, $Build | Out-Null

$Entry = Join-Path $Root "src\ios_restore\__main__.py"
$Icon = Join-Path $Root "assets\favicon.ico"
$Args = @(
  "-m", "PyInstaller",
  "--noconfirm", "--clean", "--windowed", "--onedir",
  "--name", $Name,
  "--distpath", $Dist,
  "--workpath", $Build,
  "--specpath", $Build,
  "--hidden-import", "PySide6.QtCore",
  "--hidden-import", "PySide6.QtGui",
  "--hidden-import", "PySide6.QtWidgets",
  "--exclude-module", "PySide6.QtWebEngine",
  "--exclude-module", "PySide6.QtWebEngineCore",
  "--exclude-module", "PySide6.QtWebEngineWidgets"
)
if (Test-Path $Icon) { $Args += @("--icon", $Icon) }
$Args += $Entry
& $Py @Args

$AppDir = Join-Path $Dist $Name
foreach ($sub in @("tools\libimobiledevice", "packages", "data", "assets")) {
  New-Item -ItemType Directory -Force -Path (Join-Path $AppDir $sub) | Out-Null
}
if (Test-Path "data\apps_catalog.txt") {
  Copy-Item "data\apps_catalog.txt" (Join-Path $AppDir "data\") -Force
}
if (Test-Path "CHANGELOG.md") { Copy-Item "CHANGELOG.md" $AppDir -Force }
if (Test-Path "docs\client-first-run.md") { Copy-Item "docs\client-first-run.md" $AppDir -Force }
if (Test-Path "assets") { Copy-Item "assets\*" (Join-Path $AppDir "assets\") -Recurse -Force }
foreach ($script in @("download_one.py", "list_versions_dump.py", "list_purchases_dump.py")) {
  $src = Join-Path "tools" $script
  if (Test-Path $src) { Copy-Item $src (Join-Path $AppDir "tools\") -Force }
}

@"
iCarcas for Windows

1) Run iCarcas.exe
2) «Впервые здесь?» — install tools / Apple drivers if needed
3) Cable → Trust → Device → Find → Apple ID → Sign in

See client-first-run.md
"@ | Set-Content -Encoding UTF8 (Join-Path $AppDir "README.txt")

$Zip = Join-Path $Dist "iCarcas-windows.zip"
if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path $AppDir -DestinationPath $Zip -Force
$VerZip = Join-Path $Dist "iCarcas-windows-v$((Get-Content pyproject.toml | Select-String '^version').ToString().Split('"')[1]).zip"
Copy-Item $Zip $VerZip -Force

Write-Host "Done:"
Write-Host "  $AppDir"
Write-Host "  $Zip"
Write-Host "  $VerZip"
