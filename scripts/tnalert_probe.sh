#!/bin/bash
# Usage: tnalert_probe.sh OUT_DIR
OUT=$1; mkdir -p $OUT; W=/tmp/tna; mkdir -p $W; cd $W
curl -sL "https://ws75.aptoide.com/api/7/app/getMeta/package_name=int_.rimes.tnsmart" > meta.json
python3 -c "import json;d=json.load(open('meta.json'));f=d['data']['file'];print(f['path']);print(f.get('vername'),f.get('md5sum'))" > info.txt 2>&1
cat info.txt | tee $GITHUB_WORKSPACE/$OUT/apk_info.txt
APK=$(head -1 info.txt); curl -sL "$APK" -o app.apk; ls -la app.apk | tee -a $GITHUB_WORKSPACE/$OUT/apk_info.txt
mkdir -p x && cd x && unzip -q -o ../app.apk; ls | tee $GITHUB_WORKSPACE/$OUT/apk_files.txt
# all URLs in every file (dex, assets, js bundles, flutter libapp.so)
find . -type f -print0 | xargs -0 strings -n 8 2>/dev/null | head -c 400000000 | grep -oE "https?://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+" | sed -E 's/[?#].*$//' | grep -viE 'mapbox|token|key=' | sort | uniq -c | sort -rn > $GITHUB_WORKSPACE/$OUT/urls.txt   # no query strings: never store keys
find . -type f -print0 | xargs -0 strings -n 6 2>/dev/null | grep -iE "rain|gauge|station|api/|/MIS/|getdata|json" | grep -viE 'token|secret|key|pk\.|sk\.' | grep -E '^[ -~]{6,200}$' | grep -iE '/api|/MIS/|rainfall|raingauge' | sort -u | head -400 > $GITHUB_WORKSPACE/$OUT/keywords.txt
find . -type f \( -name "*.bundle" -o -name "*.js" -o -name "libapp.so" -o -name "*.json" \) | head -50 > $GITHUB_WORKSPACE/$OUT/code_files.txt
wc -l $GITHUB_WORKSPACE/$OUT/*.txt
