"""Forecast builder (experimental) for the Tamil Nadu weather page.

Runs 3x a day on GitHub Actions:
1. 16-day daily forecast on a 0.25 degree Tamil Nadu grid from five models via Open-Meteo
   (GFS, ECMWF IFS, ECMWF AIFS, GEM, ICON) and their average (only models that cover that day).
2. Wind fields every 6 hours for 7 days at the surface and 925/850/700/500/200 hPa on a 1 degree
   grid over 0-25N, 65-95E (GFS), for the wind animation.
3. Writes site/forecast.html from site/forecast_template.html.

Open-Meteo free tier: non-commercial use, 10,000 calls/day. One run uses roughly 1,000-2,000 calls.
"""
import datetime as dt, json, math, os, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
API = 'https://api.open-meteo.com/v1/forecast'
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))

MODELS = [  # (label, Open-Meteo model id)
    ('GFS', 'gfs_seamless'),
    ('ECMWF', 'ecmwf_ifs025'),
    ('ECMWF AI', 'ecmwf_aifs025_single'),
    ('GEM', 'gem_seamless'),
    ('ICON', 'icon_seamless'),
]
DAILY = ['precipitation_sum', 'temperature_2m_max', 'temperature_2m_min', 'wind_speed_10m_max', 'wind_direction_10m_dominant']
LEVELS = ['10m', '925hPa', '850hPa', '700hPa', '500hPa', '200hPa']
WIND_BOX = dict(lat0=0, lat1=25, lon0=65, lon1=95, step=1.0)
PACE = 8
LAND_URL = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson'


def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'tn-rainfall-map forecast (non-commercial)'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', 'replace')[:300]
            if e.code == 400:            # bad request (e.g. unknown model) - retrying won't help
                raise RuntimeError(f'HTTP 400: {body}')
            last = f'HTTP {e.code}: {body}'
        except Exception as e:
            last = e
        time.sleep(20 * (i + 1))
    raise RuntimeError(str(last))


