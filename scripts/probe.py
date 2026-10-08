"""One-off probe: does TN SMART's station page return past dates?"""
import json, sys, time, urllib.request, urllib.parse, re, uuid
sys.path.insert(0, 'scripts')
import update
URL = 'https://beta-tnsmart.rimes.int/index.php/MIS/Rainfall/raingauge_stations'
out = {}
def post(date, multipart=True):
    if multipart:
        b = uuid.uuid4().hex
        body = ''.join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n' for k, v in [('date_on', date), ('search_submit', 'View Data')]) + f'--{b}--\r\n'
        ct = f'multipart/form-data; boundary={b}'; data = body.encode()
    else:
        data = urllib.parse.urlencode({'date_on': date, 'search_submit': 'View Data'}).encode(); ct = 'application/x-www-form-urlencoded'
    req = urllib.request.Request(URL, data=data, headers={'User-Agent': 'Mozilla/5.0 (tn-rainfall-map daily update)', 'Content-Type': ct})
    t = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        page = r.read().decode('utf-8', 'replace')
    geo = json.load(open('data/geo.json'))
    districts = list(geo['d']) + list(update.ALIASES)
    try:
        d, rows = update.parse_page(page, districts)
    except Exception as e:
        return dict(err=str(e), len=len(page))
    v = [r['rain'] for r in rows if r['rain'] is not None]
    return dict(as_on=d, rows=len(rows), with_rain=len(v), wet=sum(1 for x in v if x > 0), total=round(sum(v), 1), max=max(v) if v else None,
                secs=round(time.time() - t, 1), len=len(page), cols=re.findall(r'<th[^>]*>([^<]{2,60})</th>', page)[:12])
for date, mp in [('2026-10-07', True), ('2026-09-15', True), ('2026-06-01', True), ('2026-01-15', True), ('2025-12-01', True), ('2026-09-15', False)]:
    try:
        out[f'{date} {"mp" if mp else "form"}'] = post(date, mp)
    except Exception as e:
        out[f'{date} {"mp" if mp else "form"}'] = str(e)
json.dump(out, open('data/probe.json', 'w'), indent=1); print(json.dumps(out, indent=1))
