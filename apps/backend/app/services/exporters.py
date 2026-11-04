"""Write a generated version (manifest + images) out in a dataset format.

The manifest is produced by services.versioning:
  {"classes": [name, ...], "type": project type,
   "items": [{"file": "train/x.jpg", "split", "width", "height", "anns": [{"cls": idx, "shape": {...}}]}]}
Each exporter lays files out under `out` the way Roboflow's download zip does.
"""
import csv
import json
import shutil
import threading
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from ..adapters.base import Cancelled
from ..naming import path_segment
from .imaging import bbox_of, obb_corners

FORMATS = {
    "coco":            {"label": "COCO JSON",             "tasks": ["object-detection", "instance-segmentation"]},
    "yolo":            {"label": "YOLOv8 / v11 / 26",     "tasks": ["object-detection", "instance-segmentation"]},
    "yolo_obb":        {"label": "YOLO OBB (v8/v11/v26)", "tasks": ["object-detection"]},
    "coco_keypoints":  {"label": "COCO Keypoints",        "tasks": ["keypoint-detection"]},
    "voc":             {"label": "Pascal VOC XML",         "tasks": ["object-detection"]},
    "createml":        {"label": "CreateML JSON",          "tasks": ["object-detection"]},
    "tf_csv":          {"label": "TensorFlow Object Detection CSV", "tasks": ["object-detection"]},
    "folder":          {"label": "Folder Structure",       "tasks": ["classification"]},
    "multiclass_csv":  {"label": "Multi-Label Classification CSV", "tasks": ["classification"]},
}


def _check_stop(should_stop) -> None:
    """Stop between items; the caller cleans the partial directory (I22)."""
    if should_stop and should_stop():
        raise Cancelled("export cancelled")


def _copy(src_root: Path, out: Path, item: dict, sub: str = "images") -> Path:
    name = Path(item["file"]).name
    dst = out / item["split"] / sub / name if sub else out / item["split"] / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_root / item["file"], dst)
    return dst


def _abs_box(ann, W, H):
    b = bbox_of(ann, W, H)
    if not b:
        return None
    x, y, w, h = b
    return x * W, y * H, w * W, h * H


def _obb_corners_px(ann: dict, W: float, H: float) -> list[tuple[float, float]] | None:
    """Pixel corners for an obb, or the axis-aligned corners of a bbox/polygon annotation."""
    s = ann["shape"]
    if s["kind"] == "obb":
        return obb_corners(s, W, H)
    box = bbox_of(ann, W, H)
    if not box:
        return None
    x, y, w, h = box
    return [(x * W, y * H), ((x + w) * W, y * H), ((x + w) * W, (y + h) * H), (x * W, (y + h) * H)]


def _yolo_yaml(m: dict, out: Path, task: str = ""):
    splits = {it["split"] for it in m["items"]}
    yaml = []   # no `path:` — ultralytics then resolves splits relative to this yaml's folder
    for s in ("train", "valid", "test"):
        # ultralytics requires train+val keys; fall back to train when a split is empty
        key = "val" if s == "valid" else s
        yaml.append(f"{key}: {(s if s in splits else 'train')}/images")
    yaml.append(f"nc: {len(m['classes'])}")
    yaml.append("names: " + json.dumps(m["classes"]))
    if task:
        yaml.append(f"task: {task}")
    (out / "data.yaml").write_text("\n".join(yaml) + "\n")


def export_coco(m: dict, src: Path, out: Path, should_stop=None):
    cats = [{"id": i, "name": n, "supercategory": "none"} for i, n in enumerate(m["classes"])]
    for split in ("train", "valid", "test"):
        items = [it for it in m["items"] if it["split"] == split]
        if not items:
            continue
        imgs, anns, aid = [], [], 0
        for iid, it in enumerate(items):
            _check_stop(should_stop)
            _copy(src, out, it, sub="")
            W, H = it["width"], it["height"]
            imgs.append({"id": iid, "file_name": Path(it["file"]).name, "width": W, "height": H})
            for a in it["anns"]:
                box = _abs_box(a, W, H)
                if not box:
                    continue
                rec = {"id": aid, "image_id": iid, "category_id": a["cls"], "bbox": [round(v, 2) for v in box],
                       "area": round(box[2] * box[3], 2), "iscrowd": 0, "segmentation": []}
                if a["shape"]["kind"] == "polygon":
                    rec["segmentation"] = [[round(v * (W if i % 2 == 0 else H), 2) for i, v in enumerate(a["shape"]["points"])]]
                anns.append(rec); aid += 1
        (out / split).mkdir(parents=True, exist_ok=True)
        (out / split / "_annotations.coco.json").write_text(json.dumps(
            {"info": {"description": "LabelDesk export"}, "images": imgs, "annotations": anns, "categories": cats}))


