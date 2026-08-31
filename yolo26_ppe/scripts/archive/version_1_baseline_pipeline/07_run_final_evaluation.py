#!/usr/bin/env python3
"""Final evaluation of all completed models on test set."""
import json
from pathlib import Path
from ultralytics import YOLO
import mlflow

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
mlflow.set_tracking_uri(f"sqlite:///{BASE}/mlflow/mlflow.db")
mlflow.set_experiment("yolo26_ppe_final_eval")

models = {
    "n_detect": {
        "weights": BASE / "models/yolo26n_detect_v2/run1/weights/best.pt",
        "data": BASE / "data/yolo_detect_v2/data.yaml",
        "task": "detect",
    },
    "s_detect": {
        "weights": BASE / "models/yolo26s_detect_v2/run1/weights/best.pt",
        "data": BASE / "data/yolo_detect_v2/data.yaml",
        "task": "detect",
    },
    "n_seg": {
        "weights": BASE / "models/yolo26n_seg_v2/run1/weights/best.pt",
        "data": BASE / "data/yolo_segment_v2/data.yaml",
        "task": "segment",
    },
    "s_seg": {
        "weights": BASE / "models/yolo26s_seg_v2/run1/weights/best.pt",
        "data": BASE / "data/yolo_segment_v2/data.yaml",
        "task": "segment",
    },
}

all_results = {}
for name, cfg in models.items():
    print(f"\n{'='*60}")
    print(f"  Evaluating {name} on test set")
    print(f"{'='*60}")

    model = YOLO(str(cfg["weights"]))
    results = model.val(
        data=str(cfg["data"]),
        split="test",
        imgsz=640,
        device="0",
        project=str(cfg["weights"].parent.parent),
        name="eval_test_final",
        exist_ok=True,
    )

    metrics = {}
    if hasattr(results, "results_dict"):
        for k, v in results.results_dict.items():
            metrics[k] = float(v)
    if hasattr(results, "box"):
        metrics["box_mAP50"] = float(results.box.map50)
        metrics["box_mAP50_95"] = float(results.box.map)
        metrics["box_precision"] = float(results.box.mp)
        metrics["box_recall"] = float(results.box.mr)
    if hasattr(results, "mask") and results.mask is not None:
        metrics["mask_mAP50"] = float(results.mask.map50)
        metrics["mask_mAP50_95"] = float(results.mask.map)
        metrics["mask_precision"] = float(results.mask.mp)
        metrics["mask_recall"] = float(results.mask.mr)

    # Per-class
    if hasattr(results, "names"):
        names = results.names
        if hasattr(results.box, "ap50"):
            for i, cls_name in names.items():
                metrics[f"box_mAP50_{cls_name}"] = float(results.box.ap50[i])
        if hasattr(results, "mask") and results.mask is not None and hasattr(results.mask, "ap50"):
            for i, cls_name in names.items():
                metrics[f"mask_mAP50_{cls_name}"] = float(results.mask.ap50[i])

    all_results[name] = metrics

    # Print summary
    bmap50 = metrics.get("box_mAP50", metrics.get("metrics/mAP50(B)", 0))
    bmap5095 = metrics.get("box_mAP50_95", metrics.get("metrics/mAP50-95(B)", 0))
    bp = metrics.get("box_precision", metrics.get("metrics/precision(B)", 0))
    br = metrics.get("box_recall", metrics.get("metrics/recall(B)", 0))
    print(f"  Box:  mAP50={bmap50:.4f}  mAP50-95={bmap5095:.4f}  P={bp:.4f}  R={br:.4f}")
    if "mask_mAP50" in metrics:
        mmap50 = metrics["mask_mAP50"]
        mmap5095 = metrics["mask_mAP50_95"]
        mp = metrics["mask_precision"]
        mr = metrics["mask_recall"]
        print(f"  Mask: mAP50={mmap50:.4f}  mAP50-95={mmap5095:.4f}  P={mp:.4f}  R={mr:.4f}")

    # Log to MLflow
    with mlflow.start_run(run_name=f"final_eval_{name}"):
        mlflow.set_tags({
            "model_variant": name,
            "eval_type": "test_set",
            "task": cfg["task"],
            "optimizer": "SGD",
            "version": "v2",
        })
        for k, v in metrics.items():
            safe_k = k.replace("(", "").replace(")", "").replace("/", "_")
            mlflow.log_metric(safe_k, float(v))

# Save
output_file = BASE / "report" / "final_eval_results.json"
output_file.parent.mkdir(parents=True, exist_ok=True)
with open(output_file, "w") as f:
    json.dump(all_results, f, indent=2)

print(f"\n{'='*60}")
print(f"  All evaluations complete!")
print(f"  Results saved: {output_file}")
print(f"{'='*60}")
print(json.dumps(all_results, indent=2))
