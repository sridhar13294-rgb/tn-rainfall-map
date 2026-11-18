"""17 Nov (P3 core budget reference): ERA5 rain around the storm centre, 0-72 h every 6 h, for the storms of tn-p3core-a/b.
Centre = ERA5 msl minimum within 2.5 deg of the best track (own-centre, as the model budget). Rain = total and convective
precipitation accumulated over the 6 h ending at h, as mm/day, mean within 100 km and within 300 km (fair at T170: compare 300 km).
Output data/cyclone/wx/core_rain.json. GitHub 'core rain'.
18 Nov: also ERA5 inner-core size (radius of max 10-m wind, RMW) and 850-200 hPa shear (500 km box) at each h (rmw add-on)."""
import json, os, datetime as dt, numpy as np, xarray as xr
LIBL = json.load(open('data/cyclone/lib_list.json'))
path_of = lambda s: [(dt.datetime.fromisoformat(p[0]), p[1], p[2], p[3]) for p in s['path'] if p[1] is not None]
def gen_time(s): t0 = dt.datetime.strptime(s['t0'], '%Y-%m-%dT%H'); return t0.replace(hour=t0.hour // 6 * 6)
def at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])
STORMS = ["Madi","Sidr","Phailin","Hudhud","Giri","Sitrang","Nilam","Titli","Dana","Thane","Michaung","Mandous","Nivar","Vardah","Khai-Muk","Montha","Rashmi"]
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
out = {}
for s in LIBL:
    if s['name'] not in STORMS: continue
    g = gen_time(s); P0 = path_of(s); key = f"{s['name']}|{g.strftime('%Y-%m-%dT%H')}"; rows = {}
    for h in range(6, 73, 6):
        t = g + dt.timedelta(hours=h); p = at(P0, t)
        if p is None: continue
        try:
            box = dict(latitude=slice(p[0] + 5, p[0] - 5), longitude=slice((p[1] - 5) % 360, (p[1] + 5) % 360))
            m = A['mean_sea_level_pressure'].sel(time=np.datetime64(t)).sel(**box); la = m.latitude.values; lo = m.longitude.values; mv = m.values
            near = (np.abs(la[:, None] - p[0]) <= 2.5) & (np.abs(lo[None] - p[1]) <= 2.5)
            i = np.argmin(np.where(near, mv, 1e9)); cy, cx = la[i // len(lo)], lo[i % len(lo)]
            d = 111.2 * np.hypot(la[:, None] - cy, (lo[None] - cx) * np.cos(np.radians(cy)))
            r = {}
            for v in ('total_precipitation', 'convective_precipitation'):
                acc = A[v].sel(time=slice(np.datetime64(t - dt.timedelta(hours=5)), np.datetime64(t))).sel(**box).values.sum(0) * 1000.0 * 4  # mm/6h -> mm/day
                r[v[:4] + '_100'] = round(float(acc[d <= 100].mean()), 1); r[v[:4] + '_300'] = round(float(acc[d <= 300].mean()), 1)
            ws = np.hypot(A['10m_u_component_of_wind'].sel(time=np.datetime64(t)).sel(**box).values, A['10m_v_component_of_wind'].sel(time=np.datetime64(t)).sel(**box).values)
            for v, nm in (('surface_sensible_heat_flux', 'sshf'), ('surface_latent_heat_flux', 'slhf')):
                acc = A[v].sel(time=slice(np.datetime64(t - dt.timedelta(hours=5)), np.datetime64(t))).sel(**box).values.mean(0) / -3600.0  # W m-2 upward
                r[nm + '_100'] = round(float(acc[d <= 100].mean()), 1); r[nm + '_300'] = round(float(acc[d <= 300].mean()), 1)
            ws = np.hypot(A['10m_u_component_of_wind'].sel(time=np.datetime64(t)).sel(**box).values, A['10m_v_component_of_wind'].sel(time=np.datetime64(t)).sel(**box).values)
            fx = {v: A[v].sel(time=np.datetime64(t)).sel(**box).values for v in ('sea_surface_temperature', '2m_temperature', '2m_dewpoint_temperature', 'surface_pressure')}
            sea = np.isfinite(fx['sea_surface_temperature']) & (d <= 100)
            e_ = lambda T_: 611.2 * np.exp(17.67 * (T_ - 273.15) / (T_ - 29.65))
            q2 = 0.622 * e_(fx['2m_dewpoint_temperature']) / fx['surface_pressure']; qs = 0.622 * 0.98 * e_(fx['sea_surface_temperature']) / fx['surface_pressure']
            dk = 1004.6 * (fx['sea_surface_temperature'] - fx['2m_temperature']) + 2.5e6 * (qs - q2)
            rho = fx['surface_pressure'] / (287.04 * fx['2m_temperature'] * (1 + 0.61 * q2))
            if sea.any():
                F = r.get('sshf_100', 0) + r.get('slhf_100', 0)
                r.update(fs_V10=round(float(ws[sea].mean()), 2), fs_sst=round(float(fx['sea_surface_temperature'][sea].mean()), 2),
                         fs_dk=round(float(dk[sea].mean()), 0), fs_Ck=round(float(F / max((rho * ws * dk)[sea].mean(), 1e-6)), 5))
            r['vmax10'] = round(float(ws[d <= 300].max()), 1); r['rmw'] = round(float(d[d <= 300][np.argmax(ws[d <= 300])]), 0)
            sh = {}
            for lv in (850, 200):
                for c in ('u', 'v'): sh[c + str(lv)] = float(A[c + '_component_of_wind'].sel(time=np.datetime64(t), level=lv).sel(**box).values[d <= 500].mean())
            r['shear'] = round(float(np.hypot(sh['u200'] - sh['u850'], sh['v200'] - sh['v850'])), 1)
            rows[str(h)] = dict(r, lat=round(float(cy), 2), lon=round(float(cx), 2), msl=round(float(mv.flat[i]) / 100, 1))
        except Exception as e: print('fail', key, h, repr(e)[:120], flush=True)
    out[key] = rows; print(key, {h: (v['tota_300'], v['conv_300']) for h, v in rows.items()}, flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/core_rain.json', 'w'), indent=1); print('core rain ready', len(out))