def export_yolo(m: dict, src: Path, out: Path, should_stop=None):
    seg = m["type"] == "instance-segmentation"
    for it in m["items"]:
        _check_stop(should_stop)
        img = _copy(src, out, it)
        lines = []
        for a in it["anns"]:
            s = a["shape"]
            if seg and s["kind"] == "polygon":
                lines.append(f"{a['cls']} " + " ".join(f"{v:.6f}" for v in s["points"]))
            else:
                b = bbox_of(a)
                if b:
                    x, y, w, h = b
                    lines.append(f"{a['cls']} {x + w / 2:.6f} {y + h / 2:.6f} {w:.6f} {h:.6f}")
        lbl = out / it["split"] / "labels" / (img.stem + ".txt")
        lbl.parent.mkdir(parents=True, exist_ok=True)
        lbl.write_text("\n".join(lines))
    _yolo_yaml(m, out)


def export_yolo_obb(m: dict, src: Path, out: Path, should_stop=None):
    for it in m["items"]:
        _check_stop(should_stop)
        img = _copy(src, out, it)
        W, H = it["width"], it["height"]
        lines = []
        for a in it["anns"]:
            pts = _obb_corners_px(a, W, H)
            if not pts:
                continue
            flat = [v for x, y in pts for v in (x / W, y / H)]
            lines.append(f"{a['cls']} " + " ".join(f"{v:.6f}" for v in flat))
        lbl = out / it["split"] / "labels" / (img.stem + ".txt")
        lbl.parent.mkdir(parents=True, exist_ok=True)
        lbl.write_text("\n".join(lines))
    _yolo_yaml(m, out, task="obb")


def export_coco_keypoints(m: dict, src: Path, out: Path, should_stop=None):
    skeletons = m.get("skeletons") or []
    cats = []
    for i, name in enumerate(m["classes"]):
        cat = {"id": i, "name": name, "supercategory": "none"}
        sk = skeletons[i] if i < len(skeletons) else None
        if sk and sk.get("names"):
            cat["keypoints"] = sk["names"]
            if sk.get("edges"):
                cat["skeleton"] = [[a + 1, b + 1] for a, b in sk["edges"]]   # COCO is 1-based
        cats.append(cat)
    for split in ("train", "valid", "test"):
        items = [it for it in m["items"] if it["split"] == split]
        if not items:
            continue
        imgs, anns, aid = [], [], 0
        for iid, it in enumerate(items):
            _check_stop(should_stop)
            _copy(src, out, it, sub="")
            W, H = it["width"], it["height"]
            imgs.append({"id": iid, "file_name": Path(it["file"]).name, "width": W, "height": H})
            for a in it["anns"]:
                s = a["shape"]
                if s["kind"] != "keypoints":
                    continue
                box = bbox_of(a)
                if not box:
                    continue
                x, y, w, h = box
                pts = s["points"]
                flat = [round(v * (W if i % 3 == 0 else H), 2) if i % 3 != 2 else int(v)
                        for i, v in enumerate(pts)]
                anns.append({"id": aid, "image_id": iid, "category_id": a["cls"],
                             "bbox": [round(x * W, 2), round(y * H, 2), round(w * W, 2), round(h * H, 2)],
                             "area": round(w * W * h * H, 2), "iscrowd": 0, "keypoints": flat,
                             "num_keypoints": sum(1 for i in range(2, len(pts), 3) if int(pts[i]) > 0)})
                aid += 1
        (out / split).mkdir(parents=True, exist_ok=True)
        (out / split / "_annotations.coco.json").write_text(json.dumps(
            {"info": {"description": "LabelDesk export"}, "images": imgs, "annotations": anns, "categories": cats}))


def export_voc(m: dict, src: Path, out: Path, should_stop=None):
    for it in m["items"]:
        _check_stop(should_stop)
        img = _copy(src, out, it, sub="")
        W, H = it["width"], it["height"]
        objs = []
        for a in it["anns"]:
            box = _abs_box(a, W, H)
            if not box:
                continue
            x, y, w, h = box
            objs.append(f"<object><name>{escape(m['classes'][a['cls']])}</name><pose>Unspecified</pose><truncated>0</truncated>"
                        f"<difficult>0</difficult><bndbox><xmin>{x:.0f}</xmin><ymin>{y:.0f}</ymin>"
                        f"<xmax>{x + w:.0f}</xmax><ymax>{y + h:.0f}</ymax></bndbox></object>")
        (img.with_suffix(".xml")).write_text(
            f"<annotation><folder></folder><filename>{escape(img.name)}</filename><size><width>{W}</width>"
            f"<height>{H}</height><depth>3</depth></size>{''.join(objs)}</annotation>")


