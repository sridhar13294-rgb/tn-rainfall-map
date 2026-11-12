"""ERA5 surface / top-of-atmosphere energy-flux truth (12 Nov 2026; A + P1: which term of the low-level heat budget is short).
For every 2020 exam start (73, every 5 days) the DAILY MEAN (4 x 6-hourly means) of days 0, 1 and 2 of: surface sensible and latent
heat flux, surface net long-wave and short-wave, TOA net long-wave and short-wave, TOA incoming short-wave (W m-2, ERA5 sign: downward
positive), plus boundary-layer height (m) and total precipitation 24 h. 1.5 deg (121 x 240, lat ascending).
Writes /tmp/cyc_out/flux_truth_2020.npz (keys o_<name>, days = start dates, shape [start, day(0..2), lat, lon]).
Runs on GitHub Actions (cyclone-wx.yml, commit message 'flux truth')."""
import os, datetime as dt, numpy as np, xarray as xr
os.makedirs('data/cyclone/wx', exist_ok=True); LOG = open('data/cyclone/wx/flux_log.txt', 'w')
def log(*a): print(*a, flush=True); print(*a, file=LOG, flush=True)
ERA = 'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
STARTS = [dt.datetime(2020, 1, 1) + dt.timedelta(days=5 * i) for i in range(73)]
VARS = {'shf': 'mean_surface_sensible_heat_flux', 'lhf': 'mean_surface_latent_heat_flux', 'snlw': 'mean_surface_net_long_wave_radiation_flux',
        'snsw': 'mean_surface_net_short_wave_radiation_flux', 'tnlw': 'mean_top_net_long_wave_radiation_flux', 'tnsw': 'mean_top_net_short_wave_radiation_flux',
        'tdsw': 'mean_top_downward_short_wave_radiation_flux', 'blh': 'boundary_layer_height', 'tp24': 'total_precipitation_6hr'}
E = xr.open_zarr(ERA, storage_options={'token': 'anon'}, chunks=None)
have = {k: v for k, v in VARS.items() if v in E}; log('available', sorted(have), 'missing', sorted(set(VARS) - set(have)))
O = {k: np.full((len(STARTS), 3, 121, 240), np.nan, np.float32) for k in have}
for i, s in enumerate(STARTS):
    for d in range(3):
        ts = [np.datetime64(s + dt.timedelta(days=d, hours=h)) for h in (6, 12, 18, 24)]   # 6-h means ENDING at these times cover the day
        for k, var in have.items():
            try:
                x = E[var].sel(time=ts); la = 'latitude' if 'latitude' in x.dims else 'lat'; lo = 'longitude' if 'longitude' in x.dims else 'lon'
                x = x.sortby(la).transpose('time', la, lo).values.astype(np.float64)
                O[k][i, d] = (x.sum(0) if k == 'tp24' else x.mean(0)).astype(np.float32)
            except Exception as e: log('era5', s, d, k, repr(e)[:150])
    if i % 10 == 0: log('flux truth', i, s)
os.makedirs('/tmp/cyc_out', exist_ok=True)
np.savez_compressed('/tmp/cyc_out/flux_truth_2020.npz', days=np.array([s.strftime('%Y-%m-%dT%H') for s in STARTS]), **{'o_' + k: v for k, v in O.items()})
log('flux truth ready', os.path.getsize('/tmp/cyc_out/flux_truth_2020.npz'))
