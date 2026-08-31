# Report Plan — 4 YOLO26 Models vs SAM 3.1 Comparison

## บทนำสำหรับทีม/บริษัท

เอกสารนี้เป็นแผนการทำรายงานเปรียบเทียบโมเดล 4 ตัว (YOLO26n/s detect + YOLO26n/s seg) กับ SAM 3.1 สำหรับส่งให้บริษัท โดยเน้นความกระชับ เข้าใจง่าย มีกราฟและสถิติที่อ่านได้ทันที

---

## Role ของแต่ละขั้นตอน

### Role 1: Data Collector (รวบรวมผล)
- รอทั้ง 4 โมเดลเทรนเสร็จ
- Evaluate บน test set เดียวกัน
- ดึง metrics จาก MLflow
- Benchmark SAM 3.1 บน test set เดียวกัน

### Role 2: Export Engineer (ส่งออกโมเดล)
- Export ONNX ทั้ง 4 โมเดล
- Benchmark inference speed (PT vs ONNX)
- Research GPU deployment formats:
  - **TensorRT** (NVIDIA GPU)
  - **OpenVINO** (Intel CPU/GPU/NPU)
  - **DirectML** (Windows GPU ทุกยี่ห้อ)
  - **MIGraphX** (AMD ROCm — แทน ROCm EP ที่ deprecated)
  - **CoreML** (macOS/iOS)
- วัดขนาดไฟล์, ความเร็ว, VRAM

### Role 3: Visualization Designer (ออกแบบกราฟ)
- **Radar/Spider chart**: เปรียบเทียบ 5 มิติ (P, R, F1, mAP50, mAP50-95) ทุกโมเดล
- **Bar chart**: mAP50 แต่ละคลาส (person, helmet, boots, shoes, harness)
- **Heatmap**: Confusion matrix แต่ละโมเดล
- **Bar chart**: Inference speed (ms) ทุกโมเดล + SAM 3.1
- **Bar chart**: Model size (MB) ทุกโมเดล + SAM 3.1
- **Trade-off scatter**: Accuracy vs Speed (แกน X=speed, Y=accuracy)
- **Box plot**: IoU distribution แต่ละคลาส

### Role 4: Statistician (สถิติ)
- Per-class precision, recall, F1
- Confusion matrix (class confusion)
- False positives, false negatives ต่อคลาส
- IoU distribution
- Statistical significance (ถ้ามีข้อมูลพอ)

### Role 5: Report Writer (เขียนรายงาน)
- ภาษาไทย เป็นธรรมชาติ ไม่เกร็ง
- โครงสร้างแบบ company technical report (ไม่ใช่ academic paper)
- เริ่มด้วย Executive Summary → ข้อแนะนำ → ผล → วิธีการ
- เน้นส่วนเปรียบเทียบ 4 โมเดล vs SAM 3.1
- กราฟและตารางแทรกในจุดที่เกี่ยวข้อง
- ใช้ XeLaTeX + TH Sarabun New

---

## โครงสร้าง Report (LaTeX)

```
1. หน้าปก (Title, ผู้จัดทำ, วันที่, บริษัท)
2. Executive Summary (1 หน้า — ข้อสรุปสำหรับผู้บริหาร)
   - โมเดลไหนดีที่สุดสำหรับ production
   - ความแม่น vs ความเร็ว trade-off
   - ข้อแนะนำการ deploy
3. บทนำ (0.5 หน้า)
   - ปัญหา PPE detection
   - เป้าหมาย: เปรียบเทียบ 4 YOLO + SAM 3.1
4. วิธีการ (1 หน้า — สั้นกระชับ)
   - Dataset: 913 ภาพ, 5 คลาส
   - Training: 300 epochs, SGD, imgsz=640
   - Evaluation: test set 92 ภาพ
5. ผลเปรียบเทียบ (3-4 หน้า — ใจกลางของ report)
   5.1 ตารางสรุป metrics ทั้งหมด
   5.2 Radar chart: 5 โมเดล × 5 metrics
   5.3 Bar chart: mAP50 ต่อคลาส
   5.4 Confusion matrix heatmap
   5.5 Inference speed comparison
   5.6 Model size comparison
   5.7 Trade-off scatter plot
6. ข้อแนะนำ Production (1 หน้า)
   - โมเดลไหนใช้ตอนไหน
   - ONNX deployment guide
   - GPU format สำหรับแต่ละ platform
7. ภาคผนวก
   - Hyperparameters
   - MLflow run IDs
   - ไฟล์โมเดล
```

---

## สิ่งที่ต้องรอ

- n_seg: epoch ~162/300 (อีก ~138 epochs)
- s_seg: epoch ~2/300 (อีก ~298 epochs)
- พอเสร็จทั้งคู่ → evaluate → export → visualize → write

## สิ่งที่ทำได้ตอนนี้ (ไม่ต้องรอ)

- Research ONNX GPU formats ✅ (ทำแล้ว)
- เตรียม LaTeX template
- เตรียม visualization scripts
- เตรียม report skeleton

---

## ONNX GPU Formats Research Summary

| Format | Hardware | ความเร็ว | ความยาก | หมายเหตุ |
|--------|----------|---------|--------|---------|
| **TensorRT** | NVIDIA GPU | เร็วสุด | กลาง | ต้อง build engine ต่อ GPU |
| **OpenVINO** | Intel CPU/GPU/NPU | เร็วมาก (CPU) | ง่าย | เหมาะ edge deployment |
| **DirectML** | Windows GPU ทุกยี่ห้อ | กลาง | ง่าย | รองรับ AMD + NVIDIA + Intel |
| **MIGraphX** | AMD ROCm | เร็ว | กลาง | แทน ROCm EP ที่ deprecated |
| **CoreML** | Apple | กลาง | ง่าย | macOS/iOS เท่านั้น |
| **ONNX Runtime CPU** | ทุก platform | ช้ากว่า | ง่ายสุด | fallback ทั่วไป |

### ข้อแนะนำสำหรับเรา
- บนเครื่องเรา (AMD ROCm): PyTorch โดยตรงเร็วสุด
- ส่งให้บริษัท (NVIDIA): TensorRT
- ส่งให้บริษัท (Intel): OpenVINO
- ส่งให้บริษัท (ไม่รู้ GPU): ONNX Runtime + DirectML
