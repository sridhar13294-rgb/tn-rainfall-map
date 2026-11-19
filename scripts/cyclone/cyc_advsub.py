"""19 Nov (A): ERA5 temperature budget terms at ~937 hPa (mean of 925 and 950, = model sigma 0.925 over the ocean) over the subtropical OCEAN
10-40 N/S, all longitudes, day 1 every 3 h of the 3 screen starts: horizontal advection -V.grad T and the vertical term
-omega (dT/dp - kappa T / p), K/day. GitHub 'adv truth' -> data/cyclone/wx/adv_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, -40)); R = 6.371e6; out = {}; LV = [900, 925, 950, 975]
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in range(1, 25, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); sel = lambda k: A[k].sel(time=t, level=LV, **box)
        T0 = sel('temperature'); la = T0.latitude.values; lo = T0.longitude.values; T = T0.values; p = np.array(LV, float) * 100.0
        u = sel('u_component_of_wind').values; v = sel('v_component_of_wind').values; w = sel('vertical_velocity').values
        cl = np.cos(np.radians(la))[None, :, None]
        dTdx = np.gradient(T, np.radians(lo), axis=2) / (R * cl); dTdy = np.gradient(T, np.radians(la), axis=1) / R; dTdp = np.gradient(T, p, axis=0)
        hadv = -(u * dTdx + v * dTdy) * 86400.0; vert = -w * (dTdp - 0.2857 * T / p[:, None, None]) * 86400.0
        lsm = A['land_sea_mask'].sel(time=t, **box).values < 0.5; W = np.cos(np.radians(la))[:, None] * np.ones((1, len(lo)))
        m = lsm & (np.abs(la) >= 10)[:, None]; f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 4)
        r = dict(hadv=f(0.5 * (hadv[1] + hadv[2])), vert=f(0.5 * (vert[1] + vert[2])), omega=f(0.5 * (w[1] + w[2])))
        out[f'{s}_{h}'] = r; print(s, h, r, flush=True)
out['mean'] = {k: round(float(np.mean([v[k] for v in out.values()])), 4) for k in ('hadv', 'vert', 'omega')}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/adv_truth.json', 'w'), indent=1)
