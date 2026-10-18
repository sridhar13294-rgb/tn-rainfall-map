"""Daily climatology (1990-2019) for anomalies, from WeatherBench2's public ERA5 climatology (Google Cloud, no key).
Averages the 00/06/12/18 UTC values for each day of the year, over 0-40N 50-110E.  Output: release asset era5_clim_daily.npz"""
import json, os, sys, time, subprocess
import numpy as np, xarray as xr
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data/cases/era5'); LOG = []
def log(*a):
    m = ' '.join(str(x) for x in a); print(m, flush=True); LOG.append(m[:1500]); json.dump(dict(log=LOG), open(os.path.join(OUT, 'clim_status.json'), 'w'), indent=1)
CANDS = ['gs://weatherbench2/datasets/era5-hourly-climatology/1990-2019_6h_240x121_equiangular_with_poles_conservative.zarr',
         'gs://weatherbench2/datasets/era5-hourly-climatology/1990-2019_6h_512x256_equiangular_conservative.zarr',
         'gs://weatherbench2/datasets/era5-hourly-climatology/1990-2019_6h_1440x721.zarr']
ds = None
for u in CANDS:
    try:
        ds = xr.open_zarr(u, storage_options={'token': 'anon'}, chunks=None); log('opened', u, dict(ds.sizes)); log('vars', sorted(ds.data_vars)); break
    except Exception as e:
        log('no', u, repr(e)[:200])
if ds is None: sys.exit(1)
lat = ds.latitude.values; sel = dict(latitude=slice(0, 40) if lat[0] < lat[-1] else slice(40, 0), longitude=slice(50, 110))
WANT = {'geopotential': 'z', 'u_component_of_wind': 'u', 'v_component_of_wind': 'v', 'specific_humidity': 'q', 'temperature': 't',
        'vertical_velocity': 'w', 'relative_humidity': 'r', 'mean_sea_level_pressure': 'msl', 'total_column_water_vapour': 'tcwv',
        'sea_surface_temperature': 'sst', '10m_u_component_of_wind': 'u10', '10m_v_component_of_wind': 'v10', 'integrated_vapor_transport': 'ivt',
        'total_precipitation_24hr': 'tp24', 'total_precipitation_6hr': 'tp6'}
out = {}
for var, key in WANT.items():
    if var not in ds: log('missing', var); continue
    t0 = time.time(); x = ds[var].sel(**sel)
    if 'level' in x.dims: x = x.sel(level=[l for l in (925, 850, 700, 500, 300, 200) if l in x.level.values])
    a = x.mean('hour').values if 'hour' in x.dims else x.values           # dayofyear first
    if 'level' in x.dims:
        for i, l in enumerate(x.level.values): out[f'{key}{int(l)}'] = a[:, i].astype(np.float32)
    else: out[key] = a.astype(np.float32)
    log(var, x.dims, a.shape, int(time.time() - t0), 's')
la = ds.latitude.sel(latitude=sel['latitude']).values; lo = ds.longitude.sel(longitude=sel['longitude']).values
np.savez_compressed('/tmp/era5_clim_daily.npz', lat=la, lon=lo, doy=ds.dayofyear.values, **out)
log('saved', len(out), os.path.getsize('/tmp/era5_clim_daily.npz') // 1000, 'kB')
r = subprocess.run(['gh', 'release', 'upload', 'era5-cases', '/tmp/era5_clim_daily.npz', '--clobber'], capture_output=True, text=True); log('upload', r.returncode, r.stderr[:200])
