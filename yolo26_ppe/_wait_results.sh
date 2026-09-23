#!/bin/bash
for i in 1 2 3 4 5 6 7 8; do
  sleep 30
  if [ -f /mnt/e/02_Projects/auto_label/yolo26_ppe/yolo26_ppe/models/production/small_detection/stage_2_final_fine_tuning/results.csv ]; then
    echo "FOUND results.csv"
    cat /mnt/e/02_Projects/auto_label/yolo26_ppe/yolo26_ppe/models/production/small_detection/stage_2_final_fine_tuning/results.csv
    break
  fi
  echo "check $i: no results.csv yet ($(date +%H:%M:%S))"
done
