"""Case studies, set-up run.
1. Probe the Copernicus Climate Data Store (ERA5) with the ECMWF key.   2. Climate indices (MJO, Nino 3.4, IOD).
3. IMD gridded daily rain over Tamil Nadu 2000-2025 (to rank every big day).   4. ERA5 monthly climatology 1991-2020
(so a case can be compared with what is normal for that month).   Writes data/cases/era5/prep_status.json."""
import json, os, sys, time, datetime as dt, urllib.request, threading
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_lib import *
LOG = []; ST = os.path.join(OUT, 'prep_status.json'); LOCK = threading.Lock()
def log(*a):
    m = ' '.join(str(x) for x in a); print(m, flush=True)
    with LOCK:
        LOG.append(m[:1500]); json.dump(dict(log=LOG), open(ST, 'w'), indent=1)
log('key present' if KEY else 'NO KEY', len(KEY))
# 1. probe
ok = False
try:
    c = client()
    c.retrieve('reanalysis-era5-single-levels', {'product_type': ['reanalysis'], 'variable': ['mean_sea_level_pressure'],
               'year': ['2015'], 'month': ['12'], 'day': ['01'], 'time': ['00:00'], 'area': [14, 79, 12, 81], 'grid': GRID,
               'data_format': 'grib', 'download_format': 'unarchived'}, '/tmp/probe.grib')
    import pygrib
    m = pygrib.open('/tmp/probe.grib').message(1); log('PROBE OK: ERA5 msl near Chennai 1 Dec 2015 00 UTC =', round(float(m.values.mean()) / 100, 1), 'hPa')
    ok = True
except Exception as e:
    log('PROBE FAILED', repr(e)[:1400])
# 4. climatology (background, only if the probe worked)
def clim():
    try:
        c = client(); F = {}; lat = lon = None
        jobs = [('reanalysis-era5-pressure-levels-monthly-means', v, LEVELS) for v in PL_VARS] + \
               [('reanalysis-era5-single-levels-monthly-means', v, None) for v in SL_VARS + ['total_precipitation']]
        for ds, var, lev in jobs:
            req = {'product_type': ['monthly_averaged_reanalysis'], 'variable': [var], 'year': [str(y) for y in range(1991, 2021)],
                   'month': ['%02d' % m for m in range(1, 13)], 'time': ['00:00'], 'area': AREA, 'grid': GRID,
                   'data_format': 'grib', 'download_format': 'unarchived'}
            if lev: req['pressure_level'] = lev
            fn = f'/tmp/clim_{var}.grib'
            for k in range(3):
                try:
                    c.retrieve(ds, req, fn); break
                except Exception as e:
                    log('clim request failed', var, k, repr(e)[:600]); time.sleep(30)
            else:
                continue
            G = {}
            la, lo = read_grib(fn, G, lambda m: (m.validDate.year, m.validDate.month)); os.remove(fn)
            if la is not None: lat, lon = la, lo
            for k, d in G.items():
                F[k] = np.stack([np.nanmean([d[(y, mo)] for y in range(1991, 2021) if (y, mo) in d], 0) for mo in range(1, 13)])
            log('clim', var, 'done', sorted(G))
        np.savez_compressed(os.path.join('/tmp', 'era5_clim_1991_2020.npz'), lat=lat, lon=lon, **{k: v.astype(np.float32) for k, v in F.items()})
        log('CLIM SAVED', len(F), 'fields')
    except Exception as e:
        log('CLIM FAILED', repr(e)[:1200])
th = threading.Thread(target=clim)
if ok: th.start()
# 2. climate indices
IDX = os.path.join(OUT, 'indices'); os.makedirs(IDX, exist_ok=True)
for name, url in [('rmm.txt', 'http://www.bom.gov.au/climate/mjo/graphics/rmm.74toRealtime.txt'),
                  ('omi.txt', 'https://psl.noaa.gov/mjo/mjoindex/omi.1x.txt'),
                  ('oni.txt', 'https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt'),
                  ('nino34_weekly.txt', 'https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for'),
                  ('dmi_monthly.txt', 'https://psl.noaa.gov/gcos_wgsp/Timeseries/Data/dmi.had.long.data')]:
    for k in range(4):
        try:
            rq = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) tn-rainfall-map research'})
            b = urllib.request.urlopen(rq, timeout=90).read(); open(os.path.join(IDX, name), 'wb').write(b); log('index', name, len(b), 'bytes'); break
        except Exception as e:
            log('index failed', name, k, repr(e)[:300]); time.sleep(10)
# 3. IMD gridded rain over Tamil Nadu, every day 2000-2025
try:
    import imdlib as imd
    os.makedirs('/tmp/imd', exist_ok=True); arrs, days = [], []
    for y in range(2000, 2026):
        try:
            ds = imd.get_data('rain', y, y, fn_format='yearwise', file_dir='/tmp/imd').get_xarray()
            sub = ds['rain'].sel(lat=slice(7.75, 13.75), lon=slice(76.0, 80.5)); v = sub.values.astype(np.float32); v[v < -1] = np.nan
            arrs.append(v); days += [str(x)[:10] for x in sub.time.values]; lat, lon = sub.lat.values, sub.lon.values
            log('IMD', y, v.shape, 'max', float(np.nanmax(v)))
        except Exception as e:
            log('IMD year failed', y, repr(e)[:300])
    R = np.concatenate(arrs); R = np.where(np.isfinite(R), np.round(R * 10), -10)          # tenths of mm; -10 = no data (sea)
    np.savez_compressed(os.path.join(OUT, 'imd_tn_2000_2025.npz'), rain=R.astype(np.int16), scale=0.1,
                        lat=lat, lon=lon, days=np.array(days))
    log('IMD SAVED', len(days), 'days')
except Exception as e:
    log('IMD FAILED', repr(e)[:600])
if ok: th.join()
log('prep finished')
