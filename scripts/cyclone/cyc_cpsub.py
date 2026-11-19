"""20 Nov (A): ERA5 total and convective precipitation (1-h accumulations -> mm/day) over the subtropical OCEAN 10-40 N/S, all longitudes,
day 1 (+1..+24 h) of the 3 screen starts. GitHub 'cpsub truth' -> data/cyclone/wx/cpsub_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, -40)); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    t0 = np.datetime64(s + 'T00'); la = A.latitude.sel(**box).values
    m = (A['land_sea_mask'].sel(time=t0, **box).values < 0.5) & (np.abs(la) >= 10)[:, None]; W = np.cos(np.radians(la))[:, None] * np.ones(m.shape)
    f = lambda X: float((np.where(m, X, 0) * W).sum() / (W * m).sum())
    tp, cp = [], []
    for h in range(1, 25):
        t = t0 + np.timedelta64(h, 'h'); tp.append(f(A['total_precipitation'].sel(time=t, **box).values)); cp.append(f(A['convective_precipitation'].sel(time=t, **box).values))
    out[s] = dict(tp=round(float(np.sum(tp)) * 1000, 3), cp=round(float(np.sum(cp)) * 1000, 3)); print(s, out[s], flush=True)
out['mean'] = {k: round(float(np.mean([out[s][k] for s in ('2020-10-07', '2020-11-01', '2020-11-26')])), 3) for k in ('tp', 'cp')}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/cpsub_truth.json', 'w'), indent=1)
