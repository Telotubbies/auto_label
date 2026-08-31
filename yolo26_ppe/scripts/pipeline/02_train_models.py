"""Step 13: Full training recipe for all 4 YOLO26 PPE models.

Recipe (version v4_recipe):
  - Focal Loss (fl_gamma=1.5)
  - Gradient Accumulation (nbs=64)
  - AMP (mixed precision)
  - Two-stage fine-tuning:
      Stage 1: freeze backbone (freeze=10), lr0=0.01, 150 epochs
      Stage 2: unfreeze all (freeze=0), lr0=0.001, 50 epochs, reduced aug

Uses /tmp datasets for fast I/O (copied from v2 datasets).
Uses larger batch (32 for detect, 16 for seg) to leverage 16GB VRAM.
Logs to MLflow with version=v4_recipe tags.

Usage:
  python 13_train_recipe_all.py              # all 4 models, stage1 + stage2
  python 13_train_recipe_all.py --stage 1    # stage 1 only
  python 13_train_recipe_all.py --stage 2    # stage 2 only (requires stage 1 done)
  python 13_train_recipe_all.py --model n --task detect
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

# MLflow setup
MLFLOW_DB = os.path.join(BASE, "yolo26_ppe", "mlflow", "mlflow.db")
os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{MLFLOW_DB}"

# Import focal patch BEFORE ultralytics YOLO — monkey-patches v8DetectionLoss
# to use Focal Loss (gamma=1.5) instead of plain BCE.
import focal_patch  # noqa: F401

from ultralytics import YOLO, settings
import mlflow

settings.update({"mlflow": True})

# Load augmentation config
with open(os.path.join(BASE, "yolo26_ppe", "configs", "augmentation.yaml")) as f:
    AUG_CFG = yaml.safe_load(f)

VERSION = "v4_recipe"

# Use /tmp datasets for fast I/O (must be copied before running)
DATA_DETECT = "/tmp/yolo_detect_data/data.yaml"
DATA_SEG = "/tmp/yolo_seg_data/data.yaml"

# Model configs — v4_recipe output dirs (separate from v2 baseline and v3 adamw)
MODELS = {
    "n_detect": {
        "weights": "yolo26n.pt",
        "task": "detect",
        "data": DATA_DETECT,
        "project": f"yolo26_ppe/models/yolo26n_detect_{VERSION}",
        "batch": 64,       # n detect uses ~4GB at 32 → 64 ~8GB (plenty of headroom)
    },
    "s_detect": {
        "weights": "yolo26s.pt",
        "task": "detect",
        "data": DATA_DETECT,
        "project": f"yolo26_ppe/models/yolo26s_detect_{VERSION}",
        "batch": 48,       # s detect uses ~10GB at 32 → 48 ~15GB (tight but fits 16GB)
    },
    "n_seg": {
        "weights": "yolo26n-seg.pt",
        "task": "segment",
        "data": DATA_SEG,
        "project": f"yolo26_ppe/models/yolo26n_seg_{VERSION}",
        "batch": 16,       # parallel: n_seg stage2 ~6GB
    },
    "s_seg": {
        "weights": "yolo26s-seg.pt",
        "task": "segment",
        "data": DATA_SEG,
        "project": f"yolo26_ppe/models/yolo26s_seg_{VERSION}",
        "batch": 16,       # stable: 24 caused deadlock, 16 is safe
    },
}

# Stage 1 args — frozen backbone, high LR, full augmentation
def get_stage1_args(batch):
    args = {
        "epochs": 150,
        "imgsz": 640,
        "batch": batch,
        "patience": 30,
        "freeze": 10,
        "cls_pw": 0.5,
        # Optimizer
        "lr0": 0.01,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_epochs": 3,
        "warmup_momentum": 0.8,
        "warmup_bias_lr": 0.1,
        # Loss weights
        "box": 7.5,
        "cls": 0.5,
        "dfl": 1.5,
        # Focal Loss — applied via focal_patch.py monkey-patch (gamma=1.5)
        # fl_gamma is NOT a valid Ultralytics arg; logged to MLflow only.
        # Gradient Accumulation — effective batch 64
        "nbs": 64,
        # AMP
        "amp": True,
        # Save + val
        "save": True,
        "save_period": -1,
        "val": True,
        "plots": True,
        "exist_ok": True,
        # Cache dataset in RAM (datasets are small, /tmp is fast)
        "cache": True,
        "workers": 4,
        # Seed
        "seed": 42,
    }
    # Augmentation from config
    args.update(AUG_CFG)
    return args

# Stage 2 args — unfreeze all, low LR, reduced augmentation
def get_stage2_args(batch):
    args = {
        "epochs": 50,
        "imgsz": 640,
        "batch": batch,
        "patience": 15,
        "freeze": 0,              # unfreeze ALL layers
        "cls_pw": 0.5,
        # Optimizer — 10x lower LR
        "lr0": 0.001,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_epochs": 1,
        "warmup_momentum": 0.8,
        "warmup_bias_lr": 0.01,
        # Loss weights
        "box": 7.5,
        "cls": 0.5,
        "dfl": 1.5,
        # Focal Loss — applied via focal_patch.py monkey-patch (gamma=1.5)
        # fl_gamma is NOT a valid Ultralytics arg; logged to MLflow only.
        # Gradient Accumulation
        "nbs": 64,
        # AMP
        "amp": True,
        # Save + val
        "save": True,
        "save_period": -1,
        "val": True,
        "plots": True,
        "exist_ok": True,
        "cache": True,
        "workers": 4,
        "seed": 42,
        # Reduced augmentation for fine-tuning
        "hsv_h": 0.015,
        "hsv_s": 0.5,
        "hsv_v": 0.4,
        "degrees": 5.0,
        "translate": 0.15,
        "scale": 0.4,
        "shear": 2.0,
        "perspective": 0.0,
        "fliplr": 0.5,
        "flipud": 0.0,
        "mosaic": 0.5,
        "mixup": 0.0,
        "copy_paste": 0.1,
        "close_mosaic": 5,
        "erasing": 0.2,
    }
    return args


def log_common_params(model_key, config, stage, args, gpu_name, data_stats):
    """Log common MLflow params for both stages."""
    mlflow.log_param("model_key", model_key)
    mlflow.log_param("version", VERSION)
    mlflow.log_param("stage", stage)
    mlflow.log_param("task", config["task"])
    model_size = "n" if "n_detect" in model_key or "n_seg" in model_key else "s"
    mlflow.log_param("model_size", model_size)
    mlflow.log_param("optimizer", "MuSGD")
    mlflow.log_param("seed", args.get("seed", 42))
    mlflow.log_param("epochs", args["epochs"])
    mlflow.log_param("batch", args["batch"])
    mlflow.log_param("nbs", args.get("nbs", 64))
    mlflow.log_param("amp", args.get("amp", True))
    accum_steps = max(1, args.get("nbs", 64) // args["batch"])
    mlflow.log_param("gradient_accum_steps", accum_steps)
    mlflow.log_param("effective_batch", args["batch"] * accum_steps)
    mlflow.log_param("fl_gamma", 1.5)  # applied via focal_patch.py monkey-patch
    mlflow.log_param("freeze", args.get("freeze", 0))
    mlflow.log_param("lr0", args["lr0"])
    mlflow.log_param("lrf", args["lrf"])
    mlflow.log_param("imgsz", args["imgsz"])
    mlflow.log_param("patience", args["patience"])
    mlflow.log_param("dataset_size", data_stats["total_images"])
    mlflow.log_param("gpu", gpu_name)
    mlflow.log_param("runtime", "WSL2 ROCm")
    mlflow.log_param("augment_level", "medium-heavy" if stage == 1 else "reduced")


def train_stage1(model_key, config):
    """Run stage 1 training for one model."""
    import torch

    print(f"\n{'=' * 70}")
    print(f"Stage 1 Training: {model_key} (version={VERSION})")
    print(f"  Weights: {config['weights']}")
    print(f"  Task:    {config['task']}")
    print(f"  Data:    {config['data']}")
    print(f"  Batch:   {config['batch']}, nbs=64, fl_gamma=1.5, amp=True, freeze=10")
    print(f"{'=' * 70}")

    os.environ["MLFLOW_EXPERIMENT_NAME"] = "yolo26_ppe_v4_recipe"

    args = get_stage1_args(config["batch"])
    model = YOLO(config["weights"])

    # Read dataset stats
    analysis_path = os.path.join(BASE, "yolo26_ppe", "data", "analysis", "data_analysis.json")
    with open(analysis_path) as f:
        data_stats = json.load(f)

    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    if "CPU" in gpu_name:
        print("ERROR: GPU not available! Refusing to run on CPU.")
        sys.exit(1)

    project_abs = os.path.join(BASE, config["project"])
    data_abs = config["data"]  # already absolute (/tmp path)

    t0 = time.time()
    with mlflow.start_run(run_name=f"{model_key}_stage1_{VERSION}"):
        results = model.train(
            data=data_abs,
            project=project_abs,
            name="run1",
            **args,
        )
        train_time = time.time() - t0

        try:
            log_common_params(model_key, config, 1, args, gpu_name, data_stats)
            mlflow.log_metric("train_time_seconds", train_time)
            best_pt = os.path.join(project_abs, "run1", "weights", "best.pt")
            if os.path.exists(best_pt):
                mlflow.log_metric("model_size_mb", os.path.getsize(best_pt) / 1e6)
            params = sum(p.numel() for p in model.model.parameters()) / 1e6
            mlflow.log_metric("params_M", params)
        except Exception as e:
            print(f"  MLflow log warning: {e}")

        # Inference timing
        try:
            data_dir = os.path.dirname(data_abs)
            test_img_dir = os.path.join(data_dir, "images", "test")
            test_images = sorted(glob.glob(os.path.join(test_img_dir, "*.jpg")))
            if test_images:
                single_img = test_images[0]
                model.predict(source=single_img, verbose=False)
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

    print(f"\n  Stage 1 training time: {train_time:.1f}s ({train_time/60:.1f} min)")
    print(f"  Stage 1 weights: {project_abs}/run1/weights/best.pt")

    del model
    torch.cuda.empty_cache()
    return results


def train_stage2(model_key, config):
    """Run stage 2 fine-tuning for one model."""
    import torch

    print(f"\n{'=' * 70}")
    print(f"Stage 2 Fine-tuning: {model_key} (version={VERSION})")
    print(f"  Task:    {config['task']}")
    print(f"  Batch:   {config['batch']}, lr0=0.001, freeze=0, patience=15")
    print(f"{'=' * 70}")

    os.environ["MLFLOW_EXPERIMENT_NAME"] = "yolo26_ppe_v4_recipe_stage2"

    stage1_best = os.path.join(BASE, config["project"], "run1", "weights", "best.pt")
    if not os.path.exists(stage1_best):
        print(f"  ERROR: Stage 1 best.pt not found: {stage1_best}")
        print(f"  Run stage 1 first.")
        return None

    args = get_stage2_args(config["batch"])
    model = YOLO(stage1_best)

    analysis_path = os.path.join(BASE, "yolo26_ppe", "data", "analysis", "data_analysis.json")
    with open(analysis_path) as f:
        data_stats = json.load(f)

    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
    if "CPU" in gpu_name:
        print("ERROR: GPU not available! Refusing to run on CPU.")
        sys.exit(1)

    project_abs = os.path.join(BASE, config["project"])
    data_abs = config["data"]

    t0 = time.time()
    with mlflow.start_run(run_name=f"{model_key}_stage2_{VERSION}"):
        results = model.train(
            data=data_abs,
            project=project_abs,
            name="run2_stage2",
            **args,
        )
        train_time = time.time() - t0

        try:
            log_common_params(model_key, config, 2, args, gpu_name, data_stats)
            mlflow.log_param("stage1_weights", stage1_best)
            mlflow.log_metric("stage2_train_time_seconds", train_time)
            stage2_best = os.path.join(project_abs, "run2_stage2", "weights", "best.pt")
            if os.path.exists(stage2_best):
                mlflow.log_metric("stage2_model_size_mb", os.path.getsize(stage2_best) / 1e6)
                mlflow.log_metric("stage1_model_size_mb", os.path.getsize(stage1_best) / 1e6)
            params = sum(p.numel() for p in model.model.parameters()) / 1e6
            mlflow.log_metric("params_M", params)
        except Exception as e:
            print(f"  MLflow log warning: {e}")

        # Inference timing
        try:
            data_dir = os.path.dirname(data_abs)
            test_img_dir = os.path.join(data_dir, "images", "test")
            test_images = sorted(glob.glob(os.path.join(test_img_dir, "*.jpg")))
            if test_images:
                single_img = test_images[0]
                model.predict(source=single_img, verbose=False)
                times = []
                for _ in range(10):
                    ti = time.time()
                    model.predict(source=single_img, verbose=False)
                    times.append(time.time() - ti)
                inference_ms = (sum(times) / len(times)) * 1000
                mlflow.log_metric("stage2_inference_ms", inference_ms)
                print(f"  Inference: {inference_ms:.1f} ms/image (avg of 10)")
        except Exception as e:
            print(f"  Inference timing warning: {e}")

    print(f"\n  Stage 2 training time: {train_time:.1f}s ({train_time/60:.1f} min)")
    print(f"  Stage 2 weights: {project_abs}/run2_stage2/weights/best.pt")

    del model
    torch.cuda.empty_cache()
    return results


def main():
    parser = argparse.ArgumentParser(description="Full recipe training (v4_recipe) for all 4 models")
    parser.add_argument("--stage", choices=[1, 2, 12], type=int, default=12,
                        help="Stage to run: 1=stage1 only, 2=stage2 only, 12=both (default)")
    parser.add_argument("--model", choices=["n", "s"], help="Model size (single model)")
    parser.add_argument("--task", choices=["detect", "segment"], help="Task (single model)")
    args = parser.parse_args()

    # Select models
    if args.model and args.task:
        key = f"{args.model}_{'seg' if args.task == 'segment' else 'detect'}"
        if key not in MODELS:
            print(f"Unknown model: {key}")
            sys.exit(1)
        model_list = [(key, MODELS[key])]
    else:
        model_list = list(MODELS.items())

    # Verify /tmp datasets exist
    for _, cfg in model_list:
        if not os.path.exists(cfg["data"]):
            print(f"ERROR: Dataset not found: {cfg['data']}")
            print("Run dataset copy first:")
            print("  cp -rL yolo26_ppe/data/yolo_detect_v2/* /tmp/yolo_detect_data/")
            print("  cp -rL yolo26_ppe/data/yolo_segment_v2/* /tmp/yolo_seg_data/")
            sys.exit(1)

    print(f"\n{'#' * 70}")
    print(f"# Recipe: {VERSION}")
    print(f"#   Focal Loss (fl_gamma=1.5)")
    print(f"#   Gradient Accumulation (nbs=64)")
    print(f"#   AMP (mixed precision)")
    print(f"#   Two-stage: Stage1 (freeze=10, lr0=0.01) → Stage2 (freeze=0, lr0=0.001)")
    print(f"#   Models: {[k for k, _ in model_list]}")
    print(f"#   Stage: {args.stage}")
    print(f"{'#' * 70}\n")

    for model_key, config in model_list:
        if args.stage in (1, 12):
            train_stage1(model_key, config)
        if args.stage in (2, 12):
            train_stage2(model_key, config)

    print(f"\n{'=' * 70}")
    print(f"All training complete for {VERSION}!")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
