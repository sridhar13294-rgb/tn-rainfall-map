"""Our own rain forecast (v3): our own prediction; the other models are only one of its inputs.

For every 0.25 degree forecast square and day it looks at:
  1. the average of the 5 models (GFS, ECMWF, ECMWF AI, GEM, ICON),
  2. the wettest of the 5 models (averaging hides a storm that only one model sees, e.g. GFS at Coimbatore on 15 Oct),
  3. the rain measured there and in the squares around it on the latest observed day: TN SMART gauges, or our
     satellite day total (corrected with TN SMART) where there is no gauge or before TN SMART publishes,
  4. how wrong the models' average was there over the past week (observed minus forecast), yesterday counting most
     (each day back counts half as much), also smoothed over the neighbouring squares.
What it learns, every forecast run, from the past 30 days of saved forecasts and what really fell (TN SMART, or the
satellite where there is no gauge), separately for 1, 2 and 3 days ahead:
  (a) WILL IT RAIN (2.5 mm or more)? a chance from 0 to 1, learned from all squares and days;
  (b) HOW MUCH, if it rains? learned only from the squares where it did rain, so the many dry squares do not drag the
      amounts down.
Our amount = (b) where the chance is above the level that gives the right size of rain area on past days, otherwise a
small amount (chance x (b) / 2). Each day's total is our own: it is NOT forced to match the models. Where the chance is
high, the wettest model's amount is also kept as "could reach" (the storm risk).
Confidence per square and day: high / medium / low from (a) model agreement, (b) whether a gauge or the satellite
checks that square, (c) how far ahead the day is.
"""
import datetime as dt, json, math, os, urllib.request
import numpy as np
import verify

MIN_SAMPLES = 150
GAP_DAYS = 7             # past week of model errors; each day back counts half as much
SATGAUGE = 'https://raw.githubusercontent.com/sridhar13294-rgb/tn-rainfall-map/sat-radar/data/satradar/satgauge.json'
OUT = verify.P('data', 'verify', 'ourfc.json')
NAME = 'Our forecast'
MODEL_SKIP = ('Average', 'Weighted average', NAME)


def _sat_weight():
    """How much a satellite-only square counts (0-0.6), from the satellite's own match with the gauges."""
    try:
        with urllib.request.urlopen(urllib.request.Request(SATGAUGE, headers={'User-Agent': 'tn-rainfall-map'}), timeout=30) as r:
            g = json.loads(r.read())
        ets = ((g.get('overall') or {}).get('gauge_fitted') or {}).get('ets') or 0
        return round(max(0.0, min(0.6, (ets - 0.15) * 2.4)), 2), ets
    except Exception:
        return 0.0, None


def neighbours(pts, r=0.3):
    return [[j for j, (lo2, la2) in enumerate(pts) if abs(lo2 - lo) <= r and abs(la2 - la) <= r] for lo, la in pts]


def smooth(vals, nb):
    """Square value blended with the squares around it (itself counts double)."""
    out = {}
    for i, js in enumerate(nb):
        s = w = 0.0
        for j in js:
            if j in vals:
                k = 2.0 if j == i else 1.0; s += vals[j] * k; w += k
        if w:
            out[i] = s / w
    return out


class Obs:
    """What fell on each TN SMART day at each forecast square: gauges first, else the corrected satellite total."""
    def __init__(self, pts, sat_w, allow_partial=False):
        self.pts, self.sat_w, self.cells, self.partial = pts, sat_w, verify.gauge_cells(pts), allow_partial
        self.cache = {}

    def day(self, d, gauges=True):
        key = (d, gauges)
        if key in self.cache:
            return self.cache[key]
        out = {}
        obs = None
        if gauges:
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
            if S and S.get('grid') and (S.get('complete', True) or self.partial):
                for i, (lo, la) in enumerate(self.pts):
                    if i not in out:
                        v = verify.sat_at(S, lo, la)
                        if v is not None:
                            out[i] = (v, self.sat_w, 'satellite')
        self.cache[key] = out if len(out) >= 20 else None
        return self.cache[key]


