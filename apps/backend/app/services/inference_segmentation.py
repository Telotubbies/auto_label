"""Segmentation catalogue (T-1014): the models auto-label can actually run on this host.

Every row names the licence its weights carry, the memory one image occupies at 512 px and
1024 px, the official source and the ref the shipped auto-label flow accepts. The figures are
**not** the T-1004 LLM estimator's: segmentation memory is dominated by image-resolution
activations and the encoder, not by parameters and a KV cache, so each row carries a reference
figure and the note that says how it was taken.

``provisioned`` is the verdict the Segmentation tab (T-1015) renders as its state chip; the
reason always opens with the chip text. Reading config and the filesystem is the whole surface:
nothing here writes, downloads or starts a model (PLAN §12 decision 5: installs stay admin-only).
"""

import os
from pathlib import Path

from .. import config
from ..adapters.catalog import _zoo

MISSING = "Missing checkpoint"
NO_ADAPTER = "Adapter not installed"
NO_OS = "Not supported on this OS"

SAM_CHECKPOINT = Path("checkpoints") / "sam3.1_multiplex.pt"
VRAM_NOTE = (
    "Reference figure for one image at fp16 on one GPU, not a measurement on this machine; "
    "activations dominate at 1024 px, so re-measure on this host before relying on it."
)
# A licence whose name says non-commercial must carry the badge; AGPL is its own badge, not this one.
_NC_WORDS = ("NON-COMMERCIAL", "NONCOMMERCIAL", "NC", "RESEARCH ONLY")

SEGMENTATION: list[dict] = [
    {
        "id": "sam3.1",
        "name": "SAM 3.1",
        "family": "SAM",
        "params_m": 848.0,
        "engine": "sam3",
        "licence": {
            "name": "SAM License",
            "non_commercial": False,
            "url": "https://github.com/facebookresearch/sam3/blob/main/LICENSE",
        },
        "vram": {"512": 4300, "1024": 8100},
        "source_url": "https://github.com/facebookresearch/sam3",
        "note": VRAM_NOTE,
    },
    {
        "id": "sam2",
        "name": "SAM2 Large",
        "family": "SAM",
        "params_m": 224.4,
        "engine": "sam2",
        "licence": {
            "name": "Apache-2.0",
            "non_commercial": False,
            "url": "https://github.com/facebookresearch/sam2/blob/main/LICENSE",
        },
        "vram": {"512": 2600, "1024": 4200},
        "source_url": "https://github.com/facebookresearch/sam2",
        "note": VRAM_NOTE,
    },
    {
        "id": "yolo26n-seg",
        "name": "YOLO26 N Seg",
        "family": "YOLO26",
        "params_m": 2.7,
        "engine": "ultralytics",
        "licence": {
            "name": "AGPL-3.0",
            "non_commercial": False,
            "url": "https://github.com/ultralytics/ultralytics/blob/main/LICENSE",
        },
        "vram": {"512": 1200, "1024": 1900},
        "source_url": "https://docs.ultralytics.com/models/yolo26/",
        "note": VRAM_NOTE,
    },
    {
        "id": "yolo26s-seg",
        "name": "YOLO26 S Seg",
        "family": "YOLO26",
        "params_m": 10.4,
        "engine": "ultralytics",
        "licence": {
            "name": "AGPL-3.0",
            "non_commercial": False,
            "url": "https://github.com/ultralytics/ultralytics/blob/main/LICENSE",
        },
        "vram": {"512": 1500, "1024": 2400},
        "source_url": "https://docs.ultralytics.com/models/yolo26/",
        "note": VRAM_NOTE,
    },
    {
        "id": "yolo26m-seg",
        "name": "YOLO26 M Seg",
        "family": "YOLO26",
        "params_m": 23.6,
        "engine": "ultralytics",
        "licence": {
            "name": "AGPL-3.0",
            "non_commercial": False,
            "url": "https://github.com/ultralytics/ultralytics/blob/main/LICENSE",
        },
        "vram": {"512": 2200, "1024": 3600},
        "source_url": "https://docs.ultralytics.com/models/yolo26/",
        "note": VRAM_NOTE,
    },
    {
        "id": "mask2former-swin-l",
        "name": "Mask2Former Swin-L",
        "family": "Mask2Former",
        "params_m": 216.0,
        "engine": "mask2former",
        "licence": {
            "name": "CC-BY-NC-4.0",
            "non_commercial": True,
            "url": "https://creativecommons.org/licenses/by-nc/4.0/legalcode",
        },
        "vram": {"512": 3900, "1024": 7400},
        "source_url": "https://huggingface.co/facebook/mask2former-swin-large-coco-instance",
        "note": VRAM_NOTE,
    },
]

# The ref the shipped flow resolves, and whether a project must add classes first. SAM family
# prompts come from the project's class names; a COCO YOLO weight brings its own labels.
_AUTO_LABEL = {
    "sam3.1": ("sam3:sam3.1", True),
    "sam2": (None, True),
    "yolo26n-seg": ("ultralytics:yolo26n-seg", False),
    "yolo26s-seg": ("ultralytics:yolo26s-seg", False),
    "yolo26m-seg": ("ultralytics:yolo26m-seg", False),
    "mask2former-swin-l": (None, True),
}


