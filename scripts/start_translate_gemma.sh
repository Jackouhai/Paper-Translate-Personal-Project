#!/usr/bin/env bash
set -euo pipefail

vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --dtype bfloat16 \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --max-model-len 8192 \
    --max-num-seqs 10 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.7 \
    --port 8001