def export_createml(m: dict, src: Path, out: Path, should_stop=None):
    for split in ("train", "valid", "test"):
        rows = []
        for it in (i for i in m["items"] if i["split"] == split):
            _check_stop(should_stop)
            img = _copy(src, out, it, sub="")
            W, H = it["width"], it["height"]
            labels = []
            for a in it["anns"]:
                box = _abs_box(a, W, H)
                if box:
                    x, y, w, h = box
                    labels.append({"label": m["classes"][a["cls"]],
                                   "coordinates": {"x": x + w / 2, "y": y + h / 2, "width": w, "height": h}})
            rows.append({"image": img.name, "annotations": labels})
        if rows:
            (out / split / "_annotations.createml.json").write_text(json.dumps(rows))


def export_tf_csv(m: dict, src: Path, out: Path, should_stop=None):
    for split in ("train", "valid", "test"):
        items = [i for i in m["items"] if i["split"] == split]
        if not items:
            continue
        (out / split).mkdir(parents=True, exist_ok=True)
        with open(out / split / "_annotations.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["filename", "width", "height", "class", "xmin", "ymin", "xmax", "ymax"])
            for it in items:
                _check_stop(should_stop)
                img = _copy(src, out, it, sub="")
                for a in it["anns"]:
                    box = _abs_box(a, it["width"], it["height"])
                    if box:
                        x, y, bw, bh = box
                        w.writerow([img.name, it["width"], it["height"], m["classes"][a["cls"]],
                                    round(x), round(y), round(x + bw), round(y + bh)])


def export_folder(m: dict, src: Path, out: Path, should_stop=None):
    root = out.resolve()
    for it in m["items"]:
        _check_stop(should_stop)
        for a in it["anns"][:1] or [None]:
            cls = path_segment(m["classes"][a["cls"]]) if a else "_unlabeled"
            dst = out / it["split"] / cls / Path(it["file"]).name
            if not dst.resolve().is_relative_to(root):
                raise ValueError(f"class name is not a safe path segment: {cls!r}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src / it["file"], dst)


def export_multiclass_csv(m: dict, src: Path, out: Path, should_stop=None):
    for split in ("train", "valid", "test"):
        items = [i for i in m["items"] if i["split"] == split]
        if not items:
            continue
        (out / split).mkdir(parents=True, exist_ok=True)
        with open(out / split / "_classes.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["filename", *m["classes"]])
            for it in items:
                _check_stop(should_stop)
                img = _copy(src, out, it, sub="")
                on = {a["cls"] for a in it["anns"]}
                w.writerow([img.name, *[1 if i in on else 0 for i in range(len(m["classes"]))]])


EXPORTERS = {
    "coco": export_coco, "yolo": export_yolo, "yolo_obb": export_yolo_obb, "coco_keypoints": export_coco_keypoints,
    "voc": export_voc, "createml": export_createml, "tf_csv": export_tf_csv, "folder": export_folder,
    "multiclass_csv": export_multiclass_csv,
}


def build_dir(fmt: str, version_dir: Path, out: Path, should_stop=None) -> Path:
    """Lay version_dir/manifest.json out in `fmt` under a fresh `out` directory."""
    m = json.loads((version_dir / "manifest.json").read_text())
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    EXPORTERS[fmt](m, version_dir, out, should_stop=should_stop)
    _check_stop(should_stop)
    (out / "README.labeldesk.txt").write_text(
        f"Exported from LabelDesk\nformat: {FORMATS[fmt]['label']}\nclasses: {', '.join(m['classes'])}\n"
        f"images: {len(m['items'])}\n")
    return out


def export(fmt: str, version_dir: Path, out: Path, should_stop=None) -> Path:
    """Export version_dir/manifest.json into `out` and return the zip path."""
    build_dir(fmt, version_dir, out, should_stop=should_stop)
    return Path(shutil.make_archive(str(out), "zip", out))


_LOCKS: dict = {}
_LOCKS_GUARD = threading.Lock()


def cached_export(version_dir: Path, fmt: str, should_stop=None) -> Path:
    """versions/<id>/exports/<fmt>/, built once under a per-(version, fmt) lock into a unique temp dir."""
    dst = version_dir / "exports" / fmt
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault((str(version_dir), fmt), threading.Lock())
    with lock:
        if dst.exists():
            return dst
        tmp = version_dir / "exports" / f".{fmt}.{uuid.uuid4().hex}.tmp"
        try:
            if should_stop is None:
                build_dir(fmt, version_dir, tmp)
            else:
                build_dir(fmt, version_dir, tmp, should_stop=should_stop)
            tmp.rename(dst)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return dst
