#!/usr/bin/env python3
"""GPU compute benchmark — verify 100% GPU utilization with PyTorch optimizations."""
import os
os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")
os.environ.setdefault("LD_PRELOAD", "/opt/rocm/lib/libamdhip64.so")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "max_split_size_mb:512")

import torch
import time

print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if not torch.cuda.is_available():
    print("ERROR: No GPU detected!")
    exit(1)

print(f"GPU: {torch.cuda.get_device_name(0)}")
props = torch.cuda.get_device_properties(0)
print(f"VRAM: {props.total_memory / 1024**3:.1f} GB")
print(f"Compute capability: {props.major}.{props.minor}")

# Apply optimizations
torch.backends.cudnn.benchmark = True
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
torch.backends.cudnn.deterministic = False
torch.cuda.set_per_process_memory_fraction(0.95, 0)

print(f"\nOptimizations:")
print(f"  cudnn.benchmark: {torch.backends.cudnn.benchmark}")
print(f"  tf32 matmul: {torch.backends.cuda.matmul.allow_tf32}")
print(f"  tf32 cudnn: {torch.backends.cudnn.allow_tf32}")
print(f"  deterministic: {torch.backends.cudnn.deterministic}")
print(f"  memory_fraction: 0.95")

# Benchmark 1: Large matmul (compute-bound)
print("\n=== Benchmark 1: Matmul (compute-bound) ===")
device = torch.device("cuda")
a = torch.randn(4096, 4096, device=device)
b = torch.randn(4096, 4096, device=device)
torch.cuda.synchronize()
t0 = time.time()
for _ in range(10):
    c = a @ b
torch.cuda.synchronize()
t1 = time.time()
print(f"  10x matmul (4096x4096): {(t1-t0)*1000:.1f} ms ({10/(t1-t0):.1f} GFLOPS)")

# Benchmark 2: Conv2d (typical YOLO workload)
print("\n=== Benchmark 2: Conv2d (YOLO-like) ===")
conv = torch.nn.Conv2d(64, 256, 3, stride=2, padding=1).cuda()
x = torch.randn(16, 64, 640, 640, device=device)  # batch=16, 64ch, 640x640
torch.cuda.synchronize()
t0 = time.time()
for _ in range(5):
    y = conv(x)
torch.cuda.synchronize()
t1 = time.time()
print(f"  5x Conv2d (batch=16): {(t1-t0)*1000:.1f} ms")

# Benchmark 3: channels_last vs channels_first
print("\n=== Benchmark 3: channels_last vs channels_first ===")
x_contiguous = torch.randn(16, 3, 640, 640, device=device)
x_channels_last = x_contiguous.to(memory_format=torch.channels_last)
conv2 = torch.nn.Conv2d(3, 64, 3, stride=2, padding=1).cuda()
conv2_cl = torch.nn.Conv2d(3, 64, 3, stride=2, padding=1).to(memory_format=torch.channels_last).cuda()

# Warmup
for _ in range(3):
    _ = conv2(x_contiguous)
    _ = conv2_cl(x_channels_last)
torch.cuda.synchronize()

t0 = time.time()
for _ in range(10):
    _ = conv2(x_contiguous)
torch.cuda.synchronize()
t1 = time.time()
print(f"  channels_first: {(t1-t0)*1000:.1f} ms")

t0 = time.time()
for _ in range(10):
    _ = conv2_cl(x_channels_last)
torch.cuda.synchronize()
t1 = time.time()
print(f"  channels_last:  {(t1-t0)*1000:.1f} ms")

# Benchmark 4: VRAM usage
print(f"\n=== VRAM Usage ===")
print(f"  Allocated: {torch.cuda.memory_allocated() / 1024**3:.2f} GB")
print(f"  Reserved:  {torch.cuda.memory_reserved() / 1024**3:.2f} GB")
print(f"  Max alloc:  {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")

print("\n=== GPU optimization benchmark complete ===")