def batches(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def query(points, params):
    """Open-Meteo multi-location request; returns one result dict per point."""
    out = []
    for chunk in batches(points, 60):
        q = dict(params, latitude=','.join(f'{p[1]:.2f}' for p in chunk), longitude=','.join(f'{p[0]:.2f}' for p in chunk))
        res = get(API + '?' + urllib.parse.urlencode(q))
        out += res if isinstance(res, list) else [res]
        time.sleep(PACE)   # stay under Open-Meteo's 600 calls/minute (each location counts ~1.2 calls)
    return out


def tn_points(geo):
    """0.25 degree points whose 0.25 box overlaps any 0.1 degree Tamil Nadu cell."""
    cells = [(lo + .05, la + .05) for lo, la, _ in geo['cells']]
    pts = []
    la = 8.0
    while la <= 13.6:
        lo = 76.25
        while lo <= 80.5:
            if any(abs(cx - lo) <= .15 and abs(cy - la) <= .15 for cx, cy in cells):
                pts.append((round(lo, 2), round(la, 2)))
            lo += .25
        la += .25
    return pts


def land_outline():
    cache = P('data/land_region.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    try:
        g = get(LAND_URL)
        rings = []
        for f in g['features']:
            geom = f['geometry']
            polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
            for poly in polys:
                for ring in poly:
                    if not any(55 < x < 105 and -10 < y < 35 for x, y in ring):
                        continue
                    r, last = [], None
                    for x, y in ring:
                        q = [round(x, 2), round(y, 2)]
                        if q != last:
                            r.append(q)
                        last = q
                    if len(r) > 3:
                        rings.append(r)
        json.dump(rings, open(cache, 'w'), separators=(',', ':'))
        return rings
    except Exception as e:
        print('coastline download failed:', e, file=sys.stderr)
        return []


def avg_dir(dirs, speeds):
    x = y = 0.0
    for d, s in zip(dirs, speeds):
        x += (s or 1) * math.sin(math.radians(d)); y += (s or 1) * math.cos(math.radians(d))
    return round(math.degrees(math.atan2(x, y)) % 360)


def main():
    status = {'run_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'models': {}}
    geo = json.load(open(P('data/geo.json')))
    pts = tn_points(geo)

    # 1. five-model daily forecast for Tamil Nadu
    per_model, dates = {}, None
    for label, mid in MODELS:
        try:
            res = query(pts, dict(daily=','.join(DAILY), models=mid, forecast_days=16, timezone='Asia/Kolkata',
                                  wind_speed_unit='kmh'))
            per_model[label] = [r['daily'] for r in res]
            dates = dates or res[0]['daily']['time']
            days = sum(v is not None for v in res[0]['daily']['precipitation_sum'])
            status['models'][label] = f'ok ({days} days)'
        except Exception as e:
            status['models'][label] = f'FAILED: {e}'
            print(label, 'failed:', e, file=sys.stderr)
    if not per_model:
        raise SystemExit('no model data at all')

    labels = [m for m, _ in MODELS if m in per_model]
    # drop trailing days that no model fully covers
    nd = len(dates)
    while nd and all(per_model[m][0]['precipitation_sum'][nd - 1] is None for m in labels):
        nd -= 1
    dates = dates[:nd]
    for m in labels:
        for rec in per_model[m]:
            for k in rec:
                rec[k] = rec[k][:nd]
    # cells: [lon, lat, {var: [[avg per day], {model: [per day]}]}]
    cells = []
    coverage = [[m for m in labels if per_model[m][0]['precipitation_sum'][d] is not None] for d in range(nd)]
    for i, (lo, la) in enumerate(pts):
        rec = {'lon': lo, 'lat': la}
        for var in DAILY[:4]:
            mv = {m: [None if v is None else round(v, 1) for v in per_model[m][i][var]] for m in labels}
            av = []
            for d in range(nd):
                xs = [mv[m][d] for m in labels if mv[m][d] is not None]
                av.append(round(sum(xs) / len(xs), 1) if xs else None)
            rec[var] = {'avg': av, **mv}
        dd = []
        for d in range(nd):
            ds = [(per_model[m][i]['wind_direction_10m_dominant'][d], per_model[m][i]['wind_speed_10m_max'][d]) for m in labels
                  if per_model[m][i]['wind_direction_10m_dominant'][d] is not None]
            dd.append(avg_dir([a for a, _ in ds], [b for _, b in ds]) if ds else None)
        rec['wind_dir'] = dd
        cells.append(rec)

    # 2. GFS wind fields over the region, every 6 h for 7 days
    b = WIND_BOX
    lats = [b['lat0'] + k * b['step'] for k in range(int((b['lat1'] - b['lat0']) / b['step']) + 1)]
    lons = [b['lon0'] + k * b['step'] for k in range(int((b['lon1'] - b['lon0']) / b['step']) + 1)]
    grid = [(lo, la) for la in lats for lo in lons]
    wind = None
    try:
        hv = [f'wind_speed_{l}' for l in LEVELS] + [f'wind_direction_{l}' for l in LEVELS]
        res = query(grid, dict(hourly=','.join(hv), models='gfs_seamless', forecast_days=7, timezone='GMT', wind_speed_unit='ms'))
        times = res[0]['hourly']['time']
        idx = [k for k, t in enumerate(times) if int(t[11:13]) % 6 == 0]
        lv = {}
        for l in LEVELS:
            frames = []
            for k in idx:
                u, v = [], []
                for r in res:
                    s, d = r['hourly'][f'wind_speed_{l}'][k], r['hourly'][f'wind_direction_{l}'][k]
                    if s is None or d is None:
                        u.append(0); v.append(0); continue
                    u.append(round(-s * math.sin(math.radians(d)) * 2))   # 0.5 m/s units
                    v.append(round(-s * math.cos(math.radians(d)) * 2))
                frames.append([u, v])
            lv[l] = frames
        wind = dict(lat0=lats[0], lon0=lons[0], step=b['step'], ny=len(lats), nx=len(lons),
                    times=[times[k] + 'Z' for k in idx], levels=lv)
        status['wind'] = f'ok ({len(idx)} frames x {len(LEVELS)} levels)'
    except Exception as e:
        status['wind'] = f'FAILED: {e}'
        print('wind failed:', e, file=sys.stderr)

    now = dt.datetime.now(IST)
    F = dict(updated=now.strftime('%d %b %Y, %H:%M IST'), dates=dates, models=labels, coverage=coverage,
             cells=cells, wind=wind, land=land_outline(), tn=geo['tn'], ct=geo['ct'], step=.25)
    tpl = open(P('site/forecast_template.html')).read()
    open(P('site/forecast.html'), 'w').write(tpl.replace('/*FDATA*/', json.dumps(F, separators=(',', ':'))))
    status['points'] = len(pts)
    status['days'] = nd
    json.dump(status, open(P('data/forecast_status.json'), 'w'), indent=1)
    print(json.dumps(status, indent=1))


if __name__ == '__main__':
    main()
