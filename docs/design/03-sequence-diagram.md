---
title: "Sequence Diagram"
category: "Design"
order: 3
status: "Verified"
---

# Sequence Diagram

> Function call sequence between components in a single inference round
>
> **Status**: Verified — cross-checked against `src/batch_segment.py:main()` and `src/inference.py:segment_image()`

---

## Sequence: Full Pipeline Run

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam sequence {
  ParticipantBackgroundColor #E8F0FE
  ParticipantBorderColor #4285F4
  LifeLineBorderColor #4285F4
}

participant "segment_image" as SI
participant "SAM 3.1 Processor" as PROC
database "SAM 3.1 Model" as MODEL
participant "cross_class_nms" as NMS
participant "mask_to_rle" as RLE

SI -> PROC : reset_all_prompts(state)
loop each category (6 classes)
  SI -> PROC : set_text_prompt(state, cat.prompt)
  PROC -> MODEL : forward(image, prompt)
  MODEL --> PROC : masks, boxes, scores
  PROC --> SI : output
  SI -> SI : filter score >= cat_threshold
end

SI -> SI : stack all detections
SI -> NMS : cross_class_nms(masks, boxes, scores, cat_ids, IoU=0.5)
alt GPU available
  NMS -> NMS : gpu_mask_iou (mask IoU)
else CPU fallback
  NMS -> NMS : torchvision.ops.nms (bbox IoU)
end
NMS --> SI : keep_indices

SI -> SI : clamp boxes to image bounds
loop each kept detection
  SI -> RLE : mask_to_rle(mask)
  RLE --> SI : RLE counts string
  SI -> SI : build annotation dict
end

SI --> SI : return annotations[]
@enduml
```

---

## Sequence: Error Path (image where inference failed)

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam sequence {
  ParticipantBackgroundColor #FCE8E6
  ParticipantBorderColor #EA4335
  LifeLineBorderColor #EA4335
}

participant "main loop" as CLI
participant "segment_image" as SEG
participant "Exception handler" as EXC
participant "tracker.py" as TRK
database "errors.json" as ERR

CLI -> SEG : segment_image(...)
SEG --> CLI : raise Exception("...")
CLI -> EXC : catch Exception
EXC -> EXC : log error message
EXC -> EXC : mark image as processed
EXC -> ERR : append to errors list
EXC -> TRK : (no image_result logged — skipped)
EXC --> CLI : continue to next image
@enduml
```

> **No retry** — errored images are skipped and not reprocessed

---

## References

- `src/batch_segment.py:130-435` — main loop
- `src/inference.py:382-520` — segment_image
- `src/inference.py:189-313` — cross_class_nms
- `src/inference.py:22-84` — mask_to_rle
