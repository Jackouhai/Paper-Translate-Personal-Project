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
export VLLM_USE_FLASHINFER_SAMPLER="${VLLM_USE_FLASHINFER_SAMPLER:-0}"
exec uv run vllm serve PaddlePaddle/PaddleOCR-VL-1.6 \
    --served-model-name PaddleOCR-VL-1.5-0.9B \
    --trust-remote-code \
    --dtype bfloat16 \
    --max-model-len 16384 \
    --max-num-seqs 30 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.2 \
    --no-enable-prefix-caching \
    --mm-processor-cache-gb 0 \
    --port 8000
