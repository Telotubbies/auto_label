#!/usr/bin/env python3
"""Analyze blurred inference results, pick good/bad cases, create montages, generate LaTeX tables."""
import json
import cv2
import numpy as np
from pathlib import Path
from skimage.color import lab2rgb, rgb2lab
from sklearn.cluster import KMeans

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/onnx_inference_results/blur_robustness")
OUT = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe/reports/source/figures/blur_robustness")
OUT.mkdir(parents=True, exist_ok=True)

MODELS = ["medium_detection", "medium_segmentation"]
CLASSES = ["person", "helmet", "closed footwear", "harness"]

# SAM-style colors
def generate_colors(n_colors=256, n_samples=5000):
    np.random.seed(42)
    rgb = np.random.rand(n_samples, 3)
    lab = rgb2lab(rgb.reshape(1, -1, 3)).reshape(-1, 3)
    kmeans = KMeans(n_clusters=n_colors, n_init=10)
    kmeans.fit(lab)
    centers_lab = kmeans.cluster_centers_
    colors_rgb = lab2rgb(centers_lab.reshape(1, -1, 3)).reshape(-1, 3)
    return np.clip(colors_rgb, 0, 1)

_SAM = generate_colors(128, 5000)
CIDX = {0:0, 1:10, 2:25, 3:60}

def class_color_bgr(c):
    col = _SAM[CIDX.get(c, c) % len(_SAM)]
    return (int(col[2]*255), int(col[0]*255), int(col[1]*255))

# Load all summaries
summaries = {}
for m in MODELS:
    s = json.load(open(BASE / m / "_summary.json"))
    summaries[m] = s

# Aggregate per-image stats across all models
all_images = {}
for m in MODELS:
    for r in summaries[m]["results"]:
        img = r["image"]
        if img not in all_images:
            all_images[img] = {}
        all_images[img][m] = r

# Score: good = high total detections + diverse classes; bad = 0-1 detections or very few classes
img_scores = []
for img, models in all_images.items():
    total_det = sum(r["n_det"] for r in models.values())
    all_classes = set()
    for r in models.values():
        all_classes.update(r["classes"].keys())
    n_classes = len(all_classes)
    avg_latency = np.mean([r["latency_ms"] for r in models.values()])
    img_scores.append({
        "image": img,
        "total_det": total_det,
        "n_classes": n_classes,
        "avg_latency": avg_latency,
        "per_model": {m: models.get(m, {}) for m in MODELS},
    })

# Sort: good = high total_det + many classes; bad = low total_det
good = sorted(img_scores, key=lambda x: (-x["n_classes"], -x["total_det"]))[:6]
bad = sorted(img_scores, key=lambda x: (x["total_det"], x["n_classes"]))[:6]

print("=== GOOD cases (many detections, many classes) ===")
for g in good:
    print(f"  {g['image'][:60]}... det={g['total_det']} cls={g['n_classes']} lat={g['avg_latency']:.1f}ms")

print("\n=== BAD cases (few detections) ===")
for b in bad:
    print(f"  {b['image'][:60]}... det={b['total_det']} cls={b['n_classes']} lat={b['avg_latency']:.1f}ms")

# Create montages
THUMB_W = 480
THUMB_H = 320

def resize_pad(img, tw, th):
    h, w = img.shape[:2]
    r = min(tw/w, th/h)
    nw, nh = int(w*r), int(h*r)
    img = cv2.resize(img, (nw, nh))
    pw, ph = tw-nw, th-nh
    return cv2.copyMakeBorder(img, ph//2, ph-ph//2, pw//2, pw-pw//2,
                              cv2.BORDER_CONSTANT, value=(255,255,255))

