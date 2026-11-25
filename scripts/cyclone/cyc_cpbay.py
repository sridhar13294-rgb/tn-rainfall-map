"""25 Nov: ERA5 total / convective precipitation over Bay/TN 5-20N 75-95E, day 1 of 3 starts (hourly accumulations), mean mm/day and the
area fraction with convective rain > 0.1 mm/h (trigger frequency proxy). GitHub 'cpbay truth' -> data/cyclone/wx/cpbay2_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(20, 5), longitude=slice(75, 95)); out = {}
la = A.latitude.sel(latitude=slice(20, 5)).values
for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
    t0 = np.datetime64(s + 'T00'); TP = []; CP = []
    for h in range(1, 25):
        t = t0 + np.timedelta64(h, 'h'); TP.append(A['total_precipitation'].sel(time=t, **box).values * 1000.0); CP.append(A['convective_precipitation'].sel(time=t, **box).values * 1000.0)
    TP, CP = np.array(TP), np.array(CP); W = np.cos(np.radians(la))[:, None] * np.ones(TP.shape[1:]); f = lambda X: float((X * W).sum() / W.sum())
    out[s] = dict(tp_mmday=round(f(TP.sum(0)), 2), cp_mmday=round(f(CP.sum(0)), 2), cp_area=round(float(np.mean([f((c > 0.1).astype(float)) for c in CP])), 3), tp_area=round(float(np.mean([f((c > 0.1).astype(float)) for c in TP])), 3),
                  cp_per_active_mmday=round(f(CP.sum(0)) / max(float(np.mean([f((c > 0.1).astype(float)) for c in CP])), 1e-6), 1)); print(s, out[s], flush=True)
out['mean'] = {k: round(float(np.mean([v[k] for v in out.values()])), 3) for k in next(iter(out.values()))}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/cpbay2_truth.json', 'w'), indent=1); print(out['mean'])
