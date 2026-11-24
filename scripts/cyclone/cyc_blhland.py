"""19 Nov (A): ERA5 boundary-layer height over LAND 20-40 N, all longitudes, day 1 hourly (+1..+24 h) of the 3 screen starts: mean of the
hourly means and mean of the per-point daily maximum (same domain/sampling as /tmp landhbl.py). GitHub 'blhland truth' -> data/cyclone/wx/blhland_truth.json"""
import json, os, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
out = {}; box = dict(latitude=slice(40, 20))
for s in ('2020-10-07', '2020-11-01', '2020-11-26'):
    t0 = np.datetime64(s + 'T00'); la = A.latitude.sel(**box).values
    m = A['land_sea_mask'].sel(time=t0, **box).values > 0.5; W = np.cos(np.radians(la))[:, None] * np.ones(m.shape)
    f = lambda X: round(float((np.where(m, X, 0) * W).sum() / (W * m).sum()), 1)
    B = np.array([A['boundary_layer_height'].sel(time=t0 + np.timedelta64(h, 'h'), **box).values for h in range(1, 25)])
    lo = A.longitude.values; lh = (np.arange(1, 25)[:, None] + lo[None, :] / 15.0) % 24          # local hour [24, lon]
    nt = ((lh >= 21) | (lh <= 4))[:, None, :] * np.ones(B.shape, bool); dy = ((lh >= 10) & (lh <= 16))[:, None, :] * np.ones(B.shape, bool)
    bn = np.where(nt, B, 0).sum(0) / np.maximum(nt.sum(0), 1); bd = np.where(dy, B, 0).sum(0) / np.maximum(dy.sum(0), 1)
    out[s] = dict(mean=f(B.mean(0)), max=f(B.max(0)), night=f(bn), day=f(bd))
    for zz in ('10', '100'):                                                                         # 24 Nov: land wind by local hour (drag 5-why)
        W_ = np.array([np.hypot(A[zz + 'm_u_component_of_wind'].sel(time=t0 + np.timedelta64(h, 'h'), **box).values, A[zz + 'm_v_component_of_wind'].sel(time=t0 + np.timedelta64(h, 'h'), **box).values) for h in range(1, 25)])
        out[s]['ws%s_night' % zz] = f(np.where(nt, W_, 0).sum(0) / np.maximum(nt.sum(0), 1)); out[s]['ws%s_day' % zz] = f(np.where(dy, W_, 0).sum(0) / np.maximum(dy.sum(0), 1))
    # 24 Nov: daytime sensible heat flux (ERA5 hourly accumulation J m-2, downward +) -> W m-2 upward
    Hf = -np.array([A['surface_sensible_heat_flux'].sel(time=t0 + np.timedelta64(h, 'h'), **box).values for h in range(1, 25)]) / 3600.0
    out[s]['H_day'] = f(np.where(dy, Hf, 0).sum(0) / np.maximum(dy.sum(0), 1)); out[s]['H_night'] = f(np.where(nt, Hf, 0).sum(0) / np.maximum(nt.sum(0), 1))
    print(s, out[s], flush=True)
out['all'] = {k: round(float(np.mean([v[k] for v in out.values()])), 1) for k in ('mean', 'max', 'night', 'day', 'ws10_night', 'ws10_day', 'ws100_night', 'ws100_day', 'H_day', 'H_night')}
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/blhland4_truth.json', 'w'), indent=1)
