#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export DEPLOYMATE_DB_MODE=prod
BUILD_DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/deploymate-build-empty.XXXXXX")"
export DEPLOYMATE_DATA_DIR="$BUILD_DATA_DIR"
trap 'rm -rf "$BUILD_DATA_DIR"' EXIT

echo "[1/5] Checking build dependencies..."
"$PYTHON_BIN" -m PyInstaller --version >/dev/null
"$PYTHON_BIN" -c "from PIL import Image" >/dev/null

echo "[2/5] Creating logo.icns..."
rm -rf build/icon.iconset
mkdir -p build/icon.iconset
for size in 16 32 128 256 512; do
    double=$((size * 2))
    sips -z "$size" "$size" logo.png --out "build/icon.iconset/icon_${size}x${size}.png" >/dev/null
    sips -z "$double" "$double" logo.png --out "build/icon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns build/icon.iconset -o logo.icns

echo "[3/5] Building DeployMate.app..."
echo "Database mode: production (packaged application)"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean deploymate.spec

echo "[4/5] Applying an ad-hoc signature..."
codesign --deep --force --sign - dist/DeployMate.app

case "$(uname -m)" in
    x86_64) ARCH_NAME="intel-x64" ;;
    arm64) ARCH_NAME="arm64" ;;
    *) echo "Unsupported macOS architecture: $(uname -m)" >&2; exit 1 ;;
esac

DMG_PATH="${DMG_PATH:-dist/DeployMate-V1.0-macos-${ARCH_NAME}.dmg}"
echo "[5/5] Creating ${DMG_PATH}..."
rm -f "$DMG_PATH"
DMG_ROOT="build/dmg-root"
rm -rf "$DMG_ROOT"
mkdir -p "$DMG_ROOT"
cp -R dist/DeployMate.app "$DMG_ROOT/DeployMate.app"
ln -s /Applications "$DMG_ROOT/Applications"
hdiutil create -volname DeployMate -srcfolder "$DMG_ROOT" -ov -format UDZO "$DMG_PATH"

echo "Build complete: $(pwd)/$DMG_PATH"
