---
title: "06 — Class Diagram"
category: "SAM 3.1 Auto-Labeling"
order: 6
status: "Verified"
---

# 06 — Class Diagram

> Class structure and relationships in the system
>
> **Status**: Verified — cross-checked against `src/config.py`, `src/inference.py`, `src/tracker.py`, `src/exporters.py`

---

## Class Diagram

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam package {
  BorderColor #4285F4
  BackgroundColor #F0F4FF
}

package "inference.py" {
  [build_model\ncfg → processor] as BM
  [segment_image\nprocessor + image → annotations] as SI
  [save_coco\nannotations → JSON] as SC
  [save_masks\nannotations → PNG] as SM
  [save_viz\nimage + annotations → overlay PNG] as SV
  [resolve_device\ncfg → device string] as RD
}

package "NMS" {
  [cross_class_nms\nCPU path] as CN
  [cross_class_nms_gpu\nGPU path] as CNG
  [_gpu_nms] as GN
  [_gpu_bbox_nms] as GBN
}

package "RLE" {
  [mask_to_rle\nCPU] as MR
  [mask_to_rle_gpu\nGPU] as MRG
  [masks_batch_to_rle_gpu] as MBR
}

BM --> SI
SI --> CN
CN --> CNG
CNG --> GN
GN --> GBN
SI --> MR
MR --> MRG
MRG --> MBR
SI --> SC
SI --> SM
SI --> SV
@enduml
```

### `exporters.py` — Export Registry

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam package {
  BorderColor #34A853
  BackgroundColor #F0F8F0
}

package "exporters.py" {
  [write_image_exports\nper-image] as WE
  [finalize_exports\nend-of-run] as FE
  [EXPORTERS registry] as REG

  [_coco_final] as CF
  [_yolo_image + _yolo_final] as YOLO
  [_voc_image] as VOC
  [_labelme_image] as LM
  [_cvat_final] as CVAT
  [_label_studio_final] as LS
  [_kitti_image] as KITTI
  [_createml_final] as CM
  [_openimages_final] as OI
  [_supervisely_image + _supervisely_final] as SUP
  [_masks_image] as MASKS
}

WE --> REG
FE --> REG
REG --> CF
REG --> YOLO
REG --> VOC
REG --> LM
REG --> CVAT
REG --> LS
REG --> KITTI
REG --> CM
REG --> OI
REG --> SUP
REG --> MASKS
@enduml
```

---

## What Typical Systems Usually Have (but this code does not)

| Common class | Status | Note |
|----------------|-------|---------|
| `Segmenter` interface (abstract) | ❌ | `build_model` is directly coupled to SAM 3.1 |
| `SAM3Segmenter`, `SAM2Segmenter`, `YOLOSegmenter` | ❌ | No polymorphism — changing the model requires modifying `inference.py` |
| `ImageLoader` class | ❌ | Implemented as a `load_image` function in `batch_segment.py` |
| `Preprocessor` class | ❌ | SAM processor handles resizing internally |
| `PromptGenerator` class | ❌ | Prompts come directly from config |
| `MaskProcessor` class | ❌ | Distributed across `inference.py` (NMS, RLE, clamp) |
| `Classifier` class | ❌ | No separate classifier |
| `ConfidenceScorer` class | ❌ | Uses raw scores from the model |
| `LabelValidator` class | ❌ | No validation before export |
| `AutoLabeler`, `HumanReviewer` class | ❌ | No review process |
| `DatasetExporter` class | ❌ | Implemented as a registry of functions, not a class |

---

## References

- `src/config.py:10-125` — dataclasses
- `src/tracker.py:23-229` — ExperimentTracker
- `src/inference.py:347-365` — build_model (not a class)
- `src/exporters.py:577-589` — EXPORTERS registry (not a class)
