#!/usr/bin/env python3
"""Debug anomaly scoring for the burnt-IC image."""
import os, sys
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # sam3_auto_label/
sys.path[:0] = [_ROOT, os.path.join(_ROOT, "src")]
from config import load_config
from inference import build_model, device_type
import ic_defect_pipeline as P

IMG = "/mnt/c/Users/Gigabyte/Downloads/05vnk95w40gg1.jpg"

cfg = load_config("config/ppe_4class.yaml")
processor = build_model(cfg)
device = processor.device
d3 = P.build_dinov3(device)
image = Image.open(IMG).convert("RGB")
W, H = image.size

with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    state = processor.set_image(image)
    ics = P.collect_ic_masks(processor, state,
                             ["ic", "ic package", "integrated circuit", "chip"],
                             0.25, W, H)
    feats, (nw, nh) = P.dinov3_grid(d3, image, device)

gh, gw, D = feats.shape
print(f"grid {gh}x{gw}, {len(ics)} ics")

# union of all IC patches = rough "normal surface" bank minus the IC under test
pm_all = [P.mask_to_patch(ic["mask"], gh, gw) for ic in ics]
flat = feats.reshape(-1, D)

for i, ic in enumerate(ics):
    pm = pm_all[i]
    if pm.sum() < 4:
        continue
    f = flat[pm.reshape(-1)]
    # (a) within-IC median z
    center = F.normalize(f.median(0).values, dim=0)
    d = 1 - f @ center
    med = d.median(); mad = (d - med).abs().median()
    za = ((d - med) / (1.4826 * mad + 1e-6)).cpu().numpy()
    # (b) NN distance to OTHER ICs' patches (bank)
    bank_sel = np.zeros(gh * gw, bool)
    for j, p in enumerate(pm_all):
        if j != i:
            bank_sel |= p.reshape(-1)
    bank = flat[bank_sel]
    nn = torch.cdist(f.float(), bank.float()).topk(3, largest=False).values.mean(1)
    zb = (nn - nn.median()) / (1.4826 * (nn - nn.median()).abs().median() + 1e-6)
    zb = zb.cpu().numpy()
    box = ic["box"]
    print(f"\nIC#{i} score={ic['score']:.2f} box={box} patches={pm.sum()}")
    print(f"  median-z : max={za.max():.2f} p95={np.percentile(za,95):.2f} "
          f"rawdist p95={np.percentile(d.cpu().numpy(),95):.3f}")
    print(f"  bank-nn-z: max={zb.max():.2f} p95={np.percentile(zb,95):.2f} "
          f"rawdist p95={np.percentile(nn.cpu().numpy(),95):.3f}")
    # where are the top patches?
    zz = np.full(gh * gw, -1e9); zz[pm.reshape(-1)] = za
    top = np.argsort(-zz)[:12]
    for t in top[:8]:
        y, x = divmod(t, gw)
        print(f"    patch ({x},{y}) z={zz[t]:.2f} -> px ({int(x*W/gw)},{int(y*H/gh)})")
