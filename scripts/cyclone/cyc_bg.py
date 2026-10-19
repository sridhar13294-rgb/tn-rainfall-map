"""Background fields for past Bay of Bengal storms: geopotential and winds at 850, 500 and 200 hPa over
0-40N, 60-110E on a 1.5 deg grid, at each time in data/cyclone/bg_list.json plus 2 and 1 days before genesis.
Up to Jan 2023 from WeatherBench2's 1.5 deg ERA5; later from ARCO-ERA5 (0.25 deg, thinned to 1.5 deg).
Output: /tmp/cyc_out/bg_fields.npz"""
import json, os, datetime as dt, numpy as np, xarray as xr
WB2 = 'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
VARS = ['geopotential', 'u_component_of_wind', 'v_component_of_wind']
LEVS = [850, 500, 200]
LATS = np.arange(0, 40.1, 1.5); LONS = np.arange(60, 110.1, 1.5)
def log(*a): print(*a, flush=True)
L = json.load(open('data/cyclone/bg_list.json'))
times = set()
for s in L:
    t0 = dt.datetime.strptime(s['times'][0], '%Y-%m-%dT%H')
    s['all'] = [(t0 - dt.timedelta(hours=48)).strftime('%Y-%m-%dT%H'), (t0 - dt.timedelta(hours=24)).strftime('%Y-%m-%dT%H')] + s['times']
    times.update(s['all'])
times = sorted(times); log(len(times), 'times')
W = xr.open_zarr(WB2, storage_options={'token': 'anon'}, chunks=None); log('wb2', dict(W.sizes))
wlat = 'latitude' if 'latitude' in W.dims else 'lat'; wlon = 'longitude' if 'longitude' in W.dims else 'lon'
A = None
out = np.full((len(times), 3, 3, len(LATS), len(LONS)), np.nan, np.float32)
for i, t in enumerate(times):
    T = np.datetime64(dt.datetime.strptime(t, '%Y-%m-%dT%H'))
    try:
        if T < np.datetime64('2023-01-09T00'):
            for k, v in enumerate(VARS):
                x = W[v].sel(time=T, level=LEVS).sel({wlat: LATS, wlon: LONS}, method='nearest').values
                out[i, k] = x
        else:
            if A is None:
                A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None); log('arco', dict(A.sizes))
            for k, v in enumerate(VARS):
                x = A[v].sel(time=T, level=LEVS).sel(latitude=LATS, longitude=LONS, method='nearest').values
                out[i, k] = x
        log(i, t, 'ok', float(np.nanmean(out[i, 0, 1])) / 9.80665)
    except Exception as e:
        log(i, t, 'FAILED', repr(e)[:200])
os.makedirs('/tmp/cyc_out', exist_ok=True)
np.savez_compressed('/tmp/cyc_out/bg_fields.npz', data=out, times=np.array(times), lats=LATS, lons=LONS, vars=np.array(['z', 'u', 'v']), levs=np.array(LEVS))
log('saved', os.path.getsize('/tmp/cyc_out/bg_fields.npz'))
