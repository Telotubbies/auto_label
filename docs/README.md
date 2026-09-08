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
| **RQ1** | Auto-label PPE images with SAM 3.1 | ✅ Completed | [pipeline/pipeline-flow.md](pipeline/pipeline-flow.md) |
| **RQ2** | Train YOLO26 on the PPE dataset | ✅ Completed | [pipeline/yolo26-training.md](pipeline/yolo26-training.md) |
| **RQ3** | Generate ground truth from provided data | ✅ Completed | [pipeline/ground-truth-generation.md](pipeline/ground-truth-generation.md) |

> Full report: `yolo26_ppe/reports/final/report.pdf`

---

## Document Structure

```
docs/
│
├── README.md                          ← This file (index)
├── 00-overview.md                     ← Overview of 3 requirements
├── 01-requirements.md                 ← Hardware/software requirements
│
├── architecture/
│   ├── system-architecture.md         ← Architecture (SAM + YOLO + pipeline_cli)
│   ├── data-flow.md                   ← Data flow + Dataset Versioning
│   └── deployment.md                  ← Deployment
│
├── pipeline/
│   ├── pipeline-flow.md               ← SAM 3.1 workflow
│   ├── auto-labeling-strategy.md      ← Auto-labeling strategy
│   ├── quality-control.md             ← Quality control + Confidence Scoring
│   ├── yolo26-training.md             ← YOLO26 Training (RQ2)
│   └── ground-truth-generation.md     ← Ground Truth Generation (RQ3)
│
├── design/
│   ├── component-design.md            ← Component responsibilities
│   ├── class-diagram.md               ← Class diagram
│   ├── sequence-diagram.md            ← Sequence diagram
│   └── state-diagram.md               ← State diagram
│
├── models/
│   ├── sam3.md                        ← SAM 3.1
│   ├── yolo26.md                      ← YOLO26 (4 models)
│   └── classifier.md                  ← Classifier (❌ not in code)
│
└── operations/
    ├── configuration.md               ← Config and parameters
    ├── cli-and-api.md                 ← CLI 3 modes (sam/yolo/pred)
    ├── testing.md                     ← Testing
    ├── performance.md                 ← Performance (SAM + YOLO26)
    ├── error-handling.md              ← Error handling
    └── troubleshooting.md             ← Troubleshooting
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
| [system-architecture.md](architecture/system-architecture.md) | Architecture (SAM + YOLO + 3 modes) | ✅ Verified |
| [data-flow.md](architecture/data-flow.md) | Data flow + YOLO26 data flow | ✅ Verified |
| [deployment.md](architecture/deployment.md) | Deployment | ✅ Verified |

### pipeline/

| File | Topic | Status |
|------|--------|-------|
| [pipeline-flow.md](pipeline/pipeline-flow.md) | SAM 3.1 workflow | ✅ Verified |
| [auto-labeling-strategy.md](pipeline/auto-labeling-strategy.md) | Auto-labeling strategy | ✅ Verified |
| [quality-control.md](pipeline/quality-control.md) | Quality control + Confidence Scoring | ✅ Verified |
| [yolo26-training.md](pipeline/yolo26-training.md) | YOLO26 Training (RQ2) | ✅ Verified |
| [ground-truth-generation.md](pipeline/ground-truth-generation.md) | Ground Truth Generation (RQ3) | ✅ Verified |

### design/

| File | Topic | Status |
|------|--------|-------|
| [component-design.md](design/component-design.md) | Component responsibilities | ✅ Verified |
| [class-diagram.md](design/class-diagram.md) | Class diagram | ✅ Verified |
| [sequence-diagram.md](design/sequence-diagram.md) | Sequence diagram | ✅ Verified |
| [state-diagram.md](design/state-diagram.md) | State diagram | ✅ Verified |

### models/

| File | Topic | Status |
|------|--------|-------|
| [sam3.md](models/sam3.md) | SAM 3.1 | ✅ Verified |
| [yolo26.md](models/yolo26.md) | YOLO26 (4 models + benchmark) | ✅ Verified |
| [classifier.md](models/classifier.md) | Classifier (❌ not in code) | ✅ Verified |

### operations/

| File | Topic | Status |
|------|--------|-------|
| [configuration.md](operations/configuration.md) | Config and parameters | ✅ Verified |
| [cli-and-api.md](operations/cli-and-api.md) | CLI 3 modes (sam/yolo/pred) | ✅ Verified |
| [testing.md](operations/testing.md) | Testing | ✅ Verified |
| [performance.md](operations/performance.md) | Performance (SAM + YOLO26) | ✅ Verified |
| [error-handling.md](operations/error-handling.md) | Error handling | ✅ Verified |
| [troubleshooting.md](operations/troubleshooting.md) | Troubleshooting | ✅ Verified |

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
