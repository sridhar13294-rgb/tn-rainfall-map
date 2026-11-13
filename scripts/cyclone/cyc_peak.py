"""ERA5 peak-intensity targets for the Stage-1 intensity check (13 Nov rule 1: >= 80 % of the library storms with 0-72 h PEAK intensity
within +-5 hPa of ERA5). For every library storm (data/cyclone/lib_list.json, the hind2 / lib84 set): at its model start time (gen_time,
as hind2) and every 6 h to +72 h, the ERA5 0.25-deg mean-sea-level pressure minimum and 850-hPa wind maximum within 2.5 deg of the
best-track position (same definition as data/cyclone/era5_p3_targets.json 'msl_min'). Peak = min over 0-72 h.
Output: data/cyclone/wx/peak_targets.json. Runs on GitHub Actions (cyclone-wx.yml, commit message 'peak truth')."""
import json, os, sys, datetime as dt, numpy as np, xarray as xr
class O:                                                                                          # same definitions as analysis/ourens.py (which needs matplotlib)
    LIBL = json.load(open('data/cyclone/lib_list.json'))
    path_of = staticmethod(lambda s: [(dt.datetime.fromisoformat(p[0]), p[1], p[2], p[3]) for p in s['path'] if p[1] is not None])
    @staticmethod
    def gen_time(s):
        t0 = dt.datetime.strptime(s['t0'], '%Y-%m-%dT%H'); return t0.replace(hour=t0.hour // 6 * 6)
ARCO = 'gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3'
os.makedirs('data/cyclone/wx', exist_ok=True); LOG = open('data/cyclone/wx/peak_log.txt', 'w')
def log(*a): print(*a, flush=True); print(*a, file=LOG, flush=True)
A = xr.open_zarr(ARCO, storage_options={'token': 'anon'}, chunks=None)
def at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])
    return None
out = {}
for s in O.LIBL:
    g = O.gen_time(s); P0 = O.path_of(s); key = f"{s['name']}|{g.strftime('%Y-%m-%dT%H')}"; rows = {}
    for h in range(0, 73, 6):
        t = g + dt.timedelta(hours=h); p = at(P0, t)
        if p is None: continue
        la, lo = p
        try:
            box = dict(latitude=slice(la + 2.5, la - 2.5), longitude=slice((lo - 2.5) % 360, (lo + 2.5) % 360))
            m = A['mean_sea_level_pressure'].sel(time=np.datetime64(t)).sel(**box).values
            u = A['u_component_of_wind'].sel(time=np.datetime64(t), level=850).sel(**box).values; v = A['v_component_of_wind'].sel(time=np.datetime64(t), level=850).sel(**box).values
            rows[str(h)] = dict(msl_min=round(float(np.nanmin(m)) / 100, 2), v850_max=round(float(np.nanmax(np.hypot(u, v))), 2), lat=round(la, 2), lon=round(lo, 2), obs_kt=None)
        except Exception as e: log('fail', key, h, repr(e)[:120])
    if rows:
        out[key] = dict(rows=rows, peak_msl=min(r['msl_min'] for r in rows.values()), hours=max(int(h) for h in rows))
        log(key, 'peak', out[key]['peak_msl'], 'n', len(rows))
json.dump(out, open('data/cyclone/wx/peak_targets.json', 'w'), indent=1); log('peak truth ready', len(out))
