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
        for kw in ('get_overall_rainfall_date(', 'get_overall_rainfall', 'overall_rainfall'):
            for m in re.finditer(re.escape(kw), s):
                ctx = s[max(0, m.start() - 300): m.end() + 1500]
                ctx = re.sub(r'(pk|sk)\.[A-Za-z0-9._-]{20,}', '<KEY>', ctx); ctx = re.sub(r'(?i)(token|apikey|api_key|key)(["\']?\s*[:=]\s*["\'])[^"\']+', r'\1\2<KEY>', ctx)
                out.write(f'===== {f} :: {kw}\n{ctx}\n\n')
P
cd $W
for u in "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_rainfall/change/english/daily_data" "https://beta-tnsmart.rimes.int/index.php/Api_mobile/Api_rainfall/daily_data?date=2026-11-02"; do
  echo "== $u" >> $OUT/responses.txt; curl -s -m 60 -D - -o $OUT/body_$(echo $u | md5sum | cut -c1-6).txt "$u" | grep -iE "^HTTP|^location|^content-type" >> $OUT/responses.txt
done
for f in $OUT/body_*; do head -c 4000 $f > $f.t; mv $f.t $f; done
cat $OUT/responses.txt
