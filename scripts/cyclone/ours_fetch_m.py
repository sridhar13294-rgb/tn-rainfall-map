"""Live start data for the moist multi-level model: the latest GFS analysis (step 0 only - observed state, no forecast),
global, 1.5 deg, same layout as the ERA5 file for past storms (cyc_libm.py): temperature, specific humidity, u, v,
geopotential on 13 levels; surface pressure, sea temperature, land mask, terrain. -> /tmp/cyc_out/live_GFSM_<run>.npz"""
import os, sys, numpy as np, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cyc_fetch as C
C.LATS = np.arange(-90, 90.1, 1.5); C.LONS = np.arange(0, 360, 1.5)
LEVS = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
V3 = {'TMP': 'temperature', 'SPFH': 'specific_humidity', 'UGRD': 'u_component_of_wind', 'VGRD': 'v_component_of_wind', 'HGT': 'geopotential'}
V2 = {('PRES', 'surface'): 'surface_pressure', ('TMP', 'surface'): 'sea_surface_temperature', ('LAND', 'surface'): 'land_sea_mask', ('HGT', 'surface'): 'geopotential_at_surface'}
run = C.latest_run(lambda r: C.http(C.gfs_url(r, 0) + '.idx', method='HEAD') is not None); print('GFS analysis', run, flush=True)
idx = C.parse_idx(C.http(C.gfs_url(run, 0) + '.idx').decode())
f3 = np.full((len(V3), len(LEVS), len(C.LATS), len(C.LONS)), np.nan, np.float32); f2 = np.full((len(V2), len(C.LATS), len(C.LONS)), np.nan, np.float32)
k3 = list(V3); k2 = list(V2)
for r in idx:
    lev = r['level']; tgt = None
    if r['var'] in V3 and lev.endswith(' mb'):
        try: p = float(lev.split()[0])
        except ValueError: continue
        if p == int(p) and int(p) in LEVS: tgt = ('3', k3.index(r['var']), LEVS.index(int(p)))
    elif (r['var'], lev) in V2: tgt = ('2', k2.index((r['var'], lev)))
    if tgt is None: continue
    buf = C.http(C.gfs_url(run, 0), rng=(r['start'], r['end']))
    if not buf: print('no bytes', r, flush=True); continue
    a = C.subset(buf)
    if tgt[0] == '3': f3[tgt[1], tgt[2]] = a * (9.80665 if r['var'] == 'HGT' else 1.0)          # height -> geopotential, as ERA5
    else: f2[tgt[1]] = a * (9.80665 if tgt[1] == 3 else 1.0)
land = f2[2] > 0.5; f2[1] = np.where(land, np.nan, f2[1])                                           # sea temperature only over sea
fn = f'/tmp/cyc_out/live_GFSM_{run:%Y%m%d%H}.npz'; os.makedirs('/tmp/cyc_out', exist_ok=True)
np.savez_compressed(fn, f3=f3[None], f2=f2[None], times=np.array([f'{run:%Y-%m-%dT%H}']), lats=C.LATS, lons=C.LONS,
                    v3=np.array([V3[k] for k in k3]), v2=np.array([V2[k] for k in k2]), levs=np.array(LEVS))
print('saved', fn, 'coverage 3d', float(np.isfinite(f3).mean()), '2d', [float(np.isfinite(x).mean()) for x in f2], flush=True)
