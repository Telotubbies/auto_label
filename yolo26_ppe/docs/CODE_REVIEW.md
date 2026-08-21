# Code Review — `yolo26_ppe` (Enterprise Standard)

**Reviewer role**: QA / Data / AI (multi-role review)
**Date**: 2026-08-20
**Scope**: `yolo26_ppe/` ทั้ง pipeline (scripts, configs, shell, data flow, MLOps)
**Verdict**: ❌ **ยังไม่ผ่าน enterprise standard** — pipeline มี critical bugs ที่ทำให้ผลลัพธ์เชื่อถือไม่ได้ และ integration ระหว่าง step พังอยู่

---

## สรุปผลตามมิติ (Five-Axis)

| มิติ | เกรด | หมายเหตุ |
|------|------|----------|
| Correctness | ❌ Fail | Data leakage ใน split, evaluate/export หา best.pt ไม่เจอ, search space ใน tune ไม่ถูกใช้ |
| Readability | ⚠️ Pass- | โครงสร้าง step อ่านง่าย แต่ numbering ข้าม (ไม่มี 02), hardcode กระจาย |
| Architecture | ⚠️ Pass- | แยก step ชัดเจน แต่ config drift ระหว่าง yaml กับ code |
| Security | ⚠️ Warn | MLflow 0.0.0.0 ไม่มี auth, artifacts/weights เสี่ยง commit เข้า git |
| Performance | ⚠️ Warn | เมทริก inference_ms วัดผิดวิธี, oversampling 83x |
| Reproducibility / MLOps | ❌ Fail | ไม่มี tests/CI, requirements ขาด core deps, hardcode path เครื่อง |

---

## 🔴 CRITICAL — ต้องแก้ก่อนใช้ผลลัพธ์จริง

### C1. Data Leakage ใน train/val/test split
**ไฟล์**: `scripts/01_prepare_data.py` บรรทัด 132–134

```python
for split_name in ["train", "val", "test"]:
    splits[split_name] = split_imgs(images_2026)[split_name] + split_imgs(images_blurred)[split_name]
```

`split_imgs()` ถูกเรียก **6 ครั้ง** (2 sources × 3 splits) ทุกครั้ง `random.shuffle()` ต่อจาก RNG state เดิม และ shuffle in-place → แต่ละครั้งได้ permutation ต่างกัน

**ผลคือ**: รูปเดียวกันสามารถหลุดไปอยู่ทั้ง train และ test พร้อมกัน — **test set contaminated** เมทริก mAP ที่ได้จะ optimistic กว่าความจริง ใช้อ้างอิงในรายงานไม่ได้

**Fix**: split ครั้งเดียวต่อ source แล้วเก็บผลไว้:

```python
split_2026 = split_imgs(images_2026)
split_blurred = split_imgs(images_blurred)
for s in ["train", "val", "test"]:
    splits[s] = split_2026[s] + split_blurred[s]
```

และควรเขียน unit test ยืนยัน `set(train_ids) ∩ set(test_ids) == ∅`

---

### C2. Evaluate/Export/Compare หา `best.pt` ไม่เจอ — pipeline ขาดตอนกลาง
**ไฟล์**: `scripts/04_evaluate.py:40`, `scripts/07_export.py:33`, `scripts/03_train.py:33-36`

`03_train.py` ส่ง `project="yolo26_ppe/models/yolo26n_detect"` แต่ Ultralytics resolve เป็น relative path ใต้ `runs/detect/` — หลักฐานจาก `runs/detect/.../run1/args.yaml`:

```
project: yolo26_ppe/models/yolo26n_detect
save_dir: /mnt/e/02_Projects/auto_label/runs/detect/yolo26_ppe/models/yolo26n_detect/run1
```

**สถานะจริงตอนนี้**:
- ✅ best.pt อยู่ที่ `runs/detect/yolo26_ppe/models/yolo26n_detect/run1/weights/best.pt`
- ❌ `yolo26_ppe/models/*/` ว่างเปล่าทั้ง 4 โฟลเดอร์
- ❌ `reports/eval_all.json` ไม่มี → `04_evaluate.py`, `07_export.py` จะ print `ERROR: ... not found. Train first.` แล้วข้ามทั้งหมด

