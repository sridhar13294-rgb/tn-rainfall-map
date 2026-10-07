"""Daily update for the Tamil Nadu Rainfall Grid Map.

1. Downloads TN SMART's station-wise rainfall page (station name, district, lat/lon, today's rain).
2. Saves that day's rainfall to data/daily/YYYY-MM-DD.json and station positions to data/stations.json.
3. Matches the monthly-report stations (data/baseline.json) to TN SMART stations to give them real GPS.
4. Adds daily rain after the report's sync date to each station's monthly totals.
5. Interpolates a 0.1 degree grid (inverse distance) and writes site/index.html.

If TN SMART can't be reached, the map is rebuilt from the data already saved and the problem is
written to data/status.json, so a failed day never breaks the site.
"""
import datetime as dt, difflib, html, json, math, os, re, statistics, sys, time, urllib.request
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
URL = 'https://beta-tnsmart.rimes.int/index.php/MIS/Rainfall/raingauge_stations/'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(obj, f, ensure_ascii=False, indent=None if compact else 1, separators=(',', ':') if compact else None)


# ---------------------------------------------------------------- TN SMART page
class Rows(HTMLParser):
    """Collects every table row as a list of (cell text, [hrefs])."""
    def __init__(self):
        super().__init__(); self.rows = []; self.row = None; self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = ['', []]
        elif tag == 'a' and self.cell is not None:
            self.cell[1].append(dict(attrs).get('href', ''))
        elif tag == 'br' and self.cell is not None:
            self.cell[0] += ' | '

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append((re.sub(r'\s+', ' ', self.cell[0]).strip(), self.cell[1])); self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.row:
                self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell[0] += data


def fetch(url):
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (tn-rainfall-map daily update)'})
            with urllib.request.urlopen(req, timeout=90) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:  # network hiccups: retry with back-off
            last = e; time.sleep(15 * (attempt + 1))
    raise RuntimeError(f'could not download {url}: {last}')


def num(s):
    try:
        return float(s.replace(',', ''))
    except ValueError:
        return None


def parse_page(page, districts):
    m = re.search(r'as on\s*(\d{4}-\d{2}-\d{2})', page)
    date = m.group(1) if m else None
    p = Rows(); p.feed(page)
    out, cols = [], {}
    for row in p.rows:
        texts = [html.unescape(t) for t, _ in row]
        low = [t.lower() for t in texts]
        if any('name of the station' in t for t in low):
            cols = {'name': next(i for i, t in enumerate(low) if 'name of the station' in t),
                    'district': next((i for i, t in enumerate(low) if t.startswith('district')), None)}
            continue
        hrefs = [h for _, hs in row for h in hs]
        sid = next((re.search(r'add_stations/(\d+)', h).group(1) for h in hrefs if 'add_stations/' in h), None)
        nums = [(i, num(t)) for i, t in enumerate(texts)]
        lat = next(((i, v) for i, v in nums if v is not None and 7.5 < v < 14.0 and '.' in texts[i]), None)
        lon = next(((i, v) for i, v in nums if v is not None and 75.5 < v < 81.0 and lat and i > lat[0]), None)
        if not lat or not lon:
            continue
        rain = next((v for i, v in reversed(nums) if v is not None and i > lon[0]), None)
        if cols and len(texts) > max(c for c in cols.values() if c is not None):
            name = texts[cols['name']]
            dcell = texts[cols['district']] if cols['district'] is not None else ''
        else:
            dcell = next((t for t in texts if any(t.startswith(d) for d in districts)), '')
            name = next((t for t in texts if t and num(t) is None and t != dcell and not re.fullmatch(r'[\d\-/ :]+', t)), '')
        district = next((d for d in sorted(districts, key=len, reverse=True) if dcell.lower().startswith(d.lower())), None)
        parts = [x.strip() for x in dcell.split('|')]
        out.append({'id': sid or f'{district}:{name}', 'name': name.strip(' .'), 'district': district,
                    'taluk': parts[1] if len(parts) > 1 else '', 'lat': lat[1], 'lon': lon[1], 'rain': rain})
    return date, out


