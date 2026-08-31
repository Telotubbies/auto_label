#!/usr/bin/env python3
"""Export 4 v4_recipe models to ONNX, benchmark on GPU, evaluate on test set.
Compare PyTorch vs ONNX results."""
import sys, os, json, time, shutil
sys.path.insert(0, os.path.dirname(__file__))
try:
    import focal_patch
except Exception:
    pass

# Prevent Ultralytics from auto-installing onnxruntime (CPU version)
os.environ["ULTRALYTICS_AUTOINSTALL"] = "False"
os.environ["YOLO_AUTOINSTALL"] = "False"

# Patch Ultralytics checks to prevent auto-install
import ultralytics.utils.checks as _checks
_orig_check = _checks.check_requirements
def _patched_check(*args, **kwargs):
    # Skip auto-install for onnxruntime
    if args and any('onnxruntime' in str(a) for a in args):
        return True
    return _orig_check(*args, **kwargs)
_checks.check_requirements = _patched_check

from ultralytics import YOLO
import torch
import numpy as np
from pathlib import Path
import onnxruntime as ort

VERSION = "v4_recipe"
BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
ONNX_DIR = BASE / "onnx_exports" / VERSION
ONNX_DIR.mkdir(parents=True, exist_ok=True)
EVAL_OUT = BASE / "eval_results" / VERSION / "onnx"
EVAL_OUT.mkdir(parents=True, exist_ok=True)

MODELS = {
    "n_detect": {
        "weights": BASE / f"models/yolo26n_detect_{VERSION}/run2_stage2/weights/best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "task": "detect",
    },
    "s_detect": {
        "weights": BASE / f"models/yolo26s_detect_{VERSION}/run2_stage2/weights/best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "task": "detect",
    },
    "n_seg": {
        "weights": BASE / f"models/yolo26n_seg_{VERSION}/run2_stage2/weights/best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
    },
    "s_seg": {
        "weights": BASE / f"models/yolo26s_seg_{VERSION}/run2_stage2/weights/best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
    },
}

NAMES = ["person", "helmet", "boots", "shoes", "harness"]

def export_onnx(key, cfg):
    print(f"\n{'='*60}")
    print(f"Exporting ONNX: {key}")
    print(f"{'='*60}")
    model = YOLO(str(cfg["weights"]))
    onnx_path = ONNX_DIR / f"{key}.onnx"
    if onnx_path.exists():
        print(f"  Already exists: {onnx_path} ({onnx_path.stat().st_size/1024**2:.1f} MB)")
        return onnx_path
    path = model.export(
        format="onnx",
        imgsz=640,
        half=False,
        dynamic=False,
        simplify=True,
        opset=12,
        batch=1,
    )
    # Move to our dir
    src = Path(path)
    if src != onnx_path:
        shutil.copy(src, onnx_path)
    size_mb = onnx_path.stat().st_size / 1024**2
    print(f"  Exported: {onnx_path} ({size_mb:.1f} MB)")
    return onnx_path

def eval_pytorch(key, cfg):
    """Evaluate with PyTorch (before ONNX)."""
    print(f"\n--- PyTorch eval: {key} ---")
    model = YOLO(str(cfg["weights"]))
    results = model.val(
        data=cfg["data"],
        split="test",
        imgsz=640,
        batch=16,
        conf=0.001,
        iou=0.6,
        device=0,
        verbose=False,
        project=str(EVAL_OUT / key),
        name="pytorch_eval",
        exist_ok=True,
    )
    metrics = extract_metrics(results, cfg["task"])
    metrics["engine"] = "pytorch"
    metrics["model_size_MB"] = cfg["weights"].stat().st_size / 1024**2
    # Benchmark latency on a test image
    test_dir = Path("/tmp/yolo_detect_data/images/test") if cfg["task"] == "detect" else Path("/tmp/yolo_seg_data/images/test")
    test_imgs = sorted(test_dir.glob("*.jpg"))
    sample_img = str(test_imgs[0]) if test_imgs else None
    latencies = []
    if sample_img:
        for _ in range(20):
            t0 = time.time()
            model.predict(sample_img, imgsz=640, device=0, verbose=False)
            latencies.append((time.time() - t0) * 1000)
    metrics["latency_ms"] = float(np.median(latencies[5:])) if latencies else 0
    return metrics

