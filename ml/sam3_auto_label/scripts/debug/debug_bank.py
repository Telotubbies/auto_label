#!/usr/bin/env python3
"""PatchCore-style test: NN distance of IC#0 patches to a clean-IC bank
built from the 3 DIP product shots."""
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

TARGET = "/mnt/c/Users/Gigabyte/Downloads/05vnk95w40gg1.jpg"
REFS = [
    "/mnt/c/Users/Gigabyte/Downloads/DIP-ic-packaging.webp",
    "/mnt/c/Users/Gigabyte/Downloads/DIP-ICs.jpg",
    "/mnt/c/Users/Gigabyte/Downloads/realistic-computer-chip-dippackage-top-260nw-2469498987.webp",
]

cfg = load_config("config/ppe_4class.yaml")
processor = build_model(cfg)
device = processor.device
d3 = P.build_dinov3(device)

bank, meta = [], []

def feats_for(image):
    with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
        state = processor.set_image(image)
        ics = P.collect_ic_masks(processor, state,
                                 ["ic", "ic package", "integrated circuit", "chip"],
                                 0.25, *image.size)
        feats, _ = P.dinov3_grid(d3, image, device)
    return state, ics, feats

# build bank from reference images
for p in REFS:
    img = Image.open(p).convert("RGB")
    _, ics, feats = feats_for(img)
    gh, gw = feats.shape[:2]
    n = 0
    for ic in ics:
        pm = P.mask_to_patch(ic["mask"], gh, gw)
        bank.append(feats[pm])
        n += 1
    print(f"{os.path.basename(p)}: {n} ics -> bank patches {sum(b.shape[0] for b in bank)}")

bank = torch.cat(bank)  # [Nb, D]
print("bank size:", bank.shape)

# score target ic#0 (burnt chip)
img = Image.open(TARGET).convert("RGB")
W, H = img.size
with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    state = processor.set_image(img)
    ics = P.collect_ic_masks(processor, state,
                             ["ic", "ic package", "integrated circuit", "chip"],
                             0.25, W, H)
    feats, _ = P.dinov3_grid(d3, img, device)
gh, gw = feats.shape[:2]
ic0 = ics[0]
pm = P.mask_to_patch(ic0["mask"], gh, gw)
f = feats[pm]  # [N, D]
d = torch.cdist(f, bank)  # [N, Nb]
nn1 = d.min(1).values
nnk = d.topk(5, largest=False).values.mean(1)
med = nnk.median(); mad = (nnk - med).abs().median()
z = ((nnk - med) / (1.4826 * mad + 1e-6)).cpu().numpy()

zgrid = np.full(gh * gw, np.nan); zgrid[pm.reshape(-1)] = z
zg = zgrid.reshape(gh, gw)
print(f"\nIC#0: bank-NN z max={z.max():.2f} p95={np.percentile(z,95):.2f}")
top = np.argsort(-np.nan_to_num(zgrid, nan=-1e9))[:12]
for t in top:
    y, x = divmod(t, gw)
    print(f"  patch col{x} row{y} z={zg[y,x]:.2f} -> px ({int(x*W/gw)},{int(y*H/gh)})")

# ascii z map over the chip
for r in range(gh):
    line = ""
    for c in range(gw):
        v = zg[r, c]
        line += "." if np.isnan(v) else ("#"[0] if v >= 3 else ("+" if v >= 1.5 else "-"))
    print(line)
print("dome approx px(967,367) -> col", 967 * gw // W, "row", 367 * gh // H)