**Fix**: ส่ง absolute path ให้ `project` (เช่น `os.path.join(BASE, config["project"])`) หรือปรับทุก step ให้อ่านจาก `runs/` ให้ตรงกัน — ทางใดทางหนึ่ง ห้ามคนละทาง

---

### C3. `05_tune.py` ประกาศ search space แต่ไม่เคยส่งเข้า tuner
**ไฟล์**: `scripts/05_tune.py:55-74`

```python
tune_cfg = { "lr0": (1e-5, 1e-1), ... }   # ประกาศไว้
results = model.tune(data=..., **base_args)  # แต่ไม่ได้ส่ง space=tune_cfg
```

`tune_cfg` เป็น dead code — tuning จะรันด้วย default space ของ Ultralytics ต่างจากที่ comment/README อ้าง นอกจากนี้ `use_ray=False` ไม่ใช่ parameter มาตรฐานของ `model.tune()` — ถูกกลืนเข้า `**kwargs` เงียบๆ

**Fix**: ส่ง `space=tune_cfg` และตรวจ signature ของ `YOLO.tune()` ในเวอร์ชันที่ใช้จริง

---

### C4. เมทริก `inference_ms` วัดผิดวิธี (ทั้ง train และ eval)
**ไฟล์**: `scripts/03_train.py:126-133`, `scripts/04_evaluate.py:91-101`

```python
for _ in range(5):
    model.predict(source=test_dir, ...)   # predict ทั้งโฟลเดอร์ (~50 รูป)
metrics["inference_ms"] = (time.time() - t0) / 5 * 1000
```

นี่คือ **เวลาต่อการ predict ทั้ง test set 50 รูป** ไม่ใช่ต่อ 1 รูป — ตัวเลขที่ log เข้า MLflow จะใหญ่กว่าความจริง ~50 เท่า และจะเปรียบเทียบกับ SAM 3.1 (700ms/รูป) ใน `06_compare.py` แบบผิดหน่วย

**Fix**: `predict` ทีละรูป หรือหารด้วยจำนวนรูปจริง และควร warmup ก่อน time

---

### C5. `mlflow.log_param` ถูกเรียกนอก active run → หายเงียบๆ
**ไฟล์**: `scripts/03_train.py:93-106`

`mlflow.log_param(...)` ถูกเรียก **ก่อน** `model.train()` โดยไม่มี `mlflow.start_run()` — run ถูกสร้างโดย Ultralytics callback ภายหลัง → calls เหล่านี้ raise แล้วถูก `except` กลืน (print warning เท่านั้น) custom params ทั้งหมด (dataset_size, gpu, runtime, class_imbalance_ratio) **ไม่เคยถูก log จริง**

แถมค่าทั้งหมดเป็น hardcode (`480`, `335/95/50`, `"AMD RX 7800 XT"`) — เมื่อ dataset เปลี่ยน ค่าเหล่านี้จะกลายเป็น "ข้อมูลโกหก" ใน tracking

**Fix**: log ผ่าน callback หลัง train, หรือเปิด run เองด้วย `mlflow.start_run()` แล้วส่ง run_id ให้ Ultralytics และคำนวณค่าจาก `data_analysis.json` แทน hardcode

---

## 🟠 HIGH — ก่อน production

### H1. Config drift: `03_train.py` ไม่อ่าน `configs/train.yaml`
`03_train.py:42-74` hardcode `TRAIN_ARGS` เป็น dict ใน code ทั้งที่ `configs/train.yaml` + `configs/augmentation.yaml` มีอยู่และถูกใช้โดย `04/05/07` — ค่าไม่ตรงกัน เช่น `copy_paste: 0.1` (code) vs `0.15` (yaml), `shear: 2.0` มีใน yaml แต่ไม่มีใน code → แก้ yaml แล้วไม่มีผลกับ training, แก้ code แล้ว tune/eval ตามไม่ทัน **Single source of truth หาย**

**Fix**: `03_train.py` โหลด yaml เหมือน script อื่น แล้ว merge

