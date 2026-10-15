"""Our own rain forecast: a small learning model on top of the other models.

Inputs, for every 0.25 degree forecast square and day:
  1. the average of the other models (GFS, ECMWF, ECMWF AI, GEM, ICON) for that day,
  2. the rain that really fell there just before the forecast was made: TN SMART gauges where the square has a gauge,
     otherwise our satellite day total (corrected with TN SMART, from the sat-radar background job),
  3. how the models compared with TN SMART and the satellite at that square over the last 14 days.
What it learns (refitted every forecast run from the saved forecasts and what fell afterwards):
  rain = local factor x b0 * (1 + model average)^b1 * (1 + rain yesterday)^b2 * (1 + rain last 3 days)^b3 - 1
  fitted in log form, separately for 1, 2 and 3 days ahead, pulled towards "just the model average" while there are few
  days to learn from. Squares with a gauge count fully; satellite-only squares count less (by the satellite's own skill).
Confidence per square and day: high / medium / low from (a) whether the models agree, (b) whether the square is checked
by a gauge or by the satellite, (c) how far ahead the day is.
"""
import datetime as dt, json, math, os, urllib.request
import numpy as np
import verify

LOCAL_DAYS = 14          # local factor: last 14 days
PRIOR = 40.0             # pull towards "just the model average" (in squares x days of evidence)
MIN_SAMPLES = 150
SATGAUGE = 'https://raw.githubusercontent.com/sridhar13294-rgb/tn-rainfall-map/sat-radar/data/satradar/satgauge.json'
OUT = verify.P('data', 'verify', 'ourfc.json')
NAME = 'Our forecast'


def _sat_weight():
    """How much a satellite-only square counts (0-0.6), from the satellite's own match with the gauges."""
    try:
        with urllib.request.urlopen(urllib.request.Request(SATGAUGE, headers={'User-Agent': 'tn-rainfall-map'}), timeout=30) as r:
            g = json.loads(r.read())
        ets = ((g.get('overall') or {}).get('gauge_fitted') or {}).get('ets') or 0
        return round(max(0.0, min(0.6, (ets - 0.15) * 2.4)), 2), ets
    except Exception:
        return 0.0, None


class Obs:
    """What fell on each TN SMART day at each forecast square: gauges first, else the corrected satellite total."""
    def __init__(self, pts, sat_w):
        self.pts, self.sat_w, self.cells = pts, sat_w, verify.gauge_cells(pts)
        self.cache = {}

    def day(self, d):
        if d in self.cache:
            return self.cache[d]
        out = {}
        try:
            obs = json.load(open(verify.OBS('data', 'daily', d.isoformat() + '.json')))
        except Exception:
            obs = None
        if obs:
            for i, sids in self.cells.items():
                v = [obs[s] for s in sids if obs.get(s) is not None]
                if v:
                    out[i] = (sum(v) / len(v), 1.0, 'gauge')
        if self.sat_w > 0:
            S = verify.sat_day(d)
            if S and S.get('grid'):
                for i, (lo, la) in enumerate(self.pts):
                    if i not in out:
                        v = verify.sat_at(S, lo, la)
                        if v is not None:
                            out[i] = (v, self.sat_w, 'satellite')
        self.cache[d] = out if len(out) >= 20 else None
        return self.cache[d]

    def recent(self, last):
        """(rain on day `last`, mean of the 3 days to `last`) per square."""
        a, b = self.day(last), [self.day(last - dt.timedelta(days=k)) for k in range(3)]
        if not a:
            return {}
        out = {}
        for i, (v, w, src) in a.items():
            vs = [x[i][0] for x in b if x and i in x]
            out[i] = (v, sum(vs) / len(vs))
        return out


def _fit(X, y, w, prior):
    """Weighted least squares, pulled towards `prior` coefficients."""
    X, y, w = np.asarray(X), np.asarray(y), np.asarray(w)
    A = X.T @ (X * w[:, None]) + PRIOR * np.eye(X.shape[1])
    rhs = X.T @ (w * y) + PRIOR * np.asarray(prior)
    return np.linalg.solve(A, rhs)


