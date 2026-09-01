---
title: "PPE Auto-Labeling & YOLO26 Training — Documentation"
category: "Index"
order: -1
status: "Verified"
---

# PPE Auto-Labeling & YOLO26 Training — Documentation Index

> เอกสารชุดสำหรับโปรเจกต์ **PPE Auto-Labeling & YOLO26 Training**
>
> ครอบคลุม 3 requirements: (1) SAM 3.1 auto-labeling, (2) YOLO26 training, (3) ground-truth generation
>
> สร้างด้วย **Markdown Preview Enhanced (MPE)** — เปิดไฟล์ด้วย VS Code แล้วกด `Ctrl+Shift+V` เพื่อ preview
>
> ใช้ PlantUML (ต้องมี Java), GraphViz (Viz.js มากับ MPE), KaTeX math, `@import` ของ MPE
>
> **ลูกศรเป็นเส้นตรงเหลี่ยม (orthogonal)** — `skinparam linetype ortho` ใน PlantUML, `splines=ortho` ใน GraphViz

---

## 3 Requirements

| # | Requirement | สถานะ | เอกสารหลัก |
|---|-------------|-------|-----------|
| **RQ1** | ทำ auto-label ภาพ PPE ด้วย SAM 3.1 | ✅ ทำเสร็จ | [pipeline/pipeline-flow.md](pipeline/pipeline-flow.md) |
| **RQ2** | ทำ YOLO26 train จากชุด PPE | ✅ ทำเสร็จ | [pipeline/yolo26-training.md](pipeline/yolo26-training.md) |
| **RQ3** | ทำ ground truth จาก data ที่ส่งไปให้ | ✅ ทำเสร็จ | [pipeline/ground-truth-generation.md](pipeline/ground-truth-generation.md) |

> รายงานฉบับสมบูรณ์: `yolo26_ppe/reports/final/report.pdf`

---

## โครงสร้างเอกสาร

```
docs/
│
├── README.md                          ← ไฟล์นี้ (index)
├── 00-overview.md                     ← ภาพรวม 3 requirements
├── 01-requirements.md                 ← ความต้องการ hardware/software
│
├── architecture/
│   ├── system-architecture.md         ← สถาปัตยกรรม (SAM + YOLO + pipeline_cli)
│   ├── data-flow.md                   ← การไหลของข้อมูล + Dataset Versioning
│   └── deployment.md                  ← การ deploy
│
├── pipeline/
│   ├── pipeline-flow.md               ← ลำดับการทำงาน SAM 3.1
│   ├── auto-labeling-strategy.md      ← กลยุทธ์ auto-labeling
│   ├── quality-control.md             ← การควบคุมคุณภาพ + Confidence Scoring
│   ├── yolo26-training.md             ← YOLO26 Training (RQ2)
│   └── ground-truth-generation.md     ← Ground Truth Generation (RQ3)
│
├── design/
│   ├── component-design.md            ← หน้าที่ component
│   ├── class-diagram.md               ← Class diagram
│   ├── sequence-diagram.md            ← Sequence diagram
│   └── state-diagram.md               ← State diagram
│
├── models/
│   ├── sam3.md                        ← SAM 3.1
│   ├── yolo26.md                      ← YOLO26 (4 โมเดล)
│   └── classifier.md                  ← Classifier (❌ ไม่มีในโค้ด)
│
└── operations/
    ├── configuration.md               ← Config และ parameters
    ├── cli-and-api.md                 ← CLI 3 modes (sam/yolo/pred)
    ├── testing.md                     ← การทดสอบ
    ├── performance.md                 ← ประสิทธิภาพ (SAM + YOLO26)
    ├── error-handling.md              ← การจัดการ error
    └── troubleshooting.md             ← การแก้ปัญหา
```

---

## รายการไฟล์

### ระดับบน

| # | File | หัวข้อ | สถานะ |
|---|------|--------|-------|
| 00 | [00-overview.md](00-overview.md) | ภาพรวม 3 requirements | ✅ Verified |
| 01 | [01-requirements.md](01-requirements.md) | ความต้องการ (RQ1+RQ2+RQ3) | ✅ Verified |

### architecture/

| File | หัวข้อ | สถานะ |
|------|--------|-------|
| [system-architecture.md](architecture/system-architecture.md) | สถาปัตยกรรม (SAM + YOLO + 3 modes) | ✅ Verified |
| [data-flow.md](architecture/data-flow.md) | การไหลของข้อมูล + YOLO26 data flow | ✅ Verified |
| [deployment.md](architecture/deployment.md) | การ deploy | ✅ Verified |

### pipeline/

| File | หัวข้อ | สถานะ |
|------|--------|-------|
| [pipeline-flow.md](pipeline/pipeline-flow.md) | ลำดับการทำงาน SAM 3.1 | ✅ Verified |
| [auto-labeling-strategy.md](pipeline/auto-labeling-strategy.md) | กลยุทธ์ auto-labeling | ✅ Verified |
| [quality-control.md](pipeline/quality-control.md) | การควบคุมคุณภาพ + Confidence Scoring | ✅ Verified |
| [yolo26-training.md](pipeline/yolo26-training.md) | YOLO26 Training (RQ2) | ✅ Verified |
| [ground-truth-generation.md](pipeline/ground-truth-generation.md) | Ground Truth Generation (RQ3) | ✅ Verified |

