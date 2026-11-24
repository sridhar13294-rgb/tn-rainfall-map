"""25 Nov: ERA5 low / total cloud cover over Bay/TN 5-20 N 75-95 E (land+sea), hourly day 1 (h1-h24) of the 3 screen starts.
GitHub 'lccbay truth' -> data/cyclone/wx/lccbay_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
out = {}
for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
    for h in range(1, 25, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); g = lambda k: A[k].sel(time=t, latitude=slice(20, 5), longitude=slice(75, 95)).values
        la = A.latitude.sel(latitude=slice(20, 5)).values; m = np.ones(g('low_cloud_cover').shape, bool)
        W = np.cos(np.radians(la))[:, None] * np.ones(m.shape); f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 3)
        lcc = g('low_cloud_cover'); out[f'{s}_{h}'] = dict(lcc=f(lcc), tcc=f(g('total_cloud_cover')), frac_lcc_ge_0p3=f((lcc >= 0.3).astype(float)))
        print(s, h, out[f'{s}_{h}'], flush=True)
out['mean'] = {k: round(float(np.mean([v[k] for v in out.values()])), 3) for k in ('lcc', 'tcc', 'frac_lcc_ge_0p3')}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/lccbay_truth.json', 'w'), indent=1)
