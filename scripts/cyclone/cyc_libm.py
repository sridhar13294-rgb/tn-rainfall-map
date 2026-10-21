"""Global multi-level ERA5 at each past storm's start time, for the moist multi-level model (scripts/cyclone/mm/).
13 pressure levels (50-1000 hPa): temperature, specific humidity, u, v, geopotential; plus surface pressure, sea-surface
temperature, land-sea mask and terrain height. 1.5 deg global. WeatherBench2 ERA5 up to Jan 2023, ARCO-ERA5 after.
Output: /tmp/cyc_out/libm_fields.npz"""
import json, os, datetime as dt, numpy as np, xarray as xr
WB2 = 'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
V3 = ['temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind', 'geopotential']
V2 = ['surface_pressure', 'sea_surface_temperature', 'land_sea_mask', 'geopotential_at_surface']
LEVS = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
LATS = np.arange(-90, 90.1, 1.5); LONS = np.arange(0, 360, 1.5)
os.makedirs('data/cyclone', exist_ok=True); LOGF = open('data/cyclone/libm_log.txt', 'w')
def log(*a): print(*a, flush=True); print(*a, file=LOGF, flush=True)
L = json.load(open('data/cyclone/lib_list.json')); times = set()
for s in L:
    t0 = dt.datetime.strptime(s['t0'], '%Y-%m-%dT%H'); t0 = t0.replace(hour=t0.hour // 6 * 6); times.add(t0.strftime('%Y-%m-%dT%H'))
times = sorted(times); log(len(times), 'times')
def grab(ds, var, T, lev):
    x = ds[var]
    if 'time' in x.dims: x = x.sel(time=T)
    if lev: x = x.sel(level=LEVS)
    x = x.sel(latitude=LATS, longitude=LONS, method='nearest')
    return x.transpose(*((['level'] if lev else []) + ['latitude', 'longitude'])).values
W = xr.open_zarr(WB2, storage_options={'token': 'anon'}, chunks=None); A = None
log('WB2 vars', [v for v in V3 + V2 if v not in W])
F3 = np.full((len(times), len(V3), len(LEVS), len(LATS), len(LONS)), np.nan, np.float32)
F2 = np.full((len(times), len(V2), len(LATS), len(LONS)), np.nan, np.float32)
for i, t in enumerate(times):
    T = np.datetime64(dt.datetime.strptime(t, '%Y-%m-%dT%H'))
    for src in (('W', W) if T < np.datetime64('2023-01-09T00') else (None, None), ('A', None)):
        if src[0] is None: continue
        try:
            ds = src[1]
            if src[0] == 'A':
                if A is None: A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
                ds = A
            for k, v in enumerate(V3): F3[i, k] = grab(ds, v, T, True)
            for k, v in enumerate(V2):
                try: F2[i, k] = grab(ds, v, T, False)
                except Exception as e: log(i, t, src[0], v, 'missing', repr(e)[:120])
            break
        except Exception as e: log(i, t, src[0], 'failed', repr(e)[:300])
    log(i, t, 'ok' if np.isfinite(F3[i, 0, 5]).all() else 'MISSING')
os.makedirs('/tmp/cyc_out', exist_ok=True)
np.savez_compressed('/tmp/cyc_out/libm_fields.npz', f3=F3, f2=F2, times=np.array(times), lats=LATS, lons=LONS, v3=np.array(V3), v2=np.array(V2), levs=np.array(LEVS))
log('saved', os.path.getsize('/tmp/cyc_out/libm_fields.npz'))
