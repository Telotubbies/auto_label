#!/bin/bash
for i in $(seq 1 20); do
  sleep 30
  CSV="/mnt/e/02_Projects/auto_label/yolo26_ppe/yolo26_ppe/models/production/small_detection/stage_2_final_fine_tuning/results.csv"
  if [ -f "$CSV" ]; then
    echo "FOUND results.csv at check $i ($(date +%H:%M:%S))"
    cat "$CSV"
    break
  fi
  echo "check $i: no results.csv yet ($(date +%H:%M:%S))"
done
