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

quantization="${TRANSLATE_GEMMA_QUANTIZATION:-fp8}"
args=(
    --max-model-len "${TRANSLATE_GEMMA_MAX_MODEL_LEN:-4096}"
    --max-num-seqs "${TRANSLATE_GEMMA_MAX_NUM_SEQS:-24}"
    --max-num-batched-tokens "${TRANSLATE_GEMMA_MAX_BATCHED_TOKENS:-16384}"
    --gpu-memory-utilization "${TRANSLATE_GEMMA_GPU_MEMORY_UTILIZATION:-0.8}"
    --dtype "${TRANSLATE_GEMMA_DTYPE:-auto}"
    --kv-cache-dtype "${TRANSLATE_GEMMA_KV_CACHE_DTYPE:-fp8}"
    --enable-chunked-prefill
    --port 8001
)

if [[ "${quantization}" != "none" ]]; then
    args+=(--quantization "${quantization}")
fi

if [[ "${TRANSLATE_GEMMA_ENFORCE_EAGER:-0}" == "1" ]]; then
    args+=(--enforce-eager)
fi

cpu_offload_gb="${TRANSLATE_GEMMA_CPU_OFFLOAD_GB:-0}"
if [[ "${cpu_offload_gb}" != "0" ]]; then
    args+=(--cpu-offload-gb "${cpu_offload_gb}")
fi

exec uv run vllm serve Infomaniak-AI/vllm-translategemma-4b-it "${args[@]}"
