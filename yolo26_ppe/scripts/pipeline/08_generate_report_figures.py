#!/usr/bin/env python3
"""Generate all report figures as PDF (vector) with proper font sizes and consistent colors.
Following Nature/CASRAI guidelines:
- Vector format (PDF) for all charts
- Font size >= 10pt at final print size
- Colorblind-safe palette (viridis-based)
- One message per figure
- No chartjunk
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import json
from pathlib import Path

OUT = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe/reports/source/figures")
OUT.mkdir(parents=True, exist_ok=True)

# ─── Global style ──────────────────────────────────────────────
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['DejaVu Sans', 'Arial', 'Helvetica'],
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.alpha': 0.3,
    'grid.linewidth': 0.5,
})

# Consistent color palette (colorblind-safe, viridis-inspired)
COLORS = {
    'medium_detection': '#21918c',  # teal
    'medium_segmentation':    '#5ec962',  # green
}
CLASS_COLORS = {
    'person':  '#440154',
    'helmet':  '#3b528b',
    'closed footwear':   '#21918c',
    'harness': '#fde725',
}
SAM_COLOR = '#e74c3c'  # red for SAM

# ─── Data ──────────────────────────────────────────────────────
# v4_recipe final results — medium models only (4-class)
MODELS = ['medium_detection', 'medium_segmentation']
MODEL_LABELS = ['YOLO26m\ndetect', 'YOLO26m\nseg']

# From stage_2 final validation (best.pt)
# Detection: mAP50=0.700, mAP50-95=0.485, P=0.889, R=0.574
# Segmentation (box): mAP50=0.602, mAP50-95=0.427, P=0.792, R=0.537
# Segmentation (mask): mAP50=0.545, mAP50-95=0.324, P=0.754, R=0.500
MAP50 = [0.700, 0.602]
MAP5095 = [0.485, 0.427]
PRECISION = [0.889, 0.792]
RECALL = [0.574, 0.537]
F1 = [0.667, 0.610]
LATENCY = [34.9, 44.3]
SIZES = [54.5, 54.5]

# Per-class mAP50 (box) — from final validation
PER_CLASS = {
    'person':  [0.907, 0.727],
    'helmet':  [0.744, 0.713],
    'closed footwear':   [0.613, 0.562],
    'harness': [0.537, 0.404],
}

# SAM 3.1 data
SAM_LATENCY = 672.1
SAM_MAP50 = None  # no mAP for SAM (0 masks)

# ─── Figure 1: Pareto Frontier (latency vs mAP50) ─────────────
def fig_pareto():
    fig, ax = plt.subplots(figsize=(7, 5))
    for i, m in enumerate(MODELS):
        ax.scatter(LATENCY[i], MAP50[i], s=120, c=COLORS[m], zorder=5,
                   edgecolors='black', linewidth=0.5, label=m)
        ax.annotate(m, (LATENCY[i], MAP50[i]),
                    textcoords="offset points", xytext=(8, 5),
                    fontsize=9, fontweight='bold')
    # SAM point
    ax.scatter(SAM_LATENCY, 0.0, s=120, c=SAM_COLOR, zorder=5,
               edgecolors='black', linewidth=0.5, marker='D',
               label='SAM 3.1 (0 mask)')
    ax.annotate('SAM 3.1', (SAM_LATENCY, 0.0),
                textcoords="offset points", xytext=(8, 10),
                fontsize=9, fontweight='bold', color=SAM_COLOR)
    # Pareto frontier (m_detect is best)
    pareto_x = [SAM_LATENCY, LATENCY[0]]
    pareto_y = [0.0, MAP50[0]]
    ax.plot(pareto_x, pareto_y, 'k--', alpha=0.3, linewidth=1)
    ax.set_xlabel('Latency (ms)', fontweight='bold')
    ax.set_ylabel('mAP@0.5', fontweight='bold')
    ax.set_title('Pareto Frontier: Accuracy vs Latency', fontweight='bold')
    ax.legend(loc='upper right', framealpha=0.9)
    ax.set_xlim(-20, 750)
    ax.set_ylim(-0.05, 0.85)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    fig.savefig(OUT / 'pareto_frontier.pdf')
    plt.close(fig)
    print("Saved: pareto_frontier.pdf")

# ─── Figure 2: Per-class mAP50 bar chart ──────────────────────
def fig_perclass():
    classes = list(PER_CLASS.keys())
    n_cls = len(classes)
    x = np.arange(n_cls)
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, m in enumerate(MODELS):
        vals = [PER_CLASS[c][i] for c in classes]
        bars = ax.bar(x + i*width, vals, width, label=m, color=COLORS[m],
                      edgecolor='black', linewidth=0.3)
    ax.set_xlabel('Class', fontweight='bold')
    ax.set_ylabel('mAP@0.5', fontweight='bold')
    ax.set_title('Per-class mAP@0.5 — v4_recipe', fontweight='bold')
    ax.set_xticks(x + width*0.5)
    ax.set_xticklabels(classes, fontweight='bold', fontsize=9)
    ax.legend(loc='upper right', ncol=1, framealpha=0.9)
    ax.set_ylim(0, 1.0)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f'))
    fig.savefig(OUT / 'perclass_map50.pdf')
    plt.close(fig)
    print("Saved: perclass_map50.pdf")

# ─── Figure 3: Model size vs accuracy ─────────────────────────
def fig_size_vs_acc():
    fig, ax = plt.subplots(figsize=(7, 5))
    for i, m in enumerate(MODELS):
        ax.scatter(SIZES[i], MAP50[i], s=150, c=COLORS[m], zorder=5,
                   edgecolors='black', linewidth=0.5, label=m)
        ax.annotate(f"{m}\n({SIZES[i]} MB)", (SIZES[i], MAP50[i]),
                    textcoords="offset points", xytext=(10, 5),
                    fontsize=9, fontweight='bold')
    ax.set_xlabel('Model Size (MB)', fontweight='bold')
    ax.set_ylabel('mAP@0.5', fontweight='bold')
    ax.set_title('Model Size vs Accuracy', fontweight='bold')
    ax.legend(loc='lower right', framealpha=0.9)
    ax.set_xlim(0, 70)
    ax.set_ylim(0.4, 0.8)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    fig.savefig(OUT / 'size_vs_accuracy.pdf')
    plt.close(fig)
    print("Saved: size_vs_accuracy.pdf")

# ─── Figure 4: Overall metrics grouped bar ────────────────────
def fig_overall_metrics():
    metrics = ['mAP50', 'mAP50-95', 'Precision', 'Recall', 'F1']
    data = [MAP50, MAP5095, PRECISION, RECALL, F1]
    x = np.arange(len(metrics))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 5))
    for i, m in enumerate(MODELS):
        vals = [d[i] for d in data]
        ax.bar(x + i*width, vals, width, label=m, color=COLORS[m],
               edgecolor='black', linewidth=0.3)
    ax.set_ylabel('Score', fontweight='bold')
    ax.set_title('Overall Metrics Comparison — v4_recipe', fontweight='bold')
    ax.set_xticks(x + width*0.5)
    ax.set_xticklabels(metrics, fontweight='bold')
    ax.legend(loc='upper right', ncol=1, framealpha=0.9)
    ax.set_ylim(0, 1.0)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f'))
    fig.savefig(OUT / 'overall_metrics.pdf')
    plt.close(fig)
    print("Saved: overall_metrics.pdf")

# ─── Figure 5: Latency comparison (PyTorch vs ONNX) ───────────
def fig_latency_pt_vs_onnx():
    # Load from comparison JSON if available
    comp_path = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/evaluation/yolo/production_v4_recipe/onnx/all_comparison.json")
    pt_lat = []
    onnx_lat = []
    if comp_path.exists():
        comp = json.load(open(comp_path))
        for m in MODELS:
            if m in comp:
                pt_lat.append(comp[m]["pytorch"].get("latency_ms", 0))
                onnx_lat.append(comp[m]["onnx"].get("latency_ms", 0))
            else:
                pt_lat.append(0)
                onnx_lat.append(0)
    else:
        pt_lat = [34.9, 44.3]
        onnx_lat = [0, 0]
    x = np.arange(len(MODELS))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width/2, pt_lat, width, label='PyTorch', color='#21918c',
           edgecolor='black', linewidth=0.3)
    ax.bar(x + width/2, onnx_lat, width, label='ONNX', color='#fde725',
           edgecolor='black', linewidth=0.3)
    ax.set_ylabel('Latency (ms)', fontweight='bold')
    ax.set_title('PyTorch vs ONNX Latency (ROCm GPU)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace('_', '\n') for m in MODELS], fontweight='bold')
    ax.legend(framealpha=0.9)
    # Add value labels
    for i, (p, o) in enumerate(zip(pt_lat, onnx_lat)):
        ax.text(i - width/2, p + 5, f'{p:.1f}', ha='center', fontsize=9)
        if o > 0:
            ax.text(i + width/2, o + 5, f'{o:.1f}', ha='center', fontsize=9)
    fig.savefig(OUT / 'latency_pt_vs_onnx.pdf')
    plt.close(fig)
    print("Saved: latency_pt_vs_onnx.pdf")

# ─── Figure 6: Blurred dataset class distribution ─────────────
def fig_blurred_class_dist():
    # Load from JSON
    stats_path = OUT / "blur_robustness" / "blurred_aggregate_stats.json"
    if not stats_path.exists():
        print("SKIP blurred_class_dist: no stats")
        return
    stats = json.load(open(stats_path))
    classes = ['person', 'helmet', 'closed footwear', 'harness']
    x = np.arange(len(classes))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, m in enumerate(MODELS):
        cd = stats[m]["class_distribution"]
        vals = [cd.get(c, 0) for c in classes]
        ax.bar(x + i*width, vals, width, label=m, color=COLORS[m],
               edgecolor='black', linewidth=0.3)
    ax.set_ylabel('Detection Count', fontweight='bold')
    ax.set_title('Class Distribution on Blurred Dataset (48 images)', fontweight='bold')
    ax.set_xticks(x + width*0.5)
    ax.set_xticklabels(classes, fontweight='bold', fontsize=9)
    ax.legend(loc='upper right', ncol=1, framealpha=0.9)
    fig.savefig(OUT / 'blurred_class_dist.pdf')
    plt.close(fig)
    print("Saved: blurred_class_dist.pdf")

# ─── Figure 7: Blurred latency with error bars ────────────────
def fig_blurred_latency():
    stats_path = OUT / "blur_robustness" / "blurred_aggregate_stats.json"
    if not stats_path.exists():
        print("SKIP blurred_latency: no stats")
        return
    stats = json.load(open(stats_path))
    avgs = [stats[m]["avg_latency_ms"] for m in MODELS]
    stds = [stats[m]["std_latency_ms"] for m in MODELS]
    p95s = [stats[m]["p95_latency_ms"] for m in MODELS]
    x = np.arange(len(MODELS))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x, avgs, 0.5, yerr=stds, capsize=5,
           color=[COLORS[m] for m in MODELS],
           edgecolor='black', linewidth=0.3, label='Avg ± Std')
    # P95 markers
    ax.scatter(x, p95s, color='red', marker='_', s=200, zorder=5, label='P95')
    ax.set_ylabel('Latency (ms)', fontweight='bold')
    ax.set_title('Blurred Dataset Inference Latency (ONNX, ROCm)', fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace('_', '\n') for m in MODELS], fontweight='bold')
    ax.legend(framealpha=0.9)
    for i, a in enumerate(avgs):
        ax.text(i, a + stds[i] + 5, f'{a}±{stds[i]}', ha='center', fontsize=9)
    fig.savefig(OUT / 'blurred_latency.pdf')
    plt.close(fig)
    print("Saved: blurred_latency.pdf")

# ─── Figure 8: Training curves (if results.csv exists) ────────
def fig_training_curves():
    import csv
    csv_path = "/mnt/e/02_Projects/auto_label/yolo26_ppe/yolo26_ppe/models/production/medium_detection/stage_2_final_fine_tuning/results.csv"
    if not Path(csv_path).exists():
        # Try alternate path
        for p in Path("/mnt/e/02_Projects/auto_label/yolo26_ppe").rglob("results.csv"):
            if "medium_detection" in str(p) and "stage_2" in str(p):
                csv_path = str(p)
                break
        else:
            print("SKIP training_curves: no results.csv")
            return
    epochs, loss, map50 = [], [], []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            epochs.append(int(float(row.get('epoch', 0))))
            # Try different column names
            l = row.get('train/box_loss') or row.get('train_loss') or row.get('loss', '?')
            m = row.get('metrics/mAP50(B)') or row.get('metrics/mAP50') or row.get('mAP50', '?')
            try:
                loss.append(float(l))
                map50.append(float(m))
            except (ValueError, TypeError):
                pass
    if not epochs:
        print("SKIP training_curves: no data parsed")
        return
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
    ax1.plot(epochs, loss, color='#21918c', linewidth=1.5)
    ax1.set_ylabel('Training Loss', fontweight='bold')
    ax1.set_title('Training Curves — YOLO26m detect (v4_recipe)', fontweight='bold')
    ax2.plot(epochs, map50, color='#440154', linewidth=1.5)
    ax2.set_ylabel('mAP@0.5', fontweight='bold')
    ax2.set_xlabel('Epoch', fontweight='bold')
    ax2.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2f'))
    fig.savefig(OUT / 'training_curves_m_detect.pdf')
    plt.close(fig)
    print("Saved: training_curves_m_detect.pdf")

# ─── Run all ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating PDF figures...")
    fig_pareto()
    fig_perclass()
    fig_size_vs_acc()
    fig_overall_metrics()
    fig_latency_pt_vs_onnx()
    fig_blurred_class_dist()
    fig_blurred_latency()
    fig_training_curves()
    print("\nAll figures generated in:", OUT)
    # List
    for f in sorted(OUT.glob("*.pdf")):
        print(f"  {f.name} ({f.stat().st_size // 1024} KB)")
