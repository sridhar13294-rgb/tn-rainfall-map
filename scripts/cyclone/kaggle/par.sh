#!/bin/bash
# Run one copy of a past-storm driver per GPU (Kaggle T4 x2): par.sh SCRIPT LIB CONFIG OUTPREFIX
# Starts are staggered by 6 min so the two compiles (the host-memory peak) don't overlap; XLA constant folding is off
# (it copies the large spectral-transform matrices and blew the 30 GB host memory with two processes).
S=$1; LIB=$2; CFG=$3; OUT=$4; N=$(nvidia-smi -L 2>/dev/null | wc -l); [ "$N" -lt 1 ] && N=1
export XLA_FLAGS="--xla_disable_hlo_passes=constant_folding"
(while true; do echo "$(date -u +%H:%M) $(free -g | awk '/Mem/{print "ram used",$3,"of",$2,"GB"}')"; sleep 120; done) > ${OUT}_mem.log 2>&1 &
for i in $(seq 0 $((N-1))); do
  CUDA_VISIBLE_DEVICES=$i python -W ignore $S $LIB $CFG $i $N ${OUT}_$i.json > ${OUT}_$i.log 2>&1 &
  [ $i -lt $((N-1)) ] && sleep 360
done
wait $(jobs -p | tail -n +2); tail -5 ${OUT}_*.log; dmesg 2>/dev/null | grep -i kill | tail -3
