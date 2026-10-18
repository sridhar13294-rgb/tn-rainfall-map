"""Case study data: ECMWF IFS analyses (step 0 of the 00 and 12 UTC runs, open-data archive on AWS, 0.25 deg) over
south Asia for an event, plus each 00 UTC run's next-24-hour rain, and IMD's gridded daily rainfall (0.25 deg).
Usage: python scripts/case_fetch.py NAME START END     (dates YYYY-MM-DD; works from 20 Jan 2023)"""
import json, os, sys, datetime as dt, urllib.request, urllib.error, time, concurrent.futures as cf
import numpy as np, pygrib
NAME, START, END = sys.argv[1], dt.date.fromisoformat(sys.argv[2]), dt.date.fromisoformat(sys.argv[3])
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'cases', NAME); os.makedirs(OUT, exist_ok=True)
B = 'https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com'
LA0, LA1, LO0, LO1 = 0.0, 36.0, 55.0, 100.0
WANT = [('msl', None), ('tcwv', None), ('2t', None)] + [(p, l) for p in ('u', 'v') for l in (925, 850, 700, 500, 300, 200)] + \
       [('gh', 500), ('gh', 200), ('vo', 850), ('vo', 500), ('d', 850), ('d', 200), ('r', 700), ('q', 850), ('w', 500)]
LOG = []
def log(*a):
    m = ' '.join(str(x) for x in a); print(m, flush=True); LOG.append(m[:600])
def get(u, rng=None):
    for k in range(6):
        try:
            hd = {'User-Agent': 'tn-rainfall-map case study'}
            if rng: hd['Range'] = 'bytes=%d-%d' % (rng[0], rng[0] + rng[1] - 1)
            with urllib.request.urlopen(urllib.request.Request(u, headers=hd), timeout=120) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (403, 404): return None
            time.sleep(3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    return None
def prefixes(t):
    d = f'{t:%Y%m%d}/{t:%H}z'
    return [f'{d}/ifs/0p25/oper', f'{d}/0p4-beta/oper', f'{d}/ifs/0p4-beta/oper']
def fields(t, step, want):
    for p in prefixes(t):
        base = f'{B}/{p}/{t:%Y%m%d%H%M%S}-{step}h-oper-fc'
        ix = get(base + '.index')
        if not ix: continue
        L = [json.loads(l) for l in ix.decode().strip().split('\n')]; pick = {}
        for name, lev in want:
            for e in L:
                if e.get('param') == name and (lev is None and e.get('levtype') == 'sfc' or lev is not None and str(e.get('levelist')) == str(lev)):
                    pick[f'{name}{lev or ""}'] = (e['_offset'], e['_length']); break
        bufs = dict(zip(pick, cf.ThreadPoolExecutor(8).map(lambda k: get(base + '.grib2', pick[k]), pick)))
        out, grid = {}, None
        for k, b in bufs.items():
            if not b: continue
            fn = f'/tmp/c{os.getpid()}.grb'; open(fn, 'wb').write(b); g = pygrib.open(fn); m = g.message(1)
            v, la, lo = m.data(lat1=LA0, lat2=LA1, lon1=LO0, lon2=LO1); g.close()
            if la[0, 0] > la[-1, 0]: v, la, lo = v[::-1], la[::-1], lo[::-1]
            out[k] = v.astype(np.float32); grid = (la[:, 0], lo[0, :])
        return out, grid, p
    return {}, None, None
times = []; t = dt.datetime(START.year, START.month, START.day)
while t.date() <= END:
    times.append(t); t += dt.timedelta(hours=12)
A, R, grid = {}, {}, None
for t in times:
    f, g, p = fields(t, 0, WANT)
    if g is not None: grid = g
    log(t, 'analysis', p, len(f), 'fields')
    for k, v in f.items(): A.setdefault(k, {})[t.strftime('%Y%m%d%H')] = v
    if t.hour == 0:
        r0, _, _ = fields(t, 0, [('tp', None)]); r24, _, _ = fields(t, 24, [('tp', None)])
        if 'tp' in r24:
            R[t.strftime('%Y%m%d')] = ((r24['tp'] - (r0.get('tp', 0) if r0 else 0)) * 1000).astype(np.float32)
keys = sorted({k for v in A.values() for k in v})
np.savez_compressed(f'{OUT}/ecmwf.npz', lat=grid[0], lon=grid[1], times=np.array(keys), **{k: np.stack([A[k].get(t, np.full((len(grid[0]), len(grid[1])), np.nan, np.float32)) for t in keys]) for k in A},
                    rain_days=np.array(sorted(R)), rain24=np.stack([R[d] for d in sorted(R)]) if R else np.zeros((0,)))
log('saved', len(keys), 'times', sorted(A))
# IMD gridded rainfall (0.25 deg, daily 08:30 IST windows)
try:
    import imdlib as imd
    os.makedirs('/tmp/imd', exist_ok=True); years = sorted({START.year, END.year})
    data = imd.get_data('rain', years[0], years[-1], fn_format='yearwise', file_dir='/tmp/imd'); ds = data.get_xarray()
    sub = ds['rain'].sel(time=slice(str(START - dt.timedelta(days=2)), str(END)), lat=slice(7, 15), lon=slice(75.5, 81.5))
    v = sub.values.astype(np.float32); v[v < -1] = np.nan
    np.savez_compressed(f'{OUT}/imd_rain.npz', rain=v, lat=sub.lat.values, lon=sub.lon.values, days=np.array([str(x)[:10] for x in sub.time.values]))
    log('IMD gridded rain saved', v.shape, 'max', float(np.nanmax(v)))
except Exception as e:
    log('IMD gridded rain failed', repr(e)[:400])
json.dump(dict(name=NAME, start=str(START), end=str(END), log=LOG), open(f'{OUT}/status.json', 'w'), indent=1)
