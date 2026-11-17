#!/usr/bin/env python3
"""KMeans on IC#0 patches: does the burnt blob form its own cluster?"""
import os, sys
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from sklearn.cluster import KMeans

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
m = timm.create_model(P.DINOV3_TIMM_NAME, pretrained=True, num_classes=0).eval().to(device)

image = Image.open(IMG).convert("RGB")
W, H = image.size
with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    state = processor.set_image(image)
    ics = P.collect_ic_masks(processor, state,
                             ["ic", "ic package", "integrated circuit", "chip"],
                             0.25, W, H)
ic0 = ics[0]

scale = min(1.0, P.MAX_SIDE / max(W, H))
nw = max(16, int(round(W * scale / 16)) * 16)
nh = max(16, int(round(H * scale / 16)) * 16)
small = image.resize((nw, nh), Image.BILINEAR)
x = torch.from_numpy(np.asarray(small, np.float32) / 255).permute(2, 0, 1)
x = ((x.unsqueeze(0).to(device) - torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1))
     / torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1))
gh, gw = nh // 16, nw // 16

with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    out = m.forward_features(x)
t = out[0].float() if not isinstance(out, dict) else out["x_norm_patchtokens"][0].float()
f = t[-gh * gw:].reshape(gh, gw, -1)
f = F.normalize(f, dim=-1)

pm = P.mask_to_patch(ic0["mask"], gh, gw)
fi = f[pm].cpu().numpy()
km = KMeans(n_clusters=4, n_init=10, random_state=0).fit(fi)
lab = np.full(pm.shape, -1, int)
lab[pm] = km.labels_

print(f"IC#0 patch grid {pm.sum()} patches, clusters:")
for c in range(4):
    print(f"  cluster {c}: {(km.labels_ == c).sum()} patches")
for r in range(gh):
    print("".join("." if lab[r, c] < 0 else str(lab[r, c]) for c in range(gw)))
print(f"\nburnt dome approx px(967,367) -> patch col {967*gw//W}, row {367*gh//H}")
