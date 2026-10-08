"""Forecast builder (experimental) for the Tamil Nadu weather page.

Runs 3x a day on GitHub Actions and reads model output straight from the official open-data servers:
  GFS       NOAA, AWS open data          noaa-gfs-bdp-pds  (0.25 deg, 3-hourly to 384 h)
  ECMWF     ECMWF open data (IFS HRES)   ecmwf-forecasts   (0.25 deg, 3/6-hourly to 360 h)
  ECMWF AI  ECMWF open data (AIFS)       ecmwf-forecasts   (0.25 deg, 6-hourly to 360 h)
  ICON      DWD open data                opendata.dwd.de   (13 km icosahedral, to 180 h)
  GEM       ECCC Datamart (GDPS)         dd.weather.gc.ca  (0.15 deg, 3-hourly to 240 h)

Output:
  - daily rain, max/min temperature, max wind and wind direction on a 0.25 deg Tamil Nadu grid,
    per model and as the average of the models that cover the day. A forecast "day" is
    00 UTC to 00 UTC (05:30 to 05:30 IST), because every model has output at 00 UTC.
  - GFS wind at 10 m and 925/850/700/500/200 hPa, every 6 h for 7 days, 1 deg grid, 0-25N 65-95E.
  - site/forecast.html (from site/forecast_template.html) and data/forecast_status.json.
"""
import bz2, concurrent.futures as cf, datetime as dt, json, math, os, random, re, sys, threading, time, traceback
import urllib.error, urllib.request

import numpy as np

try:
    import eccodes
except ImportError:          # allows the pure-python parts to be tested without eccodes
    eccodes = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
UTC, IST = dt.timezone.utc, dt.timezone(dt.timedelta(hours=5, minutes=30))
UA = 'tn-rainfall-map forecast (non-commercial; github.com/sridhar13294-rgb/tn-rainfall-map)'
T_START = time.time()
DEADLINE = T_START + 62 * 60
BUDGET = {'GFS': 9, 'ECMWF': 6, 'ECMWF AI': 4, 'ICON': 8, 'GEM': 8, 'GEFS': 12, 'ECMWF ENS': 14}   # minutes per model
NDAYS = 16
LEVELS = ['10m', '925', '850', '700', '500', '200']           # page keys: 10m and hPa levels
WIND_BOX = dict(lat0=0, lat1=25, lon0=65, lon1=95, step=1.0)
LAND_URL = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson'
LOCK = threading.RLock()


class NotFound(Exception):
    pass


# ------------------------------------------------------------------ network
CURRENT = {'deadline': DEADLINE}


