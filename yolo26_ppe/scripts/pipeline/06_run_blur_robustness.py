#!/usr/bin/env python3
"""Run 4 ONNX models on blurred dataset, save annotated outputs + summary.
- Uses SAM-style perceptual colors (generate_colors with seed=42, LAB kmeans)
- For seg models: draws actual segmentation masks (coef @ proto) + bbox
- For detect models: draws bbox only
- Class order from dataset: {0: person, 1: helmet, 2: boots, 3: shoes, 4: harness}
"""
import onnxruntime as ort
import numpy as np
import cv2
import json
import time
from pathlib import Path
from skimage.color import lab2rgb, rgb2lab
from sklearn.cluster import KMeans

# Paths
ONNX_DIR = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/onnx_models/production")
INPUT_DIR = Path("/mnt/e/02_Projects/auto_label/data/raw/blurred")
OUT_BASE = Path("/mnt/e/02_Projects/auto_label/yolo26_ppe/artifacts/onnx_inference_results/blur_robustness")

MODELS = ["medium_detection", "medium_segmentation"]
# Class order from dataset (verified against ONNX metadata)
CLASSES = ["person", "helmet", "closed footwear", "harness"]

# ONNX input
IMGSZ = 640
CONF_THRES = 0.25
IOU_THRES = 0.45
MASK_ALPHA = 0.45  # mask overlay opacity

# --- SAM-style perceptual colors (same as sam3/visualization_utils.py) ---
def generate_colors(n_colors=256, n_samples=5000):
    np.random.seed(42)
    rgb = np.random.rand(n_samples, 3)
    lab = rgb2lab(rgb.reshape(1, -1, 3)).reshape(-1, 3)
    kmeans = KMeans(n_clusters=n_colors, n_init=10)
    kmeans.fit(lab)
    centers_lab = kmeans.cluster_centers_
    colors_rgb = lab2rgb(centers_lab.reshape(1, -1, 3)).reshape(-1, 3)
    colors_rgb = np.clip(colors_rgb, 0, 1)
    return colors_rgb

# Generate 128 colors (same as SAM) and use first 5 for our classes
_SAM_COLORS = generate_colors(n_colors=128, n_samples=5000)

# Class -> color (BGR uint8 for cv2)
# Use distinct indices for visual separation
CLASS_COLOR_IDX = {
    0: 0,   # person
    1: 10,  # helmet
    2: 25,  # closed footwear
    3: 60,  # harness
}

def class_color_bgr(cls_id):
    """Return BGR uint8 color for a class, SAM-style."""
    idx = CLASS_COLOR_IDX.get(cls_id, cls_id)
    c = _SAM_COLORS[idx % len(_SAM_COLORS)]
    # RGB -> BGR for cv2
    return (int(c[2]*255), int(c[0]*255), int(c[1]*255))

def class_color_rgb(cls_id):
    """Return RGB uint8 color for a class (for mask overlay)."""
    idx = CLASS_COLOR_IDX.get(cls_id, cls_id)
    c = _SAM_COLORS[idx % len(_SAM_COLORS)]
    return (int(c[0]*255), int(c[1]*255), int(c[2]*255))

