#!/bin/bash
# Usage: tnalert_probe.sh OUT_DIR - fetch the TN-ALERT app's public station rainfall (Api_common/get_overall_rainfall) for given days
OUT=$GITHUB_WORKSPACE/$1; mkdir -p $OUT/raw; : > $OUT/responses.txt
for d in 2026-10-30 2026-10-31 2026-11-01 2026-11-02 2026-11-03; do
  curl -s -m 90 -o $OUT/raw/$d.json -w "get_overall_rainfall $d -> %{http_code} %{content_type} %{size_download}\n" "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_common/get_overall_rainfall?date=$d" >> $OUT/responses.txt
done
cat $OUT/responses.txt
