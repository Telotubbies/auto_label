# Techniques to Improve YOLO26 Accuracy — Research Summary

Based on web research from Ultralytics docs, arxiv papers, and community discussions.

## Current Status
- n_detect: mAP50 = 0.712 (target: 0.85)
- s_detect: mAP50 = 0.808 (target: 0.85)
- n_seg: training (epoch ~126, mAP50 = 0.485)
- s_seg: not started

## Weak Classes
- boots: mAP50 = 0.475-0.593 (worst)
- shoes: mAP50 = 0.559-0.674
- harness: good on test (0.82-0.95) but few instances

---

## Techniques (ranked by expected impact for our case)

### Tier 1: High Impact — Data & Resolution

#### 1. Higher Resolution (imgsz 960 or 1280)
- **Why**: boots/shoes are small objects, lost at 640px
- **How**: `imgsz=960` (batch=4 to fit 16GB VRAM)
- **Expected**: +5-10% mAP50 for small classes
- **Cost**: 2-3x training time, more VRAM
- **Source**: Ultralytics tips, YOLOv5 issue #2103

#### 2. SAHI Sliced Inference (inference only, no retrain)
- **Why**: Detect small objects by slicing image into tiles
- **How**: `pip install sahi` + use at inference time
- **Expected**: +5-7% AP for small objects
- **Cost**: 2-3x inference time
- **Source**: arxiv 2202.06934, Ultralytics SAHI guide

#### 3. More Data for Rare Classes
- **Why**: boots/shoes have few instances (116/406 in test)
- **How**: 
  - Collect more from Roboflow, Open Images
  - Synthetic data generation
  - Copy-paste augmentation (paste boots/shoes onto new backgrounds)
- **Expected**: +10-15% mAP50 for rare classes
- **Source**: Ultralytics community, MDPI papers

#### 4. Copy-Paste Augmentation (increase from 0.1)
- **Why**: Creates new training examples by pasting objects onto backgrounds
- **How**: `copy_paste=0.3-0.5` (currently 0.1)
- **Expected**: +3-5% mAP50, especially for rare classes
- **Source**: Ultralytics Copy-Paste PR, CPA paper

### Tier 2: Medium Impact — Training & Augmentation

#### 5. Knowledge Distillation (s → n)
- **Why**: Train n model with s model as teacher
- **How**: `distill_model="yolo26s.pt"` when training yolo26n
- **Expected**: +0.6-1.0% mAP50-95 (COCO results)
- **Cost**: No inference cost increase
- **Source**: Ultralytics Knowledge Distillation guide

#### 6. Mosaic Augmentation (increase from 0.5)
- **Why**: YOLO26 official recipe uses 0.9-1.0
- **How**: `mosaic=0.9` (currently 0.5)
- **Expected**: +2-4% mAP50
- **Source**: YOLO26 training recipe docs

#### 7. Scale Augmentation (increase from 0.5)
- **Why**: YOLO26 official uses 0.9 for N, 0.56-0.95 for S
- **How**: `scale=0.9` (currently 0.5)
- **Expected**: +1-3% mAP50
- **Source**: YOLO26 training recipe

#### 8. Hyperparameter Tuning (genetic algorithm)
- **Why**: Automated search over lr, augmentation, loss weights
- **How**: `model.tune(data=..., epochs=50, iterations=300)`
- **Expected**: +2-5% mAP50
- **Cost**: Very expensive (300 short runs)
- **Source**: Ultralytics Tuner docs

#### 9. Focal Loss
- **Why**: Helps with class imbalance (boots/shoes rare)
- **How**: Not directly supported in YOLO26, but `cls_pw` (class positive weight) can be adjusted
- **Expected**: +1-3% for rare classes
- **Source**: Various papers

### Tier 3: Inference-Time (No Retrain)

#### 10. Test-Time Augmentation (TTA)
- **Why**: Flip + multi-scale at inference, average predictions
- **How**: `model.val(augment=True)` or `model.predict(augment=True)`
- **Expected**: +1-2% mAP50
- **Cost**: 2-3x inference time
- **Source**: Ultralytics TTA guide

#### 11. Model Ensembling
- **Why**: Combine n + s predictions
- **How**: Run both models, merge predictions with NMS
- **Expected**: +1-3% mAP50
- **Cost**: 2x inference time
- **Source**: Ultralytics ensembling guide

#### 12. Lower Confidence Threshold
- **Why**: Current default 0.25 may miss valid detections
- **How**: `conf=0.15` or `conf=0.1` at inference
- **Expected**: +5-10% recall, may reduce precision
- **Source**: Ultralytics evaluation guide

#### 13. Adjust IoU/NMS Threshold
- **Why**: Default IoU=0.45 may suppress valid overlapping detections
- **How**: `iou=0.5` or `iou=0.6` at inference
- **Expected**: +1-2% mAP50
- **Source**: Ultralytics community

### Tier 4: Architecture & Advanced

#### 14. P2 Model (small object head)
- **Why**: Adds P2 detection head for tiny objects (<8px)
- **How**: Use YOLO with P2 head variant
- **Expected**: +5-10% for small objects
- **Cost**: More parameters, slower
- **Source**: Ultralytics GitHub discussions

#### 15. Background Images (0-10%)
- **Why**: Reduce false positives
- **How**: Add ~50-90 background images (no labels) to training
- **Expected**: +1-2% precision
- **Source**: Ultralytics tips, COCO has 1% backgrounds

#### 16. Rectangular Inference
- **Why**: Preserve aspect ratio instead of square padding
- **How**: `rect=True` during validation
- **Expected**: +0.5-1% mAP50
- **Source**: Ultralytics evaluation guide

---

## Recommended Action Plan for Our Pipeline

### Phase 1: Quick Wins (no retrain)
1. TTA on existing s_detect → check if mAP50 > 0.85
2. Lower conf threshold to 0.15 → check recall improvement
3. SAHI sliced inference → check small object improvement

### Phase 2: Retrain with Better Config
4. imgsz=960, batch=4, mosaic=0.9, scale=0.9, copy_paste=0.3
5. Add background images (50-90 images)
6. Knowledge distillation: s → n

### Phase 3: Data Improvement
7. Collect more boots/shoes images (Roboflow, Open Images)
8. Copy-paste augmentation for rare classes
9. Hyperparameter tuning (50 trials)

### Phase 4: Advanced
10. Model ensembling (n + s)
11. P2 head for small objects
12. Custom loss weights for rare classes
