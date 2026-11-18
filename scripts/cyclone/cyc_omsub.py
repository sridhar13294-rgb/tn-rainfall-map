"""19 Nov (A): ERA5 omega (Pa/s, + = descent) at 850/700/500 and Q1/cp (K/day) at 925/850/700/500 over the OCEAN, subtropics 10-40 N/S
and deep tropics |lat| < 10, all longitudes; starts 2020-10-07 / 11-01 / 11-26 at +12/24/36/48 h. GitHub 'omsub truth' -> data/cyclone/wx/omsub_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, -40)); R = 6.371e6; out = {}; LV = [925, 850, 700, 500]
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in (12, 24, 36, 48):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); one = np.timedelta64(1, 'h')
        sel = lambda k, tt: A[k].sel(time=tt, level=LV, **box)
        T0 = sel('temperature', t); la = T0.latitude.values; lo = T0.longitude.values; T = T0.values; lev = np.array(LV, float) * 100.0
        Tm = sel('temperature', t - one).values; Tp = sel('temperature', t + one).values
        u = sel('u_component_of_wind', t).values; v = sel('v_component_of_wind', t).values; w = sel('vertical_velocity', t).values
        Tall = A['temperature'].sel(time=t, level=[1000, 925, 850, 700, 600, 500, 400], **box).values; lall = np.array([1000, 925, 850, 700, 600, 500, 400], float) * 100.0
        dTdp_all = np.gradient(Tall, lall, axis=0); dTdp = dTdp_all[[1, 2, 3, 5]]
        cl = np.cos(np.radians(la))[None, :, None]
        dTdx = np.gradient(T, np.radians(lo), axis=2) / (R * cl); dTdy = np.gradient(T, np.radians(la), axis=1) / R
        q1 = ((Tp - Tm) / 7200.0 + u * dTdx + v * dTdy + w * (dTdp - 0.2857 * T / lev[:, None, None])) * 86400.0
        lsm = A['land_sea_mask'].sel(time=t, **box).values < 0.5; W = np.cos(np.radians(la))[:, None] * np.ones((1, len(lo))); r = {}
        for nm, m in (('sub', lsm & (np.abs(la) >= 10)[:, None]), ('deep', lsm & (np.abs(la) < 10)[:, None])):
            f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 4)
            r[nm] = dict(**{f'w{p}': f(w[i]) for i, p in enumerate(LV) if p != 925}, **{f'q1_{p}': f(q1[i]) for i, p in enumerate(LV)})
        out[f'{s}_{h}'] = r; print(s, h, r, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/omsub_truth.json', 'w'), indent=1)
