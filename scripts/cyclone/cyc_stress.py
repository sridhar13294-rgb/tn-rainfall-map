"""ERA5 surface stress (turbulent + gravity-wave/orographic) for the A/P1 'missing drag sink' check (22 Nov): daily-mean eastward
and northward turbulent surface stress and gravity-wave surface stress (ARCO hourly accumulations, N m-2 s -> N m-2), on the 1.5 deg
library grid, for day 1 and day 2 after the Jan and Jul local-test starts. Output data/cyclone/wx/era5_stress.npz ('stress truth')."""
import numpy as np, xarray as xr
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
V = ['eastward_turbulent_surface_stress', 'northward_turbulent_surface_stress', 'eastward_gravity_wave_surface_stress', 'northward_gravity_wave_surface_stress']
print({v: v in A for v in V}, flush=True)
LATS = np.linspace(-90, 90, 121); LONS = np.arange(240) * 1.5
la = A.latitude.values; lo = A.longitude.values
il = np.abs(la[:, None] - LATS[None]).argmin(0); io = np.abs(lo[:, None] - LONS[None]).argmin(0)
from scipy.ndimage import uniform_filter
out = {}
for tag, s in (('jan', '2020-01-06'), ('jul', '2020-06-29')):
    for d in (1, 2):
        t0 = np.datetime64(s + 'T01') + np.timedelta64(24 * (d - 1), 'h')
        for v in V:
            x = A[v].sel(time=slice(t0, t0 + np.timedelta64(23, 'h'))).values.sum(0) / 86400.0
            out['%s_d%d_%s' % (tag, d, v)] = uniform_filter(x, size=[6, 6], mode=['nearest', 'wrap'])[il][:, io].astype(np.float32)
        print(tag, d, flush=True)
np.savez_compressed('data/cyclone/wx/era5_stress.npz', lats=LATS, lons=LONS, **out); print('saved')