### H2. `requirements.txt` ขาด core dependencies
ไม่มี `ultralytics` และ `mlflow` ใน `requirements.txt` ทั้งที่เป็น dependency หลักของ pipeline นี้ — setup เครื่องใหม่ล้มแน่ ไม่มี `check_setup.py` (เปิดค้างใน IDE แต่ไฟล์ไม่มีจริงใน `scripts/`)

### H3. Oversampling รุนแรง: sandals 4 → 333 (83x)
`data_analysis.json`: sandals มี 4 annotations จริง ถูก copy เป็น 333 — โมเดลจะ memorize รูปเดิม ไม่ generalize; person/helmet/shoes ถูก inflate ตามไปด้วย (side effect จากการ copy ทั้งรูป) ตัวเลข `imbalance_after: 10.5:1` จึงดูดีแต่เป็น "สมดุลเทียม" — ข้อมูล unique ไม่ได้เพิ่ม

**ข้อเสนอ**: พิจารณา copy_paste เฉพาะ instance (ทำอยู่แล้วใน aug), class-weighted loss, หรือเก็บข้อมูล sandals เพิ่ม — อย่า oversample ทั้งรูป 83 เท่า และต้องรายงาน unique-image count ควบคู่

### H4. ไม่มี tests / CI / lint gate
ไม่มี test แม้แต่ไฟล์เดียวสำหรับ pipeline นี้ (มี `pyrefly.toml` ที่ root แต่ไม่ได้บังคับใช้) — bug ระดับ C1/C2/C3 ทั้งหมดจับได้ง่ายๆ ด้วย smoke test: "รัน 01 แล้ว assert ไม่มี id ซ้ำข้าม split", "รัน train 1 epoch แล้ว assert eval หา best.pt เจอ"

### H5. `.gitignore` ไม่คลุม artifacts ใหญ่
`yolo26_ppe/` ทั้งโฟลเดอร์เป็น untracked (ดี) แต่ถ้า track จะดูด `data/` (รูปหลายร้อย MB), `mlflow/mlruns/`, `models/` เข้า git — น้ำหนัก `yolo26*.pt` 4 ไฟล์ (~60MB) ที่ root ก็ untracked แต่ไม่ได้ ignore — เสี่ยง commit เข้า repo โดยไม่ตั้งใจ ควร ignore `*.pt`, `yolo26_ppe/data/`, `yolo26_ppe/mlflow/`, `runs/`

---

## 🟡 MEDIUM

| # | เรื่อง | ไฟล์/บรรทัด | รายละเอียด |
|---|--------|-------------|------------|
| M1 | MLflow server ไม่มี auth + host 0.0.0.0 | `run_all.sh:21-24`, `start_mlflow.sh` | เปิดทุก interface ไม่มี authentication — โอเคสำหรับ local dev แต่ห้ามใช้ pattern นี้บนเครื่อง shared/prod; SQLite ถูกเขียนจาก server + Ultralytics client พร้อมกัน เสี่ยง `database is locked` |
| M2 | `wait $MLFLOW_PID` ท้าย script | `run_all.sh:69` | pipeline จบแล้วแต่ script ค้างถาวรเพราะรอ MLflow — ควร kill หลังจบ หรือแยก server ออกจาก pipeline |
| M3 | Path ติดเครื่อง | `run_all.sh:10-11`, `data.yaml` | hardcode `cd /mnt/e/...`, `PY=/opt/sam3_venv/bin/python`; `01_prepare_data.py:293` เขียน `os.path.abspath` ลง data.yaml → WSL ได้ `/mnt/e/...`, Windows ได้ `E:\...` — regenerate คนละ OS = พัง |
| M4 | Hardcoded SAM baseline + ข้อมูลไม่ตรง | `06_compare.py:41-60` | ตัวเลข 700ms/3.3GB hardcode; per-class count (person=2375, helmet=2846) **ไม่ตรงกับ `data_analysis.json` จริง** (2271, 2693) — report สร้างจากข้อมูล stale |
| M5 | Speed/accuracy rank ใน report เป็น hardcode | `06_compare.py:114-118` | rank "1 (fastest)" ฯลฯ พิมพ์ตายตัว ไม่ได้คำนวณจากผลจริง — ถ้าผล train เปลี่ยน report จะโกหก |
| M6 | Silent failures | `01:194-195`, `04:88-89,108-109` | รูป source หาย → `continue` เงียบ; metric extraction fail → `except: pass` — ต้องมีอย่างน้อย warning + count สรุปตอนจบ |
| M7 | Training run ปัจจุบันไม่จบ | `runs/.../results.csv` | หยุดที่ epoch 12–13 จาก 150 — `best.pt` ที่มีอยู่คือของงานที่ยังไม่ converged ห้ามเอาไป export/eval เพื่อตัดสินใจ production |
| M8 | `dynamic=True` กับ torchscript | `07_export.py:48` | dynamic axes ใช้ได้เฉพาะ ONNX; ไม่มี smoke test รัน exported model ทดสอบว่าโหลด+inference ได้จริง |

