#!/usr/bin/env python3
"""Export YOLO26 models to ONNX + other formats for production deployment.

Exports:
- ONNX (default, dynamic batch)
- ONNX (static batch, optimized)
- OpenVINO (if available)
- TensorRT (if available)
- CoreML (if on macOS)

Also benchmarks ONNX vs PyTorch inference speed and logs to MLflow.

Usage:
    # Export single model
    /opt/sam3_venv/bin/python3 scripts/export_onnx.py --model yolo26s_detect_v2

    # Export all available models
    /opt/sam3_venv/bin/python3 scripts/export_onnx.py --all

    # Export + benchmark
    /opt/sam3_venv/bin/python3 scripts/export_onnx.py --all --benchmark
"""
import argparse
import sys
import time
import json
from pathlib import Path

import mlflow
from mlflow.tracking import MlflowClient

TRACKING_URI = "sqlite:////mnt/e/02_Projects/auto_label/yolo26_ppe/mlflow/mlflow.db"
BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")

MODELS = {
    "yolo26n_detect_v2": {
        "weights": BASE / "models/yolo26n_detect_v2/run1/weights/best.pt",
        "task": "detect",
        "size": "n",
    },
    "yolo26s_detect_v2": {
        "weights": BASE / "models/yolo26s_detect_v2/run1/weights/best.pt",
        "task": "detect",
        "size": "s",
    },
    "yolo26n_seg_v2": {
        "weights": BASE / "models/yolo26n_seg_v2/run1/weights/best.pt",
        "task": "segment",
        "size": "n",
    },
    "yolo26s_seg_v2": {
        "weights": BASE / "models/yolo26s_seg_v2/run1/weights/best.pt",
        "task": "segment",
        "size": "s",
    },
}


def export_onnx(model_name, dynamic=True, simplify=True, opset=12, imgsz=640):
    """Export model to ONNX format."""
    from ultralytics import YOLO

    meta = MODELS[model_name]
    weights = meta["weights"]

    if not weights.exists():
        print(f"  [SKIP] Weights not found: {weights}")
        return None

    print(f"\n{'='*60}")
    print(f"Exporting: {model_name}")
    print(f"  Weights: {weights}")
    print(f"  Task: {meta['task']}")
    print(f"  ONNX: dynamic={dynamic} simplify={simplify} opset={opset} imgsz={imgsz}")
    print(f"{'='*60}")

    model = YOLO(str(weights))

    # Export to ONNX
    export_path = model.export(
        format="onnx",
        imgsz=imgsz,
        dynamic=dynamic,
        simplify=simplify,
        opset=opset,
        half=False,  # FP32 for compatibility
    )

    onnx_path = Path(export_path)
    pt_size = weights.stat().st_size / 1e6
    onnx_size = onnx_path.stat().st_size / 1e6 if onnx_path.exists() else 0

    print(f"  [OK] ONNX exported: {onnx_path}")
    print(f"  [OK] PT size: {pt_size:.2f} MB")
    print(f"  [OK] ONNX size: {onnx_size:.2f} MB")

    # Log to MLflow
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("yolo26_ppe_v2")
    with mlflow.start_run(run_name=f"{model_name}_onnx_export") as run:
        mlflow.set_tag("export_type", "onnx")
        mlflow.set_tag("model", model_name)
        mlflow.set_tag("task", meta["task"])
        mlflow.log_param("format", "onnx")
        mlflow.log_param("dynamic", dynamic)
        mlflow.log_param("simplify", simplify)
        mlflow.log_param("opset", opset)
        mlflow.log_param("imgsz", imgsz)
        mlflow.log_metric("pt_size_mb", pt_size)
        mlflow.log_metric("onnx_size_mb", onnx_size)
        mlflow.log_metric("size_ratio", onnx_size / pt_size if pt_size > 0 else 0)

        # Log ONNX model as artifact
        if onnx_path.exists():
            mlflow.log_artifact(str(onnx_path), artifact_path="onnx")
            print(f"  [MLflow] Logged ONNX artifact: {run.info.run_id[:16]}")

    return onnx_path


def export_other_formats(model_name, imgsz=640):
    """Try exporting to other formats (OpenVINO, TensorRT, etc.)."""
    from ultralytics import YOLO

    meta = MODELS[model_name]
    weights = meta["weights"]

    if not weights.exists():
        return

    model = YOLO(str(weights))

    formats_to_try = [
        ("openvino", "OpenVINO"),
        ("engine", "TensorRT"),
        ("torchscript", "TorchScript"),
    ]

    exported = {}
    for fmt, name in formats_to_try:
        try:
            print(f"  Trying {name} export...")
            path = model.export(format=fmt, imgsz=imgsz, dynamic=True)
            if path:
                size = Path(path).stat().st_size / 1e6
                exported[fmt] = {"path": str(path), "size_mb": size}
                print(f"    [OK] {name}: {path} ({size:.2f} MB)")
        except Exception as e:
            print(f"    [SKIP] {name}: {e}")

    # Log to MLflow
    if exported:
        mlflow.set_tracking_uri(TRACKING_URI)
        mlflow.set_experiment("yolo26_ppe_v2")
        with mlflow.start_run(run_name=f"{model_name}_multi_export") as run:
            mlflow.set_tag("export_type", "multi_format")
            mlflow.set_tag("model", model_name)
            for fmt, info in exported.items():
                mlflow.log_metric(f"{fmt}_size_mb", info["size_mb"])
            mlflow.log_dict(exported, "exports/formats.json")

    return exported


