#!/usr/bin/env bash
# Serve Qwen2.5-VL (AWQ) for LabelDesk. Run in WSL on the GPU box. Fits a 12 GB card (~0.55 utilisation).
set -euo pipefail
VLLM_SERVER_DEV_MODE=1 exec vllm serve "${LD_VLM_MODEL:-Qwen/Qwen2.5-VL-7B-Instruct-AWQ}" --host 127.0.0.1 --port 8000 --quantization awq --max-model-len 4096 --gpu-memory-utilization 0.55 --max-num-seqs 4 --limit-mm-per-prompt '{"image": 1}' --mm-processor-kwargs '{"max_pixels": 589824}' --enable-sleep-mode
