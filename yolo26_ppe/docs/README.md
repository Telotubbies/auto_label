# yolo26_ppe/docs — Engineering Notes

เอกสารทางวิศวกรรม บันทึกการวิจัย และ code review

## ไฟล์

| ไฟล์ | เนื้อหา |
|------|--------|
| `accuracy_techniques.md` | เทคนิคพัฒนาความแม่นยำ YOLO26 (resolution, SAHI, augmentation) |
| `code_review.md` | บันทึก code review ของ pipeline |
| `optimizer_experiment_plan.md` | แผนทดลองเปรียบเทียบ optimizer |

## โครงสร้าง

```text
docs/
├── datasheets/        # (ว่าง — สำหรับ datasheet ในอนาคต)
├── model_cards/       # (ว่าง — สำหรับ model card ในอนาคต)
├── accuracy_techniques.md
├── code_review.md
└── optimizer_experiment_plan.md
```

## ข้อควรระวัง

- เอกสารที่อ้างอิงผลลัพธ์ ให้ตรวจกับ `../artifacts/evaluation/yolo/production_v4_recipe/` ก่อนใช้
- ถ้าทำการทดลองใหม่ บันทึกเป็นไฟล์ใหม่ในนี้
- อย่าลบเอกสารเก่า ถ้ายังอ้างอิงใน report หรือ code
