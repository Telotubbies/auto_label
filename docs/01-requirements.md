---
title: "01 — Requirements"
category: "SAM 3.1 Auto-Labeling"
order: 1
status: "Verified"
---

# 01 — Requirements

> ความต้องการของระบบ — hardware, software, dependencies
>
> **Status**: Verified — สอบกับ `setup.py`, `requirements.txt`, `Dockerfile`

---

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | ไม่บังคับ (CPU ได้) | NVIDIA 8GB+ VRAM หรือ AMD ROCm 16GB+ |
| RAM | 8 GB | 16 GB+ |
| Disk | 5 GB (model 3.34 GB + deps) | 10 GB+ (รวม output) |
| OS | Linux, Windows (WSL2), macOS | Linux/WSL2 (ROCm) |

### GPU ที่รองรับ

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam rectangle {
  BackgroundColor #E8F0FE
  BorderColor #4285F4
}

rectangle "NVIDIA" as nvidia {
  rectangle "CUDA 12.1" as cuda
}
rectangle "AMD" as amd {
  rectangle "ROCm 6.1" as rocm
}
rectangle "Apple" as apple {
  rectangle "MPS" as mps
}
rectangle "Any" as any {
  rectangle "CPU\n(ช้ามาก)" as cpu
}

nvidia --> cuda : torch==2.5.1+cu121
amd --> rocm : torch==2.5.1+rocm6.1
apple --> mps : torch==2.5.1 (PyPI)
any --> cpu : torch==2.5.1+cpu
@enduml
```

> ที่มา: `setup.py:95-178`, `Dockerfile:1-77`

---

## Software Requirements

| Software | Version | ที่มา |
|----------|---------|-------|
| Python | 3.12 | `Dockerfile`, `setup.py` |
| PyTorch | 2.5.1 | `setup.py` (ติดตั้งแยกตาม GPU) |
| torchvision | 0.20.1 | `setup.py` |
| Git | ใด ๆ | `tracker.py` เรียก `git rev-parse` |

---

## Python Dependencies

### `requirements.txt` (non-torch)

@import "../sam3_auto_label/requirements.txt" {title="requirements.txt"}

> PyTorch ถูกติดตั้งแยกจาก `requirements.txt` เพราะต้องเลือก index URL ตาม GPU

### Vendored SAM 3.1

- โฟลเดอร์ `sam3/` คือ source code ของ SAM 3.1 ที่ vendored ไว้ใน repo
- **ห้ามแก้** (`README.md:73`)
- import เป็น `sam3.model_builder`, `sam3.model.sam3_image_processor`, `sam3.eval.postprocessors`, `sam3.perflib.*`

### Parent repo CLI (`pipeline_cli.py`)

| Package | หน้าที่ |
|---------|---------|
| `questionary` | interactive prompts |
| `rich` | terminal formatting |

> ไม่อยู่ใน `sam3_auto_label/requirements.txt` — ติดตั้งใน venv ระดับ repo root

---

## Model Checkpoint

| รายการ | ค่า |
|--------|-----|
| Checkpoint | `sam3.1_multiplex.pt` |
| ขนาด | $3340 \text{ MB} \approx 3.34 \text{ GB}$ |
| URL | `https://huggingface.co/facebook/sam3.1/resolve/main/sam3.1_multiplex.pt` |
| ที่เก็บ (runtime) | `sam3_auto_label/checkpoints/sam3.1_multiplex.pt` |

> **⚠️ Known issue**: `setup.py:35` ดาวน์โหลดไป `models/sam3/` แต่ `config.py:112-113` มองหาที่ `checkpoints/` — ต้องย้ายไฟล์หรือ symlink ด้วยตนเองหลัง setup

---

## ข้อกำหนดเชิงฟังก์ชัน (Functional Requirements)

### RQ1 — SAM 3.1 Auto-Labeling

| ID | ข้อกำหนด | สถานะ |
|----|---------|-------|
| FR-01 | รัน batch segmentation บนโฟลเดอร์ภาพ | ✅ |
| FR-02 | รองรับ text prompt หลายคลาส | ✅ (6 คลาส) |
| FR-03 | สร้าง bounding box + segmentation mask | ✅ |
| FR-04 | Export 11 ฟอร์แมต | ✅ |
| FR-05 | Checkpoint/resume | ✅ |
| FR-06 | Experiment tracking | ✅ (SQLite) |
| FR-07 | Visualization overlay | ✅ |
| FR-08 | GPU auto-detect | ✅ |

