---
title: "State Diagram"
category: "Design"
order: 4
status: "Verified"
---

# State Diagram

> สถานะของระบบและการเปลี่ยนสถานะ
>
> **Status**: Verified — สอบกับ `src/batch_segment.py` และ `src/tracker.py`

---

## State: Pipeline Run

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam state {
  BackgroundColor #E8F0FE
  BorderColor #4285F4
}

[*] --> PENDING
PENDING --> LOADING : prefetch
LOADING --> LOADED : load_image success
LOADING --> ERROR : load_image fail (return None)
LOADED --> SEGMENTING : segment_image
SEGMENTING --> SEGMENTED : inference success
SEGMENTING --> ERROR : inference exception
SEGMENTED --> EXPORTING : write_image_exports + save_viz (async)
EXPORTING --> EXPORTED : export success
EXPORTING --> ERROR : export fail (logged, not fatal)
EXPORTED --> LOGGING : tracker.log_image_result
LOGGING --> CHECKPOINT : save_checkpoint
CHECKPOINT --> DONE : mark processed
ERROR --> DONE : mark processed (no retry)
DONE --> [*]

@enduml
```

---

## State: Experiment (tracker.py)

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam state {
  BackgroundColor #E8F0FE
  BorderColor #4285F4
}

[*] --> ABSENT : ยังไม่เริ่ม run
ABSENT --> EXISTS : save_checkpoint (first image)
EXISTS --> EXISTS : save_checkpoint (each image)
EXISTS --> ABSENT : delete_checkpoint (clear_on_success=true, run completed)
EXISTS --> ABSENT : delete_checkpoint (--fresh flag)
EXISTS --> LOADED : load_checkpoint (--resume)
LOADED --> EXISTS : save_checkpoint (continue from resumed point)

@enduml
```

> `src/batch_segment.py:52-83` — load/save/delete checkpoint

---

## อ้างอิง

- `src/batch_segment.py:130-435` — main state flow
- `src/batch_segment.py:52-83` — checkpoint state
- `src/tracker.py:98-168` — experiment state
