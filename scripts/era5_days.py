"""Every NE-monsoon day, for testing warning signs: ERA5 at 00 and 12 UTC, 1 deg, 0-40N 50-110E, 23 Sep - 31 Dec of
one year.  Pressure levels 925/850/700/500/200: wind, height, humidity (q and RH), vertical motion.  Surface: pressure,
water vapour, sea temperature, CAPE, moisture flux, outgoing longwave.  Usage: python scripts/era5_days.py YEAR
Writes /tmp/era5_out/days_YEAR.npz (uploaded to the era5-cases release) and data/cases/era5/days_YEAR.json (log)."""
import json, os, sys, time, datetime as dt, concurrent.futures as cf
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from era5_lib import *
YEAR = int(sys.argv[1]); TMP = '/tmp/era5_out'; os.makedirs(TMP, exist_ok=True); LOG = []
def log(*a):
    m = ' '.join(str(x) for x in a); print(m, flush=True); LOG.append(m[:1200])
    json.dump(dict(year=YEAR, log=LOG), open(os.path.join(OUT, f'days_{YEAR}.json'), 'w'), indent=1)
PL = ['u_component_of_wind', 'v_component_of_wind', 'geopotential', 'specific_humidity', 'vertical_velocity', 'relative_humidity']
LV = ['200', '500', '700', '850', '925']
SL = ['mean_sea_level_pressure', 'total_column_water_vapour', 'sea_surface_temperature', 'convective_available_potential_energy',
      'vertical_integral_of_eastward_water_vapour_flux', 'vertical_integral_of_northward_water_vapour_flux', 'top_net_thermal_radiation']
def job(args):
    m, ds, kind = args; c = client()
    base = {'product_type': ['reanalysis'], 'year': [str(YEAR)], 'month': ['%02d' % m], 'day': ['%02d' % d for d in ds], 'time': ['00:00', '12:00'],
            'area': AREA, 'grid': [1.0, 1.0], 'data_format': 'grib', 'download_format': 'unarchived'}
    if kind == 'pl': req = dict(base, variable=PL, pressure_level=LV); name = 'reanalysis-era5-pressure-levels'
    else: req = dict(base, variable=SL); name = 'reanalysis-era5-single-levels'
    fn = f'/tmp/days_{YEAR}_{m}_{kind}.grib'
    for k in range(4):
        try:
            t0 = time.time(); c.retrieve(name, req, fn); log(kind, m, 'ok', int(time.time() - t0), 's'); break
        except Exception as e:
            log('failed', kind, m, k, repr(e)[:600]); time.sleep(60)
    else:
        return {}, None, None
    F = {}; la, lo = read_grib(fn, F, lambda g: g.validDate.strftime('%Y%m%d%H')); os.remove(fn)
    return F, la, lo
jobs = [(m, ds, kind) for (y, m, ds) in month_groups(dt.date(YEAR, 9, 23), dt.date(YEAR, 12, 31)) for kind in ('pl', 'sl')]
F = {}; lat = lon = None
with cf.ThreadPoolExecutor(int(os.environ.get('ERA5_PAR', '3'))) as ex:
    for f, la, lo in ex.map(job, jobs):
        if la is not None: lat, lon = la, lo
        for k, d in f.items(): F.setdefault(k, {}).update(d)
if not F:
    log('NO DATA'); sys.exit(1)
times = sorted({t for d in F.values() for t in d}); out = dict(lat=lat, lon=lon, times=np.array(times))
for k, d in F.items():
    q, off, s = pack(np.stack([d.get(t, np.full((len(lat), len(lon)), np.nan)) for t in times])); out[k] = q; out[k + '__off'] = off; out[k + '__scale'] = s
np.savez_compressed(os.path.join(TMP, f'days_{YEAR}.npz'), **out)
log('SAVED', len(times), 'times', len(F), 'fields', os.path.getsize(os.path.join(TMP, f'days_{YEAR}.npz')) // 1000, 'kB')
