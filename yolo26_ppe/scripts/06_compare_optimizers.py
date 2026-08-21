#!/usr/bin/env python3
"""Compare all optimizer experiment results.

Reads metrics.json from each model/optimizer folder and produces
a comparison table + bar chart.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe")

MODELS = ["n_detect", "s_detect", "n_seg", "s_seg"]
OPTIMIZERS = ["SGD", "AdamW", "Adam", "auto"]
VERSIONS = {"SGD": "v2", "AdamW": "v3", "Adam": "v4", "auto": "v5"}


def load_all_results():
    """Load metrics.json from all model/optimizer folders."""
    results = {}
    for model in MODELS:
        for opt in OPTIMIZERS:
            opt_lower = opt.lower()
            ver = VERSIONS[opt]
            folder = BASE / "models" / f"yolo26{model}_{ver}_{opt_lower}"
            metrics_file = folder / "eval_test" / "metrics.json"
            if metrics_file.exists():
                with open(metrics_file) as f:
                    results[(model, opt)] = json.load(f)
                    print(f"  [OK] {model} / {opt}: {metrics_file}")
            else:
                print(f"  [SKIP] {model} / {opt}: not found")
    return results


def print_comparison_table(results):
    """Print comparison table."""
    print("\n" + "=" * 80)
    print("  Optimizer Comparison Results (test set)")
    print("=" * 80)

    # Detect models — use mAP50
    # Seg models — use box mAP50 and mask mAP50
    for model in MODELS:
        print(f"\n  --- {model} ---")
        print(f"  {'Optimizer':<10} {'mAP50':>8} {'mAP50-95':>10} {'P':>8} {'R':>8}")
        print(f"  {'-'*50}")

        for opt in OPTIMIZERS:
            if (model, opt) not in results:
                print(f"  {opt:<10} {'N/A':>8}")
                continue

            m = results[(model, opt)]
            # Find the right metric keys
            map50 = m.get("metrics/mAP50(B)", m.get("metrics/mAP50", m.get("box_mAP50", 0)))
            map5095 = m.get("metrics/mAP50-95(B)", m.get("metrics/mAP50-95", m.get("box_mAP50_95", 0)))
            p = m.get("metrics/precision(B)", m.get("metrics/precision", m.get("box_precision", 0)))
            r = m.get("metrics/recall(B)", m.get("metrics/recall", m.get("box_recall", 0)))

            print(f"  {opt:<10} {map50:>8.4f} {map5095:>10.4f} {p:>8.4f} {r:>8.4f}")

            # For seg, also print mask metrics
            if "seg" in model:
                mmap50 = m.get("metrics/mAP50(M)", m.get("mask_mAP50", 0))
                print(f"  {'  mask':<10} {mmap50:>8.4f}")


def plot_optimizer_comparison(results):
    """Bar chart comparing optimizers for each model."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()

    colors = {"SGD": "#3498db", "AdamW": "#2ecc71", "Adam": "#e74c3c", "auto": "#f39c12"}

    for idx, model in enumerate(MODELS):
        ax = axes[idx]
        opt_names = []
        map50_values = []
        map50_colors = []

        for opt in OPTIMIZERS:
            if (model, opt) not in results:
                continue
            m = results[(model, opt)]
            map50 = m.get("metrics/mAP50(B)", m.get("metrics/mAP50", m.get("box_mAP50", 0)))
            opt_names.append(opt)
            map50_values.append(map50)
            map50_colors.append(colors[opt])

        if opt_names:
            bars = ax.bar(opt_names, map50_values, color=map50_colors)
            for bar, v in zip(bars, map50_values):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{v:.3f}", ha="center", fontsize=10)
            ax.set_ylim(0, 1.0)
            ax.axhline(y=0.85, color="red", linestyle="--", alpha=0.5)
        ax.set_title(model, fontsize=13, fontweight="bold")
        ax.set_ylabel("mAP50", fontsize=11)
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Optimizer Comparison: mAP50 on test set", fontsize=15, fontweight="bold")
    plt.tight_layout()
    output = BASE / "report" / "figures" / "optimizer_comparison.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Chart saved: {output}")


def main():
    print("=" * 60)
    print("  Optimizer Experiment Comparison")
    print("=" * 60)

    results = load_all_results()

    if not results:
        print("\n  No results found yet. Run training + eval first.")
        return

    print_comparison_table(results)
    plot_optimizer_comparison(results)

    # Save summary JSON
    summary = {}
    for (model, opt), metrics in results.items():
        key = f"{model}_{opt}"
        summary[key] = metrics
    summary_file = BASE / "report" / "optimizer_experiment_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary saved: {summary_file}")


if __name__ == "__main__":
    main()
