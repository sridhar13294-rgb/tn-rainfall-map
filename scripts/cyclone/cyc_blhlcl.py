"""18 Nov (A): ERA5 BL height vs LCL height in 20-40N 50-110E (surface pressure > 900 hPa), split by 850-hPa ascent / subsidence,
screen starts +12/24/36 h. LCL from 2-m T and dewpoint (Lawrence 2005: ~125 m per K of T - Td). GitHub 'blh lcl' -> data/cyclone/wx/blh_lcl.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, 20), longitude=slice(50, 110)); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in (12, 24, 36):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h')
        b = A['boundary_layer_height'].sel(time=t, **box).values; T2 = A['2m_temperature'].sel(time=t, **box).values; Td = A['2m_dewpoint_temperature'].sel(time=t, **box).values
        sp = A['surface_pressure'].sel(time=t, **box).values; w = A['vertical_velocity'].sel(time=t, level=850, **box).values
        la = A.latitude.sel(latitude=slice(40, 20)).values; W = np.cos(np.radians(la))[:, None] * np.ones_like(b); lcl = 125.0 * np.maximum(T2 - Td, 0.0)
        r = {}
        for nm, m in (('ascent', (sp > 90000) & (w <= 0)), ('subsidence', (sp > 90000) & (w > 0))):
            f = lambda X: float((np.where(m, X, 0) * W).sum() / (W * m).sum())
            r[nm] = dict(blh=round(f(b), 0), lcl=round(f(lcl), 0), frac_blh_ge_09lcl=round(f(b >= 0.9 * lcl), 3))
        out[f'{s}_{h}'] = r; print(s, h, r, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/blh_lcl.json', 'w'), indent=1)
