---
title: "16 — Testing"
category: "SAM 3.1 Auto-Labeling"
order: 16
status: "Verified"
---

# 16 — Testing

> การทดสอบ — สิ่งที่มีและสิ่งที่ขาด
>
> **Status**: Verified — สอบกับ `tests/` ที่ repo root
>
> **⚠️ ไม่มี unit test สำหรับ `sam3_auto_label/src/` โดยตรง**

---

## การทดสอบที่มีจริง

### Tests สำหรับ `pipeline_cli.py` (repo root)

| File | ครอบคลุม | ที่มา |
|------|---------|------|
| `tests/conftest.py` | fixtures: load `pipeline_cli.py`, mock args, tmp `data/raw/` | `tests/README.md:7-15` |
| `tests/test_pipeline_cli_unit.py` | unit tests สำหรับ CLI functions | เดียวกัน |
| `tests/test_pipeline_cli_comprehensive.py` | full branch coverage ของ CLI logic | เดียวกัน |
| `tests/test_pipeline_cli_advanced.py` | edge cases / advanced features | เดียวกัน |
| `tests/test_pipeline_cli_uat.py` | user-acceptance simulation | เดียวกัน |
| `tests/test_dry_run_integration.py` | end-to-end dry-run integration | เดียวกัน |
| `tests/test_prepare_dataset.py` | prepare-dataset step integration | เดียวกัน |

### Tests สำหรับ YOLO (`yolo26_ppe/tests/`)

| File | ครอบคลุม |
|------|---------|
| `yolo26_ppe/tests/test_dataset_artifacts.py` | dataset artifact validation |
| `yolo26_ppe/tests/test_split_integrity.py` | train/val/test split integrity |

---

## การทดสอบที่ไม่มี

```plantuml {align="center"}
@startuml
!theme plain
skinparam linetype ortho
skinparam backgroundColor #FEFEFE
skinparam package {
  BorderColor #34A853
  BackgroundColor #F0F8F0
}
skinparam package "ไม่มี" {
  BorderColor #EA4335
  BackgroundColor #FCE8E6
}

package "มีจริง" {
  [CLI unit tests\npipeline_cli.py]
  [CLI integration tests\ndry-run]
  [YOLO dataset tests]
}

package "ไม่มี" {
  [config.py unit tests]
  [inference.py unit tests]
  [batch_segment.py unit tests]
  [exporters.py unit tests]
  [tracker.py unit tests]
  [SAM 3.1 inference test]
  [NMS test]
  [RLE encode/decode test]
  [Export format test]
  [End-to-end pipeline test\nwith real model]
  [Performance test]
  [Security test]
}
@enduml
```

| Test Type | สถานะ | หมายเหตุ |
|-----------|-------|---------|
| Unit test `config.py` | ❌ | ไม่มี test สำหรับ validation logic |
| Unit test `inference.py` | ❌ | ไม่มี test สำหรับ segment_image, NMS, RLE |
| Unit test `batch_segment.py` | ❌ | ไม่มี test สำหรับ checkpoint, ETA |
| Unit test `exporters.py` | ❌ | ไม่มี test สำหรับ 11 export formats |
| Unit test `tracker.py` | ❌ | ไม่มี test สำหรับ SQLite operations |
| Integration test (SAM + export) | ❌ | ไม่มี end-to-end test ที่ใช้ model จริง |
| Performance test | ❌ | มี benchmark แต่ไม่ใช่ automated test |
| Regression test | ❌ | ไม่มี |

---

## สิ่งที่ระบบทั่วไปมักมี

| Test ทั่วไป | สถานะ |
|---------------|-------|
| `test_mask_processor()` | ❌ ไม่มี (ไม่มี class นี้ด้วย) |
| `test_confidence_scorer()` | ❌ ไม่มี |
| `test_sam_inference()` | ❌ ไม่มี |
| `test_annotation_export()` | ❌ ไม่มี |
| `test_end_to_end_pipeline()` | ❌ ไม่มี (มี dry-run แต่ไม่ได้รัน inference จริง) |

---

## วิธีรัน test ที่มี

```bash {cmd=true output="text"}
# แสดงคำสั่งสำหรับรัน test
echo "=== Run tests ==="
echo "cd E:\\02_Projects\\auto_label"
echo "python -m pytest tests/ -v"
echo ""
echo "=== Run specific test ==="
echo "python -m pytest tests/test_dry_run_integration.py -v"
```

> **หมายเหตุ**: tests ใช้ `pytest` — ตรวจสอบว่าติดตั้งแล้ว (`pip install pytest`)

---

## ความเสี่ยงด้าน Testing

| ความเสี่ยง | ระดับ | หมายเหตุ |
|-----------|-------|---------|
| เปลี่ยน `config.py` validation แล้วไม่รู้ว่าพัง | สูง | ไม่มี unit test |
| เปลี่ยน `exporters.py` format แล้ว output ผิด | สูง | ไม่มี test สำหรับ 11 formats |
| เปลี่ยน NMS logic แล้ว detection ต่างจากเดิม | สูง | ไม่มี regression test |
| `tracker.py` SQLite schema เปลี่ยน | กลาง | ไม่มี migration test |

---

## อ้างอิง

- `tests/README.md:7-15` — test descriptions
- `tests/conftest.py` — fixtures
- `yolo26_ppe/tests/` — YOLO tests
