"""Step 5: Practical hyperparameter tuning for underperforming models.

Instead of Ultralytics' built-in tuner (which runs 30+ full training iterations
taking 10+ hours per model), this script does a focused manual search over a
small set of high-impact hyperparameters with shorter training per trial.

Usage:
  python 05_tune.py --model n --task detect --iterations 5
  python 05_tune.py --model s --task segment --iterations 5
"""
import argparse
import json
import os
import shutil
import sys
import yaml

os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MLFLOW_DB = os.path.join(BASE, "yolo26_ppe", "mlflow", "mlflow.db")
os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{MLFLOW_DB}"
os.environ["MLFLOW_EXPERIMENT_NAME"] = "yolo26_ppe_tune"

from ultralytics import YOLO, settings
import mlflow

settings.update({"mlflow": True})

with open(os.path.join(BASE, "yolo26_ppe", "configs", "train.yaml")) as f:
    TRAIN_CFG = yaml.safe_load(f)
with open(os.path.join(BASE, "yolo26_ppe", "configs", "augmentation.yaml")) as f:
    AUG_CFG = yaml.safe_load(f)

MODELS = TRAIN_CFG["models"]


# Focused hyperparameter search space — high-impact params only.
# Each entry is a list of values to try. We do a grid/random search over these.
SEARCH_SPACE = {
    "lr0": [0.01, 0.005, 0.02],           # learning rate
    "imgsz": [640, 960],                   # resolution (small objects)
    "cls_pw": [0.3, 0.5, 0.8],            # class loss weight (Ultralytics: 0-1 range)
    "mosaic": [0.8, 1.0],                  # augmentation
    "mixup": [0.1, 0.0],                   # mixup
    "copy_paste": [0.15, 0.0],            # copy-paste
    "scale": [0.6, 0.5],                   # scale augmentation
    "close_mosaic": [15, 20],             # close mosaic earlier
}

# Default/baseline config (from initial training) — used as starting point
BASELINE = {
    "lr0": 0.01,
    "imgsz": 640,
    "cls_pw": 0.5,
    "mosaic": 0.8,
    "mixup": 0.1,
    "copy_paste": 0.15,
    "scale": 0.6,
    "close_mosaic": 15,
}


def generate_trials(iterations, seed=42):
    """Generate a set of hyperparameter combinations to try.

    First trial is always the baseline. Subsequent trials vary one or two
    parameters at a time to explore the space efficiently.
    """
    import random
    random.seed(seed)

    trials = [dict(BASELINE)]  # trial 0: baseline

    # Predefined high-impact variations
    variations = [
        # Higher resolution (small objects)
        {"imgsz": 960, "lr0": 0.005, "cls_pw": 0.8},
        # Lower class loss weight for rare classes
        {"cls_pw": 0.3, "lr0": 0.005, "imgsz": 960},
        # Higher LR with more augmentation
        {"lr0": 0.02, "mosaic": 1.0, "mixup": 0.0, "copy_paste": 0.0},
        # Lower LR, less augmentation, higher res
        {"lr0": 0.005, "imgsz": 960, "mosaic": 0.8, "scale": 0.5, "close_mosaic": 20},
        # Focus on rare classes with copy-paste
        {"cls_pw": 0.3, "copy_paste": 0.15, "imgsz": 960, "lr0": 0.005},
        # Minimal augmentation, high res
        {"imgsz": 960, "mosaic": 0.8, "mixup": 0.0, "copy_paste": 0.0, "scale": 0.5},
        # Higher LR, high res
        {"lr0": 0.02, "imgsz": 960, "cls_pw": 0.8},
        # Conservative: lower LR, standard res
        {"lr0": 0.005, "cls_pw": 0.8, "close_mosaic": 20},
    ]

    for v in variations[:iterations - 1]:
        trial = dict(BASELINE)
        trial.update(v)
        trials.append(trial)

    return trials[:iterations]


