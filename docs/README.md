---
title: "PPE Auto-Labeling & YOLO26 Training — Documentation"
category: "Index"
order: -1
status: "Verified"
---

# PPE Auto-Labeling & YOLO26 Training — Documentation Index

> Documentation set for the **PPE Auto-Labeling & YOLO26 Training** project
>
> Covers 3 requirements: (1) SAM 3.1 auto-labeling, (2) YOLO26 training, (3) ground-truth generation
>
> Built with **Markdown Preview Enhanced (MPE)** — open the file in VS Code and press `Ctrl+Shift+V` to preview
>
> Uses PlantUML (requires Java), GraphViz (Viz.js bundled with MPE), KaTeX math, MPE `@import`
>
> **Arrows use orthogonal lines** — `skinparam linetype ortho` in PlantUML, `splines=ortho` in GraphViz

---

## 3 Requirements

| # | Requirement | Status | Main Document |
|---|-------------|-------|-----------|
| **RQ1** | Auto-label PPE images with SAM 3.1 | ✅ Completed | [pipeline/01-pipeline-flow.md](pipeline/01-pipeline-flow.md) |
| **RQ2** | Train YOLO26 on the PPE dataset | ✅ Completed | [pipeline/05-yolo26-training.md](pipeline/05-yolo26-training.md) |
| **RQ3** | Generate ground truth from provided data | ✅ Completed | [pipeline/03-ground-truth-generation.md](pipeline/03-ground-truth-generation.md) |

> Full report: `yolo26_ppe/reports/final/report.pdf`

---

## Document Structure

```
docs/
│
├── README.md                              ← This file (index)
├── 00-overview.md                         ← Overview of 3 requirements
├── 01-requirements.md                     ← Hardware/software requirements
│
├── architecture/
│   ├── 01-system-architecture.md          ← Architecture (SAM + YOLO + pipeline_cli)
│   ├── 02-data-flow.md                    ← Data flow + Dataset Versioning
│   └── 03-deployment.md                   ← Deployment
│
├── design/
│   ├── 01-component-design.md             ← Component responsibilities
│   ├── 02-class-diagram.md                ← Class diagram
│   └── 03-sequence-diagram.md             ← Sequence diagram
│
├── pipeline/
│   ├── 01-pipeline-flow.md                ← SAM 3.1 workflow
│   ├── 02-auto-labeling-strategy.md       ← Auto-labeling strategy
│   ├── 03-ground-truth-generation.md      ← Ground Truth Generation (RQ3)
│   ├── 04-quality-control.md              ← Quality control + Confidence Scoring
│   └── 05-yolo26-training.md              ← YOLO26 Training (RQ2)
│
├── qa/
│   └── qa-test-design.md                   ← QA design: why each test function exists
│
└── sdlc/
    ├── 01-overview.md                     ← SDLC Phase 1-2: Business Analysis + Requirements
    ├── 02-design.md                       ← SDLC Phase 3-4: Architecture, Design + Development
    └── 03-ops.md                           ← SDLC Phase 5-7: Testing, Deployment + Post-Release
```

---

## File Listing

### Top Level

| # | File | Topic | Status |
|---|------|--------|-------|
| 00 | [00-overview.md](00-overview.md) | Overview of 3 requirements | ✅ Verified |
| 01 | [01-requirements.md](01-requirements.md) | Requirements (RQ1+RQ2+RQ3) | ✅ Verified |

### architecture/

| File | Topic | Status |
|------|--------|-------|
| [01-system-architecture.md](architecture/01-system-architecture.md) | Architecture (SAM + YOLO + 3 modes) | ✅ Verified |
| [02-data-flow.md](architecture/02-data-flow.md) | Data flow + YOLO26 data flow | ✅ Verified |
| [03-deployment.md](architecture/03-deployment.md) | Deployment | ✅ Verified |

### design/

| File | Topic | Status |
|------|--------|-------|
| [01-component-design.md](design/01-component-design.md) | Component responsibilities | ✅ Verified |
| [02-class-diagram.md](design/02-class-diagram.md) | Class diagram | ✅ Verified |
| [03-sequence-diagram.md](design/03-sequence-diagram.md) | Sequence diagram | ✅ Verified |

