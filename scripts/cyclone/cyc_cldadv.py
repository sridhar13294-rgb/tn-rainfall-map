"""26 Nov (cloud 5-why: carried cloud too thin without advection): ERA5 Bay/TN (5-20N 75-95E) and S.India (8-20N 74-82E) boxes, starts 1/11/16 Nov
2020 days 3-5 every 3 h: share of points with NO convection (convective precip < 0.1 mm/h) and, among them, mean total and low cloud cover and the
share with total cover > 0.3 - cloud that cannot be a local convective product. GitHub 'cldadv truth' -> data/cyclone/wx/cldadv_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
B = {'bay_tn': (20, 5, 75, 95), 'india_south': (20, 8, 74, 82)}; out = {}
for b, (n, s, w, e) in B.items():
    rows = []
    for st in ('2020-11-01', '2020-11-11', '2020-11-16'):
        for h in range(72, 120, 3):
            t = np.datetime64(st + 'T00') + np.timedelta64(h, 'h'); g = lambda k: A[k].sel(time=t, latitude=slice(n, s), longitude=slice(w, e)).values
            cp = g('convective_precipitation') * 1000; tcc = g('total_cloud_cover'); lcc = g('low_cloud_cover'); nc = cp < 0.1
            rows.append([nc.mean(), tcc[nc].mean() if nc.any() else np.nan, lcc[nc].mean() if nc.any() else np.nan, (tcc[nc] > 0.3).mean() if nc.any() else np.nan,
                         (tcc * nc).sum() / max(tcc.sum(), 1e-9), (lcc * nc).sum() / max(lcc.sum(), 1e-9)])
    r = np.nanmean(rows, 0); out[b] = dict(noconv_share=r[0], tcc_noconv=r[1], lcc_noconv=r[2], share_tcc_gt03_noconv=r[3], tcc_area_share_noconv=r[4], lcc_area_share_noconv=r[5])
    print(b, {k: round(float(v), 3) for k, v in out[b].items()}, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump({b: {k: round(float(v), 4) for k, v in d.items()} for b, d in out.items()}, open('data/cyclone/wx/cldadv_truth.json', 'w'), indent=1)
