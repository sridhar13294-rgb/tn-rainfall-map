"""Training history, part 5: ECMWF's real forecasts before 2023, from the TIGGE archive on the ECMWF Data Store (ECDS).
Needs the GitHub secret ECMWF_DS_KEY (personal access token from https://ecds.ecmwf.int, TIGGE licence accepted).
ECMWF control forecast, 00 UTC runs, 0.5 deg, 6-hourly steps. For each TN SMART day D (03 UTC D-1 to 03 UTC D):
  day1 = run of D-2, steps 27-51 (03 UTC values interpolated between the 6-hourly steps); day0 = run of D-1, steps 3-27.
Rain total; CAPE max; total column water mean; 850 hPa spin (vorticity, x1e-5/s) max.  Usage: hist_tigge.py YEAR"""
import json, os, sys, datetime as dt, time, calendar
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, 'data/history/tigge'); os.makedirs(OUT, exist_ok=True)
KEY = os.environ.get('ECMWF_DS_KEY', '').strip()
LOG = []
def log(*a):
    m = ' '.join(str(x) for x in a); print(m, flush=True); LOG.append(m[:1500])
    json.dump(dict(year=sys.argv[1], log=LOG), open(os.path.join(OUT, f'_status_{sys.argv[1]}.json'), 'w'), indent=1)
if not KEY:
    log('No ECMWF_DS_KEY secret: nothing to do.'); sys.exit(0)
log('key present, length', len(KEY), 'looks like', 'UUID' if KEY.count('-') == 4 else ('uid:key (old style)' if ':' in KEY else 'other'))
import cdsapi, pygrib
C = cdsapi.Client(url='https://ecds.ecmwf.int/api', key=KEY, quiet=False, timeout=600, retry_max=20)
h = open(os.path.join(ROOT, 'site/forecast.html')).read(); i = h.index('const F=') + 8; F, _ = json.JSONDecoder().raw_decode(h[i:])
CELLS = [(c['lat'], c['lon']) for c in F['cells']]
year = int(sys.argv[1]); STEPS = '0/6/12/18/24/30/36/42/48/54'
def fetch(levtype, d0, d1, target):
    req = {'class': 'ti', 'expver': 'prod', 'origin': 'ecmf', 'type': 'cf', 'time': '00:00:00', 'step': STEPS, 'grid': '0.5/0.5',
           'date': f'{d0}/{d1}', 'levtype': levtype}
    req.update({'param': '228228/59/136'} if levtype == 'sfc' else {'param': '131/132', 'levelist': '850'})
    for area in ('16/74/6/83', None):
        r = dict(req, **({'area': area} if area else {}))
        try:
            C.retrieve('tigge-forecasts', r, target); return True
        except Exception as e:
            log('request failed', levtype, d0, area, repr(e)[:1200])
    return False
F_ = {}                                                     # (init date, step, shortName) -> 2D field; plus lat/lon
LL = None
months = [(dt.date(year, 9, 29), dt.date(year, 10, 31)), (dt.date(year, 11, 1), dt.date(year, 11, 30)), (dt.date(year, 12, 1), dt.date(year, 12, 30))]
if os.environ.get('TIGGE_PROBE'):
    months = [(dt.date(year, 11, 14), dt.date(year, 11, 16))]
for d0, d1 in months:
    for lt in ('sfc', 'pl'):
        fn = f'/tmp/tigge_{year}_{d0:%m}_{lt}.grib'
        if not fetch(lt, d0.isoformat(), d1.isoformat(), fn): continue
        g = pygrib.open(fn)
        for m in g:
            if LL is None: LL = m.latlons()
            F_[(m.dataDate, m.endStep if hasattr(m, 'endStep') else m.step, m.shortName)] = m.values.astype(float)
        g.close(); os.remove(fn)
if not F_:
    log('no data'); sys.exit(1)
lat1 = LL[0][:, 0]; lon1 = LL[1][0, :] % 360
II = [int(np.abs(lat1 - a).argmin()) for a, _ in CELLS]; JJ = [int(np.abs(lon1 - b % 360).argmin()) for _, b in CELLS]
at = lambda v: np.array([v[a, b] for a, b in zip(II, JJ)])
names = sorted({k[2] for k in F_}); print('fields', names, flush=True)
TP = 'tp' if any(k[2] == 'tp' for k in F_) else names[0]
def get(init, step, name): return F_.get((int(f'{init:%Y%m%d}'), step, name))
def tp_at(init, s):                                          # accumulated rain at step s (3-hourly values interpolated)
    if s % 6 == 0: return get(init, s, TP)
    a, b = get(init, s - 3, TP), get(init, s + 3, TP)
    return None if a is None or b is None else (a + b) / 2
def vort(u, v):
    dy = 0.5 * 110.6e3; dx = 0.5 * 111.32e3 * np.cos(np.radians(LL[0]))
    return (np.gradient(v, axis=1) / dx - np.gradient(u, axis=0) / (-dy)) * 1e5   # rows run north to south
days = [dt.date(year, 10, 1) + dt.timedelta(days=k) for k in range(92)]
R = {f'{k}{w}': [[None] * len(days) for _ in CELLS] for k in ('rain', 'cape', 'tcw', 'vo850') for w in '01'}
for k, D in enumerate(days):
    for w, lag, (a, b) in (('0', 1, (3, 27)), ('1', 2, (27, 51))):
        init = D - dt.timedelta(days=lag); A, Bv = tp_at(init, a), tp_at(init, b)
        if A is not None and Bv is not None:
            r = np.maximum(0, at(Bv - A)); r = r * 1000 if r.max() < 1 and r.max() > 0 else r     # metres -> mm if needed
            for c in range(len(CELLS)): R['rain' + w][c][k] = round(float(r[c]), 1)
        steps = [s for s in range(0, 55, 6) if a - 3 <= s <= b + 3]
        for key, name, how in (('cape', 'cape', 'max'), ('tcw', 'tcw', 'mean')):
            V = [get(init, s, name) for s in steps]; V = [at(x) for x in V if x is not None]
            if len(V) >= 3:
                x = np.max(V, 0) if how == 'max' else np.mean(V, 0)
                for c in range(len(CELLS)): R[key + w][c][k] = round(float(x[c]), 1)
        V = [vort(get(init, s, 'u'), get(init, s, 'v')) for s in steps if get(init, s, 'u') is not None and get(init, s, 'v') is not None]
        if len(V) >= 3:
            x = at(np.max(V, 0))
            for c in range(len(CELLS)): R['vo850' + w][c][k] = round(float(x[c]), 2)
cover = {k: round(sum(x is not None for r in v for x in r) / (len(CELLS) * len(days)), 2) for k, v in R.items()}
json.dump(dict(model='ECMWF (TIGGE control forecast, 0.5 deg)', year=year, days=[d.isoformat() for d in days], cells=CELLS, cover=cover, data=R),
          open(f'{OUT}/{year}.json', 'w'), separators=(',', ':'))
log('cover', cover)
