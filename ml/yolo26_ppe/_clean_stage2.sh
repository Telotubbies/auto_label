#!/bin/bash
for m in medium_detection medium_segmentation small_detection small_segmentation; do
  rm -rf "/mnt/e/02_Projects/auto_label/yolo26_ppe/yolo26_ppe/models/production/$m/stage_2_final_fine_tuning"
  echo "Cleaned $m stage_2"
done
echo "All stage_2 dirs cleaned"
