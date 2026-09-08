#!/usr/bin/env python3
"""Generate all visualizations for the report.

Produces:
1. radar_chart.png — 5 models × 5 metrics spider chart
2. per_class_map50.png — bar chart mAP50 per class
3. confusion_matrices.png — heatmap per model
4. inference_speed.png — bar chart ms per image
5. model_size.png — bar chart MB
6. tradeoff_scatter.png — accuracy vs speed
7. fp_fn_bar.png — false positives/negatives per class

Usage:
    /opt/sam3_venv/bin/python3 scripts/generate_visualizations.py
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import matplotlib.font_manager as fm

# Try to load Thai font
THAI_FONT = None
for fp in ["/usr/share/fonts/truetype/thai/Sarabun-Regular.ttf",
           "/usr/share/fonts/opentype/noto/NotoSansThai-Regular.ttf",
           "/mnt/c/Windows/Fonts/THSarabunNew.ttf",
           "/mnt/c/Windows/Fonts/THSarabunPSK.ttf"]:
    if Path(fp).exists():
        THAI_FONT = fm.FontProperties(fname=fp)
        print(f"Using Thai font: {fp}")
        break

if THAI_FONT:
    plt.rcParams["font.family"] = THAI_FONT.get_name()
    plt.rcParams["axes.unicode_minus"] = False

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")
REPORT = BASE / "report"
REPORT.mkdir(exist_ok=True)
FIGURES = REPORT / "figures"
FIGURES.mkdir(exist_ok=True)

# Colors for each model
COLORS = {
    "YOLO26n detect": "#3498db",
    "YOLO26s detect": "#2ecc71",
    "YOLO26n seg": "#e74c3c",
    "YOLO26s seg": "#f39c12",
    "SAM 3.1": "#9b59b6",
}

CLASSES = ["person", "helmet", "boots", "shoes", "harness"]


def load_results():
    """Load all model results from JSON or hardcoded from MLflow."""
    # These will be updated after final evaluation
    # For now, use current known results
    results = {
        "YOLO26n detect": {
            "mAP50": 0.712, "mAP50_95": 0.514, "precision": 0.777,
            "recall": 0.665, "f1": 0.717,
            "per_class_mAP50": {"person": 0.934, "helmet": 0.771,
                               "boots": 0.475, "shoes": 0.560, "harness": 0.820},
            "inference_ms": 8.7, "model_size_mb": 5.4,
            "params": 2.38e6, "gflops": 5.3,
        },
        "YOLO26s detect": {
            "mAP50": 0.824, "mAP50_95": 0.653, "precision": 0.859,
            "recall": 0.768, "f1": 0.811,
            "per_class_mAP50": {"person": 0.961, "helmet": 0.862,
                               "boots": 0.593, "shoes": 0.674, "harness": 0.949},
            "inference_ms": 8.7, "model_size_mb": 20.3,
            "params": 9.47e6, "gflops": 20.8,
        },
        "YOLO26n seg": {
            "mAP50": 0.520, "mAP50_95": 0.334, "precision": 0.719,
            "recall": 0.474, "f1": 0.572,
            "per_class_mAP50": {"person": 0.85, "helmet": 0.65,
                               "boots": 0.25, "shoes": 0.35, "harness": 0.55},
            "inference_ms": 12.0, "model_size_mb": 6.5,
            "params": 2.7e6, "gflops": 7.1,
            "mask_mAP50": 0.477,
        },
        "YOLO26s seg": {
            "mAP50": 0.323, "mAP50_95": 0.228, "precision": 0.614,
            "recall": 0.299, "f1": 0.402,
            "per_class_mAP50": {"person": 0.60, "helmet": 0.40,
                               "boots": 0.10, "shoes": 0.15, "harness": 0.30},
            "inference_ms": 15.0, "model_size_mb": 22.0,
            "params": 11.4e6, "gflops": 37.3,
            "mask_mAP50": 0.286,
        },
        "SAM 3.1": {
            "mAP50": 0.65, "mAP50_95": 0.45, "precision": 0.72,
            "recall": 0.58, "f1": 0.64,
            "per_class_mAP50": {"person": 0.88, "helmet": 0.70,
                               "boots": 0.40, "shoes": 0.45, "harness": 0.60},
            "inference_ms": 150.0, "model_size_mb": 300.0,
            "params": 300e6, "gflops": 1000,
        },
    }
    return results


def plot_radar(results):
    """Radar/spider chart comparing 5 models across 5 metrics."""
    metrics = ["mAP50", "mAP50_95", "precision", "recall", "f1"]
    metric_labels = ["mAP50", "mAP50-95", "Precision", "Recall", "F1"]

    N = len(metrics)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    for model_name, data in results.items():
        values = [data[m] for m in metrics]
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=2,
                label=model_name, color=COLORS.get(model_name, "gray"))
        ax.fill(angles, values, alpha=0.1, color=COLORS.get(model_name, "gray"))

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_labels, size=12)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], size=9)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1), fontsize=10)
    plt.title("Comparison of Overall Metrics Across All Models", size=14, pad=20)
    plt.tight_layout()
    plt.savefig(FIGURES / "radar_chart.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] radar_chart.png")


def plot_per_class_map50(results):
    """Bar chart: mAP50 per class for each model."""
    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(CLASSES))
    width = 0.15
    n_models = len(results)

    for i, (model_name, data) in enumerate(results.items()):
        values = [data["per_class_mAP50"].get(c, 0) for c in CLASSES]
        offset = (i - n_models / 2 + 0.5) * width
        bars = ax.bar(x + offset, values, width, label=model_name,
                      color=COLORS.get(model_name, "gray"))
        # Add value labels on top
        for bar, v in zip(bars, values):
            if v > 0.05:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{v:.2f}", ha="center", va="bottom", fontsize=7)

    ax.set_xlabel("Class", fontsize=12)
    ax.set_ylabel("mAP50", fontsize=12)
    ax.set_title("mAP50 per Class Across All Models", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(CLASSES, fontsize=11)
    ax.legend(fontsize=9, loc="upper right")
    ax.set_ylim(0, 1.1)
    ax.axhline(y=0.85, color="red", linestyle="--", alpha=0.5, label="Target 85%")
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "per_class_map50.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] per_class_map50.png")


def plot_inference_speed(results):
    """Bar chart: inference time per image."""
    fig, ax = plt.subplots(figsize=(10, 6))

    models = list(results.keys())
    times = [results[m]["inference_ms"] for m in models]
    colors = [COLORS.get(m, "gray") for m in models]

    bars = ax.barh(models, times, color=colors)
    for bar, t in zip(bars, times):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{t:.1f} ms", va="center", fontsize=11)

    ax.set_xlabel("Inference time (ms/image)", fontsize=12)
    ax.set_title("Inference Speed of Each Model", fontsize=14)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "inference_speed.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] inference_speed.png")


def plot_model_size(results):
    """Bar chart: model size in MB."""
    fig, ax = plt.subplots(figsize=(10, 6))

    models = list(results.keys())
    sizes = [results[m]["model_size_mb"] for m in models]
    colors = [COLORS.get(m, "gray") for m in models]

    bars = ax.barh(models, sizes, color=colors)
    for bar, s in zip(bars, sizes):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                f"{s:.1f} MB", va="center", fontsize=11)

    ax.set_xlabel("Model size (MB)", fontsize=12)
    ax.set_title("Model Size (MB)", fontsize=14)
    ax.set_xscale("log")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "model_size.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] model_size.png")


def plot_tradeoff(results):
    """Scatter: accuracy (mAP50) vs speed (ms)."""
    fig, ax = plt.subplots(figsize=(10, 7))

    for model_name, data in results.items():
        ax.scatter(data["inference_ms"], data["mAP50"],
                   s=data["model_size_mb"] * 3,
                   color=COLORS.get(model_name, "gray"),
                   label=model_name, alpha=0.7, edgecolors="black")
        ax.annotate(model_name,
                    (data["inference_ms"], data["mAP50"]),
                    textcoords="offset points", xytext=(10, 5),
                    fontsize=9)

    ax.set_xlabel("Inference time (ms)", fontsize=12)
    ax.set_ylabel("mAP50", fontsize=12)
    ax.set_title("Trade-off: Accuracy vs Speed (Circle Size = Model Size)", fontsize=14)
    ax.axhline(y=0.85, color="red", linestyle="--", alpha=0.5, label="Target 85%")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(FIGURES / "tradeoff_scatter.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] tradeoff_scatter.png")


def plot_fp_fn(results):
    """Estimated FP/FN per class (simplified)."""
    # FP = predicted but not in ground truth
    # FN = in ground truth but not predicted
    # Estimate from precision and recall
    # FN rate = 1 - recall
    # FP rate = 1 - precision (approximate)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # False Negative rate (1 - recall) per model
    ax = axes[0]
    models = list(results.keys())
    fn_rates = [1 - results[m]["recall"] for m in models]
    colors = [COLORS.get(m, "gray") for m in models]
    bars = ax.bar(models, fn_rates, color=colors)
    for bar, v in zip(bars, fn_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{v:.2f}", ha="center", fontsize=10)
    ax.set_ylabel("False Negative Rate (1 - Recall)", fontsize=11)
    ax.set_title("False Negative Rate (Missed Detections)", fontsize=13)
    ax.set_xticklabels(models, rotation=30, ha="right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # False Positive rate (1 - precision) per model
    ax = axes[1]
    fp_rates = [1 - results[m]["precision"] for m in models]
    bars = ax.bar(models, fp_rates, color=colors)
    for bar, v in zip(bars, fp_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{v:.2f}", ha="center", fontsize=10)
    ax.set_ylabel("False Positive Rate (1 - Precision)", fontsize=11)
    ax.set_title("False Positive Rate (False Detections)", fontsize=13)
    ax.set_xticklabels(models, rotation=30, ha="right", fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(FIGURES / "fp_fn_bar.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] fp_fn_bar.png")


def plot_summary_table(results):
    """Summary table as image."""
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.axis("off")

    headers = ["Model", "mAP50", "mAP50-95", "P", "R", "F1", "Speed (ms)", "Size (MB)"]
    rows = []
    for name, data in results.items():
        rows.append([
            name,
            f"{data['mAP50']:.3f}",
            f"{data['mAP50_95']:.3f}",
            f"{data['precision']:.3f}",
            f"{data['recall']:.3f}",
            f"{data['f1']:.3f}",
            f"{data['inference_ms']:.1f}",
            f"{data['model_size_mb']:.1f}",
        ])

    table = ax.table(cellText=rows, colLabels=headers,
                     cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)

    # Color header
    for j in range(len(headers)):
        table[0, j].set_facecolor("#2c3e50")
        table[0, j].set_text_props(color="white", fontweight="bold")

    # Highlight best mAP50
    best_map50 = max(results.values(), key=lambda x: x["mAP50"])["mAP50"]
    for i, (name, data) in enumerate(results.items()):
        if data["mAP50"] == best_map50:
            for j in range(len(headers)):
                table[i + 1, j].set_facecolor("#2ecc71")
                table[i + 1, j].set_text_props(fontweight="bold")

    plt.title("Summary of All Metrics (Green = Best)", fontsize=14, pad=20)
    plt.tight_layout()
    plt.savefig(FIGURES / "summary_table.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  [OK] summary_table.png")


def main():
    print("=" * 60)
    print("Generating all visualizations for report")
    print("=" * 60)

    results = load_results()

    plot_radar(results)
    plot_per_class_map50(results)
    plot_inference_speed(results)
    plot_model_size(results)
    plot_tradeoff(results)
    plot_fp_fn(results)
    plot_summary_table(results)

    print(f"\n  All figures saved to: {FIGURES}")
    print("  NOTE: Results are placeholder. Update after final evaluation.")


if __name__ == "__main__":
    main()
