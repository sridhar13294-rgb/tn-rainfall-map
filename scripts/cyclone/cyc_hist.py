"""Every Bay of Bengal storm since 1980 (IBTrACS best tracks) plus the ERA5 steering winds around each storm every 12 h,
to train our track model and to find analogues.
Writes data/cyclone/ibtracs_bob.json (tracks) and data/cyclone/steering_era5.json (winds around the storm centre)."""
import json, os, sys, csv, io, time, datetime as dt, urllib.request, concurrent.futures as cf
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, 'data', 'cyclone'); os.makedirs(OUT, exist_ok=True)
URL = 'https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv'
def num(x):
    try: return float(x)
    except Exception: return None
raw = None
for k in range(5):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(URL, headers={'User-Agent': 'tn-rainfall-map'}), timeout=300).read().decode('utf-8', 'replace'); break
    except Exception as e:
        print('ibtracs retry', k, e, flush=True); time.sleep(20)
rows = list(csv.reader(io.StringIO(raw))); head = rows[0]; H = {h: i for i, h in enumerate(head)}
storms = {}
for r in rows[2:]:
    if r[H['BASIN']] != 'NI' or r[H['SUBBASIN']] != 'BB': continue
    season = int(r[H['SEASON']])
    if season < 1980: continue
    t = r[H['ISO_TIME']]
    if t[11:13] not in ('00', '06', '12', '18') or t[14:16] != '00': continue
    sid = r[H['SID']]
    wind = next((num(r[H[c]]) for c in ('NEWDELHI_WIND', 'WMO_WIND', 'USA_WIND') if c in H and num(r[H[c]]) is not None), None)
    pres = next((num(r[H[c]]) for c in ('NEWDELHI_PRES', 'WMO_PRES', 'USA_PRES') if c in H and num(r[H[c]]) is not None), None)
    s = storms.setdefault(sid, dict(sid=sid, name=r[H['NAME']], season=season, pts=[]))
    s['pts'].append([t[:13].replace(' ', 'T'), num(r[H['LAT']]), num(r[H['LON']]), wind, pres, num(r[H['DIST2LAND']]), num(r[H['LANDFALL']]),
                     r[H['NEWDELHI_GRADE']] if 'NEWDELHI_GRADE' in H else ''])
json.dump(list(storms.values()), open(os.path.join(OUT, 'ibtracs_bob.json'), 'w'), separators=(',', ':'))
print('storms', len(storms), flush=True)
# ERA5 steering winds at 00/12 UTC points (Google's public ARCO-ERA5 copy)
import xarray as xr
DS = xr.open_zarr('gs://gcp-public-data-arco-era5/ar/full_37-1h-0p25deg-chunk-1.zarr-v3', storage_options={'token': 'anon'}, chunks=None)
LEV = [925, 850, 700, 500, 400, 300, 250, 200]
lat = DS.latitude.values; lon = DS.longitude.values
la_sel = (lat >= -5) & (lat <= 35); lo_sel = (lon >= 65) & (lon <= 110)
LA, LO = np.meshgrid(lat[la_sel], lon[lo_sel], indexing='ij')
need = {}
for s in storms.values():
    for p in s['pts']:
        if p[0][11:13] in ('00', '12') and p[1] is not None and p[1] <= 25 and (p[3] or 0) >= 17:
            need.setdefault(p[0], []).append((s['sid'], p[1], p[2]))
times = sorted(need); print('times', len(times), flush=True)
def read(var, t):
    for k in range(5):
        try:
            x = DS[var].sel(time=np.datetime64(t)).sel(level=LEV)
            return x.values[:, la_sel][:, :, lo_sel].astype(np.float32)
        except Exception as e:
            err = e; time.sleep(5 * (k + 1))
    raise err
def job(t):
    try:
        U = read('u_component_of_wind', t); V = read('v_component_of_wind', t)
    except Exception as e:
        return []
    out = []
    for sid, la, lo in need[t]:
        d = np.hypot(LA - la, (LO - lo) * np.cos(np.radians(la)))
        w = np.cos(np.radians(LA))
        rec = dict(sid=sid, t=t, lat=la, lon=lo)
        for name, (r0, r1) in (('ann', (2, 6)), ('disk', (0, 5)), ('ann2', (3, 7))):
            m = (d >= r0) & (d <= r1); ww = w[m]
            rec[name] = {str(p): [round(float((U[i][m] * ww).sum() / ww.sum()), 2), round(float((V[i][m] * ww).sum() / ww.sum()), 2)] for i, p in enumerate(LEV)}
        out.append(rec)
    return out
res = []; t0 = time.time()
with cf.ThreadPoolExecutor(16) as ex:
    for n, o in enumerate(ex.map(job, times)):
        res += o
        if n % 200 == 0: print('done', n, 'of', len(times), int(time.time() - t0), 's', flush=True)
json.dump(res, open(os.path.join(OUT, 'steering_era5.json'), 'w'), separators=(',', ':'))
print('saved', len(res), flush=True)
