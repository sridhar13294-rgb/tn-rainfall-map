"""18 Nov (A): ERA5 boundary_layer_height, global 1.5-deg box means, screen starts +12/24/36 h; area fraction > 1500 m by region.
GitHub 'blh global' -> data/cyclone/wx/blh_global.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
la = A.latitude.values[:720]; W = np.cos(np.radians(la))[:, None] * np.ones((1, 1440)); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in (12, 24, 36):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); b = A['boundary_layer_height'].sel(time=t).values[:720]
        r = {}
        for nm, m in (('globe', np.ones_like(b, bool)), ('tropics', np.abs(la)[:, None] < 20 + 0 * b), ('extratrop', np.abs(la)[:, None] >= 20 + 0 * b)):
            r[nm] = dict(mean=round(float((b * W * m).sum() / (W * m).sum()), 1), frac_gt1500=round(float(((b > 1500) * W * m).sum() / (W * m).sum()), 4))
        out[f'{s}_{h:02d}'] = r; print(s, h, r, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/blh_global.json', 'w'), indent=1)