---

## 🔵 LOW / NIT

- Script numbering ข้าม `02` (มี 01,03,04,05,06,07) — สับสน; docstring ใน `03_train.py` เขียนว่า "Step 2" แต่ชื่อไฟล์ 03
- `run1` hardcode + `exist_ok=True` ทุก script — rerun ทับของเดิมไม่มี versioning นอก MLflow
- `CLASS_NAMES` ซ้ำใน 3 ไฟล์ (`01`, `04`, `06`) — ควรมาจาก config เดียว
- ใช้ `print` ล้วน ไม่มี `logging` module, log file เต็ม ANSI escape codes จาก progress bar (ดู `logs_n_detect.log` ยาก)
- `load_yolo_results()` มี `.replace('_detect','_detect')` ที่เป็น no-op (`06_compare.py:25`) — dead logic
- `06_compare.py` "Conclusion" เขียนล็อกผลลัพธ์ไว้ล่วงหน้า ("Best overall: yolo26s_seg") ก่อนมีผล eval จริง

---

## ✅ สิ่งที่ทำดี (ควรรักษาไว้)

1. แยก step เป็น scripts ชัดเจน มี README อธิบับ pipeline + quick start
2. มี stratified split ตาม source (แยก 2026/blurred) — แนวคิดถูก แม้ implementation มี bug (C1)
3. Augmentation config มีเหตุผลประกอบทุกตัว (`flipud: 0.0` พร้อม comment ว่า PPE ไม่ควรกลับหัว — ใส่ใจ domain)
4. ใช้ MLflow tracking + แยก experiment `yolo26_ppe_tune` สำหรับ tuning
5. Export หลาย format พร้อมบันทึก `export_info.json`
6. มี comparison report อัตโนมัติ — โครงดี แค่ต้องคำนวณจากข้อมูลจริง (M4/M5)

---

## แผนแก้ตามลำดับความสำคัญ

| Priority | งาน | Effort |
|----------|-----|--------|
| P0 | แก้ C1 (split leakage) → regenerate dataset → retrain | S |
| P0 | แก้ C2 (project path) ให้ทุก step ชี้ที่เดียวกัน | S |
| P0 | แก้ C5 (MLflow logging) + เอา hardcode params ออก | S |
| P1 | รวม config เป็น yaml เดียว (H1), เพิ่ม ultralytics/mlflow ใน requirements (H2) | S |
| P1 | แก้ C3, C4 (tune space + inference metric) | S |
| P1 | เขียน smoke test: split integrity + train 1 epoch → eval → export (H4) | M |
| P2 | ปรับ oversampling strategy (H3), คำนวณ report จากผลจริง (M4/M5) | M |
| P2 | อัปเดต .gitignore (H5), แยก MLflow server ออกจาก run_all.sh (M1/M2) | S |
| P3 | Retrain ให้จบ 150 epochs หลังแก้ P0–P1 แล้วค่อย eval/export/report | L |

**สรุป**: โครง pipeline มีดีไซน์ที่ดีในระดับแผน แต่ implementation ปัจจุบันมี data leakage และ integration ขาด — **ผลลัพธ์ชุดปัจจุบัน (ถ้ามี) ใช้อ้างอิงไม่ได้** แก้ P0 แล้ว retrain ใหม่ทั้งหมดก่อนตัดสินใจเรื่อง production
