#!/usr/bin/env bash
# Download ipatool into tools/libimobiledevice for macOS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/tools/libimobiledevice"
mkdir -p "$OUT"

ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  URL="https://github.com/majd/ipatool/releases/download/v2.8.1/ipatool-2.8.1-macos-arm64.tar.gz"
else
  URL="https://github.com/majd/ipatool/releases/download/v2.8.1/ipatool-2.8.1-macos-amd64.tar.gz"
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "$URL" -o "$TMP/ipatool.tar.gz"
tar -xzf "$TMP/ipatool.tar.gz" -C "$TMP"
BIN="$(find "$TMP" -type f -name 'ipatool' | head -n 1)"
if [[ -z "$BIN" ]]; then
  echo "ipatool binary not found in archive"
  exit 1
fi
cp "$BIN" "$OUT/ipatool"
chmod 755 "$OUT/ipatool"
echo "OK $OUT/ipatool"

echo "Device CLI: brew install libimobiledevice ideviceinstaller"
