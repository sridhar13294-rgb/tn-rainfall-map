#!/bin/bash
# Tamil Nadu watch, one cycle: download the newest forecast file of each source from the era5-cases release
# into a work folder, run tn_watch.py, and keep the history in data/cyclone/tn_watch_history.json (cases branch).
# Usage: tn_watch_run.sh <workdir>   (run from the repo root, on the cases branch)
set -e
WORK=${1:-/tmp/tn_watch}; R=repos/sridhar13294-rgb/tn-rainfall-map; HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../../.." && pwd)
mkdir -p "$WORK/data"; rm -f "$WORK"/data/fc_*.npz
gh api "$R/releases/tags/era5-cases" -q '.assets[] | select(.name|test("^fc_")) | "\(.id) \(.name)"' > "$WORK/assets.txt"
for src in ENS GEFS HRES GFS; do
  line=$(grep " fc_${src}_" "$WORK/assets.txt" | sort -k2 | tail -1)
  [ -z "$line" ] && continue
  id=${line%% *}; name=${line#* }
  gh api -H 'Accept: application/octet-stream' "$R/releases/assets/$id" > "$WORK/data/$name"
done
[ -f "$ROOT/data/cyclone/tn_watch_history.json" ] && cp "$ROOT/data/cyclone/tn_watch_history.json" "$WORK/data/"
(cd "$WORK" && TZ=UTC python3 -W ignore "$HERE/tn_watch.py" .)
cp "$WORK/data/tn_watch_history.json" "$ROOT/data/cyclone/tn_watch_history.json"
