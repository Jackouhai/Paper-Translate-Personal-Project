#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

export WEB_FRONTEND_HOST_IP="${WEB_FRONTEND_HOST_IP:-127.0.0.1}"
export WEB_FRONTEND_HOST_PORT="${WEB_FRONTEND_HOST_PORT:-3100}"

exec "${SCRIPT_DIR}/start_vps_demo.sh" "$@" --local
