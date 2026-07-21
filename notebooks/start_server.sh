#!/bin/bash

vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --dtype bfloat16 \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --max-model-len 32768 \
    --max-num-seqs 30 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.7 \
    --kv-cache-dtype fp8 \
    --enforce-eager \
    --port 8001


# vllm serve PaddlePaddle/PaddleOCR-VL-1.5 \
#     --served-model-name PaddleOCR-VL-1.5-0.9B \
#     --trust-remote-code \
#     --dtype bfloat16 \
#     --max-model-len 16384 \
#     --max-num-seqs 30 \
#     --max-num-batched-tokens 8192 \
#     --gpu-memory-utilization 0.2 \
#     --enforce-eager \
#     --no-enable-prefix-caching \
#     --mm-processor-cache-gb 0


uv run pp_doclayout_service.py --workers 2

vllm serve PaddlePaddle/PaddleOCR-VL-1.5 \
    --served-model-name PaddleOCR-VL-1.5-0.9B \
    --trust-remote-code \
    --dtype bfloat16 \
    --max-model-len 16384 \
    --max-num-seqs 30 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.5 \
    --enforce-eager \
    --no-enable-prefix-caching \
    --mm-processor-cache-gb 0