class Archive:
    """Saved forecasts (data/verify/fc): the models' values for a TN SMART day at a given lead."""
    def __init__(self):
        self.runs = []
        if os.path.isdir(verify.FC_DIR):
            for f in sorted(os.listdir(verify.FC_DIR)):
                try:
                    self.runs.append((verify.utc(f[:10]), os.path.join(verify.FC_DIR, f)))
                except ValueError:
                    pass
        self.cache = {}

    def get(self, D, L, before=None):
        ws = verify.window_start(D)
        cand = [(t, p) for t, p in self.runs if ws - dt.timedelta(hours=24 * L) <= t < ws - dt.timedelta(hours=24 * (L - 1))
                and (before is None or t < before)]
        if not cand:
            return None
        p = cand[-1][1]
        if p not in self.cache:
            self.cache[p] = json.load(open(p))
        fc = self.cache[p]['days'].get(D.isoformat())
        if not fc or 'Average' not in fc:
            return None
        avg = [x / 10 for x in fc['Average']]
        models = [n for n in fc if n not in MODEL_SKIP]
        mx = [max(fc[n][i] for n in models) / 10 if models else avg[i] for i in range(len(avg))]
        return avg, mx


def obs_features(Ob, Ar, O, nb, gap_from=None):
    """Recent rain (smoothed) and the past week's model error (smoothed) at every square, as of observed day O
    (the model error is taken from complete days up to gap_from, default O)."""
    rec = Ob.day(O)
    r = smooth({i: v[0] for i, v in rec.items()}, nb) if rec else {}
    gs, ws = {}, {}
    G0 = gap_from or O
    for b in range(GAP_DAYS):
        X = G0 - dt.timedelta(days=b)
        ob = Ob.day(X); fc = Ar.get(X, 1)
        if not ob or not fc:
            continue
        k = 0.5 ** b
        for i, v in ob.items():
            if i < len(fc[0]):
                gs[i] = gs.get(i, 0.0) + k * (v[0] - fc[0][i]); ws[i] = ws.get(i, 0.0) + k
    g = smooth({i: gs[i] / ws[i] for i in gs}, nb)
    return r, g


def x_row(a, m, r, g):
    return [1.0, math.log1p(max(a, 0)), math.log1p(max(m, 0)), math.log1p(max(r, 0)), math.copysign(math.log1p(abs(g)), g)]


WET = 2.5
LAM = 5.0                # gentle pull of every learned weight towards zero (few days of data)


def _logit(X, y, w):
    X, y, w = np.asarray(X), np.asarray(y, float), np.asarray(w); b = np.zeros(X.shape[1])
    for _ in range(40):
        p = 1 / (1 + np.exp(-X @ b)); W_ = w * p * (1 - p) + 1e-6
        b = b + np.linalg.solve(X.T @ (X * W_[:, None]) + LAM * np.eye(len(b)), X.T @ (w * (y - p)) - LAM * b)
    return b


def fit_lead(S):
    """S: list of (x_row, obs, weight). Returns the rain-chance weights, the amount weights, and the chance level."""
    X = [s[0] for s in S]; y = [s[1] >= WET for s in S]; w = [s[2] for s in S]
    b = _logit(X, y, w)
    WR = [s for s in S if s[1] >= WET]
    Xw = np.asarray([s[0] for s in WR]); lw = np.log([s[1] for s in WR]); ww = np.asarray([s[2] for s in WR])
    c = np.linalg.solve(Xw.T @ (Xw * ww[:, None]) + LAM * np.eye(Xw.shape[1]), Xw.T @ (ww * lw))
    smear = float((ww * np.exp(lw - Xw @ c)).sum() / ww.sum())
    p = 1 / (1 + np.exp(-np.asarray(X) @ b)); frac = sum(wi for yi, wi in zip(y, w) if yi) / sum(w)
    level = float(np.quantile(p, 1 - frac)) if 0 < frac < 1 else 0.5
    return dict(chance=[round(float(x), 4) for x in b], amount=[round(float(x), 4) for x in c], smear=round(smear, 3),
                level=round(level, 3))


