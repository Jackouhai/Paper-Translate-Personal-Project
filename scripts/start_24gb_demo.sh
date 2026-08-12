#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.24gb"

for argument in "$@"; do
    if [[ "${argument}" == "--help" || "${argument}" == "-h" ]]; then
        exec "${SCRIPT_DIR}/start_vps_demo.sh" "$@" --env-file "${ENV_FILE}"
    fi
done

if [[ ! -f "${ENV_FILE}" ]]; then
    cp "${PROJECT_ROOT}/.env.24gb.example" "${ENV_FILE}"
    echo "created ${ENV_FILE} from .env.24gb.example"
fi

export WEB_FRONTEND_HOST_IP="${WEB_FRONTEND_HOST_IP:-0.0.0.0}"
export WEB_FRONTEND_HOST_PORT="${WEB_FRONTEND_HOST_PORT:-3000}"

exec "${SCRIPT_DIR}/start_vps_demo.sh" "$@" --env-file "${ENV_FILE}"
