"""25 Nov (Bay 850 cold -> low-cloud excess -> c_ls named): apply OUR RH-cloud mapping (Sundqvist, RHc(sigma) = 0.7 + 0.1 exp(1 - sigma^-4),
mixed-phase saturation, maximum-random overlap) to ERA5's OWN instantaneous RH on the 25-hPa pressure levels 1000-800 hPa (p > 0.8 ps)
over Bay/TN 5-20 N 75-95 E, 3 starts x 8 hours of day 1, and compare with ERA5 lcc at the same times. GitHub 'clsbay truth' ->
data/cyclone/wx/clsbay_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
LV = [1000, 975, 950, 925, 900, 875, 850, 825, 800]
def qs_mix(T, p):
    es_w = 611.21 * np.exp(17.502 * (T - 273.16) / (T - 32.19)); es_i = 611.21 * np.exp(22.587 * (T - 273.16) / (T + 0.7))
    a = np.clip((T - 250.16) / 23.0, 0, 1) ** 2; es = a * es_w + (1 - a) * es_i; return 0.622 * es / np.maximum(p - 0.378 * es, 1.0)
box = dict(latitude=slice(20, 5), longitude=slice(75, 95)); out = {}
for s in ('2020-11-01', '2020-11-11', '2020-11-16'):
    for h in range(1, 25, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h')
        ps = A['surface_pressure'].sel(time=t, **box).values; la = A.latitude.sel(latitude=slice(20, 5)).values
        T = A['temperature'].sel(time=t, level=LV, **box).values; q = A['specific_humidity'].sel(time=t, level=LV, **box).values
        p = np.array(LV, float)[:, None, None] * 100.0 * np.ones_like(T); sig = p / ps[None]
        rh = np.clip(q / qs_mix(T, p), 0, 1); rhc = 0.7 + 0.1 * np.exp(1.0 - np.maximum(sig, 0.05) ** -4.0)
        c = 1.0 - np.sqrt(np.clip((1.0 - rh) / (1.0 - rhc), 0.0, 1.0)); c = np.where((sig >= 0.8) & (sig <= 1.0), c, 0.0)   # below ground / above 0.8 ps -> none
        clr = np.ones(ps.shape); prev = np.zeros(ps.shape)                           # maximum-random overlap, bottom-up
        for k in range(len(LV)):
            ck = c[k]; clr = clr * (1.0 - np.maximum(ck, prev)) / np.maximum(1.0 - prev, 1e-6); prev = ck
        cmr = 1.0 - clr; crand = 1.0 - np.prod(1.0 - c, 0); cmax = c.max(0)
        W = np.cos(np.radians(la))[:, None] * np.ones(ps.shape); f = lambda X: round(float((X * W).sum() / W.sum()), 3)
        out[f'{s}_{h}'] = dict(scheme_maxrand=f(cmr), scheme_rand=f(crand), scheme_max=f(cmax), era5_lcc=f(A['low_cloud_cover'].sel(time=t, **box).values),
                               rh900=f(rh[4]), rh850=f(rh[6])); print(s, h, out[f'{s}_{h}'], flush=True)
out['mean'] = {k: round(float(np.mean([v[k] for v in out.values()])), 3) for k in next(iter(out.values()))}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/clsbay_truth.json', 'w'), indent=1); print(out['mean'])
