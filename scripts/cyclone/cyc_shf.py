"""18 Nov (A): ERA5 sensible + latent heat flux and BLH in 20-40N 50-110E (sp > 900 hPa), ascent vs subsidence at 850, screen starts
+12/24/36 h (1-h accumulations, W m-2 upward). GitHub 'shf truth' -> data/cyclone/wx/shf_truth6.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
box = dict(latitude=slice(40, 20), longitude=slice(50, 110)); out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in (0, 6, 12, 24, 36):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h')
        H = -A['surface_sensible_heat_flux'].sel(time=t, **box).values / 3600.0; LE = -A['surface_latent_heat_flux'].sel(time=t, **box).values / 3600.0
        b = A['boundary_layer_height'].sel(time=t, **box).values; sp = A['surface_pressure'].sel(time=t, **box).values; w = A['vertical_velocity'].sel(time=t, level=850, **box).values
        sw = A['surface_solar_radiation_downwards'].sel(time=t, **box).values / 3600.0; lw = A['surface_thermal_radiation_downwards'].sel(time=t, **box).values / 3600.0
        u100 = np.hypot(A['100m_u_component_of_wind'].sel(time=t, **box).values, A['100m_v_component_of_wind'].sel(time=t, **box).values)
        u10 = np.hypot(A['10m_u_component_of_wind'].sel(time=t, **box).values, A['10m_v_component_of_wind'].sel(time=t, **box).values)
        def opt(k):
            try: return A[k].sel(time=t, **box).values
            except Exception as e: print('missing', k, e); return np.full_like(A['2m_temperature'].sel(time=t, **box).values, np.nan)
        z0f = opt('forecast_surface_roughness'); ustf = opt('friction_velocity')
        tau = np.hypot(opt('mean_eastward_turbulent_surface_stress'), opt('mean_northward_turbulent_surface_stress'))
        tgw = np.hypot(opt('mean_eastward_gravity_wave_surface_stress'), opt('mean_northward_gravity_wave_surface_stress'))
        sk = A['skin_temperature'].sel(time=t, **box).values; t2 = A['2m_temperature'].sel(time=t, **box).values; lsm = A['land_sea_mask'].sel(time=t, **box).values > 0.5
        la = A.latitude.sel(latitude=slice(40, 20)).values; W = np.cos(np.radians(la))[:, None] * np.ones_like(b); r = {}
        for nm, m in (('ascent', (sp > 90000) & (w <= 0)), ('subsidence', (sp > 90000) & (w > 0)), ('asc_land', (sp > 90000) & (w <= 0) & lsm), ('asc_sea', (sp > 90000) & (w <= 0) & ~lsm)):
            f = lambda X: float((np.where(m, X, 0) * W).sum() / max((W * m).sum(), 1e-9)); r[nm] = dict(H=round(f(H), 1), LE=round(f(LE), 1), blh=round(f(b), 0), skin=round(f(sk), 2), t2=round(f(t2), 2), sw_dn=round(f(sw), 1), lw_dn=round(f(lw), 1), u10=round(f(u10), 2), u100=round(f(u100), 2), z0=round(f(z0f), 3), ust=round(f(ustf), 3), tau_turb=round(f(tau), 3), tau_gw=round(f(tgw), 3), area=round(float((W * m).sum() / W.sum()), 3))
        out[f'{s}_{h}'] = r; print(s, h, r, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/shf_truth6.json', 'w'), indent=1)
