#!/bin/bash
# Usage: tnalert_probe.sh OUT_DIR  - step 2: how the app calls its public rainfall endpoints, and what they return
OUT=$GITHUB_WORKSPACE/$1; mkdir -p $OUT; W=/tmp/tna; mkdir -p $W; cd $W
curl -sL "https://ws75.aptoide.com/api/7/app/getMeta/package_name=int_.rimes.tnsmart" > meta.json
APK=$(python3 -c "import json;print(json.load(open('meta.json'))['data']['file']['path'])"); curl -sL "$APK" -o app.apk
mkdir -p x && cd x && unzip -q -o ../app.apk
# context around the rainfall calls in the app's web code (keys removed)
python3 - "$OUT/calls.txt" <<'P'
import os, re, sys
out = open(sys.argv[1], 'w')
for root, _, files in os.walk('assets'):
    for f in files:
        if not f.endswith('.js'): continue
        s = open(os.path.join(root, f), errors='ignore').read()
        for kw in ('Api_rainfall', 'daily_reports', 'rainfall_analysis_', 'daily_srg_24hrs', 'daily_data'):
            for m in re.finditer(re.escape(kw), s):
                ctx = s[max(0, m.start() - 700): m.end() + 700]
                ctx = re.sub(r'(pk|sk)\.[A-Za-z0-9._-]{20,}', '<KEY>', ctx); ctx = re.sub(r'(?i)(token|apikey|api_key|key)(["\']?\s*[:=]\s*["\'])[^"\']+', r'\1\2<KEY>', ctx)
                out.write(f'===== {f} :: {kw}\n{ctx}\n\n')
P
cd $W
D=$(TZ=Asia/Kolkata date +%Y-%m-%d)
for u in "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_rainfall/daily_srg_24hrs" \
         "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_rainfall/change/english/daily_data"; do
  n=$(basename $u); curl -s -m 60 -o $OUT/get_$n.txt -w "GET $u -> %{http_code} %{size_download}\n" "$u" >> $OUT/responses.txt
  curl -s -m 60 -X POST -d "date=$D" -o $OUT/post_$n.txt -w "POST $u date=$D -> %{http_code} %{size_download}\n" "$u" >> $OUT/responses.txt
done
for d in 2026-10-31 2026-11-01 2026-11-02 2026-11-03 31-10-2026 01-11-2026; do
  curl -s -m 60 -o /dev/null -w "report $d -> %{http_code} %{content_type} %{size_download}\n" "https://beta-tnsmart.rimes.int/DATA/Rainfall/daily_reports/rainfall_analysis_$d.pdf" >> $OUT/responses.txt
done
for f in $OUT/get_* $OUT/post_*; do head -c 3000 $f > $f.tmp; mv $f.tmp $f; done
cat $OUT/responses.txt
