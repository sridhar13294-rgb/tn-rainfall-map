"""Case studies from Google's public ERA5 copy (ARCO-ERA5 on Cloud Storage: no queue, no key).  Same output as
era5_case.py: 8 days before to 2 days after the main rain day, every 6 h, 0.5 deg, 0-40N 50-110E; spin (vorticity) and
divergence worked out from the 0.25 deg winds; daily ERA5 rain in IMD's 08:30 IST windows.
Usage: python scripts/era5_arco.py LISTFILE  (lines "name YYYY-MM-DD")"""
import json, os, sys, time, datetime as dt, subprocess, concurrent.futures as cf
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_lib import OUT, pack, scale
import xarray as xr
URL = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
TMP = '/tmp/era5_out'; os.makedirs(TMP, exist_ok=True)
LEV = [925, 850, 700, 500, 300, 200]
PL = {'u': 'u_component_of_wind', 'v': 'v_component_of_wind', 'z': 'geopotential', 'q': 'specific_humidity', 't': 'temperature',
      'w': 'vertical_velocity', 'r': 'relative_humidity'}
SL = {'msl': 'mean_sea_level_pressure', 'tcwv': 'total_column_water_vapour', 'sst': 'sea_surface_temperature', 'u10': '10m_u_component_of_wind',
      'v10': '10m_v_component_of_wind', 'cape': 'convective_available_potential_energy', 'ttr': 'top_net_thermal_radiation',
      'ivtu': 'vertical_integral_of_eastward_water_vapour_flux', 'ivtv': 'vertical_integral_of_northward_water_vapour_flux'}
DS = xr.open_zarr(URL, storage_options={'token': 'anon'}, chunks=None)
HAVE = set(DS.data_vars)
SUB = dict(latitude=slice(40, 0), longitude=slice(50, 110))
LAT = DS.latitude.sel(latitude=SUB['latitude']).values; LON = DS.longitude.sel(longitude=SUB['longitude']).values
def read(var, t, lev=None):
    for k in range(5):
        try:
            x = DS[var].sel(time=np.datetime64(t)); x = x.sel(level=lev) if lev else x
            return x.sel(**SUB).values.astype(np.float64)
        except Exception as e:
            err = e; time.sleep(5 * (k + 1))
    raise err
def vort_div(u, v):
    """Relative vorticity and divergence on the 0.25 deg grid (rows north to south), per second."""
    a = 6.371e6; phi = np.radians(LAT)[:, None]; dlam = np.radians(0.25); dphi = np.radians(0.25)
    dx = a * np.cos(phi) * dlam; dy = a * dphi
    dudx = np.gradient(u, axis=-1) / dx; dvdx = np.gradient(v, axis=-1) / dx
    dudy = -np.gradient(u, axis=-2) / dy; dvdy = -np.gradient(v, axis=-2) / dy        # minus: rows run north to south
    t = np.tan(phi) / a
    return dvdx - dudy + u * t, dudx + dvdy - v * t
def one(name, day, par):
    LOG = []
    def log(*a):
        m = ' '.join(str(x) for x in a); print(name, m, flush=True); LOG.append(m[:800])
        json.dump(dict(name=name, day=str(day), source='ARCO-ERA5 (Google Cloud public copy)', log=LOG), open(os.path.join(OUT, name + '.json'), 'w'), indent=1)
    d0, d1 = day - dt.timedelta(days=8), day + dt.timedelta(days=2)
    T = [dt.datetime(d0.year, d0.month, d0.day) + dt.timedelta(hours=6 * k) for k in range(((d1 - d0).days + 1) * 4)]
    t0 = time.time(); jobs = [(k, PL[k], t) for k in PL if PL[k] in HAVE for t in T] + [(k, SL[k], t) for k in SL if SL[k] in HAVE for t in T]
    log('variables missing in ARCO:', [v for v in list(PL.values()) + list(SL.values()) if v not in HAVE])
    R = {}
    with cf.ThreadPoolExecutor(par) as ex:
        futs = {ex.submit(read, var, t, LEV if k in PL else None): (k, t) for k, var, t in jobs}
        for f in cf.as_completed(futs):
            k, t = futs[f]
            try: R[(k, t)] = f.result()
            except Exception as e: log('read failed', k, t, repr(e)[:200])
    log('fields read in', int(time.time() - t0), 's')
    out = dict(lat=LAT[::2][::-1].copy(), lon=LON[::2], times=np.array([t.strftime('%Y%m%d%H') for t in T]))
    def put(key, arr): q, off, s = pack(arr); out[key] = q; out[key + '__off'] = off; out[key + '__scale'] = s
    nan = np.full((len(LAT), len(LON)), np.nan)
    for k in PL:
        if PL[k] not in HAVE: continue
        for i, p in enumerate(LEV):
            put(f'{k}{p}', np.stack([scale(f'{k}{p}', R.get((k, t), np.full((len(LEV),) + nan.shape, np.nan))[i])[::-2, ::2] for t in T]))
    for i, p in enumerate(LEV):                                             # spin and divergence from the full-resolution winds
        vo, dv = zip(*[vort_div(R[('u', t)][i], R[('v', t)][i]) if ('u', t) in R and ('v', t) in R else (nan, nan) for t in T])
        put(f'vo{p}', np.stack([scale('vo', x)[::-2, ::2] for x in vo])); put(f'd{p}', np.stack([scale('d', x)[::-2, ::2] for x in dv]))
    for k in SL:
        if SL[k] in HAVE: put(k, np.stack([scale(k, R.get((k, t), nan))[::-2, ::2] for t in T]))
    # daily rain, 24 h ending 03 UTC (08:30 IST)
    if 'total_precipitation' in HAVE:
        hours = sorted({dt.datetime(d.year, d.month, d.day, 3) - dt.timedelta(hours=h) for d in [d0 + dt.timedelta(days=j) for j in range(1, (d1 - d0).days + 1)] for h in range(24)})
        with cf.ThreadPoolExecutor(par) as ex: TP = dict(zip(hours, ex.map(lambda t: read('total_precipitation', t), hours)))
        rd, rr = [], []
        for j in range(1, (d1 - d0).days + 1):
            d = d0 + dt.timedelta(days=j); hs = [dt.datetime(d.year, d.month, d.day, 3) - dt.timedelta(hours=h) for h in range(24)]
            rd.append(d.isoformat()); rr.append(np.sum([TP[h] for h in hs], 0)[::-2, ::2] * 1000)
        put('rain', np.stack(rr)); out['rain_days'] = np.array(rd)
    fn = os.path.join(TMP, name + '.npz'); np.savez_compressed(fn, **out)
    log('SAVED', len(T), 'times', os.path.getsize(fn) // 1000, 'kB, total', int(time.time() - t0), 's')
    r = subprocess.run(['gh', 'release', 'upload', 'era5-cases', fn, '--clobber'], capture_output=True, text=True)
    if r.returncode == 0: os.remove(fn); log('uploaded')
    else: log('upload failed', r.stderr[:300])
if __name__ == '__main__':
    todo = []
    for line in open(sys.argv[1]):
        p = line.split('#')[0].split()
        if len(p) >= 2: todo.append((p[0], dt.date.fromisoformat(p[1])))
    sh, nsh = int(os.environ.get('SHARD', '0')), int(os.environ.get('NSHARDS', '1'))
    for i, (n, d) in enumerate(todo):
        if i % nsh != sh: continue
        try: one(n, d, int(os.environ.get('ARCO_PAR', '12')))
        except Exception as e: print(n, 'FAILED', repr(e)[:500], flush=True)
