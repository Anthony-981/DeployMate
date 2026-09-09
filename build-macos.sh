#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "[1/4] Checking build dependencies..."
"$PYTHON_BIN" -m PyInstaller --version >/dev/null
"$PYTHON_BIN" -c "from PIL import Image" >/dev/null

echo "[2/4] Creating logo.icns..."
rm -rf build/icon.iconset
mkdir -p build/icon.iconset
for size in 16 32 128 256 512; do
    double=$((size * 2))
    sips -z "$size" "$size" logo.png --out "build/icon.iconset/icon_${size}x${size}.png" >/dev/null
    sips -z "$double" "$double" logo.png --out "build/icon.iconset/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns build/icon.iconset -o logo.icns

echo "[3/4] Building DeployMate.app..."
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean deploymate.spec

echo "[4/4] Build complete: $(pwd)/dist/DeployMate.app"
