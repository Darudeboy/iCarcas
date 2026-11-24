#!/usr/bin/env bash
# Build iCarcas.app + .dmg on macOS (must run on a Mac / macOS CI вЂ” not Windows).
#
# Usage (from repo root):
#   ./scripts/build-macos-app.sh
#   ./scripts/build-macos-app.sh --skip-tools
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_TOOLS=0
for arg in "$@"; do
  case "$arg" in
    --skip-tools) SKIP_TOOLS=1 ;;
  esac
done

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: .app / .dmg can only be built on macOS (this host is $(uname -s))."
  echo "Use GitHub Actions workflow 'Build macOS' or a Mac."
  exit 1
fi

PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Creating .venv ..."
  python3 -m venv "${ROOT}/.venv"
  PY="${ROOT}/.venv/bin/python"
fi
"$PY" -m pip install -U pip
"$PY" -m pip install -e "${ROOT}[dev]"
"$PY" -m pip install 'pyinstaller>=6.0'

DIST="${ROOT}/dist"
BUILD="${ROOT}/build/macos"
APP_NAME="iCarcas"
rm -rf "${DIST}/${APP_NAME}.app" "${DIST}/${APP_NAME}"*.dmg "${BUILD}"
mkdir -p "${BUILD}" "${DIST}"

# --- icon .icns from assets/favicon.png ---
ICNS="${BUILD}/iCarcas.icns"
PNG="${ROOT}/assets/favicon.png"
if [[ -f "$PNG" ]] && command -v sips >/dev/null && command -v iconutil >/dev/null; then
  ICONSET="${BUILD}/iCarcas.iconset"
  rm -rf "$ICONSET"
  mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$PNG" --out "${ICONSET}/icon_${size}x${size}.png" >/dev/null
    sips -z $((size * 2)) $((size * 2)) "$PNG" --out "${ICONSET}/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$ICNS"
else
  echo "WARN: could not build .icns вЂ” continuing without custom icon"
  ICNS=""
fi

ENTRY="${ROOT}/src/ios_restore/__main__.py"
RESOURCES="${ROOT}/src/ios_restore/ui/resources"
ADD_DATA=()
if [[ -d "$RESOURCES" ]]; then
  ADD_DATA+=(--add-data "${RESOURCES}:ios_restore/ui/resources")
fi

PI_ARGS=(
  -m PyInstaller
  --noconfirm
  --clean
  --windowed
  --name "$APP_NAME"
  --distpath "$DIST"
  --workpath "$BUILD"
  --specpath "$BUILD"
  --hidden-import PySide6.QtCore
  --hidden-import PySide6.QtGui
  --hidden-import PySide6.QtWidgets
  --collect-submodules PySide6.QtCore
  --collect-submodules PySide6.QtGui
  --collect-submodules PySide6.QtWidgets
  --exclude-module PySide6.QtWebEngine
  --exclude-module PySide6.QtWebEngineCore
  --exclude-module PySide6.QtWebEngineWidgets
  --exclude-module PySide6.QtPdf
  --exclude-module PySide6.QtPdfWidgets
)
if [[ -n "$ICNS" && -f "$ICNS" ]]; then
  PI_ARGS+=(--icon "$ICNS")
fi
for d in "${ADD_DATA[@]:-}"; do
  PI_ARGS+=("$d")
done
PI_ARGS+=("$ENTRY")

echo "Running PyInstaller ..."
"$PY" "${PI_ARGS[@]}"

APP="${DIST}/${APP_NAME}.app"
MACOS_DIR="${APP}/Contents/MacOS"
if [[ ! -d "$APP" ]]; then
  echo "ERROR: ${APP} not found"
  exit 1
fi

# Portable layout next to the binary (paths.project_root() в†’ MacOS/)
mkdir -p "${MACOS_DIR}/tools/libimobiledevice" "${MACOS_DIR}/packages" "${MACOS_DIR}/data"
if [[ -f "${ROOT}/data/apps_catalog.txt" ]]; then
  cp "${ROOT}/data/apps_catalog.txt" "${MACOS_DIR}/data/"
fi
if [[ -f "${ROOT}/CHANGELOG.md" ]]; then
  cp "${ROOT}/CHANGELOG.md" "${MACOS_DIR}/"
fi
if [[ -f "${ROOT}/docs/client-first-run.md" ]]; then
  cp "${ROOT}/docs/client-first-run.md" "${MACOS_DIR}/"
fi
if [[ -d "${ROOT}/assets" ]]; then
  cp -R "${ROOT}/assets" "${MACOS_DIR}/"
fi

for name in download_one.py list_versions_dump.py list_purchases_dump.py; do
  if [[ -f "${ROOT}/tools/${name}" ]]; then
    cp "${ROOT}/tools/${name}" "${MACOS_DIR}/tools/"
  fi
done

if [[ "$SKIP_TOOLS" -eq 0 ]]; then
  echo "Fetching ipatool into app bundle ..."
  ARCH="$(uname -m)"
  if [[ "$ARCH" == "arm64" ]]; then
    URL="https://github.com/majd/ipatool/releases/download/v2.8.1/ipatool-2.8.1-macos-arm64.tar.gz"
  else
    URL="https://github.com/majd/ipatool/releases/download/v2.8.1/ipatool-2.8.1-macos-amd64.tar.gz"
  fi
  TMP="$(mktemp -d)"
  curl -fsSL "$URL" -o "${TMP}/ipatool.tar.gz"
  tar -xzf "${TMP}/ipatool.tar.gz" -C "$TMP"
  BIN="$(find "$TMP" -type f -name 'ipatool' | head -n 1)"
  if [[ -n "$BIN" ]]; then
    cp "$BIN" "${MACOS_DIR}/tools/libimobiledevice/ipatool"
    chmod 755 "${MACOS_DIR}/tools/libimobiledevice/ipatool"
    echo "OK ipatool"
  else
    echo "WARN: ipatool not found in archive"
  fi
  rm -rf "$TMP"
fi

# README for end user inside the DMG folder staging
STAGE="${BUILD}/dmg-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
cat > "${STAGE}/README.txt" <<'EOF'
iCarcas for macOS

1) Open iCarcas.app (if Gatekeeper blocks: right-click в†’ Open в†’ Open).
2) For the phone utilities once:
   brew install libimobiledevice ideviceinstaller
3) Cable в†’ Trust on iPhone в†’ in the app: PhoneвЂ¦ в†’ Find phone в†’ Apple IDвЂ¦ в†’ Sign in.

IPA files are saved next to the app data (packages folder inside the bundle MacOS/ or as prompted).
EOF
# Symlink Applications for convenience
ln -sf /Applications "${STAGE}/Applications"

ARCH_TAG="$(uname -m)"
DMG="${DIST}/iCarcas-macos-${ARCH_TAG}.dmg"
rm -f "$DMG"
hdiutil create \
  -volname "iCarcas" \
  -srcfolder "$STAGE" \
  -ov \
  -format UDZO \
  "$DMG"

# Also copy a stable name
cp "$DMG" "${DIST}/iCarcas-macos.dmg"

echo ""
echo "Done:"
echo "  $APP"
echo "  $DMG"
echo "  ${DIST}/iCarcas-macos.dmg"
echo ""
echo "Note: idevice* still come from Homebrew on the user Mac (PATH)."
