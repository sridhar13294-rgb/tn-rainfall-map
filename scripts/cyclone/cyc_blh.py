"""17 Nov P5b: ERA5 boundary-layer height over the Bay / E-of-Bay boxes at the ubudget starts +12/24/36 h (reference for model hbl).
GitHub 'blh truth' -> data/cyclone/wx/blh_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
BOX = {'Bay': (10, 22, 80, 95), 'EBay': (12, 24, 98, 110)}; out = {}
for s in ('2020-10-02', '2020-10-12', '2020-10-22', '2020-11-01', '2020-11-11', '2020-11-21', '2020-12-01', '2020-12-11'):
    for h in (12, 24, 36):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h')
        for b, (a0, a1, o0, o1) in BOX.items():
            x = A['boundary_layer_height'].sel(time=t, latitude=slice(a1, a0), longitude=slice(o0, o1)).values
            w = np.cos(np.radians(A.latitude.sel(latitude=slice(a1, a0)).values))[:, None] * np.ones_like(x)
            out.setdefault(b, []).append(dict(t=str(t), mean=round(float((x * w).sum() / w.sum()), 1), frac_gt1500=round(float(((x > 1500) * w).sum() / w.sum()), 3)))
for b, r in out.items(): print(b, 'mean BLH', round(np.mean([x['mean'] for x in r]), 1), 'frac>1500 m', round(np.mean([x['frac_gt1500'] for x in r]), 3), flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/blh_truth.json', 'w'), indent=1)
