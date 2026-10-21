"""ERA5 environment for the analogue library (data/cyclone/lib_list.json: every Oct-Dec Bay of Bengal system 2000-2025).
For each storm: every 12 h from 3 days before genesis to 5 days after. Geopotential, u, v at 850/700/500/200 hPa and
mean sea-level pressure, 0-40N 60-110E on a 1.5 deg grid. WeatherBench2 1.5 deg ERA5 up to Jan 2023, ARCO-ERA5 after.
Output: /tmp/cyc_out/lib_fields.npz"""
import json, os, datetime as dt, numpy as np, xarray as xr
WB2 = 'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
VARS = ['geopotential', 'u_component_of_wind', 'v_component_of_wind']
LEVS = [850, 700, 500, 200]
LATS = np.arange(0, 40.1, 1.5); LONS = np.arange(60, 110.1, 1.5)
os.makedirs('data/cyclone', exist_ok=True); LOGF = open('data/cyclone/lib_log.txt', 'w')
def log(*a): print(*a, flush=True); print(*a, file=LOGF, flush=True)
L = json.load(open('data/cyclone/lib_list.json'))
times = set()
for s in L:
    t0 = dt.datetime.strptime(s['t0'], '%Y-%m-%dT%H'); t0 = t0.replace(hour=t0.hour // 6 * 6)
    times.update((t0 + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H') for h in range(-72, 121, 12))
times = sorted(times); log(len(times), 'times')
def grab(ds, var, T, la, lo, lev=True):
    x = ds[var].sel(time=T)
    if lev: x = x.sel(level=LEVS)
    x = x.sel({la: LATS, lo: LONS}, method='nearest')
    dims = (['level'] if lev else []) + [la, lo]
    return x.transpose(*dims).values
W = xr.open_zarr(WB2, storage_options={'token': 'anon'}, chunks=None)
A = None
out = np.full((len(times), 3, len(LEVS), len(LATS), len(LONS)), np.nan, np.float32)
msl = np.full((len(times), len(LATS), len(LONS)), np.nan, np.float32)
for i, t in enumerate(times):
    T = np.datetime64(dt.datetime.strptime(t, '%Y-%m-%dT%H')); done = False
    if T < np.datetime64('2023-01-09T00'):
        try:
            for k, v in enumerate(VARS): out[i, k] = grab(W, v, T, 'latitude', 'longitude')
            msl[i] = grab(W, 'mean_sea_level_pressure', T, 'latitude', 'longitude', lev=False); done = True
        except Exception as e: log(i, t, 'WB2 failed', repr(e)[:300])
    if not done:
        try:
            if A is None: A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
            for k, v in enumerate(VARS): out[i, k] = grab(A, v, T, 'latitude', 'longitude')
            msl[i] = grab(A, 'mean_sea_level_pressure', T, 'latitude', 'longitude', lev=False); done = True
        except Exception as e: log(i, t, 'ARCO failed', repr(e)[:300])
    if i % 50 == 0 or not done: log(i, t, 'ok' if done else 'MISSING')
os.makedirs('/tmp/cyc_out', exist_ok=True)
np.savez_compressed('/tmp/cyc_out/lib_fields.npz', data=out, msl=msl, times=np.array(times), lats=LATS, lons=LONS, vars=np.array(['z', 'u', 'v']), levs=np.array(LEVS))
log('saved', os.path.getsize('/tmp/cyc_out/lib_fields.npz'), 'missing', int(np.isnan(out[:, 0, 2, 0, 0]).sum()))
