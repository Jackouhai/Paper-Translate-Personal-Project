#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.vps"
BUILD_IMAGES=1
START_TUNNEL=1
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-1200}"

usage() {
    cat <<'EOF'
Usage: scripts/start_vps_demo.sh [--skip-build] [--no-tunnel]

Starts the 12 GB VPS demo in this order:
  1. TranslateGemma
  2. PaddleOCR-VL
  3. Parse API, web API, and frontend
  4. Cloudflare Quick Tunnel (unless --no-tunnel is supplied)

The script copies .env.vps.example to .env.vps on its first run.
EOF
}

for argument in "$@"; do
    case "${argument}" in
        --skip-build) BUILD_IMAGES=0 ;;
        --no-tunnel) START_TUNNEL=0 ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown option: ${argument}" >&2
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

if [[ ! -f "${ENV_FILE}" ]]; then
    cp .env.vps.example "${ENV_FILE}"
    echo "created .env.vps from .env.vps.example"
fi

compose() {
    docker compose --env-file "${ENV_FILE}" "$@"
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
wait_for_endpoint "Web frontend" "http://127.0.0.1:3000" "web-frontend"

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
echo "Demo is running. Use 'docker compose --env-file .env.vps down' to stop it."
