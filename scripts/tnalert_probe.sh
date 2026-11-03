#!/bin/bash
# Usage: tnalert_probe.sh OUT_DIR - TN-ALERT public station rainfall (Api_common/get_overall_rainfall) + public daily report PDFs
OUT=$GITHUB_WORKSPACE/$1; mkdir -p $OUT/raw $OUT/pdf; : > $OUT/responses.txt
for d in $(python3 -c "import datetime as t;[print(t.date(2026,10,15)+t.timedelta(i)) for i in range(20)]"); do
  [ -s $OUT/raw/$d.json ] && [ "$d" \< "2026-10-30" ] && continue
  curl -s -m 90 -o $OUT/raw/$d.json -w "get_overall_rainfall $d -> %{http_code} %{size_download}\n" "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_common/get_overall_rainfall?date=$d" >> $OUT/responses.txt
  curl -s -m 90 -o $OUT/pdf/$d.pdf -w "report $d -> %{http_code} %{content_type} %{size_download}\n" "https://beta-tnsmart.rimes.int/DATA/Rainfall/daily_reports/rainfall_analysis_$d.pdf" >> $OUT/responses.txt
  file $OUT/pdf/$d.pdf | grep -q PDF || rm -f $OUT/pdf/$d.pdf
done
cat $OUT/responses.txt
