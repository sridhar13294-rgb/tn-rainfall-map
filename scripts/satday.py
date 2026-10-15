"""sat-radar branch: daily satellite rain totals, compared with TN SMART gauges.

Every 30 minutes (from the satcheck job) each new 15-minute satellite rain picture (EUMETSAT H SAF H63) over Tamil Nadu
is read and added up over TN SMART days (24 hours to 08:30 IST, i.e. 03 UTC to 03 UTC). For each day we keep:
  data/satradar/satday/D.json  raw satellite rain rate at every TN SMART gauge for every picture (so any correction can
                               be re-applied later), and
  data/satradar/satday/D.npz   the day's raw total on a 0.05 degree grid, counting only rates at or above each of a few
                               cut-offs (so any 'cut-off + multiplier' correction can be applied exactly afterwards).
When TN SMART publishes day D (data/daily/D.json on main), the satellite total at each gauge is compared with the gauge
(on the same 0.25 degree squares the forecast check uses) and a gauge factor is fitted over the last 14 days: the
cut-off and multiplier for the raw satellite rate that make the daily totals best match the gauges (rain/no-rain skill,
with the total amount kept within -15%/+20%). Results: data/satradar/satgauge.json (scores of the radar-matched and the
gauge-fitted correction), data/satradar/satdaily/D.json (satellite day totals at every gauge and on a 0.1 degree grid,
for the forecast check), and satcal.json (gauge_fit).
"""
import concurrent.futures as cf, datetime as dt, glob, io, json, os, time, urllib.request
import numpy as np
from PIL import Image

OUT = 'data/satradar'; SD = f'{OUT}/satday'; os.makedirs(SD, exist_ok=True)
LON0, LON1, LAT0, LAT1, STEP = 75.5, 81.5, 7.0, 14.5, 0.05
NX, NY = int(round((LON1 - LON0) / STEP)), int(round((LAT1 - LAT0) / STEP))
UTC = dt.timezone.utc
MAIN = 'https://raw.githubusercontent.com/sridhar13294-rgb/tn-rainfall-map/main/'
RAIN, HEAVY, FIT_DAYS = 2.5, 64.5, 14
CUTS = [0, 1, 2, 3, 5, 7, 10, 15]                                        # mm/h, raw satellite rate
SCALES = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.85, 1.0]
UA = {'User-Agent': 'Mozilla/5.0 (tn-rainfall-map satellite daily check)'}


def get(u, t=90, tries=3):
    if u.startswith(MAIN) and os.environ.get('MAIN_DIR'):              # local copy of main (tests)
        return open(os.path.join(os.environ['MAIN_DIR'], u[len(MAIN):]), 'rb').read()
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(2 * (k + 1))
    raise last


STOPS = [(0.0, (255, 255, 204)), (0.2, (227, 244, 192)), (1.05, (198, 232, 179)), (2.0, (162, 218, 183)), (3.0, (126, 204, 186)),
         (5.0, (96, 194, 191)), (7.0, (65, 183, 196)), (10.0, (47, 164, 194)), (15.0, (29, 145, 191)), (20.0, (32, 120, 180)),
         (30.0, (34, 94, 168)), (49.2, (12, 44, 133)), (60.0, (8, 30, 100))]


def decode(rgba):
    a = rgba[..., 3] > 0; rgb = rgba[..., :3].astype(float); best = np.full(a.shape, 1e9); val = np.zeros(a.shape)
    for (v0, c0), (v1, c1) in zip(STOPS, STOPS[1:]):
        c0, c1 = np.array(c0, float), np.array(c1, float); d = c1 - c0
        t = np.clip(((rgb - c0) @ d) / (d @ d), 0, 1); dist = np.linalg.norm(rgb - (c0 + t[..., None] * d), axis=-1)
        m = dist < best; best[m] = dist[m]; val[m] = (v0 + t * (v1 - v0))[m]
    val[~a] = 0; val[a & (best > 60)] = 0
    return val


def h63(t):
    """Raw satellite rain rate (mm/h) on the 0.05 degree grid, row 0 = south (picture read at 0.025 degree and averaged)."""
    q = (f'https://view.eumetsat.int/geoserver/ows?service=WMS&version=1.3.0&request=GetMap&layers=msg_iodc:h63&styles=&crs=EPSG:4326'
         f'&bbox={LAT0},{LON0},{LAT1},{LON1}&width={NX * 2}&height={NY * 2}&format=image/png&transparent=true&time={t:%Y-%m-%dT%H:%M:00Z}')
    r = decode(np.asarray(Image.open(io.BytesIO(get(q))).convert('RGBA')))[::-1]
    return r.reshape(NY, 2, NX, 2).mean(axis=(1, 3))


