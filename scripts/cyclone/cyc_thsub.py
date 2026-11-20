"""20 Nov (A): ERA5 potential temperature and height at 1000-850 hPa over the subtropical OCEAN 10-40 N/S, day 1 3-hourly, 3 screen starts
(cloud-layer stability for the BL-in-cloud-layer check). GitHub 'thsub truth' -> data/cyclone/wx/thsub_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, -40)); LV = [1000, 975, 950, 925, 900, 875, 850]; th, zz = [], []
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in range(3, 25, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); T = A['temperature'].sel(time=t, level=LV, **box); la = T.latitude.values
        Zg = A['geopotential'].sel(time=t, level=LV, **box).values / 9.80665; zs = A['geopotential_at_surface'].sel(time=t, **box).values / 9.80665
        m = (A['land_sea_mask'].sel(time=t, **box).values < 0.5) & (np.abs(la) >= 10)[:, None]; W = np.cos(np.radians(la))[:, None] * np.ones(m.shape)
        f = lambda X: float((np.where(m, X, 0) * W).sum() / (W * m).sum())
        TH = T.values * (1000.0 / np.array(LV, float))[:, None, None] ** 0.2857
        th.append([f(TH[i]) for i in range(len(LV))]); zz.append([f(Zg[i] - zs) for i in range(len(LV))])
th = np.mean(th, 0); zz = np.mean(zz, 0)
out = dict(levels=LV, theta=[round(float(x), 3) for x in th], z=[round(float(x), 1) for x in zz],
           dthdz_Kkm=[round(float((th[i + 1] - th[i]) / (zz[i + 1] - zz[i]) * 1000), 3) for i in range(len(LV) - 1)])
print(out, flush=True); os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/thsub_truth.json', 'w'), indent=1)
