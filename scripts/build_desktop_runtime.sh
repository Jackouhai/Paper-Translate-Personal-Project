#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
)"

RUNTIME_DIR="$PROJECT_ROOT/desktop-runtime"
PYTHON_INSTALL_DIR="$RUNTIME_DIR/python"
VENV_DIR="$RUNTIME_DIR/venv"
REQUIREMENTS_FILE="$RUNTIME_DIR/requirements.txt"

PYTHON_VERSION="3.10.20"
PYTHON_DIST="cpython-3.10.20-linux-x86_64-gnu"

export UV_HTTP_TIMEOUT="${UV_HTTP_TIMEOUT:-300}"
export UV_HTTP_RETRIES="${UV_HTTP_RETRIES:-10}"

echo "Project root: $PROJECT_ROOT"
echo "Runtime directory: $RUNTIME_DIR"
echo "Python version: $PYTHON_VERSION"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv was not found in PATH." >&2
  exit 1
fi

echo
echo "==> Removing the previous runtime"

rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR"

echo
echo "==> Installing managed Python $PYTHON_VERSION"

uv python install "$PYTHON_VERSION" \
  --install-dir "$PYTHON_INSTALL_DIR" \
  --no-bin

RUNTIME_BASE_PYTHON="$(
  find "$PYTHON_INSTALL_DIR" \
    -path "*/bin/python3.10" \
    -type f \
    -print \
    -quit
)"

if [[ -z "$RUNTIME_BASE_PYTHON" ]]; then
  echo "ERROR: Managed Python executable was not found." >&2
  exit 1
fi

echo "Managed Python: $RUNTIME_BASE_PYTHON"

echo
echo "==> Creating relocatable virtual environment"

uv venv "$VENV_DIR" \
  --python "$RUNTIME_BASE_PYTHON" \
  --relocatable \
  --seed

echo
echo "==> Repairing relative Python symlinks"

rm -f \
  "$VENV_DIR/bin/python" \
  "$VENV_DIR/bin/python3" \
  "$VENV_DIR/bin/python3.10"

ln -s \
  "../../python/$PYTHON_DIST/bin/python3.10" \
  "$VENV_DIR/bin/python"

ln -s python "$VENV_DIR/bin/python3"
ln -s python "$VENV_DIR/bin/python3.10"

MANAGED_ALIAS="$PYTHON_INSTALL_DIR/cpython-3.10-linux-x86_64-gnu"

rm -f "$MANAGED_ALIAS"

ln -s \
  "$PYTHON_DIST" \
  "$MANAGED_ALIAS"

VENV_PYTHON="$VENV_DIR/bin/python"

"$VENV_PYTHON" --version

echo
echo "==> Exporting locked production dependencies"

cd "$PROJECT_ROOT"

uv export \
  --frozen \
  --no-dev \
  --no-emit-project \
  --format requirements-txt \
  --output-file "$REQUIREMENTS_FILE"

echo
echo "==> Installing locked dependencies"

uv pip sync \
  --python "$VENV_PYTHON" \
  "$REQUIREMENTS_FILE"

echo
echo "==> Installing PaperTranslate package"

uv pip install \
  --python "$VENV_PYTHON" \
  --no-deps \
  "$PROJECT_ROOT"

echo
echo "==> Verifying runtime imports"

"$VENV_PYTHON" - <<'PY'
import fastapi
import paddle
import paddleocr
import paddlex
import pp_doclayout
import torch
import uvicorn
import vllm

print("fastapi: OK")
print("uvicorn: OK")
print("paddle:", paddle.__version__)
print("paddleocr: OK")
print("paddlex:", paddlex.__version__)
print("torch:", torch.__version__)
print("vllm:", vllm.__version__)
print("pp_doclayout: OK")
PY

echo
echo "==> Verifying PaddleX OCR dependencies"

"$VENV_PYTHON" - <<'PY'
from paddlex.utils.deps import require_extra

require_extra("ocr", obj_name="PaddleOCR-VL-1.5")
print("paddlex[ocr]: OK")
PY

echo
echo "==> Runtime size"

du -sh "$RUNTIME_DIR"

echo
echo "Desktop runtime build completed successfully."
