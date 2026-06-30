#!/usr/bin/env bash
set -euo pipefail

vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --dtype bfloat16 \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --max-model-len 32768 \
    --max-num-seqs 15 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.5 \
    --kv-cache-dtype fp8 \
    --enforce-eager \
    --port 8001
