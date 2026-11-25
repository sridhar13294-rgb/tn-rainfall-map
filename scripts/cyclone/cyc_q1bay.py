"""25 Nov: ERA5 apparent heat source (Bay/TN 5-20N 75-95E, day-1 hours 3/9/15/21) Q1/cp profile from 37 pressure levels, 0.25 deg, 1-h centred time differences, region
0-20N 50-110E (surface pressure > 900 hPa), starts 2020-10-07 / 11-01 / 11-26 at +12/24/36 h. GitHub 'q1bay truth' -> data/cyclone/wx/q1bay_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(20, 5), longitude=slice(75, 95)); R = 6.371e6; out = {}
for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
    for h in (3, 9, 15, 21):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); one = np.timedelta64(1, 'h')
        T0 = A['temperature'].sel(time=t, **box); lev = T0.level.values.astype(float) * 100.0
        Tm = A['temperature'].sel(time=t - one, **box).values; Tp = A['temperature'].sel(time=t + one, **box).values
        u = A['u_component_of_wind'].sel(time=t, **box).values; v = A['v_component_of_wind'].sel(time=t, **box).values; w = A['vertical_velocity'].sel(time=t, **box).values
        sp = A['surface_pressure'].sel(time=t, **box).values; T = T0.values; la = T0.latitude.values; lo = T0.longitude.values
        dTdt = (Tp - Tm) / 7200.0; cl = np.cos(np.radians(la))[None, :, None]
        dTdx = np.gradient(T, np.radians(lo), axis=2) / (R * cl); dTdy = np.gradient(T, np.radians(la), axis=1) / R
        dTdp = np.gradient(T, lev, axis=0); q1 = (dTdt + u * dTdx + v * dTdy + w * (dTdp - 0.2857 * T / lev[:, None, None])) * 86400.0
        W = np.cos(np.radians(la))[:, None] * np.ones((1, len(lo))); res = {}
        for k, p in enumerate(lev):
            m = (sp > max(p, 90000.0)) & np.isfinite(q1[k])
            res[int(p / 100)] = round(float((np.where(m, q1[k], 0) * W).sum() / (W * m).sum()), 3)
        out[f'{s}_{h}'] = res; print(s, h, {p: res[p] for p in (850, 700, 500, 400, 300, 250, 200)}, flush=True)
mean = {p: round(float(np.mean([out[k][p] for k in out])), 3) for p in out[next(iter(out))]}
print('MEAN', {p: mean[p] for p in (925, 850, 700, 600, 500, 400, 300, 250, 200, 150)}, flush=True)
out['mean'] = mean; os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/q1bay_truth.json', 'w'), indent=1)
