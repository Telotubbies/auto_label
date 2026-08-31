#!/usr/bin/env python3
"""Export ONNX for all completed models + benchmark."""
import json
import time
from pathlib import Path
from ultralytics import YOLO
import mlflow

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
mlflow.set_tracking_uri(f"sqlite:///{BASE}/mlflow/mlflow.db")
mlflow.set_experiment("yolo26_ppe_onnx_export")

models = {
    "n_detect": BASE / "models/yolo26n_detect_v2/run1/weights/best.pt",
    "s_detect": BASE / "models/yolo26s_detect_v2/run1/weights/best.pt",
    "n_seg": BASE / "models/yolo26n_seg_v2/run1/weights/best.pt",
    "s_seg": BASE / "models/yolo26s_seg_v2/run1/weights/best.pt",
}

results = {}
for name, weights in models.items():
    print(f"\n{'='*60}")
    print(f"  Exporting {name} to ONNX")
    print(f"{'='*60}")

    model = YOLO(str(weights))

    # Export
    onnx_path = model.export(
        format="onnx",
        dynamic=True,
        simplify=True,
        opset=12,
        imgsz=640,
    )
    print(f"  ONNX saved: {onnx_path}")

    # Get file sizes
    pt_size = weights.stat().st_size / (1024 * 1024)
    onnx_size = Path(onnx_path).stat().st_size / (1024 * 1024)

    # Benchmark PyTorch GPU
    print(f"  Benchmarking PyTorch GPU...")
    import torch
    dummy = torch.zeros(1, 3, 640, 640).to("cuda")
    model_model = model.model.to("cuda").eval()
    with torch.no_grad():
        # Warmup
        for _ in range(10):
            _ = model_model(dummy)
        torch.cuda.synchronize()
        t0 = time.time()
        for _ in range(100):
            _ = model_model(dummy)
        torch.cuda.synchronize()
        pt_ms = (time.time() - t0) / 100 * 1000

    print(f"  PyTorch GPU: {pt_ms:.1f} ms/image")
    print(f"  PT size: {pt_size:.1f} MB, ONNX size: {onnx_size:.1f} MB")

    results[name] = {
        "onnx_path": str(onnx_path),
        "pt_size_mb": pt_size,
        "onnx_size_mb": onnx_size,
        "pt_gpu_ms": pt_ms,
    }

    # Log to MLflow
    with mlflow.start_run(run_name=f"onnx_export_{name}"):
        mlflow.set_tags({"model_variant": name, "export_type": "onnx"})
        mlflow.log_metric("pt_size_mb", pt_size)
        mlflow.log_metric("onnx_size_mb", onnx_size)
        mlflow.log_metric("pt_gpu_ms", pt_ms)

# Save
output = BASE / "report" / "onnx_export_results.json"
with open(output, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}")
print(f"  All ONNX exports complete!")
print(f"  Results: {output}")
print(f"{'='*60}")
print(json.dumps(results, indent=2))
