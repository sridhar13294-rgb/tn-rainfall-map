"""26 Nov (P5b 5-why): ERA5 total column water vapour, Bay/TN box (5-20N 75-95E), starts 1/11/16 Nov 2020, h0 and days 1-3 (3-hourly means).
GitHub 'tcwv truth' -> data/cyclone/wx/tcwv_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
out = {}; box = dict(latitude=slice(20, 5), longitude=slice(75, 95)); la = A.latitude.sel(latitude=slice(20, 5)).values
for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
    row = []
    for hs in ([0], range(3, 25, 3), range(27, 49, 3), range(51, 73, 3)):
        v = []
        for h in hs:
            X = A['total_column_water_vapour'].sel(time=np.datetime64(s + 'T00') + np.timedelta64(h, 'h'), **box).values; W = np.cos(np.radians(la))[:, None] * np.ones(X.shape)
            v.append(float((X * W).sum() / W.sum()))
        row.append(round(float(np.mean(v)), 2))
    out[s] = row; print(s, row, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/tcwv_truth.json', 'w'), indent=1)
