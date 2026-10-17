"""Training history, part 2: model forecasts on the forecast page's 0.25 degree squares, from Open-Meteo's archives
(used for training only; the live page keeps reading the official open-data servers).
  day1: what each model forecast ONE DAY BEFORE (Previous Runs API, from 2024), rain and CAPE
  day0: same-day runs (Historical Forecast API, 2021-2023), rain, CAPE, 850 hPa wind and humidity
Daily values on TN SMART days (08:30 to 08:30 IST = 03 to 03 UTC): rain total, CAPE max, 850 hPa wind/humidity mean.
Saved per season/model to data/history/models/<kind>_<year>_<model>.json. Resumable; stops politely on rate limits."""
import json, os, sys, time, datetime as dt, urllib.request, urllib.parse, urllib.error
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, 'data/history/models'); os.makedirs(OUT, exist_ok=True)
h = open(os.path.join(ROOT, 'site/forecast.html')).read(); i = h.index('const F=') + 8; F, _ = json.JSONDecoder().raw_decode(h[i:])
CELLS = [(c['lat'], c['lon']) for c in F['cells']]
MODELS = ['gfs_seamless', 'ecmwf_ifs025', 'icon_seamless', 'gem_seamless']
JOBS = [('day1', y, 'previous-runs-api', ['precipitation_previous_day1', 'cape_previous_day1']) for y in (2024, 2026)] + \
       [('day0', y, 'historical-forecast-api', ['precipitation', 'cape', 'wind_speed_850hPa', 'wind_direction_850hPa', 'relative_humidity_850hPa']) for y in (2021, 2022, 2023)]
def get(u):
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'tn-rainfall-map training (non-commercial)'}), timeout=180) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429: raise
            if e.code == 400: return {'error': e.read().decode()[:300]}
            time.sleep(10 * (k + 1))
        except Exception:
            time.sleep(10 * (k + 1))
    raise RuntimeError('failed ' + u[:200])
def season(kind, year, api, var, model):
    f = f'{OUT}/{kind}_{year}_{model}.json'
    if os.path.exists(f): return 'have'
    start = dt.date(year, 9, 30); end = dt.date(year, 10, 17) if year == 2026 else dt.date(year, 12, 31)
    days = [(start + dt.timedelta(days=k + 1)) for k in range((end - start).days)]
    res = {v: [] for v in var}; info = {}
    for c0 in range(0, len(CELLS), 25):
        ch = CELLS[c0:c0 + 25]
        q = dict(latitude=','.join(f'{a:.3f}' for a, _ in ch), longitude=','.join(f'{b:.3f}' for _, b in ch), start_date=start.isoformat(),
                 end_date=end.isoformat(), models=model, hourly=','.join(var), timezone='GMT')
        j = get(f'https://{api}.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(q))
        if isinstance(j, dict) and j.get('error'):
            return 'ERR ' + str(j)[:200]
        L = j if isinstance(j, list) else [j]
        for loc in L:
            H = loc['hourly']; t = [dt.datetime.fromisoformat(x) for x in H['time']]
            for v in var:
                vals = H.get(v) or [None] * len(t); row = []
                for d in days:
                    a = dt.datetime(d.year, d.month, d.day, 3) - dt.timedelta(days=1); b = a + dt.timedelta(days=1)
                    xs = [x for tt, x in zip(t, vals) if a <= tt < b and x is not None]
                    if len(xs) < 18: row.append(None); continue
                    row.append(round(sum(xs), 1) if v.startswith('precipitation') else round(max(xs), 0) if v.startswith('cape') else round(sum(xs) / len(xs), 1))
                res[v].append(row)
        time.sleep(4)
    cover = {v: round(sum(x is not None for r in res[v] for x in r) / max(1, len(res[v]) * len(days)), 2) for v in var}
    json.dump(dict(kind=kind, year=year, model=model, days=[d.isoformat() for d in days], cells=CELLS, cover=cover, data=res), open(f, 'w'), separators=(',', ':'))
    return cover
status = {}
try:
    for kind, year, api, var in JOBS:
        for m in MODELS:
            status[f'{kind}_{year}_{m}'] = season(kind, year, api, var, m); print(kind, year, m, status[f'{kind}_{year}_{m}'], flush=True)
except urllib.error.HTTPError as e:
    status['stopped'] = f'rate limit ({e.code}); run again later to continue'
json.dump(status, open(f'{OUT}/_status.json', 'w'), indent=1); print(json.dumps(status, indent=1))
