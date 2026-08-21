"""Step 11: Deep Error Analysis for all 4 YOLO26 PPE models.

For each model, runs predictions on the test set and produces:
  - Per-image FP/FN breakdown with class, confidence, bbox size, source file
  - Failure-mode buckets: small object / low confidence / class confusion / missed
  - Visualization grid of the worst images (most errors)
  - JSON + Markdown report under yolo26_ppe/reports/error_analysis/

Usage:
  python 11_error_analysis.py --model s --task detect
  python 11_error_analysis.py --all
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MLFLOW_DB = os.path.join(BASE, "yolo26_ppe", "mlflow", "mlflow.db")
os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{MLFLOW_DB}"
os.environ["MLFLOW_EXPERIMENT_NAME"] = "yolo26_ppe_error_analysis"

from ultralytics import YOLO, settings
import mlflow

settings.update({"mlflow": True})

with open(os.path.join(BASE, "yolo26_ppe", "configs", "train.yaml")) as f:
    TRAIN_CFG = yaml.safe_load(f)

MODELS = TRAIN_CFG["models"]
CLASS_NAMES = ["person", "helmet", "boots", "shoes", "sandals", "harness"]
REPORTS_DIR = os.path.join(BASE, "yolo26_ppe", "reports", "error_analysis")
Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

# Failure-mode thresholds
SMALL_OBJ_PX = 32 * 32          # bbox area below this → "small object"
LOW_CONF = 0.25                 # prediction confidence below this → "low confidence"
IOU_MATCH = 0.5                 # IoU threshold for matching pred ↔ gt
WORST_N_IMAGES = 12             # how many worst images to visualize


# ---------- helpers ----------

def _read_yolo_labels(label_path, img_w, img_h):
    """Read a YOLO label file → list of (cls_id, x1,y1,x2,y2 in pixels)."""
    boxes = []
    if not os.path.exists(label_path):
        return boxes
    with open(label_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            cls = int(parts[0])
            cx, cy, w, h = (float(v) for v in parts[1:5])
            x1 = (cx - w / 2) * img_w
            y1 = (cy - h / 2) * img_h
            x2 = (cx + w / 2) * img_w
            y2 = (cy + h / 2) * img_h
            boxes.append((cls, x1, y1, x2, y2))
    return boxes


def _iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _bbox_area_px(box):
    _, x1, y1, x2, y2 = box
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def _match_preds_to_gt(preds, gts, iou_thr=IOU_MATCH):
    """Greedy match preds → gts by IoU. Returns (matches, false_positives, false_negatives).

    matches: list of (pred, gt, iou)
    false_positives: list of pred (unmatched)
    false_negatives: list of gt  (unmatched)
    Each pred = (cls, x1,y1,x2,y2, conf)
    Each gt   = (cls, x1,y1,x2,y2)
    """
    used_gt = set()
    matches = []
    fps = []
    # Sort preds by confidence desc for greedy matching
    for pred in sorted(preds, key=lambda p: -p[5]):
        p_cls, px1, py1, px2, py2, conf = pred
        p_box = (px1, py1, px2, py2)
        best_iou, best_j = 0.0, -1
        for j, gt in enumerate(gts):
            if j in used_gt:
                continue
            g_cls, *g_box = gt
            iou = _iou(p_box, tuple(g_box))
            if iou > best_iou:
                best_iou, best_j = iou, j
        if best_j >= 0 and best_iou >= iou_thr:
            used_gt.add(best_j)
            matches.append((pred, gts[best_j], best_iou))
        else:
            fps.append(pred)
    fns = [gt for j, gt in enumerate(gts) if j not in used_gt]
    return matches, fps, fns


def _classify_failure(pred_or_gt, mode, img_w, img_h):
    """Bucket a single FP or FN into a failure mode string."""
    _, x1, y1, x2, y2 = pred_or_gt[:5]
    area = _bbox_area_px((None, x1, y1, x2, y2))
    if mode == "fp":
        conf = pred_or_gt[5]
        tags = []
        if area < SMALL_OBJ_PX:
            tags.append("small_object")
        if conf < LOW_CONF:
            tags.append("low_confidence")
        if not tags:
            tags.append("class_confusion" if len(pred_or_gt) > 5 else "spurious")
        return tags
    else:  # fn
        tags = []
        if area < SMALL_OBJ_PX:
            tags.append("missed_small_object")
        else:
            tags.append("missed")
        return tags


# ---------- per-model analysis ----------

def analyze_one(model_key, config):
    print(f"\n{'=' * 70}")
    print(f"Error Analysis: {model_key}")
    print(f"{'=' * 70}")

    best_pt = os.path.join(BASE, config["project"], "run1", "weights", "best.pt")
    if not os.path.exists(best_pt):
        print(f"  ERROR: {best_pt} not found. Train first.")
        return None

    data_yaml = os.path.join(BASE, config["data"])
    with open(data_yaml) as f:
        data_cfg = yaml.safe_load(f)
    data_root = os.path.join(BASE, "yolo26_ppe", os.path.relpath(data_cfg["path"], "yolo26_ppe")) \
        if not os.path.isabs(data_cfg["path"]) else data_cfg["path"]
    # Fallback: data.yaml `path` is already absolute or relative to BASE
    if not os.path.isdir(data_root):
        data_root = os.path.join(BASE, data_cfg["path"])
    test_img_dir = os.path.join(data_root, "images", "test")
    test_lbl_dir = os.path.join(data_root, "labels", "test")
    if not os.path.isdir(test_img_dir):
        print(f"  ERROR: test image dir not found: {test_img_dir}")
        return None

    model = YOLO(best_pt)

    image_files = sorted(
        p for p in Path(test_img_dir).iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    print(f"  Test images: {len(image_files)}")

    per_image = []          # one entry per image with FP/FN counts + tags
    fp_by_class = Counter()
    fn_by_class = Counter()
    confusion = defaultdict(int)   # (gt_cls, pred_cls) → count  (for matched but wrong class)
    failure_tags = Counter()
    worst_images = []       # (n_errors, image_name) — sorted later

    for img_path in image_files:
        stem = img_path.stem
        # Get image size
        from PIL import Image
        with Image.open(img_path) as im:
            img_w, img_h = im.size

        # Ground truth
        gt_path = os.path.join(test_lbl_dir, f"{stem}.txt")
        gts = _read_yolo_labels(gt_path, img_w, img_h)

        # Predict
        results = model.predict(source=str(img_path), verbose=False, save=False, conf=0.001)
        preds = []
        for r in results:
            if r.boxes is None:
                continue
            for b in r.boxes:
                cls = int(b.cls.item())
                x1, y1, x2, y2 = (float(v) for v in b.xyxy[0].tolist())
                conf = float(b.conf.item())
                preds.append((cls, x1, y1, x2, y2, conf))

        matches, fps, fns = _match_preds_to_gt(preds, gts)

        # Class confusion: matched IoU but wrong class
        img_confusion = []
        for pred, gt, iou in matches:
            if pred[0] != gt[0]:
                confusion[(CLASS_NAMES[gt[0]], CLASS_NAMES[pred[0]])] += 1
                img_confusion.append((CLASS_NAMES[gt[0]], CLASS_NAMES[pred[0]], iou))

        img_tags = Counter()
        for fp in fps:
            fp_by_class[CLASS_NAMES[fp[0]]] += 1
            for t in _classify_failure(fp, "fp", img_w, img_h):
                failure_tags[t] += 1
                img_tags[t] += 1
        for fn in fns:
            fn_by_class[CLASS_NAMES[fn[0]]] += 1
            for t in _classify_failure(fn, "fn", img_w, img_h):
                failure_tags[t] += 1
                img_tags[t] += 1

        n_err = len(fps) + len(fns) + len(img_confusion)
        per_image.append({
            "image": str(img_path),
            "stem": stem,
            "n_gt": len(gts),
            "n_pred": len(preds),
            "n_fp": len(fps),
            "n_fn": len(fns),
            "n_class_confusion": len(img_confusion),
            "n_errors": n_err,
            "tags": dict(img_tags),
        })
        worst_images.append((n_err, stem, str(img_path)))

    # Sort worst images
    worst_images.sort(key=lambda x: -x[0])
    top_worst = worst_images[:WORST_N_IMAGES]

    # Build summary
    summary = {
        "model_key": model_key,
        "task": config["task"],
        "n_test_images": len(image_files),
        "total_fp": sum(fp_by_class.values()),
        "total_fn": sum(fn_by_class.values()),
        "fp_by_class": dict(fp_by_class),
        "fn_by_class": dict(fn_by_class),
        "failure_modes": dict(failure_tags),
        "class_confusion_top": [
            {"gt": gt, "pred": pred, "count": cnt}
            for (gt, pred), cnt in sorted(confusion.items(), key=lambda kv: -kv[1])[:15]
        ],
        "worst_images": [
            {"stem": s, "n_errors": n, "path": p} for n, s, p in top_worst
        ],
    }

    # Save JSON
    json_path = os.path.join(REPORTS_DIR, f"error_analysis_{model_key}.json")
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  JSON: {json_path}")

    # Save per-image CSV
    csv_path = os.path.join(REPORTS_DIR, f"error_analysis_{model_key}_per_image.csv")
    with open(csv_path, "w") as f:
        f.write("image,n_gt,n_pred,n_fp,n_fn,n_class_confusion,n_errors,tags\n")
        for r in per_image:
            tags_str = "|".join(f"{k}:{v}" for k, v in r["tags"].items())
            f.write(f"{r['stem']},{r['n_gt']},{r['n_pred']},{r['n_fp']},{r['n_fn']},"
                    f"{r['n_class_confusion']},{r['n_errors']},{tags_str}\n")
    print(f"  CSV : {csv_path}")

    # Visualize worst images
    try:
        viz_dir = os.path.join(REPORTS_DIR, "figures", model_key)
        Path(viz_dir).mkdir(parents=True, exist_ok=True)
        for n_err, stem, img_path in top_worst[:6]:
            model.predict(
                source=img_path,
                save=True,
                project=viz_dir,
                name=stem,
                exist_ok=True,
                conf=0.001,
            )
        print(f"  Viz : {viz_dir} (top {min(6, len(top_worst))} worst)")
    except Exception as e:
        print(f"  Viz skipped: {e}")

    # Log to MLflow
    try:
        os.environ["MLFLOW_RUN"] = f"{model_key}_error_analysis"
        with mlflow.start_run(run_name=f"{model_key}_error_analysis"):
            mlflow.log_param("model_key", model_key)
            mlflow.log_param("n_test_images", len(image_files))
            for k, v in summary.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(f"ea_{k}", v)
            for cls, c in fp_by_class.items():
                mlflow.log_metric(f"ea_fp_{cls}", c)
            for cls, c in fn_by_class.items():
                mlflow.log_metric(f"ea_fn_{cls}", c)
            for tag, c in failure_tags.items():
                mlflow.log_metric(f"ea_tag_{tag}", c)
    except Exception as e:
        print(f"  MLflow log warning: {e}")

    # Print summary
    print(f"\n  Total FP: {summary['total_fp']},  Total FN: {summary['total_fn']}")
    print(f"  Failure modes: {dict(failure_tags)}")
    if confusion:
        print(f"  Top confusions:")
        for (gt, pred), cnt in sorted(confusion.items(), key=lambda kv: -kv[1])[:5]:
            print(f"    {gt} → {pred}: {cnt}")
    print(f"  Worst images (top 5):")
    for n_err, stem, _ in top_worst[:5]:
        print(f"    {stem}: {n_err} errors")

    del model
    import torch
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return summary


# ---------- report ----------

def generate_markdown_report(all_summaries):
    lines = [
        "# Deep Error Analysis Report — YOLO26 PPE\n",
        f"Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"Models: {', '.join(all_summaries.keys())}\n",
        f"Classes: {', '.join(CLASS_NAMES)}\n",
    ]

    # 1. Overall
    lines.append("\n## 1. Overall Error Counts\n")
    lines.append("| Model | Test imgs | FP | FN | Class confusion |\n")
    lines.append("|-------|-----------|----|----|-----------------|\n")
    for k, s in all_summaries.items():
        lines.append(f"| {k} | {s['n_test_images']} | {s['total_fp']} | {s['total_fn']} | "
                     f"{len(s['class_confusion_top'])} |\n")

    # 2. Failure modes
    lines.append("\n## 2. Failure Modes (bucketed)\n")
    all_tags = sorted({t for s in all_summaries.values() for t in s["failure_modes"]})
    lines.append("| Model | " + " | ".join(all_tags) + " |\n")
    lines.append("|-------|" + "|".join(["------"] * len(all_tags)) + "|\n")
    for k, s in all_summaries.items():
        row = f"| {k} |"
        for t in all_tags:
            row += f" {s['failure_modes'].get(t, 0)} |"
        lines.append(row + "\n")

    # 3. FP/FN by class
    lines.append("\n## 3. False Positives by Class\n")
    lines.append("| Model | " + " | ".join(CLASS_NAMES) + " |\n")
    lines.append("|-------|" + "|".join(["---"] * len(CLASS_NAMES)) + "|\n")
    for k, s in all_summaries.items():
        row = f"| {k} |"
        for cls in CLASS_NAMES:
            row += f" {s['fp_by_class'].get(cls, 0)} |"
        lines.append(row + "\n")

    lines.append("\n## 4. False Negatives by Class\n")
    lines.append("| Model | " + " | ".join(CLASS_NAMES) + " |\n")
    lines.append("|-------|" + "|".join(["---"] * len(CLASS_NAMES)) + "|\n")
    for k, s in all_summaries.items():
        row = f"| {k} |"
        for cls in CLASS_NAMES:
            row += f" {s['fn_by_class'].get(cls, 0)} |"
        lines.append(row + "\n")

    # 5. Class confusion
    lines.append("\n## 5. Top Class Confusions (gt → pred)\n")
    for k, s in all_summaries.items():
        lines.append(f"\n### {k}\n")
        if not s["class_confusion_top"]:
            lines.append("None detected.\n")
            continue
        lines.append("| GT | Pred | Count |\n|----|------|-------|\n")
        for c in s["class_confusion_top"][:10]:
            lines.append(f"| {c['gt']} | {c['pred']} | {c['count']} |\n")

    # 6. Worst images
    lines.append("\n## 6. Worst Images (most errors)\n")
    for k, s in all_summaries.items():
        lines.append(f"\n### {k}\n")
        lines.append("| Image | Errors |\n|-------|--------|\n")
        for w in s["worst_images"][:10]:
            lines.append(f"| {w['stem']} | {w['n_errors']} |\n")

    # 7. Recommendations
    lines.append("\n## 7. Recommendations\n")
    # Aggregate FN by class across models
    agg_fn = Counter()
    for s in all_summaries.values():
        for cls, c in s["fn_by_class"].items():
            agg_fn[cls] += c
    worst_cls = agg_fn.most_common(3)
    for cls, c in worst_cls:
        lines.append(f"- **{cls}** has {c} total missed detections (FN) across models — ")
        if c > 50:
            lines.append("collect more training data and verify annotation quality.\n")
        else:
            lines.append("consider stronger augmentation or higher resolution (imgsz=960).\n")

    agg_small = sum(s["failure_modes"].get("missed_small_object", 0) for s in all_summaries.values())
    if agg_small > 20:
        lines.append(f"\n- **Small objects** account for {agg_small} missed detections. ")
        lines.append("Try `imgsz=960` or multi-scale training.\n")

    agg_conf = sum(s["failure_modes"].get("class_confusion", 0) for s in all_summaries.values())
    if agg_conf > 10:
        lines.append(f"\n- **Class confusion** detected ({agg_conf} cases). ")
        lines.append("Inspect confusion matrix and consider merging similar classes (e.g. boots↔shoes).\n")

    return "".join(lines)


# ---------- main ----------

def main():
    parser = argparse.ArgumentParser(description="Deep Error Analysis for YOLO26 PPE")
    parser.add_argument("--model", choices=["n", "s"], help="Model size")
    parser.add_argument("--task", choices=["detect", "segment"], help="Task type")
    parser.add_argument("--all", action="store_true", help="Analyze all 4 models")
    args = parser.parse_args()

    all_summaries = {}

    if args.all:
        for key, config in MODELS.items():
            s = analyze_one(key, config)
            if s:
                all_summaries[key] = s
    elif args.model and args.task:
        key = f"{args.model}_{'seg' if args.task == 'segment' else 'detect'}"
        if key not in MODELS:
            print(f"Unknown model: {key}")
            sys.exit(1)
        s = analyze_one(key, MODELS[key])
        if s:
            all_summaries[key] = s
    else:
        parser.print_help()
        sys.exit(1)

    if all_summaries:
        report = generate_markdown_report(all_summaries)
        report_path = os.path.join(REPORTS_DIR, "error_analysis_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n{'=' * 70}")
        print(f"Report saved: {report_path}")
        print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