### RQ2 — YOLO26 Training

| ID | ข้อกำหนด | สถานะ |
|----|---------|-------|
| FR-10 | เทรน YOLO26 4 รุ่น (n/s detect + n/s seg) | ✅ (300 epochs) |
| FR-11 | Dataset preparation จาก ground truth | ✅ (v1, v2) |
| FR-12 | MLflow experiment tracking | ✅ |
| FR-13 | Hyperparameter tuning | ✅ (3 trials × 4 models) |
| FR-14 | ONNX export | ✅ |
| FR-15 | รายงานเปรียบเทียบ (PDF) | ✅ (`report.pdf`) |
| FR-16 | Class balancing (oversampling) | ✅ (sandals, harness) |

### RQ3 — Ground Truth Generation

| ID | ข้อกำหนด | สถานะ |
|----|---------|-------|
| FR-20 | สร้าง ground truth จาก SAM 3.1 output | ✅ |
| FR-21 | Human verification | ✅ (manual) |
| FR-22 | Dataset versioning | ✅ (v1, v2 ใน `yolo26_ppe/data/`) |
| FR-23 | Train/val/test split | ✅ (335/95/50) |

### ไม่ได้ทำ

| ID | ข้อกำหนด | สถานะ |
|----|---------|-------|
| FR-30 | REST API | ❌ ไม่มีในโค้ด |
| FR-31 | Human review queue อัตโนมัติ | ❌ ทำ manual |
| FR-32 | Multi-model agreement (ensemble) | ❌ เปรียบเทียบในรายงานเท่านั้น |
| FR-33 | mAP50 ≥ 0.85 target | ❌ ไม่บรรลุ (dataset จำกัด) |

## ข้อกำหนดเชิงไม่ใช่ฟังก์ชัน (Non-functional)

### RQ1 — SAM 3.1

| ID | ข้อกำหนด | สถานะ |
|----|---------|-------|
| NFR-01 | throughput $\geq 0.3$ FPS บน GPU | ✅ (~0.36 FPS บน test set) |
| NFR-02 | รันได้บน CPU (ช้า) | ✅ |
| NFR-03 | ไม่เสียข้อมูลเมื่อคอมดับ | ✅ (checkpoint) |
| NFR-04 | reproducible config | ✅ (config_hash) |
| NFR-05 | retry ภาพที่ล้มเหลว | ❌ ไม่มี |
| NFR-06 | GPU OOM recovery | ❌ ไม่มี |

### RQ2 — YOLO26

| ID | ข้อกำหนด | สถานะ |
|----|---------|-------|
| NFR-10 | Training reproducible (seed=42) | ✅ |
| NFR-11 | Inference $\leq 35$ ms ทุกโมเดล | ✅ (30.8–33.8 ms) |
| NFR-12 | Model size $\leq 50$ MB | ✅ (10–42 MB) |
| NFR-13 | ONNX export สำหรับ deployment | ✅ |
| NFR-14 | mAP50 ≥ 0.85 | ❌ สูงสุด 0.808 (s_detect) |

---

## YOLO26 Training Hardware

| Component | ค่าที่ใช้ |
|-----------|---------|
| GPU | AMD RX 7800 XT (ROCm, WSL2) |
| Framework | Ultralytics YOLO26 + PyTorch 2.5.1+rocm6.1 |
| Epochs | 300 (detect), 150+50 (seg — 2 stage) |
| Batch size | 8 (detect), 4 (seg) |
| Image size | 640 px |
| Optimizer | SGD (lr0=0.01, lrf=0.01 cosine) |
| Freeze | 10 (backbone frozen) |

> ที่มา: `yolo26_ppe/reports/source/report.tex:652-677`

---

## อ้างอิง

- `sam3_auto_label/requirements.txt:1-23`
- `sam3_auto_label/setup.py:1-405`
- `sam3_auto_label/Dockerfile:1-77`
- `yolo26_ppe/reports/inputs/sam3_benchmark_results.json` — SAM 3.1 benchmark
- `yolo26_ppe/reports/inputs/final_eval_results.json` — YOLO26 metrics
- `yolo26_ppe/reports/source/report.tex:652-677` — training config
- `yolo26_ppe/configs/production_train.yaml` — training config file
