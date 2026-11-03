#!/bin/bash
# Usage: tnalert_probe.sh OUT_DIR - the app's 'Observed Rainfall' page (Api_rainfall/daily_data?date=) in full
OUT=$GITHUB_WORKSPACE/$1; mkdir -p $OUT/page; : > $OUT/responses.txt
for d in 2026-10-16 2026-10-30 2026-10-31 2026-11-01 2026-11-02 2026-11-03; do
  curl -s -m 90 -o $OUT/page/$d.html -w "daily_data $d -> %{http_code} %{size_download}\n" "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_rainfall/daily_data?date=$d" >> $OUT/responses.txt
done
cat $OUT/responses.txt
