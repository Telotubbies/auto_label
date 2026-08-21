#!/usr/bin/env python3
"""Benchmark SAM 3.1 on the same test set as YOLO models."""
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
SAM_BASE = Path("/mnt/e/02_Projects/auto_label/sam3")
REPO_BASE = Path("/mnt/e/02_Projects/auto_label")

sys.path.insert(0, str(SAM_BASE))

test_images_dir = BASE / "data/yolo_detect_v2/images/test"
test_images = sorted(list(test_images_dir.glob("*.jpg")) + list(test_images_dir.glob("*.png")))

print(f"{'='*60}")
print(f"  Benchmarking SAM 3.1 on {len(test_images)} test images")
print(f"{'='*60}")

from sam3.model_builder import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor

checkpoint = REPO_BASE / "models/sam3/sam3.1_multiplex.pt"
print(f"  Checkpoint: {checkpoint}")

device = "cuda"
model = build_sam3_image_model(
    checkpoint_path=str(checkpoint),
    load_from_HF=False,
    device=device,
)
processor = Sam3Processor(
    model,
    resolution=1008,
    confidence_threshold=0.3,
)

model_size_mb = checkpoint.stat().st_size / (1024 * 1024)
print(f"  Model size: {model_size_mb:.1f} MB")

PPE_PROMPTS = ["person", "helmet", "boots", "shoes", "harness"]

# Warmup
print("  Warming up...")
dummy = Image.new("RGB", (640, 640), (128, 128, 128))
with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    state = processor.set_image(dummy)
    state = processor.set_text_prompt("person", state)
torch.cuda.synchronize()

# Benchmark
print(f"  Running inference on {len(test_images)} images...")
inference_times = []
all_predictions = []

for img_path in test_images:
    img = Image.open(img_path).convert("RGB")

    t0 = time.time()
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        state = processor.set_image(img)
        state = processor.set_text_prompt("person, helmet, boots, shoes, harness", state)
    torch.cuda.synchronize()
    t1 = time.time()

    ms = (t1 - t0) * 1000
    inference_times.append(ms)

    num_masks = 0
    if "masks" in state and state["masks"] is not None:
        num_masks = int(state["masks"].shape[0])

    all_predictions.append({
        "image": img_path.name,
        "num_masks": num_masks,
        "time_ms": ms,
    })

    if len(inference_times) % 10 == 0:
        print(f"    {len(inference_times)}/{len(test_images)} done, avg={np.mean(inference_times):.1f}ms")

avg_ms = np.mean(inference_times)
std_ms = np.std(inference_times)
fps = 1000 / avg_ms

print(f"\n  Results:")
print(f"  Avg inference: {avg_ms:.1f} ± {std_ms:.1f} ms/image")
print(f"  FPS: {fps:.1f}")
print(f"  Model size: {model_size_mb:.1f} MB")

results = {
    "sam3_1": {
        "avg_inference_ms": float(avg_ms),
        "std_inference_ms": float(std_ms),
        "fps": float(fps),
        "model_size_mb": float(model_size_mb),
        "num_test_images": len(test_images),
        "predictions_sample": all_predictions[:10],
    }
}

output = BASE / "report" / "sam3_benchmark_results.json"
with open(output, "w") as f:
    json.dump(results, f, indent=2)

import mlflow
mlflow.set_tracking_uri(f"sqlite:///{BASE}/mlflow/mlflow.db")
mlflow.set_experiment("yolo26_ppe_final_eval")

with mlflow.start_run(run_name="sam3_1_benchmark"):
    mlflow.set_tags({"model_variant": "sam3_1", "eval_type": "test_set", "task": "segment"})
    mlflow.log_metric("avg_inference_ms", avg_ms)
    mlflow.log_metric("std_inference_ms", std_ms)
    mlflow.log_metric("fps", fps)
    mlflow.log_metric("model_size_mb", model_size_mb)

print(f"\n  Results saved: {output}")
print(f"{'='*60}")
