"""28 Nov (Tracks 5-why): ERA5 deep-layer mean wind (850-200 hPa, pressure-weighted) averaged over the 200-600 km ring around each BEST-TRACK
position, every 12 h from 0 to 72 h, for the 83 storms of tn-r1-cand1. GitHub 'dlm truth' -> data/cyclone/wx/dlm_truth.json"""
import json, os, glob, datetime as dt, numpy as np, xarray as xr
A = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
LEV = [850, 700, 600, 500, 400, 300, 250, 200]; wl = np.gradient(-np.array(LEV, float)); wl = np.abs(wl) / np.abs(wl).sum()
rows = []
for f in sorted(glob.glob('data/cyclone/kaggle/tn-r1-cand1-*/h*.json')): rows += json.load(open(f))
out = {}
for r in rows:
    t0 = dt.datetime.strptime(r['t0'], '%Y-%m-%dT%H'); R = {p[0]: (p[1], p[2]) for p in r['real']}; res = []
    for h in range(0, 73, 12):
        if h not in R: continue
        la, lo = R[h]; lo = lo % 360; t = np.datetime64(t0 + dt.timedelta(hours=h))
        box = dict(latitude=slice(la + 6, la - 6), longitude=slice(lo - 6 / np.cos(np.radians(la)), lo + 6 / np.cos(np.radians(la))))
        u = A['u_component_of_wind'].sel(time=t, level=LEV, **box).values; v = A['v_component_of_wind'].sel(time=t, level=LEV, **box).values
        LA = A.latitude.sel(latitude=box['latitude']).values; LO = A.longitude.sel(longitude=box['longitude']).values; LOm, LAm = np.meshgrid(LO, LA)
        d = np.hypot(LAm - la, ((LOm - lo + 180) % 360 - 180) * np.cos(np.radians(la))) * 111.2; m = (d >= 200) & (d <= 600)
        ud = (u * wl[:, None, None]).sum(0); vd = (v * wl[:, None, None]).sum(0); res.append((h, round(float(ud[m].mean()), 2), round(float(vd[m].mean()), 2)))
    out[r['name'] + '|' + r['t0']] = res; print(r['name'], r['t0'], res[:2], flush=True)
os.makedirs('data/cyclone/wx', exist_ok=True); json.dump(out, open('data/cyclone/wx/dlm_truth.json', 'w'), indent=1)
