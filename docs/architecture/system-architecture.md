---
title: "System Architecture"
category: "Architecture"
order: 2
status: "Verified"
---

# System Architecture

> Architecture overview — covers 3 requirements (SAM auto-label, YOLO26 train, ground truth)
>
> **Status**: Verified — cross-checked against `sam3_auto_label/src/`, `yolo26_ppe/`, `pipeline_cli.py`

---

## High-Level Architecture

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam component {
  BackgroundColor #E8F0FE
  BorderColor #4285F4
}
skinparam database {
  BackgroundColor #FFF8E1
  BorderColor #F9A825
}

actor "User" as USER

package "pipeline_cli.py\n(Orchestrator — 3 modes)" as ORCH #E8F5E9 {
  component "sam mode" as SAM_MODE
  component "yolo mode" as YOLO_MODE
  component "pred mode" as PRED_MODE
}

package "RQ1 — SAM 3.1 Auto-Label" as SAM_PKG #E8F5E9 {
  component "batch_segment.py" as BS
  component "inference.py" as INF
  component "config.py" as CFG
  component "exporters.py" as EXP
  component "tracker.py" as TRK
  database "SAM 3.1\nModel" as MODEL
}

package "RQ2 — YOLO26 Training" as YOLO_PKG #FCE8E6 {
  component "YOLO26 Train\n(Ultralytics)" as TRAIN
  component "MLflow\nTracking" as MLF
  component "ONNX Export" as ONNX
  component "Evaluate" as EVAL
  database "YOLO26 Models\n(n/s detect+seg)" as YMODELS
}

package "RQ3 — Ground Truth" as GT_PKG #FFF8E1 {
  database "data/raw/" as RAW
  database "data/sam_outputs_ground_truth/" as GT
  database "yolo26_ppe/data/\n(v1, v2)" as DS
}

USER --> ORCH : python pipeline_cli.py
ORCH --> SAM_MODE
ORCH --> YOLO_MODE
ORCH --> PRED_MODE

SAM_MODE --> BS
BS --> CFG : load_config
BS --> INF : build_model + segment
INF --> MODEL : text prompt inference
BS --> EXP : export 11 formats
BS --> TRK : log experiment
EXP --> GT : write annotations

GT --> DS : convert + verify
YOLO_MODE --> TRAIN
TRAIN --> DS : train/val/test
TRAIN --> MLF : log metrics
TRAIN --> YMODELS : save weights
YMODELS --> EVAL
EVAL --> ONNX

PRED_MODE --> YMODELS : load model
PRED_MODE --> RAW : inference

@enduml
```

---

## SAM 3.1 Module Architecture (RQ1)

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam component {
  BackgroundColor #E8F0FE
  BorderColor #4285F4
}

package "sam3_auto_label/src/" {
  [config.py\n(load + validate YAML)] as CFG
  [inference.py\n(SAM 3.1 + NMS + RLE)] as INF
  [batch_segment.py\n(batch loop + checkpoint)] as BS
  [exporters.py\n(11 formats)] as EXP
  [tracker.py\n(SQLite + JSON)] as TRK
}

file "config/ppe_6class.yaml" as YAML
database "sam3.1_multiplex.pt" as CKPT
database "sam3/\n(vendored)" as SAM3

YAML --> CFG : parse
CFG --> BS : Config
BS --> INF : build_model
CKPT --> INF : load weights
SAM3 --> INF : perflib (GPU ops)
BS --> EXP : write exports
BS --> TRK : log experiment

@enduml
```

---

## YOLO26 Module Architecture (RQ2)

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam component {
  BackgroundColor #FCE8E6
  BorderColor #EA4335
}

package "yolo26_ppe/" {
  [configs/\n(production_train.yaml)] as CONF
  [YOLO26 Train\n(Ultralytics CLI)] as TRAIN
  [MLflow Tracking] as MLF
  [Evaluate\n(test set)] as EVAL
  [ONNX Export] as ONNX
  [Report Generator\n(XeLaTeX)] as REPORT
}

database "yolo26_ppe/data/\n(v1, v2)" as DS
database "yolo26_ppe/models/" as MODELS
database "yolo26_ppe/reports/\nfinal/report.pdf" as PDF

CONF --> TRAIN
DS --> TRAIN : train/val/test split
TRAIN --> MLF : log metrics
TRAIN --> MODELS : save .pt
MODELS --> EVAL
EVAL --> ONNX
EVAL --> REPORT : metrics + figures
REPORT --> PDF

@enduml
```

---

## pipeline_cli.py — 3 Modes

> Source: `pipeline_cli.py:263-265, 550-552, 834-852`

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam ActivityBackgroundColor #E8F0FE
skinparam ActivityBorderColor #4285F4

start
:User runs pipeline_cli.py;

switch (mode)
case (sam)
  :SAM 3.1 Auto-Labeling;
  :Load config YAML;
  :Build SAM 3.1 model;
  :Batch segment all images;
  :Export 11 formats;
  :Save to sam_outputs_ground_truth/;
case (yolo)
  :YOLO26 Training;
  :Prepare dataset from ground truth;
  :Train 4 models (n/s detect+seg);
  :Evaluate on test set;
  :Export ONNX;
  :Generate report.pdf;
case (pred)
  :YOLO26 Inference;
  :Load trained model;
  :Run inference on new images;
  :Output predictions;
endswitch

stop
@enduml
```

---

## Hardware Utilization (SAM 3.1 Pipeline)

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE

concise "GPU Thread" as GPU
concise "Prefetch Thread" as PRE
concise "Export Thread" as EXP

@0
GPU is "Segment img N"
PRE is "Load img N+1"
EXP is {idle}

@100
GPU is "Segment img N+1"
PRE is "Load img N+2"
EXP is "Export img N"

@200
GPU is "Segment img N+2"
PRE is "Load img N+3"
EXP is "Export img N+1"

@300
GPU is {idle}
PRE is {idle}
EXP is "Export img N+2"
@enduml
```

> Source: `src/batch_segment.py:270, 287-295, 304, 316-320`
>
> **Note**: This is a CPU thread (ThreadPoolExecutor), not multi-GPU — inference still runs on a single GPU

---

## References

- `pipeline_cli.py:263-265` — 3 modes
- `pipeline_cli.py:550-552` — mode names
- `pipeline_cli.py:834-852` — mode selection
- `sam3_auto_label/src/config.py:70-125` — `Config` dataclass
- `sam3_auto_label/src/inference.py:347-365` — `build_model()`
- `sam3_auto_label/src/batch_segment.py:130-435` — `main()` loop
- `sam3_auto_label/src/exporters.py:577-589` — `EXPORTERS` registry
- `sam3_auto_label/src/tracker.py:23-229` — `ExperimentTracker`
- `yolo26_ppe/configs/production_train.yaml` — YOLO26 training config
- `yolo26_ppe/reports/final/report.pdf` — final report