def benchmark_onnx_vs_pt(model_name, n_runs=50, imgsz=640):
    """Benchmark ONNX vs PyTorch inference speed."""
    import numpy as np

    meta = MODELS[model_name]
    weights = meta["weights"]
    onnx_path = weights.with_suffix(".onnx")

    if not onnx_path.exists():
        print(f"  [SKIP] ONNX not found: {onnx_path}")
        return None

    print(f"\n  Benchmarking ONNX vs PyTorch ({n_runs} runs)...")

    # PyTorch benchmark
    from ultralytics import YOLO
    pt_model = YOLO(str(weights))

    # Warmup
    dummy = np.random.randint(0, 255, (imgsz, imgsz, 3), dtype=np.uint8)
    for _ in range(5):
        pt_model(dummy, verbose=False)

    # Benchmark PT
    pt_times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        pt_model(dummy, verbose=False)
        pt_times.append((time.perf_counter() - t0) * 1000)

    # ONNX benchmark
    try:
        import onnxruntime as ort
        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        input_name = sess.get_inputs()[0].name

        # Prepare input (1, 3, H, W) float32
        inp = dummy.transpose(2, 0, 1).astype(np.float32) / 255.0
        inp = np.expand_dims(inp, 0)

        # Warmup
        for _ in range(5):
            sess.run(None, {input_name: inp})

        # Benchmark ONNX
        onnx_times = []
        for _ in range(n_runs):
            t0 = time.perf_counter()
            sess.run(None, {input_name: inp})
            onnx_times.append((time.perf_counter() - t0) * 1000)

        onnx_median = np.median(onnx_times)
        onnx_mean = np.mean(onnx_times)
    except ImportError:
        print("  [SKIP] onnxruntime not installed")
        onnx_median = 0
        onnx_mean = 0

    pt_median = np.median(pt_times)
    pt_mean = np.mean(pt_times)

    print(f"  PyTorch:  median={pt_median:.2f}ms  mean={pt_mean:.2f}ms")
    print(f"  ONNX:     median={onnx_median:.2f}ms  mean={onnx_mean:.2f}ms")
    if onnx_median > 0:
        speedup = pt_median / onnx_median
        print(f"  Speedup:  {speedup:.2f}x")

    # Log to MLflow
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("yolo26_ppe_v2")
    with mlflow.start_run(run_name=f"{model_name}_benchmark") as run:
        mlflow.set_tag("benchmark_type", "onnx_vs_pt")
        mlflow.set_tag("model", model_name)
        mlflow.log_metric("pt_inference_median_ms", pt_median)
        mlflow.log_metric("pt_inference_mean_ms", pt_mean)
        mlflow.log_metric("onnx_inference_median_ms", onnx_median)
        mlflow.log_metric("onnx_inference_mean_ms", onnx_mean)
        if onnx_median > 0:
            mlflow.log_metric("speedup_onnx_vs_pt", pt_median / onnx_median)
        print(f"  [MLflow] Benchmark logged: {run.info.run_id[:16]}")

    return {
        "pt_median_ms": pt_median,
        "onnx_median_ms": onnx_median,
        "speedup": pt_median / onnx_median if onnx_median > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Export YOLO models to ONNX + other formats")
    parser.add_argument("--model", default="yolo26s_detect_v2",
                        choices=list(MODELS.keys()))
    parser.add_argument("--all", action="store_true", help="Export all available models")
    parser.add_argument("--benchmark", action="store_true", help="Benchmark ONNX vs PT")
    parser.add_argument("--multi-format", action="store_true",
                        help="Also try OpenVINO/TensorRT/TorchScript")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--opset", type=int, default=12)
    parser.add_argument("--no-dynamic", action="store_true", help="Static batch size")
    parser.add_argument("--no-simplify", action="store_true", help="Skip ONNX simplification")
    args = parser.parse_args()

    print("=" * 70)
    print("ONNX Export + Production Deployment Prep")
    print("=" * 70)

    models_to_export = list(MODELS.keys()) if args.all else [args.model]

    results = {}
    for name in models_to_export:
        meta = MODELS[name]
        if not meta["weights"].exists():
            print(f"\n[SKIP] {name}: weights not found")
            continue

        # Export ONNX
        onnx_path = export_onnx(
            name,
            dynamic=not args.no_dynamic,
            simplify=not args.no_simplify,
            opset=args.opset,
            imgsz=args.imgsz,
        )

        # Export other formats
        if args.multi_format:
            export_other_formats(name, imgsz=args.imgsz)

        # Benchmark
        if args.benchmark and onnx_path:
            bench = benchmark_onnx_vs_pt(name, imgsz=args.imgsz)
            results[name] = bench

    # Summary
    print("\n" + "=" * 70)
    print("EXPORT SUMMARY")
    print("=" * 70)
    for name in models_to_export:
        meta = MODELS[name]
        onnx_path = meta["weights"].with_suffix(".onnx")
        pt_size = meta["weights"].stat().st_size / 1e6 if meta["weights"].exists() else 0
        onnx_size = onnx_path.stat().st_size / 1e6 if onnx_path.exists() else 0
        print(f"  {name}:")
        print(f"    PT:   {pt_size:.2f} MB")
        print(f"    ONNX: {onnx_size:.2f} MB {'✓' if onnx_path.exists() else '✗'}")
        if name in results:
            r = results[name]
            print(f"    Speed: PT={r['pt_median_ms']:.1f}ms  ONNX={r['onnx_median_ms']:.1f}ms  ({r['speedup']:.2f}x)")


if __name__ == "__main__":
    main()
