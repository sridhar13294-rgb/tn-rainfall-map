"""25 Nov (P5b/Tracks 5-why: Bay column heating deficit, flux split): ERA5 Bay/TN box 5-20N 75-95E day 1 (h1..22 every 3 h), starts 2020-11-01
and 2020-11-11: surface H, LE (W m-2 upward), rain (mm/day), 10-m wind speed, SST, 2-m dewpoint, surface pressure (-> sea q_sat(SST) - q2m),
TOA and surface net SW/LW (-> atmospheric net radiation). GitHub 'bayfx truth' -> data/cyclone/wx/bayflux_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
def qs(T, p): e = 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * e / (p - 0.378 * e)
out = {}
for s in ('2020-11-01', '2020-11-11'):
    rows = []
    for h in range(1, 25, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); g = lambda k: A[k].sel(time=t, latitude=slice(20, 5), longitude=slice(75, 95)).values
        la = A.latitude.sel(latitude=slice(20, 5)).values; W = np.cos(np.radians(la))[:, None] * np.ones((len(la), 81)); sea = g('land_sea_mask') < 0.5
        f = lambda X, m=None: float((np.where(m if m is not None else True, X, 0) * W).sum() / (W * (m if m is not None else np.ones_like(W, bool))).sum())
        sp = g('surface_pressure'); sst = np.nan_to_num(g('sea_surface_temperature'), nan=300.0)
        r = dict(H=f(-g('surface_sensible_heat_flux') / 3600), LE=f(-g('surface_latent_heat_flux') / 3600), rain=f(g('total_precipitation') * 1000 * 24),
                 u10=f(np.hypot(g('10m_u_component_of_wind'), g('10m_v_component_of_wind'))), u10_sea=f(np.hypot(g('10m_u_component_of_wind'), g('10m_v_component_of_wind')), sea),
                 dq_sea=f((0.98 * qs(sst, sp) - qs(g('2m_dewpoint_temperature'), sp)) * 1000, sea), LE_sea=f(-g('surface_latent_heat_flux') / 3600, sea),
                 rad_atm=f((g('top_net_solar_radiation') + g('top_net_thermal_radiation') - g('surface_net_solar_radiation') - g('surface_net_thermal_radiation')) / 3600))
        rows.append(r); print(s, h, {k: round(v, 2) for k, v in r.items()}, flush=True)
    out[s] = {k: round(float(np.mean([r[k] for r in rows])), 3) for k in rows[0]}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/bayflux_truth.json', 'w'), indent=1); print(out, flush=True)
