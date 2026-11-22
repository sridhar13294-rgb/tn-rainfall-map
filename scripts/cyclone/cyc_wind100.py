"""ERA5 100-m wind speed (daily mean of hourly |V|) on the 1.5 deg grid, Jan 7 and Jun 30 2020 (day 1 of the local-test starts),
for the A/P1 drag 5-why (wind vs stability). Output data/cyclone/wx/era5_wind100.npz ('wind100 truth')."""
import numpy as np, xarray as xr
from scipy.ndimage import uniform_filter
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
LATS = np.linspace(-90, 90, 121); LONS = np.arange(240) * 1.5
il = np.abs(A.latitude.values[:, None] - LATS[None]).argmin(0); io = np.abs(A.longitude.values[:, None] - LONS[None]).argmin(0)
out = {}
for tag, s in (('jan', '2020-01-06'), ('jul', '2020-06-29')):
    t0 = np.datetime64(s + 'T01'); sl = slice(t0, t0 + np.timedelta64(23, 'h'))
    u = A['100m_u_component_of_wind'].sel(time=sl).values; v = A['100m_v_component_of_wind'].sel(time=sl).values
    sp = np.sqrt(u ** 2 + v ** 2).mean(0)
    out[tag + '_d1_ws100'] = uniform_filter(sp, size=[6, 6], mode=['nearest', 'wrap'])[il][:, io].astype(np.float32); print(tag, flush=True)
np.savez_compressed('data/cyclone/wx/era5_wind100.npz', lats=LATS, lons=LONS, **out); print('saved')
