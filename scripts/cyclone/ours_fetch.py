"""Live inputs for our own ensemble (runs in the Cyclone study workflow when data/cyclone/RUN starts with "ours").
1. Latest GFS analysis (step 0 only - observed state, no forecast) over 0-35N 50-110E, 0.5 deg: msl, u/v at 10 m and
   850/700/500/300/250/200 hPa, z500/z200 -> /tmp/cyc_out/live_GFS_<run>.npz (same layout as the fc_ files).
2. Latest real-time MJO (NOAA PSL ROMI, in RMM orientation) -> data/cyclone/ours/live_mjo.json"""
import os, sys, json, math, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cyc_fetch as C
C.LATS = np.arange(0, 35 + 1e-6, 0.5); C.LONS = np.arange(50, 110 + 1e-6, 0.5)
OUT = os.path.join(C.ROOT, 'data', 'cyclone', 'ours'); os.makedirs(OUT, exist_ok=True)
run = C.latest_run(lambda r: C.http(C.gfs_url(r, 0) + '.idx', method='HEAD') is not None)
print('GFS analysis', run, flush=True)
idx = C.parse_idx(C.http(C.gfs_url(run, 0) + '.idx').decode())
A = np.full((1, 1, len(C.VARS), len(C.LATS), len(C.LONS)), np.nan, np.float32)
for r in idx:
    k = C.noaa_key(r) or ('msl' if r['var'] == 'PRMSL' else None)
    if k in C.VARS:
        buf = C.http(C.gfs_url(run, 0), rng=(r['start'], r['end']))
        try:
            if buf: A[0, 0, C.VARS.index(k)] = C.subset(buf)
            else: print('no bytes', k, flush=True)
        except Exception as e: print('decode failed', k, repr(e)[:200], flush=True)
A[0, 0, C.VARS.index('msl')] /= 100.0                       # hPa, as in the fc_ files (float16 cannot hold Pa)
fn = f'/tmp/cyc_out/live_GFS_{run:%Y%m%d%H}.npz'
np.savez_compressed(fn, data=A.astype(np.float16), vars=np.array(C.VARS), lats=C.LATS, lons=C.LONS, steps=np.array([0]), members=np.array([0]), run=f'{run:%Y%m%d%H}')
print('saved', fn, 'coverage', {v: float(np.isfinite(A[0, 0, i]).mean()) for i, v in enumerate(C.VARS)}, flush=True)
mjo = dict(source='NOAA PSL ROMI', rows=[])
try:
    txt = C.http('https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt').decode('utf-8', 'replace')
    for line in txt.splitlines():
        p = line.split()
        if len(p) >= 7 and p[0].isdigit() and len(p[0]) == 4:
            try: pc1, pc2 = float(p[4]), float(p[5])
            except ValueError: continue
            if abs(pc1) > 50 or abs(pc2) > 50: continue
            x, y = pc2, -pc1; ph = [5, 6, 7, 8, 1, 2, 3, 4][int((math.degrees(math.atan2(y, x)) % 360) // 45) % 8]   # Wheeler-Hendon phase, as on the site
            mjo['rows'].append(dict(date=f'{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}', rmm1=round(x, 2), rmm2=round(y, 2), phase=ph, amp=round(math.hypot(x, y), 2)))
    mjo['rows'] = mjo['rows'][-10:]
except Exception as e:
    mjo['error'] = repr(e)[:200]
json.dump(dict(run=f'{run:%Y-%m-%d %H}Z', file=os.path.basename(fn), coverage={v: round(float(np.isfinite(A[0, 0, i]).mean()), 2) for i, v in enumerate(C.VARS)}, mjo=mjo), open(os.path.join(OUT, 'live_inputs.json'), 'w'), indent=1)
print('mjo', mjo['rows'][-1:] if mjo['rows'] else mjo)