def make_montage(cases, title, filename, per_model=False):
    """Create montage: if per_model, show 4 models per image; else show 1 model per image."""
    if per_model:
        # For each case, show 2 model outputs side by side
        # Layout: 2 cases × 2 models = 4 thumbs, 2 cols × 2 rows
        thumbs = []
        for c in cases[:2]:  # top 2 cases
            for m in MODELS:
                p = BASE / m / (Path(c["image"]).stem + ".jpg")
                if not p.exists():
                    continue
                img = cv2.imread(str(p))
                if img is None:
                    continue
                img = resize_pad(img, THUMB_W, THUMB_H)
                # Add label
                cv2.rectangle(img, (0, 0), (THUMB_W, 24), (255,255,255), -1)
                r = c["per_model"].get(m, {})
                lbl = f"[{m}] det={r.get('n_det',0)} {r.get('classes',{})}"
                cv2.putText(img, lbl, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0,0,0), 1)
                thumbs.append(img)
        while len(thumbs) < 4:
            thumbs.append(np.full((THUMB_H, THUMB_W, 3), 255, dtype=np.uint8))
        # 2 cols × 2 rows
        rows = [np.hstack(thumbs[i:i+2]) for i in range(0, 4, 2)]
        grid = np.vstack(rows)
    else:
        # Show 6 cases for best model (m_detect)
        thumbs = []
        for c in cases[:6]:
            p = BASE / "medium_detection" / (Path(c["image"]).stem + ".jpg")
            if not p.exists():
                continue
            img = cv2.imread(str(p))
            if img is None:
                continue
            img = resize_pad(img, THUMB_W, THUMB_H)
            cv2.rectangle(img, (0, 0), (THUMB_W, 24), (255,255,255), -1)
            lbl = f"det={c['total_det']} cls={c['n_classes']} {c['per_model'].get('medium_detection',{}).get('classes',{})}"
            cv2.putText(img, lbl, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,0), 1)
            thumbs.append(img)
        while len(thumbs) < 6:
            thumbs.append(np.full((THUMB_H, THUMB_W, 3), 255, dtype=np.uint8))
        # 3 cols × 2 rows
        rows = [np.hstack(thumbs[i:i+3]) for i in range(0, 6, 3)]
        grid = np.vstack(rows)
    # Title bar
    tb = np.full((30, grid.shape[1], 3), 240, dtype=np.uint8)
    cv2.putText(tb, title, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 2)
    grid = np.vstack([tb, grid])
    out = OUT / filename
    cv2.imwrite(str(out), grid, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"Saved: {out} ({grid.shape[1]}x{grid.shape[0]})")
    return out

# Good montage: 2 models × 2 best cases
make_montage(good, "Good cases — 2 models x 2 images (m_detect, m_seg per row)",
             "blurred_good_montage.jpg", per_model=True)

# Bad montage: 2 models × 2 worst cases
make_montage(bad, "Bad cases — 2 models x 2 images (low detection count)",
             "blurred_bad_montage.jpg", per_model=True)

# Also per-model summary montages (6 images each)
for m in MODELS:
    cases_sorted = sorted(img_scores, key=lambda x: -x["per_model"].get(m, {}).get("n_det", 0))
    thumbs = []
    for c in cases_sorted[:6]:
        p = BASE / m / (Path(c["image"]).stem + ".jpg")
        if not p.exists():
            continue
        img = cv2.imread(str(p))
        if img is None:
            continue
        img = resize_pad(img, THUMB_W, THUMB_H)
        r = c["per_model"].get(m, {})
        cv2.rectangle(img, (0, 0), (THUMB_W, 24), (255,255,255), -1)
        lbl = f"det={r.get('n_det',0)} {r.get('classes',{})}"
        cv2.putText(img, lbl, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,0), 1)
        thumbs.append(img)
    while len(thumbs) < 6:
        thumbs.append(np.full((THUMB_H, THUMB_W, 3), 255, dtype=np.uint8))
    rows = [np.hstack(thumbs[i:i+3]) for i in range(0, 6, 3)]
    grid = np.vstack(rows)
    tb = np.full((30, grid.shape[1], 3), 240, dtype=np.uint8)
    cv2.putText(tb, f"{m} — top 6 detections on blurred set", (10, 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,0), 2)
    grid = np.vstack([tb, grid])
    out = OUT / f"blurred_{m}_top6.jpg"
    cv2.imwrite(str(out), grid, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"Saved: {out}")

