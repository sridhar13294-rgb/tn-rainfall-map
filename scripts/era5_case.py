"""Case studies: ERA5 reanalysis for each big rain event, from 8 days before the main rain day to 2 days after.
Every 6 hours, 0.5 deg, 0-40N 50-110E.  Pressure levels 925/850/700/500/300/200: wind, height, humidity, temperature,
vertical motion, vorticity, divergence.  Surface: pressure, water vapour, sea temperature, 10 m wind, CAPE, outgoing
longwave, moisture flux.  Plus daily ERA5 rain in IMD's 08:30 IST windows.
Usage: python scripts/era5_case.py LISTFILE   (lines "name YYYY-MM-DD", the date is the day the main rain fell)
Writes /tmp/era5_out/<name>.npz (uploaded to the era5-cases release) and data/cases/era5/<name>.json (log)."""
import json, os, sys, time, datetime as dt, concurrent.futures as cf
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_lib import *
TMP = '/tmp/era5_out'; os.makedirs(TMP, exist_ok=True)
def one(name, day):
    LOG = []
    def log(*a):
        m = ' '.join(str(x) for x in a); print(name, m, flush=True); LOG.append(m[:1200])
        json.dump(dict(name=name, day=str(day), log=LOG), open(os.path.join(OUT, name + '.json'), 'w'), indent=1)
    d0, d1 = day - dt.timedelta(days=8), day + dt.timedelta(days=2)
    c = client(); F = {}; TP = {}; lat = lon = None
    for (y, m, ds) in month_groups(d0, d1):
        base = {'product_type': ['reanalysis'], 'year': [str(y)], 'month': ['%02d' % m], 'day': ['%02d' % d for d in ds],
                'area': AREA, 'grid': GRID, 'data_format': 'grib', 'download_format': 'unarchived'}
        six = ['00:00', '06:00', '12:00', '18:00']
        for ds_name, extra, store in [('reanalysis-era5-pressure-levels', {'variable': PL_VARS, 'pressure_level': LEVELS, 'time': six}, F),
                                      ('reanalysis-era5-single-levels', {'variable': SL_VARS, 'time': six}, F),
                                      ('reanalysis-era5-single-levels', {'variable': ['total_precipitation'], 'time': ['%02d:00' % h for h in range(24)]}, TP)]:
            fn = f'/tmp/{name}_{y}{m:02d}_{len(store)}_{extra["variable"][0][:6]}.grib'
            try:
                t0 = time.time(); retrieve(c, ds_name, dict(base, **extra), fn, log)
                log(ds_name, y, m, 'ok in', int(time.time() - t0), 's', os.path.getsize(fn) // 1000, 'kB')
            except Exception as e:
                log('request failed', ds_name, y, m, repr(e)[:800]); continue
            la, lo = read_grib(fn, store, lambda m: m.validDate.strftime('%Y%m%d%H')); os.remove(fn)
            if la is not None: lat, lon = la, lo
    if not F:
        log('NO DATA'); return
    times = sorted({t for d in F.values() for t in d}); out = dict(lat=lat, lon=lon, times=np.array(times))
    for k, d in F.items():
        a = np.stack([d.get(t, np.full((len(lat), len(lon)), np.nan)) for t in times])
        q, off, s = pack(a); out[k] = q; out[k + '__off'] = off; out[k + '__scale'] = s
    # ERA5 rain in IMD windows: 24 h ending 03 UTC (08:30 IST) on each day; ERA5 hourly tp at time T covers T-1h..T
    tp = TP.get('tp', {}); rd, rr = [], []
    d = d0 + dt.timedelta(days=1)
    while d <= d1:
        hrs = [(dt.datetime(d.year, d.month, d.day, 3) - dt.timedelta(hours=h)).strftime('%Y%m%d%H') for h in range(24)]
        if all(h in tp for h in hrs):
            rd.append(d.isoformat()); rr.append(np.sum([tp[h] for h in hrs], 0))
        d += dt.timedelta(days=1)
    if rr:
        q, off, s = pack(np.stack(rr)); out.update(rain_days=np.array(rd), rain=q, rain__off=off, rain__scale=s)
    fn = os.path.join(TMP, name + '.npz'); np.savez_compressed(fn, **out)
    log('SAVED', len(times), 'times', len(F), 'fields', len(rd), 'rain days', os.path.getsize(fn) // 1000, 'kB')
    import subprocess                                           # upload straight away, so progress shows on the release
    r = subprocess.run(['gh', 'release', 'upload', 'era5-cases', fn, '--clobber'], capture_output=True, text=True)
    if r.returncode == 0: os.remove(fn); log('uploaded')
    else: log('upload failed, will retry at the end', r.stderr[:300])
if __name__ == '__main__':
    todo = []
    for line in open(sys.argv[1]):
        p = line.split('#')[0].split()
        if len(p) >= 2: todo.append((p[0], dt.date.fromisoformat(p[1])))
    try:                                                        # quick check that the data store accepts us before queueing everything
        retrieve(client(), 'reanalysis-era5-single-levels', {'product_type': ['reanalysis'], 'variable': ['mean_sea_level_pressure'], 'year': ['2015'],
                          'month': ['12'], 'day': ['01'], 'time': ['00:00'], 'area': [14, 79, 12, 81], 'grid': GRID, 'data_format': 'grib',
                          'download_format': 'unarchived'}, '/tmp/probe.grib', hours=2.0); print('probe ok', flush=True)
    except Exception as e:
        json.dump(dict(probe_failed=repr(e)[:1500]), open(os.path.join(OUT, 'probe_' + os.path.basename(sys.argv[1]) + '.json'), 'w'), indent=1); sys.exit(1)
    with cf.ThreadPoolExecutor(int(os.environ.get('ERA5_PAR', '3'))) as ex:
        for f in [ex.submit(one, n, d) for n, d in todo]:
            try: f.result()
            except Exception as e: print('case failed', repr(e)[:500], flush=True)
