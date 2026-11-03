#!/bin/bash
# Usage: tnalert_probe.sh OUT_DIR - the app's 'Observed Rainfall' page for chosen dates (form POST date=YYYY-MM-DD)
OUT=$GITHUB_WORKSPACE/$1; rm -rf $OUT/page; mkdir -p $OUT/page; : > $OUT/responses.txt
for d in 2026-10-16 2026-10-28 2026-10-30 2026-10-31 2026-11-01 2026-11-02 2026-11-03; do
  curl -s -m 120 -F "date=$d" -F "submit=Submit" -o $OUT/page/$d.html -w "POST daily_data $d -> %{http_code} %{size_download}\n" "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_rainfall/daily_data" >> $OUT/responses.txt
done
cat $OUT/responses.txt
