"""19 Nov (A, land soil start): ERA5 soil temperature levels 1-4 and skin at the 3 screen starts (00Z), 20-40N 50-110E land with sp > 900 hPa.
GitHub 'stl truth' -> data/cyclone/wx/stl_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, 20), longitude=slice(50, 110)); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    t = np.datetime64(s + 'T00'); g = lambda k: A[k].sel(time=t, **box).values
    m = (g('surface_pressure') > 90000) & (g('land_sea_mask') > 0.5)
    la = A.latitude.sel(latitude=slice(40, 20)).values; W = np.cos(np.radians(la))[:, None] * np.ones(m.shape)
    f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 2)
    out[s] = {k: f(g(v)) for k, v in dict(skin='skin_temperature', stl1='soil_temperature_level_1', stl2='soil_temperature_level_2', stl3='soil_temperature_level_3', stl4='soil_temperature_level_4', swvl1='volumetric_soil_water_layer_1').items()}
    print(s, out[s], flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/stl_truth.json', 'w'), indent=1)
