"""14 Nov (A/P1): ERA5 convective / total precipitation in the first 6 h of the 3 spin-up test starts (ARCO 0.25 deg hourly
accumulations, 7x7 box mean -> 1.5 deg). Reference for how often and where deep convection should be on at the start."""
import os, numpy as np, xarray as xr
from scipy.ndimage import uniform_filter
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
LATS = np.arange(-90, 90.1, 1.5); LONS = np.arange(0, 360, 1.5)
la = A.latitude.values; lo = A.longitude.values
il = np.abs(la[:, None] - LATS[None]).argmin(0); io = np.abs(lo[:, None] - LONS[None]).argmin(0)
out = {}
for t0 in ('2020-10-27', '2020-11-01', '2020-11-06'):
    for v in ('convective_precipitation', 'total_precipitation'):
        x = A[v].sel(time=slice(t0 + 'T01', t0 + 'T06')).values.astype(np.float32) * 1000.0          # m per hour -> mm per hour
        hr = x.copy(); x = uniform_filter(x, size=[1, 7, 7], mode=['nearest', 'nearest', 'wrap'])
        out[f'{v[:4]}_{t0}'] = x[:, il][:, :, io]
        # native-resolution fraction of raining points (cp > 0.1 mm/h) in 20S-20N, first hour
        tr = np.abs(la) < 20; w = np.cos(np.radians(la))[tr][:, None]
        print(t0, v, 'global mean h0-1 mm/day %.2f' % (float((hr[0] * np.cos(np.radians(la))[:, None]).sum() / (np.cos(np.radians(la))[:, None] * np.ones_like(hr[0])).sum()) * 24),
              '| tropics native frac > 0.1 mm/h %.3f' % float(((hr[0][tr] > 0.1) * w).sum() / (w * np.ones_like(hr[0][tr])).sum()), flush=True)
os.makedirs('/tmp/cyc_out', exist_ok=True); np.savez_compressed('/tmp/cyc_out/cp_start.npz', lats=LATS, lons=LONS, **out)
