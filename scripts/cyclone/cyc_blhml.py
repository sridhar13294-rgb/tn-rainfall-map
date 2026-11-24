"""24 Nov (Land night BL, depth-measure check, registered 20:0x): ERA5 bulk-Ri boundary-layer depth computed from ERA5 MODEL LEVELS with two
reference levels - L137 (~10 m, ERA5's own; must reproduce ERA5 BLH) and L134 (~79 m, = our lowest level ~82 m) - with Ri interpolation,
IFS 3.10.1 definition (Ri_c 0.25, no excess, wind at the reference set to zero). Land 20-40 N, 1-deg subsample, 3 starts, day-1 hours
in the night (21-04 local) and day (10-16 local) bands. Heights of model levels: standard-atmosphere L137 table (stated approximation).
GitHub 'blhml truth' -> data/cyclone/wx/blhml_truth.json"""
import json, os, numpy as np, xarray as xr
FULL = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
ML = 'gs://gcp-public-data-arco-era5/ar/model-level-1h-0p25deg.zarr-v1'
A = xr.open_zarr(FULL, storage_options={'token': 'anon'}, chunks=None); B = xr.open_zarr(ML, storage_options={'token': 'anon'}, chunks=None)
LEV = list(range(105, 138)); ZH = dict(zip(range(137, 104, -1), [10.0, 31.0, 53.9, 79.0, 106.5, 136.6, 169.5, 205.2, 243.9, 285.9, 331.1, 379.7, 431.7,
      487.3, 546.4, 609.0, 675.0, 744.4, 817.0, 892.7, 971.6, 1053.6, 1138.6, 1226.4, 1317.0, 1410.4, 1506.5, 1605.0, 1706.0, 1809.6, 1915.6, 2024.0, 2134.7]))
lvn = 'hybrid' if 'hybrid' in B.dims else [d for d in B.dims if d not in ('time', 'latitude', 'longitude')][0]
print('ML level dim', lvn, B[lvn].values[-5:], flush=True)
sl = dict(latitude=slice(40, 20, 4), longitude=slice(0, 360, 4)); la = A.latitude.sel(latitude=slice(40, 20)).values[::4]; lo = A.longitude.values[::4]
z = np.array([ZH[l] for l in LEV])[:, None, None]
def depth(T, q, u, v, kref):
    thv = T * (1 + 0.61 * q) * (1.0 + 0.0 * z)          # potential temperature: add g z / cp (dry static energy / cp)
    sv = thv + 9.80616 / 1004.6 * z; r = len(LEV) - 1 - kref   # index of the reference level (LEV ascending = top->bottom)
    U2 = u ** 2 + v ** 2 + 1e-2; zr = z[r]
    Ri = 9.80616 * (z - zr) * (sv - sv[r]) / (sv[r] * U2)
    out = np.full(T.shape[1:], np.nan)
    for k in range(r - 1, -1, -1):                       # upward from the reference
        hit = np.isnan(out) & (Ri[k] > 0.25)
        lo_ = Ri[k + 1] if k + 1 < r else np.zeros_like(Ri[k]); zl = z[k + 1, 0, 0] if k + 1 < r else zr[0, 0]
        w = np.clip((0.25 - lo_) / np.maximum(Ri[k] - lo_, 1e-6), 0, 1); out = np.where(hit, zl + w * (z[k, 0, 0] - zl), out)
    return np.where(np.isnan(out), z[0, 0, 0], out)
res = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    t0 = np.datetime64(s + 'T00'); m = A['land_sea_mask'].sel(time=t0, **sl).values > 0.5; W = np.cos(np.radians(la))[:, None] * np.ones(m.shape)
    acc = {k: [0.0, 0.0] for k in ('n137', 'n134', 'nblh', 'd137', 'd134', 'dblh')}
    for h in (2, 6, 10, 14, 18, 22):
        t = t0 + np.timedelta64(h, 'h'); lh = (h + lo / 15.0) % 24; nt = ((lh >= 21) | (lh <= 4))[None, :] & m; dy = ((lh >= 10) & (lh <= 16))[None, :] & m
        g = lambda v: B[v].sel(time=t, **{lvn: LEV}, **sl).values.astype(float)
        T, q, u, v = g('temperature'), g('specific_humidity'), g('u_component_of_wind'), g('v_component_of_wind')
        D137, D134 = depth(T, q, u, v, 0), depth(T, q, u, v, 3); BL = A['boundary_layer_height'].sel(time=t, **sl).values
        for key, msk in (('n', nt), ('d', dy)):
            for nm, X in (('137', D137), ('134', D134), ('blh', BL)):
                acc[key + nm][0] += float((np.where(msk, X, 0) * W).sum()); acc[key + nm][1] += float((W * msk).sum())
        print(s, h, flush=True)
    res[s] = {k: round(a / max(b, 1e-9), 1) for k, (a, b) in acc.items()}; print(s, res[s], flush=True)
res['all'] = {k: round(float(np.mean([r[k] for r in res.values()])), 1) for k in res[s]}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(res, open('data/cyclone/wx/blhml_truth.json', 'w'), indent=1); print(res['all'])