def train(pts, now):
    """Learn from saved forecasts (the other models' average) and what fell afterwards. Returns the model dict."""
    sat_w, sat_ets = _sat_weight()
    O = Obs(pts, sat_w)
    runs = []
    if os.path.isdir(verify.FC_DIR):
        for f in sorted(os.listdir(verify.FC_DIR)):
            try:
                runs.append((verify.utc(f[:10]), os.path.join(verify.FC_DIR, f)))
            except ValueError:
                pass
    samples = {1: [], 2: [], 3: []}
    resid = {}                                                 # square -> [(obs, pred_without_local, weight)] (lead 1-2)
    last_day = now.date()
    for back in range(1, 31):
        D = last_day - dt.timedelta(days=back)
        tgt = O.day(D)
        if not tgt:
            continue
        ws = verify.window_start(D)
        for L in (1, 2, 3):
            cand = [(t, p) for t, p in runs if ws - dt.timedelta(hours=24 * L) <= t < ws - dt.timedelta(hours=24 * (L - 1))]
            if not cand:
                continue
            fc = json.load(open(cand[-1][1]))['days'].get(D.isoformat())
            if not fc or 'Average' not in fc:
                continue
            rec = O.recent(D - dt.timedelta(days=L + 1))         # the latest TN SMART day out when that forecast was made
            for i, (ob, w, src) in tgt.items():
                if i >= len(fc['Average']) or i not in rec:
                    continue
                samples[L].append((fc['Average'][i] / 10, rec[i][0], rec[i][1], ob, w, i, D))
    model = dict(updated=now.strftime('%Y-%m-%dT%H:%MZ'), satellite_weight=sat_w, satellite_ets=sat_ets, leads={})
    for L, S in samples.items():
        if len(S) < MIN_SAMPLES:
            model['leads'][str(L)] = dict(coef=[0, 1, 0, 0], samples=len(S), note='not enough days yet: model average only')
            continue
        X = [[1, math.log1p(a), math.log1p(r1), math.log1p(r3)] for a, r1, r3, *_ in S]
        y = [math.log1p(s[3]) for s in S]
        w = [s[4] for s in S]
        c = _fit(X, y, w, [0, 1, 0, 0])
        pred = [math.expm1(max(0, float(np.dot(c, x)))) for x in X]
        tot_o = sum(s[3] * s[4] for s in S); tot_p = sum(p * s[4] for p, s in zip(pred, S))
        scale = min(3.0, max(0.33, tot_o / tot_p)) if tot_p > 0 else 1.0     # keep the total amount right
        # skill on the training days, against the plain model average (same squares, same weights)
        def mae(vals):
            return sum(abs(v - s[3]) * s[4] for v, s in zip(vals, S)) / sum(s[4] for s in S)
        model['leads'][str(L)] = dict(coef=[round(float(x), 4) for x in c], scale=round(scale, 3), samples=len(S),
                                      days=len({s[6] for s in S}), mae_ours=round(mae([p * scale for p in pred]), 2),
                                      mae_average=round(mae([s[0] for s in S]), 2))
        if L in (1, 2):
            for p, s in zip(pred, S):
                if (now.date() - s[6]).days <= LOCAL_DAYS:
                    resid.setdefault(s[5], []).append((s[3], p * scale, s[4]))
    # local factor per square: how much more or less rain fell than we would have said, shrunk towards 1
    local = {}
    for i, rs in resid.items():
        o = sum(r[0] * r[2] for r in rs); p = sum(r[1] * r[2] for r in rs); n = sum(r[2] for r in rs)
        k = n / (n + 5)
        f = (o + 5) / (p + 5)
        local[i] = round(max(0.5, min(2.0, 1 + k * (f - 1))), 2)
    model['local'] = local
    latest = next((d for d in [last_day - dt.timedelta(days=b) for b in range(0, 6)] if O.day(d)), None)
    model['latest_obs_day'] = latest.isoformat() if latest else None
    model['support'] = {i: v[2] for i, v in (O.day(latest) or {}).items()} if latest else {}
    model['_recent'] = O.recent(latest) if latest else {}
    model['_obs'] = O
    return model


def predict(model, avg, lead, i, recent):
    """Our rain (mm) for one square: avg = other models' average, lead = days ahead (1..), recent = (yesterday, 3-day)."""
    if avg is None:
        return None
    L = str(min(max(lead, 1), 3))
    m = model['leads'].get(L) or {}
    c = m.get('coef', [0, 1, 0, 0]); sc = m.get('scale', 1.0)
    r1, r3 = recent if recent else (None, None)
    if r1 is None or lead > 3:                                  # beyond 3 days (or nothing observed): model average part only
        x = c[0] + c[1] * math.log1p(avg)
        if r1 is not None and lead > 3:
            fade = max(0.0, 1 - (lead - 3) / 3)
            x += fade * (c[2] * math.log1p(r1) + c[3] * math.log1p(r3))
    else:
        x = c[0] + c[1] * math.log1p(avg) + c[2] * math.log1p(r1) + c[3] * math.log1p(r3)
    v = math.expm1(max(0.0, x)) * sc * float(model['local'].get(i, model['local'].get(str(i), 1.0)))
    return round(v, 1)


def confidence(model_vals, lead, support):
    """'high' / 'medium' / 'low' from model agreement, observation support at the square and how far ahead."""
    xs = [v for v in model_vals if v is not None]
    if not xs:
        return None
    mean = sum(xs) / len(xs); sd = (sum((v - mean) ** 2 for v in xs) / len(xs)) ** .5
    agree = mean < 2.5 and max(xs) < 10 or (mean >= 2.5 and sd / mean < 0.45)
    checked = support in ('gauge', 'satellite')
    level = 2 if agree and checked else 1 if agree or checked else 0
    if lead > 3:
        level -= 1                                             # 4 days or more ahead: one level lower
    if lead > 7:
        level = 0
    return 'high' if level >= 2 else 'medium' if level == 1 else 'low'


def save(model):
    m = {k: v for k, v in model.items() if not k.startswith('_')}
    json.dump(m, open(OUT, 'w'), indent=1)
