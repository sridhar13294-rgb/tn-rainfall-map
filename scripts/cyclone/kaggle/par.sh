#!/bin/bash
# Run one copy of a past-storm driver per GPU (Kaggle T4 x2): par.sh SCRIPT LIB CONFIG OUTPREFIX
S=$1; LIB=$2; CFG=$3; OUT=$4; N=$(nvidia-smi -L 2>/dev/null | wc -l); [ "$N" -lt 1 ] && N=1
for i in $(seq 0 $((N-1))); do
  CUDA_VISIBLE_DEVICES=$i python -W ignore $S $LIB $CFG $i $N ${OUT}_$i.json > ${OUT}_$i.log 2>&1 &
done
wait; tail -5 ${OUT}_*.log
