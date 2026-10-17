"""Training history, part 3b: more from the GEFS reforecasts (2000-2019) for the day-before window (run of D-2, hours 27-51):
  - rain from the 4 perturbed members p01-p04 (with the control: a 5-member chance of heavy rain)
  - 850 hPa spin (relative vorticity, x1e-5/s, max over the window) and wind (mean) from the control
Usage: python scripts/hist_gefs2.py YEAR"""
import json, os, sys, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0], sys.argv[1]]
import importlib.util
spec = importlib.util.spec_from_file_location('g', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hist_gefs.py'))
src = open(spec.origin).read(); src = src[:src.index('year = int(sys.argv[1])')]            # reuse the helpers only
g = {}; exec(compile(src, 'hist_gefs_helpers', 'exec'), g)
BASE, CELLS, idx, values, get = g['BASE'], g['CELLS'], g['idx'], g['values'], g['get']
OUT = os.path.join(g['ROOT'], 'data/history/gefs'); year = int(sys.argv[1])
days = [dt.date(year, 10, 1) + dt.timedelta(days=k) for k in range(92)]
R = {k: [[None] * len(days) for _ in CELLS] for k in ('p01', 'p02', 'p03', 'p04', 'vo850', 'u850', 'v850')}
LAT_I, LON_I = g['LAT_I'], g['LON_I']
def rain_member(init, mem, a, b):
    u = f'{BASE}/{init:%Y}/{init:%Y%m%d%H}/{mem}/Days:1-10/apcp_sfc_{init:%Y%m%d%H}_{mem}.grib2'
    old = g['BASE']; return g['rain_windows'].__globals__['rain_windows'](init, [(a, b)]) if mem == 'c00' else _rain(u, a, b)
def _rain(u, a, b):
    I = idx(u)
    if not I: return None
    acc = {e['acc']: e for e in I if e['acc']}; need = {}
    for t in range(a, b, 3):
        if (t, t + 3) in acc: need[(t, t + 3)] = acc[(t, t + 3)]
        else:
            s = [k for k in acc if k[1] == t + 3 and k[0] < t]
            if not s or (s[0][0], t) not in acc: return None
            need[s[0]] = acc[s[0]]; need[(s[0][0], t)] = acc[(s[0][0], t)]
    keys = list(need); vals = dict(zip(keys, values(u, [need[k] for k in keys])))
    if any(v is None for v in vals.values()): return None
    tot = 0
    for t in range(a, b, 3):
        if (t, t + 3) in vals: inc = vals[(t, t + 3)]
        else:
            s = [k for k in vals if k[1] == t + 3 and k[0] < t][0]; inc = vals[s] - vals[(s[0], t)]
        tot = tot + np.maximum(0, inc[LAT_I, LON_I])
    return np.round(tot, 1)
def winds(init, a, b):
    out = {}
    for var in ('ugrd', 'vgrd'):
        u = f'{BASE}/{init:%Y}/{init:%Y%m%d%H}/c00/Days:1-10/{var}_pres_{init:%Y%m%d%H}_c00.grib2'
        t = get(u + '.idx')
        if not t: return None
        L = [l.split(':') for l in t.decode().strip().split('\n')]; ent = {}
        for n, l in enumerate(L):
            if l[4] == '850 mb':
                m = __import__('re').match(r'(\d+) hour fcst', l[5])
                if m and a <= int(m.group(1)) <= b:
                    end = int(L[n + 1][1]) - 1 if n + 1 < len(L) else None; ent[int(m.group(1))] = dict(rng=(int(l[1]), end))
        steps = sorted(ent); vals = values(u, [ent[s] for s in steps]); out[var] = [v for v in vals if v is not None]
    if not out.get('ugrd') or len(out['ugrd']) != len(out['vgrd']): return None
    lat = np.linspace(90, -90, 721); dx = 0.25 * 111.32e3 * np.cos(np.radians(lat))[:, None]; dy = 0.25 * 110.6e3
    vo = [((np.roll(v, -1, 1) - np.roll(v, 1, 1)) / (2 * dx) - (np.roll(uu, 1, 0) - np.roll(uu, -1, 0)) / (2 * dy)) * 1e5 for uu, v in zip(out['ugrd'], out['vgrd'])]
    return (np.max(vo, 0)[LAT_I, LON_I], np.mean(out['ugrd'], 0)[LAT_I, LON_I], np.mean(out['vgrd'], 0)[LAT_I, LON_I])
for k, D in enumerate(days):
    init = dt.datetime(D.year, D.month, D.day) - dt.timedelta(days=2)
    for mem in ('p01', 'p02', 'p03', 'p04'):
        r = _rain(f'{BASE}/{init:%Y}/{init:%Y%m%d%H}/{mem}/Days:1-10/apcp_sfc_{init:%Y%m%d%H}_{mem}.grib2', 27, 51)
        if r is not None:
            for c in range(len(CELLS)): R[mem][c][k] = float(r[c])
    w = winds(init, 27, 51)
    if w is not None:
        for c in range(len(CELLS)):
            R['vo850'][c][k] = round(float(w[0][c]), 2); R['u850'][c][k] = round(float(w[1][c]), 1); R['v850'][c][k] = round(float(w[2][c]), 1)
    print(year, D, flush=True)
cover = {k: round(sum(x is not None for r in v for x in r) / (len(CELLS) * len(days)), 2) for k, v in R.items()}
json.dump(dict(year=year, days=[d.isoformat() for d in days], cells=CELLS, cover=cover, data=R), open(f'{OUT}/extra_{year}.json', 'w'), separators=(',', ':'))
print('cover', cover)
