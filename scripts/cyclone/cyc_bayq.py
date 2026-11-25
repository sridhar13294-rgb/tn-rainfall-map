"""25 Nov (P5b 5-why: Bay surface air too moist): ERA5 specific humidity 1000/975/950/925/900 hPa and q2m over Bay/TN SEA points (5-20N 75-95E),
h0 and day 1 (h1..22 every 3 h), starts 2020-11-01 / 2020-11-11. GitHub 'bayq truth' -> data/cyclone/wx/bayq_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
def qs(T, p): e = 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * e / (p - 0.378 * e)
out = {}; L = [1000, 975, 950, 925, 900]
for s in ('2020-11-01', '2020-11-11'):
    for tag, hs in (('h0', [0]), ('day1', list(range(1, 25, 3)))):
        rows = []
        for h in hs:
            t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); g = lambda k, **kw: A[k].sel(time=t, latitude=slice(20, 5), longitude=slice(75, 95), **kw).values
            la = A.latitude.sel(latitude=slice(20, 5)).values; W = np.cos(np.radians(la))[:, None] * np.ones((len(la), 81)); sea = g('land_sea_mask') < 0.5
            f = lambda X: float((np.where(sea, X, 0) * W).sum() / (W * sea).sum())
            Q = g('specific_humidity', level=L); r = {str(p): f(Q[i]) * 1000 for i, p in enumerate(L)}
            r['q2m'] = f(qs(g('2m_dewpoint_temperature'), g('surface_pressure'))) * 1000; rows.append(r)
        out[f'{s}_{tag}'] = {k: round(float(np.mean([r[k] for r in rows])), 3) for k in rows[0]}; print(s, tag, out[f'{s}_{tag}'], flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/bayq_truth.json', 'w'), indent=1)
