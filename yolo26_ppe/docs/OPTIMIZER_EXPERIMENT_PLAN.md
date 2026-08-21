# Optimizer Experiment Plan

## เป้าหมาย
เปรียบเทียบ optimizer 4 ตัวบนทุก model variant (n/s × detect/seg = 4 โมเดล)
เพื่อหา optimizer ที่ดีที่สุดสำหรับ dataset PPE ของเรา

## Versioning

```
v2 = SGD (current, กำลังรัน/เสร็จแล้ว)
v3 = AdamW
v4 = Adam
v5 = auto (Ultralytics ตัดสินใจเอง)
```

## Folder Structure

```
yolo26_ppe/models/
├── yolo26n_detect_v2_sgd/      # รันแล้ว
├── yolo26s_detect_v2_sgd/      # รันแล้ว
├── yolo26n_seg_v2_sgd/         # กำลังรัน
├── yolo26s_seg_v2_sgd/         # กำลังรัน
├── yolo26n_detect_v3_adamw/    # รอ
├── yolo26s_detect_v3_adamw/
├── yolo26n_seg_v3_adamw/
├── yolo26s_seg_v3_adamw/
├── yolo26n_detect_v4_adam/
├── yolo26s_detect_v4_adam/
├── yolo26n_seg_v4_adam/
├── yolo26s_seg_v4_adam/
├── yolo26n_detect_v5_auto/
├── yolo26s_detect_v5_auto/
├── yolo26n_seg_v5_auto/
└── yolo26s_seg_v5_auto/
```

## Optimizer Settings

### v2: SGD (current)
```python
optimizer = "SGD"
lr0 = 0.01
lrf = 0.01
momentum = 0.937
weight_decay = 0.0005
warmup_bias_lr = 0.1
```

### v3: AdamW
```python
optimizer = "AdamW"
lr0 = 0.001        # ต้องต่ำกว่า SGD 10x ไม่งั้น NaN
lrf = 0.01
momentum = 0.937   # beta1
weight_decay = 0.0005
warmup_bias_lr = 0.0   # ต้องเป็น 0 สำหรับ Adam family
```

### v4: Adam
```python
optimizer = "Adam"
lr0 = 0.001
lrf = 0.01
momentum = 0.937
weight_decay = 0.0005
warmup_bias_lr = 0.0
```

### v5: auto
```python
optimizer = "auto"
# Ultralytics จะเลือกเอง:
# - >10000 iterations → MuSGD (lr=0.01)
# - <10000 iterations → AdamW (lr_fit = 0.002 * 5 / (4 + nc))
# เรามี 729 images, batch 8, 300 epochs = ~27338 iterations → น่าจะเลือก MuSGD
```

## Evaluation Protocol

แต่ละ optimizer:
1. เทรน 300 epochs (เหมือนกันทุกอย่าง ยกเว้น optimizer)
2. Evaluate บน test set 92 ภาพ
3. Log ผลเข้า MLflow โดยใส่ tag `optimizer` และ `version`
4. เก็บ best.pt และ last.pt
5. เปรียบเทียบ mAP50, mAP50-95, P, R, F1

## Execution Order

1. รอ v2 (SGD) ทั้ง 4 โมเดลเสร็จ
2. Evaluate v2 ทั้ง 4 บน test set
3. เริ่ม v3 (AdamW) ทั้ง 4 — รันคู่ได้ (n_detect + s_detect คู่กัน, n_seg + s_seg คู่กัน)
4. รอ v3 เสร็จ → evaluate
5. เริ่ม v4 (Adam) ทั้ง 4
6. รอ v4 เสร็จ → evaluate
7. เริ่ม v5 (auto) ทั้ง 4
8. รอ v5 เสร็จ → evaluate
9. สร้างตารางเปรียบเทียบ optimizer × model
10. เลือก best optimizer สำหรับแต่ละ model
11. อัปเดต report

## VRAM Considerations

- detect models: batch 8 ใช้ ~3-4 GB
- seg models: batch 4 ใช้ ~4-5 GB
- รันคู่ detect + seg ได้ (~8-9 GB รวม, เหลือพอ)
- รัน 4 พร้อมกันอาจ OOM → รันทีละ 2 คู่

## MLflow Tags

แต่ละ run จะมี:
- `optimizer`: SGD / AdamW / Adam / auto
- `version`: v2 / v3 / v4 / v5
- `model_variant`: n_detect / s_detect / n_seg / s_seg
- `dataset`: ppe_v2
- `seed`: 42
