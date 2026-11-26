"""26 Nov (high-cloud 5-why): ERA5 low/medium/high/total cloud cover PER START (1/11/16 Nov 2020), boxes Bay/TN and S.India, days 1-5 daily means
of 3-hourly values (same boxes/hours as lcc5/mhcc truth). GitHub 'cldps truth' -> data/cyclone/wx/cldps_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
B = {'india_south': dict(latitude=slice(18, 8), longitude=slice(74, 84)), 'bay_tn': dict(latitude=slice(20, 5), longitude=slice(75, 95))}; out = {}
for b, box in B.items():
    la = A.latitude.sel(latitude=box['latitude']).values
    for v in ('low_cloud_cover', 'medium_cloud_cover', 'high_cloud_cover', 'total_cloud_cover'):
        for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
            days = []
            for dd in (1, 2, 3, 4, 5):
                vals = []
                for h in range(24 * (dd - 1) + 3, 24 * dd + 1, 3):
                    X = A[v].sel(time=np.datetime64(s + 'T00') + np.timedelta64(h, 'h'), **box).values; W = np.cos(np.radians(la))[:, None] * np.ones(X.shape)
                    vals.append(float((X * W).sum() / W.sum()))
                days.append(round(float(np.mean(vals)), 3))
            out[f'{b}|{v}|{s}'] = days; print(b, v, s, days, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/cldps_truth.json', 'w'), indent=1)
