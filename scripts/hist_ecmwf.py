"""Training history, part 4: ECMWF's real forecasts from its open-data archive on AWS (from 20 Jan 2023).
IFS (HRES, 0.4 deg until early 2024, then 0.25 deg) and AIFS (ECMWF's AI model), 00 UTC runs. For each TN SMART day D
(03 UTC D-1 to 03 UTC D): day1 = run of D-2 (hours 27-51), day0 = run of D-1 (hours 3-27).
Rain total; precipitable water (tcwv) mean; 850 hPa vorticity max (spin, x1e-5/s); 850 hPa wind mean (u, v).
Only the needed GRIB messages are fetched (byte ranges from the .index files). Usage: hist_ecmwf.py MODEL YEAR"""
import json, os, sys, datetime as dt, urllib.request, urllib.error, concurrent.futures as cf, time
import numpy as np, pygrib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, 'data/history/ecmwf'); os.makedirs(OUT, exist_ok=True)
h = open(os.path.join(ROOT, 'site/forecast.html')).read(); i = h.index('const F=') + 8; F, _ = json.JSONDecoder().raw_decode(h[i:])
CELLS = [(c['lat'], c['lon']) for c in F['cells']]
B = 'https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com'
model, year = sys.argv[1], int(sys.argv[2])
def get(u, rng=None):
    for k in range(8):
        try:
            hd = {'User-Agent': 'tn-rainfall-map training'}
            if rng: hd['Range'] = 'bytes=%d-%d' % (rng[0], rng[0] + rng[1] - 1)
            with urllib.request.urlopen(urllib.request.Request(u, headers=hd), timeout=120) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            time.sleep(4 * (k + 1))
        except Exception:
            time.sleep(4 * (k + 1))
    return None
def prefix(init):
    d = f'{init:%Y%m%d}'
    if model == 'ifs':
        return [f'{d}/00z/ifs/0p25/oper', f'{d}/00z/0p4-beta/oper', f'{d}/00z/ifs/0p4-beta/oper']
    return [f'{d}/00z/aifs-single/0p25/oper', f'{d}/00z/aifs/0p25/oper', f'{d}/00z/aifs/0p25-beta/oper']
WANT = [('tp', 'sfc', None), ('tcwv', 'sfc', None), ('vo', 'pl', '850'), ('u', 'pl', '850'), ('v', 'pl', '850')]
def step_fields(init, step):
    for p in prefix(init):
        base = f'{B}/{p}/{init:%Y%m%d%H%M%S}-{step}h-oper-fc'
        ix = get(base + '.index')
        if not ix: continue
        L = [json.loads(l) for l in ix.decode().strip().split('\n')]
        pick = {}
        for name, lt, lev in WANT:
            for e in L:
                if e.get('param') == name and (lev is None or str(e.get('levelist')) == lev) and (lt != 'pl' or e.get('levtype') == 'pl'):
                    pick[name] = (e['_offset'], e['_length']); break
        bufs = dict(zip(pick, cf.ThreadPoolExecutor(5).map(lambda k: get(base + '.grib2', pick[k]), pick)))
        out = {}
        for k, b in bufs.items():
            if not b: continue
            fn = f'/tmp/e{os.getpid()}.grb'; open(fn, 'wb').write(b); g = pygrib.open(fn); m = g.message(1)
            v = m.values; la, lo = m.latlons(); g.close()
            lat1 = la[:, 0]; lon1 = lo[0, :] % 360
            ii = [int(np.abs(lat1 - a).argmin()) for a, _ in CELLS]; jj = [int(np.abs(lon1 - (b_ % 360)).argmin()) for _, b_ in CELLS]
            out[k] = np.array([v[a, b_] for a, b_ in zip(ii, jj)], float)
        if out: return out, p
    return None, None
days = [dt.date(year, 10, 1) + dt.timedelta(days=k) for k in range(18 if year == 2026 else 92)]
days = [d for d in days if d >= dt.date(2023, 1, 22)]
KEYS = ('rain', 'tcwv', 'vo850', 'u850', 'v850')
R = {f'{k}{w}': [[None] * len(days) for _ in CELLS] for k in KEYS for w in ('0', '1')}; used = set()
for k, D in enumerate(days):
    for w, lag, (a, b) in (('0', 1, (3, 27)), ('1', 2, (27, 51))):
        init = dt.datetime(D.year, D.month, D.day) - dt.timedelta(days=lag)
        S = {}
        for s in range(a, b + 1, 6):
            f, p = step_fields(init, s)
            if f: S[s] = f; used.add(p.split('/', 2)[2])
        if a in S and b in S and 'tp' in S[a] and 'tp' in S[b]:
            r = np.maximum(0, (S[b]['tp'] - S[a]['tp']) * 1000)                 # metres -> mm
            for c in range(len(CELLS)): R['rain' + w][c][k] = round(float(r[c]), 1)
        for key, name, how in (('tcwv', 'tcwv', 'mean'), ('vo850', 'vo', 'max'), ('u850', 'u', 'mean'), ('v850', 'v', 'mean')):
            V = [S[s][name] for s in S if name in S[s]]
            if len(V) >= 3:
                x = np.max(V, 0) * (1e5 if name == 'vo' else 1) if how == 'max' else np.mean(V, 0)
                for c in range(len(CELLS)): R[key + w][c][k] = round(float(x[c]), 2)
    print(model, D, 'Chennai day1 rain', R['rain1'][min(range(len(CELLS)), key=lambda c: (CELLS[c][0]-13.0)**2+(CELLS[c][1]-80.25)**2)][k], flush=True)
cover = {k: round(sum(x is not None for r in v for x in r) / max(1, len(CELLS) * len(days)), 2) for k, v in R.items()}
json.dump(dict(model=model, year=year, source=sorted(used), days=[d.isoformat() for d in days], cells=CELLS, cover=cover, data=R),
          open(f'{OUT}/{model}_{year}.json', 'w'), separators=(',', ':'))
print('cover', cover, sorted(used))
