"""19 Nov (A): ERA5 boundary-layer height over LAND 20-40 N, all longitudes, day 1 hourly (+1..+24 h) of the 3 screen starts: mean of the
hourly means and mean of the per-point daily maximum (same domain/sampling as /tmp landhbl.py). GitHub 'blhland truth' -> data/cyclone/wx/blhland_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
out = {}; box = dict(latitude=slice(40, 20))
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    t0 = np.datetime64(s + 'T00'); la = A.latitude.sel(**box).values
    m = A['land_sea_mask'].sel(time=t0, **box).values > 0.5; W = np.cos(np.radians(la))[:, None] * np.ones(m.shape)
    f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 1)
    B = np.array([A['boundary_layer_height'].sel(time=t0 + np.timedelta64(h, 'h'), **box).values for h in range(1, 25)])
    out[s] = dict(mean=f(B.mean(0)), max=f(B.max(0))); print(s, out[s], flush=True)
out['all'] = {k: round(float(np.mean([v[k] for v in out.values()])), 1) for k in ('mean', 'max')}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/blhland_truth.json', 'w'), indent=1)
