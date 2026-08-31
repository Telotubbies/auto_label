"""Step 12: Two-stage fine-tuning for YOLO26 PPE models.

Stage 1 (already done by 03_train.py): freeze backbone (freeze=10), train head
Stage 2 (this script): unfreeze all layers, fine-tune full model with low LR

This implements the standard transfer-learning recipe:
  Stage 1: Pretrained backbone → freeze → train head only (high LR)
  Stage 2: Unfreeze all → fine-tune everything (low LR, e.g. 10x lower)

Usage:
  python 12_finetune_stage2.py --model s --task detect
  python 12_finetune_stage2.py --all
"""
import argparse
import glob
import json
import os
import sys
import time

import yaml

os.environ.setdefault("HSA_ENABLE_DXG_DETECTION", "1")
os.environ.setdefault("TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL", "1")

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MLFLOW_DB = os.path.join(BASE, "yolo26_ppe", "mlflow", "mlflow.db")
os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{MLFLOW_DB}"
os.environ["MLFLOW_EXPERIMENT_NAME"] = "yolo26_ppe_stage2"

from ultralytics import YOLO, settings
import mlflow

settings.update({"mlflow": True})

with open(os.path.join(BASE, "yolo26_ppe", "configs", "train.yaml")) as f:
    TRAIN_CFG = yaml.safe_load(f)
with open(os.path.join(BASE, "yolo26_ppe", "configs", "augmentation.yaml")) as f:
    AUG_CFG = yaml.safe_load(f)

MODELS = TRAIN_CFG["models"]

# Stage 2 config — unfreeze + low LR + shorter training
# Key differences from stage 1 (03_train.py):
#   freeze=0          → unfreeze ALL layers (was 10)
#   lr0=0.001         → 10x lower than stage 1 (was 0.01)
#   lrf=0.01          → cosine decay to 1% of lr0 (same schedule shape)
#   epochs=50         → shorter (stage 1 already converged the head)
#   patience=15       → tighter early stopping
#   close_mosaic=5    → disable mosaic earlier (stabilize final convergence)
#   warmup_epochs=1   → shorter warmup (model is already warmed up from stage 1)
STAGE2_ARGS = {
    "epochs": 50,
    "imgsz": 640,
    "batch": 16,
    "patience": 15,
    "freeze": 0,              # ← KEY: unfreeze all layers
    "cls_pw": 0.5,
    # Optimizer — 10x lower LR than stage 1
    "lr0": 0.001,             # ← was 0.01 in stage 1
    "lrf": 0.01,              # cosine decay factor (lr0 → lr0*lrf)
    "momentum": 0.937,
    "weight_decay": 0.0005,
    "warmup_epochs": 1,       # ← shorter (model already warmed up)
    "warmup_momentum": 0.8,
    "warmup_bias_lr": 0.01,
    # Loss weights (same as stage 1)
    "box": 7.5,
    "cls": 0.5,
    "dfl": 1.5,
    # Focal Loss — keep enabled from stage 1 (class imbalance persists)
    "fl_gamma": 1.5,
    # Gradient Accumulation — same effective batch as stage 1
    "nbs": 64,
    # Mixed precision
    "amp": True,
    # Save + val
    "save": True,
    "save_period": -1,
    "val": True,
    "plots": True,
    "exist_ok": True,
    # Augmentation — slightly reduced (model is past the heavy-aug phase)
    "hsv_h": 0.015,
    "hsv_s": 0.5,
    "hsv_v": 0.4,
    "degrees": 5.0,
    "translate": 0.15,
    "scale": 0.4,             # ← less aggressive (was 0.6)
    "shear": 2.0,
    "perspective": 0.0,
    "fliplr": 0.5,
    "flipud": 0.0,
    "mosaic": 0.5,            # ← reduced (was 0.8)
    "mixup": 0.0,             # ← off (was 0.1) — no mixing in fine-tune phase
    "copy_paste": 0.1,
    "close_mosaic": 5,        # ← earlier (was 10)
    "erasing": 0.2,           # ← reduced (was 0.3)
}


