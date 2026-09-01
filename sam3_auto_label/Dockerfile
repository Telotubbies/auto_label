# SAM 3.1 PPE Segmentation — GPU inference (ROCm/CUDA) + batch CLI
#
# Build arg: GPU_TYPE = rocm | cuda | cpu
# Usage:
#   docker build --build-arg GPU_TYPE=rocm -f Dockerfile .   (AMD GPU)
#   docker build --build-arg GPU_TYPE=cuda -f Dockerfile .   (NVIDIA GPU)
#   docker build --build-arg GPU_TYPE=cpu  -f Dockerfile .   (fallback)
# Or use docker-compose profiles (see docker-compose.yml)

ARG GPU_TYPE=cpu

# ---------------------------------------------------------------------------
# Stage 1: Base images
# ---------------------------------------------------------------------------
FROM rocm/pytorch:rocm6.2_ubuntu22.04_py3.12_pytorch_release_2.4.0 AS base-rocm
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS base-cuda
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3-pip python3.12-venv \
    gcc g++ libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.12 /usr/bin/python

FROM python:3.12-slim AS base-cpu
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Select base
FROM base-${GPU_TYPE} AS final

# ---------------------------------------------------------------------------
# Stage 2: Install deps
# ---------------------------------------------------------------------------
WORKDIR /app

ARG GPU_TYPE=cpu

# Copy requirements (torch excluded — installed per GPU type)
COPY requirements.txt .

# Install non-torch deps
RUN pip install --no-cache-dir -r requirements.txt

# Install PyTorch — GPU variants first, CPU last resort
RUN if [ "$GPU_TYPE" = "rocm" ]; then \
        pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/rocm6.2; \
    elif [ "$GPU_TYPE" = "cuda" ]; then \
        pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cu121; \
    else \
        pip install --no-cache-dir torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu; \
    fi

# Copy source
COPY src/ ./src/
COPY config/ ./config/
COPY sam3/ ./sam3/

# Model checkpoint is mounted at runtime: -v ./checkpoints:/app/checkpoints
RUN mkdir -p /app/input /app/output /app/checkpoints

# ROCm environment for RDNA3 (RX 7800 XT) — experimental attention kernels
ENV HSA_ENABLE_DXG_DETECTION=1
ENV TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL=1
ENV PYTHONPATH=/app/src:/app/sam3
ENV PYTHONUNBUFFERED=1

# Batch CLI is the entrypoint (no web service)
# Run: docker run --rm -v ./checkpoints:/app/checkpoints -v ../data/raw:/app/input <image> \
#          python src/batch_segment.py -c config/ppe_6class.yaml --input /app/input/<batch> --output /app/output/<batch>
CMD ["python", "src/batch_segment.py", "--help"]