def predict_one(model, a, m, r, g, L):
    """(our amount, chance of rain, could-reach amount) for one square."""
    lead = model['leads'].get(str(min(max(L, 1), 3))) or {}
    fade = 1.0 if L <= 3 else max(0.0, 1 - (L - 3) / 4)        # observations matter less far ahead
    x = x_row(a, m, r * fade, g * fade)
    if 'chance' not in lead:                                    # not enough days yet: the models' average
        return round(a, 1), None, None
    p = 1 / (1 + math.exp(-float(np.dot(lead['chance'], x))))
    amt = math.exp(float(np.dot(lead['amount'], x))) * lead['smear']
    v = amt if p >= lead['level'] else amt * p / 2
    reach = round(max(v, m), 1) if p >= max(0.5, lead['level']) and m > v else None
    return round(v, 1), round(p, 2), reach


def build_samples(pts, Ob, Ar, nb, days, before_day=None):
    """Training rows for target days `days` (forecast lead L made when the latest observed day was D-L-1)."""
    samples = {1: [], 2: [], 3: []}
    for D in days:
        tgt = Ob.day(D)
        if not tgt:
            continue
        for L in (1, 2, 3):
            O = D - dt.timedelta(days=L + 1)
            if before_day and O >= before_day:
                continue
            fc = Ar.get(D, L)
            if not fc:
                continue
            r, g = obs_features(Ob, Ar, O, nb)
            for i, (ob, w, src) in tgt.items():
                if i < len(fc[0]):
                    samples[L].append((x_row(fc[0][i], fc[1][i], r.get(i, 0.0), g.get(i, 0.0)), ob, w, i, D))
    return samples


def train(pts, now):
    """Learn from the past 30 days. Returns the model dict (with live inputs for the latest observed day)."""
    sat_w, sat_ets = _sat_weight()
    Ob = Obs(pts, sat_w); Ar = Archive(); nb = neighbours(pts)
    days = [now.date() - dt.timedelta(days=b) for b in range(1, 31)]
    samples = build_samples(pts, Ob, Ar, nb, days)
    model = dict(version=3, updated=now.strftime('%Y-%m-%dT%H:%MZ'), satellite_weight=sat_w, satellite_ets=sat_ets, leads={},
                 inputs=['models average', 'wettest model', 'recent rain (TN SMART / satellite)', 'past-week model error'])
    for L, S in samples.items():
        if len(S) < MIN_SAMPLES or sum(s[1] >= WET for s in S) < 30:
            model['leads'][str(L)] = dict(samples=len(S), note='not enough days yet: models average')
            continue
        f = fit_lead([(s[0], s[1], s[2]) for s in S])
        model['leads'][str(L)] = dict(f, samples=len(S), wet_samples=sum(s[1] >= WET for s in S), days=len({s[4] for s in S}))
    # live inputs: the newest observed day (TN SMART, or the satellite's day so far if TN SMART has not published it)
    ObL = Obs(pts, max(sat_w, 0.3), allow_partial=True)
    latest = None
    for b in range(0, 6):
        d = now.date() + dt.timedelta(days=1) - dt.timedelta(days=b)
        if ObL.day(d):
            latest = d; break
    model['latest_obs_day'] = latest.isoformat() if latest else None
    if latest:
        S_ = verify.sat_day(latest)
        partial = bool(S_ and not S_.get('complete', True)) and not os.path.exists(verify.OBS('data', 'daily', latest.isoformat() + '.json'))
        r, g = obs_features(ObL, Ar, latest, nb, gap_from=latest - dt.timedelta(days=1) if partial else None)
        model['latest_partial'] = partial
        src = ObL.day(latest) or {}
        model['support'] = {i: v[2] for i, v in src.items()}
        model['_recent'], model['_gap'] = r, g
    else:
        model['support'], model['_recent'], model['_gap'] = {}, {}, {}
    model['_latest'] = latest
    return model


def forecast_day(model, avgs, maxs, D):
    """Our rain for every square on TN SMART day D (a date): list of (amount, chance, could_reach)."""
    latest = model.get('_latest')
    L = max(1, (D - latest).days - 1) if latest else 3           # same alignment as training (observed day = D-L-1)
    r, g = model.get('_recent', {}), model.get('_gap', {})
    return [(None, None, None) if a is None else predict_one(model, a, m if m is not None else a, r.get(i, 0.0), g.get(i, 0.0), L)
            for i, (a, m) in enumerate(zip(avgs, maxs))], L


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
