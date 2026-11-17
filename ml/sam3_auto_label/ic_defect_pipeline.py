#!/usr/bin/env python3
"""IC defect detection: DINOv3 patch-anomaly bank + SAM 3.1, batch mode.

Pipeline:
  A. SAM 3.1 text prompts locate every IC instance per image
     ("ic", "ic package", "integrated circuit", "chip").
  B. DINOv3 ViT-S/16 (timm, LVD-1689M) extracts dense patch features;
     all IC patches across ALL images form a shared feature bank.
  C. Each IC patch is scored by its nearest-neighbour distance to the bank
     (its own IC excluded) -> spatially coherent top clusters become
     defect candidates -> padded box -> SAM geometric prompt -> refined mask.
  D. Defect-class text prompts ("burnt chip", "damaged ic", ...) flag which
     ICs are defective at the semantic level; combined with candidates.

Outputs per image under <out>/<image-stem>/:
    ic_viz.png            IC detections (green) + defect-flagged ICs (red)
    anomaly_heatmap.png   bank-NN distance heatmap inside IC masks
    defect_viz.png        refined defect masks + boxes
    objects/defect_XX.png transparent cutouts
    defects.json          machine-readable summary

Usage:
  ./sam3_venv/bin/python ic_defect_pipeline.py \
      --images /mnt/c/Users/Gigabyte/Downloads/*.jpg \
      --output /mnt/c/Users/Gigabyte/Downloads/dinov3_ic_defect
"""

import argparse
import json
import os
import sys

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from config import load_config  # noqa: E402
from inference import build_model, _to_float32, device_type  # noqa: E402

DET_COLORS = [
    (255, 56, 56), (255, 157, 51), (255, 220, 60), (74, 222, 128),
    (56, 189, 248), (167, 139, 250), (244, 114, 182), (45, 212, 191),
]
IC_COLOR = (74, 222, 128)
DEFECT_FLAG_COLOR = (255, 56, 56)

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
DINOV3_TIMM_NAME = "vit_small_patch16_dinov3.lvd1689m"
PATCH = 16
MAX_SIDE = 896


def stem(p):
    return os.path.splitext(os.path.basename(p))[0]


def build_dinov3(device):
    import timm
    print(f"loading DINOv3 ({DINOV3_TIMM_NAME}) ...", flush=True)
    model = timm.create_model(DINOV3_TIMM_NAME, pretrained=True, num_classes=0)
    model.eval().to(device)
    return model


@torch.inference_mode()
def dinov3_grid(model, image, device):
    """Patch features [gh, gw, D] + resized input size (nw, nh)."""
    W, H = image.size
    scale = min(1.0, MAX_SIDE / max(W, H))
    nw = max(PATCH, int(round(W * scale / PATCH)) * PATCH)
    nh = max(PATCH, int(round(H * scale / PATCH)) * PATCH)
    small = image.resize((nw, nh), Image.BILINEAR)
    x = torch.from_numpy(np.asarray(small, np.float32) / 255.0)
    x = x.permute(2, 0, 1).unsqueeze(0).to(device)
    mean = torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
    x = (x - mean) / std

    out = model.forward_features(x)
    if isinstance(out, dict):
        tokens = out["x_norm_patchtokens"]
    else:
        n_prefix = getattr(model, "num_prefix_tokens",
                           getattr(model, "num_reg_tokens", 0) + 1)
        tokens = out[:, n_prefix:, :]
    gh, gw = nh // PATCH, nw // PATCH
    feats = F.normalize(tokens[0].reshape(gh, gw, -1).float(), dim=-1)
    return feats


def mask_to_patch(mask_bool, gh, gw):
    m = torch.from_numpy(mask_bool.astype(np.float32)).unsqueeze(0).unsqueeze(0)
    m = F.interpolate(m, size=(gh, gw), mode="area")
    return (m[0, 0] >= 0.4).cpu().numpy()


