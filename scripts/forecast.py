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
import bz2, concurrent.futures as cf, datetime as dt, json, math, os, re, sys, threading, time, traceback
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
DEADLINE = T_START + 45 * 60
NDAYS = 16
LEVELS = ['10m', '925', '850', '700', '500', '200']           # page keys: 10m and hPa levels
WIND_BOX = dict(lat0=0, lat1=25, lon0=65, lon1=95, step=1.0)
LAND_URL = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson'
LOCK = threading.Lock()


class NotFound(Exception):
    pass


# ------------------------------------------------------------------ network
def http(url, rng=None, tries=4, timeout=120, method='GET'):
    last = None
    for i in range(tries):
        if time.time() > DEADLINE:
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
    """

    def __init__(self, name):
        self.name, self.run = name, None
        self.recs = {k: [] for k in ('tp', 't2', 'tmax', 'tmin', 'u10', 'v10')}
        self.ok = self.failed = 0
        self.errors, self.samples, self.info = [], {}, {}

    def err(self, msg):
        with LOCK:
            self.failed += 1
            if len(self.errors) < 8:
                self.errors.append(msg[:300])

    def add(self, var, info, step, vals_pts):
        lo, hi = step_range(info)
        end = hi if hi is not None else step
        if var in ('t2', 'tmax', 'tmin'):
            if np.nanmean(vals_pts) > 150:       # Kelvin
                vals_pts = vals_pts - 273.15
        if var == 'tp' and (info.get('units') or '') == 'm':
            vals_pts = vals_pts * 1000.0
        with LOCK:
            self.ok += 1
            if var not in self.samples:
                self.samples[var] = {k: (v if isinstance(v, (int, float, str)) or v is None else str(v))
                                     for k, v in info.items() if k in ('shortName', 'units', 'gridType', 'stepRange',
                                                                       'typeOfLevel', 'level', 'Ni', 'Nj', 'numberOfDataPoints')}
            if var in ('tp', 'tmax', 'tmin'):
                start = lo if lo is not None else (0 if var == 'tp' else end - 6)
                self.recs[var].append((start, end, vals_pts))
            else:
                self.recs[var].append((step, vals_pts))


def run_tasks(pool, tasks):
    """tasks: list of callables; runs them, swallowing (but recording) errors inside each task."""
    futs = [pool.submit(t) for t in tasks]
    for f in cf.as_completed(futs):
        f.result()


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

    def field(step, rec, var, kind):
        def task():
            try:
                info, vals = decode(http(gfs_url(run, step), (rec['start'], rec['end'])))
                if kind in ('tn', 'both'):
                    m.add(var, info, step, sample(info, vals, pts, 'tn'))
                if kind in ('wind', 'both'):
                    lev = wanted_levels[rec['level']]
                    comp = 'u' if rec['var'] == 'UGRD' else 'v'
                    with LOCK:
                        wind_out.setdefault(step, {}).setdefault(lev, {})[comp] = sample(info, vals, wpts, 'wind')
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
                    out.append(field(step, r, 't2', 'tn'))
                elif r['var'] == 'APCP' and r['level'] == 'surface' and step % 6 == 0:
                    out.append(field(step, r, 'tp', 'tn'))
                elif r['var'] in ('TMAX', 'TMIN') and r['level'] == '2 m above ground' and in_days and step % 6 == 0:
                    out.append(field(step, r, r['var'].lower(), 'tn'))
                elif r['var'] in ('UGRD', 'VGRD') and r['level'] in wanted_levels:
                    is10 = r['level'] == '10 m above ground'
                    tn = is10 and in_days and step % 6 == 0
                    wd = step in wind_steps
                    if tn or wd:
                        var = 'u10' if r['var'] == 'UGRD' else 'v10'
                        out.append(field(step, r, var, 'both' if (tn and wd) else ('tn' if tn else 'wind')))
            return out
        return task

    idx_futs = [pool.submit(idx_task(s)) for s in steps]
    tasks = []
    for f in cf.as_completed(idx_futs):
        tasks += f.result()
    run_tasks(pool, tasks)


# ------------------------------------------------------------------ ECMWF IFS and AIFS (open data)
ECMWF_BASES = ['https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com', 'https://data.ecmwf.int/forecasts']


def ec_url(base, model, run, step):
    return f"{base}/{run:%Y%m%d}/{run:%H}z/{model}/0p25/oper/{run:%Y%m%d%H}0000-{step}h-oper-fc"


def ec_collect(m, pool, pts, d0, now, model):
    full = 360
    steps_all = (list(range(0, 145, 3)) + list(range(150, 361, 6))) if model == 'ifs' else list(range(0, 361, 6))
    cycles = (0, 12) if model == 'ifs' else (0, 6, 12, 18)
    chosen = None
    for run in candidate_runs(now, cycles, 5):
        for base in ECMWF_BASES:
            if exists(ec_url(base, model, run, full) + '.index'):
                chosen = (run, base); break
        if chosen:
            break
    if not chosen:
        raise RuntimeError(f'no complete {model} run found')
    run, base = chosen
    m.run, m.info['base'] = run, base
    s0, s1 = needed(run, d0, NDAYS)
    steps = [s for s in steps_all if s <= s1]

    def field(step, rec, var):
        def task():
            try:
                info, vals = decode(http(ec_url(base, model, run, step) + '.grib2',
                                         (rec['_offset'], rec['_offset'] + rec['_length'] - 1)))
                m.add(var, info, step, sample(info, vals, pts, 'tn'))
            except Exception as e:
                m.err(f'{step}h {rec.get("param")}: {e}')
        return task

    params_seen = set()

    def idx_task(step):
        def task():
            try:
                lines = http(ec_url(base, model, run, step) + '.index').decode().strip().splitlines()
                recs = [json.loads(l) for l in lines if l.strip()]
            except Exception as e:
                m.err(f'index {step}h: {e}'); return []
            out = []
            in_days = s0 <= step <= s1
            for r in recs:
                p, lt = r.get('param'), r.get('levtype')
                if lt != 'sfc':
                    continue
                with LOCK:
                    params_seen.add(p)
                if p == 'tp' and step % 6 == 0:
                    out.append(field(step, r, 'tp'))
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


def icon_neighbours(run, pts):
    cache = P('data/icon_tn_neighbours.json')
    if os.path.exists(cache):
        c = json.load(open(cache))
        if len(c['idx']) == len(pts):
            return np.array(c['idx']).T, np.array(c['w']).T, c['n']
    arrs = {}
    for v in ('clat', 'clon'):
        url = f"{DWD}/{run:%H}/{v}/icon_global_icosahedral_time-invariant_{run:%Y%m%d%H}_{v.upper()}.grib2.bz2"
        info, vals = decode(http(url))
        if np.nanmax(np.abs(vals)) < 3.3:
            vals = np.degrees(vals)
        arrs[v] = vals
    lat, lon = arrs['clat'], arrs['clon']
    sel = np.where((lat > 7.4) & (lat < 14.3) & (lon > 75.7) & (lon < 81.0))[0]
    idx, w = [], []
    for lo, la in pts:
        d = np.hypot((lon[sel] - lo) * math.cos(math.radians(la)), lat[sel] - la)
        k = np.argsort(d)[:4]
        ww = 1 / np.maximum(d[k], 1e-4) ** 2
        idx.append([int(i) for i in sel[k]]); w.append([float(x) for x in ww / ww.sum()])
    json.dump({'n': int(len(lat)), 'idx': idx, 'w': w}, open(cache, 'w'))
    return np.array(idx).T, np.array(w).T, int(len(lat))


def icon_collect(m, pool, pts, d0, now):
    for run in candidate_runs(now, (0, 12), 3.5):
        if exists(icon_url(run, 't_2m', 180)):
            break
    else:
        raise RuntimeError('no complete ICON run found')
    m.run = run
    s0, s1 = needed(run, d0, NDAYS)
    idx, w, n = icon_neighbours(run, pts)
    m.info['cells'] = n
    steps = [s for s in list(range(0, 79, 3)) + list(range(81, 181, 3)) if s0 <= s <= s1]

    def field(var, step, tag):
        def task():
            try:
                info, vals = decode(http(icon_url(run, var, step)))
                if len(vals) != n:
                    raise RuntimeError(f'grid size {len(vals)} != {n}')
                m.add(tag, info, step, np.sum(vals[idx] * w, axis=0))
            except Exception as e:
                m.err(f'{var} {step}: {e}')
        return task

    tasks = []
    for s in steps:
        tasks.append(field('t_2m', s, 't2'))
        if s % 6 == 0:
            tasks += [field('u_10m', s, 'u10'), field('v_10m', s, 'v10')]
        if (run + dt.timedelta(hours=s)).hour == 0 and s > 0:
            tasks.append(field('tot_prec', s, 'tp'))
    run_tasks(pool, tasks)


# ------------------------------------------------------------------ GEM (ECCC Datamart)
GEM_PAT = {
    'tp': r'(Precip-Accum|PrecipAccum|APCP_SFC)',
    't2': r'_(AirTemp_AGL-2m|TMP_TGL_2)_',
    'u10': r'_(WindU_AGL-10m|UGRD_TGL_10)_',
    'v10': r'_(WindV_AGL-10m|VGRD_TGL_10)_',
}


def gem_dirs(run):
    return [f"https://dd.weather.gc.ca/{run:%Y%m%d}/WXO-DD/model_gdps/15km/{run:%H}/{{h:03d}}/",
            f"https://dd.weather.gc.ca/today/model_gdps/15km/{run:%H}/{{h:03d}}/",
            f"https://dd.weather.gc.ca/model_gem_global/15km/grib2/lat_lon/{run:%H}/{{h:03d}}/"]


def gem_list(url):
    html = http(url, tries=2, timeout=60).decode('utf-8', 'replace')
    return sorted(set(re.findall(r'href="([^"/?]+\.grib2)"', html)))


def gem_collect(m, pool, pts, d0, now):
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
    m.info['listing_sample'] = names240[:40] if len(names) < 4 else None
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
                m.add(var, info, step, sample(info, vals, pts, 'tn'))
            except Exception as e:
                m.err(f'{var} {step}: {e}')
        return task

    tasks = []
    for s in steps:
        tasks.append(field('t2', s))
        if s % 6 == 0 and 'u10' in names:
            tasks += [field('u10', s), field('v10', s)]
        if 'tp' in names and s > 0 and (run + dt.timedelta(hours=s)).hour == 0:
            tasks.append(field('tp', s))
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
        'ECMWF': lambda m, pool: ec_collect(m, pool, pts, d0, now, 'ifs'),
        'ECMWF AI': lambda m, pool: ec_collect(m, pool, pts, d0, now, 'aifs-single'),
        'ICON': lambda m, pool: icon_collect(m, pool, pts, d0, now),
        'GEM': lambda m, pool: gem_collect(m, pool, pts, d0, now),
    }
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for name, job in jobs.items():
            if only and name not in only:
                continue
            m, t0 = models[name], time.time()
            try:
                job(m, pool)
            except Exception as e:
                m.err(f'FATAL {e}')
                traceback.print_exc()
            status['models'][name] = dict(run=m.run.strftime('%Y-%m-%d %HZ') if m.run else None,
                                          fields_ok=m.ok, fields_failed=m.failed, seconds=round(time.time() - t0),
                                          errors=m.errors, samples=m.samples, **m.info)
            print(name, json.dumps(status['models'][name], default=str)[:800], flush=True)

    # daily values per model
    per = {n: daily(m, d0, NDAYS, len(pts)) for n, m in models.items()}
    labels = [n for n in models if any(x is not None for x in per[n]['rain'])]
    for n in labels:
        status['models'][n]['days_with_rain'] = sum(x is not None for x in per[n]['rain'])
    if not labels:
        json.dump(status, open(P('data/forecast_status.json'), 'w'), indent=1)
        raise SystemExit('no model produced a forecast; previous page kept')
    nd = max(d + 1 for n in labels for d in range(NDAYS) if per[n]['rain'][d] is not None)
    dates = [(d0 + dt.timedelta(days=d)).strftime('%Y-%m-%d') for d in range(nd)]
    coverage = [[n for n in labels if per[n]['rain'][d] is not None] for d in range(nd)]
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
        cells.append(rec)

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

    runs = {n: models[n].run.strftime('%HZ %d %b') for n in labels}
    F = dict(updated=dt.datetime.now(IST).strftime('%d %b %Y, %H:%M IST'), dates=dates, models=labels, runs=runs,
             coverage=coverage, cells=cells, wind=wind, land=land_outline(), tn=geo['tn'], ct=geo['ct'], step=.25)
    tpl = open(P('site/forecast_template.html')).read()
    open(P('site/forecast.html'), 'w').write(tpl.replace('/*FDATA*/', json.dumps(F, separators=(',', ':'))))
    status.update(points=len(pts), days=nd, seconds=round(time.time() - T_START))
    json.dump(status, open(P('data/forecast_status.json'), 'w'), indent=1, default=str)
    print(json.dumps({k: v for k, v in status.items() if k != 'models'}, indent=1))


if __name__ == '__main__':
    main()
