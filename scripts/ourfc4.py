"""Our forecast v4: the GFS forecast corrected with 20 north-east monsoons of TN SMART gauges.

Training (data/ourfc4/train.npz, built once from the 2000-2019 study): for every district and day of 1 Oct-31 Dec,
what NOAA's GFS ensemble reforecast (GEFSv12, the current GFS model re-run on past days) forecast a day ahead, next to
the district average of the TN SMART gauges. Inputs per district and day:
  GFS rain (district average over its gauges' squares, wettest square), rain within 100 km, the district's usual rain,
  5 GFS ensemble members (mean, wettest, share with 35 mm+, share with a 64.5 mm+ square),
  storm energy (CAPE, max), moisture (precipitable water, mean), spin at 850 hPa (~1.5 km, max) and 850 hPa wind (mean).
Three things are learned (gradient-boosted trees, refitted every run in ~1 minute so no binary model file is stored):
  amount  - the district average rain (then matched to the gauges' own spread of amounts, so heavy days stay heavy),
  risk    - the chance that some gauge in the district gets 64.5 mm or more (IMD heavy rain),
  reach   - a 'could reach' amount that the district's wettest gauge stays under 9 times in 10.
Tested by leaving one year out at a time (2000-2019): heavy district days (district average 35 mm+) given at least 75%
of their rain the day before went from 17% (GFS as it is) to 30%, with no more false heavy calls.

Live (forecast.py): per page day the same inputs come from the latest GFS run (rain, CAPE, precipitable water, 850 hPa
wind at the forecast squares) and the first 5 GEFS members; without the members a second model that does not use them
is used. Each square then gets the district amount spread like the models' average pattern inside the district."""
import json, os, math
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
VERSION = 4
NB_KM = 100.0


def _feat(fc_avg, fc_max, clim, nb_max, nb_avg, ens, cape, pwat, vo, u, v):
    l = np.log1p
    f = [l(fc_avg), l(fc_max), l(clim), l(nb_max), l(nb_avg)]
    if ens is not None:
        f += [l(ens[0]), l(ens[1]), ens[2], ens[3]]
    f += [l(max(cape, 0) / 100), pwat / 10, (pwat / 10) * l(fc_avg),
          max(-2.0, min(6.0, vo / 2)), u / 5, v / 5, max(0.0, vo) / 2 * l(fc_avg)]
    return f


def _qmap(ptr, otr):
    q = np.linspace(0, 1, 401); a = np.quantile(ptr, q); b = np.quantile(otr, q)
    return lambda p: np.interp(p, a, b) + np.maximum(0, p - a[-1]) * (b[-1] / max(a[-1], 1e-6))


def train():
    """Fit the six models (amount, risk, reach; with and without ensemble members). Returns a dict."""
    from sklearn.ensemble import HistGradientBoostingRegressor as HR, HistGradientBoostingClassifier as HC
    meta = json.load(open(P('data/ourfc4/meta.json'))); z = np.load(P('data/ourfc4/train.npz'))
    C = {c: i for i, c in enumerate(meta['columns'])}; A = z['X'].astype(float); dname = [meta['districts'][k] for k in z['district']]
    clim = {}
    for d, o in zip(dname, A[:, C['obs_avg']]):
        clim.setdefault(d, []).append(o)
    clim = {d: float(np.mean(v)) for d, v in clim.items()}
    def rows(with_ens):
        X = []
        for r, d in zip(A, dname):
            ens = (r[C['ens_mean']], r[C['ens_wettest']], r[C['ens_p35']], r[C['ens_pmax65']]) if with_ens else None
            X.append(_feat(r[C['fc_avg']], r[C['fc_max']], clim.get(d, 5.0), r[C['nb_max']], r[C['nb_avg']], ens,
                           r[C['cape']], r[C['pwat']], r[C['vo850']], r[C['u850']], r[C['v850']]))
        return np.array(X)
    oa, om = A[:, C['obs_avg']], A[:, C['obs_max']]
    kw = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=40, early_stopping=False)
    M = dict(version=VERSION, clim=clim, rows=len(A))
    for tag, with_ens in (('ens', True), ('det', False)):
        X = rows(with_ens)
        amt = HR(l2_regularization=1.0, **kw).fit(X, np.log1p(oa))
        M[f'amount_{tag}'] = amt; M[f'qmap_{tag}'] = _qmap(np.expm1(amt.predict(X)), oa)
        M[f'risk_{tag}'] = HC(**kw).fit(X, (om >= 64.5).astype(int))
        M[f'reach_{tag}'] = HR(loss='quantile', quantile=0.9, **kw).fit(X, np.log1p(om))
    return M