# Generate aggregate statistics
print("\n=== Aggregate Statistics ===")
for m in MODELS:
    s = summaries[m]
    dets = [r["n_det"] for r in s["results"]]
    lats = [r["latency_ms"] for r in s["results"]]
    all_cls = {}
    for r in s["results"]:
        for cn, cnt in r["classes"].items():
            all_cls[cn] = all_cls.get(cn, 0) + cnt
    print(f"\n{m}:")
    print(f"  images: {s['n_images']}")
    print(f"  avg latency: {s['avg_latency_ms']:.1f} ms (std={np.std(lats):.1f})")
    print(f"  total detections: {sum(dets)}")
    print(f"  avg det/image: {np.mean(dets):.1f} (std={np.std(dets):.1f})")
    print(f"  min/max det: {min(dets)}/{max(dets)}")
    print(f"  class distribution: {all_cls}")

# Save aggregate stats
agg = {}
for m in MODELS:
    s = summaries[m]
    dets = [r["n_det"] for r in s["results"]]
    lats = [r["latency_ms"] for r in s["results"]]
    all_cls = {}
    for r in s["results"]:
        for cn, cnt in r["classes"].items():
            all_cls[cn] = all_cls.get(cn, 0) + cnt
    agg[m] = {
        "n_images": s["n_images"],
        "avg_latency_ms": round(np.mean(lats), 1),
        "std_latency_ms": round(np.std(lats), 1),
        "min_latency_ms": round(min(lats), 1),
        "max_latency_ms": round(max(lats), 1),
        "p95_latency_ms": round(np.percentile(lats, 95), 1),
        "total_detections": sum(dets),
        "avg_det_per_img": round(np.mean(dets), 1),
        "std_det_per_img": round(np.std(dets), 1),
        "min_det": min(dets),
        "max_det": max(dets),
        "class_distribution": all_cls,
        "images_with_zero_det": sum(1 for d in dets if d == 0),
    }
json.dump(agg, open(OUT / "blurred_aggregate_stats.json", "w"), indent=2)
print(f"\nSaved aggregate stats to {OUT / 'blurred_aggregate_stats.json'}")

# Generate LaTeX table
print("\n=== LaTeX Table ===")
latex = r"""\begin{table}[H]
\centering
\begin{tabular}{lrrrrrrr}
\toprule
\textbf{Model} & \textbf{Imgs} & \textbf{Avg lat} & \textbf{Std lat} & \textbf{Total det} & \textbf{Avg det/img} & \textbf{Zero-det} & \textbf{P95 lat} \\
 &  & (ms) & (ms) &  &  & (imgs) & (ms) \\
\midrule
"""
for m in MODELS:
    a = agg[m]
    latex += f"{m} & {a['n_images']} & {a['avg_latency_ms']} & {a['std_latency_ms']} & {a['total_detections']} & {a['avg_det_per_img']} & {a['images_with_zero_det']} & {a['p95_latency_ms']} \\\\\n"
latex += r"""\bottomrule
\end{tabular}
\caption{Inference results on blurred dataset (48 images) using ONNX — latency and detection count}
\label{tab:blurred_onnx_results}
\end{table}"""

# Class distribution table
latex_cls = r"""\begin{table}[H]
\centering
\begin{tabular}{lrrrrr}
\toprule
\textbf{Model} & \textbf{person} & \textbf{helmet} & \textbf{closed footwear} & \textbf{harness} & \textbf{Total} \\
\midrule
"""
for m in MODELS:
    a = agg[m]
    cd = a["class_distribution"]
    total = sum(cd.values())
    latex_cls += f"{m} & {cd.get('person',0)} & {cd.get('helmet',0)} & {cd.get('closed footwear',0)} & {cd.get('harness',0)} & {total} \\\\\n"
latex_cls += r"""\bottomrule
\end{tabular}
\caption{Class distribution of detections on blurred dataset (48 images) using ONNX}
\label{tab:blurred_class_dist}
\end{table}"""

with open(OUT / "blurred_latex_tables.tex", "w") as f:
    f.write(latex + "\n\n" + latex_cls)
print(f"Saved LaTeX tables to {OUT / 'blurred_latex_tables.tex'}")
print("\n--- LaTeX Table 1 ---")
print(latex)
print("\n--- LaTeX Table 2 ---")
print(latex_cls)