### pipeline/

| File | Topic | Status |
|------|--------|-------|
| [01-pipeline-flow.md](pipeline/01-pipeline-flow.md) | SAM 3.1 workflow | ✅ Verified |
| [02-auto-labeling-strategy.md](pipeline/02-auto-labeling-strategy.md) | Auto-labeling strategy | ✅ Verified |
| [03-ground-truth-generation.md](pipeline/03-ground-truth-generation.md) | Ground Truth Generation (RQ3) | ✅ Verified |
| [04-quality-control.md](pipeline/04-quality-control.md) | Quality control + Confidence Scoring | ✅ Verified |
| [05-yolo26-training.md](pipeline/05-yolo26-training.md) | YOLO26 Training (RQ2) | ✅ Verified |

### sdlc/

| File | Topic | Status |
|------|--------|-------|
| [01-overview.md](sdlc/01-overview.md) | SDLC Phase 1-2: Business Analysis + Requirements | ✅ Verified |
| [02-design.md](sdlc/02-design.md) | SDLC Phase 3-4: Architecture, Design + Development | ✅ Verified |
| [03-ops.md](sdlc/03-ops.md) | SDLC Phase 5-7: Testing, Deployment + Post-Release | ✅ Verified |

### qa/

| File | Topic | Status |
|------|-------|--------|
| [qa-test-design.md](qa/qa-test-design.md) | QA design: why each test function exists + doc redundancy analysis | Verified |

---

## How to Read

1. Install **Markdown Preview Enhanced** in VS Code (extension ID: `shd101wyy.markdown-preview-enhanced`)
2. Install **Java** (for PlantUML) — verify with `java -version`
3. Open the `.md` file in VS Code
4. Press `Ctrl+Shift+V` to open the preview
5. PlantUML, GraphViz, KaTeX, and `@import` will render automatically

### MPE Features Used

| Feature | Notes |
|---------|---------|
| **PlantUML** (`puml`) | Requires Java — orthogonal arrows (`skinparam linetype ortho`) |
| **GraphViz** (`dot`) | Viz.js bundled with MPE — orthogonal lines (`splines=ortho`) |
| **KaTeX** math (`$...$`) | built-in |
| **@import** | Imports code/config files (path relative to file location) |
| **Code chunks** (`{cmd=true}`) | Requires `enableScriptExecution` to be enabled |
| **Front-matter** | YAML metadata in every file |

---

## Document Status

- **Verified** = Verified against code
- **Inferred** = Inferred from system characteristics (noted in document)
- **Assumed** = Assumed for completeness (noted in document)

The documentation clearly indicates which parts are commonly found in general systems but **not present in the actual code** (e.g., REST API, classifier, automated human review queue)

---

## Key References

| File | Responsibility |
|------|---------|
| `sam3_auto_label/src/config.py` | Config dataclasses + validation |
| `sam3_auto_label/src/inference.py` | SAM 3.1 inference + NMS + RLE |
| `sam3_auto_label/src/batch_segment.py` | Batch loop + checkpoint + ETA |
| `sam3_auto_label/src/exporters.py` | 11 export formats |
| `sam3_auto_label/src/tracker.py` | SQLite experiment tracking |
| `sam3_auto_label/config/ppe_6class.yaml` | Actual config (6 classes) |
| `pipeline_cli.py` | Root CLI — 3 modes (sam/yolo/pred) |
| `yolo26_ppe/configs/production_train.yaml` | YOLO26 training config |
| `yolo26_ppe/configs/production_augmentation.yaml` | YOLO26 augmentation config |
| `yolo26_ppe/configs/mlflow.yaml` | MLflow config |
| `yolo26_ppe/reports/final/report.pdf` | Full report |
| `yolo26_ppe/reports/inputs/final_eval_results.json` | YOLO26 metrics |
| `yolo26_ppe/reports/metrics/comparison_report.md` | Comparison summary |
