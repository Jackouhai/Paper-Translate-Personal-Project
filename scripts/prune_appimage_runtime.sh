#!/usr/bin/env bash
set -euo pipefail

APPDIR="${1:?Usage: prune_appimage_runtime.sh <PaperTranslate.AppDir>}"
RUNTIME="$APPDIR/usr/lib/PaperTranslate/runtime"
SITE_PACKAGES="$RUNTIME/venv/lib/python3.10/site-packages"

if [[ ! -d "$SITE_PACKAGES" ]]; then
  echo "ERROR: Site-packages not found: $SITE_PACKAGES" >&2
  exit 1
fi

echo "Removing optional NVSHMEM backends..."

rm -f \
  "$SITE_PACKAGES/nvidia/nvshmem/lib/nvshmem_bootstrap_mpi.so."* \
  "$SITE_PACKAGES/nvidia/nvshmem/lib/nvshmem_bootstrap_shmem.so."* \
  "$SITE_PACKAGES/nvidia/nvshmem/lib/nvshmem_transport_libfabric.so."* \
  "$SITE_PACKAGES/nvidia/nvshmem/lib/nvshmem_transport_ucx.so."*

echo "Removing bitsandbytes ROCm backends..."

if [[ -d "$SITE_PACKAGES/bitsandbytes" ]]; then
  find "$SITE_PACKAGES/bitsandbytes" \
    -maxdepth 1 \
    -type f \
    -name 'libbitsandbytes_rocm*.so' \
    -delete
fi

echo "Checking known unsupported dependencies..."

remaining="$(
  find "$RUNTIME" -type f -print0 |
  while IFS= read -r -d '' file; do
    if readelf -d "$file" 2>/dev/null |
       grep -Eq \
         'Shared library: \[(libmpi\.so\.40|liboshmem\.so\.40|libfabric\.so\.1|libucs\.so\.0|libucp\.so\.0|libhipblas\.so\.2)\]'; then
      printf '%s\n' "$file"
    fi
  done
)"

if [[ -n "$remaining" ]]; then
  echo "ERROR: Unsupported dependency references remain:" >&2
  printf '%s\n' "$remaining" >&2
  exit 1
fi

echo "Runtime prune: PASS"
