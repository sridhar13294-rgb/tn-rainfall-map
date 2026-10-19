"""Our track model: the storm's next-12-hour motion from the winds around it (2-6 deg ring) at 850, 700, 500 and 200 hPa,
plus a learned drift (the beta drift that pushes Bay storms north-west), trained on every Bay storm since 1980 with ERA5
winds and IBTrACS positions. Tested leave-one-year-out against persistence and against a plain deep-layer mean wind."""
import json, os, math, datetime as dt, numpy as np
from sklearn.linear_model import Ridge
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.abspath('data')
LEVS = ['850', '700', '500', '200']
def load():
    T = {s['sid']: s for s in json.load(open(os.path.join(D, 'ibtracs_bob.json')))}
    S = json.load(open(os.path.join(D, 'steering_era5.json')))
    pos = {}
    for s in T.values():
        for p in s['pts']: pos[(s['sid'], p[0])] = (p[1], p[2], p[3])
    X, Y, P, yrs, keys = [], [], [], [], []
    for r in S:
        t0 = dt.datetime.strptime(r['t'], '%Y-%m-%dT%H'); t1 = (t0 + dt.timedelta(hours=12)).strftime('%Y-%m-%dT%H'); tm = (t0 - dt.timedelta(hours=12)).strftime('%Y-%m-%dT%H')
        if (r['sid'], t1) not in pos: continue
        la1, lo1, _ = pos[(r['sid'], t1)]
        vy = (la1 - r['lat']) * 111.2 / 12; vx = (lo1 - r['lon']) * 111.2 * math.cos(math.radians((la1 + r['lat']) / 2)) / 12     # km/h
        prev = pos.get((r['sid'], tm))
        pv = ((r['lat'] - prev[0]) * 111.2 / 12, (r['lon'] - prev[1]) * 111.2 * math.cos(math.radians(r['lat'])) / 12) if prev else None
        x = []
        for l in LEVS: x += [r['ann'][l][0] * 3.6, r['ann'][l][1] * 3.6]           # km/h
        x += [r['lat'] - 15, r['lon'] - 88]
        X.append(x); Y.append([vx, vy]); P.append(pv); yrs.append(int(r['t'][:4])); keys.append((r['sid'], r['t'], r['lat'], r['lon']))
    return np.array(X), np.array(Y), P, np.array(yrs), keys
def fit(X, Y, alpha=10.0):
    return [Ridge(alpha=alpha).fit(X, Y[:, k]) for k in range(2)]
def predict(M, X):
    return np.stack([M[0].predict(X), M[1].predict(X)], -1)
def dlm(X):                                                    # plain deep-layer mean wind (850-200, pressure weights)
    w = np.array([0.3, 0.3, 0.25, 0.15]); u = sum(w[i] * X[:, 2 * i] for i in range(4)); v = sum(w[i] * X[:, 2 * i + 1] for i in range(4)); return np.stack([u, v], -1)
if __name__ == '__main__':
    X, Y, P, yrs, keys = load(); print('samples', len(Y), 'years', yrs.min(), yrs.max())
    pred = np.zeros_like(Y)
    for y in np.unique(yrs):
        tr, te = yrs != y, yrs == y; M = fit(X[tr], Y[tr]); pred[te] = predict(M, X[te])
    err = lambda a: float(np.mean(np.hypot(a[:, 0] - Y[:, 0], a[:, 1] - Y[:, 1])) * 12)        # km error after 12 h
    has = np.array([p is not None for p in P]); per = np.array([p if p is not None else (np.nan, np.nan) for p in P])[:, ::-1]
    print('12-h position error (km): our model', round(err(pred), 1), '| deep-layer mean wind', round(err(dlm(X)), 1),
          '| persistence', round(float(np.nanmean(np.hypot(per[has, 0] - Y[has, 0], per[has, 1] - Y[has, 1])) * 12), 1), '(where a previous point exists:', int(has.sum()), ')')
    print('  ours on the same points', round(float(np.mean(np.hypot(pred[has, 0] - Y[has, 0], pred[has, 1] - Y[has, 1])) * 12), 1))
    M = fit(X, Y); names = [f'{c}{l}' for l in LEVS for c in 'uv'] + ['lat', 'lon']
    for k, comp in enumerate(('east', 'north')):
        print(comp, 'drift', round(M[k].intercept_, 2), 'km/h', {n: round(c, 3) for n, c in zip(names, M[k].coef_)})
    import pickle; pickle.dump(M, open(os.path.join(D, 'steer_model.pkl'), 'wb'))
    json.dump(dict(n=len(Y), err_ours=err(pred), err_dlm=err(dlm(X))), open(os.path.join(D, 'steer_eval.json'), 'w'))
