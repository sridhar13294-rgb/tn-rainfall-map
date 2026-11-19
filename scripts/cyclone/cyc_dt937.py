"""19 Nov (A): ERA5 day-1 temperature change at ~937 hPa (925/950 mean) over the subtropical OCEAN 10-40 N/S, all longitudes, 3 screen
starts, 0..24 h every 3 h -> closes the hourly ERA5 Q1 = dT - hadv - vert with adv_truth.json. GitHub 'dt937 truth' -> data/cyclone/wx/dt937_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, -40)); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    r = {}
    for h in range(0, 25, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); T = A['temperature'].sel(time=t, level=[925, 950], **box); la = T.latitude.values
        lsm = A['land_sea_mask'].sel(time=t, **box).values < 0.5; W = np.cos(np.radians(la))[:, None] * np.ones(lsm.shape); m = lsm & (np.abs(la) >= 10)[:, None]
        X = T.values.mean(0); r[h] = round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 4)
    out[s] = dict(T=r, dT=round(r[24] - r[0], 4)); print(s, out[s], flush=True)
out['mean_dT'] = round(float(np.mean([out[s]['dT'] for s in ('2020-10-07', '2020-11-01', '2020-11-26')])), 4)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/dt937_truth.json', 'w'), indent=1)
