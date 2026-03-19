#!/bin/bash

vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --dtype bfloat16 \
    --max-model-len 32768\
    --max-num-seqs 32 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.9 \
    --enforce-eager \
    --port 8001 \
    --optimization-level 0


vllm serve PaddlePaddle/PaddleOCR-VL-1.5 \
    --served-model-name PaddleOCR-VL-1.5-0.9B \
    --trust-remote-code \
    --max-num-batched-tokens 16384  \
    --max-num-seqs 3 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.6 \
    --no-enable-prefix-caching \
    --mm-processor-cache-gb 0 \
    --dtype bfloat16 \
    --tensor-parallel-size 1



