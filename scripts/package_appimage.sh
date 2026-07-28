#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UI="$ROOT/papertranslate-ui"
TAURI="$UI/src-tauri"
BUNDLE_DIR="$TAURI/target/release/bundle/appimage"
APPDIR="$BUNDLE_DIR/PaperTranslate.AppDir"

APPIMAGETOOL="${APPIMAGETOOL:-$HOME/.cache/tauri/appimagetool-x86_64.AppImage}"
TMPDIR_PATH="${TMPDIR_PATH:-$HOME/.cache/papertranslate-appimage-tmp}"
OUTPUT="$BUNDLE_DIR/PaperTranslate-x86_64.AppImage"

if [[ ! -d "$APPDIR" ]]; then
  echo "ERROR: AppDir not found: $APPDIR" >&2
  exit 1
fi

if [[ ! -x "$APPIMAGETOOL" ]]; then
  echo "ERROR: appimagetool not found or not executable:" >&2
  echo "  $APPIMAGETOOL" >&2
  exit 1
fi

echo "Building frontend..."
cd "$UI"
npm run build

echo "Building production Tauri binary..."
npx tauri build --no-bundle

echo "Installing updated binary into AppDir..."
install -m 755 \
  "$TAURI/target/release/app" \
  "$APPDIR/usr/bin/app"

echo "Pruning optional runtime components..."
"$ROOT/scripts/prune_appimage_runtime.sh" "$APPDIR"

PYTHON="$APPDIR/usr/lib/PaperTranslate/runtime/python/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10"
SITE_PACKAGES="$APPDIR/usr/lib/PaperTranslate/runtime/venv/lib/python3.10/site-packages"

if [[ ! -x "$PYTHON" ]]; then
  echo "ERROR: Bundled Python missing: $PYTHON" >&2
  exit 1
fi

if [[ ! -d "$SITE_PACKAGES" ]]; then
  echo "ERROR: Bundled site-packages missing: $SITE_PACKAGES" >&2
  exit 1
fi

mkdir -p "$TMPDIR_PATH"
rm -f "$OUTPUT"

echo "Creating AppImage..."
ARCH=x86_64 \
TMPDIR="$TMPDIR_PATH" \
"$APPIMAGETOOL" \
  --appimage-extract-and-run \
  "$APPDIR" \
  "$OUTPUT"

chmod +x "$OUTPUT"

echo
echo "AppImage build: PASS"
ls -lh "$OUTPUT"