# TN SMART spells some districts differently from the monthly report
ALIASES = {'Kanyakumari': 'Kanniyakumari', 'Tiruchirappalli': 'Thiruchirappalli', 'Trichy': 'Thiruchirappalli',
           'Tiruvarur': 'Thiruvarur', 'Thiruvallur': 'Tiruvallur', 'Tuticorin': 'Thoothukudi', 'The Nilgiris': 'Nilgiris',
           'Kanchipuram': 'Kancheepuram', 'Viluppuram': 'Villupuram', 'Thirupathur': 'Tirupathur', 'Tirupattur': 'Tirupathur',
           'Sivaganga': 'Sivagangai', 'Thiruvannamalai': 'Tiruvannamalai', 'Tirunelveli ': 'Tirunelveli'}


# ---------------------------------------------------------------- name matching
STOP = {'taluk', 'office', 'pwd', 'aws', 'arg', 'tndrra', 'rtff', 'vao', 'the', 'of', 'and', 'tk', 'to', 'gcc', 'pal',
        'basl', 'dscl', 'rscl', 'corporation', 'park', 'w', 'z'}


def canon(w):
    """Collapse common Tamil-name spelling variants: Thondi/Tondi, Mimisal/Meemisal, Pettai/Pet."""
    w = w.replace('pettai', 'pet').replace('patti', 'pati').replace('th', 't').replace('dh', 'd').replace('zh', 'l')
    w = w.replace('ee', 'i').replace('oo', 'u').replace('aa', 'a').replace('w', 'v').replace('y', 'i').replace('g', 'k')
    return re.sub(r'(.)\1+', r'\1', w)


def norm(name):
    n = name.lower()
    n = re.sub(r'_\d+$', '', n)
    n = re.sub(r'[^a-z ]', ' ', n)
    return [canon(w) for w in n.split() if w not in STOP and len(w) > 1]


def score(report_name, tn_name):
    a, b = norm(report_name), norm(tn_name)
    if not a or not b:
        return 0.0
    r = difflib.SequenceMatcher(None, ' '.join(a), ' '.join(b)).ratio()
    # every word of the report name found in the TN SMART name, e.g. "Andimadam" in "Taluk Office, Andimadam".
    # Not the other way round: "Kodaikanal Perumalmalai" is a different place from the "Kodaikanal" gauge.
    hit = sum(any(difflib.SequenceMatcher(None, w, x).ratio() >= .925 for x in b) for w in a) / len(a)
    return max(r, .97 if hit == 1 else 0)


def match(baseline, stations, overrides):
    by_d = {}
    for s in stations.values():
        by_d.setdefault(s['district'], []).append(s)
    res = []
    for b in baseline:
        key = f"{b['district']}|{b['station']}"
        if key in overrides:
            res.append((overrides[key] or None, 1.0, 'manual')); continue
        best = max(((score(b['station'], s['name']), s['id']) for s in by_d.get(b['district'], [])), default=(0, None))
        res.append((best[1], best[0], 'auto') if best[0] >= 0.925 else (None, best[0], 'none'))
    return res


# ---------------------------------------------------------------- grid
def km(lo1, la1, lo2, la2):
    return math.hypot((lo1 - lo2) * math.cos(math.radians((la1 + la2) / 2)), la1 - la2) * 111.2