def collect_masks(processor, state, prompts, threshold, W, H):
    """Union detections across prompts, dedupe by mask containment, size-filter."""
    all_masks, all_scores, all_boxes = [], [], []
    for prompt in prompts:
        processor.reset_all_prompts(state)
        out = processor.set_text_prompt(state=state, prompt=prompt)
        scores = out.get("scores")
        if scores is None or len(scores) == 0:
            continue
        keep = _to_float32(scores).float() >= threshold
        idx = torch.nonzero(keep, as_tuple=True)[0]
        if not len(idx):
            continue
        masks = _to_float32(out["masks"])[idx].bool()
        if masks.ndim > 3:
            masks = masks.squeeze(1)
        all_masks.append(masks.cpu())
        all_scores.append(_to_float32(scores).float()[idx].cpu())
        if out.get("boxes") is not None:
            all_boxes.append(_to_float32(out["boxes"])[idx].cpu())
    if not all_masks:
        return []

    masks = torch.cat(all_masks).numpy()
    scores = torch.cat(all_scores).numpy()
    boxes = torch.cat(all_boxes).numpy() if all_boxes else None

    ok = np.array([m.sum() for m in masks]) >= W * H * 0.005
    if ok.any():
        keep_idx = np.nonzero(ok)[0]
        masks, scores = masks[keep_idx], scores[keep_idx]
        boxes = boxes[keep_idx] if boxes is not None else None

    order = np.argsort(-scores)
    kept, used = [], np.zeros(len(order), bool)
    for i in order:
        if used[i]:
            continue
        kept.append(i)
        for j in order:
            if used[j] or j == i:
                continue
            inter = np.logical_and(masks[i], masks[j]).sum()
            union = np.logical_or(masks[i], masks[j]).sum()
            smaller = min(masks[i].sum(), masks[j].sum())
            if (union and inter / union > 0.3) or (smaller and inter / smaller > 0.5):
                used[j] = True
    kept = kept[:8]
    return [{"mask": masks[i], "score": float(scores[i]),
             "box": boxes[i].tolist() if boxes is not None else None}
            for i in kept]


def defect_components(dist_grid, z_grid, min_patches, ic_patch_mask, max_comps):
    import cv2
    hot = (np.nan_to_num(z_grid, nan=-np.inf) >= 0) & ic_patch_mask
    # threshold: patches above median+2*scaled-MAD were already z>=... caller
    # passes z_grid thresholded to >=0 meaning "above IC median"; here rank
    # components by mean distance instead.
    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        hot.astype(np.uint8), connectivity=8)
    comps = []
    for lab in range(1, n):
        area = stats[lab, cv2.CC_STAT_AREA]
        if area < min_patches:
            continue
        ys, xs = np.where(labels == lab)
        d = np.nan_to_num(dist_grid[ys, xs], nan=0.0)
        comps.append({"patches": (ys, xs), "area": int(area),
                      "mean_dist": float(d.mean()), "z_max": float(
                          np.nanmax(z_grid[ys, xs]))})
    comps.sort(key=lambda c: -c["mean_dist"])
    return comps[:max_comps]


def patch_box_to_image(ys, xs, gh, gw, W, H, pad=0.15):
    pw, ph = W / gw, H / gh
    x0, x1 = xs.min() * pw, (xs.max() + 1) * pw
    y0, y1 = ys.min() * ph, (ys.max() + 1) * ph
    bw, bh = x1 - x0, y1 - y0
    x0 = max(0, x0 - bw * pad); y0 = max(0, y0 - bh * pad)
    x1 = min(W, x1 + bw * pad); y1 = min(H, y1 + bh * pad)
    return [float(x0), float(y0), float(x1), float(y1)]


