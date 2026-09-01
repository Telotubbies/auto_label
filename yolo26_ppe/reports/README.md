# yolo26_ppe/reports — รายงาย PDF

รายงายฉบับสมบูรณ์ภาษาไทย (XeLaTeX) สำหรับโปรเจกต์ YOLO26 PPE

## โครงสร้าง

```text
reports/
├── final/
│   └── report.pdf              # ← PDF สำเร็จ (79 หน้า) — ใช้ตัวนี้
├── source/
│   ├── report.tex              # LaTeX source
│   ├── report_plan.md          # โครงร่างรายงาน
│   ├── figures/                # กราฟ PDF/PNG (training curves, confusion matrix, Pareto)
│   └── fonts/
│       └── Sarabun-Regular.ttf # ฟอนต์ไทย
├── inputs/                     # JSON ที่ใช้สร้างรายงาน
│   ├── final_eval_results.json
│   ├── onnx_export_results.json
│   └── sam3_benchmark_results.json
├── metrics/                    # สรุป metrics ในรูปแบบต่างๆ
│   ├── comparison_report.md
│   ├── eval_all.json
│   ├── model_comparison.csv
│   ├── model_comparison.json
│   ├── train_v2_summary.json
│   └── tune_*.json             # ผล hyperparameter tuning แยกต่อโมเดล
└── build/                      # XeLaTeX intermediate files (.aux, .log, .toc)
```

## final/report.pdf

รายงายฉบับสมบูรณ์ 79 หน้า ภาษาไทย เนื้อหาครอบคลุม:

- ภาพรวมโปรเจกต์และ dataset
- การฝึก YOLO26 4 โมเดล
- ผล evaluation (P/R/F1/mAP50/mAP50-95)
- Confusion matrix แยกต่อโมเดล
- Per-class comparison
- ONNX vs PyTorch comparison
- Robustness test (ภาพเบลอ)
- SAM 3.1 benchmark
- Production recommendation

## วิธีสร้างใหม่

```bash
cd reports/source
xelatex report.tex
xelatex report.tex   # รัน 2 รอบเพื่อ cross-reference
mv report.pdf ../final/
```

หรือรันผ่าน pipeline: `scripts/pipeline/08_generate_report_figures.py`

## inputs/

JSON ที่เป็น input ของรายงาน — ดึงมาจาก `../artifacts/evaluation/` ถ้าข้อมูลเปลี่ยน ต้อง regenerate ก่อน build PDF

## metrics/

สรุป metrics ในรูปแบบที่อ่านง่าย:
- `comparison_report.md` — ตารางเปรียบเทียบโมเดล
- `model_comparison.csv` — สำหรับ Excel
- `tune_*.json` — ผล Ultralytics Tune แยกต่อโมเดล

## ข้อควรระวัง

- ต้องมี XeLaTeX สำหรับฟอนต์ไทย (Sarabun)
- อย่าแก้ `final/report.pdf` โดยตรง — แก้ `source/report.tex` แล้ว build ใหม่
- `build/` เป็น intermediate files — ลบได้ถ้าจะ build ใหม่
- ถ้าข้อมูลใน `inputs/` เปลี่ยน ต้อง rebuild PDF ไม่งั้นรายงานจะไม่ตรง
