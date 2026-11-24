#!/usr/bin/env bash
# Build iCarcas.app + .dmg on macOS (must run on a Mac / macOS CI РІР‚вЂќ not Windows).
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
  echo "WARN: could not build .icns РІР‚вЂќ continuing without custom icon"
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

# Bundle extras under Contents/Resources, then symlink into MacOS/ so
# project_root() (…/Contents/MacOS) still finds tools/data/assets.
# Sign only AFTER the tree is complete — avoids Gatekeeper
# "a sealed resource is missing or invalid".
RES_DIR="${APP}/Contents/Resources"
mkdir -p "${RES_DIR}/tools/libimobiledevice" "${RES_DIR}/packages" "${RES_DIR}/data"
if [[ -f "${ROOT}/data/apps_catalog.txt" ]]; then
  cp "${ROOT}/data/apps_catalog.txt" "${RES_DIR}/data/"
fi
if [[ -f "${ROOT}/CHANGELOG.md" ]]; then
  cp "${ROOT}/CHANGELOG.md" "${RES_DIR}/"
fi
if [[ -f "${ROOT}/docs/client-first-run.md" ]]; then
  cp "${ROOT}/docs/client-first-run.md" "${RES_DIR}/"
fi
if [[ -d "${ROOT}/assets" ]]; then
  cp -R "${ROOT}/assets" "${RES_DIR}/"
fi

for name in download_one.py list_versions_dump.py list_purchases_dump.py; do
  if [[ -f "${ROOT}/tools/${name}" ]]; then
    cp "${ROOT}/tools/${name}" "${RES_DIR}/tools/"
  fi
done

if [[ "$SKIP_TOOLS" -eq 0 ]]; then
  echo "Fetching ipatool into app bundle ..."
  arch="$(uname -m)"
  if [[ "$arch" == "x86_64" ]]; then arch="amd64"; fi
  name="ipatool-2.8.1-macos-${arch}"
  url="https://github.com/majd/ipatool/releases/download/v2.8.1/${name}.tar.gz"
  archive="${BUILD}/ipatool.tar.gz"
  curl -fsSL "$url" -o "$archive"
  if curl -fsSL "$url.sha256sum" -o "${archive}.sha256sum"; then
    expected="$(awk '{print $1}' "${archive}.sha256sum")"
    printf '%s  %s\n' "$expected" "$archive" | shasum -a 256 -c -
  else
    echo "WARN: could not fetch ipatool sha256sum — continuing without verify"
  fi
  bin="${RES_DIR}/tools/libimobiledevice/ipatool"
  if tar -tzf "$archive" | grep -q "bin/${name}$"; then
    tar -xzOf "$archive" "bin/${name}" > "$bin"
  else
    # Fallback: first file named ipatool in the archive
    TMP="$(mktemp -d)"
    tar -xzf "$archive" -C "$TMP"
    src="$(find "$TMP" -type f -name 'ipatool' | head -n 1)"
    if [[ -z "$src" ]]; then
      echo "ERROR: ipatool not found in archive"
      rm -rf "$TMP"
      exit 1
    fi
    cp "$src" "$bin"
    rm -rf "$TMP"
  fi
  chmod 755 "$bin"
  codesign --force --sign - "$bin" || echo "WARN: codesign ipatool failed"
  echo "OK ipatool"
fi

for name in assets data tools packages CHANGELOG.md client-first-run.md; do
  if [[ -e "${RES_DIR}/${name}" ]]; then
    ln -sfn "../Resources/${name}" "${MACOS_DIR}/${name}"
  fi
done

echo "Ad-hoc codesign…"
codesign --force --sign - "${APP}"
codesign --verify --deep --strict "${APP}"
xattr -cr "${APP}" 2>/dev/null || true

# README for end user inside the DMG folder staging
STAGE="${BUILD}/dmg-stage"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
cat > "${STAGE}/README.txt" <<'EOF'
iCarcas for macOS

1) Drag iCarcas.app to Applications.
2) If macOS says the app is вЂњdamagedвЂќ / cannot be opened (Gatekeeper):
   - Right-click the app в†’ Open в†’ Open
   OR in Terminal:
     xattr -cr /Applications/iCarcas.app
     open /Applications/iCarcas.app
3) Once: brew install libimobiledevice ideviceinstaller
4) Cable в†’ Trust on device в†’ in iCarcas: Device в†’ Find в†’ Apple ID в†’ Sign in

Unsigned build: no Apple Developer notarization yet.
EOF
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