def main():
    status = {'run_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}
    geo = load(P('data/geo.json'), None)
    base = load(P('data/baseline.json'), None)
    districts = geo['d']
    stations = load(P('data/stations.json'), {})
    overrides = load(P('data/match_overrides.json'), {})

    # 1-2. today's TN SMART page
    try:
        page = open(os.environ['TNSMART_HTML']).read() if os.environ.get('TNSMART_HTML') else fetch(URL)
        os.makedirs(P('data/raw'), exist_ok=True)
        open(P('data/raw/latest.html'), 'w').write(page)
        date, rows = parse_page(page, districts + list(ALIASES))
        for r in rows:
            r['district'] = ALIASES.get(r['district'], r['district'])
        status.update(page_date=date, rows_on_page=len(rows), rows_with_rain=sum(r['rain'] is not None for r in rows))
        if not rows:
            raise RuntimeError('page downloaded but no station rows recognised (layout may have changed)')
        for r in rows:
            stations[r['id']] = {k: r[k] for k in ('id', 'name', 'district', 'taluk', 'lat', 'lon')}
        if date:
            save(P('data/daily', date + '.json'), {r['id']: r['rain'] for r in rows if r['rain'] is not None})
        save(P('data/stations.json'), stations)
        status['tnsmart'] = 'ok'
    except Exception as e:
        status['tnsmart'] = f'FAILED: {e}'
        print('TN SMART step failed:', e, file=sys.stderr)

    # 3. give monthly-report stations real coordinates
    sync = dt.date.fromisoformat(base['synced_till'])
    year = sync.year
    matches = match(base['stations'], stations, overrides)
    save(P('data/match_report.json'), [{'district': b['district'], 'station': b['station'], 'tnsmart_id': m[0],
          'tnsmart_name': stations.get(m[0], {}).get('name') if m[0] else None, 'score': round(m[1], 2), 'how': m[2]}
          for b, m in zip(base['stations'], matches)])

    # 4. monthly series per gauge
    daily = {}
    if os.path.isdir(P('data/daily')):
        for f in sorted(os.listdir(P('data/daily'))):
            d = dt.date.fromisoformat(f[:10])
            if d > sync and d.year == year:
                daily[d] = load(P('data/daily', f), {})
    last = max([sync] + list(daily))
    nm = last.month
    first_daily = min(daily) if daily else None

    def add_daily(series, sid):
        for d, vals in daily.items():
            if sid in vals and series[d.month - 1] is not None:
                series[d.month - 1] += vals[sid]

    # cell-centre centroid of each district, for report stations without GPS
    cen = {}
    for lo, la, di in geo['cells']:
        cen.setdefault(di, []).append((lo + .05, la + .05))
    cen = {districts[k]: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)) for k, v in cen.items()}

    gauges, used = [], set()
    for b, (sid, sc, how) in zip(base['stations'], matches):
        series = [round(x, 1) for x in b['m'][:nm]]
        if sid and sid in stations:
            s = stations[sid]; used.add(sid)
            add_daily(series, sid)
            gauges.append(dict(name=b['station'], district=b['district'], lon=s['lon'], lat=s['lat'], gps=1, m=series))
        else:
            # no GPS: unknown position and no daily feed, so months after the report are unknown
            if last > sync:
                for k in range(sync.month - 1, nm):
                    series[k] = None
            gauges.append(dict(name=b['station'], district=b['district'], lon=None, lat=None, gps=0, m=series))
    for sid, s in stations.items():   # TN SMART gauges not in the monthly report: only whole months after first daily record
        if sid in used or s['district'] not in districts:
            continue
        series = [None] * nm
        for k in range(nm):
            if first_daily and dt.date(year, k + 1, 1) >= first_daily:
                series[k] = 0.0
        add_daily(series, sid)
        if any(v is not None for v in series):
            gauges.append(dict(name=s['name'], district=s['district'], lon=s['lon'], lat=s['lat'], gps=1, m=series))

    # spread no-GPS gauges around their district centre (only used where a district has few GPS gauges)
    nogps = {}
    for g in gauges:
        if not g['gps']:
            nogps.setdefault(g['district'], []).append(g)
    for d, L in nogps.items():
        c = cen.get(d, (78.5, 11))
        for i, g in enumerate(sorted(L, key=lambda g: g['name'])):
            r, a = .3 * math.sqrt((i + .5) / len(L)), i * 2.39996
            g['lon'], g['lat'] = c[0] + r * math.cos(a) / .98, c[1] + r * math.sin(a)

    # an exact 0 mm month while the district's median gauge had 20+ mm means the gauge wasn't reporting
    # (newly installed "_2" gauges, ARG gaps): treat it as missing, not as a dry month
    n_gap = 0
    for k in range(nm):
        vals = {}
        for g in gauges:
            if g['m'][k] is not None:
                vals.setdefault(g['district'], []).append(g['m'][k])
        med = {d: statistics.median(v) for d, v in vals.items()}
        for g in gauges:
            if g['m'][k] == 0 and med.get(g['district'], 0) >= 20:
                g['m'][k] = None; n_gap += 1

    # suspect readings: > 1000 mm in a month and > 5x the district median for that month
    for k in range(nm):
        vals = {}
        for g in gauges:
            if g['m'][k] is not None:
                vals.setdefault(g['district'], []).append(g['m'][k])
        med = {d: statistics.median(v) for d, v in vals.items()}
        for g in gauges:
            v = g['m'][k]
            if v is not None and v > 1000 and v > 5 * max(med[g['district']], 20):
                g.setdefault('suspect', []).append(k)

    gps_count = {}
    for g in gauges:
        if g['gps']:
            gps_count[g['district']] = gps_count.get(g['district'], 0) + 1

    def usable(g, k):
        return g['m'][k] is not None and k not in g.get('suspect', []) and (g['gps'] or gps_count.get(g['district'], 0) < 5)

    # 5. inverse-distance grid: 8 nearest usable gauges within 60 km, power 2
    cells = []
    for lo, la, di in geo['cells']:
        cx, cy = lo + .05, la + .05
        near = sorted(((km(cx, cy, g['lon'], g['lat']), g) for g in gauges if abs(g['lat'] - cy) < .6 and abs(g['lon'] - cx) < .7),
                      key=lambda t: t[0])
        vals = []
        for k in range(nm):
            pts = [(d, g['m'][k]) for d, g in near if usable(g, k)][:8]
            if not pts:
                vals.append(0.0); continue
            if pts[0][0] < .5:
                vals.append(round(pts[0][1], 1)); continue
            w = [1 / d ** 2 for d, _ in pts]
            vals.append(round(sum(wi * v for wi, (_, v) in zip(w, pts)) / sum(w), 1))
        cells.append([lo, la, di] + vals + [round(sum(vals), 1)])

    n_gps = sum(g['gps'] for g in gauges)
    n_match = sum(1 for m in matches if m[0])
    n_susp = sum(1 for g in gauges if g.get('suspect'))
    upd = dt.datetime.now(IST).strftime('%d %b %Y, %H:%M IST')
    meta = {
        'year': year,
        'subtitle': f"0.1° grid (~11 km) · TN SMART rain gauges · data to {last.strftime('%d %b %Y')} · updated {upd}",
        'notes': (f"Monthly totals come from the TNSDMA TN SMART monthly report (synced till {sync.strftime('%d %b %Y')}) "
                  f"plus TN SMART daily station readings saved automatically each day since then. "
                  f"{n_gps} gauges are placed at their real TN SMART latitude/longitude ({n_match} of {len(base['stations'])} report "
                  f"stations matched by name). Report stations that could not be matched are only used in districts with "
                  f"fewer than 5 located gauges. Grid values are inverse-distance estimates from the 8 nearest gauges within 60 km. "
                  f"{n_gap} gauge-months showing 0 mm while their district had rain are treated as missing. "
                  f"{n_susp} suspect gauge reading(s) (over 1,000 mm in a month and over 5× the district median) are excluded. "
                  f"Hill zones are hand-drawn approximations; the hill shading is illustrative relief and does not change the rainfall colours."),
    }
    D = dict(g=geo['g'], tn=geo['tn'], d=districts, ct=geo['ct'], c=cells, mn=MONTHS[:nm], meta=meta,
             st=[[g['name'], districts.index(g['district']) if g['district'] in districts else 0, round(g['lon'], 4), round(g['lat'], 4),
                  g['gps'], 1 if g.get('suspect') else 0] + g['m'] for g in gauges])
    tpl = open(P('site/template.html')).read()
    open(P('site/index.html'), 'w').write(tpl.replace('/*DATA*/', json.dumps(D, separators=(',', ':'), ensure_ascii=False)))
    status.update(data_to=str(last), months=nm, gauges=len(gauges), gauges_with_gps=n_gps, report_matched=n_match,
                  report_total=len(base['stations']), suspect=n_susp, zero_gaps=n_gap, daily_files=len(daily))
    save(P('data/status.json'), status)
    print(json.dumps(status, indent=1))


if __name__ == '__main__':
    main()
