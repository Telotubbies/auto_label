"""Step 3: Train YOLO26 models with MLflow tracking.

Usage:
  python 03_train.py --model n --task detect
  python 03_train.py --model s --task detect
  python 03_train.py --model n --task segment
  python 03_train.py --model s --task segment
  python 03_train.py --all
"""
import argparse
import glob
import json
import os
import sys
import time
import yaml

# ROCm env (must be before torch import)
os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load configs
with open(os.path.join(BASE, "yolo26_ppe", "configs", "train.yaml")) as f:
    TRAIN_CFG = yaml.safe_load(f)
with open(os.path.join(BASE, "yolo26_ppe", "configs", "augmentation.yaml")) as f:
    AUG_CFG = yaml.safe_load(f)

# MLflow setup
MLFLOW_DB = os.path.join(BASE, "yolo26_ppe", "mlflow", "mlflow.db")
os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{MLFLOW_DB}"
os.environ["MLFLOW_EXPERIMENT_NAME"] = TRAIN_CFG.get("experiment_name", "yolo26_ppe")

from ultralytics import YOLO, settings
import mlflow

settings.update({"mlflow": True})

# Keys in train.yaml that are NOT Ultralytics train() arguments
_NON_TRAIN_KEYS = {"models", "experiment_name"}

# Build train args from configs (train.yaml + augmentation.yaml)
def get_train_args():
    args = {}
    # From train.yaml (exclude non-train keys like 'models', 'experiment_name')
    for k, v in TRAIN_CFG.items():
        if k not in _NON_TRAIN_KEYS:
            args[k] = v
    # From augmentation.yaml (all keys are train args)
    args.update(AUG_CFG)
    return args

TRAIN_ARGS = get_train_args()


def train_one(model_key, config):
    """Train a single model."""
    print(f"\n{'=' * 70}")
    print(f"Training: {model_key}")
    print(f"  Weights: {config['weights']}")
    print(f"  Task:    {config['task']}")
    print(f"  Data:    {config['data']}")
    print(f"  Epochs:  {TRAIN_ARGS['epochs']}, Batch: {TRAIN_ARGS['batch']}, Imgsz: {TRAIN_ARGS['imgsz']}")
    print(f"{'=' * 70}")

    os.environ["MLFLOW_RUN"] = f"{model_key}_run1"

    model = YOLO(config["weights"])

    # Read dataset stats from analysis JSON (avoid hardcoding)
    analysis_path = os.path.join(BASE, "yolo26_ppe", "data", "analysis", "data_analysis.json")
    with open(analysis_path) as f:
        data_stats = json.load(f)

    # Read GPU info dynamically
    import torch
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"

    # Absolute project path so best.pt lands under yolo26_ppe/models/... not runs/detect/...
    project_abs = os.path.join(BASE, config["project"])
    # Absolute data.yaml path so Ultralytics resolves images correctly
    data_abs = os.path.join(BASE, config["data"])

    t0 = time.time()
    # Wrap train in an explicit MLflow run so custom params/metrics are logged
    # inside an active run (Ultralytics callback may otherwise control the run).
    with mlflow.start_run(run_name=f"{model_key}_run1"):
        results = model.train(
            data=data_abs,
            project=project_abs,
            name="run1",
            **TRAIN_ARGS,
        )
        train_time = time.time() - t0

        # Custom MLflow params — logged AFTER train completes, inside the run
        try:
            mlflow.log_param("model_key", model_key)
            mlflow.log_param("dataset_size", data_stats["total_images"])
            mlflow.log_param("train_split", data_stats["splits"]["train"])
            mlflow.log_param("val_split", data_stats["splits"]["val"])
            mlflow.log_param("test_split", data_stats["splits"]["test"])
            mlflow.log_param("augment_level", "medium-heavy")
            mlflow.log_param("noise_robust", True)
            mlflow.log_param("lighting_robust", True)
            mlflow.log_param("gpu", gpu_name)
            mlflow.log_param("runtime", "WSL2 ROCm")
            mlflow.log_param("imbalance_after_balance", data_stats.get("imbalance_after", "10.5:1"))
            # New training-recipe params (#5 Focal, #3 Grad Accum, #3 AMP)
            mlflow.log_param("fl_gamma", TRAIN_ARGS.get("fl_gamma", 0))
            mlflow.log_param("nbs", TRAIN_ARGS.get("nbs", 64))
            mlflow.log_param("amp", TRAIN_ARGS.get("amp", True))
            accum_steps = max(1, TRAIN_ARGS.get("nbs", 64) // TRAIN_ARGS.get("batch", 16))
            mlflow.log_param("gradient_accum_steps", accum_steps)
            mlflow.log_param("effective_batch", TRAIN_ARGS.get("batch", 16) * accum_steps)
        except Exception as e:
            print(f"  MLflow param log warning: {e}")

        # Final MLflow metrics
        try:
            mlflow.log_metric("train_time_seconds", train_time)
            best_pt = os.path.join(project_abs, "run1", "weights", "best.pt")
            if os.path.exists(best_pt):
                mlflow.log_metric("model_size_mb", os.path.getsize(best_pt) / 1e6)
            params = sum(p.numel() for p in model.model.parameters()) / 1e6
            mlflow.log_metric("params_M", params)
        except Exception as e:
            print(f"  MLflow metric log warning: {e}")

        # Inference timing — single image, warmup, average 10 runs
        try:
            data_dir = os.path.dirname(os.path.join(BASE, config["data"]))
            test_img_dir = os.path.join(data_dir, "images", "test")
            test_images = sorted(glob.glob(os.path.join(test_img_dir, "*.jpg")))
            if test_images:
                single_img = test_images[0]
                # Warmup (first predict includes lazy init overhead)
                model.predict(source=single_img, verbose=False)
                # Time 10 individual predictions on a single image
                times = []
                for _ in range(10):
                    ti = time.time()
                    model.predict(source=single_img, verbose=False)
                    times.append(time.time() - ti)
                inference_ms = (sum(times) / len(times)) * 1000
                mlflow.log_metric("inference_ms", inference_ms)
                print(f"  Inference: {inference_ms:.1f} ms/image (avg of 10)")
        except Exception as e:
            print(f"  Inference timing warning: {e}")

    print(f"\n  Training time: {train_time:.1f}s ({train_time/60:.1f} min)")

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return results


def main():
    parser = argparse.ArgumentParser(description="Train YOLO26 PPE models")
    parser.add_argument("--model", choices=["n", "s"], help="Model size")
    parser.add_argument("--task", choices=["detect", "segment"], help="Task")
    parser.add_argument("--all", action="store_true", help="Train all 4 models sequentially")
    args = parser.parse_args()

    models = TRAIN_CFG["models"]

    if args.all:
        for key, config in models.items():
            train_one(key, config)
    elif args.model and args.task:
        key = f"{args.model}_{'seg' if args.task == 'segment' else 'detect'}"
        if key not in models:
            print(f"Unknown model: {key}")
            sys.exit(1)
        train_one(key, models[key])
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