def get_providers():
    avail = ort.get_available_providers()
    if "ROCMExecutionProvider" in avail:
        return ["ROCMExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]

def letterbox(img, new_shape=640):
    h, w = img.shape[:2]
    r = min(new_shape/h, new_shape/w)
    nh, nw = int(h*r), int(w*r)
    img = cv2.resize(img, (nw, nh))
    pad_h = new_shape - nh
    pad_w = new_shape - nw
    top, left = pad_h//2, pad_w//2
    img = cv2.copyMakeBorder(img, top, pad_h-top, left, pad_w-left,
                             cv2.BORDER_CONSTANT, value=(114,114,114))
    return img, r, (left, top)

def preprocess(img):
    lb, ratio, (dw, dh) = letterbox(img, IMGSZ)
    lb = cv2.cvtColor(lb, cv2.COLOR_BGR2RGB)
    lb = lb.transpose(2,0,1).astype(np.float32)/255.0
    lb = lb[None]
    return lb, ratio, (dw, dh)

def post_end2end(out, ratio, dw, dh, is_seg=False):
    """Parse Ultralytics ONNX output.
    Handles two formats:
    - end2end: [1, 300, 6] or [1, 300, 38] = [x1, y1, x2, y2, conf, cls, (32 mask coeffs)]
    - raw: [1, C, N] where C = 4 + num_classes (cx, cy, w, h, cls_scores...)
    Boxes in 640x640 letterboxed space.
    """
    out = out[0]  # remove batch dim

    # Check if end2end format (300, 6) or (300, 38)
    if out.ndim == 2 and out.shape[0] == 300 and out.shape[1] in (6, 38):
        confs = out[:, 4]
        keep = confs > CONF_THRES
        out = out[keep]
        dets = []
        for row in out:
            x1, y1, x2, y2, conf, cls = row[:6]
            x1o = (x1 - dw) / ratio
            y1o = (y1 - dh) / ratio
            x2o = (x2 - dw) / ratio
            y2o = (y2 - dh) / ratio
            d = {
                "box": [float(x1o), float(y1o), float(x2o), float(y2o)],
                "box_640": [float(x1), float(y1), float(x2), float(y2)],
                "cls": int(cls),
                "conf": float(conf),
            }
            if is_seg and out.shape[1] == 38:
                d["mask_coef"] = row[6:38]
            dets.append(d)
        return dets

    # Raw YOLO format: [C, N] = [4+nc, 8400] (detect) or [4+nc+32, 8400] (seg)
    # channels 0-3: cx, cy, w, h (in 640 letterboxed space)
    # channels 4..4+nc-1: class confidence scores
    # channels 4+nc..: mask coefficients (seg only, 32 values)
    if out.ndim == 2 and out.shape[0] > 4:
        total_c = out.shape[0]
        n_mask_coef = 32 if is_seg else 0
        nc = total_c - 4 - n_mask_coef
        # Transpose to [N, C]
        preds = out.T  # [8400, total_c]
        boxes_cxcywh = preds[:, :4]  # cx, cy, w, h
        class_scores = preds[:, 4:4+nc]  # [N, nc]
        mask_coefs = preds[:, 4+nc:4+nc+n_mask_coef] if is_seg else None  # [N, 32]

        # Get max class per anchor
        cls_ids = np.argmax(class_scores, axis=1)
        confs = np.max(class_scores, axis=1)

        # Filter by confidence
        keep = confs > CONF_THRES
        boxes_cxcywh = boxes_cxcywh[keep]
        cls_ids = cls_ids[keep]
        confs = confs[keep]
        if mask_coefs is not None:
            mask_coefs = mask_coefs[keep]

        if len(confs) == 0:
            return []

        # Convert cxcywh to xyxy in 640 space
        cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2

        # NMS
        import cv2 as _cv2
        boxes_for_nms = np.stack([x1, y1, x2 - x1, y2 - y1], axis=1).tolist()
        keep_idx = _cv2.dnn.NMSBoxes(boxes_for_nms, confs.tolist(), CONF_THRES, IOU_THRES)
        if len(keep_idx) == 0:
            return []
        keep_idx = keep_idx.flatten()

        dets = []
        for idx in keep_idx:
            x1o = (x1[idx] - dw) / ratio
            y1o = (y1[idx] - dh) / ratio
            x2o = (x2[idx] - dw) / ratio
            y2o = (y2[idx] - dh) / ratio
            d = {
                "box": [float(x1o), float(y1o), float(x2o), float(y2o)],
                "box_640": [float(x1[idx]), float(y1[idx]), float(x2[idx]), float(y2[idx])],
                "cls": int(cls_ids[idx]),
                "conf": float(confs[idx]),
            }
            if is_seg and mask_coefs is not None:
                d["mask_coef"] = mask_coefs[idx]
            dets.append(d)
        return dets

    # Unknown format
    print(f"WARN: unknown ONNX output shape: {out.shape}")
    return []

def generate_masks(dets, mask_proto, ratio, dw, dh, orig_shape):
    """Generate binary masks for seg detections.
    mask_proto: [1, 32, 160, 160] from ONNX output1
    mask_coef: [32] per detection
    mask = sigmoid(coef @ proto_flat).reshape(160,160)
    Then crop to bbox region in 640 space, upscale to original.
    """
    if mask_proto is None or not dets:
        return [None] * len(dets)
    proto = mask_proto[0]  # (32, 160, 160)
    proto_flat = proto.reshape(32, -1)  # (32, 25600)
    masks_out = []
    H, W = orig_shape[:2]
    for d in dets:
        coef = np.array(d["mask_coef"])  # (32,)
        # mask = sigmoid(coef @ proto_flat) -> (160*160,)
        mask_logit = coef @ proto_flat  # (25600,)
        mask = 1.0 / (1.0 + np.exp(-mask_logit))
        mask = mask.reshape(160, 160)
        # Crop to bbox in 640 space (downsampled to 160)
        x1, y1, x2, y2 = d["box_640"]
        # Scale from 640 to 160
        sx = 160.0 / 640
        sy = 160.0 / 640
        mx1 = max(0, int(x1 * sx))
        my1 = max(0, int(y1 * sy))
        mx2 = min(160, int(x2 * sx))
        my2 = min(160, int(y2 * sy))
        # Zero out outside bbox
        mask_cropped = np.zeros_like(mask)
        mask_cropped[my1:my2, mx1:mx2] = mask[my1:my2, mx1:mx2]
        # Threshold
        mask_bin = (mask_cropped > 0.5).astype(np.uint8)
        # Resize to 640x640 then crop letterbox padding then scale to original
        mask_640 = cv2.resize(mask_bin, (640, 640), interpolation=cv2.INTER_NEAREST)
        # Remove letterbox padding
        lb_h = int(IMGSZ - 2 * dh) if False else None  # not needed, use ratio
        # Crop padding: 640 -> original via inverse letterbox
        # mask_640 is in 640 space, remove pad then scale by 1/ratio
        # Region without padding: [dw:dw+int(W*ratio), dh:dh+int(H*ratio)]
        roi_w = int(W * ratio)
        roi_h = int(H * ratio)
        mask_roi = mask_640[dh:dh+roi_h, dw:dw+roi_w]
        # Scale to original
        mask_orig = cv2.resize(mask_roi, (W, H), interpolation=cv2.INTER_NEAREST)
        masks_out.append(mask_orig)
    return masks_out

def draw_bbox(img, d, color_bgr):
    x1, y1, x2, y2 = [int(v) for v in d["box"]]
    cv2.rectangle(img, (x1, y1), (x2, y2), color_bgr, 2)
    label = f"{CLASSES[d['cls']]} {d['conf']:.2f}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    cv2.rectangle(img, (x1, max(y1 - th - 6, 0)), (x1 + tw + 6, y1), color_bgr, -1)
    cv2.putText(img, label, (x1 + 3, max(y1 - 4, th + 2)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

def draw_mask(img, mask, color_rgb, alpha=MASK_ALPHA):
    """Overlay mask on image with color and alpha."""
    if mask is None or mask.sum() == 0:
        return
    color = np.array(color_rgb, dtype=np.float32)  # RGB
    overlay = img.copy()
    # mask is HxW binary
    for c in range(3):
        overlay[:, :, c][mask > 0] = color[c]
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

def draw_all(img, dets, masks=None, is_seg=False):
    """Draw masks (if seg) then bboxes on top."""
    out = img.copy()
    if is_seg and masks is not None:
        for d, m in zip(dets, masks):
            if m is not None:
                draw_mask(out, m, class_color_rgb(d["cls"]))
    for d in dets:
        draw_bbox(out, d, class_color_bgr(d["cls"]))
    return out

def run_model(model_name, sess, input_name, images, out_dir, is_seg):
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    total_time = 0
    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"WARN: cannot read {img_path}")
            continue
        lb, ratio, (dw, dh) = preprocess(img)
        t0 = time.time()
        outs = sess.run(None, {input_name: lb})
        t1 = time.time()
        dt = t1 - t0
        total_time += dt
        dets = post_end2end(outs[0], ratio, dw, dh, is_seg)
        masks = None
        if is_seg and len(outs) > 1:
            masks = generate_masks(dets, outs[1], ratio, dw, dh, img.shape)
        ann = draw_all(img, dets, masks, is_seg)
        out_path = out_dir / (img_path.stem + ".jpg")
        cv2.imwrite(str(out_path), ann, [cv2.IMWRITE_JPEG_QUALITY, 92])
        cls_counts = {}
        for d in dets:
            cn = CLASSES[d["cls"]]
            cls_counts[cn] = cls_counts.get(cn, 0) + 1
        results.append({
            "image": img_path.name,
            "n_det": len(dets),
            "latency_ms": round(dt*1000, 1),
            "classes": cls_counts,
        })
    avg = total_time / max(len(images), 1) * 1000
    summary = {
        "model": model_name,
        "n_images": len(images),
        "total_time_s": round(total_time, 2),
        "avg_latency_ms": round(avg, 1),
        "class_order": CLASSES,
        "results": results,
    }
    json.dump(summary, open(out_dir / "_summary.json", "w"), indent=2)
    print(f"[{model_name}] {len(images)} images, avg {avg:.1f} ms/img, saved to {out_dir}")
    return summary

def main():
    images = sorted([p for p in INPUT_DIR.iterdir()
                     if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    print(f"Found {len(images)} images in {INPUT_DIR}")
    print(f"Class order: {CLASSES}")
    print(f"Colors: SAM-style perceptual (generate_colors seed=42)")
    providers = get_providers()
    print(f"Providers: {providers}")
    all_summaries = []
    for model_name in MODELS:
        onnx_path = ONNX_DIR / f"{model_name}.onnx"
        if not onnx_path.exists():
            print(f"SKIP {model_name}: {onnx_path} not found")
            continue
        is_seg = "seg" in model_name
        sess = ort.InferenceSession(str(onnx_path), providers=providers)
        input_name = sess.get_inputs()[0].name
        meta = sess.get_modelmeta()
        names_str = meta.custom_metadata_map.get("names", "")
        print(f"  {model_name} metadata names: {names_str}")
        out_dir = OUT_BASE / model_name
        s = run_model(model_name, sess, input_name, images, out_dir, is_seg)
        all_summaries.append(s)
    json.dump(all_summaries, open(OUT_BASE / "all_summary.json", "w"), indent=2)
    print("\n=== Summary ===")
    for s in all_summaries:
        print(f"{s['model']:12s} | {s['n_images']:3d} imgs | avg {s['avg_latency_ms']:.1f} ms")
    print(f"\nOutputs: {OUT_BASE}")

if __name__ == "__main__":
    main()
