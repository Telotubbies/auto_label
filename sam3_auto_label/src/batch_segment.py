"""Batch segment all images using SAM 3.1 with YAML config.

Features:
  - Checkpoint/resume: บันทึกความคืบหน้า ถ้าคอมดับกลางคันรันต่อได้
  - ETA estimation: ประเมินเวลาที่เหลือจากค่าเฉลี่ย

Usage:
    python src/batch_segment.py                          # use config/ppe.yaml
    python src/batch_segment.py --resume                 # resume from checkpoint
    python src/batch_segment.py --fresh                  # start fresh (delete checkpoint)
    python src/batch_segment.py --threshold 0.5          # override threshold
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from glob import glob

from PIL import Image
from tqdm import tqdm

from config import load_config, Config
from exporters import write_image_exports, finalize_exports
from inference import (
    build_model,
    segment_image,
    save_coco,
    save_viz,
)
from tracker import ExperimentTracker

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

def checkpoint_path(cfg: Config):
    return os.path.join(cfg.output_path, "checkpoint.json")


def load_checkpoint(cfg: Config):
    """Load checkpoint. Returns dict with processed images or None."""
    path = checkpoint_path(cfg)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"checkpoint corrupt, ignoring: {e}")
        return None


def save_checkpoint(cfg: Config, ckpt: dict):
    """Save checkpoint atomically."""
    path = checkpoint_path(cfg)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(ckpt, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomic on same filesystem


def delete_checkpoint(cfg: Config):
    path = checkpoint_path(cfg)
    if os.path.exists(path):
        os.remove(path)
        log.info("deleted old checkpoint")


def format_eta(seconds):
    """Format seconds to human readable."""
    if seconds < 0:
        return "?"
    td = timedelta(seconds=int(seconds))
    return str(td)


# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="SAM 3.1 batch segmentation")
    p.add_argument("-c", "--config", default="config/ppe.yaml", help="path to YAML config")
    p.add_argument("--threshold", type=float, help="override confidence threshold")
    p.add_argument("--resolution", type=int, help="override input resolution")
    p.add_argument("--device", choices=["auto", "cpu", "cuda", "rocm", "mps"], help="override device")
    p.add_argument("--input", help="override input directory")
    p.add_argument("--output", help="override output directory")
    p.add_argument("--resume", action="store_true", help="resume from checkpoint")
    p.add_argument("--fresh", action="store_true", help="start fresh, delete checkpoint")
    return p.parse_args()


def ask_resume(ckpt):
    """Interactive prompt: resume or fresh?"""
    processed = len(ckpt.get("processed", {}))
    total = ckpt.get("total_images", 0)
    print(f"\n  Found checkpoint: {processed}/{total} images processed")
    print(f"  Last run: {ckpt.get('started_at', '?')}")
    print()
    while True:
        choice = input("  Resume from checkpoint? [Y/n] ").strip().lower()
        if choice in ("", "y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print("  Please answer y or n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    cfg = load_config(args.config)

    # CLI overrides
    if args.threshold is not None:
        cfg.inference.confidence_threshold = args.threshold
    if args.resolution is not None:
        cfg.inference.resolution = args.resolution
    if args.device is not None:
        cfg.inference.device = args.device
    if args.input is not None:
        cfg.output.input_dir = args.input
    if args.output is not None:
        cfg.output.output_dir = args.output

    log.info("=" * 60)
    log.info("SAM 3.1 batch segmentation")
    log.info(f"  config: {args.config}")
    log.info(f"  threshold: {cfg.inference.confidence_threshold}")
    log.info(f"  resolution: {cfg.inference.resolution}")
    log.info(f"  categories: {len(cfg.categories)}")
    log.info("=" * 60)

    # Ensure dirs (format exporters create their own output/<fmt>/ dirs)
    for d in [cfg.coco_path, cfg.viz_path]:
        os.makedirs(d, exist_ok=True)

    # Experiment tracker (init only; start_run after images found)
    tracker = ExperimentTracker(cfg)
    exp_id = None

    # Find images — all supported extensions
    exts = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.webp", "*.tiff", "*.tif",
            "*.JPG", "*.JPEG", "*.PNG", "*.WEBP", "*.TIFF", "*.TIF")
    image_files = []
    for ext in exts:
        image_files.extend(glob(os.path.join(cfg.input_path, ext)))
    image_files = sorted(set(image_files))

    if not image_files:
        log.warning("no images found. exiting.")
        return

    total_images = len(image_files)
    log.info(f"found {total_images} image(s)")

    # Start experiment tracking
    exp_id = tracker.start_run(cfg, [os.path.basename(f) for f in image_files])

    # Checkpoint logic
    ckpt = load_checkpoint(cfg)
    do_resume = False

    if args.fresh:
        delete_checkpoint(cfg)
        ckpt = None
        log.info("starting fresh (checkpoint deleted)")
    elif args.resume:
        if ckpt is None:
            log.info("no checkpoint found, starting fresh")
        else:
            do_resume = True
            log.info("resuming from checkpoint")
    elif ckpt is not None:
        # Interactive prompt
        if sys.stdin.isatty():
            do_resume = ask_resume(ckpt)
            if not do_resume:
                delete_checkpoint(cfg)
                ckpt = None
        else:
            # Non-interactive: auto-resume
            do_resume = True
            log.info("checkpoint found, auto-resuming (use --fresh to restart)")

    # Initialize checkpoint
    if do_resume and ckpt is not None:
        processed = ckpt.get("processed", {})
        # Filter out images that are already done
        pending = [f for f in image_files if os.path.basename(f) not in processed]
        log.info(f"  already processed: {len(processed)}")
        log.info(f"  remaining: {len(pending)}")
    else:
        processed = {}
        pending = list(image_files)
        ckpt = {
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_images": total_images,
            "processed": {},
            "config": {
                "threshold": cfg.inference.confidence_threshold,
                "resolution": cfg.inference.resolution,
                "categories": [c.name for c in cfg.categories],
            },
        }
        save_checkpoint(cfg, ckpt)

    if not pending:
        log.info("all images already processed. rebuilding combined outputs...")
        # Rebuild combined COCO from per-image files
        rebuild_combined(cfg, processed)
        return

    # Estimate time
    if processed:
        times = [v.get("time", 0) for v in processed.values() if v.get("time")]
        if times:
            avg = sum(times) / len(times)
            eta = avg * len(pending)
            log.info(f"  avg time/image: {avg:.1f}s")
            log.info(f"  estimated remaining: {format_eta(eta)} ({len(pending)} images)")
    else:
        log.info(f"  estimated: ~{total_images * 40}s (first run, will calibrate)")

    # Build model
    log.info("Building SAM 3.1 model...")
    t0 = time.time()
    processor = build_model(cfg)
    log.info(f"model loaded in {time.time() - t0:.1f}s")

    # Process
    all_images = []
    all_annotations = []
    ann_id = 1
    errors = []

    # If resuming, load previous data from per-image files
    if do_resume and processed:
        all_images, all_annotations = load_previous_results(cfg, processed)
        ann_id = max(a["id"] for a in all_annotations) + 1 if all_annotations else 1

    # Build index map for O(1) lookup (avoid O(n^2) with .index())
    image_id_map = {path: i + 1 for i, path in enumerate(image_files)}

    pbar = tqdm(pending, desc="Processing", initial=len(processed), total=total_images)

    # Prefetch: load next image in a background thread while GPU processes current.
    # This keeps the GPU fed — image I/O overlaps with inference instead of serializing.
    prefetch_executor = ThreadPoolExecutor(max_workers=1)

    # Export pipeline: save_coco + save_viz + write_image_exports run in a
    # background thread so the GPU can start the next image immediately.
    # This overlaps CPU export (~0.1s) with GPU inference (~0.65s),
    # pushing GPU utilization from ~87% toward ~100%.
    # Disabled when cfg.inference.pipeline_export=False (sequential export).
    use_pipeline = getattr(cfg.inference, "pipeline_export", True)
    export_executor = ThreadPoolExecutor(max_workers=1) if use_pipeline else None
    export_future = None  # tracks the in-progress export task

    def load_image(path):
        """Load and convert image in background thread."""
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            return None

    def export_image(image, name, basename, image_info, annotations, img_path):
        """Save all per-image outputs (runs in background thread)."""
        try:
            save_coco(image_info, annotations, os.path.join(cfg.coco_path, f"{name}.json"), cfg)
            write_image_exports(cfg, image_info, annotations)
            if cfg.output.save_viz:
                save_viz(image, name, annotations, os.path.join(cfg.viz_path, f"{name}.png"), cfg)
        except Exception as e:
            log.error(f"export failed: {basename} — {e}")

    # Prime the pipeline: start loading the first image
    pending_iter = iter(pending)
    try:
        first_path = next(pending_iter)
    except StopIteration:
        first_path = None

    next_future = prefetch_executor.submit(load_image, first_path) if first_path else None

    for img_path in pbar:
        name = os.path.splitext(os.path.basename(img_path))[0]
        basename = os.path.basename(img_path)
        t1 = time.time()

        try:
            # Wait for the prefetched image (already loading in background)
            image = next_future.result() if next_future else None

            # Start prefetching the NEXT image immediately (non-blocking)
            try:
                next_path = next(pending_iter)
                next_future = prefetch_executor.submit(load_image, next_path)
            except StopIteration:
                next_future = None

            if image is None:
                raise RuntimeError(f"failed to load {img_path}")

            W, H = image.size

            # img_id = position in full image list (O(1) lookup)
            img_id = image_id_map[img_path]

            annotations, ann_id = segment_image(processor, image, img_id, ann_id, cfg)

            image_info = {
                "id": img_id,
                "file_name": basename,
                "width": W,
                "height": H,
            }
            all_images.append(image_info)
            all_annotations.extend(annotations)

            # Pipeline: wait for PREVIOUS export (should be done — it ran
            # during this image's GPU inference), then start exporting
            # current image in background for next iteration's GPU to overlap.
            # When pipeline disabled: export synchronously (GPU waits for CPU).
            if use_pipeline:
                if export_future is not None:
                    export_future.result()
                export_future = export_executor.submit(
                    export_image, image, name, basename, image_info, annotations, img_path,
                )
            else:
                export_image(image, name, basename, image_info, annotations, img_path)

            # Free image memory — export thread has its own reference
            del image

            elapsed = time.time() - t1

            # Update checkpoint
            processed[basename] = {
                "time": round(elapsed, 1),
                "annotations": len(annotations),
            }
            ckpt["processed"] = processed
            save_checkpoint(cfg, ckpt)

            # Track in experiment DB
            if exp_id:
                tracker.log_image_result(
                    exp_id, basename, len(annotations), elapsed,
                )

            # ETA update
            times = [v.get("time", 0) for v in processed.values() if v.get("time")]
            if times:
                avg = sum(times) / len(times)
                remaining = total_images - len(processed)
                eta = avg * remaining
                pbar.set_postfix({
                    "avg": f"{avg:.1f}s",
                    "ETA": format_eta(eta),
                })

            log.info(f"[OK] {basename}: {len(annotations)} anns in {elapsed:.1f}s")

        except Exception as e:
            log.error(f"failed: {basename} — {e}")
            errors.append({"image": basename, "error": str(e)})
            # Still mark as processed (with error) so we don't retry forever
            processed[basename] = {"time": 0, "annotations": 0, "error": str(e)}
            ckpt["processed"] = processed
            save_checkpoint(cfg, ckpt)

    pbar.close()
    prefetch_executor.shutdown(wait=False)

    # Wait for the last export to finish before saving combined outputs
    if export_future is not None:
        export_future.result()
    if export_executor is not None:
        export_executor.shutdown(wait=True)

    # Save combined outputs
    save_combined(cfg, all_images, all_annotations, errors)

    # Compute final metrics
    times = [v.get("time", 0) for v in processed.values() if v.get("time", 0) > 0]
    total_time = sum(times)
    avg_time = total_time / len(times) if times else 0

    # Log to experiment tracker
    if exp_id:
        tracker.log_metrics(exp_id, {
            "annotations": len(all_annotations),
            "total_time": total_time,
            "avg_time": avg_time,
            "errors": len(errors),
        })
        tracker.end_run(exp_id, status="failed" if errors else "completed")

    # Final summary
    log.info("=" * 60)
    log.info("DONE")
    log.info(f"  images:      {len(processed)}/{total_images}")
    log.info(f"  annotations: {len(all_annotations)}")
    if errors:
        log.info(f"  errors:      {len(errors)}")
    log.info(f"  experiment:  {exp_id}")
    log.info(f"  output:      {cfg.output_path}")
    log.info("=" * 60)

    # Clean checkpoint on success
    if not errors:
        delete_checkpoint(cfg)
        log.info("checkpoint cleared (all done, no errors)")


def load_previous_results(cfg: Config, processed: dict):
    """Load previously processed results from per-image COCO files."""
    all_images = []
    all_annotations = []

    for basename, info in processed.items():
        if info.get("error"):
            continue
        name = os.path.splitext(basename)[0]
        coco_path = os.path.join(cfg.coco_path, f"{name}.json")
        if not os.path.exists(coco_path):
            continue
        with open(coco_path, "r", encoding="utf-8") as f:
            coco = json.load(f)
        all_images.extend(coco.get("images", []))
        all_annotations.extend(coco.get("annotations", []))

    return all_images, all_annotations


def save_combined(cfg: Config, all_images, all_annotations, errors):
    """Save combined dataset exports."""
    finalize_exports(cfg, all_images, all_annotations)

    if errors:
        report = {
            "summary": {"total": len(all_images), "errors": len(errors)},
            "errors": errors,
        }
        with open(os.path.join(cfg.output_path, "errors.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)


def rebuild_combined(cfg: Config, processed: dict):
    """Rebuild combined outputs from per-image files (when all already done)."""
    all_images, all_annotations = load_previous_results(cfg, processed)
    save_combined(cfg, all_images, all_annotations, [])
    log.info(f"rebuilt: {len(all_images)} images, {len(all_annotations)} annotations")


if __name__ == "__main__":
    main()
