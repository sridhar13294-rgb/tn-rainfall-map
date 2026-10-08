"""Step 4: one-month outlook for Tamil Nadu (weeks 1-4) from NOAA CFSv2, against the 1991-2020 normal.

CFSv2 (NOAA NCEP) runs 4 times a day with 4 members each; its 6-hourly time-series files are on AWS
(noaa-cfs-pds). The latest NCYC complete cycles are combined as a lagged ensemble (NCYC x 4 members).
For each member: daily rain (sum of the four 6-hour mean rates) and daily max/min temperature (max/min of the
6-hour max/min) on the Tamil Nadu forecast grid, then weekly totals/means.

Normals: NOAA CPC global unified gauge analysis, daily 1991-2020 long-term mean, 0.5 degree, read once from NOAA
PSL by OPeNDAP and cached in data/cpc_clim_tn.json.

Temperature: CFSv2 has a steady 2 m temperature bias over land, so each grid point's CFSv2 week-1 mean is matched to
the five-model week-1 mean (the main forecast) and that difference is removed from all four weeks. Rain is not
adjusted: it is shown as CFSv2 gives it, with the chance of an above- or below-normal week taken from the members.
"""
import concurrent.futures as cf, datetime as dt, json, math, os, re, time

import numpy as np

try:
    import eccodes
except Exception:      # pragma: no cover
    eccodes = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
CFS = 'https://noaa-cfs-pds.s3.amazonaws.com'
NCYC = 8                                   # 8 cycles = last 2 days x 4 members = 32 members
WEEKS = 4
CLIM_CACHE = P('data', 'cpc_clim_tn.json')
CLIM_DAP = {'rain': ('https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_global_precip/precip.day.ltm.1991-2020.nc', 'precip'),
            'tmax': ('https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_global_temp/tmax.day.ltm.1991-2020.nc', 'tmax'),
            'tmin': ('https://psl.noaa.gov/thredds/dodsC/Datasets/cpc_global_temp/tmin.day.ltm.1991-2020.nc', 'tmin')}
CLIM_BOX = (7.0, 14.5, 75.5, 81.5)         # lat0, lat1, lon0, lon1
VARS = {'rain': 'prate', 'tmax': 'tmax', 'tmin': 'tmin'}
UP, DOWN = 1.2, 0.8                        # above normal: 20% or more over the normal; below: 20% or more under


# ------------------------------------------------------------------ normals
def climatology():
    if os.path.exists(CLIM_CACHE):
        c = json.load(open(CLIM_CACHE))
        if all(k in c for k in VARS):
            return c
    import netCDF4
    out = {}
    for k, (url, vn) in CLIM_DAP.items():
        ds = netCDF4.Dataset(url)
        la, lo = ds['lat'][:], ds['lon'][:]
        j = [i for i, x in enumerate(la) if CLIM_BOX[0] <= x <= CLIM_BOX[1]]
        i2 = [i for i, x in enumerate(lo) if CLIM_BOX[2] <= x <= CLIM_BOX[3]]
        a = ds[vn][:, min(j):max(j) + 1, min(i2):max(i2) + 1]
        a = np.ma.filled(a.astype(float), np.nan)
        out['lat'] = [float(x) for x in la[min(j):max(j) + 1]]
        out['lon'] = [float(x) for x in lo[min(i2):max(i2) + 1]]
        out[k] = [[[None if not np.isfinite(v) else round(float(v), 2) for v in row] for row in day] for day in a]
        ds.close()
    out['source'] = 'NOAA CPC global unified gauge analysis, daily 1991-2020 normal (NOAA PSL)'
    json.dump(out, open(CLIM_CACHE, 'w'), separators=(',', ':'))
    return out


def _doy(d):
    """Index 0-364 into a 365-day climatology (29 Feb uses 28 Feb)."""
    if d.month == 2 and d.day == 29:
        d = d - dt.timedelta(days=1)
    return (dt.date(2001, d.month, d.day) - dt.date(2001, 1, 1)).days