def corr_fn(cal):
    """The page's correction: rates below the cut-off dropped, the rest mapped with the radar-matched table (or scale)."""
    cut = float(cal.get('cut_mm_h') or 0); lut = cal.get('lut'); sc = float(cal.get('scale') or 0.3)
    if lut and len(lut) >= 2:
        xs = np.array([p[0] for p in lut]); ys = np.array([p[1] for p in lut])
        def f(r):
            r = np.asarray(r, float); y = np.interp(r, xs, ys)
            hi = r > xs[-1]; y[hi] = ys[-1] + (ys[-1] - ys[-2]) / max(xs[-1] - xs[-2], 1e-6) * (r[hi] - xs[-1])
            return np.where(r >= cut, y, 0.0)
    else:
        def f(r):
            r = np.asarray(r, float); return np.where(r >= cut, r * sc, 0.0)
    return f


def day_of(t):
    """TN SMART day a picture time belongs to (the day whose 08:30 IST ends the window)."""
    return (t - dt.timedelta(hours=3)).date() + dt.timedelta(days=1)


def window(day):
    t0 = dt.datetime(day.year, day.month, day.day, 3, tzinfo=UTC) - dt.timedelta(days=1)
    return [t0 + dt.timedelta(minutes=15 * k) for k in range(96)]


_stations = None
def stations():
    global _stations
    if _stations is None:
        st = json.loads(get(MAIN + 'data/stations.json'))
        _stations = {k: v for k, v in st.items() if v.get('lat') is not None and v.get('lon') is not None
                     and LAT0 <= v['lat'] < LAT1 and LON0 <= v['lon'] < LON1}
    return _stations


def load_day(day):
    f = f'{SD}/{day}.json'
    if os.path.exists(f):
        return json.load(open(f))
    st = stations()
    return dict(day=day.isoformat(), window=[window(day)[0].isoformat(), (window(day)[0] + dt.timedelta(days=1)).isoformat()],
                gauge_ids=sorted(st), frames={}, missing=[])


def save_day(D):
    json.dump(D, open(f'{SD}/{D["day"]}.json', 'w'), separators=(',', ':'))


def accumulate(L, budget=48):
    """Read pictures not yet added (current and previous TN SMART day), at most `budget` per run."""
    if L is None:
        return {}
    st = stations(); done = {}
    for day in sorted({day_of(L), day_of(L) - dt.timedelta(days=1)}):
        D = load_day(day); gid = D['gauge_ids']
        gj = np.array([min(NY - 1, int((st[k]['lat'] - LAT0) / STEP)) if k in st else 0 for k in gid])
        gi = np.array([min(NX - 1, int((st[k]['lon'] - LON0) / STEP)) if k in st else 0 for k in gid])
        todo = [t for t in window(day) if t <= L and f'{t:%H%M}' not in D['frames'] and f'{t:%H%M}' not in D['missing']][:budget]
        if not todo:
            continue
        npz = f'{SD}/{day}.npz'
        acc = np.load(npz)['acc'].astype(float) if os.path.exists(npz) else np.zeros((len(CUTS), NY, NX))
        def safe(t):
            try: return h63(t)
            except Exception as e: return e
        with cf.ThreadPoolExecutor(6) as ex:
            for t, r in zip(todo, ex.map(safe, todo)):
                key = f'{t:%H%M}'
                if isinstance(r, Exception):
                    if (L - t).total_seconds() > 3 * 3600:             # still failing 3 h later: count as missing
                        D['missing'].append(key)
                    continue
                D['frames'][key] = [round(float(x), 2) for x in r[gj, gi]]
                for k, c in enumerate(CUTS):
                    acc[k] += np.where(r >= c, r, 0) * 0.25
        budget -= len(todo); done[day.isoformat()] = len(D['frames'])
        D['complete'] = len(D['frames']) + len(D['missing']) >= 96
        save_day(D); np.savez_compressed(npz, acc=acc.astype(np.float32), cuts=np.array(CUTS, float), frames=len(D['frames']))
        if budget <= 0:
            break
    return done