def tune_one(model_key, config, iterations=5):
    """Run focused hyperparameter search for a model.

    Each trial trains for a reduced number of epochs (50, patience 20) to
    quickly identify promising hyperparameter combinations. The best
    checkpoint is preserved.
    """
    print(f"\n{'=' * 70}")
    print(f"Tuning: {model_key} ({iterations} trials, 50 epochs each)")
    print(f"{'=' * 70}")

    best_pt = os.path.join(BASE, config["project"], "run1", "weights", "best.pt")
    if not os.path.exists(best_pt):
        print(f"  ERROR: {best_pt} not found. Train first.")
        return None

    # Load current best metrics for comparison
    eval_path = os.path.join(BASE, "yolo26_ppe", "reports", "eval_all.json")
    current_best_map50 = 0.0
    if os.path.exists(eval_path):
        with open(eval_path) as f:
            eval_data = json.load(f)
        if model_key in eval_data:
            current_best_map50 = eval_data[model_key].get("mAP50", 0) or 0
    print(f"  Current best mAP50: {current_best_map50:.4f}")

    # Use the original pretrained weights (not the trained best.pt) for tuning
    # This allows the tuner to explore different training regimes
    weights_path = os.path.join(BASE, config["weights"])
    if not os.path.exists(weights_path):
        # Try yolo26_ppe/weights/
        weights_path = os.path.join(BASE, "yolo26_ppe", "weights", config["weights"])
    if not os.path.exists(weights_path):
        # Let Ultralytics find/download it
        weights_path = config["weights"]

    data_path = os.path.join(BASE, config["data"])
    tune_project = os.path.join(BASE, config["project"])

    trials = generate_trials(iterations)

    # Base args from configs (excluding models dict)
    base_args = {}
    for k, v in TRAIN_CFG.items():
        if k != "models":
            base_args[k] = v
    base_args.update(AUG_CFG)

    # Override for tuning: shorter training
    base_args["epochs"] = 50
    base_args["patience"] = 20
    base_args["freeze"] = 0  # unfreeze for tuning (allow full adaptation)

    best_trial_map50 = current_best_map50
    best_trial_idx = -1
    best_trial_params = None
    best_trial_path = None

    for idx, trial_params in enumerate(trials):
        print(f"\n  --- Trial {idx + 1}/{len(trials)} ---")
        print(f"  Params: {trial_params}")

        trial_name = f"tune_trial{idx + 1}"

        # Merge trial params with base args
        train_args = dict(base_args)
        train_args.update(trial_params)

        # Remove non-trainable keys
        for skip_key in ["models", "weights", "task", "data", "project"]:
            train_args.pop(skip_key, None)

        try:
            model = YOLO(weights_path)
            results = model.train(
                data=data_path,
                project=tune_project,
                name=trial_name,
                **train_args,
            )

            # Get validation mAP50 from training results
            trial_map50 = 0.0
            if hasattr(results, "results_dict"):
                rd = results.results_dict
                # For detect: metrics/mAP50(B), for segment: metrics/mAP50(B) or metrics/mAP50(M)
                trial_map50 = rd.get("metrics/mAP50(B)", 0) or 0
                if trial_map50 == 0:
                    trial_map50 = rd.get("metrics/mAP50(M)", 0) or 0

            print(f"  Trial {idx + 1} mAP50: {trial_map50:.4f}")

            if trial_map50 > best_trial_map50:
                best_trial_map50 = trial_map50
                best_trial_idx = idx
                best_trial_params = dict(trial_params)
                best_trial_path = os.path.join(tune_project, trial_name, "weights", "best.pt")
                print(f"  *** NEW BEST! Trial {idx + 1} (mAP50={trial_map50:.4f}) ***")

        except Exception as e:
            print(f"  Trial {idx + 1} FAILED: {e}")
            continue

    # If we found a better model, replace the run1 best.pt
    if best_trial_idx >= 0 and best_trial_path and os.path.exists(best_trial_path):
        print(f"\n  Best trial: #{best_trial_idx + 1} with mAP50={best_trial_map50:.4f}")
        print(f"  Best params: {best_trial_params}")
        print(f"  Replacing run1/weights/best.pt with tuned model...")

        # Backup original
        original_best = os.path.join(tune_project, "run1", "weights", "best.pt")
        backup_path = os.path.join(tune_project, "run1", "weights", "best_original.pt")
        if not os.path.exists(backup_path):
            shutil.copy2(original_best, backup_path)

        # Copy tuned model as new best
        shutil.copy2(best_trial_path, original_best)
        print(f"  Done. Tuned model is now run1/weights/best.pt")

        # Save tuning results
        tune_results = {
            "model_key": model_key,
            "baseline_mAP50": current_best_map50,
            "best_trial_mAP50": best_trial_map50,
            "best_trial_idx": best_trial_idx + 1,
            "best_params": best_trial_params,
            "improvement": best_trial_map50 - current_best_map50,
            "all_trials": len(trials),
        }
        tune_path = os.path.join(BASE, "yolo26_ppe", "reports", f"tune_{model_key}.json")
        with open(tune_path, "w") as f:
            json.dump(tune_results, f, indent=2)
        print(f"  Results saved to {tune_path}")

        return tune_results
    else:
        print(f"\n  No improvement over baseline (mAP50={current_best_map50:.4f}).")
        print(f"  Keeping original best.pt.")
        # Save tuning results even when no improvement
        tune_results = {
            "model_key": model_key,
            "baseline_mAP50": current_best_map50,
            "best_trial_mAP50": best_trial_map50 if best_trial_idx >= 0 else current_best_map50,
            "best_trial_idx": best_trial_idx + 1 if best_trial_idx >= 0 else None,
            "best_params": best_trial_params if best_trial_idx >= 0 else {},
            "improvement": (best_trial_map50 - current_best_map50) if best_trial_idx >= 0 else 0,
            "all_trials": len(trials),
            "improved": False,
        }
        tune_path = os.path.join(BASE, "yolo26_ppe", "reports", f"tune_{model_key}.json")
        with open(tune_path, "w") as f:
            json.dump(tune_results, f, indent=2)
        print(f"  Results saved to {tune_path}")
        return tune_results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["n", "s"], required=True)
    parser.add_argument("--task", choices=["detect", "segment"], required=True)
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()

    key = f"{args.model}_{'seg' if args.task == 'segment' else 'detect'}"
    if key not in MODELS:
        print(f"Unknown model: {key}")
        sys.exit(1)

    result = tune_one(key, MODELS[key], args.iterations)
    if result:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
