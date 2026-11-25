"""25 Nov: ERA5 low / total cloud over South India (8-18N, 74-84E) and Bay/TN (5-20N, 75-95E), days 1-3 (3-hourly) of the 3 Nov starts.
GitHub 'mhcc truth' -> data/cyclone/wx/mhcc_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
B = {'india_south': dict(latitude=slice(18, 8), longitude=slice(74, 84)), 'bay_tn': dict(latitude=slice(20, 5), longitude=slice(75, 95))}; out = {}
for b, box in B.items():
    la = A.latitude.sel(latitude=box['latitude']).values
    for v in ('medium_cloud_cover', 'high_cloud_cover'):
        days = []
        for dd in (1, 2, 3, 4, 5):
            vals = []
            for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
                for h in range(24 * (dd - 1) + 3, 24 * dd + 1, 3):
                    X = A[v].sel(time=np.datetime64(s + 'T00') + np.timedelta64(h, 'h'), **box).values; W = np.cos(np.radians(la))[:, None] * np.ones(X.shape)
                    vals.append(float((X * W).sum() / W.sum()))
            days.append(round(float(np.mean(vals)), 3))
        out[f'{b}|{v}'] = days; print(b, v, days, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/mhcc_truth.json', 'w'), indent=1)