def http(url, rng=None, tries=5, timeout=60, method='GET'):
    last = None
    for i in range(tries):
        if time.time() > min(DEADLINE, CURRENT['deadline']):
            raise RuntimeError('time budget used up')
        h = {'User-Agent': UA}
        if rng:
            h['Range'] = f'bytes={rng[0]}-' + ('' if rng[1] is None else str(rng[1]))
        try:
            req = urllib.request.Request(url, headers=h, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read() if method == 'GET' else b''
        except urllib.error.HTTPError as e:
            if e.code in (403, 404, 410):
                raise NotFound(f'{e.code} {url}')
            last = f'HTTP {e.code}'
            if e.code in (429, 503):                  # server asks us to slow down: back off harder
                time.sleep(min(30, 3 * 2 ** i) + random.uniform(0, 3)); continue
        except Exception as e:
            last = repr(e)
        time.sleep(4 * (i + 1))
    raise RuntimeError(f'{last} for {url}')


def exists(url):
    try:
        http(url, method='HEAD', tries=2, timeout=40)
        return True
    except NotFound:
        return False
    except Exception:
        try:                                   # some servers dislike HEAD
            http(url, rng=(0, 0), tries=1, timeout=40)
            return True
        except Exception:
            return False


# ------------------------------------------------------------------ GRIB decoding and sampling
INFO_KEYS = ['shortName', 'units', 'gridType', 'typeOfLevel', 'level', 'Ni', 'Nj', 'numberOfDataPoints',
             'latitudeOfFirstGridPointInDegrees', 'longitudeOfFirstGridPointInDegrees',
             'iDirectionIncrementInDegrees', 'jDirectionIncrementInDegrees', 'iScansNegatively', 'jScansPositively',
             'missingValue']


def decode(buf):
    if buf[:3] == b'BZh':
        buf = bz2.decompress(buf)
    h = eccodes.codes_new_from_message(buf)
    try:
        info = {}
        for k in INFO_KEYS:
            try:
                info[k] = eccodes.codes_get(h, k)
            except Exception:
                pass
        try:
            eccodes.codes_set(h, 'stepUnits', 'h')
        except Exception:
            pass
        try:
            info['stepRange'] = str(eccodes.codes_get(h, 'stepRange', str))
        except Exception:
            info['stepRange'] = None
        vals = np.asarray(eccodes.codes_get_values(h), dtype=float)
    finally:
        eccodes.codes_release(h)
    mv = info.get('missingValue', 9999)
    vals[vals == mv] = np.nan
    return info, vals


def step_range(info):
    """'0-6' -> (0, 6); '6' -> (None, 6)."""
    s = info.get('stepRange') or ''
    m = re.fullmatch(r'(\d+)-(\d+)', s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return (None, int(s)) if s.isdigit() else (None, None)


_wcache = {}


def ll_weights(info, lons, lats, key):
    """Bilinear weights for a regular lat-lon grid."""
    geom = (info['Ni'], info['Nj'], info['latitudeOfFirstGridPointInDegrees'], info['longitudeOfFirstGridPointInDegrees'],
            info['iDirectionIncrementInDegrees'], info['jDirectionIncrementInDegrees'],
            info.get('iScansNegatively', 0), info.get('jScansPositively', 0), key)
    with LOCK:
        if geom in _wcache:
            return _wcache[geom]
    ni, nj, la1, lo1, di, dj, ineg, jpos, _ = geom
    lons, lats = np.asarray(lons, float), np.asarray(lats, float)
    fi = (((lo1 - lons) if ineg else (lons - lo1)) % 360) / di
    fj = (lats - la1) / (dj if jpos else -dj)
    i0, j0 = np.floor(fi).astype(int), np.floor(fj).astype(int)
    wx, wy = fi - i0, fj - j0
    i1 = (i0 + 1) % ni
    j0 = np.clip(j0, 0, nj - 1); j1 = np.clip(j0 + 1, 0, nj - 1)
    idx = np.stack([j0 * ni + i0, j0 * ni + i1, j1 * ni + i0, j1 * ni + i1])
    w = np.stack([(1 - wx) * (1 - wy), wx * (1 - wy), (1 - wx) * wy, wx * wy])
    with LOCK:
        _wcache[geom] = (idx, w)
    return idx, w


def sample(info, vals, pts, key):
    """Values at points [(lon, lat)] for regular lat-lon grids."""
    if info.get('gridType') != 'regular_ll':
        raise RuntimeError(f"unsupported grid {info.get('gridType')}")
    idx, w = ll_weights(info, [p[0] for p in pts], [p[1] for p in pts], key)
    return np.nansum(vals[idx] * w, axis=0)


# ------------------------------------------------------------------ helpers
def tn_points(geo):
    """0.25 degree points whose 0.25 box overlaps a 0.1 degree Tamil Nadu cell."""
    cells = [(lo + .05, la + .05) for lo, la, _ in geo['cells']]
    pts, la = [], 8.0
    while la <= 13.6:
        lo = 76.25
        while lo <= 80.5:
            if any(abs(cx - lo) <= .15 and abs(cy - la) <= .15 for cx, cy in cells):
                pts.append((round(lo, 2), round(la, 2)))
            lo += .25
        la += .25
    return pts


def wind_points():
    b = WIND_BOX
    lats = [b['lat0'] + k * b['step'] for k in range(int((b['lat1'] - b['lat0']) / b['step']) + 1)]
    lons = [b['lon0'] + k * b['step'] for k in range(int((b['lon1'] - b['lon0']) / b['step']) + 1)]
    return lats, lons, [(lo, la) for la in lats for lo in lons]


BAND_LATS = [-15 + 2.5 * k for k in range(13)]
BAND_LONS = [2.5 * k for k in range(144)]
BAND_PTS = [(lo, la) for la in BAND_LATS for lo in BAND_LONS]
OLR_LATS = [-20 + 2.5 * k for k in range(17)]                  # OMI grid: 20S-20N, 2.5 deg, latitude outer
OLR_PTS = [(lo, la) for la in OLR_LATS for lo in BAND_LONS]


def band_mean(vals_pts):
    """15S-15N average at each 2.5 degree longitude (equal weights, as in the RMM index)."""
    return np.asarray(vals_pts).reshape(len(BAND_LATS), len(BAND_LONS)).mean(axis=0)


def add_850(m, info, step, vals, comp, wpts):
    m.add('u850' if comp == 'u' else 'v850', info, step, sample(info, vals, wpts, 'wind'))
    if comp == 'u':
        m.add('band850', info, step, band_mean(sample(info, vals, BAND_PTS, 'band')))


def floor6(t):
    return t.replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=t.hour % 6)


def candidate_runs(now, cycles, min_age_h):
    t = floor6(now)
    out = []
    for k in range(12):
        r = t - dt.timedelta(hours=6 * k)
        if r.hour in cycles and (now - r).total_seconds() >= min_age_h * 3600:
            out.append(r)
    return out


class Model:
    """Collects sampled fields for one model run.

    recs['tp']   -> list of (start_step, end_step, values)  accumulated precipitation (mm)
    recs['t2']   -> list of (step, values)                  2 m temperature (degC)
    recs['tmax'] -> list of (start_step, end_step, values)  window maximum (degC); same for 'tmin'
    recs['u10'], recs['v10'] -> list of (step, values)      10 m wind (m/s)
    recs['msl']  -> list of (step, values over the wind/pressure region)  mean sea-level pressure (hPa)
    """

    def __init__(self, name):
        self.name, self.run = name, None
        self.recs = {k: [] for k in ('tp', 't2', 'tmax', 'tmin', 'u10', 'v10', 'msl', 'u850', 'v850', 'band850', 'olr', 'ttr')}
        self.ok = self.failed = 0
        self.errors, self.samples, self.info = [], {}, {}
        self.bytes = 0

    def err(self, msg):
        with LOCK:
            PROGRESS[self.name] = f'ok {self.ok} failed {self.failed + 1}'
            self.failed += 1
            if len(self.errors) < 8:
                self.errors.append(msg[:300])

    def add(self, var, info, step, vals_pts):
        lo, hi = step_range(info)
        end = hi if hi is not None else step
        if var in ('t2', 'tmax', 'tmin'):
            if np.nanmean(vals_pts) > 150:       # Kelvin
                vals_pts = vals_pts - 273.15
        if var == 'msl' and np.nanmean(vals_pts) > 2000:   # Pa -> hPa
            vals_pts = vals_pts / 100.0
        if var == 'tp' and (info.get('units') or '') == 'm':
            vals_pts = vals_pts * 1000.0
        with LOCK:
            self.ok += 1
            PROGRESS[self.name] = f'ok {self.ok} failed {self.failed}'
            if var not in self.samples:
                self.samples[var] = {k: (v if isinstance(v, (int, float, str)) or v is None else str(v))
                                     for k, v in info.items() if k in ('shortName', 'units', 'gridType', 'stepRange',
                                                                       'typeOfLevel', 'level', 'Ni', 'Nj', 'numberOfDataPoints')}
            if var in ('tp', 'tmax', 'tmin', 'olr', 'ttr'):
                start = lo if lo is not None else (0 if var in ('tp', 'ttr') else end - 6)
                self.recs[var].append((start, end, vals_pts))
            else:
                self.recs[var].append((step, vals_pts))


def run_tasks(pool, tasks):
    """tasks: list of callables; runs them, swallowing (but recording) errors inside each task."""
    futs = [pool.submit(t) for t in tasks]
    for f in cf.as_completed(futs):
        f.result()


PROGRESS = {}


def heartbeat(stop):
    while not stop.wait(30):
        try:
            with LOCK:
                snap = dict(PROGRESS, elapsed_s=round(time.time() - T_START))
            json.dump(snap, open(P('data/forecast_progress.json'), 'w'), indent=1, default=str)
        except Exception:
            pass


# ------------------------------------------------------------------ steps needed
def needed(run, d0, ndays):
    """Forecast steps (h) of this run that fall inside [d0 00Z, d0+ndays 00Z]."""
    s0 = int((d0 - run).total_seconds() // 3600)
    return s0, s0 + 24 * ndays


# ------------------------------------------------------------------ GFS (NOAA, AWS)
GFS = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com'


def gfs_url(run, step):
    return f"{GFS}/gfs.{run:%Y%m%d}/{run:%H}/atmos/gfs.t{run:%H}z.pgrb2.0p25.f{step:03d}"


def parse_idx(txt):
    rows = [l.split(':') for l in txt.strip().splitlines() if l.count(':') >= 5]
    out = []
    for k, r in enumerate(rows):
        end = int(rows[k + 1][1]) - 1 if k + 1 < len(rows) else None
        out.append(dict(var=r[3], level=r[4], fc=r[5], start=int(r[1]), end=end))
    return out


def gfs_collect(m, pool, pts, wpts, d0, now, wind_out):
    for run in candidate_runs(now, (0, 6, 12, 18), 3.5):
        if exists(gfs_url(run, 384) + '.idx'):
            break
    else:
        raise RuntimeError('no complete GFS run found')
    m.run = run
    s0, s1 = needed(run, d0, NDAYS)
    steps = [s for s in range(0, 385, 3) if s <= s1]
    wind_steps = [s for s in range(max(0, s0 - s0 % 6), 169, 6)]
    wanted_levels = {'10 m above ground': '10m', '925 mb': '925', '850 mb': '850', '700 mb': '700', '500 mb': '500', '200 mb': '200'}

    def field(step, rec, var, kinds):
        def task():
            try:
                info, vals = decode(http(gfs_url(run, step), (rec['start'], rec['end'])))
                comp = 'u' if rec['var'] == 'UGRD' else 'v'
                if 'msl' in kinds:
                    m.add('msl', info, step, sample(info, vals, wpts, 'wind'))
                if 'olr' in kinds:
                    m.add('olr', info, step, sample(info, vals, OLR_PTS, 'olr'))
                if 'tn' in kinds:
                    m.add(var, info, step, sample(info, vals, pts, 'tn'))
                if 'p850' in kinds:
                    add_850(m, info, step, vals, comp, wpts)
                if 'wind' in kinds:
                    lev = wanted_levels[rec['level']]
                    sw = sample(info, vals, wpts, 'wind')      # computed outside the lock
                    with LOCK:
                        wind_out.setdefault(step, {}).setdefault(lev, {})[comp] = sw
            except Exception as e:
                m.err(f'f{step:03d} {rec["var"]} {rec["level"]}: {e}')
        return task

    def idx_task(step):
        def task():
            try:
                recs = parse_idx(http(gfs_url(run, step) + '.idx').decode())
            except Exception as e:
                m.err(f'idx f{step:03d}: {e}'); return []
            out = []
            in_days = s0 <= step <= s1
            for r in recs:
                if r['var'] == 'TMP' and r['level'] == '2 m above ground' and in_days:
                    out.append(field(step, r, 't2', {'tn'}))
                elif r['var'] == 'PRMSL' and r['level'] == 'mean sea level' and in_days and step % 6 == 0:
                    out.append(field(step, r, 'msl', {'msl'}))
                elif r['var'] == 'ULWRF' and r['level'] == 'top of atmosphere' and in_days and step % 6 == 0 and 'ave' in r['fc']:
                    out.append(field(step, r, 'olr', {'olr'}))
                elif r['var'] == 'APCP' and r['level'] == 'surface' and step % 6 == 0:
                    out.append(field(step, r, 'tp', {'tn'}))
                elif r['var'] in ('TMAX', 'TMIN') and r['level'] == '2 m above ground' and in_days and step % 6 == 0:
                    out.append(field(step, r, r['var'].lower(), {'tn'}))
                elif r['var'] in ('UGRD', 'VGRD') and r['level'] in wanted_levels:
                    is10 = r['level'] == '10 m above ground'
                    kinds = set()
                    if is10 and in_days and step % 6 == 0:
                        kinds.add('tn')
                    if step in wind_steps:
                        kinds.add('wind')
                    if r['level'] == '850 mb' and in_days and step % 6 == 0:
                        kinds.add('p850')
                    if kinds:
                        out.append(field(step, r, 'u10' if r['var'] == 'UGRD' else 'v10', kinds))
            return out
        return task

    idx_futs = [pool.submit(idx_task(s)) for s in steps]
    tasks = []
    for f in cf.as_completed(idx_futs):
        tasks += f.result()
    run_tasks(pool, tasks)


# ------------------------------------------------------------------ ECMWF IFS and AIFS (open data)
ECMWF_BASES = ['https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com',
               'https://data.ecmwf.int/forecasts',
               'https://ai4edataeuwest.blob.core.windows.net/ecmwf']


def ec_fetch(bases, url_fn, rng, salt):
    """Byte-range download spread across all mirrors that hold the run (load balancing), with failover."""
    order = bases[salt % len(bases):] + bases[:salt % len(bases)]
    last = None
    for k, b in enumerate(order):
        try:
            return http(url_fn(b) + '.grib2', rng, tries=3 if k == 0 else 2)
        except Exception as e:
            last = e
    raise RuntimeError(f'all mirrors failed: {last}')


def ec_index(bases, url_fn):
    last = None
    for b in bases:
        try:
            return [json.loads(l) for l in http(url_fn(b) + '.index', tries=3).decode().splitlines() if l.strip()]
        except Exception as e:
            last = e
    raise RuntimeError(f'index unavailable on all mirrors: {last}')


def ec_url(base, model, run, step):
    return f"{base}/{run:%Y%m%d}/{run:%H}z/{model}/0p25/oper/{run:%Y%m%d%H}0000-{step}h-oper-fc"


def ec_collect(m, pool, pts, wpts, d0, now, model):
    full = 360
    steps_all = (list(range(0, 145, 3)) + list(range(150, 361, 6))) if model == 'ifs' else list(range(0, 361, 6))
    cycles = (0, 12) if model == 'ifs' else (0, 6, 12, 18)
    chosen = None
    for run in candidate_runs(now, cycles, 5):
        bases = [b for b in ECMWF_BASES if exists(ec_url(b, model, run, full) + '.index')]
        if bases:
            chosen = (run, bases); break
    if not chosen:
        raise RuntimeError(f'no complete {model} run found')
    run, bases = chosen
    base = bases[0]
    m.run, m.info['mirrors'] = run, bases
    s0, s1 = needed(run, d0, NDAYS)
    steps = [s for s in steps_all if s <= s1]

    def field(step, rec, var):
        def task():
            try:
                rng = (rec['_offset'], rec['_offset'] + rec['_length'] - 1)
                info, vals = decode(ec_fetch(bases, lambda b: ec_url(b, model, run, step), rng, step + rec['_offset']))
                if var == 'msl':
                    m.add(var, info, step, sample(info, vals, wpts, 'wind'))
                elif var in ('u850', 'v850'):
                    add_850(m, info, step, vals, var[0], wpts)
                elif var == 'ttr':
                    m.add(var, info, step, sample(info, vals, OLR_PTS, 'olr'))
                else:
                    m.add(var, info, step, sample(info, vals, pts, 'tn'))
            except Exception as e:
                m.err(f'{step}h {rec.get("param")}: {e}')
        return task

    params_seen = set()

    def idx_task(step):
        def task():
            try:
                recs = ec_index(bases, lambda b: ec_url(b, model, run, step))
            except Exception as e:
                m.err(f'index {step}h: {e}'); return []
            out = []
            in_days = s0 <= step <= s1
            for r in recs:
                p, lt = r.get('param'), r.get('levtype')
                if lt == 'pl' and str(r.get('levelist')) == '850' and p in ('u', 'v') and in_days and step % 6 == 0:
                    out.append(field(step, r, p + '850'))
                    continue
                if lt != 'sfc':
                    continue
                with LOCK:
                    params_seen.add(p)
                if p == 'tp' and step % 6 == 0:
                    out.append(field(step, r, 'tp'))
                elif p == 'msl' and in_days and step % 6 == 0:
                    out.append(field(step, r, 'msl'))
                elif p == 'ttr' and (run + dt.timedelta(hours=step)).hour == 0 and step >= s0:
                    out.append(field(step, r, 'ttr'))
                elif p == '2t' and in_days:
                    out.append(field(step, r, 't2'))
                elif p in ('mx2t3', 'mx2t6') and in_days:
                    out.append(field(step, r, 'tmax'))
                elif p in ('mn2t3', 'mn2t6') and in_days:
                    out.append(field(step, r, 'tmin'))
                elif p in ('10u', '10v') and in_days and step % 6 == 0:
                    out.append(field(step, r, 'u10' if p == '10u' else 'v10'))
            return out
        return task

    idx_futs = [pool.submit(idx_task(s)) for s in steps]
    tasks = []
    for f in cf.as_completed(idx_futs):
        tasks += f.result()
    m.info['sfc_params'] = sorted(params_seen)
    run_tasks(pool, tasks)


# ------------------------------------------------------------------ ICON (DWD)
DWD = 'https://opendata.dwd.de/weather/nwp/icon/grib'


def icon_url(run, var, step):
    return f"{DWD}/{run:%H}/{var}/icon_global_icosahedral_single-level_{run:%Y%m%d%H}_{step:03d}_{var.upper()}.grib2.bz2"


_icon_grid = {}


def icon_neighbours(run, pts, name, box):
    """4 nearest icosahedral cells (inverse-distance weights) for each point; cached in data/."""
    cache = P(f'data/icon_{name}_neighbours.json')
    if os.path.exists(cache):
        c = json.load(open(cache))
        if len(c['idx']) == len(pts):
            return np.array(c['idx']).T, np.array(c['w']).T, c['n']
    if not _icon_grid:
        for v in ('clat', 'clon'):
            url = f"{DWD}/{run:%H}/{v}/icon_global_icosahedral_time-invariant_{run:%Y%m%d%H}_{v.upper()}.grib2.bz2"
            info, vals = decode(http(url))
            if np.nanmax(np.abs(vals)) < 3.3:
                vals = np.degrees(vals)
            _icon_grid[v] = vals
    lat, lon = _icon_grid['clat'], _icon_grid['clon']
    la0, la1, lo0, lo1 = box
    sel = np.where((lat > la0) & (lat < la1) & (lon > lo0) & (lon < lo1))[0]
    slat, slon = lat[sel], lon[sel]
    idx, w = [], []
    for lo, la in pts:
        near = np.where((np.abs(slat - la) < .4) & (np.abs(slon - lo) < .4))[0]
        d = np.hypot((slon[near] - lo) * math.cos(math.radians(la)), slat[near] - la)
        k = np.argsort(d)[:4]
        ww = 1 / np.maximum(d[k], 1e-4) ** 2
        idx.append([int(i) for i in sel[near[k]]]); w.append([float(x) for x in ww / ww.sum()])
    json.dump({'n': int(len(lat)), 'idx': idx, 'w': w}, open(cache, 'w'))
    return np.array(idx).T, np.array(w).T, int(len(lat))


def icon_collect(m, pool, pts, wpts, d0, now):
    for run in candidate_runs(now, (0, 12), 3.5):
        if exists(icon_url(run, 't_2m', 180)):
            break
    else:
        raise RuntimeError('no complete ICON run found')
    m.run = run
    s0, s1 = needed(run, d0, NDAYS)
    idx, w, n = icon_neighbours(run, pts, 'tn', (7.4, 14.3, 75.7, 81.0))
    ridx, rw, _ = icon_neighbours(run, wpts, 'region', (-1.5, 26.5, 63.5, 96.5))
    m.info['cells'] = n
    steps = [s for s in list(range(0, 79, 3)) + list(range(81, 181, 3)) if s0 <= s <= s1]

    def field(var, step, tag):
        def task():
            try:
                info, vals = decode(http(icon_url(run, var, step)))
                if len(vals) != n:
                    raise RuntimeError(f'grid size {len(vals)} != {n}')
                if tag == 'msl':
                    m.add(tag, info, step, np.sum(vals[ridx] * rw, axis=0))
                else:
                    m.add(tag, info, step, np.sum(vals[idx] * w, axis=0))
            except Exception as e:
                m.err(f'{var} {step}: {e}')
        return task

    tasks = []
    for s in steps:
        tasks.append(field('t_2m', s, 't2'))
        if s % 6 == 0:
            tasks += [field('u_10m', s, 'u10'), field('v_10m', s, 'v10')]
        if s % 6 == 0 and s > 0:
            tasks.append(field('tot_prec', s, 'tp'))
        if s % 6 == 0:
            tasks.append(field('pmsl', s, 'msl'))
    run_tasks(pool, tasks)


# ------------------------------------------------------------------ GEM (ECCC Datamart)
GEM_PAT = {
    'tp': r'(Precip-Accum|PrecipAccum|APCP_SFC)',
    't2': r'_(AirTemp_AGL-2m|TMP_TGL_2)_',
    'u10': r'_(WindU_AGL-10m|UGRD_TGL_10)_',
    'v10': r'_(WindV_AGL-10m|VGRD_TGL_10)_',
    'msl': r'_(Pressure_MSL|PRMSL_MSL|MSLP|Pressure-MSL|PressureMSL|PRMSL)',
}


def gem_dirs(run):
    return [f"https://dd.weather.gc.ca/{run:%Y%m%d}/WXO-DD/model_gdps/15km/{run:%H}/{{h:03d}}/",
            f"https://dd.weather.gc.ca/today/model_gdps/15km/{run:%H}/{{h:03d}}/",
            f"https://dd.weather.gc.ca/model_gem_global/15km/grib2/lat_lon/{run:%H}/{{h:03d}}/"]


def gem_list(url):
    html = http(url, tries=2, timeout=60).decode('utf-8', 'replace')
    return sorted(set(re.findall(r'href="([^"/?]+\.grib2)"', html)))


def gem_collect(m, pool, pts, wpts, d0, now):
    found = None
    for run in candidate_runs(now, (0, 12), 4):
        for pat in gem_dirs(run):
            try:
                names = gem_list(pat.format(h=240))
            except Exception:
                continue
            if any(re.search(GEM_PAT['t2'], x) for x in names):
                found = (run, pat, names); break
        if found:
            break
    if not found:
        raise RuntimeError('no complete GEM run found')
    run, pat, names240 = found
    m.run, m.info['dir'] = run, pat
    names = {}
    for var, rx in GEM_PAT.items():
        cand = [x for x in names240 if re.search(rx, x) and 'Rate' not in x]
        cand.sort(key=lambda x: ('0.15' not in x and '.15x.15' not in x, len(x)))
        if cand:
            names[var] = cand[0]
    m.info['files_240'] = names
    m.info['listing_sample'] = [x for x in names240 if 'Sfc' in x or 'MSL' in x.upper()][:60] if len(names) < 5 else None
    if 't2' not in names:
        raise RuntimeError('GEM file names not recognised')
    s0, s1 = needed(run, d0, NDAYS)
    steps = [s for s in range(0, 241, 3) if s0 <= s <= s1]

    def field(var, step):
        name = re.sub(r'PT240H', f'PT{step:03d}H', names[var]).replace('_P240', f'_P{step:03d}')
        url = pat.format(h=step) + name

        def task():
            try:
                info, vals = decode(http(url))
                m.add(var, info, step, sample(info, vals, wpts if var == 'msl' else pts, 'wind' if var == 'msl' else 'tn'))
            except Exception as e:
                m.err(f'{var} {step}: {e}')
        return task

    tasks = []
    for s in steps:
        tasks.append(field('t2', s))
        if s % 6 == 0 and 'u10' in names:
            tasks += [field('u10', s), field('v10', s)]
        if 'tp' in names and s > 0 and s % 6 == 0:
            tasks.append(field('tp', s))
        if 'msl' in names and s % 6 == 0:
            tasks.append(field('msl', s))
    run_tasks(pool, tasks)


# ------------------------------------------------------------------ daily aggregation
def cumulative(tp_recs):
    """Chain accumulation records into cumulative totals since the run start: {end_step: values}."""
    C = {0: None}
    recs = sorted(tp_recs, key=lambda r: (r[1], r[1] - r[0]))
    progress = True
    while progress:
        progress = False
        for a, b, v in recs:
            if b in C:
                continue
            if a == 0:
                C[b] = v; progress = True
            elif a in C and C[a] is not None:
                C[b] = C[a] + v; progress = True
    return C


def daily(m, d0, ndays, npts):
    """Per-day arrays for one model: dict var -> list (per day) of arrays or None."""
    out = {k: [None] * ndays for k in ('rain', 'tmax', 'tmin', 'wmax', 'wdir')}
    if m.run is None:
        return out
    C = cumulative(m.recs['tp'])
    zero = np.zeros(npts)
    t2 = m.recs['t2']; tx = m.recs['tmax']; tn = m.recs['tmin']
    uv = {}
    for s, v in m.recs['u10']:
        uv.setdefault(s, [None, None])[0] = v
    for s, v in m.recs['v10']:
        uv.setdefault(s, [None, None])[1] = v
    for d in range(ndays):
        a = int((d0 + dt.timedelta(days=d) - m.run).total_seconds() // 3600)
        b = a + 24
        if a >= 0 and a in C and b in C:
            ca = zero if a == 0 else C[a]
            cb = C[b]
            if cb is not None and ca is not None:
                out['rain'][d] = np.maximum(cb - ca, 0)
        if a < 0:
            continue
        smp = [v for s, v in t2 if a <= s <= b]
        hi = smp + [v for s, e, v in tx if a < e <= b]
        lo = smp + [v for s, e, v in tn if a < e <= b]
        if len(smp) >= 4 or (len(smp) >= 2 and len(hi) >= 4):
            out['tmax'][d] = np.max(np.stack(hi), axis=0)
            out['tmin'][d] = np.min(np.stack(lo), axis=0)
        w = [(u, v) for s, (u, v) in uv.items() if a <= s <= b and u is not None and v is not None]
        if len(w) >= 3:
            U, V = np.stack([x[0] for x in w]), np.stack([x[1] for x in w])
            out['wmax'][d] = np.max(np.hypot(U, V), axis=0) * 3.6
            out['wdir'][d] = (np.degrees(np.arctan2(-U.mean(0), -V.mean(0))) + 360) % 360
    return out


def six_hourly(m, d0, nper):
    """Rain in each 6-hour period [d0 + 6k h, d0 + 6(k+1) h] for one model."""
    out = [None] * nper
    if m.run is None:
        return out
    C = cumulative(m.recs['tp'])
    for k in range(nper):
        a = int((d0 + dt.timedelta(hours=6 * k) - m.run).total_seconds() // 3600)
        b = a + 6
        if a < 0 or a not in C or b not in C:
            continue
        ca = np.zeros_like(C[b]) if a == 0 else C[a]
        if ca is not None and C[b] is not None:
            out[k] = np.maximum(C[b] - ca, 0)
    return out



# ------------------------------------------------------------------ large-scale drivers (step 2)
PSL = 'https://downloads.psl.noaa.gov/Datasets/ncep.reanalysis.derived/pressure'
OISST = 'https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2.1/access/avhrr'
BOM_RMM = 'https://www.bom.gov.au/clim_data/IDCKGEM000/rmm.74toRealtime.txt'
SST_BOX = dict(lat0=-15, lat1=30, lon0=40, lon1=110, step=0.5)


def _bilinear_ll(field, la_axis, lo_axis, pts):
    """Bilinear interpolation on a regular global grid (la_axis may be descending; lo 0..360)."""
    la_axis, lo_axis = np.asarray(la_axis, float), np.asarray(lo_axis, float)
    dla, dlo = la_axis[1] - la_axis[0], lo_axis[1] - lo_axis[0]
    out = []
    for lo, la in pts:
        fi = ((lo - lo_axis[0]) % 360) / dlo
        fj = (la - la_axis[0]) / dla
        i0, j0 = int(np.floor(fi)), int(np.floor(fj))
        wx, wy = fi - i0, fj - j0
        i1 = (i0 + 1) % len(lo_axis)
        j0 = min(max(j0, 0), len(la_axis) - 1); j1 = min(j0 + 1, len(la_axis) - 1)
        v = (field[j0, i0] * (1 - wx) + field[j0, i1] * wx) * (1 - wy) + (field[j1, i0] * (1 - wx) + field[j1, i1] * wx) * wy
        out.append(float(v))
    return out


def climatology(wpts):
    """NCEP/NCAR reanalysis monthly long-term means: 850 hPa u/v over the region and 15S-15N u850 by longitude."""
    cache = P('data/clim_ncep.json')
    if os.path.exists(cache):
        c = json.load(open(cache))
        if len(c['u850'][0]) == len(wpts):
            return c
    import netCDF4
    c = {}
    for var in ('uwnd', 'vwnd'):
        last = None
        for fn in (f'{var}.mon.ltm.1991-2020.nc', f'{var}.mon.ltm.nc'):
            try:
                buf = http(f'{PSL}/{fn}', timeout=180)
                c['source'] = fn.replace(var, '{var}'); break
            except Exception as e:
                last = e
        else:
            raise RuntimeError(f'NCEP climatology not available: {last}')
        ds = netCDF4.Dataset('mem.nc', memory=buf)
        lev = [int(x) for x in ds['level'][:]]
        la, lo = ds['lat'][:], ds['lon'][:]
        data = np.asarray(ds[var][:, lev.index(850), :, :], float)       # (12, lat, lon)
        key = 'u850' if var == 'uwnd' else 'v850'
        c[key] = [[round(x, 2) for x in _bilinear_ll(data[mth], la, lo, wpts)] for mth in range(12)]
        if var == 'uwnd':
            band = [(lo_, la_) for la_ in BAND_LATS for lo_ in BAND_LONS]
            c['band850'] = [[round(x, 2) for x in band_mean(_bilinear_ll(data[mth], la, lo, band))] for mth in range(12)]
        ds.close()
    json.dump(c, open(cache, 'w'), separators=(',', ':'))
    return c


def clim_on(c, key, day):
    """Monthly climatology linearly interpolated to a date (monthly means taken as valid on the 15th)."""
    y = day.year
    mids = [dt.date(y, m, 15) for m in range(1, 13)]
    if day < mids[0]:
        a, b, ia, ib = dt.date(y - 1, 12, 15), mids[0], 11, 0
    elif day >= mids[11]:
        a, b, ia, ib = mids[11], dt.date(y + 1, 1, 15), 11, 0
    else:
        k = max(i for i in range(12) if mids[i] <= day)
        a, b, ia, ib = mids[k], mids[k + 1], k, k + 1
    w = (day - a).days / (b - a).days
    return np.asarray(c[key][ia]) * (1 - w) + np.asarray(c[key][ib]) * w


def anomalies_850(models, labels, clim, d0, nd):
    """Daily-mean 850 hPa wind anomaly over the region, averaged across models with 850 hPa winds."""
    days, out_u, out_v, mods, band = [], [], [], [], []
    for d in range(nd):
        a_t = d0 + dt.timedelta(days=d)
        us, vs, bs, who = [], [], [], []
        for n in labels:
            m = models[n]
            a = int((a_t - m.run).total_seconds() // 3600)
            if a < 0:
                continue
            want = {a, a + 6, a + 12, a + 18}
            u = {s: v for s, v in m.recs['u850'] if s in want}
            v = {s: x for s, x in m.recs['v850'] if s in want}
            b = {s: x for s, x in m.recs['band850'] if s in want}
            if len(u) == 4 and len(v) == 4:
                us.append(np.mean(list(u.values()), 0)); vs.append(np.mean(list(v.values()), 0)); who.append(n)
                if len(b) == 4:
                    bs.append(np.mean(list(b.values()), 0))
        if not us:
            break
        day = a_t.date()
        du = np.mean(us, 0) - clim_on(clim, 'u850', day)
        dv = np.mean(vs, 0) - clim_on(clim, 'v850', day)
        days.append(day.isoformat()); mods.append(who)
        out_u.append([int(round(x * 10)) for x in du]); out_v.append([int(round(x * 10)) for x in dv])
        band.append([round(float(x), 1) for x in (np.mean(bs, 0) - clim_on(clim, 'band850', day))] if bs else None)
    return dict(days=days, models=mods, u=out_u, v=out_v), band


SST_LTM = 'https://downloads.psl.noaa.gov/Datasets/noaa.oisst.v2.highres/sst.mon.ltm.1991-2020.nc'
SST_BOXES = dict(iod_w=(-10, 10, 50, 70), iod_e=(-10, 0, 90, 110), nino34=(-5, 5, 190, 240), bob=(5, 22, 80, 95), arabian=(5, 22, 60, 75),
                 tropics=(-20, 20, 0, 360))


def _box_mean(f, la, lo, box):
    la0, la1, lo0, lo1 = box
    j = (la >= la0) & (la <= la1); i = (lo >= lo0) & (lo <= lo1)
    sub = f[np.ix_(j, i)]
    w = np.cos(np.radians(la[j]))[:, None] * np.ones((1, int(i.sum())))
    ok = ~np.ma.getmaskarray(sub)
    return float(np.sum(np.where(ok, np.ma.getdata(sub), 0) * w) / np.sum(w * ok))


def _region_half_deg(f, la, lo):
    b = SST_BOX
    j = np.where((la >= b['lat0'] - 1e-6) & (la <= b['lat1'] + 1e-6))[0]
    i = np.where((lo >= b['lon0'] - 1e-6) & (lo <= b['lon1'] + 1e-6))[0]
    nj, ni = (len(j) // 2) * 2, (len(i) // 2) * 2
    sub = f[np.ix_(j[:nj], i[:ni])]
    blk = np.ma.masked_invalid(sub).reshape(nj // 2, 2, ni // 2, 2).mean(axis=(1, 3))
    return blk, dict(lat0=float(la[j[0]] + .125), lon0=float(lo[i[0]] + .125), step=0.5, ny=nj // 2, nx=ni // 2)


def sst_climatology():
    """1991-2020 monthly OISST climatology (NOAA PSL) for the map region and the index boxes; cached."""
    cache = P('data/sst_clim_1991_2020.json')
    if os.path.exists(cache):
        c = json.load(open(cache))
        if all(k in c['boxes'][0] for k in SST_BOXES):
            return c
    import netCDF4
    ds = netCDF4.Dataset('ltm.nc', memory=http(SST_LTM, timeout=300))
    la, lo = np.asarray(ds['lat'][:]), np.asarray(ds['lon'][:])
    c = {'grid': [], 'boxes': []}
    for mth in range(12):
        f = ds['sst'][mth, :, :]
        blk, geom = _region_half_deg(f, la, lo)
        c['grid'].append([None if np.ma.is_masked(x) else round(float(x), 2) for x in np.ma.ravel(blk)])
        c['boxes'].append({k: round(_box_mean(f, la, lo, bx), 3) for k, bx in SST_BOXES.items()})
    c['geom'] = geom
    ds.close()
    json.dump(c, open(cache, 'w'), separators=(',', ':'))
    return c


def _clim_month_weights(day):
    y = day.year
    mids = [dt.date(y, m, 15) for m in range(1, 13)]
    if day < mids[0]:
        a, b, ia, ib = dt.date(y - 1, 12, 15), mids[0], 11, 0
    elif day >= mids[11]:
        a, b, ia, ib = mids[11], dt.date(y + 1, 1, 15), 11, 0
    else:
        k = max(i for i in range(12) if mids[i] <= day)
        a, b, ia, ib = mids[k], mids[k + 1], k, k + 1
    w = (day - a).days / (b - a).days
    return ia, ib, w


def sst_latest(status):
    """Latest NOAA OISST v2.1 daily SST over the Indian Ocean as an anomaly against the 1991-2020 climatology,
    plus IOD, Nino 3.4, Bay of Bengal and Arabian Sea indices (history kept in data/sst_indices.json)."""
    import netCDF4
    clim = sst_climatology()
    today = dt.datetime.now(UTC).date()
    hist_path = P('data/sst_indices.json')
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else {}
    if hist and 'nino34_rel' not in next(iter(hist.values())):
        hist = {}                                   # drop values made with the old 1971-2000 base

    def load(day):
        for suffix in ('_preliminary', ''):
            url = f"{OISST}/{day:%Y%m}/oisst-avhrr-v02r01.{day:%Y%m%d}{suffix}.nc"
            try:
                return netCDF4.Dataset('sst.nc', memory=http(url, tries=2, timeout=120)), url
            except NotFound:
                continue
        return None, None

    def indices(sst, la, lo, day):
        ia, ib, w = _clim_month_weights(day)
        cb = {k: clim['boxes'][ia][k] * (1 - w) + clim['boxes'][ib][k] * w for k in SST_BOXES}
        v = {k: _box_mean(sst, la, lo, bx) - cb[k] for k, bx in SST_BOXES.items()}
        return dict(iod=round(v['iod_w'] - v['iod_e'], 2), nino34=round(v['nino34'], 2), bob=round(v['bob'], 2),
                    arabian=round(v['arabian'], 2), tropics=round(v['tropics'], 2),
                    nino34_rel=round(v['nino34'] - v['tropics'], 2), base='1991-2020')

    latest = None
    for back in range(1, 8):
        day = today - dt.timedelta(days=back)
        ds, url = load(day)
        if ds is None:
            continue
        sst = ds['sst'][0, 0, :, :]; la = np.asarray(ds['lat'][:]); lo = np.asarray(ds['lon'][:])
        status['sst_file_anom_note'] = str(getattr(ds['anom'], 'long_name', '')) + ' | ' + str(getattr(ds, 'climatology', getattr(ds['anom'], 'comment', '')))[:160]
        hist[day.isoformat()] = indices(sst, la, lo, day)
        blk, geom = _region_half_deg(sst, la, lo)
        ia, ib, w = _clim_month_weights(day)
        g1, g2 = clim['grid'][ia], clim['grid'][ib]
        grid = []
        for k, x in enumerate(np.ma.ravel(blk)):
            if np.ma.is_masked(x) or g1[k] is None or g2[k] is None:
                grid.append(-999)
            else:
                grid.append(int(round((float(x) - (g1[k] * (1 - w) + g2[k] * w)) * 10)))
        latest = dict(date=day.isoformat(), anom=grid, source=url.rsplit('/', 1)[1], base='1991-2020', **geom)
        ds.close()
        break
    filled = 0
    for back in range(2, 61):
        day = today - dt.timedelta(days=back)
        if day.isoformat() in hist or filled >= 8:
            continue
        try:
            ds, _ = load(day)
        except Exception:
            ds = None
        if ds is None:
            continue
        hist[day.isoformat()] = indices(ds['sst'][0, 0, :, :], np.asarray(ds['lat'][:]), np.asarray(ds['lon'][:]), day)
        ds.close(); filled += 1
    hist = {k: hist[k] for k in sorted(hist)[-90:]}
    json.dump(hist, open(hist_path, 'w'), indent=0)
    status['sst'] = f"latest {latest['date'] if latest else 'none'}, history {len(hist)} days, base 1991-2020"
    return latest, [dict(date=k, **{x: y for x, y in hist[k].items() if x != 'base'}) for k in sorted(hist)[-60:]]


ROMI = 'https://psl.noaa.gov/mjo/mjoindex/romi.cpcolr.1x.txt'


def rmm_phase(x, y):
    """Wheeler-Hendon phase (1-8) from a point on the RMM phase diagram."""
    ang = math.degrees(math.atan2(y, x)) % 360
    return [5, 6, 7, 8, 1, 2, 3, 4][int(ang // 45) % 8]


def mjo_observed(status):
    """Observed real-time MJO: BoM RMM if reachable, otherwise NOAA PSL real-time OMI (ROMI) in RMM orientation."""
    rows, src = [], None
    try:
        txt = http(BOM_RMM, tries=1, timeout=60).decode('utf-8', 'replace')
        for line in txt.splitlines():
            p = line.split()
            if len(p) >= 7 and p[0].isdigit() and len(p[0]) == 4:
                try:
                    r1, r2, ph, amp = float(p[3]), float(p[4]), int(float(p[5])), float(p[6])
                except ValueError:
                    continue
                if abs(r1) > 100 or abs(amp) > 100:
                    continue
                rows.append(dict(date=f'{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}', rmm1=round(r1, 2), rmm2=round(r2, 2), phase=ph, amp=round(amp, 2)))
        src = 'bom'
    except Exception as e:
        status['mjo_bom'] = f'unavailable: {e}'
    if not rows:
        txt = http(ROMI, timeout=120).decode('utf-8', 'replace')
        for line in txt.splitlines():
            p = line.split()
            if len(p) >= 7 and p[0].isdigit() and len(p[0]) == 4:
                try:
                    pc1, pc2 = float(p[4]), float(p[5])
                except ValueError:
                    continue
                if abs(pc1) > 50 or abs(pc2) > 50:
                    continue
                x, y = pc2, -pc1                     # PSL: OMI PC2 ~ RMM1 and -OMI PC1 ~ RMM2
                rows.append(dict(date=f'{int(p[0]):04d}-{int(p[1]):02d}-{int(p[2]):02d}', rmm1=round(x, 2), rmm2=round(y, 2),
                                 phase=rmm_phase(x, y), amp=round(math.hypot(x, y), 2), pc1=pc1, pc2=pc2))
        src = 'romi'
    status['mjo'] = f"{src}, latest {rows[-1]['date'] if rows else 'none'}"
    return dict(source=src, days=rows[-60:])


def update_band_history(band, d0):
    """Keep day-0 (analysis-like) tropical u850 anomalies so the time-longitude plot has a past as well as a future."""
    path = P('data/mjo_u850_history.json')
    hist = json.load(open(path)) if os.path.exists(path) else {}
    if band and band[0] is not None:
        hist[d0.date().isoformat()] = band[0]
    keep = sorted(hist)[-45:]
    hist = {k: hist[k] for k in keep}
    json.dump(hist, open(path, 'w'), separators=(',', ':'))
    return [dict(date=k, u=hist[k]) for k in keep if k < d0.date().isoformat()]



# ------------------------------------------------------------------ step 3: ensembles when a system is possible
GEFS = 'https://noaa-gefs-pds.s3.amazonaws.com'
ENS_HOURS = 240                      # ensembles are read to day 10
LOW_BOXES = {'Bay of Bengal': (3, 22, 79.5, 95), 'Arabian Sea': (3, 21, 65, 74.5)}


def find_lows(grid, ny, nx, lat0, lon0, step, min_depth=1.5):
    """Closed lows on a regular grid: local minimum over +-2 cells, at least min_depth hPa below the ring 3-4 cells away."""
    g = np.asarray(grid, float).reshape(ny, nx)
    out = []
    for j in range(2, ny - 2):
        for i in range(2, nx - 2):
            v = g[j, i]
            if v > g[j - 2:j + 3, i - 2:i + 3].min() + 1e-9:
                continue
            ring = [g[jj, ii] for jj in range(j - 4, j + 5) for ii in range(i - 4, i + 5)
                    if 0 <= jj < ny and 0 <= ii < nx and max(abs(jj - j), abs(ii - i)) >= 3]
            depth = float(np.mean(ring) - v) if ring else 0
            # sub-grid position of the minimum (parabola through the neighbours)
            cx, cy = g[j, i - 1] - 2 * v + g[j, i + 1], g[j - 1, i] - 2 * v + g[j + 1, i]
            dx = 0.5 * (g[j, i - 1] - g[j, i + 1]) / cx if cx > 1e-6 else 0.0
            dy = 0.5 * (g[j - 1, i] - g[j + 1, i]) / cy if cy > 1e-6 else 0.0
            la, lo = lat0 + (j + max(-.5, min(.5, dy))) * step, lon0 + (i + max(-.5, min(.5, dx))) * step
            basin = next((b for b, (a0, a1, o0, o1) in LOW_BOXES.items() if a0 <= la <= a1 and o0 <= lo <= o1), None)
            if basin and depth >= min_depth:
                out.append((lo, la, round(float(v), 1), round(depth, 1), basin))
    return out


def track_lows(frames, lat0, lon0, ny, nx, step):
    """frames: list of (time_index, grid). Links lows within 4 degrees between consecutive 6-hourly frames;
    keeps tracks lasting at least 3 frames (18 h)."""
    tracks, live = [], []
    for k, grid in frames:
        lows = find_lows(grid, ny, nx, lat0, lon0, step)
        nxt = []
        used = set()
        for tr in live:
            lk, lo, la = tr[-1][0], tr[-1][1], tr[-1][2]
            best = None
            for q, (x, y, pv, dp, b) in enumerate(lows):
                d = math.hypot((x - lo) * math.cos(math.radians(la)), y - la)
                if q not in used and d <= 4 and k - lk <= 2 and (best is None or d < best[0]):
                    best = (d, q)
            if best:
                used.add(best[1]); x, y, pv, dp, b = lows[best[1]]
                tr.append([k, x, y, pv, dp]); nxt.append(tr)
            elif k - lk <= 2:
                nxt.append(tr)
            else:
                if len(tr) >= 3:
                    tracks.append(tr)
        for q, (x, y, pv, dp, b) in enumerate(lows):
            if q not in used and dp >= 2:
                nxt.append([[k, x, y, pv, dp]])
        live = nxt
    tracks += [t for t in live if len(t) >= 3]
    return tracks


def deterministic_lows(models, labels, d0, nframes, wbox):
    """Tracks of lows in each deterministic model's sea-level pressure over the first 10 days."""
    out = {}
    for n in labels:
        m = models[n]
        by = {s: v for s, v in m.recs['msl']}
        frames = []
        for k in range(min(nframes, ENS_HOURS // 6 + 1)):
            st = int((d0 + dt.timedelta(hours=6 * k) - m.run).total_seconds() // 3600)
            if st in by:
                frames.append((k, by[st]))
        tr = track_lows(frames, wbox['lat0'], wbox['lon0'], wbox['ny'], wbox['nx'], wbox['step'])
        if tr:
            out[n] = tr
    return out


def gefs_url(run, mem, step):
    name = 'gec00' if mem == 0 else f'gep{mem:02d}'
    return f"{GEFS}/gefs.{run:%Y%m%d}/{run:%H}/atmos/pgrb2ap5/{name}.t{run:%H}z.pgrb2a.0p50.f{step:03d}"


def gefs_collect(pool, pts, wpts, d0, now, info, system=True):
    for run in candidate_runs(now, (0, 6, 12, 18), 5):
        if exists(gefs_url(run, 30, ENS_HOURS) + '.idx'):
            break
    else:
        try:
            info['listing'] = http(f"{GEFS}/?list-type=2&delimiter=/&prefix=gefs.{now:%Y%m%d}/00/atmos/", tries=1).decode()[:1500]
        except Exception as e:
            info['listing'] = str(e)
        raise RuntimeError('no complete GEFS run found')
    s0, _ = needed(run, d0, NDAYS)
    s1 = min(ENS_HOURS, s0 + 24 * NDAYS)
    members = {k: Model(f'GEFS {k}') for k in range(31)}
    for mm in members.values():
        mm.run = run

    def field(mem, step, rec, var):
        def task():
            m = members[mem]
            try:
                inf, vals = decode(http(gefs_url(run, mem, step), (rec['start'], rec['end'])))
                if var == 'olr':
                    m.add(var, inf, step, sample(inf, vals, OLR_PTS, 'olr'))
                else:
                    m.add(var, inf, step, sample(inf, vals, wpts if var == 'msl' else pts, ('gefs-w' if var == 'msl' else 'gefs-tn')))
            except Exception as e:
                m.err(f'{mem} f{step}: {e}')
        return task

    def idx_task(mem, step):
        def task():
            try:
                recs = parse_idx(http(gefs_url(run, mem, step) + '.idx').decode())
            except Exception as e:
                members[mem].err(f'idx {mem} f{step}: {e}'); return []
            out = []
            for r in recs:
                if r['var'] == 'ULWRF' and r['level'] == 'top of atmosphere' and 'ave' in r['fc'] and s0 < step <= s1:
                    out.append(field(mem, step, r, 'olr'))
                if not system:
                    continue
                if r['var'] == 'APCP' and r['level'] == 'surface':
                    out.append(field(mem, step, r, 'tp'))
                elif r['var'] == 'PRMSL' and r['level'] == 'mean sea level' and s0 <= step <= s1:
                    out.append(field(mem, step, r, 'msl'))
            return out
        return task

    futs = [pool.submit(idx_task(mem, st)) for mem in range(31) for st in range(6, s1 + 1, 6)]
    tasks = []
    for f in cf.as_completed(futs):
        tasks += f.result()
    run_tasks(pool, tasks)
    info['run'] = run.strftime('%Y-%m-%d %HZ')
    info['fields_ok'] = sum(m.ok for m in members.values()); info['fields_failed'] = sum(m.failed for m in members.values())
    info['errors'] = [e for m in members.values() for e in m.errors][:5]
    return run, members


def ens_url(base, run, step):
    return f"{base}/{run:%Y%m%d}/{run:%H}z/ifs/0p25/enfo/{run:%Y%m%d%H}0000-{step}h-enfo-ef"


def ecens_collect(pool, pts, wpts, d0, now, info, system=True):
    chosen = None
    for run in candidate_runs(now, (0, 12), 7):
        bases = [b for b in ECMWF_BASES if exists(ens_url(b, run, ENS_HOURS) + '.index')]
        if bases:
            chosen = (run, bases); break
    if not chosen:
        raise RuntimeError('no complete ECMWF ensemble run found')
    run, bases = chosen
    base = bases[0]
    info['mirrors'] = bases
    s0, _ = needed(run, d0, NDAYS)
    s1 = min(ENS_HOURS, s0 + 24 * NDAYS)
    members = {}
    pool = cf.ThreadPoolExecutor(max_workers=8)     # ECMWF's bucket throttles heavy parallel use

    def mem_model(k):
        with LOCK:
            if k not in members:
                members[k] = Model(f'ENS {k}'); members[k].run = run
            return members[k]

    def field(step, rec, var):
        k = int(rec.get('number', 0)) if rec.get('type') == 'pf' else 0

        def task():
            m = mem_model(k)
            try:
                rng = (rec['_offset'], rec['_offset'] + rec['_length'] - 1)
                inf, vals = decode(ec_fetch(bases, lambda b: ens_url(b, run, step), rng, k + step))
                if var == 'ttr':
                    m.add(var, inf, step, sample(inf, vals, OLR_PTS, 'olr'))
                else:
                    m.add(var, inf, step, sample(inf, vals, wpts if var == 'msl' else pts, 'wind' if var == 'msl' else 'tn'))
            except Exception as e:
                m.err(f'{k} {step}h {var}: {e}')
        return task

    def idx_task(step):
        def task():
            try:
                recs = ec_index(bases, lambda b: ens_url(b, run, step))
            except Exception as e:
                with LOCK:
                    info.setdefault('index_errors', []).append(f'{step}: {e}')
                return []
            out = []
            boundary = (run + dt.timedelta(hours=step)).hour == 0
            for r in recs:
                if r.get('levtype') != 'sfc' or r.get('type') not in ('cf', 'pf'):
                    continue
                if r.get('param') == 'ttr' and boundary and step >= s0:
                    out.append(field(step, r, 'ttr'))
                if not system:
                    continue
                if r.get('param') == 'tp' and boundary:
                    out.append(field(step, r, 'tp'))
                elif r.get('param') == 'msl' and s0 <= step <= s1 and (run + dt.timedelta(hours=step)).hour in (0, 12):
                    out.append(field(step, r, 'msl'))
            return out
        return task

    steps = [st for st in list(range(0, 145, 3)) + list(range(150, 361, 6))
             if st <= s1 and (run + dt.timedelta(hours=st)).hour in ((0, 12) if system else (0,))]
    futs = [pool.submit(idx_task(st)) for st in steps]
    tasks = []
    for f in cf.as_completed(futs):
        tasks += f.result()
    run_tasks(pool, tasks)
    pool.shutdown()
    info['run'] = run.strftime('%Y-%m-%d %HZ'); info['members'] = len(members)
    info['fields_ok'] = sum(m.ok for m in members.values()); info['fields_failed'] = sum(m.failed for m in members.values())
    info['errors'] = [e for m in members.values() for e in m.errors][:5]
    return run, members


def ensemble_products(ens, d0, wbox, npts):
    """ens: {'GEFS': members, 'ECMWF ENS': members}. Returns daily mean rain and heavy-rain probabilities
    (each ensemble weighted equally), combined mean sea-level pressure and every member's low-pressure tracks."""
    nd = ENS_HOURS // 24
    per_ens = {}
    for name, members in ens.items():
        rains = []
        for m in members.values():
            r = daily(m, d0, nd, npts)['rain']
            rains.append(r)
        per_ens[name] = rains
    days = []
    for d in range(nd):
        means, p64, p115, counts = [], [], [], {}
        for name, rains in per_ens.items():
            xs = [r[d] for r in rains if r[d] is not None]
            if len(xs) < 5:
                continue
            arr = np.stack(xs)
            means.append(arr.mean(0)); p64.append((arr >= 64.5).mean(0)); p115.append((arr >= 115.6).mean(0)); counts[name] = len(xs)
        if not means:
            break
        days.append(dict(date=(d0 + dt.timedelta(days=d)).strftime('%Y-%m-%d'), members=counts,
                         mean=[round(float(x), 1) for x in np.mean(means, 0)],
                         p64=[int(round(100 * float(x))) for x in np.mean(p64, 0)],
                         p115=[int(round(100 * float(x))) for x in np.mean(p115, 0)]))
    # pressure: combined ensemble mean (each ensemble's mean weighted equally) and member tracks
    nfr = ENS_HOURS // 6 + 1
    msl_mean, tracks, chance, by_member, ens_mean_tracks = [], {}, {}, {}, {}
    for name, members in ens.items():
        tracks[name] = []
        hit = 0
        for k_m, m in members.items():
            by = {s: v for s, v in m.recs['msl']}
            frames = []
            for k in range(nfr):
                st = int((d0 + dt.timedelta(hours=6 * k) - m.run).total_seconds() // 3600)
                if st in by:
                    frames.append((k, by[st]))
            tr = track_lows(frames, wbox['lat0'], wbox['lon0'], wbox['ny'], wbox['nx'], wbox['step'])
            if tr:
                hit += 1
                by_member.setdefault(name, {})[k_m] = tr
            tracks[name] += [[[p[0], round(p[1], 1), round(p[2], 1), p[3]] for p in t] for t in tr]
        chance[name] = round(100 * hit / max(1, len(members)))
        ens_mean_tracks[name] = mean_tracks(by_member.get(name, {}), len(members))
    for k in range(nfr):
        ms = []
        for name, members in ens.items():
            vs = []
            for m in members.values():
                st = int((d0 + dt.timedelta(hours=6 * k) - m.run).total_seconds() // 3600)
                v = next((v for s, v in m.recs['msl'] if s == st), None)
                if v is not None:
                    vs.append(v)
            if len(vs) >= 5:
                ms.append(np.mean(vs, 0))
        if not ms:
            break
        msl_mean.append([int(round((x - 1000) * 10)) for x in np.mean(ms, 0)])
    return dict(days=days, msl=msl_mean, tracks=tracks, mean_tracks=ens_mean_tracks, chance_low=chance,
                chance_low_avg=round(sum(chance.values()) / max(1, len(chance))))


def basin_of(lo):
    return 'Bay of Bengal' if lo >= 77 else 'Arabian Sea'


def mean_tracks(member_tracks, n_members, min_frac=0.2):
    """Ensemble-mean track per basin: at each 6-hourly frame, the average position of the members that have a low
    in that basin (deepest one per member), kept when at least 20% of members (and 3 or more) agree."""
    per = {}
    for mi, trs in member_tracks.items():
        for t in trs:
            for k, lo, la, pv, *_ in t:
                key = (basin_of(lo), k, mi)
                if key not in per or pv < per[key][2]:
                    per[key] = (lo, la, pv)
    out = {}
    need = max(3, int(math.ceil(min_frac * n_members)))
    for (b, k, mi), v in per.items():
        out.setdefault(b, {}).setdefault(k, []).append(v)
    res = {}
    for b, frames in out.items():
        pts = []
        for k in sorted(frames):
            vs = frames[k]
            if len(vs) >= need:
                lo = sum(v[0] for v in vs) / len(vs); la = sum(v[1] for v in vs) / len(vs); pv = sum(v[2] for v in vs) / len(vs)
                pts.append([k, round(lo, 2), round(la, 2), round(pv, 1), len(vs)])
        if len(pts) >= 2:
            res[b] = pts
    return res


def consensus_tracks(ens_means, det_tracks):
    """Our own consensus per basin: equal-weight average of the GFS-ensemble mean, the ECMWF-ensemble mean and the
    average of the main models that have the low, at each frame where at least two of these three are available."""
    det = {}
    for n, trs in det_tracks.items():
        for t in trs:
            for k, lo, la, pv, *_ in t:
                det.setdefault((basin_of(lo), k), {})[n] = (lo, la, pv)
    det_mean = {}
    for (b, k), byn in det.items():
        vs = list(byn.values())
        det_mean.setdefault(b, {})[k] = (sum(v[0] for v in vs) / len(vs), sum(v[1] for v in vs) / len(vs), sum(v[2] for v in vs) / len(vs))
    out = {}
    basins = set(det_mean) | {b for m in ens_means.values() for b in m}
    for b in basins:
        frames = set(det_mean.get(b, {}))
        for m in ens_means.values():
            frames |= {p[0] for p in m.get(b, [])}
        pts = []
        for k in sorted(frames):
            comps = []
            for m in ens_means.values():
                q = next((p for p in m.get(b, []) if p[0] == k), None)
                if q:
                    comps.append((q[1], q[2], q[3]))
            if k in det_mean.get(b, {}):
                comps.append(det_mean[b][k])
            if len(comps) >= 2:
                pts.append([k, round(sum(c[0] for c in comps) / len(comps), 2), round(sum(c[1] for c in comps) / len(comps), 2),
                            round(sum(c[2] for c in comps) / len(comps), 1), len(comps)])
        if len(pts) >= 2:
            out[b] = pts
    return out



# ------------------------------------------------------------------ MJO forecast (OMI / ROMI method on model OLR)
PSL_EOF = 'https://downloads.psl.noaa.gov/Datasets.other/MJO/eof{k}/eof{doy:03d}.txt'
OLR_LTM = 'https://downloads.psl.noaa.gov/Datasets/cpc_blended_olr-2.5deg/olr.cbo-2.5deg.day.ltm.1991-2020.nc'
OLR_DAP = 'https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_blended_olr-2.5deg/olr.cbo-2.5deg.day.mean.nc'


def _doy(d):
    return min(d.timetuple().tm_yday, 365) if not (d.month == 2 and d.day == 29) else 59


def olr_daily_from_model(m, d0, ndays):
    """Daily-mean OLR (W m-2) on the OMI grid for each forecast day, from 6-h averages (GFS) or accumulated ttr (ECMWF)."""
    out = {}
    if m.run is None:
        return out
    C = cumulative(m.recs['ttr']) if m.recs['ttr'] else None
    for d in range(ndays):
        a = int((d0 + dt.timedelta(days=d) - m.run).total_seconds() // 3600); b = a + 24
        if a < 0:
            continue
        day = (d0 + dt.timedelta(days=d)).date()
        if m.recs['olr']:
            vs = [v for st, e, v in m.recs['olr'] if a < e <= b and e - st == 6]
            if len(vs) == 4:
                out[day] = np.mean(vs, 0)
        elif C is not None and b in C and (a == 0 or a in C):
            ca = 0 if a == 0 else C[a]
            if C[b] is not None and (a == 0 or ca is not None):
                out[day] = -(C[b] - ca) / 86400.0
    return out


def mjo_forecasts(sources, d0, romi_rows, status):
    """sources: {name: {date: OLR field}} (deterministic) and {name: [member dicts]} (ensembles).
    Observed OLR (NOAA interpolated OLR) fills the past; each series is turned into anomalies, the mean of the previous
    40 days is removed, a 9-day running mean applied and the result projected on NOAA PSL's daily OMI EOFs.
    The scale is calibrated on the observed part against NOAA's real-time OMI (ROMI)."""
    import netCDF4
    # climatology and observations on the OMI grid (latitude ascending, 20S-20N)
    ltm = netCDF4.Dataset('ltm.nc', memory=http(OLR_LTM, timeout=180))
    la = np.asarray(ltm['lat'][:]); j = [int(np.argmin(np.abs(la - x))) for x in OLR_LATS]
    lo = np.asarray(ltm['lon'][:]) % 360; i = [int(np.argmin(np.abs(lo - x))) for x in BAND_LONS]
    clim = np.asarray(ltm['olr'][:, j, :], float)[:, :, i].reshape(ltm['olr'].shape[0], -1)       # (365, 2448)
    ltm.close()
    ds = netCDF4.Dataset(OLR_DAP)
    t = ds['time']; n = len(t); n0 = max(0, n - 90)
    times = netCDF4.num2date(t[n0:n], t.units, only_use_cftime_datetimes=False)
    la = np.asarray(ds['lat'][:]); j = [int(np.argmin(np.abs(la - x))) for x in OLR_LATS]
    lo = np.asarray(ds['lon'][:]) % 360; i = [int(np.argmin(np.abs(lo - x))) for x in BAND_LONS]
    obs_raw = np.asarray(ds['olr'][n0:n, :, :], float)[:, j, :][:, :, i].reshape(n - n0, -1)
    status['mjo_obs_grid'] = f'lat {la[0]}..{la[-1]}, lon {lo[0]}..{lo[-1]}'
    ds.close()
    obs = {}
    for tt, row in zip(times, obs_raw):
        d = dt.date(tt.year, tt.month, tt.day)
        if np.all(np.isfinite(row)) and row.mean() > 100:
            obs[d] = row - clim[_doy(d) - 1]
    last_obs = max(obs)
    status['mjo_obs_olr'] = f'{min(obs)} to {last_obs}'
    eofs = {}

    def eof(d):
        k = _doy(d)
        if k not in eofs:
            e = []
            for i in (1, 2):
                txt = http(PSL_EOF.format(k=i, doy=k), timeout=60).decode()
                e.append(np.array([float(x) for x in txt.split()], float))
            eofs[k] = e
        return eofs[k]

    def index_series(fc_days):
        """fc_days: {date: OLR field} for forecast days. Returns {date: (pc1, pc2)} (uncalibrated)."""
        series = dict(obs)
        if fc_days:
            fc_anom = {d: v - clim[_doy(d) - 1] for d, v in fc_days.items() if d > last_obs}
            if not fc_anom:
                return {}
            # keep the domain-mean anomaly continuous with the last 10 observed days (removes model-wide OLR bias)
            ref = np.mean([obs[d].mean() for d in sorted(obs)[-10:]])
            bias = np.mean([v.mean() for v in fc_anom.values()]) - ref
            fc_anom = {d: v - bias for d, v in fc_anom.items()}
            first = min(fc_anom)
            gap = (first - last_obs).days
            for g in range(1, gap):                    # linear fill between the last observation and the forecast
                w = g / gap
                series[last_obs + dt.timedelta(days=g)] = obs[last_obs] * (1 - w) + fc_anom[first] * w
            series.update(fc_anom)
        days = sorted(series)
        x = {}
        for d in days:
            prev = [series[d - dt.timedelta(days=i)] for i in range(1, 41) if d - dt.timedelta(days=i) in series]
            if len(prev) >= 35:
                x[d] = series[d] - np.mean(prev, 0)
        out = {}
        for d in sorted(x):
            win = [x[d + dt.timedelta(days=i)] for i in range(-4, 5) if d + dt.timedelta(days=i) in x]
            if len(win) >= 5:
                e1, e2 = eof(d)
                v = np.mean(win, 0)
                out[d] = (float(v @ e1), float(v @ e2))
        return out

    # calibration on observations only, against ROMI
    obs_idx = index_series({})
    pairs = [(obs_idx[dt.date.fromisoformat(r['date'])], (r['pc1'], r['pc2'])) for r in romi_rows
             if 'pc1' in r and dt.date.fromisoformat(r['date']) in obs_idx]
    if len(pairs) < 10:
        raise RuntimeError(f'too few days to calibrate ({len(pairs)})')
    a = np.array([p[0] for p in pairs]).ravel(); b = np.array([p[1] for p in pairs]).ravel()
    scale = float(a @ b / (a @ a))
    corr = float(np.corrcoef(a, b)[0, 1])
    status['mjo_calibration'] = dict(days=len(pairs), scale=round(scale, 4), corr=round(corr, 3))

    def to_xy(idx, start):
        return [[d.isoformat(), round(scale * pc2, 2), round(-scale * pc1, 2)] for d, (pc1, pc2) in sorted(idx.items()) if d >= start]

    start = min(dt.date.fromisoformat(romi_rows[-1]['date']), last_obs)
    out = {'calibration': status['mjo_calibration'], 'start': start.isoformat(), 'tracks': {}}
    for name, src in sources.items():
        try:
            if isinstance(src, dict):
                tr = to_xy(index_series(src), start)
            else:                                       # ensemble: average the members' index values by date
                acc = {}
                for mem in src:
                    for d, x, y in to_xy(index_series(mem), start):
                        acc.setdefault(d, []).append((x, y))
                tr = [[d, round(float(np.mean([p[0] for p in v])), 2), round(float(np.mean([p[1] for p in v])), 2), len(v)]
                      for d, v in sorted(acc.items()) if len(v) >= 5]
            if len(tr) >= 3:
                out['tracks'][name] = tr
        except Exception as e:
            status.setdefault('mjo_errors', {})[name] = str(e)[:200]

    def avg(names, label):
        ts = [dict((p[0], p) for p in out['tracks'][n]) for n in names if n in out['tracks']]
        if len(ts) < 2:
            return
        common = sorted(set.intersection(*[set(t) for t in ts]))
        out['tracks'][label] = [[d, round(sum(t[d][1] for t in ts) / len(ts), 2), round(sum(t[d][2] for t in ts) / len(ts), 2)] for d in common]
    avg(['GFS', 'ECMWF'], 'GFS + ECMWF average')
    avg(['GFS ensemble mean', 'ECMWF ensemble mean'], 'Ensembles average')
    return out


# ------------------------------------------------------------------ main
def land_outline():
    cache = P('data/land_region.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    try:
        g = json.loads(http(LAND_URL))
        rings = []
        for f in g['features']:
            geom = f['geometry']
            polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
            for poly in polys:
                for ring in poly:
                    if any(55 < x < 105 and -10 < y < 35 for x, y in ring):
                        r = []
                        for x, y in ring:
                            q = [round(x, 2), round(y, 2)]
                            if not r or q != r[-1]:
                                r.append(q)
                        if len(r) > 3:
                            rings.append(r)
        json.dump(rings, open(cache, 'w'), separators=(',', ':'))
        return rings
    except Exception as e:
        print('coastline download failed:', e, file=sys.stderr)
        return []


def r1(x):
    return None if x is None or not np.isfinite(x) else round(float(x), 1)


def main():
    now = dt.datetime.now(UTC)
    d0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    geo = json.load(open(P('data/geo.json')))
    pts = tn_points(geo)
    lats, lons, wpts = wind_points()
    models = {n: Model(n) for n in ('GFS', 'ECMWF', 'ECMWF AI', 'GEM', 'ICON')}
    wind_raw = {}
    status = {'run_utc': now.isoformat(timespec='seconds'), 'models': {}}
    only = set(filter(None, os.environ.get('FORECAST_MODELS', '').split(',')))

    jobs = {
        'GFS': lambda m, pool: gfs_collect(m, pool, pts, wpts, d0, now, wind_raw),
        'ECMWF': lambda m, pool: ec_collect(m, pool, pts, wpts, d0, now, 'ifs'),
        'ECMWF AI': lambda m, pool: ec_collect(m, pool, pts, wpts, d0, now, 'aifs-single'),
        'ICON': lambda m, pool: icon_collect(m, pool, pts, wpts, d0, now),
        'GEM': lambda m, pool: gem_collect(m, pool, pts, wpts, d0, now),
    }
    stop = threading.Event()
    threading.Thread(target=heartbeat, args=(stop,), daemon=True).start()
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for name, job in jobs.items():
            if only and name not in only:
                continue
            m, t0 = models[name], time.time()
            CURRENT['deadline'] = t0 + BUDGET[name] * 60
            PROGRESS['current'] = name
            try:
                job(m, pool)
            except Exception as e:
                m.err(f'FATAL {e}')
                traceback.print_exc()
            status['models'][name] = dict(run=m.run.strftime('%Y-%m-%d %HZ') if m.run else None,
                                          fields_ok=m.ok, fields_failed=m.failed, seconds=round(time.time() - t0),
                                          errors=m.errors, samples=m.samples, **m.info)
            print(name, json.dumps(status['models'][name], default=str)[:800], flush=True)
            json.dump(status, open(P('data/forecast_status.json'), 'w'), indent=1, default=str)
    stop.set()
    CURRENT['deadline'] = DEADLINE

    # daily values per model
    per = {n: daily(m, d0, NDAYS, len(pts)) for n, m in models.items()}
    per6 = {n: six_hourly(m, d0, NDAYS * 4) for n, m in models.items()}
    labels = [n for n in models if any(x is not None for x in per[n]['rain'])]
    for n in labels:
        status['models'][n]['days_with_rain'] = sum(x is not None for x in per[n]['rain'])
    if not labels:
        json.dump(status, open(P('data/forecast_status.json'), 'w'), indent=1)
        raise SystemExit('no model produced a forecast; previous page kept')
    nd = max(d + 1 for n in labels for d in range(NDAYS) if per[n]['rain'][d] is not None)
    dates = [(d0 + dt.timedelta(days=d)).strftime('%Y-%m-%d') for d in range(nd)]
    coverage = [[n for n in labels if per[n]['rain'][d] is not None] for d in range(nd)]
    coverage6 = [[n for n in labels if per6[n][k] is not None] for k in range(nd * 4)]
    keymap = {'precipitation_sum': 'rain', 'temperature_2m_max': 'tmax', 'temperature_2m_min': 'tmin', 'wind_speed_10m_max': 'wmax'}
    cells = []
    for i, (lo, la) in enumerate(pts):
        rec = {'lon': lo, 'lat': la}
        for out_key, k in keymap.items():
            mv = {n: [r1(per[n][k][d][i]) if per[n][k][d] is not None else None for d in range(nd)] for n in labels}
            avg = []
            for d in range(nd):
                xs = [mv[n][d] for n in labels if mv[n][d] is not None]
                avg.append(round(sum(xs) / len(xs), 1) if xs else None)
            rec[out_key] = {'avg': avg, **mv}
        dd = []
        for d in range(nd):
            xs = [(per[n]['wdir'][d][i], per[n]['wmax'][d][i]) for n in labels if per[n]['wdir'][d] is not None]
            if xs:
                x = sum(s * math.sin(math.radians(a)) for a, s in xs); y = sum(s * math.cos(math.radians(a)) for a, s in xs)
                dd.append(round(math.degrees(math.atan2(x, y)) % 360))
            else:
                dd.append(None)
        rec['wind_dir'] = dd
        mv = {n: [r1(per6[n][k][i]) if per6[n][k] is not None else None for k in range(nd * 4)] for n in labels}
        avg6 = []
        for k in range(nd * 4):
            xs = [mv[n][k] for n in labels if mv[n][k] is not None]
            avg6.append(round(sum(xs) / len(xs), 1) if xs else None)
        rec['rain6'] = {'avg': avg6, **mv}
        cells.append(rec)

    # mean sea-level pressure: average and spread of the models, every 6 h
    mslp = None
    frames = []
    for k in range(nd * 4 + 1):
        vt = d0 + dt.timedelta(hours=6 * k)
        got = {}
        for n in labels:
            mm = models[n]
            st = int((vt - mm.run).total_seconds() // 3600)
            for s, v in mm.recs['msl']:
                if s == st and np.isfinite(v).all() and 900 < np.nanmean(v) < 1100:
                    got[n] = v
        if got:
            arr = np.stack(list(got.values()))
            frames.append((vt, sorted(got), arr.mean(0), arr.std(0)))
    if frames:
        mslp = dict(lat0=lats[0], lon0=lons[0], step=WIND_BOX['step'], ny=len(lats), nx=len(lons),
                    times=[f[0].strftime('%Y-%m-%dT%H:%MZ') for f in frames], models=[f[1] for f in frames],
                    avg=[[int(round((x - 1000) * 10)) for x in f[2]] for f in frames],
                    spread=[[int(round(x * 10)) for x in f[3]] for f in frames])
    status['mslp'] = {n: len(models[n].recs['msl']) for n in labels}

    # wind animation frames (GFS)
    wind = None
    gfs = models['GFS']
    frames = sorted(s for s, lv in wind_raw.items() if all(l in lv and 'u' in lv[l] and 'v' in lv[l] for l in LEVELS))
    if frames:
        wind = dict(lat0=lats[0], lon0=lons[0], step=WIND_BOX['step'], ny=len(lats), nx=len(lons),
                    times=[(gfs.run + dt.timedelta(hours=s)).strftime('%Y-%m-%dT%H:%MZ') for s in frames],
                    run=gfs.run.strftime('%HZ %d %b'),
                    levels={('10m' if l == '10m' else l + 'hPa'): [[[int(round(x * 2)) for x in wind_raw[s][l]['u']],
                                                                    [int(round(x * 2)) for x in wind_raw[s][l]['v']]] for s in frames]
                            for l in LEVELS})
        status['wind'] = f'ok ({len(frames)} frames)'
    else:
        status['wind'] = 'FAILED: no complete GFS wind frames'
        try:
            old = open(P('site/forecast.html')).read()
            wind = json.loads(old[old.index('const F=') + 8:old.index(';\nconst $=')])['wind']
            status['wind'] += ' (showing previous run)'
        except Exception:
            pass

    # step 2: large-scale drivers (each part optional: a failure never blocks the forecast)
    drivers = {}
    try:
        clim = climatology(wpts)
        anom, band = anomalies_850(models, labels, clim, d0, nd)
        drivers['anom850'] = dict(lat0=lats[0], lon0=lons[0], step=WIND_BOX['step'], ny=len(lats), nx=len(lons), **anom)
        drivers['hov'] = dict(lons=BAND_LONS, past=update_band_history(band, d0),
                              future=[dict(date=d, u=b) for d, b in zip(anom['days'], band) if b is not None])
        status['anom850'] = f"{len(anom['days'])} days, climatology {clim.get('source')}"
    except Exception as e:
        status['anom850'] = f'FAILED: {e}'; traceback.print_exc()
    try:
        drivers['sst'], drivers['sst_idx'] = sst_latest(status)
    except Exception as e:
        status['sst'] = f'FAILED: {e}'; traceback.print_exc()
    try:
        drivers['mjo'] = mjo_observed(status)
    except Exception as e:
        status['mjo'] = f'FAILED: {e}'; traceback.print_exc()

    # step 3: ensembles. Always read for the MJO forecast (OLR only); when any main model shows a low over the
    # Bay of Bengal or Arabian Sea (or on a manual test), rain and pressure are read as well for the system watch.
    wbox = dict(lat0=lats[0], lon0=lons[0], ny=len(lats), nx=len(lons), step=WIND_BOX['step'])
    systems, ens, einfo, lows = {}, {}, {}, {}
    try:
        lows = deterministic_lows(models, labels, d0, nd * 4 + 1, wbox)
        systems = dict(deterministic={n: [[[p[0], round(p[1], 1), round(p[2], 1), p[3]] for p in t] for t in tr] for n, tr in lows.items()},
                       triggered=bool(lows), forced=os.environ.get('FORCE_ENS') == '1')
        status['systems'] = {n: len(t) for n, t in lows.items()}
    except Exception as e:
        status['systems_error'] = str(e); traceback.print_exc()
    want_system = bool(lows) or systems.get('forced', False)
    with cf.ThreadPoolExecutor(max_workers=24) as pool2:
        for name, fn in (('GEFS', gefs_collect), ('ECMWF ENS', ecens_collect)):
            t0 = time.time(); CURRENT['deadline'] = t0 + BUDGET[name] * 60; einfo[name] = {}
            try:
                _, mem = fn(pool2, pts, wpts, d0, now, einfo[name], system=want_system)
                ens[name] = mem
            except Exception as e:
                einfo[name]['error'] = str(e); traceback.print_exc()
            einfo[name]['seconds'] = round(time.time() - t0)
            json.dump(dict(status, ensembles=einfo), open(P('data/forecast_status.json'), 'w'), indent=1, default=str)
    CURRENT['deadline'] = DEADLINE
    status['ensembles'] = einfo
    if want_system and ens:
        try:
            systems['ens'] = ensemble_products(ens, d0, wbox, len(pts))
            systems['ens']['consensus'] = consensus_tracks(systems['ens']['mean_tracks'], lows)
            systems['ens_runs'] = {n: einfo[n].get('run') for n in ens}
        except Exception as e:
            status['systems_error'] = str(e); traceback.print_exc()
    # MJO forecast: GFS, ECMWF, their ensembles, and averages
    try:
        romi = (drivers.get('mjo') or {}).get('days') or []
        srcs = {}
        for n in ('GFS', 'ECMWF'):
            if n in labels:
                srcs[n] = olr_daily_from_model(models[n], d0, NDAYS)
        for n, lab in (('GEFS', 'GFS ensemble mean'), ('ECMWF ENS', 'ECMWF ensemble mean')):
            if n in ens:
                srcs[lab] = [olr_daily_from_model(m, d0, ENS_HOURS // 24) for m in ens[n].values()]
        status['mjo_sources'] = {k: (len(v) if isinstance(v, dict) else f'{len(v)} members, {max((len(x) for x in v), default=0)} days') for k, v in srcs.items()}
        if romi and srcs:
            drivers['mjo_fc'] = mjo_forecasts(srcs, d0, romi, status)
            for r in drivers['mjo'].get('days', []):
                r.pop('pc1', None); r.pop('pc2', None)
    except Exception as e:
        status['mjo_fc'] = f'FAILED: {e}'; traceback.print_exc()

    runs = {n: models[n].run.strftime('%HZ %d %b') for n in labels}
    F = dict(updated=dt.datetime.now(IST).strftime('%d %b %Y, %H:%M IST'), dates=dates, models=labels, runs=runs,
             coverage=coverage, coverage6=coverage6, cells=cells, wind=wind, mslp=mslp, drivers=drivers, systems=systems, land=land_outline(), tn=geo['tn'], ct=geo['ct'], step=.25)
    tpl = open(P('site/forecast_template.html')).read()
    open(P('site/forecast.html'), 'w').write(tpl.replace('/*FDATA*/', json.dumps(F, separators=(',', ':'))))
    status.update(points=len(pts), days=nd, seconds=round(time.time() - T_START))
    json.dump(status, open(P('data/forecast_status.json'), 'w'), indent=1, default=str)
    print(json.dumps({k: v for k, v in status.items() if k != 'models'}, indent=1))


if __name__ == '__main__':
    main()