### design/

| File | หัวข้อ | สถานะ |
|------|--------|-------|
| [component-design.md](design/component-design.md) | หน้าที่ component | ✅ Verified |
| [class-diagram.md](design/class-diagram.md) | Class diagram | ✅ Verified |
| [sequence-diagram.md](design/sequence-diagram.md) | Sequence diagram | ✅ Verified |
| [state-diagram.md](design/state-diagram.md) | State diagram | ✅ Verified |

### models/

| File | หัวข้อ | สถานะ |
|------|--------|-------|
| [sam3.md](models/sam3.md) | SAM 3.1 | ✅ Verified |
| [yolo26.md](models/yolo26.md) | YOLO26 (4 โมเดล + benchmark) | ✅ Verified |
| [classifier.md](models/classifier.md) | Classifier (❌ ไม่มีในโค้ด) | ✅ Verified |

### operations/

| File | หัวข้อ | สถานะ |
|------|--------|-------|
| [configuration.md](operations/configuration.md) | Config และ parameters | ✅ Verified |
| [cli-and-api.md](operations/cli-and-api.md) | CLI 3 modes (sam/yolo/pred) | ✅ Verified |
| [testing.md](operations/testing.md) | การทดสอบ | ✅ Verified |
| [performance.md](operations/performance.md) | ประสิทธิภาพ (SAM + YOLO26) | ✅ Verified |
| [error-handling.md](operations/error-handling.md) | การจัดการ error | ✅ Verified |
| [troubleshooting.md](operations/troubleshooting.md) | การแก้ปัญหา | ✅ Verified |

---

## วิธีอ่าน

1. ติดตั้ง **Markdown Preview Enhanced** ใน VS Code (extension ID: `shd101wyy.markdown-preview-enhanced`)
2. ติดตั้ง **Java** (สำหรับ PlantUML) — ตรวจสอบด้วย `java -version`
3. เปิดไฟล์ `.md` ใน VS Code
4. กด `Ctrl+Shift+V` เพื่อเปิด preview
5. PlantUML, GraphViz, KaTeX, และ `@import` จะ render อัตโนมัติ

### MPE Features ที่ใช้

| Feature | หมายเหตุ |
|---------|---------|
| **PlantUML** (`puml`) | ต้องมี Java — ลูกศรเป็นเส้นตรงเหลี่ยม (`skinparam linetype ortho`) |
| **GraphViz** (`dot`) | Viz.js มากับ MPE — เส้นเป็นเหลี่ยม (`splines=ortho`) |
| **KaTeX** math (`$...$`) | built-in |
| **@import** | ดึงไฟล์โค้ด/config เข้ามา (path สัมพันธ์กับตำแหน่งไฟล์) |
| **Code chunks** (`{cmd=true}`) | ต้องเปิด `enableScriptExecution` |
| **Front-matter** | YAML metadata ทุกไฟล์ |

---

## สถานะเอกสาร

- **Verified** = สอบกับโค้ดแล้ว
- **Inferred** = อนุมานจากลักษณะของระบบ (ระบุในเอกสาร)
- **Assumed** = สมมติเพื่อให้เอกสารครบ (ระบุในเอกสาร)

เอกสารระบุชัดเจนว่าส่วนไหนที่ระบบทั่วไปมักมีแต่ **โค้ดจริงไม่มี** (เช่น REST API, classifier, human review queue อัตโนมัติ)

---

## อ้างอิงหลัก

| ไฟล์ | หน้าที่ |
|------|---------|
| `sam3_auto_label/src/config.py` | Config dataclasses + validation |
| `sam3_auto_label/src/inference.py` | SAM 3.1 inference + NMS + RLE |
| `sam3_auto_label/src/batch_segment.py` | Batch loop + checkpoint + ETA |
| `sam3_auto_label/src/exporters.py` | 11 export formats |
| `sam3_auto_label/src/tracker.py` | SQLite experiment tracking |
| `sam3_auto_label/config/ppe_6class.yaml` | Config จริง (6 คลาส) |
| `pipeline_cli.py` | Root CLI — 3 modes (sam/yolo/pred) |
| `yolo26_ppe/configs/production_train.yaml` | YOLO26 training config |
| `yolo26_ppe/configs/production_augmentation.yaml` | YOLO26 augmentation config |
| `yolo26_ppe/configs/mlflow.yaml` | MLflow config |
| `yolo26_ppe/reports/final/report.pdf` | รายงานฉบับสมบูรณ์ |
| `yolo26_ppe/reports/inputs/final_eval_results.json` | YOLO26 metrics |
| `yolo26_ppe/reports/metrics/comparison_report.md` | สรุปเปรียบเทียบ |
