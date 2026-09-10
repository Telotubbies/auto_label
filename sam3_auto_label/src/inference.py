"""SAM 3.1 inference core — shared by the CLI batch runner and the API service.

Everything model-related lives here:
  - device resolution (CUDA > ROCm > MPS > CPU)
  - model building (build_model)
  - single-image segmentation (segment_image)
  - COCO / mask / visualization export helpers
"""

import json
import logging
import os

import numpy as np
import torch
from PIL import Image
from pycocotools import mask as mask_util

from config import Config

# GPU-accelerated ops from SAM 3.1 perflib
try:
    from sam3.eval.postprocessors import robust_rle_encode
    from sam3.perflib.masks_ops import mask_iou as gpu_mask_iou
    _HAS_GPU_OPS = True
except ImportError:
    _HAS_GPU_OPS = False

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLORS = {
    1: (1, 0, 0, 0.4),       # person
    2: (0, 1, 0, 0.4),       # safety_boots
    3: (1, 0.5, 0, 0.4),     # sandals
    4: (1, 0, 1, 0.4),       # flip_flops
    5: (1, 1, 0, 0.4),       # helmet
    6: (0.2, 1, 0.6, 0.4),   # safety_harness
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_numpy(tensor):
    """Move tensor-like data to a CPU NumPy array without changing shape."""
    if hasattr(tensor, "cpu"):
        return tensor.cpu().numpy()
    return np.asarray(tensor)


def mask_to_rle(mask):
    """Encode a mask to RLE using GPU if available, else CPU fallback."""
    arr = np.asfortranarray(to_numpy(mask).astype(np.uint8))
    while arr.ndim > 2:
        arr = arr[0]
    rle = mask_util.encode(arr)
    rle["counts"] = rle["counts"].decode("utf-8")
    return rle


def mask_to_rle_gpu(mask_tensor, device="cuda"):
    """Encode a single mask (GPU tensor) to RLE using GPU-accelerated encode.

    Falls back to CPU if GPU encode fails or GPU ops unavailable.
    """
    if not _HAS_GPU_OPS:
        return mask_to_rle(mask_tensor)

    # Ensure mask is bool and 3D (1, H, W) on GPU
    if mask_tensor.ndim > 3:
        mask_tensor = mask_tensor.squeeze()
    if mask_tensor.ndim == 2:
        mask_tensor = mask_tensor.unsqueeze(0)
    mask_bool = mask_tensor.bool().to(device)

    try:
        rles = robust_rle_encode(mask_bool)
        return rles[0] if rles else None
    except Exception:
        return mask_to_rle(mask_tensor)


def masks_batch_to_rle_gpu(masks_tensor, device="cuda"):
    """Encode a batch of masks (GPU tensor) to RLE using GPU-accelerated encode.

    Args:
        masks_tensor: (N, H, W) or (N, 1, H, W) tensor on GPU
    Returns:
        list of RLE dicts, list of areas
    """
    if masks_tensor.ndim > 3:
        masks_tensor = masks_tensor.squeeze(1)
    n = masks_tensor.shape[0]

    if not _HAS_GPU_OPS or n == 0:
        # CPU fallback
        rles = []
        areas = []
        cpu_masks = to_numpy(masks_tensor)
        for i in range(n):
            arr = cpu_masks[i].astype(np.uint8)
            rle = mask_util.encode(np.asfortranarray(arr))
            rle["counts"] = rle["counts"].decode("utf-8")
            rles.append(rle)
            areas.append(int(arr.sum()))
        return rles, areas

    mask_bool = masks_tensor.bool().to(device)

    try:
        rles = robust_rle_encode(mask_bool)
        # Compute areas on GPU
        areas = mask_bool.sum(dim=(1, 2)).cpu().tolist()
        areas = [int(a) for a in areas]
        return rles, areas
    except Exception as e:
        log.debug(f"GPU RLE failed, CPU fallback: {e}")
        rles = []
        areas = []
        cpu_masks = to_numpy(masks_tensor)
        for i in range(n):
            arr = cpu_masks[i].astype(np.uint8)
            rle = mask_util.encode(np.asfortranarray(arr))
            rle["counts"] = rle["counts"].decode("utf-8")
            rles.append(rle)
            areas.append(int(arr.sum()))
        return rles, areas


def rle_to_mask(rle):
    rle = rle.copy()
    rle["counts"] = rle["counts"].encode("utf-8")
    return mask_util.decode(rle)


def clamp_box(box, W, H):
    """Convert an XYXY box to image-bounded COCO XYWH coordinates."""
    x0 = max(0, min(float(box[0]), W))
    y0 = max(0, min(float(box[1]), H))
    x1 = max(0, min(float(box[2]), W))
    y1 = max(0, min(float(box[3]), H))
    return [round(x0, 2), round(y0, 2), round(x1 - x0, 2), round(y1 - y0, 2)]


# ---------------------------------------------------------------------------
# NMS — Non-Maximum Suppression
# ---------------------------------------------------------------------------

def _bbox_iou(boxA, boxB):
    """Compute IoU between two COCO-format bboxes [x, y, w, h]."""
    ax1, ay1, aw, ah = boxA
    bx1, by1, bw, bh = boxB
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h

    areaA = max(0.0, aw) * max(0.0, ah)
    areaB = max(0.0, bw) * max(0.0, bh)
    union = areaA + areaB - inter
    if union <= 0:
        return 0.0
    return inter / union


def _mask_iou(rleA, rleB):
    """Compute mask IoU between two RLE-encoded masks using pycocotools."""
    try:
        m_a = rle_to_mask(rleA)
        m_b = rle_to_mask(rleB)
        inter = np.logical_and(m_a, m_b).sum()
        union = np.logical_or(m_a, m_b).sum()
        if union <= 0:
            return 0.0
        return float(inter) / float(union)
    except Exception:
        return 0.0


def cross_class_nms(annotations, iou_threshold=0.5, use_mask=False):
    """Cross-class NMS: when detections from DIFFERENT classes overlap,
    keep the one with higher score, suppress the other.

    Also applies within-class NMS to remove duplicate boxes in the same class.

    Args:
        annotations: list of COCO annotation dicts with 'bbox', 'score', 'category_id'
        iou_threshold: IoU above this -> suppress lower-score detection
        use_mask: if True, use mask IoU (more accurate, slower);
                  if False, use bbox IoU (faster, standard)

    Returns:
        filtered list of annotations (renumbered ids starting at 1)
    """
    if not annotations:
        return annotations

    # Sort by score descending — highest score wins
    indexed = sorted(enumerate(annotations), key=lambda x: -x[1]["score"])
    kept_indices = set()
    suppressed = set()

    for i, (orig_i, ann_i) in enumerate(indexed):
        if orig_i in suppressed:
            continue

        kept_indices.add(orig_i)

        # Suppress any lower-score detection that overlaps
        for j in range(i + 1, len(indexed)):
            orig_j, ann_j = indexed[j]
            if orig_j in suppressed or orig_j in kept_indices:
                continue

            # Only suppress if different classes (cross-class)
            # Within-class duplicates are also suppressed here
            if use_mask and "segmentation" in ann_i and "segmentation" in ann_j:
                iou = _mask_iou(ann_i["segmentation"], ann_j["segmentation"])
            else:
                iou = _bbox_iou(ann_i["bbox"], ann_j["bbox"])

            if iou > iou_threshold:
                # Suppress lower-score detection
                suppressed.add(orig_j)

    # Build result preserving original order, renumber ids
    result = [annotations[i] for i in range(len(annotations)) if i in kept_indices]
    for new_id, ann in enumerate(result, start=1):
        ann = dict(ann)  # copy to avoid mutating input
        ann["id"] = new_id
        result[new_id - 1] = ann

    return result


def cross_class_nms_gpu(annotations, masks_tensor, scores_tensor, iou_threshold=0.5, device="cuda"):
    """GPU-accelerated cross-class NMS using mask IoU.

    Uses perflib mask_iou (matmul-based, Tensor Core accelerated) for
    computing pairwise mask IoU on GPU, then greedy NMS on GPU.

    Args:
        annotations: list of COCO annotation dicts (with bbox, score, category_id)
        masks_tensor: (N, H, W) bool/float tensor on GPU — masks for all detections
        scores_tensor: (N,) float tensor on GPU — scores for all detections
        iou_threshold: suppress lower-score detection if IoU > threshold
        device: GPU device

    Returns:
        filtered list of annotations (renumbered ids starting at 1)
    """
    if not annotations or len(annotations) == 0:
        return annotations

    n = len(annotations)
    if n == 1:
        return [dict(annotations[0], id=1)]

    if not _HAS_GPU_OPS or masks_tensor is None or scores_tensor is None:
        return cross_class_nms(annotations, iou_threshold=iou_threshold, use_mask=False)

    try:
        # Ensure masks are bool on GPU
        if masks_tensor.ndim > 3:
            masks_tensor = masks_tensor.squeeze(1)
        masks_bool = masks_tensor.bool().to(device)
        scores_f32 = scores_tensor.float().to(device)

        # Compute pairwise mask IoU on GPU — (N, N) matrix
        ious = gpu_mask_iou(masks_bool, masks_bool)  # (N, N)

        # Greedy NMS: sort by score desc, suppress overlapping lower-score
        order = torch.argsort(scores_f32, descending=True)
        keep = torch.ones(n, dtype=torch.bool, device=device)
        suppressed = torch.zeros(n, dtype=torch.bool, device=device)

        for idx in range(n):
            i = order[idx].item()
            if suppressed[i]:
                continue
            # Suppress all lower-score detections with IoU > threshold
            overlap = ious[i] > iou_threshold
            overlap = overlap & ~suppressed
            # Don't suppress self
            overlap[i] = False
            suppressed |= overlap

        keep = ~suppressed
        keep_indices = keep.cpu().numpy()

        # Build result preserving original order, renumber ids
        result = [annotations[i] for i in range(n) if keep_indices[i]]
        for new_id, ann in enumerate(result, start=1):
            ann = dict(ann)
            ann["id"] = new_id
            result[new_id - 1] = ann

        return result
    except Exception as e:
        log.debug(f"GPU NMS failed, CPU fallback: {e}")
        return cross_class_nms(annotations, iou_threshold=iou_threshold, use_mask=False)


def device_type(device):
    """Normalize torch.device and string representations to a device family."""
    return device.type if isinstance(device, torch.device) else str(device).split(":", 1)[0]


def resolve_device(device_str):
    """Resolve device string to a torch device.

    Priority: CUDA > ROCm (via CUDA API) > MPS > CPU (last resort).
    Note: ROCm PyTorch exposes GPU through torch.cuda, so 'rocm' maps to 'cuda'.
    """
    if device_str == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    # ROCm uses the CUDA API in PyTorch, so normalize 'rocm' to 'cuda'
    if device_str == "rocm":
        if torch.cuda.is_available():
            return "cuda"
        log.warning("rocm requested but torch.cuda not available, falling back to cpu")
        return "cpu"
    # Validate explicit device
    if device_str == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
        log.warning("mps requested but not available, falling back to cpu")
        return "cpu"
    if device_str == "cuda" and not torch.cuda.is_available():
        log.warning("cuda requested but not available, falling back to cpu")
        return "cpu"
    return device_str


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def build_model(cfg: Config):
    """Load the configured SAM model and return its image processor."""
    from sam3.model_builder import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor

    device = resolve_device(cfg.inference.device)
    log.info(f"device: {device}, resolution: {cfg.inference.resolution}px")

    # Enable TF32 on Ampere+ GPUs for ~2-3x matmul throughput without
    # meaningful accuracy loss. Recommended by the SAM 3 batched
    # inference guide (facebookresearch/sam3 docs/guides/batched-inference).
    if device_type(device) == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    model = build_sam3_image_model(
        bpe_path=cfg.bpe_path,
        checkpoint_path=cfg.ckpt_path,
        load_from_HF=False,
        device=device,
        compile=cfg.inference.compile,
    )
    processor = Sam3Processor(
        model,
        resolution=cfg.inference.resolution,
        confidence_threshold=cfg.inference.confidence_threshold,
    )
    return processor


def _to_float32(t):
    """Cast bfloat16/float16 tensors to float32 before numpy conversion.

    numpy has no bfloat16 dtype, so SAM 3.1 outputs (bf16 under autocast)
    must be cast to float32 first. See facebookresearch/sam3#507 and
    opengeos/segment-geospatial commit 04c90b9.
    """
    if t is None or not hasattr(t, "dtype"):
        return t
    if t.dtype in (torch.bfloat16, torch.float16):
        return t.float()
    return t


def _gpu_nms(scores, masks, iou_threshold=0.5, device="cuda"):
    """Return a keep mask using pairwise mask IoU on the selected accelerator."""
    n = len(scores)
    if n <= 1:
        return torch.ones(n, dtype=torch.bool, device=device)

    ious = gpu_mask_iou(masks, masks)
    order = torch.argsort(scores, descending=True)
    suppressed = torch.zeros(n, dtype=torch.bool, device=device)

    for idx in range(n):
        i = order[idx].item()
        if suppressed[i]:
            continue
        overlap = ious[i] > iou_threshold
        overlap[i] = False
        overlap &= ~suppressed
        suppressed |= overlap

    return ~suppressed


def _gpu_bbox_nms(scores, boxes, iou_threshold=0.5, device="cuda"):
    """Return a keep mask using torchvision NMS over XYXY boxes."""
    from torchvision.ops import nms as tv_nms

    n = len(scores)
    if n <= 1:
        return torch.ones(n, dtype=torch.bool, device=device)

    keep_indices = tv_nms(boxes, scores, iou_threshold)
    keep_mask = torch.zeros(n, dtype=torch.bool, device=device)
    keep_mask[keep_indices] = True
    return keep_mask


def segment_image(processor, image, image_id, start_ann_id, cfg: Config):
    """Segment a single image with all configured categories.

    Optimized for GPU utilization:
    - All 6 category prompts run on GPU without CPU sync inside the loop
    - Scores, boxes, masks stay on GPU until after ALL categories are done
    - Single batched .cpu() transfer at the end (1 sync instead of 18)
    - GPU RLE encode + GPU mask IoU NMS (when cfg.inference.gpu_ops=True)
    - This keeps the GPU busy ~90%+ of the time
    """
    W, H = image.size
    device = processor.device
    use_gpu_ops = _HAS_GPU_OPS and device_type(device) == "cuda" and getattr(cfg.inference, "gpu_ops", True)

    with torch.inference_mode(), \
         torch.autocast("cuda", dtype=torch.bfloat16, enabled=device_type(device) == "cuda"):
        inference_state = processor.set_image(image)

        # --- Phase 1: Run all 6 text prompts on GPU, collect results ---
        # NO .cpu() calls here — keep GPU busy with back-to-back inference
        per_cat_results = []  # list of (cat, keep_indices, scores_gpu, boxes_gpu, masks_bool_gpu)

        for cat in cfg.categories:
            processor.reset_all_prompts(inference_state)
            output = processor.set_text_prompt(state=inference_state, prompt=cat.prompt)

            masks = output.get("masks")
            boxes = output.get("boxes")
            scores = output.get("scores")

            n = 0 if masks is None else len(masks)
            if n == 0:
                continue

            cat_threshold = cfg.inference.confidence_threshold if cat.threshold < 0 else cat.threshold

            # GPU-side filtering — no CPU sync
            if scores is not None:
                scores_f32 = _to_float32(scores)
                keep_mask = scores_f32 >= cat_threshold
                keep_indices = torch.nonzero(keep_mask, as_tuple=True)[0]
                n_keep = len(keep_indices)
                if n_keep == 0:
                    continue
            else:
                keep_indices = torch.arange(n, device=device)
                n_keep = n
                scores_f32 = torch.zeros(n, device=device)

            # Gather kept detections on GPU — no .cpu() yet
            scores_keep = scores_f32[keep_indices]
            boxes_keep = _to_float32(boxes)[keep_indices] if boxes is not None else None

            if masks is not None:
                # Sam3Processor._forward_grounding already binarizes via
                # `state["masks"] = out_masks > 0.5`, so output["masks"] is
                # already bool. We only need to cast dtype (in case of bf16
                # output under autocast) and squeeze the channel dim if present.
                masks_bool = _to_float32(masks)[keep_indices].bool()
                if masks_bool.ndim > 3:
                    masks_bool = masks_bool.squeeze(1)
            else:
                masks_bool = None

            per_cat_results.append((cat, scores_keep, boxes_keep, masks_bool))

        # --- Phase 2: GPU NMS across ALL detections ---
        # Stack all detections from all categories into one tensor
        all_scores = []
        all_boxes = []
        all_masks = []
        all_cats = []

        for cat, scores, boxes, masks in per_cat_results:
            n = len(scores)
            all_scores.append(scores)
            if boxes is not None:
                all_boxes.append(boxes)
            if masks is not None:
                all_masks.append(masks)
            all_cats.extend([cat.id] * n)

        n_total = len(all_cats)
        if n_total == 0:
            return [], start_ann_id

        scores_stack = torch.cat(all_scores)
        masks_stack = torch.cat(all_masks) if all_masks else None
        boxes_stack = torch.cat(all_boxes) if all_boxes else None

        # GPU cross-class NMS using mask IoU (matmul-based, Tensor Core accelerated)
        if use_gpu_ops and masks_stack is not None and n_total > 1:
            keep_mask = _gpu_nms(scores_stack, masks_stack, iou_threshold=0.5, device=device)
        else:
            # Fallback: bbox-based NMS on GPU using torchvision
            keep_mask = _gpu_bbox_nms(scores_stack, boxes_stack, iou_threshold=0.5, device=device)

        # --- Phase 3: Single batched .cpu() transfer ---
        # ONE sync point — transfer all surviving detections at once
        keep_indices = torch.nonzero(keep_mask, as_tuple=True)[0]

        scores_cpu = scores_stack[keep_indices].cpu().numpy()
        if boxes_stack is not None:
            # Convert from xyxy to COCO xywh on GPU first, then transfer
            boxes_keep = boxes_stack[keep_indices]
            boxes_xyxy = boxes_keep.cpu().numpy()
        else:
            boxes_xyxy = None

        # GPU RLE encode for surviving masks
        if masks_stack is not None:
            masks_keep = masks_stack[keep_indices]
            rles, areas = masks_batch_to_rle_gpu(masks_keep, device=device)
        else:
            rles = [None] * len(keep_indices)
            areas = [0] * len(keep_indices)

        # Build annotation dicts on CPU
        annotations = []
        kept_category_ids = [all_cats[index] for index in keep_indices.tolist()]
        for i, cat_id in enumerate(kept_category_ids):
            score = float(scores_cpu[i])

            if boxes_xyxy is not None:
                bbox = clamp_box(boxes_xyxy[i], W, H)
            else:
                bbox = [0, 0, 0, 0]

            annotations.append(build_annotation_dict(
                ann_id=start_ann_id + i,
                image_id=image_id,
                category_id=cat_id,
                bbox=bbox,
                area=areas[i] if i < len(areas) else 0,
                score=score,
                segmentation=rles[i] if i < len(rles) else None,
                annotation_source="auto",
            ))

        ann_id = start_ann_id + len(annotations)

        # Apply min_area filter if configured
        min_area = getattr(cfg.inference, "min_area", 0)
        if min_area > 0:
            annotations = filter_by_min_area(annotations, min_area)
            # Re-number annotation IDs after filtering
            for new_idx, ann in enumerate(annotations):
                ann["id"] = start_ann_id + new_idx
            ann_id = start_ann_id + len(annotations)

        # Validate annotations before returning
        annotations = [ann for ann in annotations if validate_annotation(ann)]

    return annotations, ann_id


# ---------------------------------------------------------------------------
# Annotation construction, validation, and filtering
# ---------------------------------------------------------------------------

def build_annotation_dict(ann_id, image_id, category_id, bbox, area,
                          score, segmentation, annotation_source="auto"):
    """Build a COCO-format annotation dict with provenance field.

    The annotation_source field tracks whether this annotation was
    auto-generated ('auto') or human-reviewed ('reviewed').
    """
    return {
        "id": ann_id,
        "image_id": image_id,
        "category_id": category_id,
        "bbox": bbox,
        "area": area,
        "iscrowd": 0,
        "segmentation": segmentation,
        "score": score,
        "annotation_source": annotation_source,
    }


def validate_annotation(ann):
    """Return True if the annotation has valid data, False otherwise.

    Checks:
    - bbox has no NaN values
    - bbox width and height are non-negative
    - area is non-negative
    - category_id is positive
    - score is in [0, 1]
    """
    import math

    bbox = ann.get("bbox", [])
    if len(bbox) != 4:
        return False
    if any(math.isnan(v) or math.isinf(v) for v in bbox):
        return False
    # bbox is [x, y, w, h] in COCO format
    if bbox[2] < 0 or bbox[3] < 0:
        return False

    area = ann.get("area", 0)
    if area is None or (isinstance(area, float) and math.isnan(area)):
        return False
    if area <= 0:
        return False

    cat_id = ann.get("category_id", 0)
    if cat_id is None or cat_id <= 0:
        return False

    score = ann.get("score", 0)
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return False
    if score < 0 or score > 1:
        return False

    return True


def filter_by_min_area(annotations, min_area):
    """Drop annotations with area < min_area. Returns filtered list."""
    if min_area <= 0:
        return annotations
    return [ann for ann in annotations if ann.get("area", 0) >= min_area]


# ---------------------------------------------------------------------------
# Output serialization
# ---------------------------------------------------------------------------

def save_coco(image_info, annotations, path, cfg: Config):
    """Persist the durable per-image COCO record used by resume reconstruction."""
    coco = {
        "images": [image_info],
        "annotations": annotations,
        "categories": [
            {"id": c.id, "name": c.name, "supercategory": "object"}
            for c in cfg.categories
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(coco, f, ensure_ascii=False, indent=2)


def save_masks(image_name, annotations, output_dir):
    """Write one binary PNG for each RLE-encoded instance annotation."""
    for ann in annotations:
        m = rle_to_mask(ann["segmentation"])
        img = Image.fromarray((m * 255).astype(np.uint8))
        fname = f"{image_name}_ann{ann['id']}_cat{ann['category_id']}.png"
        img.save(os.path.join(output_dir, fname))


def save_viz(image, image_name, annotations, output_path, cfg: Config):
    """Render visualization using OpenCV instead of matplotlib.

    OpenCV is 10-50x faster than matplotlib for image annotation:
    - matplotlib: 2-6s per image (figure creation, patch rendering, savefig)
    - OpenCV: 0.05-0.1s per image (direct numpy array drawing)
    """
    import cv2

    # Convert PIL → numpy BGR (OpenCV format)
    img_np = np.array(image)
    if img_np.ndim == 2:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
    else:
        img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # Overlay layer for masks (semi-transparent)
    overlay = img_np.copy()
    names = cfg.category_names

    for ann in annotations:
        cat_id = ann["category_id"]
        # COLORS values are (R, G, B, alpha) — convert to BGR for OpenCV
        rgba = COLORS.get(cat_id, (0.5, 0.5, 0.5, 0.4))
        bgr = (int(rgba[2] * 255), int(rgba[1] * 255), int(rgba[0] * 255))

        # Draw mask
        if ann.get("segmentation"):
            m = rle_to_mask(ann["segmentation"])
            overlay[m > 0] = bgr

        # Draw bbox
        x, y, w, h = [int(v) for v in ann["bbox"]]
        cv2.rectangle(img_np, (x, y), (x + w, y + h), bgr, 2)

        # Draw label
        label = f"{names.get(cat_id, '?')} {ann['score']:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        y_text = max(y - 5, th + 2)
        cv2.rectangle(img_np, (x, y_text - th - 2), (x + tw + 4, y_text + 2), bgr, -1)
        cv2.putText(img_np, label, (x + 2, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # Blend overlay with original (alpha blending)
    cv2.addWeighted(overlay, 0.4, img_np, 0.6, 0, img_np)

    # Add title
    title = f"{image_name} — {len(annotations)} annotations"
    cv2.putText(img_np, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

    cv2.imwrite(output_path, img_np)