def districts(pts, stations):
    """Districts from the TN SMART gauge list: gauge squares (each gauge's nearest square, gauge-weighted), the squares
    each district covers, district centres, and every square's district (its nearest gauge's)."""
    lo = np.array([p[0] for p in pts]); la = np.array([p[1] for p in pts])
    g_cells, cen, sq_dist, best = {}, {}, {}, {}
    for k, s in stations.items():
        if s.get('lat') is None or s.get('lon') is None or not s.get('district'):
            continue
        d2 = (lo - s['lon']) ** 2 + (la - s['lat']) ** 2; i = int(d2.argmin())
        cen.setdefault(s['district'], []).append((s['lat'], s['lon']))
        if d2[i] < 0.3 ** 2:
            g_cells.setdefault(s['district'], []).append(i)
        for j in np.where(d2 < 0.6 ** 2)[0]:                  # nearest gauge decides each square's district
            if j not in best or d2[j] < best[j]:
                best[int(j)] = float(d2[j]); sq_dist[int(j)] = s['district']
    cen = {d: np.mean(v, 0) for d, v in cen.items()}
    for j in range(len(pts)):
        if j not in sq_dist:
            sq_dist[j] = min(cen, key=lambda d: (cen[d][0] - la[j]) ** 2 + (cen[d][1] - lo[j]) ** 2)
    return dict(g_cells={d: v for d, v in g_cells.items() if len(v) >= 1}, cen=cen, sq=sq_dist)


def vorticity(pts, u, v):
    """850 hPa relative vorticity (x1e-5 per second) on the forecast squares (0.25 degree), from neighbouring squares."""
    idx = {(round(p[0] * 4), round(p[1] * 4)): i for i, p in enumerate(pts)}
    out = np.zeros(len(pts))
    for i, (lo, la) in enumerate(pts):
        x, y = round(lo * 4), round(la * 4)
        dx = 0.25 * 111.32e3 * math.cos(math.radians(la)); dy = 0.25 * 110.6e3
        e, w, n, s = idx.get((x + 1, y)), idx.get((x - 1, y)), idx.get((x, y + 1)), idx.get((x, y - 1))
        if e is not None and w is not None: dvdx = (v[e] - v[w]) / (2 * dx)
        elif e is not None: dvdx = (v[e] - v[i]) / dx
        elif w is not None: dvdx = (v[i] - v[w]) / dx
        else: dvdx = 0.0
        if n is not None and s is not None: dudy = (u[n] - u[s]) / (2 * dy)
        elif n is not None: dudy = (u[n] - u[i]) / dy
        elif s is not None: dudy = (u[i] - u[s]) / dy
        else: dudy = 0.0
        out[i] = (dvdx - dudy) * 1e5
    return out


def predict_day(M, geo, gfs_rain, members, cape, pwat, u, v, vo):
    """One page day. gfs_rain: GFS rain per square; members: list of 5 GEFS member rain arrays or None;
    cape/pwat/u/v/vo: per square (window max / mean / mean / mean / max). Returns {district: (amount, risk, reach)}."""
    G, cen = geo['g_cells'], geo['cen']
    base = {}
    for d, cells in G.items():
        ix = np.array(cells); s = sorted(set(cells))
        base[d] = dict(avg=float(np.mean(gfs_rain[ix])), mx=float(np.max(gfs_rain[s])), s=s, ix=ix)
    km = lambda a, b: math.hypot((a[0] - b[0]) * 110.6, (a[1] - b[1]) * 108.0)
    tag = 'ens' if members is not None else 'det'
    X, names = [], []
    for d, b in base.items():
        nb = [q for q in base if d in cen and q in cen and km(cen[q], cen[d]) <= NB_KM] or [d]
        ens = None
        if members is not None:
            avgs = [float(np.mean(m[b['ix']])) for m in members]; mxs = [float(np.max(m[b['s']])) for m in members]
            ens = (float(np.mean(avgs)), float(max(avgs)), sum(a >= 35 for a in avgs) / len(avgs), sum(x >= 64.5 for x in mxs) / len(mxs))
        s = b['s']
        X.append(_feat(b['avg'], b['mx'], M['clim'].get(d, 5.0), max(base[q]['mx'] for q in nb), float(np.mean([base[q]['avg'] for q in nb])),
                       ens, float(np.max(cape[s])), float(np.mean(pwat[s])), float(np.max(vo[s])), float(np.mean(u[s])), float(np.mean(v[s]))))
        names.append(d)
    X = np.array(X)
    amt = np.maximum(0, M[f'qmap_{tag}'](np.expm1(M[f'amount_{tag}'].predict(X))))
    risk = M[f'risk_{tag}'].predict_proba(X)[:, 1]
    reach = np.expm1(M[f'reach_{tag}'].predict(X))
    return {d: (round(float(a), 1), round(float(r), 2), round(float(q))) for d, a, r, q in zip(names, amt, risk, reach)}, tag


def spread(geo, dist_out, pattern):
    """Square values: the district amount spread like the models' average pattern inside the district.
    Returns (amounts per square, factor per square relative to the pattern)."""
    G, SQ = geo['g_cells'], geo['sq']
    pb = {d: float(np.mean([pattern[i] for i in cells])) for d, cells in G.items()}
    vals, fac = [], []
    for i in range(len(pattern)):
        d = SQ.get(i)
        if d not in dist_out or d not in pb:
            vals.append(None); fac.append(None); continue
        A = dist_out[d][0]; f = min(10.0, (A + 0.2) / (pb[d] + 0.2))
        vals.append(round(max(0.0, (pattern[i] + 0.2) * f - 0.2), 1)); fac.append(f)
    return vals, fac
