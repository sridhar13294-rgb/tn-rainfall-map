"""18 Nov (A): ERA5 cloud fraction and RH at 925/850/700 hPa, coarsened to 1.5 deg, for the screen starts 2020-10-07/11-01/11-26 +0..48 h
(every 12 h). GitHub 'cc truth' -> release era5-cases: cc_truth_2020.npz"""
import numpy as np, xarray as xr, os
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
print([v for v in A.data_vars if 'cloud' in v], flush=True)
out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in (0, 12, 24, 36, 48):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h')
        for v, nm in (('fraction_of_cloud_cover', 'cc'),):
            x = A[v].sel(time=t, level=[925, 850, 700]).values                     # [3, 721, 1440]
            x = x[:, :720, :].reshape(3, 120, 6, 240, 6).mean((2, 4))               # 1.5-deg boxes (0.25 x 6)
            out[f'{nm}_{s}_{h:02d}'] = x.astype(np.float32)
out['lat'] = A.latitude.values[:720].reshape(120, 6).mean(1); out['lon'] = A.longitude.values.reshape(240, 6).mean(1); out['levels'] = np.array([925, 850, 700])
os.makedirs('/tmp/cyc_out', exist_ok=True); np.savez_compressed('/tmp/cyc_out/cc_truth_2020.npz', **out); print('saved', len(out), flush=True)
