"""The inference-test form shared by the model Predict route and the Playground.

One dependency reads every slice-inference (SAHI) and inference-time option; ``resolve_options`` validates
them. A bad value is a 400 before any credit is charged or any model runs.
"""
from fastapi import Form, HTTPException

from ..services import sahi
from ..services.flags import is_enabled


def infer_form(slice_width: int | None = Form(None), slice_height: int | None = Form(None),
               overlap_width_ratio: float | None = Form(None), overlap_height_ratio: float | None = Form(None),
               auto_slice: bool | None = Form(None), perform_standard_pred: bool | None = Form(None),
               min_area_ratio: float | None = Form(None), postprocess_type: str | None = Form(None),
               postprocess_match_metric: str | None = Form(None), postprocess_match_threshold: float | None = Form(None),
               postprocess_class_agnostic: bool | None = Form(None), imgsz: int | None = Form(None),
               max_det: int | None = Form(None), agnostic_nms: bool | None = Form(None), augment: bool | None = Form(None),
               half: bool | None = Form(None), retina_masks: bool | None = Form(None),
               class_ids: str | None = Form(None)) -> dict:
    return {
        "slice": {"slice_width": slice_width, "slice_height": slice_height, "overlap_width_ratio": overlap_width_ratio,
                  "overlap_height_ratio": overlap_height_ratio, "auto_slice": auto_slice,
                  "perform_standard_pred": perform_standard_pred, "min_area_ratio": min_area_ratio,
                  "postprocess_type": postprocess_type, "postprocess_match_metric": postprocess_match_metric,
                  "postprocess_match_threshold": postprocess_match_threshold,
                  "postprocess_class_agnostic": postprocess_class_agnostic},
        "model": {"imgsz": imgsz, "max_det": max_det, "agnostic_nms": agnostic_nms, "augment": augment, "half": half,
                  "retina_masks": retina_masks, "class_ids": class_ids},
    }


def resolve_options(form: dict, db, workspace_id: str) -> tuple[sahi.SliceConfig | None, dict]:
    """(slice config or None, inference-time options). Slice options sit behind task_30 like tiling does."""
    try:
        slicing = sahi.parse_options(form["slice"])
        model_opts = sahi.parse_model_options(form["model"])
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if slicing is not None and not is_enabled("task_30", db, workspace_id):
        raise HTTPException(404, "not found")          # a disabled surface looks missing
    return slicing, model_opts
