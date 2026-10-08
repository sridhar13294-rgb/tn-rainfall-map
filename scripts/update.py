"""Daily update for the Tamil Nadu Rainfall Grid Map.

1. Downloads TN SMART's station-wise rainfall page (station name, district, lat/lon, today's rain).
2. Saves that day's rainfall to data/daily/YYYY-MM-DD.json and station positions to data/stations.json.
3. Matches the monthly-report stations (data/baseline.json) to TN SMART stations to give them real GPS.
4. Adds daily rain after the report's sync date to each station's monthly totals.
5. Interpolates a 0.1 degree grid (inverse distance) and writes site/index.html.

If TN SMART can't be reached, the map is rebuilt from the data already saved and the problem is
written to data/status.json, so a failed day never breaks the site.
"""
import datetime as dt, difflib, html, json, math, os, re, statistics, sys, time, urllib.parse, urllib.request
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


def fetch_date(date):
    """TN SMART station page for a past date (YYYY-MM-DD), via the page's own date form."""
    data = urllib.parse.urlencode({'date_on': date, 'search_submit': 'View Data'}).encode()
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(URL.rstrip('/'), data=data, headers={
                'User-Agent': 'Mozilla/5.0 (tn-rainfall-map daily update)', 'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e; time.sleep(10 * (attempt + 1))
    raise RuntimeError(f'could not download {date}: {last}')


def save_day(page, districts, stations, want=None):
    """Parse a TN SMART page, update gauge positions and save that day's readings. Returns (date, rows)."""
    date, rows = parse_page(page, districts + list(ALIASES))
    for r in rows:
        r['district'] = ALIASES.get(r['district'], r['district'])
    if want and date != want:
        raise RuntimeError(f'asked for {want}, page shows {date}')
    if not rows:
        raise RuntimeError('page downloaded but no station rows recognised (layout may have changed)')
    for r in rows:
        stations[r['id']] = {k: r[k] for k in ('id', 'name', 'district', 'taluk', 'lat', 'lon')}
    vals = {r['id']: r['rain'] for r in rows if r['rain'] is not None}
    if date and vals:
        save(P('data/daily', date + '.json'), vals)
    return date, rows


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

    # 1-2. TN SMART: today's page, plus the two previous days again (late or corrected readings)
    try:
        page = open(os.environ['TNSMART_HTML']).read() if os.environ.get('TNSMART_HTML') else fetch(URL)
        os.makedirs(P('data/raw'), exist_ok=True)
        open(P('data/raw/latest.html'), 'w').write(page)
        date, rows = save_day(page, districts, stations)
        status.update(page_date=date, rows_on_page=len(rows), rows_with_rain=sum(r['rain'] is not None for r in rows))
        status['tnsmart'] = 'ok'
        if date and not os.environ.get('TNSMART_HTML'):
            for k in (1, 2):
                d = (dt.date.fromisoformat(date) - dt.timedelta(days=k)).isoformat()
                try:
                    save_day(fetch_date(d), districts, stations, want=d)
                except Exception as e:
                    status[f'refresh_{d}'] = f'FAILED: {e}'
        save(P('data/stations.json'), stations)
    except Exception as e:
        status['tnsmart'] = f'FAILED: {e}'
        print('TN SMART step failed:', e, file=sys.stderr)

    # 3. every saved day of the year, per gauge
    files = sorted(f[:10] for f in os.listdir(P('data/daily')) if f.endswith('.json'))
    last = dt.date.fromisoformat(files[-1])
    year = last.year
    start = dt.date(year, 1, 1)
    ndays = (last - start).days + 1
    daily = {}
    for f in files:
        d = dt.date.fromisoformat(f)
        if d.year == year:
            daily[(d - start).days] = load(P('data/daily', f + '.json'), {})
    gauges = [s for s in sorted(stations.values(), key=lambda s: (s['district'] or '', s['name']))
              if s['district'] in districts and s.get('lat') and s.get('lon')]
    vals = []
    for g in gauges:
        row = []
        for k in range(ndays):
            v = daily.get(k, {}).get(g['id'])
            row.append(-1 if v is None else int(round(v * 10)))
        vals.append(row)
    missing_days = [(start + dt.timedelta(days=k)).isoformat() for k in range(ndays) if k not in daily]

    # 4. for every 0.1 degree cell, its 12 nearest gauges within 60 km (the page picks the 8 nearest with data)
    cells = []
    for lo, la, di in geo['cells']:
        cx, cy = lo + .05, la + .05
        near = sorted(((km(cx, cy, g['lon'], g['lat']), i) for i, g in enumerate(gauges)
                       if abs(g['lat'] - cy) < .6 and abs(g['lon'] - cx) < .7), key=lambda t: t[0])
        near = [(d, i) for d, i in near if d <= 60][:12]
        cells.append([lo, la, di, [i for _, i in near], [round(d, 1) for d, _ in near]])

    # state-average gauge rain per day (for the calendar shading)
    sd = []
    for k in range(ndays):
        v = [r[k] for r in vals if r[k] >= 0]
        sd.append(round(sum(v) / len(v) / 10, 1) if v else None)

    upd = dt.datetime.now(IST).strftime('%d %b %Y, %H:%M IST')
    meta = {
        'year': year, 'start': start.isoformat(), 'last': last.isoformat(), 'updated': upd, 'gauges': len(gauges),
        'missing': missing_days,
        'notes': (f"Daily readings from the {len(gauges)} TN SMART (TNSDMA) rain gauges with a known position, for every day "
                  f"from 1 Jan {year}. A TN SMART day is the 24 hours ending 08:30 IST on that date. "
                  f"For the period you choose, each gauge's rain is added up; a gauge missing more than 10% of the days is left out, "
                  f"and smaller gaps are filled in proportion. Over 20 days or more, a gauge showing 0 mm while its district's median "
                  f"gauge had 20 mm or more is treated as not reporting. A gauge more than 5 times its district median "
                  f"(and well above normal amounts) is flagged as suspect and left out of the grid. Grid squares (0.1°, ~11 km) "
                  f"are inverse-distance estimates from the 8 nearest gauges within 60 km. Hill zones are hand-drawn "
                  f"approximations; the hill shading is illustrative relief and does not change the rainfall colours."),
    }
    D = dict(g=geo['g'], tn=geo['tn'], d=districts, ct=geo['ct'], meta=meta, sd=sd,
             st=[[g['name'], districts.index(g['district']), round(g['lon'], 4), round(g['lat'], 4)] for g in gauges],
             v=vals, c=cells)
    tpl = open(P('site/template.html')).read()
    open(P('site/index.html'), 'w').write(tpl.replace('/*DATA*/', json.dumps(D, separators=(',', ':'), ensure_ascii=False)))
    status.update(data_to=str(last), days=ndays, days_missing=len(missing_days), gauges=len(gauges))
    save(P('data/status.json'), status)
    print(json.dumps(status, indent=1))


if __name__ == '__main__':
    main()
