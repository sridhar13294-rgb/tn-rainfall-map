"""ERA5 humidity / cloud truth for the 2020 exam days (11 Nov 2026; root-cause work on the model's 24-48 h moistening/cloud drift).
Same days as wx_truth_2020.npz PLUS day 0 of every start (so hour 0 on our levels can be checked against ERA5 too).
Writes /tmp/cyc_out/wx_truth_moist_2020.npz: days, o_q925, o_q850, o_q700, o_q500 (kg/kg), o_t925 (K), o_tcwv (kg/m2),
o_tcc, o_lcc (0-1, when the archive has them), 1.5 deg (121 x 240, lat ascending). Runs on GitHub Actions (cyclone-wx.yml,
commit message 'moist truth'). The standard truth file is not touched."""
import os, sys, datetime as dt, numpy as np, xarray as xr
os.makedirs('data/cyclone/wx', exist_ok=True); LOG = open('data/cyclone/wx/moist_log.txt', 'w')
def log(*a): print(*a, flush=True); print(*a, file=LOG, flush=True)
ERA = 'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr'
STARTS = [dt.datetime(2020, 1, 1) + dt.timedelta(days=5 * i) for i in range(73)]
DAYS = sorted({s + dt.timedelta(days=d) for s in STARTS for d in range(0, 11)})
VARS = {'q925': ('specific_humidity', 925), 'q850': ('specific_humidity', 850), 'q700': ('specific_humidity', 700), 'q500': ('specific_humidity', 500),
        't925': ('temperature', 925), 'tcwv': ('total_column_water_vapour', None), 'tcc': ('total_cloud_cover', None), 'lcc': ('low_cloud_cover', None)}
E = xr.open_zarr(ERA, storage_options={'token': 'anon'}, chunks=None)
log('opened; variables:', sorted(E.data_vars))
have = {k: v for k, v in VARS.items() if v[0] in E}
log('available:', sorted(have), 'missing:', sorted(set(VARS) - set(have)))
O = {k: np.full((len(DAYS), 121, 240), np.nan, np.float32) for k in have}
for i, d in enumerate(DAYS):
    for k, (var, lev) in have.items():
        try:
            x = E[var].sel(time=np.datetime64(d))
            if lev is not None: x = x.sel(level=lev)
            la = 'latitude' if 'latitude' in x.dims else 'lat'; lo = 'longitude' if 'longitude' in x.dims else 'lon'
            O[k][i] = x.sortby(la).transpose(la, lo).values.astype(np.float32)
        except Exception as e: log('era5', d, k, repr(e)[:150])
    if i % 50 == 0: log('moist truth', i, d)
os.makedirs('/tmp/cyc_out', exist_ok=True)
np.savez_compressed('/tmp/cyc_out/wx_truth_moist_2020.npz', days=np.array([d.strftime('%Y-%m-%dT%H') for d in DAYS]), **{'o_' + k: v for k, v in O.items()})
log('moist truth ready', os.path.getsize('/tmp/cyc_out/wx_truth_moist_2020.npz'))
