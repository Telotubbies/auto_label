"""Step 7: Export models for production (ONNX, TensorRT, TorchScript).

Usage:
  python 07_export.py --model n --task detect
  python 07_export.py --all
"""
import argparse
import os
import sys
import json
import yaml

os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with open(os.path.join(BASE, "yolo26_ppe", "configs", "train.yaml")) as f:
    TRAIN_CFG = yaml.safe_load(f)

MODELS = TRAIN_CFG["models"]

# Export formats — ONNX is most portable, TensorRT for NVIDIA, TorchScript for PyTorch
EXPORT_FORMATS = ["onnx", "torchscript"]  # TensorRT only on NVIDIA


def export_one(model_key, config):
    """Export a single model to production formats."""
    print(f"\n{'=' * 70}")
    print(f"Exporting: {model_key}")
    print(f"{'=' * 70}")

    best_pt = os.path.join(BASE, config["project"], "run1", "weights", "best.pt")
    if not os.path.exists(best_pt):
        # Fallback: runs/detect or runs/segment default location
        task_subdir = "detect" if config.get("task") == "detect" else "segment"
        fallback = os.path.join(BASE, "runs", task_subdir, "run1", "weights", "best.pt")
        if os.path.exists(fallback):
            best_pt = fallback
        else:
            print(f"  ERROR: {best_pt} not found (also checked {fallback}). Train first.")
            return

    from ultralytics import YOLO
    model = YOLO(best_pt)

    export_dir = os.path.join(BASE, config["project"], "export")
    os.makedirs(export_dir, exist_ok=True)

    results = {}
    for fmt in EXPORT_FORMATS:
        try:
            print(f"\n  Exporting {fmt}...")
            # dynamic=True only valid for ONNX; TorchScript doesn't support it
            export_kwargs = dict(format=fmt, imgsz=640, simplify=True)
            if fmt == "onnx":
                export_kwargs["dynamic"] = True
            path = model.export(**export_kwargs)
            results[fmt] = {"path": path, "size_mb": os.path.getsize(path) / 1e6 if os.path.exists(path) else 0}
            print(f"    → {path} ({results[fmt]['size_mb']:.1f} MB)")
        except Exception as e:
            print(f"    FAILED: {e}")
            results[fmt] = {"error": str(e)}

    # Save export info
    info_path = os.path.join(export_dir, "export_info.json")
    with open(info_path, "w") as f:
        json.dump({"model_key": model_key, "formats": results}, f, indent=2)

    print(f"\n  Export info: {info_path}")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["n", "s"])
    parser.add_argument("--task", choices=["detect", "segment"])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if args.all:
        for key, config in MODELS.items():
            export_one(key, config)
    elif args.model and args.task:
        key = f"{args.model}_{'seg' if args.task == 'segment' else 'detect'}"
        if key not in MODELS:
            print(f"Unknown: {key}")
            sys.exit(1)
        export_one(key, MODELS[key])
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