def finetune_one(model_key, config):
    """Run stage 2 fine-tuning on a single model."""
    print(f"\n{'=' * 70}")
    print(f"Stage 2 Fine-tuning: {model_key}")
    print(f"  Task:    {config['task']}")
    print(f"  Epochs:  {STAGE2_ARGS['epochs']}, LR: {STAGE2_ARGS['lr0']}, Freeze: {STAGE2_ARGS['freeze']}")
    print(f"{'=' * 70}")

    # Stage 1 best.pt — this is our starting point
    stage1_best = os.path.join(BASE, config["project"], "run1", "weights", "best.pt")
    if not os.path.exists(stage1_best):
        print(f"  ERROR: Stage 1 best.pt not found: {stage1_best}")
        print(f"  Run 03_train.py first to produce stage 1 weights.")
        return None

    # Load stage 1 weights (NOT the original pretrained — we continue from stage 1)
    model = YOLO(stage1_best)

    # Read dataset stats
    analysis_path = os.path.join(BASE, "yolo26_ppe", "data", "analysis", "data_analysis.json")
    with open(analysis_path) as f:
        data_stats = json.load(f)

    # GPU info
    import torch
    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"

    # Absolute paths
    project_abs = os.path.join(BASE, config["project"])
    data_abs = os.path.join(BASE, config["data"])

    t0 = time.time()
    with mlflow.start_run(run_name=f"{model_key}_stage2"):
        results = model.train(
            data=data_abs,
            project=project_abs,
            name="run2_stage2",   # ← distinct from stage 1's "run1"
            **STAGE2_ARGS,
        )
        train_time = time.time() - t0

        # Log stage 2 params
        try:
            mlflow.log_param("model_key", model_key)
            mlflow.log_param("stage", 2)
            mlflow.log_param("stage1_weights", stage1_best)
            mlflow.log_param("freeze", STAGE2_ARGS["freeze"])
            mlflow.log_param("lr0", STAGE2_ARGS["lr0"])
            mlflow.log_param("epochs", STAGE2_ARGS["epochs"])
            mlflow.log_param("dataset_size", data_stats["total_images"])
            mlflow.log_param("gpu", gpu_name)
            mlflow.log_param("runtime", "WSL2 ROCm")
            # New training-recipe params (#5 Focal, #3 Grad Accum, #3 AMP)
            mlflow.log_param("fl_gamma", STAGE2_ARGS["fl_gamma"])
            mlflow.log_param("nbs", STAGE2_ARGS["nbs"])
            mlflow.log_param("amp", STAGE2_ARGS["amp"])
            accum_steps = max(1, STAGE2_ARGS["nbs"] // STAGE2_ARGS["batch"])
            mlflow.log_param("gradient_accum_steps", accum_steps)
            mlflow.log_param("effective_batch", STAGE2_ARGS["batch"] * accum_steps)
        except Exception as e:
            print(f"  MLflow param log warning: {e}")

        # Log stage 2 metrics
        try:
            mlflow.log_metric("stage2_train_time_seconds", train_time)
            stage2_best = os.path.join(project_abs, "run2_stage2", "weights", "best.pt")
            if os.path.exists(stage2_best):
                mlflow.log_metric("stage2_model_size_mb", os.path.getsize(stage2_best) / 1e6)
                # Compare stage 1 vs stage 2 model size
                stage1_size = os.path.getsize(stage1_best) / 1e6
                mlflow.log_metric("stage1_model_size_mb", stage1_size)
            params = sum(p.numel() for p in model.model.parameters()) / 1e6
            mlflow.log_metric("params_M", params)
        except Exception as e:
            print(f"  MLflow metric log warning: {e}")

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
                print(f"  Inference: {inference_ms:.1f} ms/image")
        except Exception as e:
            print(f"  Inference timing warning: {e}")

    print(f"\n  Stage 2 training time: {train_time:.1f}s ({train_time/60:.1f} min)")
    print(f"  Stage 2 weights: {project_abs}/run2_stage2/weights/best.pt")

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    return results


def main():
    parser = argparse.ArgumentParser(description="Stage 2 fine-tuning (unfreeze + low LR)")
    parser.add_argument("--model", choices=["n", "s"], help="Model size")
    parser.add_argument("--task", choices=["detect", "segment"], help="Task type")
    parser.add_argument("--all", action="store_true", help="Fine-tune all 4 models")
    args = parser.parse_args()

    if args.all:
        for key, config in MODELS.items():
            finetune_one(key, config)
    elif args.model and args.task:
        key = f"{args.model}_{'seg' if args.task == 'segment' else 'detect'}"
        if key not in MODELS:
            print(f"Unknown model: {key}")
            sys.exit(1)
        finetune_one(key, MODELS[key])
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