def auto_label_ref(model: dict) -> dict:
    """The ref auto-label accepts for this row, its engine and whether classes are required."""
    ref, classes_required = _AUTO_LABEL[model["id"]]
    return {"ref": ref, "engine_hint": model["engine"], "classes_required": classes_required}


def _zoo_refs() -> set[str]:
    """Every ref the registry ships; a row's ref must be one of them or auto-label fails at run time."""
    return {f"{family}:{variant}" for family, variant, _ in _zoo()}


def _seg_dir() -> Path:
    """Where SAM2 and Mask2Former weights live: the named env, else the sibling ML checkout."""
    return Path(os.environ.get("LD_SEG_MODELS_DIR") or config.ML_SIBLING / "seg_models")


def _adapter_present(name: str) -> bool:
    """Whether the adapter module ships beside this service."""
    return (Path(__file__).parents[1] / "adapters" / name).exists()


def _sam3() -> tuple[bool, str]:
    if config.SAM_ENABLED == "0":
        return False, f"{NO_ADAPTER}: SAM is switched off on this host (LD_SAM_ENABLED=0)."
    path = Path(config.SAM_ROOT) / SAM_CHECKPOINT
    if not path.exists():
        return False, (
            f"{MISSING}: set LD_SAM_ROOT to a sam3_auto_label checkout that contains "
            f"{SAM_CHECKPOINT.as_posix()} (looked in {path})."
        )
    if not _adapter_present("sam3_ad.py"):
        return False, f"{NO_ADAPTER}: {path} exists but app/adapters/sam3_ad.py is missing."
    return True, ""


def _sam2() -> tuple[bool, str]:
    folder = _seg_dir()
    if folder.is_dir() and next(folder.glob("sam2*.pt"), None) is not None:
        return True, ""
    return False, (f"{MISSING}: put a SAM2 checkpoint named sam2*.pt in LD_SEG_MODELS_DIR ({folder}); no file matched.")


def _yolo() -> tuple[bool, str]:
    folder = Path(config.PRETRAINED_DIR)
    if folder.is_dir() and next(folder.glob("yolo26*-seg.pt"), None) is not None:
        return True, ""
    return False, (f"{MISSING}: set LD_PRETRAINED_DIR to a folder holding a yolo26*-seg.pt weight ({folder} has none).")


def _mask2former() -> tuple[bool, str]:
    folder = _seg_dir()
    found = folder.is_dir() and any(path.is_dir() for path in folder.glob("mask2former*"))
    if found:
        return True, ""
    return False, (f"{MISSING}: put a mask2former* directory in LD_SEG_MODELS_DIR ({folder}); none was found.")


_CHECKS = {"sam3": _sam3, "sam2": _sam2, "ultralytics": _yolo, "mask2former": _mask2former}


def provisioned(model: dict, host_inventory: dict | None) -> dict:
    """This host's verdict for one row: a GPU first, then the weights, then a shipped adapter."""
    gpus = (host_inventory or {}).get("gpus")
    if isinstance(gpus, list) and not gpus:
        return {
            "ok": False,
            "reason": (
                f"{NO_OS}: this host reports no GPU, and every segmentation model in this catalogue runs on one."
            ),
        }
    ok, reason = _CHECKS[model["engine"]]()
    if ok and auto_label_ref(model)["ref"] is None:
        return {
            "ok": False,
            "reason": (
                f"{NO_ADAPTER}: the auto-label flow has no {model['engine']} adapter yet, so this model cannot be used."
            ),
        }
    return {"ok": ok, "reason": reason}


def rows(host: dict) -> list[dict]:
    """The catalogue with this host's verdict; the route adds the chosen project."""
    inventory = host.get("inventory")
    return [
        {
            **row,
            "licence": dict(row["licence"]),
            "vram": dict(row["vram"]),
            "provisioned": provisioned(row, inventory),
            "auto_label": auto_label_ref(row),
        }
        for row in SEGMENTATION
    ]


def validate() -> None:
    """Raise ``ValueError`` if a row could hide a licence, a memory figure or a dangling ref."""
    ids = [row["id"] for row in SEGMENTATION]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate segmentation model ids")
    zoo = _zoo_refs()
    for row in SEGMENTATION:
        if row["engine"] not in _CHECKS:
            raise ValueError(f"{row['id']}: unknown engine {row['engine']}")
        if not row["name"].strip() or not row["family"].strip():
            raise ValueError(f"{row['id']}: no name")
        if row["params_m"] <= 0:
            raise ValueError(f"{row['id']}: no parameter count")
        for size in ("512", "1024"):
            if row["vram"].get(size, 0) <= 0:
                raise ValueError(f"{row['id']}: no VRAM figure at {size} px")
        licence = row["licence"]
        if not licence["name"].strip() or not str(licence["url"]).startswith("https://"):
            raise ValueError(f"{row['id']}: no licence url")
        if any(word in licence["name"].upper() for word in _NC_WORDS) and not licence["non_commercial"]:
            raise ValueError(f"{row['id']}: a non-commercial licence must say so")
        if not str(row["source_url"]).startswith("https://"):
            raise ValueError(f"{row['id']}: no source url")
        if not row["note"].strip():
            raise ValueError(f"{row['id']}: no note for the memory figure")
        ref = auto_label_ref(row)["ref"]
        if ref is not None and ref not in zoo:
            raise ValueError(f"{row['id']}: auto-label ref {ref} is not in the registry")
    return None