def refine_with_sam(processor, state, box_xyxy, W, H):
    x0, y0, x1, y1 = box_xyxy
    box = [(x0 + x1) / 2 / W, (y0 + y1) / 2 / H, (x1 - x0) / W, (y1 - y0) / H]
    processor.reset_all_prompts(state)
    out = processor.add_geometric_prompt(box, True, state)
    scores = out.get("scores")
    if scores is None or len(scores) == 0:
        return None
    masks = _to_float32(out["masks"]).bool()
    if masks.ndim > 3:
        masks = masks.squeeze(1)
    masks = masks.cpu().numpy()
    boxes_o = _to_float32(out["boxes"]).cpu().numpy() if out.get("boxes") is not None else None
    scores = _to_float32(scores).float().cpu().numpy()
    ax0, ay0, ax1, ay1 = box_xyxy
    best, best_iou = None, -1.0
    for i in range(len(scores)):
        if boxes_o is not None:
            bx0, by0, bx1, by1 = boxes_o[i]
            inter = max(0, min(ax1, bx1) - max(ax0, bx0)) * \
                max(0, min(ay1, by1) - max(ay0, by0))
            ua = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
            iou = inter / ua if ua > 0 else 0
        else:
            iou = float(scores[i])
        if iou > best_iou:
            best_iou, best = iou, i
    if best is None:
        return None
    return {"mask": masks[best], "score": float(scores[best]),
            "iou_box": float(best_iou)}


def heatmap_overlay(img_np, dist_grid, union_mask):
    import cv2
    H, W = img_np.shape[:2]
    d = np.nan_to_num(dist_grid, nan=0.0)
    if d.max() > 0:
        d = d / d.max()
    d = cv2.resize(d, (W, H), interpolation=cv2.INTER_LINEAR)
    heat = cv2.applyColorMap((np.clip(d, 0, 1) * 255).astype(np.uint8),
                             cv2.COLORMAP_JET)
    union = cv2.resize(union_mask.astype(np.uint8), (W, H),
                       interpolation=cv2.INTER_NEAREST) > 0
    vis = img_np.copy()
    vis[union] = cv2.addWeighted(img_np, 0.45,
                                 cv2.cvtColor(heat, cv2.COLOR_BGR2RGB),
                                 0.55, 0)[union]
    return vis