def clim_points(c, k, day, pts):
    """Normal of variable k on `day` at points, bilinear over land cells (nearest land cell near the coast)."""
    g = np.array([[np.nan if v is None else v for v in row] for row in c[k][_doy(day)]], float)
    la, lo = np.array(c['lat']), np.array(c['lon'])
    if la[0] > la[-1]:
        la, g = la[::-1], g[::-1]
    out = []
    for x, y in pts:
        fy = np.interp(y, la, np.arange(len(la))); fx = np.interp(x, lo, np.arange(len(lo)))
        j0, i0 = min(int(fy), len(la) - 2), min(int(fx), len(lo) - 2)
        wy, wx = fy - j0, fx - i0
        q = [(g[j0, i0], (1 - wx) * (1 - wy)), (g[j0, i0 + 1], wx * (1 - wy)), (g[j0 + 1, i0], (1 - wx) * wy), (g[j0 + 1, i0 + 1], wx * wy)]
        q = [(v, w) for v, w in q if np.isfinite(v)]
        if q and sum(w for _, w in q) > 0.05:
            out.append(sum(v * w for v, w in q) / sum(w for _, w in q))
        else:
            d2 = (la[:, None] - y) ** 2 + (lo[None, :] - x) ** 2
            d2[~np.isfinite(g)] = np.inf
            jj, ii = np.unravel_index(np.argmin(d2), d2.shape)
            out.append(g[jj, ii] if np.isfinite(d2[jj, ii]) and d2[jj, ii] < 1.0 else np.nan)
    return np.array(out)


# ------------------------------------------------------------------ CFSv2 members
def cfs_url(cyc, mem, var):
    return f"{CFS}/cfs.{cyc:%Y%m%d}/{cyc:%H}/time_grib_{mem:02d}/{var}.{mem:02d}.{cyc:%Y%m%d%H}.daily.grb2"


def parse_idx(txt):
    rows = []
    for line in txt.strip().split('\n'):
        p = line.split(':')
        m = re.match(r'(\d+) hour fcst', p[5]) if len(p) > 5 else None
        if m:
            rows.append((int(p[1]), int(m.group(1))))
    return rows


_W = {}


def gauss_weights(h, pts):
    ni = eccodes.codes_get(h, 'Ni'); lats = np.array(eccodes.codes_get_array(h, 'distinctLatitudes'), float)
    lo1 = eccodes.codes_get(h, 'longitudeOfFirstGridPointInDegrees')
    key = (ni, len(lats), lo1)
    if key in _W:
        return _W[key]
    desc = lats[0] > lats[-1]
    L = lats[::-1] if desc else lats
    idx, w = [], []
    for x, y in pts:
        fx = ((x - lo1) % 360) / (360.0 / ni)
        i0 = int(fx) % ni; i1 = (i0 + 1) % ni; wx = fx - int(fx)
        j = int(np.searchsorted(L, y)) - 1
        j = min(max(j, 0), len(L) - 2)
        wy = (y - L[j]) / (L[j + 1] - L[j])
        ja, jb = (len(L) - 1 - j, len(L) - 2 - j) if desc else (j, j + 1)
        idx.append([ja * ni + i0, ja * ni + i1, jb * ni + i0, jb * ni + i1])
        w.append([(1 - wx) * (1 - wy), wx * (1 - wy), (1 - wx) * wy, wx * wy])
    _W[key] = (np.array(idx).T, np.array(w).T)
    return _W[key]


