"""Resolution effect on surface stress (A/P1 drag 5-why, 22 Nov): for NH winter ocean 30-60N on 2020-01-07 (hourly), the same neutral
Charnock bulk law (alpha 0.018, 10 m) applied (i) at 0.25 deg then box-averaged to 1.5 deg, (ii) to the 1.5-deg box-mean wind.
Ratio (ii)/(i) = stress lost by coarse winds alone. Output data/cyclone/wx/stress_res.json ('stressres truth')."""
import json, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
sel = dict(latitude=slice(60, 30), longitude=slice(150, 240))                     # N Pacific box (open ocean)
def cd(V):
    us = 0.04 * V
    for _ in range(8):
        z0 = 0.018 * us ** 2 / 9.80665 + 1.5e-5; c = (0.4 / np.log(10 / z0)) ** 2; us = np.sqrt(c) * V
    return c
fine = coarse = real = 0.0; n = 0
for h in range(1, 25):
    t = np.datetime64('2020-01-06T00') + np.timedelta64(h, 'h')
    u = A['10m_u_component_of_wind'].sel(time=t, **sel).values; v = A['10m_v_component_of_wind'].sel(time=t, **sel).values
    lsm = A['land_sea_mask'].sel(time=t, **sel).values < 0.5
    V = np.sqrt(u ** 2 + v ** 2); sf = cd(V) * V ** 2                                 # |tau| per unit rho, fine
    ny, nx = (u.shape[0] // 6) * 6, (u.shape[1] // 6) * 6
    B = lambda X: X[:ny, :nx].reshape(ny // 6, 6, nx // 6, 6).mean((1, 3))
    ub, vb = B(u), B(v); Vb = np.sqrt(ub ** 2 + vb ** 2); m = B(lsm.astype(float)) > 0.99
    fine += B(sf)[m].mean(); coarse += (cd(Vb) * Vb ** 2)[m].mean(); n += 1
r = dict(fine=float(fine / n), coarse=float(coarse / n), ratio=float(coarse / fine)); print(r)
json.dump(r, open('data/cyclone/wx/stress_res.json', 'w'))
