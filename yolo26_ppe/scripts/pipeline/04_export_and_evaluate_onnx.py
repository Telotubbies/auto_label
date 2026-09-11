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
ONNX_DIR = BASE / "artifacts" / "onnx_models" / "production"
ONNX_DIR.mkdir(parents=True, exist_ok=True)
EVAL_OUT = BASE / "artifacts" / "evaluation" / "yolo" / f"production_{VERSION}" / "onnx"
EVAL_OUT.mkdir(parents=True, exist_ok=True)

MODELS = {
    "medium_detection": {
        "weights": BASE / "yolo26_ppe/models/production/medium_detection/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "task": "detect",
    },
    "medium_segmentation": {
        "weights": BASE / "yolo26_ppe/models/production/medium_segmentation/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
    },
    "small_detection": {
        "weights": BASE / "yolo26_ppe/models/production/small_detection/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_detect_data/data.yaml",
        "task": "detect",
    },
    "small_segmentation": {
        "weights": BASE / "yolo26_ppe/models/production/small_segmentation/stage_2_final_fine_tuning/weights/best.pt",
        "data": "/tmp/yolo_seg_data/data.yaml",
        "task": "segment",
    },
}

NAMES = ["person", "helmet", "closed footwear", "harness"]

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
    """Extract box (B) and, for segment tasks, mask (M) metrics.

    Uses the current Ultralytics API: results.box.map, .map50, .map75,
    .mp, .mr, .p[i], .r[i], .ap50[i], .ap[i]; same shape on results.seg
    for segmentation. See ultralytics/utils/metrics.py and the val mode
    docs for the property names.
    """
    metrics = {}
    # Box (B) mean metrics — use Ultralytics' own aggregated values
    try:
        metrics["precision"] = float(results.box.mp)
        metrics["recall"] = float(results.box.mr)
        metrics["mAP50"] = float(results.box.map50)
        metrics["mAP75"] = float(results.box.map75)
        metrics["mAP50-95"] = float(results.box.map)
    except Exception as e:
        print(f"box metric error: {e}")
    # Box (B) per-class metrics
    try:
        names = results.names
        pc = {}
        for i, n in names.items():
            pc[n] = {
                "P": float(results.box.p[i]) if i < len(results.box.p) else None,
                "R": float(results.box.r[i]) if i < len(results.box.r) else None,
                "mAP50": float(results.box.ap50[i]) if i < len(results.box.ap50) else None,
                "mAP50-95": float(results.box.ap[i]) if i < len(results.box.ap) else None,
            }
        metrics["per_class"] = pc
    except Exception as e:
        print(f"per-class box error: {e}")
    # Mask (M) metrics for segmentation
    if task == "segment":
        try:
            metrics["mask_precision"] = float(results.seg.mp)
            metrics["mask_recall"] = float(results.seg.mr)
            metrics["mask_mAP50"] = float(results.seg.map50)
            metrics["mask_mAP75"] = float(results.seg.map75)
            metrics["mask_mAP50-95"] = float(results.seg.map)
        except Exception as e:
            print(f"mask mean metric error: {e}")
        try:
            seg_pc = {}
            for i, n in names.items():
                seg_pc[n] = {
                    "P": float(results.seg.p[i]) if i < len(results.seg.p) else None,
                    "R": float(results.seg.r[i]) if i < len(results.seg.r) else None,
                    "mAP50": float(results.seg.ap50[i]) if i < len(results.seg.ap50) else None,
                    "mAP50-95": float(results.seg.ap[i]) if i < len(results.seg.ap) else None,
                }
            metrics["mask_per_class"] = seg_pc
        except Exception as e:
            print(f"per-class mask error: {e}")
    try:
        speed = results.speed
        metrics["inference_ms"] = float(speed.get("inference", 0))
    except Exception:
        pass
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
    print(f"\n{'='*100}")
    print("COMPARISON: PyTorch vs ONNX (GPU) — Box (B) metrics")
    print(f"{'='*100}")
    print(f"{'Model':<18} {'Engine':<8} {'mAP50':>7} {'mAP75':>7} {'mAP50-95':>9} {'P':>7} {'R':>7} {'Size(MB)':>9} {'Lat(ms)':>8}")
    print("-"*100)
    for key, r in all_results.items():
        for engine in ["pytorch", "onnx"]:
            m = r[engine]
            print(f"{key:<18} {engine:<8} {m.get('mAP50',0):>7.3f} {m.get('mAP75',0):>7.3f} {m.get('mAP50-95',0):>9.3f} {m.get('precision',0):>7.3f} {m.get('recall',0):>7.3f} {m.get('model_size_MB',0):>9.1f} {m.get('latency_ms',0):>8.1f}")
    # Mask (M) metrics for segmentation models
    seg_models = {k: r for k, r in all_results.items() if "mask_mAP50" in r.get("pytorch", {})}
    if seg_models:
        print(f"\n--- Mask (M) metrics for segmentation models ---")
        print(f"{'Model':<18} {'Engine':<8} {'mAP50':>7} {'mAP75':>7} {'mAP50-95':>9} {'P':>7} {'R':>7}")
        for key, r in seg_models.items():
            for engine in ["pytorch", "onnx"]:
                m = r[engine]
                print(f"{key:<18} {engine:<8} {m.get('mask_mAP50',0):>7.3f} {m.get('mask_mAP75',0):>7.3f} {m.get('mask_mAP50-95',0):>9.3f} {m.get('mask_precision',0):>7.3f} {m.get('mask_recall',0):>7.3f}")
    print(f"\nResults saved to: {EVAL_OUT}")

if __name__ == "__main__":
    main()
