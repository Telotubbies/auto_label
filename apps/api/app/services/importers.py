"""Turn an upload (loose files and/or zips) into images + annotations.

Recognised annotation sources, matched to images by file name / stem:
  COCO JSON (*.json with images/annotations/categories), YOLO txt (+ data.yaml / classes.txt
  for names), Pascal VOC xml. Classification: images inside a folder named after the class.
"""
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

from .imaging import ext_ok


class Bundle:
    def __init__(self):
        self.images: dict[str, bytes] = {}        # posix path -> bytes
        self.coco: dict[str, list] = {}           # file name -> [(class name, shape)] (pixel coords, normalized later)
        self.coco_size: dict[str, tuple[int, int]] = {}
        self.yolo: dict[str, str] = {}            # stem -> txt
        self.voc: dict[str, str] = {}             # stem -> xml
        self.names: list[str] = []

    @property
    def has_annotations(self) -> bool:
        return bool(self.coco or self.yolo or self.voc)


MAX_ZIP_TOTAL = 4 * 1024**3       # uncompressed bytes per upload
MAX_ZIP_FILES = 50_000
MAX_RATIO = 200                    # compression ratio above this is treated as a zip bomb


class ImportError_(ValueError):
    pass


def collect(files: list[tuple[str, bytes]]) -> Bundle:
    b = Bundle()
    queue = list(files)
    budget, count = MAX_ZIP_TOTAL, 0
    while queue:
        name, data = queue.pop()
        name = name.replace("\\", "/")
        low = name.lower()
        if low.endswith(".zip"):
            try:
                z = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile:
                raise ImportError_(f"{name} is not a valid zip")
            with z:
                for i in z.infolist():
                    if i.is_dir() or "__MACOSX" in i.filename or i.filename.lower().endswith(".zip"):
                        continue     # nested zips are skipped: no recursive bombs
                    count += 1; budget -= i.file_size
                    if count > MAX_ZIP_FILES or budget < 0:
                        raise ImportError_("archive too large (max 50,000 files / 4 GB uncompressed)")
                    if i.compress_size and i.file_size / i.compress_size > MAX_RATIO:
                        raise ImportError_(f"{i.filename}: suspicious compression ratio")
                    queue.append((i.filename, z.read(i)))
        elif ext_ok(low):
            b.images[name] = data
        elif low.endswith(".json"):
            _coco(b, data)
        elif low.endswith(".txt"):
            stem = PurePosixPath(name).stem
            if stem in ("classes", "_darknet.labels", "obj"):
                b.names = [l.strip() for l in data.decode(errors="ignore").splitlines() if l.strip()]
            else:
                b.yolo[stem] = data.decode(errors="ignore")
        elif low.endswith(".labels"):
            b.names = [l.strip() for l in data.decode(errors="ignore").splitlines() if l.strip()]
        elif low.endswith((".yaml", ".yml")):
            m = re.search(r"names:\s*(\[.*?\])", data.decode(errors="ignore"), re.S)
            if m:
                try:
                    b.names = json.loads(m.group(1).replace("'", '"'))
                except json.JSONDecodeError:
                    pass
            else:   # block list:  names:\n  0: person\n  1: helmet   or  - person
                block = re.search(r"names:\s*\n((?:\s+.+\n?)+)", data.decode(errors="ignore"))
                if block:
                    b.names = [re.sub(r"^\s*(?:-|\d+:)\s*", "", l).strip().strip("'\"")
                               for l in block.group(1).splitlines() if l.strip()]
        elif low.endswith(".xml"):
            b.voc[PurePosixPath(name).stem] = data.decode(errors="ignore")
    return b


def _coco(b: Bundle, data: bytes):
    try:
        d = json.loads(data)
    except json.JSONDecodeError:
        return
    if not isinstance(d, dict) or "images" not in d or "annotations" not in d:
        return
    cats = {c["id"]: c["name"] for c in d.get("categories", [])}
    imgs = {i["id"]: i for i in d["images"]}
    for i in d["images"]:
        b.coco_size[PurePosixPath(i["file_name"]).name] = (i.get("width", 0), i.get("height", 0))
    for a in d["annotations"]:
        im = imgs.get(a["image_id"])
        if not im or a.get("category_id") not in cats:
            continue
        fname = PurePosixPath(im["file_name"]).name
        seg = a.get("segmentation")
        if isinstance(seg, list) and seg and isinstance(seg[0], list) and len(seg[0]) >= 6:
            shape = {"kind": "polygon", "points_px": seg[0]}
        elif a.get("bbox"):
            x, y, w, h = a["bbox"]
            shape = {"kind": "bbox", "px": [x, y, w, h]}
        else:
            continue
        b.coco.setdefault(fname, []).append((cats[a["category_id"]], shape))


def annotations_for(b: Bundle, path: str, W: int, H: int) -> list[tuple[str, dict]]:
    """-> [(class name, normalized shape)] for one image."""
    name, stem = PurePosixPath(path).name, PurePosixPath(path).stem
    out = []
    if name in b.coco:
        cw, ch = b.coco_size.get(name) or (W, H)
        cw, ch = cw or W, ch or H
        for cls, s in b.coco[name]:
            if s["kind"] == "bbox":
                x, y, w, h = s["px"]
                out.append((cls, {"kind": "bbox", "x": x / cw, "y": y / ch, "w": w / cw, "h": h / ch}))
            else:
                out.append((cls, {"kind": "polygon", "points": [v / (cw if i % 2 == 0 else ch) for i, v in enumerate(s["points_px"])]}))
    elif stem in b.yolo:
        for line in b.yolo[stem].splitlines():
            parts = line.split()
            if len(parts) < 5:
                continue
            ci = int(float(parts[0])); vals = [float(v) for v in parts[1:]]
            cls = b.names[ci] if ci < len(b.names) else f"class_{ci}"
            if len(vals) == 4:
                cx, cy, w, h = vals
                out.append((cls, {"kind": "bbox", "x": cx - w / 2, "y": cy - h / 2, "w": w, "h": h}))
            elif len(vals) >= 6:
                out.append((cls, {"kind": "polygon", "points": vals}))
    elif stem in b.voc:
        try:
            root = ET.fromstring(b.voc[stem])
            for o in root.iter("object"):
                bb = o.find("bndbox")
                x1, y1, x2, y2 = (float(bb.find(k).text) for k in ("xmin", "ymin", "xmax", "ymax"))
                out.append((o.find("name").text, {"kind": "bbox", "x": x1 / W, "y": y1 / H, "w": (x2 - x1) / W, "h": (y2 - y1) / H}))
        except Exception:
            pass
    return out


def folder_class(path: str) -> str | None:
    """Classification import: train/cat/img.jpg -> 'cat' (ignores split folder names)."""
    parts = [p for p in PurePosixPath(path).parts[:-1] if p.lower() not in ("train", "valid", "val", "test", "images")]
    return parts[-1] if parts else None


def split_of(path: str) -> str | None:
    for p in PurePosixPath(path).parts[:-1]:
        p = p.lower()
        if p in ("train", "test"):
            return p
        if p in ("valid", "val"):
            return "valid"
    return None