def save_crop(img_np, mask, out_path):
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    rgba = np.dstack([img_np[y0:y1, x0:x1],
                      (mask[y0:y1, x0:x1].astype(np.uint8) * 255)])
    Image.fromarray(rgba, "RGBA").save(out_path)
    return [int(x0), int(y0), int(x1), int(y1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--config", default="config/ppe_4class.yaml")
    ap.add_argument("--ic-prompts", nargs="+", default=["ic"])
    ap.add_argument("--defect-prompts", nargs="+",
                    default=["burnt chip", "damaged ic",
                             "scorched ic", "cracked chip"])
    ap.add_argument("--ic-threshold", type=float, default=0.25)
    ap.add_argument("--min-area-frac", type=float, default=0.01)
    ap.add_argument("--max-per-ic", type=int, default=2)
    ap.add_argument("--device", default=None,
                    choices=["auto", "cpu", "cuda", "rocm"])
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.device:
        cfg.inference.device = args.device

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
        processor.device = torch.device("cpu")
    else:
        processor = build_model(cfg)
    dev = device_type(processor.device)
    device = processor.device
    print(f"device: {device}")

    dinov3 = build_dinov3(device)

    # ---------- stage A+B: per-image IC detection + patch features ----------
    records = []
    with torch.inference_mode(), \
         torch.autocast(dev, dtype=torch.bfloat16, enabled=dev in ("cuda", "cpu")):
        for path in args.images:
            image = Image.open(path).convert("RGB")
            W, H = image.size
            print(f"\n=== {stem(path)} ({W}x{H})", flush=True)
            state = processor.set_image(image)
            ics = collect_masks(processor, state, args.ic_prompts,
                                args.ic_threshold, W, H)
            print(f"  ICs: {len(ics)}")
            feats = dinov3_grid(dinov3, image, device)
            for ic in ics:
                pm = mask_to_patch(ic["mask"], *feats.shape[:2])
                ic["pm"] = pm
                ic["pm_t"] = torch.as_tensor(pm, device=device)
            records.append({"path": path, "image": image, "W": W, "H": H,
                            "ics": ics, "feats": feats})
            del state
            torch.cuda.empty_cache()

    # ---------- global feature bank ----------
    bank_owner, bank = [], []
    for ri, rec in enumerate(records):
        for ii, ic in enumerate(rec["ics"]):
            if ic["pm"].sum() < 4:
                continue
            bank.append(rec["feats"][ic["pm_t"]])
            bank_owner += [(ri, ii)] * int(ic["pm"].sum())
    bank = torch.cat(bank) if bank else None
    bank_owner = np.array(bank_owner) if bank is not None else None
    print(f"\nfeature bank: {0 if bank is None else bank.shape[0]} patches")

    # ---------- stage C+D: scoring, refine, viz ----------
    with torch.inference_mode(), \
         torch.autocast(dev, dtype=torch.bfloat16, enabled=dev in ("cuda", "cpu")):
        for ri, rec in enumerate(records):
            image, W, H = rec["image"], rec["W"], rec["H"]
            state = processor.set_image(image)
            img_np = np.array(image)
            gh, gw = rec["feats"].shape[:2]
            out_dir = os.path.join(args.output, stem(rec["path"]))
            obj_dir = os.path.join(out_dir, "objects")
            os.makedirs(obj_dir, exist_ok=True)

            # defect-flagged ICs via text prompts
            flag = np.zeros(len(rec["ics"]), bool)
            flag_scores = {}
            flagged = collect_masks(processor, state, args.defect_prompts,
                                    args.ic_threshold, W, H)
            for f in flagged:
                for ii, ic in enumerate(rec["ics"]):
                    inter = np.logical_and(f["mask"], ic["mask"]).sum()
                    if inter / max(f["mask"].sum(), 1) > 0.3:
                        flag[ii] = True
                        flag_scores[ii] = max(flag_scores.get(ii, 0), f["score"])

            dist_full = np.full((gh, gw), np.nan, np.float32)
            union = np.zeros((gh, gw), bool)
            defects = []
            for ii, ic in enumerate(rec["ics"]):
                pm = ic["pm"]
                if pm.sum() < 4 or bank is None:
                    continue
                union |= pm
                f = rec["feats"][ic["pm_t"]]              # [N,D]
                dist = torch.cdist(f, bank)               # [N,Nb]
                own = torch.as_tensor(
                    (bank_owner[:, 0] == ri) & (bank_owner[:, 1] == ii),
                    device=device)
                dist[:, own] = float("inf")
                nn = dist.min(1).values.cpu().numpy()
                ic["nn_med"] = float(np.median(nn))
                ic["nn_p95"] = float(np.quantile(nn, 0.95))
                med = np.median(nn)
                mad = np.median(np.abs(nn - med))
                z = (nn - med) / (1.4826 * mad + 1e-6)
                dgrid = np.full(gh * gw, np.nan, np.float32)
                dgrid[pm.reshape(-1)] = nn
                dist_full = np.where(np.isnan(dist_full),
                                     dgrid.reshape(gh, gw), dist_full)
                zg = np.full(gh * gw, np.nan, np.float32)
                zg[pm.reshape(-1)] = z
                zg = zg.reshape(gh, gw)

                min_p = max(2, int(pm.sum() * args.min_area_frac))
                # candidate = patches in top tail of THIS ic's distribution
                thr = np.quantile(nn, 0.93)
                z_pass = np.where(nn >= thr, z, np.nan)
                zpass = np.full(gh * gw, np.nan, np.float32)
                zpass[pm.reshape(-1)] = np.nan_to_num(z_pass, nan=-np.inf)
                comps = defect_components(
                    dgrid.reshape(gh, gw), zpass.reshape(gh, gw),
                    min_p, pm, args.max_per_ic)
                for comp in comps:
                    ys, xs = comp["patches"]
                    box = patch_box_to_image(ys, xs, gh, gw, W, H)
                    ref = refine_with_sam(processor, state, box, W, H)
                    if ref is None:
                        continue
                    region = np.zeros((H, W), bool)
                    region[int(box[1]):int(box[3]), int(box[0]):int(box[2])] = True
                    if not np.logical_and(ref["mask"], region).any():
                        continue
                    defects.append({"ic_id": ii, "anom_box": box,
                                    "mean_dist": comp["mean_dist"],
                                    "z_max": comp["z_max"],
                                    "ic_flagged": bool(flag[ii]),
                                    **ref})

            import cv2
            # viz: ICs green, defect-flagged ICs red
            ic_vis = img_np.copy()
            for ii, ic in enumerate(rec["ics"]):
                c = DEFECT_FLAG_COLOR if flag[ii] else IC_COLOR
                lbl = f"ic#{ii} {ic['score']:.2f}"
                if flag[ii]:
                    lbl += f" DEFECT-FLAG {flag_scores.get(ii, 0):.2f}"
                ic_vis[ic["mask"]] = (ic_vis[ic["mask"]] * 0.5
                                      + np.array(c) * 0.5).astype(np.uint8)
                if ic["box"]:
                    x0, y0, x1, y1 = [int(v) for v in ic["box"]]
                    cv2.rectangle(ic_vis, (x0, y0), (x1, y1), c, 2)
                    cv2.putText(ic_vis, lbl, (x0, max(15, y0 - 4)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1, cv2.LINE_AA)
            cv2.imwrite(os.path.join(out_dir, "ic_viz.png"),
                        cv2.cvtColor(ic_vis, cv2.COLOR_RGB2BGR))
            cv2.imwrite(os.path.join(out_dir, "anomaly_heatmap.png"),
                        cv2.cvtColor(heatmap_overlay(img_np, dist_full, union),
                                     cv2.COLOR_RGB2BGR))

            def_vis = img_np.copy()
            for i, d in enumerate(defects):
                c = DET_COLORS[i % len(DET_COLORS)]
                m = d["mask"]
                def_vis[m] = (def_vis[m] * 0.4 + np.array(c) * 0.6).astype(np.uint8)
                x0, y0, x1, y1 = save_crop(img_np, m, os.path.join(
                    obj_dir,
                    f"defect_{i + 1:02d}_ic{d['ic_id']}_d{d['mean_dist']:.2f}"
                    f"_s{d['score']:.2f}.png"))
                cv2.rectangle(def_vis, (x0, y0), (x1, y1), c, 2)
                cv2.putText(def_vis,
                            f"defect#{i + 1} ic{d['ic_id']} d{d['mean_dist']:.2f}",
                            (x0, max(15, y0 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, c, 1, cv2.LINE_AA)
                d["crop"] = [x0, y0, x1, y1]
                d["mask_area_px"] = int(m.sum())
                d.pop("mask")
            cv2.imwrite(os.path.join(out_dir, "defect_viz.png"),
                        cv2.cvtColor(def_vis, cv2.COLOR_RGB2BGR))

            del state
            torch.cuda.empty_cache()
            with open(os.path.join(out_dir, "defects.json"), "w") as f:
                json.dump({
                    "image_size": [W, H], "dinov3": DINOV3_TIMM_NAME,
                    "ics": [{"score": round(ic["score"], 4),
                             "defect_flag": bool(flag[ii]),
                             "flag_score": round(flag_scores.get(ii, 0), 4),
                             "nn_med": round(ic.get("nn_med", 0), 4),
                             "nn_p95": round(ic.get("nn_p95", 0), 4)}
                            for ii, ic in enumerate(rec["ics"])],
                    "defects": defects,
                }, f, indent=2)
            print(f"  defects: {len(defects)}  flagged ICs: "
                  f"{np.nonzero(flag)[0].tolist()} -> {out_dir}")

    print("\ndone.")


if __name__ == "__main__":
    main()
