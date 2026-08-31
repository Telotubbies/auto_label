"""Step 4: Evaluate trained models on test set.

Usage:
  python 04_evaluate.py --model n --task detect
  python 04_evaluate.py --all
"""
import argparse
import os
import sys
import json
import yaml

os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MLFLOW_DB = os.path.join(BASE, "yolo26_ppe", "mlflow", "mlflow.db")
os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{MLFLOW_DB}"
os.environ["MLFLOW_EXPERIMENT_NAME"] = "yolo26_ppe"

from ultralytics import YOLO, settings
import mlflow

settings.update({"mlflow": True})

with open(os.path.join(BASE, "yolo26_ppe", "configs", "train.yaml")) as f:
    TRAIN_CFG = yaml.safe_load(f)

MODELS = TRAIN_CFG["models"]
CLASS_NAMES = ["person", "helmet", "boots", "shoes", "sandals", "harness"]


def evaluate_one(model_key, config):
    """Evaluate a single model on test set."""
    print(f"\n{'=' * 70}")
    print(f"Evaluating: {model_key}")
    print(f"{'=' * 70}")

    best_pt = os.path.join(BASE, config["project"], "run1", "weights", "best.pt")
    if not os.path.exists(best_pt):
        # Ultralytics may place runs under runs/detect/ when project is relative
        fallback = os.path.join(BASE, "yolo26_ppe", "runs", "detect", "run1", "weights", "best.pt")
        if os.path.exists(fallback):
            best_pt = fallback
        else:
            print(f"  ERROR: {best_pt} not found (also checked {fallback}). Train first.")
            return None

    model = YOLO(best_pt)
    os.environ["MLFLOW_RUN"] = f"{model_key}_eval"

    # Run validation on test split
    results = model.val(
        data=os.path.join(BASE, config["data"]),
        split="test",
        project=config["project"],
        name="eval_test",
        plots=True,
        exist_ok=True,
    )

    # Extract metrics
    metrics = {
        "model_key": model_key,
        "task": config["task"],
    }

    try:
        metrics["mAP50"] = float(results.box.map50)
        metrics["mAP50_95"] = float(results.box.map)
        metrics["precision"] = float(results.box.mp)
        metrics["recall"] = float(results.box.mr)
        if config["task"] == "segment" and hasattr(results, "seg"):
            metrics["mask_mAP50"] = float(results.seg.map50)
            metrics["mask_mAP50_95"] = float(results.seg.map)
            metrics["mask_precision"] = float(results.seg.mp)
            metrics["mask_recall"] = float(results.seg.mr)
    except Exception as e:
        print(f"  Metric extraction warning: {e}")

    # Per-class metrics
    per_class_failures = 0
    try:
        names = results.names
        per_class = {}
        for i, name in names.items():
            if i < len(results.box.maps):
                p_cls = float(results.box.p[i]) if hasattr(results.box, 'p') and i < len(results.box.p) else 0
                r_cls = float(results.box.r[i]) if hasattr(results.box, 'r') and i < len(results.box.r) else 0
                f1_cls = 2 * p_cls * r_cls / (p_cls + r_cls) if (p_cls + r_cls) > 0 else 0
                per_class[name] = {
                    "mAP50": float(results.box.ap50[i]) if i < len(results.box.ap50) else 0,
                    "mAP50_95": float(results.box.maps[i]),
                    "precision": p_cls,
                    "recall": r_cls,
                    "f1": f1_cls,
                }
        metrics["per_class"] = per_class
    except Exception as e:
        per_class_failures += 1
        print(f"  WARNING: per-class metric extraction failed: {e}")
    if per_class_failures:
        print(f"  WARNING: {per_class_failures} per-class metric extraction failure(s).")

    # F1 score (overall)
    try:
        p = metrics.get("precision", 0) or 0
        r = metrics.get("recall", 0) or 0
        metrics["f1"] = 2 * p * r / (p + r) if (p + r) > 0 else 0
    except Exception:
        pass

    # Confusion matrix path (Ultralytics generates this during val with plots=True)
    cm_path = os.path.join(BASE, config["project"], "eval_test", "confusion_matrix.png")
    if os.path.exists(cm_path):
        metrics["confusion_matrix_path"] = cm_path
    cm_norm_path = os.path.join(BASE, config["project"], "eval_test", "confusion_matrix_normalized.png")
    if os.path.exists(cm_norm_path):
        metrics["confusion_matrix_normalized_path"] = cm_norm_path

    # Inference speed — measure on a single image with warmup
    import time, torch, glob
    if torch.cuda.is_available():
        test_dir = os.path.join(BASE, "yolo26_ppe/data/yolo_detect/images/test")
        if os.path.exists(test_dir):
            images = sorted(glob.glob(os.path.join(test_dir, "*.*")))
            if images:
                sample_img = images[0]
                # Warmup (first run includes model load / CUDA init overhead)
                model.predict(source=sample_img, verbose=False, save=False)
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                t0 = time.time()
                for _ in range(10):
                    model.predict(source=sample_img, verbose=False, save=False)
                if torch.cuda.is_available():
                    torch.cuda.synchronize()
                metrics["inference_ms"] = (time.time() - t0) / 10 * 1000
            else:
                print("  WARNING: no images found in test dir for inference timing.")
        else:
            print(f"  WARNING: test dir {test_dir} not found for inference timing.")

    # Log to MLflow
    mlflow_failures = 0
    try:
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                mlflow.log_metric(f"test_{k}", v)
    except Exception as e:
        mlflow_failures += 1
        print(f"  WARNING: MLflow logging failed: {e}")
    if mlflow_failures:
        print(f"  WARNING: {mlflow_failures} MLflow logging failure(s).")

    # Print summary
    print(f"\n  Results:")
    for k, v in metrics.items():
        if isinstance(v, (int, float)):
            print(f"    {k:20s}: {v:.4f}")
        elif k == "per_class":
            print(f"    per_class:")
            for cls_name, cls_metrics in v.items():
                print(f"      {cls_name:15s}: mAP50={cls_metrics['mAP50']:.3f} mAP50-95={cls_metrics['mAP50_95']:.3f}")

    # Save JSON
    eval_path = os.path.join(BASE, config["project"], "eval_results.json")
    with open(eval_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Saved: {eval_path}")

    del model
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["n", "s"])
    parser.add_argument("--task", choices=["detect", "segment"])
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    all_results = {}

    if args.all:
        for key, config in MODELS.items():
            r = evaluate_one(key, config)
            if r:
                all_results[key] = r
    elif args.model and args.task:
        key = f"{args.model}_{'seg' if args.task == 'segment' else 'detect'}"
        r = evaluate_one(key, MODELS[key])
        if r:
            all_results[key] = r
    else:
        parser.print_help()
        sys.exit(1)

    # Save combined results
    if all_results:
        combined_path = os.path.join(BASE, "yolo26_ppe", "reports", "eval_all.json")
        os.makedirs(os.path.dirname(combined_path), exist_ok=True)
        with open(combined_path, "w") as f:
            json.dump(all_results, f, indent=2)
        print(f"\nCombined results: {combined_path}")


if __name__ == "__main__":
    main()
