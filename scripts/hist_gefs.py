"""Training history, part 3: NOAA GEFSv12 reforecasts (2000-2019): the current GFS ensemble model rerun on past days.
Control member, 00 UTC runs. For each TN SMART day D (08:30 IST D-1 to 08:30 IST D = 03 to 03 UTC):
  day1 = forecast made a day before (run of D-2 00 UTC, hours 27-51)
  day0 = same-day forecast (run of D-1 00 UTC, hours 3-27)
Rain total, CAPE max and precipitable water mean on the forecast page's 0.25 degree squares.
Only the needed GRIB messages are downloaded (byte ranges from the .idx files). Usage: python scripts/hist_gefs.py YEAR"""
import json, os, sys, re, datetime as dt, urllib.request, concurrent.futures as cf, time
import numpy as np, pygrib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, 'data/history/gefs'); os.makedirs(OUT, exist_ok=True)
h = open(os.path.join(ROOT, 'site/forecast.html')).read(); i = h.index('const F=') + 8; F, _ = json.JSONDecoder().raw_decode(h[i:])
CELLS = [(c['lat'], c['lon']) for c in F['cells']]
BASE = 'https://noaa-gefs-retrospective.s3.amazonaws.com/GEFSv12/reforecast'
def get(u, rng=None):
    for k in range(5):
        try:
            hd = {'User-Agent': 'tn-rainfall-map training'}
            if rng: hd['Range'] = 'bytes=%d-%s' % (rng[0], '' if rng[1] is None else rng[1])
            with urllib.request.urlopen(urllib.request.Request(u, headers=hd), timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            time.sleep(3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    return None
def idx(url):
    t = get(url + '.idx')
    if not t: return None
    L = [l.split(':') for l in t.decode().strip().split('\n')]
    out = []
    for n, l in enumerate(L):
        off = int(l[1]); end = int(L[n + 1][1]) - 1 if n + 1 < len(L) else None
        m = re.match(r'(\d+)-(\d+) hour acc', l[5]); s = re.match(r'(\d+) hour fcst', l[5])
        out.append(dict(rng=(off, end), acc=(int(m.group(1)), int(m.group(2))) if m else None, step=int(s.group(1)) if s else None))
    return out
def values(url, entries):
    bufs = list(cf.ThreadPoolExecutor(6).map(lambda e: get(url, e['rng']), entries))
    res = []
    for b in bufs:
        if not b: res.append(None); continue
        fn = f'/tmp/g{os.getpid()}.grb'; open(fn, 'wb').write(b); g = pygrib.open(fn); m = g.message(1); v = m.values; g.close()
        res.append(v)
    return res
LAT_I = np.array([int(round((90 - la) / 0.25)) for la, lo in CELLS]); LON_I = np.array([int(round((lo % 360) / 0.25)) for la, lo in CELLS])
def at_cells(v): return v[LAT_I, LON_I]
def rain_windows(init, wins):
    u = f'{BASE}/{init:%Y}/{init:%Y%m%d%H}/c00/Days:1-10/apcp_sfc_{init:%Y%m%d%H}_c00.grib2'; I = idx(u)
    if not I: return None
    acc = {e['acc']: e for e in I if e['acc']}
    need = {}
    for a, b in wins:
        for t in range(a, b, 3):                                     # 3-hour slot t..t+3
            if (t, t + 3) in acc: need[(t, t + 3)] = acc[(t, t + 3)]
            else:
                s = [k for k in acc if k[1] == t + 3 and k[0] < t]
                if not s or (s[0][0], t) not in acc: return None
                need[s[0]] = acc[s[0]]; need[(s[0][0], t)] = acc[(s[0][0], t)]
    keys = list(need); vals = dict(zip(keys, values(u, [need[k] for k in keys])))
    if any(v is None for v in vals.values()): return None
    out = []
    for a, b in wins:
        tot = 0
        for t in range(a, b, 3):
            if (t, t + 3) in vals: inc = vals[(t, t + 3)]
            else:
                s = [k for k in vals if k[1] == t + 3 and k[0] < t][0]; inc = vals[s] - vals[(s[0], t)]
            tot = tot + np.maximum(0, at_cells(inc))
        out.append(np.round(tot, 1))
    return out
def inst_windows(init, var, wins, how):
    u = f'{BASE}/{init:%Y}/{init:%Y%m%d%H}/c00/Days:1-10/{var}_{init:%Y%m%d%H}_c00.grib2'; I = idx(u)
    if not I: return None
    st = {e['step']: e for e in I if e['step'] is not None}
    steps = sorted({t for a, b in wins for t in range(a, b + 1, 3) if t in st})
    vals = dict(zip(steps, values(u, [st[t] for t in steps])))
    out = []
    for a, b in wins:
        V = [at_cells(vals[t]) for t in range(a, b + 1, 3) if vals.get(t) is not None]
        out.append(None if len(V) < 3 else np.round(np.max(V, 0) if how == 'max' else np.mean(V, 0), 1))
    return out
year = int(sys.argv[1]); f = f'{OUT}/{year}.json'
days = [dt.date(year, 10, 1) + dt.timedelta(days=k) for k in range(92)]
R = {k: [[None] * len(days) for _ in CELLS] for k in ('day0', 'day1', 'cape0', 'cape1', 'pwat0', 'pwat1')}
done = 0
for k, D in enumerate(days):
    for kind, lag, win in (('0', 1, (3, 27)), ('1', 2, (27, 51))):
        init = dt.datetime(D.year, D.month, D.day) - dt.timedelta(days=lag)
        r = rain_windows(init, [win])
        if r is not None:
            for c in range(len(CELLS)): R['day' + kind][c][k] = float(r[0][c])
        for var, key, how in (('cape_sfc', 'cape', 'max'), ('pwat_eatm', 'pwat', 'mean')):
            x = inst_windows(init, var, [win], how)
            if x and x[0] is not None:
                for c in range(len(CELLS)): R[key + kind][c][k] = float(x[0][c])
    done += 1; print(year, D, 'day1 Chennai cell' , R['day1'][min(range(len(CELLS)), key=lambda c: (CELLS[c][0]-13.0)**2+(CELLS[c][1]-80.25)**2)][k], flush=True)
cover = {k: round(sum(x is not None for r in v for x in r) / (len(CELLS) * len(days)), 2) for k, v in R.items()}
json.dump(dict(year=year, model='GEFSv12 reforecast control', days=[d.isoformat() for d in days], cells=CELLS, cover=cover, data=R), open(f, 'w'), separators=(',', ':'))
print('cover', cover)