def member_daily(http, cyc, mem, var, days, pts):
    """{day: array} of daily rain (mm) / max / min (deg C) for one member over the given UTC days."""
    rows = parse_idx(http(cfs_url(cyc, mem, var) + '.idx').decode())
    t_first = dt.datetime.combine(days[0], dt.time(), tzinfo=dt.timezone.utc)
    t_last = dt.datetime.combine(days[-1], dt.time(), tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
    need = [(k, off, st) for k, (off, st) in enumerate(rows) if t_first < cyc + dt.timedelta(hours=st) <= t_last]
    if not need:
        return {}
    if cyc + dt.timedelta(hours=rows[-1][1]) < t_last:
        raise RuntimeError('member ends before week 4')
    k0, k1 = need[0][0], need[-1][0]
    start = rows[k0][0]
    end = rows[k1 + 1][0] - 1 if k1 + 1 < len(rows) else None
    buf = http(cfs_url(cyc, mem, var), rng=(start, end), timeout=120)
    per = {}
    for k, off, st in need:
        a = off - start
        b = (rows[k + 1][0] - start) if k + 1 < len(rows) else len(buf)
        h = eccodes.codes_new_from_message(buf[a:b])
        try:
            vals = np.asarray(eccodes.codes_get_values(h), float)
            idx, w = gauss_weights(h, pts)
        finally:
            eccodes.codes_release(h)
        v = (vals[idx] * w).sum(axis=0)
        end_t = cyc + dt.timedelta(hours=st)
        day = (end_t - dt.timedelta(hours=6)).date()
        per.setdefault(day, []).append(v)
    out = {}
    for day, vs in per.items():
        if len(vs) < 4:
            continue
        a = np.stack(vs)
        out[day] = a.sum(0) * 21600 if var == 'prate' else (a.max(0) if var == 'tmax' else a.min(0)) - 273.15
    return out


def latest_cycles(http, now, n):
    """Most recent CFSv2 cycles whose 4 members are all out to week 4."""
    out = []
    t = now.replace(minute=0, second=0, microsecond=0)
    t -= dt.timedelta(hours=t.hour % 6)
    for k in range(16):
        cyc = t - dt.timedelta(hours=6 * k)
        try:
            for m in (1, 2, 3, 4):
                http(cfs_url(cyc, m, 'tmin') + '.idx', rng=(0, 99), tries=2)
            out.append(cyc)
        except Exception:
            continue
        if len(out) >= n:
            break
    return out


# ------------------------------------------------------------------ outlook
def build(http, pts, d0, now, five_model, status, workers=12):
    """five_model: {'rain': [day arrays (mm) for days 0..], 'tmax': [...], 'tmin': [...]} from the main forecast."""
    t0 = time.time()
    day0 = d0.date()
    days = [day0 + dt.timedelta(days=i) for i in range(1, 7 * WEEKS + 1)]
    weeks = [days[7 * w:7 * w + 7] for w in range(WEEKS)]
    clim = climatology()
    normal = {k: [clim_points(clim, k, d, pts) for d in days] for k in VARS}
    cycles = latest_cycles(http, now, NCYC)
    if not cycles:
        raise RuntimeError('no complete CFSv2 cycle found')
    jobs = {(c, m, v): None for c in cycles for m in (1, 2, 3, 4) for v in VARS.values()}
    errors = []
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        fut = {pool.submit(member_daily, http, c, m, v, days, pts): (c, m, v) for c, m, v in jobs}
        for f in cf.as_completed(fut):
            try:
                jobs[fut[f]] = f.result()
            except Exception as e:
                errors.append(f'{fut[f][0]:%d %HZ} m{fut[f][1]} {fut[f][2]}: {e}'[:200])
    members = []
    for c in cycles:
        for m in (1, 2, 3, 4):
            d = {k: jobs[(c, m, v)] for k, v in VARS.items()}
            if all(d[k] and all(day in d[k] for day in days) for k in VARS):
                members.append(d)
    if len(members) < 8:
        raise RuntimeError(f'only {len(members)} complete CFSv2 members; {errors[:3]}')
    npts = len(pts)
    # per-member weekly values: rain total, tmax/tmin mean
    wk = {k: np.zeros((len(members), WEEKS, npts)) for k in VARS}
    for i, mbr in enumerate(members):
        for w, wdays in enumerate(weeks):
            wk['rain'][i, w] = sum(mbr['rain'][d] for d in wdays)
            for k in ('tmax', 'tmin'):
                wk[k][i, w] = np.mean([mbr[k][d] for d in wdays], axis=0)
    nw = {k: np.array([sum(normal[k][7 * w + j] for j in range(7)) / (1 if k == 'rain' else 7) for w in range(WEEKS)]) for k in VARS}
    # temperature bias from week 1 against the five-model average
    bias = {}
    for k in ('tmax', 'tmin'):
        fm = [a for a in five_model.get(k, [])[1:8] if a is not None]
        if len(fm) == 7:
            bias[k] = wk[k][:, 0].mean(0) - np.mean(fm, axis=0)
        else:
            bias[k] = np.zeros(npts)
    five_rain = []
    for w in range(2):
        fm = [a for a in five_model.get('rain', [])[1 + 7 * w:8 + 7 * w] if a is not None]
        five_rain.append(np.sum(fm, axis=0) if len(fm) == 7 else None)
    land = np.isfinite(nw['rain'][0])
    R = lambda a: [None if not np.isfinite(x) else round(float(x), 1) for x in a]
    out_weeks = []
    for w, wdays in enumerate(weeks):
        r = wk['rain'][:, w]
        mean = r.mean(0)
        nr = nw['rain'][w]
        p_up = (r >= UP * nr[None, :]).mean(0) * 100
        p_dn = (r <= DOWN * nr[None, :]).mean(0) * 100
        tx = wk['tmax'][:, w].mean(0) - bias['tmax']
        tn = wk['tmin'][:, w].mean(0) - bias['tmin']
        # Tamil Nadu (land cells with a normal) area means
        area = lambda a: float(np.nanmean(np.where(land, a, np.nan)))
        mem_area = np.array([area(r[i]) for i in range(len(members))])
        na = area(nr)
        item = dict(start=wdays[0].isoformat(), end=wdays[-1].isoformat(),
                    rain=R(mean), normal=R(nr), p_up=[int(round(x)) for x in p_up], p_dn=[int(round(x)) for x in p_dn],
                    tmax=R(tx), tmax_anom=R(tx - nw['tmax'][w]), tmin=R(tn), tmin_anom=R(tn - nw['tmin'][w]),
                    tn=dict(rain=round(area(mean), 1), normal=round(na, 1),
                            dep=round((area(mean) / na - 1) * 100) if na > 0 else None,
                            p_up=int(round((mem_area >= UP * na).mean() * 100)), p_dn=int(round((mem_area <= DOWN * na).mean() * 100)),
                            lo=round(float(np.percentile(mem_area, 10)), 1), hi=round(float(np.percentile(mem_area, 90)), 1),
                            tmax_anom=round(area(tx - nw['tmax'][w]), 1), tmin_anom=round(area(tn - nw['tmin'][w]), 1)))
        if w < 2 and five_rain[w] is not None:
            item['five'] = R(five_rain[w])
            item['tn']['five'] = round(area(five_rain[w]), 1)
            item['tn']['five_dep'] = round((area(five_rain[w]) / na - 1) * 100) if na > 0 else None
        out_weeks.append(item)
    status['outlook'] = dict(cycles=[f'{c:%d %b %HZ}' for c in cycles], members=len(members), errors=errors[:5],
                             seconds=round(time.time() - t0),
                             t_bias=dict(tmax=round(float(np.mean(bias['tmax'])), 1), tmin=round(float(np.mean(bias['tmin'])), 1)))
    return dict(weeks=out_weeks, members=len(members), cycles=[f'{c:%d %b %HZ}' for c in cycles],
                newest=f'{cycles[0]:%HZ %d %b}', source=clim.get('source'),
                t_bias=status['outlook']['t_bias'])
