"""19 Nov (A): ERA5 temperature and static stability S = -(T/theta) dtheta/dp (K per 100 hPa) at 850/700/500 over the subtropical
OCEAN 10-40 N/S, all longitudes; starts 2020-10-07 / 11-01 / 11-26 at +12/24 h (weak-descent input check: omega ~ Q_rad / S).
GitHub 'stab truth' -> data/cyclone/wx/stab_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, -40)); out = {}; LL = [1000, 925, 850, 775, 700, 600, 500, 400]
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in (12, 24):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h')
        T0 = A['temperature'].sel(time=t, level=LL, **box); la = T0.latitude.values; lo = T0.longitude.values; T = T0.values; p = np.array(LL, float)
        th = T * (1000.0 / p[:, None, None]) ** 0.2857; S = -(T / th) * np.gradient(th, p, axis=0) * 100.0
        lsm = A['land_sea_mask'].sel(time=t, **box).values < 0.5; W = np.cos(np.radians(la))[:, None] * np.ones((1, len(lo)))
        m = lsm & (np.abs(la) >= 10)[:, None]; f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 4)
        r = {**{f'T{q}': f(T[LL.index(q)]) for q in (925, 850, 700, 500)}, **{f'S{q}': f(S[LL.index(q)]) for q in (850, 700, 500)}}
        out[f'{s}_{h}'] = r; print(s, h, r, flush=True)
out['mean'] = {k: round(float(np.mean([v[k] for v in out.values()])), 4) for k in out[f'2020-10-07_12']}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/stab_truth.json', 'w'), indent=1)