def eval_onnx(key, cfg, onnx_path):
    """Evaluate with ONNX Runtime on GPU."""
    print(f"\n--- ONNX eval: {key} ---")
    # Use Ultralytics YOLO with ONNX
    model = YOLO(str(onnx_path), task=cfg["task"])
    results = model.val(
        data=cfg["data"],
        split="test",
        imgsz=640,
        batch=1,
        conf=0.001,
        iou=0.6,
        device=0,  # GPU
        verbose=False,
        project=str(EVAL_OUT / key),
        name="onnx_eval",
        exist_ok=True,
    )
    metrics = extract_metrics(results, cfg["task"])
    metrics["engine"] = "onnx"
    metrics["model_size_MB"] = onnx_path.stat().st_size / 1024**2
    # Benchmark latency on a test image
    test_dir = Path("/tmp/yolo_detect_data/images/test") if cfg["task"] == "detect" else Path("/tmp/yolo_seg_data/images/test")
    test_imgs = sorted(test_dir.glob("*.jpg"))
    sample_img = str(test_imgs[0]) if test_imgs else None
    latencies = []
    if sample_img:
        for _ in range(20):
            t0 = time.time()
            model.predict(sample_img, imgsz=640, device=0, verbose=False)
            latencies.append((time.time() - t0) * 1000)
    metrics["latency_ms"] = float(np.median(latencies[5:])) if latencies else 0
    return metrics

def extract_metrics(results, task):
    metrics = {}
    try:
        pc = {}
        names = results.names
        for i, n in names.items():
            pc[n] = {
                "P": float(results.box.p[i]) if i < len(results.box.p) else None,
                "R": float(results.box.r[i]) if i < len(results.box.r) else None,
                "mAP50": float(results.box.ap50[i]) if i < len(results.box.ap50) else None,
                "mAP50-95": float(results.box.ap[i]) if i < len(results.box.ap) else None,
            }
        maps = [v["mAP50"] for v in pc.values() if v.get("mAP50") is not None]
        map95 = [v["mAP50-95"] for v in pc.values() if v.get("mAP50-95") is not None]
        ps = [v["P"] for v in pc.values() if v.get("P") is not None]
        rs = [v["R"] for v in pc.values() if v.get("R") is not None]
        metrics["mAP50"] = sum(maps)/len(maps) if maps else 0
        metrics["mAP50-95"] = sum(map95)/len(map95) if map95 else 0
        metrics["precision"] = sum(ps)/len(ps) if ps else 0
        metrics["recall"] = sum(rs)/len(rs) if rs else 0
        metrics["per_class"] = pc
    except Exception as e:
        print(f"metric error: {e}")
    try:
        speed = results.speed
        metrics["inference_ms"] = float(speed.get("inference", 0))
    except Exception:
        pass
    if task == "segment":
        try:
            seg_pc = {}
            for i, n in names.items():
                seg_pc[n] = {
                    "P": float(results.seg.p[i]) if i < len(results.seg.p) else None,
                    "R": float(results.seg.r[i]) if i < len(results.seg.r) else None,
                    "mAP50": float(results.seg.mAP50) if hasattr(results.seg, 'mAP50') else None,
                }
            metrics["mask_per_class"] = seg_pc
        except Exception as e:
            print(f"seg metric error: {e}")
    return metrics

def main():
    all_results = {}
    for key, cfg in MODELS.items():
        if not cfg["weights"].exists():
            print(f"SKIP {key}: weights not found")
            continue
        # Export
        onnx_path = export_onnx(key, cfg)
        # Eval PyTorch
        pt_metrics = eval_pytorch(key, cfg)
        # Eval ONNX
        onnx_metrics = eval_onnx(key, cfg, onnx_path)
        all_results[key] = {
            "pytorch": pt_metrics,
            "onnx": onnx_metrics,
            "onnx_path": str(onnx_path),
        }
        # Save per-model
        with open(EVAL_OUT / f"{key}_comparison.json", "w") as f:
            json.dump(all_results[key], f, indent=2, default=str)
    # Summary
    with open(EVAL_OUT / "all_comparison.json", "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    # Print comparison table
    print(f"\n{'='*90}")
    print("COMPARISON: PyTorch vs ONNX (GPU)")
    print(f"{'='*90}")
    print(f"{'Model':<12} {'Engine':<8} {'mAP50':>8} {'mAP50-95':>10} {'P':>8} {'R':>8} {'Size(MB)':>10} {'Lat(ms)':>8}")
    print("-"*90)
    for key, r in all_results.items():
        for engine in ["pytorch", "onnx"]:
            m = r[engine]
            print(f"{key:<12} {engine:<8} {m.get('mAP50',0):>8.3f} {m.get('mAP50-95',0):>10.3f} {m.get('precision',0):>8.3f} {m.get('recall',0):>8.3f} {m.get('model_size_MB',0):>10.1f} {m.get('latency_ms',0):>8.1f}")
    print(f"\nResults saved to: {EVAL_OUT}")

if __name__ == "__main__":
    main()
