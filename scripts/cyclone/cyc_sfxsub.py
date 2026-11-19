"""19 Nov (A): ERA5 surface sensible / latent heat flux (1-h accumulations, W m-2 upward) and 10-m wind over the subtropical OCEAN 10-40 N/S,
day 1 every 3 h of the 3 screen starts. GitHub 'sfx truth' -> data/cyclone/wx/sfx_truth3.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
out = {}
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    for h in range(1, 25, 3):
        t = np.datetime64(s + 'T00') + np.timedelta64(h, 'h'); g = lambda k: A[k].sel(time=t, latitude=slice(40, -40)).values
        la = A.latitude.sel(latitude=slice(40, -40)).values; m = (g('land_sea_mask') < 0.5) & (np.abs(la) >= 10)[:, None]
        W = np.cos(np.radians(la))[:, None] * np.ones(m.shape); f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 2)
        out[f'{s}_{h}'] = dict(H=f(-g('surface_sensible_heat_flux') / 3600), LE=f(-g('surface_latent_heat_flux') / 3600), u10=f(np.hypot(g('10m_u_component_of_wind'), g('10m_v_component_of_wind'))),
                              blh=f(g('boundary_layer_height')), cbh=f(np.nan_to_num(g('cloud_base_height'), nan=0.0)), cbh_frac=f(np.isfinite(g('cloud_base_height')).astype(float)), cbh_cloudy=round(float(np.nanmean(np.where(m, g('cloud_base_height'), np.nan))), 1))
        print(s, h, out[f'{s}_{h}'], flush=True)
out['mean'] = {k: round(float(np.mean([v[k] for v in out.values()])), 2) for k in ('H', 'LE', 'u10', 'blh', 'cbh_cloudy', 'cbh_frac')}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/sfx_truth3.json', 'w'), indent=1)
