#!/usr/bin/env python3
"""Test SAM 3.1 text prompts on a single image.

Loads the model once, runs each prompt independently, and writes per-prompt
outputs under the output directory:

  <out>/<prompt_slug>/viz.png            overlay (masks + boxes + scores)
  <out>/<prompt_slug>/objects/obj_XX.png transparent cutout per detection
  <out>/<prompt_slug>/detections.json    scores + boxes

Usage:
  ./sam3_venv/bin/python test_ic_prompts.py \
      --image /mnt/c/Users/Gigabyte/Downloads/DIP-ic-packaging.webp \
      --prompts "ic" "ic package" \
      --output /mnt/c/Users/Gigabyte/Downloads/sam3_ic_test
"""

import argparse
import json
import os
import re
import sys

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from config import load_config  # noqa: E402
from inference import build_model, _to_float32, device_type, _gpu_bbox_nms  # noqa: E402

DET_COLORS = [
    (255, 56, 56), (255, 157, 51), (255, 220, 60), (74, 222, 128),
    (56, 189, 248), (167, 139, 250), (244, 114, 182), (45, 212, 191),
]


def slugify(prompt: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")


def run_prompt(processor, state, prompt, image, out_dir, threshold):
    """Run one text prompt, save viz + object cutouts, return detections."""
    import cv2

    processor.reset_all_prompts(state)
    output = processor.set_text_prompt(state=state, prompt=prompt)

    masks = output.get("masks")
    boxes = output.get("boxes")
    scores = output.get("scores")
    n = 0 if scores is None else len(scores)

    W, H = image.size
    img_np = np.array(image)  # RGB
    dets = []

    if n:
        scores_f = _to_float32(scores).float()
        keep = scores_f >= threshold
        idx = torch.nonzero(keep, as_tuple=True)[0]
        if len(idx):
            scores_f = scores_f[idx]
            boxes_f = _to_float32(boxes)[idx] if boxes is not None else None
            masks_b = _to_float32(masks)[idx].bool() if masks is not None else None
            if masks_b is not None and masks_b.ndim > 3:
                masks_b = masks_b.squeeze(1)

            # within-prompt NMS on bbox IoU 0.5
            if boxes_f is not None and len(idx) > 1:
                keep_mask = _gpu_bbox_nms(scores_f, boxes_f, 0.5, device=scores_f.device)
                ki = torch.nonzero(keep_mask, as_tuple=True)[0]
                scores_f = scores_f[ki]
                boxes_f = boxes_f[ki]
                masks_b = masks_b[ki] if masks_b is not None else None

            scores_np = scores_f.cpu().numpy()
            boxes_np = boxes_f.cpu().numpy() if boxes_f is not None else None
            masks_np = masks_b.cpu().numpy() if masks_b is not None else None

            for i in range(len(scores_np)):
                dets.append({
                    "score": float(scores_np[i]),
                    "box_xyxy": boxes_np[i].tolist() if boxes_np is not None else None,
                    "mask": masks_np[i] if masks_np is not None else None,
                    "color": DET_COLORS[i % len(DET_COLORS)],
                })

    # --- visualization overlay ---
    vis = img_np.copy()
    overlay = img_np.copy()
    for i, d in enumerate(dets):
        color = d["color"]  # RGB
        if d["mask"] is not None:
            overlay[d["mask"] > 0] = color
        if d["box_xyxy"] is not None:
            x0, y0, x1, y1 = [int(v) for v in d["box_xyxy"]]
            cv2.rectangle(vis, (x0, y0), (x1, y1), color, 2)
            label = f"#{i + 1} {d['score']:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            yt = max(y0 - 5, th + 2)
            cv2.rectangle(vis, (x0, yt - th - 4), (x0 + tw + 4, yt + 2), color, -1)
            cv2.putText(vis, label, (x0 + 2, yt), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.45, vis, 0.55, 0, vis)
    title = f'prompt="{prompt}"  detections={len(dets)}'
    cv2.putText(vis, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imwrite(os.path.join(out_dir, "viz.png"), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))

    # --- per-object transparent cutouts ---
    obj_dir = os.path.join(out_dir, "objects")
    os.makedirs(obj_dir, exist_ok=True)
    img_rgba = np.dstack([img_np, np.full((H, W), 255, dtype=np.uint8)])
    for i, d in enumerate(dets):
        if d["box_xyxy"] is not None:
            x0, y0, x1, y1 = [int(round(v)) for v in d["box_xyxy"]]
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(W, x1), min(H, y1)
        else:
            ys, xs = np.where(d["mask"] > 0)
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        crop = img_rgba[y0:y1, x0:x1].copy()
        if d["mask"] is not None:
            crop[..., 3] = (d["mask"][y0:y1, x0:x1].astype(np.uint8) * 255)
        Image.fromarray(crop, "RGBA").save(
            os.path.join(obj_dir, f"obj_{i + 1:02d}_score{d['score']:.2f}.png"))
        d["crop"] = [x0, y0, x1, y1]

    summary = [{
        "id": i + 1,
        "score": round(d["score"], 4),
        "box_xyxy": [round(v, 1) for v in d["box_xyxy"]] if d["box_xyxy"] else None,
        "mask_area_px": int(d["mask"].sum()) if d["mask"] is not None else None,
    } for i, d in enumerate(dets)]
    with open(os.path.join(out_dir, "detections.json"), "w") as f:
        json.dump({"prompt": prompt, "image_size": [W, H],
                   "threshold": threshold, "detections": summary}, f, indent=2)
    return dets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--prompts", nargs="+", default=["ic", "ic package"])
    ap.add_argument("--output", required=True)
    ap.add_argument("--config", default="config/ppe_4class.yaml")
    ap.add_argument("--threshold", type=float, default=None,
                    help="override confidence threshold (default: config value)")
    ap.add_argument("--device", default=None, choices=["auto", "cpu", "cuda", "rocm"])
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.device:
        cfg.inference.device = args.device
    threshold = args.threshold if args.threshold is not None else cfg.inference.confidence_threshold

    image = Image.open(args.image).convert("RGB")
    print(f"image: {args.image} ({image.size[0]}x{image.size[1]})")
    print(f"threshold: {threshold}")

    # position_encoding.py hardcodes device="cuda" for precomputed pos-enc
    # tensors. On GPU-less runs, redirect those allocs to CPU during build only.
    print("building SAM 3.1 model ...", flush=True)
    if not torch.cuda.is_available():
        real_zeros = torch.zeros

        def cpu_zeros(*a, **k):
            if k.get("device") == "cuda":
                k["device"] = "cpu"
            return real_zeros(*a, **k)

        torch.zeros = cpu_zeros
        try:
            processor = build_model(cfg)
        finally:
            torch.zeros = real_zeros
        # Sam3Processor defaults device="cuda" regardless of model device.
        processor.device = torch.device("cpu")
    else:
        processor = build_model(cfg)
    dev = device_type(processor.device)
    print(f"device: {processor.device}")

    ac_dtype = torch.bfloat16 if dev in ("cuda", "cpu") else torch.float16
    with torch.inference_mode(), \
         torch.autocast(dev, dtype=ac_dtype, enabled=dev in ("cuda", "cpu")):
        state = processor.set_image(image)
        for prompt in args.prompts:
            out_dir = os.path.join(args.output, slugify(prompt))
            os.makedirs(out_dir, exist_ok=True)
            dets = run_prompt(processor, state, prompt, image, out_dir, threshold)
            scores = ", ".join(f"{d['score']:.3f}" for d in dets) or "-"
            print(f'\n[{prompt}] -> {len(dets)} detection(s): {scores}')
            print(f'  output: {out_dir}')

    print("\ndone.")


if __name__ == "__main__":
    main()
