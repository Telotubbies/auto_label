"""labeldesk-worker — run LabelDesk training / auto-label jobs on any GPU box.

    pip install ./apps/worker            (or: pip install "labeldesk-worker @ git+https://…#subdirectory=apps/worker")
    labeldesk-worker --server https://api.example.com --token $LD_WORKER_TOKEN

Only outbound HTTPS is used, so it works behind NAT, on Kaggle and on Colab.
"""
import argparse
import json
import logging
import os
import shutil
import socket
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import requests

log = logging.getLogger("labeldesk-worker")


class Server:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["X-Worker-Token"] = token

    def post(self, path, **kw):
        r = self.s.post(self.url + path, timeout=kw.pop("timeout", 60), **kw)
        r.raise_for_status()
        return r.json()

    def download(self, rel_url: str, dst: Path) -> Path:
        with self.s.get(self.url + rel_url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(dst, "wb") as f:
                shutil.copyfileobj(r.raw, f)
        return dst


# --- jobs -------------------------------------------------------------------------

def base_weights(task: str, size: str, pretrained_dir: str | None) -> str:
    suffix = {"detect": "", "segment": "-seg", "classify": "-cls"}[task]
    if pretrained_dir:
        local = Path(pretrained_dir) / f"yolo26{size}{suffix}.pt"
        if local.exists():
            return str(local)
    return f"yolo11{size}{suffix}.pt"


def run_train(srv: Server, job: dict, args):
    from ultralytics import YOLO
    p = job["payload"]; opts = p["options"]; task = p["task"]
    work = Path(tempfile.mkdtemp(prefix=f"ld-{job['id']}-"))
    try:
        z = srv.download(p["dataset_url"], work / "ds.zip")
        ds = work / "ds"
        zipfile.ZipFile(z).extractall(ds)
        if task == "classify" and (ds / "valid").exists():
            (ds / "valid").rename(ds / "val")
        data = str(ds) if task == "classify" else str(ds / "data.yaml")
        epochs = int(opts.get("epochs", 30))
        history = []
        model = YOLO(base_weights(task, opts.get("size", "n"), args.pretrained_dir))
        # Download, extract and model load are silent; report before the first epoch so a slow
        # start is not mistaken for a dead worker (I9/Important 1).
        srv.post(f"/api/worker/jobs/{job['id']}/progress", json={"progress": 0})

        def cb(trainer):
            m = {k: float(v) for k, v in (trainer.metrics or {}).items() if isinstance(v, (int, float))}
            history[:] = [h for h in history if h["epoch"] != trainer.epoch + 1] + [{"epoch": trainer.epoch + 1, **m}]
            try:
                if srv.post(f"/api/worker/jobs/{job['id']}/progress",
                            json={"progress": (trainer.epoch + 1) / epochs * 100, "history": history}).get("cancel"):
                    trainer.stop = True
            except requests.RequestException as e:
                log.warning("progress report failed: %s", e)
        model.add_callback("on_fit_epoch_end", cb)
        kw = dict(data=data, epochs=epochs, imgsz=int(opts.get("imgsz", 640)), batch=int(opts.get("batch", 16)),
                  project=str(work / "runs"), name="run", exist_ok=True, verbose=False, workers=2)
        if args.device:
            kw["device"] = args.device
        model.train(**kw)
        best = work / "runs" / "run" / "weights" / "best.pt"
        if not best.exists():
            best = best.with_name("last.pt")
        with open(best, "rb") as f:
            srv.post(f"/api/worker/jobs/{job['id']}/complete", data={"result": json.dumps({"history": history})},
                     files={"weights": ("best.pt", f)}, timeout=600)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _sam(args):
    root = Path(args.sam_root or os.environ.get("LD_SAM_ROOT", ""))
    if not root.exists():
        raise RuntimeError("SAM auto-label needs --sam-root pointing at a sam3_auto_label checkout with checkpoints/")
    sys.path[:0] = [str(root / "src"), str(root / "sam3")]
    from config import Config
    from inference import build_model
    return build_model(Config(base_dir=str(root)))


def _poly(mask, W, H):
    import cv2
    import numpy as np
    cs, _ = cv2.findContours((mask > 0).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 0.004 * cv2.arcLength(c, True), True)
    return [round(float(v), 5) for pt in c[:, 0, :] for v in (pt[0] / mask.shape[1], pt[1] / mask.shape[0])] if len(c) >= 3 else None


def run_autolabel(srv: Server, job: dict, args):
    import secrets
    from PIL import Image
    p = job["payload"]; conf = float(p["confidence"])
    work = Path(tempfile.mkdtemp(prefix=f"ld-{job['id']}-"))
    try:
        model = proc = None
        if p["method"] == "model":
            from ultralytics import YOLO
            model = YOLO(str(srv.download(p["weights_url"], work / "w.pt")))
        else:
            proc = _sam(args)
        # The model/SAM load above is silent; report before the first image (I9/Important 1).
        srv.post(f"/api/worker/jobs/{job['id']}/progress", json={"progress": 0})
        n = len(p["images"])
        for i, it in enumerate(p["images"]):
            im = Image.open(srv.download(it["url"], work / "img.jpg")).convert("RGB")
            W, H = im.size
            anns = []
            if model:
                r = model.predict(im, conf=conf, verbose=False)[0]
                names = r.names
                if getattr(r, "probs", None) is not None:
                    top = names[int(r.probs.top1)]
                    if top in p["classes"]:
                        anns.append({"id": "a" + secrets.token_hex(5), "classId": p["classes"][top], "shape": {"kind": "class"}})
                else:
                    polys = r.masks.xyn if r.masks is not None else None
                    for k in range(len(r.boxes)):
                        name = names[int(r.boxes.cls[k])]
                        if name not in p["classes"]:
                            continue
                        x1, y1, x2, y2 = r.boxes.xyxy[k].tolist()
                        shape = ({"kind": "polygon", "points": [float(v) for xy in polys[k] for v in xy]}
                                 if polys is not None and len(polys[k]) >= 3 else
                                 {"kind": "bbox", "x": x1 / W, "y": y1 / H, "w": (x2 - x1) / W, "h": (y2 - y1) / H})
                        anns.append({"id": "a" + secrets.token_hex(5), "classId": p["classes"][name], "shape": shape,
                                     "confidence": round(float(r.boxes.conf[k]), 4)})
            else:
                state = proc.set_image(im)
                for c in p["prompts"]:
                    proc.reset_all_prompts(state)
                    out = proc.set_text_prompt(state=state, prompt=c["name"])
                    if out.get("masks") is None:
                        continue
                    for mk, sc in zip(out["masks"].float().cpu().numpy(), out["scores"].float().cpu().tolist()):
                        poly = _poly(mk.squeeze() > 0.5, W, H) if sc >= conf else None
                        if not poly:
                            continue
                        if p["project_type"] == "object-detection":
                            xs, ys = poly[0::2], poly[1::2]
                            shape = {"kind": "bbox", "x": min(xs), "y": min(ys), "w": max(xs) - min(xs), "h": max(ys) - min(ys)}
                        else:
                            shape = {"kind": "polygon", "points": poly}
                        anns.append({"id": "a" + secrets.token_hex(5), "classId": c["id"], "shape": shape, "confidence": round(sc, 4)})
            srv.post(f"/api/worker/jobs/{job['id']}/annotations", json={"image_id": it["id"], "annotations": anns})
            if srv.post(f"/api/worker/jobs/{job['id']}/progress", json={"progress": (i + 1) / max(1, n) * 100}).get("cancel"):
                break
        srv.post(f"/api/worker/jobs/{job['id']}/complete", data={"result": json.dumps({"images": n})})
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="LabelDesk remote GPU worker")
    ap.add_argument("--server", default=os.environ.get("LD_SERVER"), help="API base URL, e.g. https://api.example.com")
    ap.add_argument("--token", default=os.environ.get("LD_WORKER_TOKEN"), help="value of LD_WORKER_TOKEN on the server")
    ap.add_argument("--kinds", default="train,autolabel")
    ap.add_argument("--device", default=os.environ.get("LD_TRAIN_DEVICE", ""), help='ultralytics device: "0", "cpu" …')
    ap.add_argument("--pretrained-dir", default=os.environ.get("LD_PRETRAINED_DIR"))
    ap.add_argument("--sam-root", default=None)
    ap.add_argument("--name", default=socket.gethostname())
    ap.add_argument("--once", action="store_true", help="exit after one job (handy on Colab/Kaggle)")
    args = ap.parse_args()
    if not args.server or not args.token:
        ap.error("--server and --token are required (or LD_SERVER / LD_WORKER_TOKEN)")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    srv = Server(args.server, args.token)
    handlers = {"train": run_train, "autolabel": run_autolabel}
    log.info("worker %s polling %s for %s", args.name, args.server, args.kinds)
    while True:
        try:
            job = srv.post("/api/worker/claim", json={"name": args.name, "kinds": args.kinds.split(",")})["job"]
        except requests.RequestException as e:
            log.warning("server unreachable: %s", e); time.sleep(15); continue
        if not job:
            time.sleep(5); continue
        log.info("job %s (%s)", job["id"], job["kind"])
        try:
            handlers[job["kind"]](srv, job, args)
            log.info("job %s done", job["id"])
        except Exception as e:
            log.exception("job %s failed", job["id"])
            try:
                srv.post(f"/api/worker/jobs/{job['id']}/fail", json={"error": f"{type(e).__name__}: {e}"})
            except requests.RequestException:
                pass
        if args.once:
            break


if __name__ == "__main__":
    main()