# ---------- comparison with the gauges
def gauge_obs(day):
    f = f'{OUT}/gauges/{day}.json'
    if os.path.exists(f):
        return json.load(open(f))
    try:
        obs = json.loads(get(MAIN + f'data/daily/{day}.json'))
    except Exception:
        return None
    os.makedirs(f'{OUT}/gauges', exist_ok=True); json.dump(obs, open(f, 'w'))
    return obs


def sat_totals(D, corr):
    """Satellite day total (mm) at each gauge, with the given correction; scaled up for missing pictures."""
    n = len(D['frames'])
    if n < 72:                                                          # need at least 18 of 24 hours
        return None
    S = np.array([corr(np.array(v)) for v in D['frames'].values()]).sum(0) * 0.25 * 96 / n
    return dict(zip(D['gauge_ids'], S))


def cells(st, sids):
    """0.25 degree squares (same as the forecast check) -> gauges in them."""
    out = {}
    for k in sids:
        if k in st:
            out.setdefault((round(st[k]['lon'] / .25), round(st[k]['lat'] / .25)), []).append(k)
    return out


def score(pairs):
    pairs = [(s, o) for s, o in pairs]
    if not pairs:
        return None
    s = np.array([p[0] for p in pairs]); o = np.array([p[1] for p in pairs])
    h = int(((s >= RAIN) & (o >= RAIN)).sum()); m = int(((s < RAIN) & (o >= RAIN)).sum()); f = int(((s >= RAIN) & (o < RAIN)).sum())
    n = len(s); hr = (h + m) * (h + f) / n
    ets = (h - hr) / (h + m + f - hr) if (h + m + f - hr) > 0 else None
    return dict(cells=n, mae=round(float(np.abs(s - o).mean()), 1), bias=round(float(s.sum() / o.sum()), 2) if o.sum() > 0 else None,
                pod=round(h / (h + m), 2) if h + m else None, far=round(f / (h + f), 2) if h + f else None,
                ets=round(ets, 2) if ets is not None else None,
                heavy=dict(hit=int(((s >= HEAVY) & (o >= HEAVY)).sum()), miss=int(((s < HEAVY) & (o >= HEAVY)).sum()),
                           false=int(((s >= HEAVY) & (o < HEAVY)).sum())),
                sat_mean=round(float(s.mean()), 1), gauge_mean=round(float(o.mean()), 1))


def wmedian(x, w):
    i = np.argsort(x); x, w = x[i], w[i]; c = np.cumsum(w)
    return float(x[np.searchsorted(c, c[-1] / 2)])


def lin(c, a):
    return lambda r: np.where(np.asarray(r, float) >= c, np.asarray(r, float) * a, 0.0)


def pairs_for(D, obs, corr, st):
    S = sat_totals(D, corr)
    if not S:
        return None
    sids = [k for k in S if obs.get(k) is not None]
    return [(float(np.mean([S[k] for k in ks])), float(np.mean([obs[k] for k in ks]))) for ks in cells(st, sids).values()]


def compare(cal, now):
    """Score every finished day that has gauge readings with the radar-matched correction, fit the gauge correction
    (cut-off + multiplier) over the last 14 days, and write satgauge.json and satdaily/D.json."""
    st = stations(); radar_corr = corr_fn(cal); days = []
    for f in sorted(glob.glob(f'{SD}/*.json')):
        D = json.load(open(f)); day = dt.date.fromisoformat(D['day'])
        if (now.date() - day).days > 30 or not D.get('complete') or len(D['frames']) < 72:
            continue
        obs = gauge_obs(day)
        if not obs:
            continue
        P = pairs_for(D, obs, radar_corr, st)
        if P and len(P) >= 20:
            days.append(dict(D=D, obs=obs, day=D['day'], radar=P))
    if not days:
        return None
    recent = days[-FIT_DAYS:]
    # raw satellite rate at each gauge square for every picture, once per day, then every candidate correction
    grid = []
    for c in CUTS:
        for a in SCALES:
            P = [p for d in recent for p in pairs_for(d['D'], d['obs'], lin(c, a), st)]
            sc = score(P); grid.append(dict(cut=c, scale=a, **{k: sc[k] for k in ('mae', 'bias', 'ets', 'pod', 'far')}))
    wet = sum(1 for d in recent for s_, o in d['radar'] if o >= RAIN)
    fit, why = None, None
    if len(recent) >= 3 and wet >= 100:
        ok = [g for g in grid if g['bias'] and 0.85 <= g['bias'] <= 1.2 and g['ets'] is not None]
        if ok:
            fit = max(ok, key=lambda g: (g['ets'], -g['mae']))
        else:
            fit = min(grid, key=lambda g: abs(np.log(g['bias'])) if g['bias'] else 9)
    else:
        why = f'{len(recent)} day(s) and {wet} rainy gauge squares so far; the gauge fit starts after 3 days and 100 rainy squares'
    use = lin(fit['cut'], fit['scale']) if fit else radar_corr
    out = dict(updated=now.isoformat(), method='satellite day totals vs TN SMART gauges on 0.25 degree squares (same squares as the forecast check)',
               gauge_fit=fit, note=why, fit_days=[d['day'] for d in recent], radar_cut=cal.get('cut_mm_h'),
               overall=dict(radar_matched=score([p for d in recent for p in d['radar']]),
                            gauge_fitted=score([p for d in recent for p in pairs_for(d['D'], d['obs'], use, st)])),
               days=[dict(day=d['day'], frames=len(d['D']['frames']), radar_matched=score(d['radar']),
                          gauge_fitted=score(pairs_for(d['D'], d['obs'], use, st))) for d in days],
               candidates=sorted(grid, key=lambda g: -(g['ets'] or 0))[:12])
    json.dump(out, open(f'{OUT}/satgauge.json', 'w'), indent=1)
    publish_daily(use, fit, now)
    return out


