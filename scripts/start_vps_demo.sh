#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.vps"
USE_ENV_FILE=0
BUILD_IMAGES=1
START_TUNNEL=1
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-1200}"
WEB_FRONTEND_HOST_PORT="${WEB_FRONTEND_HOST_PORT:-3000}"

usage() {
    cat <<'EOF'
Usage: scripts/start_vps_demo.sh [--local|--vps|--env-file FILE] [--skip-build] [--no-tunnel]

Starts the demo in this order:
  1. Verify Docker can access the NVIDIA GPU
  2. TranslateGemma
  3. PaddleOCR-VL
  4. Parse API, web API, and frontend
  5. Cloudflare Quick Tunnel (unless --no-tunnel is supplied)

By default, Compose uses the local .env file and compose.yaml defaults.
Use --vps for the RTX 3060 12 GB profile, or --env-file FILE for another profile.
EOF
}

while (( $# > 0 )); do
    case "$1" in
        --local)
            USE_ENV_FILE=0
            shift
            ;;
        --vps)
            ENV_FILE="${PROJECT_ROOT}/.env.vps"
            USE_ENV_FILE=1
            shift
            ;;
        --env-file)
            if [[ $# -lt 2 ]]; then
                echo "error: --env-file requires a path" >&2
                usage >&2
                exit 2
            fi
            ENV_FILE="$2"
            if [[ "${ENV_FILE}" != /* ]]; then
                ENV_FILE="${PROJECT_ROOT}/${ENV_FILE}"
            fi
            USE_ENV_FILE=1
            shift 2
            ;;
        --skip-build)
            BUILD_IMAGES=0
            shift
            ;;
        --no-tunnel)
            START_TUNNEL=0
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

for command in docker curl; do
    if ! command -v "${command}" >/dev/null 2>&1; then
        echo "error: required command not found: ${command}" >&2
        exit 1
    fi
done

cd "${PROJECT_ROOT}"

if (( USE_ENV_FILE )) && [[ ! -f "${ENV_FILE}" ]]; then
    cp .env.vps.example "${ENV_FILE}"
    echo "created ${ENV_FILE} from .env.vps.example"
fi

compose() {
    if (( USE_ENV_FILE )); then
        docker compose --env-file "${ENV_FILE}" "$@"
    else
        docker compose "$@"
    fi
}

check_docker_gpu() {
    echo "==> Verifying Docker GPU access"
    if ! docker run --rm --gpus all \
        nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 nvidia-smi; then
        cat >&2 <<'EOF'
error: Docker cannot access the NVIDIA GPU.
Check host `nvidia-smi`, then verify NVIDIA Container Toolkit and Docker runtime
configuration before starting model containers.
EOF
        exit 1
    fi
}

wait_for_service_health() {
    local name="$1"
    local service="$2"
    local started_at
    local container_id
    local status
    started_at="$(date +%s)"

    until container_id="$(compose ps -q "${service}")" \
        && [[ -n "${container_id}" ]] \
        && status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}" 2>/dev/null)" \
        && [[ "${status}" == "healthy" ]]; do
        if (( $(date +%s) - started_at >= HEALTH_TIMEOUT_SECONDS )); then
            echo "error: ${name} did not become ready within ${HEALTH_TIMEOUT_SECONDS}s" >&2
            compose logs --tail=120 "${service}" >&2 || true
            exit 1
        fi

        echo "waiting for ${name}..."
        sleep 10
    done

    echo "${name} is ready"
}

wait_for_endpoint() {
    local name="$1"
    local endpoint="$2"
    local service="$3"
    local started_at
    started_at="$(date +%s)"

    until curl --fail --silent --show-error --connect-timeout 5 "${endpoint}" >/dev/null; do
        if (( $(date +%s) - started_at >= HEALTH_TIMEOUT_SECONDS )); then
            echo "error: ${name} did not become ready within ${HEALTH_TIMEOUT_SECONDS}s" >&2
            compose logs --tail=120 "${service}" >&2 || true
            exit 1
        fi

        echo "waiting for ${name}..."
        sleep 10
    done

    echo "${name} is ready"
}

check_docker_gpu

if (( BUILD_IMAGES )); then
    echo "==> Building Docker images"
    compose build
fi

echo "==> Starting TranslateGemma"
compose up -d translate-gemma
wait_for_service_health "TranslateGemma" "translate-gemma"

echo "==> Starting PaddleOCR-VL"
compose up -d paddle-ocr-vl
wait_for_service_health "PaddleOCR-VL" "paddle-ocr-vl"

echo "==> Starting Parse API and browser demo"
compose up -d parse-api
wait_for_service_health "Parse API" "parse-api"
compose up -d web-api web-frontend
wait_for_service_health "Web API" "web-api"
wait_for_endpoint "Web frontend" "http://127.0.0.1:${WEB_FRONTEND_HOST_PORT}" "web-frontend"

if (( START_TUNNEL )); then
    echo "==> Starting Cloudflare Quick Tunnel"
    compose --profile tunnel up -d cloudflared

    tunnel_url=""
    for _ in {1..30}; do
        tunnel_url="$(compose logs --no-log-prefix --tail=80 cloudflared 2>/dev/null \
            | sed -nE 's#.*(https://[-a-z0-9]+\.trycloudflare\.com).*#\1#p' \
            | tail -n 1)"
        [[ -n "${tunnel_url}" ]] && break
        sleep 2
    done

    if [[ -n "${tunnel_url}" ]]; then
        echo "Quick Tunnel URL: ${tunnel_url}"
    else
        echo "warning: tunnel is starting; get its URL with:" >&2
        echo "  docker compose --env-file .env.vps logs -f cloudflared" >&2
    fi
fi

echo
compose ps
if (( USE_ENV_FILE )); then
    echo "Demo is running. Use 'docker compose --env-file ${ENV_FILE} down' to stop it."
else
    echo "Demo is running. Use 'docker compose down' to stop it."
fi
