"""Static fields for gravity-wave / blocking drag and an ozone climatology, from the public ARCO ERA5 copy on Google Cloud.
Writes /tmp/cyc_out/geo_gwd.npz (sub-grid orography: std dev, filtered std dev, anisotropy, angle, slope; 0.5 deg) and
/tmp/cyc_out/ozone_clim.npz (monthly zonal-mean ozone mass mixing ratio, 37 pressure levels, 2017-2019, 15th 00Z of each month).
Log -> data/cyclone/geo_fetch.txt"""
import os, time, numpy as np, xarray as xr
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
OUT = '/tmp/cyc_out'; os.makedirs(OUT, exist_ok=True); LOG = open('data/cyclone/geo_fetch.txt', 'w')
def log(*a): s = ' '.join(str(x) for x in a); print(s, flush=True); LOG.write(s + '\n'); LOG.flush()
t0 = time.time(); A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
lat = A.latitude.values; lon = A.longitude.values; log('opened', len(A.data_vars), 'vars', round(time.time() - t0), 's')
STAT = ['standard_deviation_of_orography', 'standard_deviation_of_filtered_subgrid_orography', 'anisotropy_of_sub_gridscale_orography',
        'angle_of_sub_gridscale_orography', 'slope_of_sub_gridscale_orography', 'geopotential_at_surface', 'land_sea_mask']
g = {}
for v in STAT:
    if v not in A: log('missing', v); continue
    x = A[v].sel(time='2020-01-01T00').values.astype(np.float32)
    if v == 'angle_of_sub_gridscale_orography':   # average angle as a doubled-angle vector (angle is mod pi)
        c = np.cos(2 * x)[:720, :].reshape(360, 2, 720, 2).mean((1, 3)); s = np.sin(2 * x)[:720, :].reshape(360, 2, 720, 2).mean((1, 3)); g[v] = 0.5 * np.arctan2(s, c)
    else: g[v] = x[:720, :].reshape(360, 2, 720, 2).mean((1, 3))
    log(v, 'min/max', float(np.nanmin(g[v])), float(np.nanmax(g[v])))
np.savez_compressed(f'{OUT}/geo_gwd.npz', lat=lat[:720].reshape(360, 2).mean(1), lon=lon.reshape(720, 2).mean(1), **{k: v.astype(np.float32) for k, v in g.items()})
log('geo_gwd.npz written', round(time.time() - t0), 's')
if 'ozone_mass_mixing_ratio' in A:
    lev = A.level.values; o3 = np.zeros((12, len(lev), len(lat)), np.float64)
    for m in range(1, 13):
        for y in (2017, 2018, 2019):
            x = A['ozone_mass_mixing_ratio'].sel(time=f'{y}-{m:02d}-15T00').values; o3[m - 1] += x.mean(-1) / 3
        log('ozone month', m, 'done; 10 hPa eq', float(o3[m - 1, list(lev).index(10), 360]) if 10 in lev else '', round(time.time() - t0), 's')
    np.savez_compressed(f'{OUT}/ozone_clim.npz', lev=lev, lat=lat, o3=o3.astype(np.float32))
    log('ozone_clim.npz written')
else: log('ozone_mass_mixing_ratio missing')