def publish_daily(corr, fit, now):
    """Satellite day totals with the correction in use, at every gauge and on a 0.1 degree grid (for the forecast check)."""
    os.makedirs(f'{OUT}/satdaily', exist_ok=True)
    for f in sorted(glob.glob(f'{SD}/*.json')):
        D = json.load(open(f)); day = D['day']
        if (now.date() - dt.date.fromisoformat(day)).days > 30 or not D.get('complete'):
            continue
        S = sat_totals(D, corr)
        if not S:
            continue
        rec = dict(day=day, frames=len(D['frames']), correction=dict(cut=fit['cut'], scale=fit['scale']) if fit else 'radar-matched',
                   gauges={k: round(float(v), 1) for k, v in S.items()})
        npz = f'{SD}/{day}.npz'
        if fit and os.path.exists(npz):
            z = np.load(npz); cuts = list(z['cuts']) if 'cuts' in z else None
            if cuts and fit['cut'] in cuts and z['acc'].ndim == 3:
                g = z['acc'][cuts.index(fit['cut'])] * fit['scale'] * 96 / max(1, int(z['frames']))
                g = g.reshape(NY // 2, 2, NX // 2, 2).mean(axis=(1, 3))       # 0.1 degree
                rec['grid'] = dict(lon0=LON0, lat0=LAT0, step=0.1, nx=NX // 2, ny=NY // 2, mm=[round(float(x), 1) for x in g.ravel()])
        json.dump(rec, open(f'{OUT}/satdaily/{day}.json', 'w'), separators=(',', ':'))


def backfill_from_acc():
    """Turn the earlier test files (acc_D.json: raw satellite rate at every gauge for each picture) into satday files."""
    for f in sorted(glob.glob(f'{OUT}/acc_*.json')):
        day = f[-15:-5]
        if os.path.exists(f'{SD}/{day}.json'):
            continue
        A = json.load(open(f)); t0 = dt.datetime.fromisoformat(A['window'][0])
        frames, missing = {}, []
        for k, v in enumerate(A['h63_series']):
            key = f'{t0 + dt.timedelta(minutes=15 * k):%H%M}'
            if v is None: missing.append(key)
            else: frames[key] = v
        save_day(dict(day=day, window=A['window'], gauge_ids=A['gauge_ids'], frames=frames, missing=missing,
                      complete=True, source='backfill from the 10-15 Oct satellite test'))


def run(L, cal, now):
    backfill_from_acc()
    acc = accumulate(L)
    out = compare(cal, now)
    return dict(accumulated=acc, gauge_fit=out['gauge_fit'] if out else None, days_compared=len(out['days']) if out else 0)


if __name__ == '__main__':
    import sys
    now = dt.datetime.now(UTC)
    cal = json.load(open(f'{OUT}/satcal.json')) if os.path.exists(f'{OUT}/satcal.json') else {}
    backfill_from_acc()
    print(json.dumps(compare(cal, now), indent=1)[:4000] if 'compare' in sys.argv else '')
