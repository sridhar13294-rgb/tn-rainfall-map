"""26 Nov (high-cloud 5-why): ERA5 ice water path above 450 hPa (specific_cloud_ice_water_content + snow excluded) and high cloud cover, Bay/TN box
(5-20N 75-95E), starts 1/11/16 Nov 2020, days 2-3 every 3 h. GitHub 'iwp truth' -> data/cyclone/wx/iwp_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
lev = [l for l in A.level.values if 100 <= l <= 450]; out = {}
for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
    rows = []
    for h in range(27, 72, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); box = dict(latitude=slice(20, 5), longitude=slice(75, 95))
        X = A['specific_cloud_ice_water_content'].sel(time=t, level=lev, **box).values; la = A.latitude.sel(latitude=slice(20, 5)).values
        dp = np.gradient(np.array(lev, float) * 100.0); iwp = (X * dp[:, None, None]).sum(0) / 9.80616 * 1000   # g m-2
        W = np.cos(np.radians(la))[:, None] * np.ones(iwp.shape); rows.append(float((iwp * W).sum() / W.sum()))
    out[s] = round(float(np.mean(rows)), 2); print(s, 'IWP g/m2', out[s], flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/iwp_truth.json', 'w'), indent=1)
