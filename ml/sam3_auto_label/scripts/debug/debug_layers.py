#!/usr/bin/env python3
"""Compare anomaly separability across DINOv3 blocks for IC#0 (burnt chip)."""
import os, sys
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))  # sam3_auto_label/
sys.path[:0] = [_ROOT, os.path.join(_ROOT, "src")]
from config import load_config
from inference import build_model
import ic_defect_pipeline as P

IMG = "/mnt/c/Users/Gigabyte/Downloads/05vnk95w40gg1.jpg"
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

cfg = load_config("config/ppe_4class.yaml")
processor = build_model(cfg)
device = processor.device

import timm
m = timm.create_model(P.DINOV3_TIMM_NAME, pretrained=True, num_classes=0)
m.eval().to(device)
n_blocks = len(m.blocks)
print("blocks:", n_blocks)
idxs = [1, 3, 5, 7, 9, 11]

image = Image.open(IMG).convert("RGB")
W, H = image.size
with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    state = processor.set_image(image)
    ics = P.collect_ic_masks(processor, state,
                             ["ic", "ic package", "integrated circuit", "chip"],
                             0.25, W, H)
ic0 = ics[0]  # burnt chip by score

scale = min(1.0, P.MAX_SIDE / max(W, H))
nw = max(16, int(round(W * scale / 16)) * 16)
nh = max(16, int(round(H * scale / 16)) * 16)
small = image.resize((nw, nh), Image.BILINEAR)
x = torch.from_numpy(np.asarray(small, np.float32) / 255).permute(2, 0, 1)
x = x.unsqueeze(0).to(device)
mean = torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)
std = torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
x = (x - mean) / std
gh, gw = nh // 16, nw // 16

with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    out, inter = m.forward_intermediates(x, indices=idxs, norm=True)

pm = P.mask_to_patch(ic0["mask"], gh, gw)
sel = pm.reshape(-1)
# burnt region approx: center patch area around px (967,367) -> patch col 967*gw/W, row 367*gh/H
bcx, bcy = int(967 * gw / W), int(367 * gh / H)
print(f"grid {gh}x{gw}, burnt-center patch approx ({bcy},{bcx})")

for li, t in zip(idxs, inter):
    t = t[0].float()
    n_pref = t.shape[0] - gh * gw
    f = t[n_pref:].reshape(gh, gw, -1)
    f = F.normalize(f, dim=-1)
    fi = f[pm]
    center = F.normalize(fi.median(0).values, dim=0)
    d = 1 - fi @ center
    med = d.median(); mad = (d - med).abs().median()
    z = ((d - med) / (1.4826 * mad + 1e-6)).cpu().numpy()
    zgrid = np.full(gh * gw, -1e9); zgrid[sel] = z
    top = np.argsort(-zgrid)[:10]
    coords = [(int(divmod(t2, gw)[1]), int(divmod(t2, gw)[0]),
               round(float(zgrid[t2]), 2)) for t2 in top]
    # separability: mean z of patches in 3x3 around burnt center vs rest
    yy, xx = np.mgrid[0:gh, 0:gw]
    burnt = (np.abs(xx - bcx) <= 2) & (np.abs(yy - bcy) <= 2) & pm
    rest = pm & ~burnt
    zb = np.nanmean(zgrid.reshape(gh, gw)[burnt])
    zr = np.nanmean(np.where(rest, zgrid.reshape(gh, gw), np.nan))
    print(f"block {li + 1:2d}: zmax={z.max():.2f} burnt_mean_z={zb:.2f} "
          f"rest_mean_z={zr:.2f} top={coords[:6]}")
