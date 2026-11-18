"""18 Nov (A, land diurnal trace): ERA5 hourly 0-24 h, 20-40N 50-110E land with sp > 900 hPa, 3 screen starts:
skin, t2, H, LE, SW/LW down, 10/100-m wind (1-h accumulations, W m-2, H/LE upward). GitHub 'shf hourly' -> data/cyclone/wx/shf_hourly3.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, 20), longitude=slice(50, 110)); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in range(0, 13):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); g = lambda k: A[k].sel(time=t, **box).values
        m = (g('surface_pressure') > 90000) & (g('land_sea_mask') > 0.5)
        la = A.latitude.sel(latitude=slice(40, 20)).values; W = np.cos(np.radians(la))[:, None] * np.ones(m.shape)
        f = lambda X: float((np.where(m, X, 0) * W).sum() / (W * m).sum())
        r = dict(H=f(-g('surface_sensible_heat_flux') / 3600), LE=f(-g('surface_latent_heat_flux') / 3600), skin=f(g('skin_temperature')), t2=f(g('2m_temperature')),
                 sw_dn=f(g('surface_solar_radiation_downwards') / 3600), sw_net=f(g('surface_net_solar_radiation') / 3600), lw_dn=f(g('surface_thermal_radiation_downwards') / 3600),
                 u10=f(np.hypot(g('10m_u_component_of_wind'), g('10m_v_component_of_wind'))), tcc=f(g('total_cloud_cover')), str_=f(g('surface_net_thermal_radiation') / 3600), sigT4=f(5.67e-8 * g('skin_temperature') ** 4), sw_clr=f(g('surface_solar_radiation_downward_clear_sky') / 3600), lon_mean=f(np.ones(m.shape) * A.longitude.sel(longitude=slice(50, 110)).values[None]), u100=f(np.hypot(g('100m_u_component_of_wind'), g('100m_v_component_of_wind'))))
        out[f'{s}_{h}'] = {k: round(v, 2) for k, v in r.items()}; print(s, h, out[f'{s}_{h}'], flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/shf_hourly3.json', 'w'), indent=1)
