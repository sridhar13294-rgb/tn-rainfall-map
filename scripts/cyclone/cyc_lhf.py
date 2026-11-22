"""ERA5 surface latent heat flux over Tamil Nadu land for the part-3 exam windows (P5b input check, 22 Nov): hourly ARCO-ERA5
'surface_latent_heat_flux' (J m-2 per hour, downward positive) -> daily mean W m-2 (upward positive) over TN land points
(8-13.5N, 76.5-80.5E, land-sea mask > 0.5), days 1-5 after each start. Also total precipitation for the same box.
Runs on GitHub Actions ('lhf truth'); output data/cyclone/wx/tn_lhf_era5.json."""
import json, datetime as dt, numpy as np, xarray as xr
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
STARTS = ['2020-01-16', '2020-02-05', '2020-02-25', '2020-03-16', '2020-04-05', '2020-04-25', '2020-05-15', '2020-06-04', '2020-06-24',
          '2020-07-14', '2020-08-03', '2020-08-23', '2020-09-12', '2020-10-02', '2020-10-22', '2020-11-11', '2020-12-01', '2020-12-21']
box = dict(latitude=slice(13.5, 8.0), longitude=slice(76.5, 80.5))
lsm = A['land_sea_mask'].sel(time=np.datetime64('2020-01-01T00'), **box).values > 0.5
out = {}
for s in STARTS:
    t0 = np.datetime64(s + 'T01'); t1 = t0 + np.timedelta64(5 * 24, 'h')
    x = A['surface_latent_heat_flux'].sel(time=slice(t0, t1 - np.timedelta64(1, 'h')), **box).values       # [120 h, lat, lon]
    p = A['total_precipitation'].sel(time=slice(t0, t1 - np.timedelta64(1, 'h')), **box).values
    le = -x.reshape(5, 24, *x.shape[1:]).sum(1) / 86400.0                                                   # W m-2, upward +
    rr = p.reshape(5, 24, *p.shape[1:]).sum(1) * 1000.0                                                     # mm/day
    out[s] = dict(le=[float(np.mean(d[lsm])) for d in le], rain=[float(np.mean(d[lsm])) for d in rr])
    print(s, ['%.0f' % v for v in out[s]['le']], ['%.1f' % v for v in out[s]['rain']], flush=True)
json.dump(out, open('data/cyclone/wx/tn_lhf_era5.json', 'w'), indent=1); print('saved')
