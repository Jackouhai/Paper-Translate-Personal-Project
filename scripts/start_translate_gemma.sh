#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
LLM_SERVER_DIR="${PROJECT_ROOT}/services/llm-server"

if [[ ! -f "${LLM_SERVER_DIR}/pyproject.toml" ]]; then
    echo "error: LLM server project not found: ${LLM_SERVER_DIR}" >&2
    exit 1
fi

cd "${LLM_SERVER_DIR}"
exec uv run vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --quantization fp8 \
    --max-model-len 4096 \
    --max-num-seqs 5 \
    --max-num-batched-tokens 4096 \
    --gpu-memory-utilization 0.49 \
    --kv-cache-dtype fp8 \
    --port 8001
