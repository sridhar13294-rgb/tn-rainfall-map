import json, math, datetime as dt, numpy as np, sys
sys.path.insert(0, '.')
from steer import load, fit, predict, dlm
from sklearn.linear_model import Ridge
X, Y, P, yrs, keys = load()
has = np.array([p is not None for p in P]); PV = np.array([(p[1], p[0]) if p else (0, 0) for p in P])     # previous motion (east, north) km/h
XH = np.hstack([X, PV]); 
def loyo(XX, idx):
    pred = np.full((len(Y), 2), np.nan)
    for y in np.unique(yrs[idx]):
        tr = idx & (yrs != y); te = idx & (yrs == y); M = fit(XX[tr], Y[tr]); pred[te] = predict(M, XX[te])
    return pred
e = lambda p, m: float(np.mean(np.hypot(p[m, 0] - Y[m, 0], p[m, 1] - Y[m, 1])) * 12)
p_w = loyo(X, np.ones(len(Y), bool)); p_h = loyo(XH, has)
print('12 h error on points with a previous fix: winds only', round(e(p_w, has), 1), '| winds + previous motion', round(e(p_h, has), 1), '| persistence', round(e(PV, has), 1), '| deep-layer mean', round(e(dlm(X), has), 1))
# chained multi-step test along the true track (winds taken at the true positions every 12 h)
idx = {(k[0], k[1]): i for i, k in enumerate(keys)}
res = {24: [], 48: [], 72: []}; resp = {24: [], 48: [], 72: []}; resd = {24: [], 48: [], 72: []}
M_all = {}
for y in np.unique(yrs):
    M_all[y] = (fit(X[yrs != y], Y[yrs != y]), fit(XH[has & (yrs != y)], Y[has & (yrs != y)]))
for i, k in enumerate(keys):
    if not has[i]: continue
    sid, t, la, lo = k; Mw, Mh = M_all[yrs[i]]
    pos = [la, lo]; prev = PV[i].copy(); ok = True; tt = dt.datetime.strptime(t, '%Y-%m-%dT%H')
    pp = [la, lo]; pd = [la, lo]
    for step in range(1, 7):
        j = idx.get((sid, (tt + dt.timedelta(hours=12 * (step - 1))).strftime('%Y-%m-%dT%H')))
        if j is None: ok = False; break
        v = predict(Mh, np.hstack([X[j:j + 1], [prev]]))[0]
        prev = v
        pos = [pos[0] + v[1] * 12 / 111.2, pos[1] + v[0] * 12 / (111.2 * math.cos(math.radians(pos[0])))]
        pp = [pp[0] + PV[i][1] * 12 / 111.2, pp[1] + PV[i][0] * 12 / (111.2 * math.cos(math.radians(pp[0])))]
        dv = dlm(X[j:j + 1])[0]; pd = [pd[0] + dv[1] * 12 / 111.2, pd[1] + dv[0] * 12 / (111.2 * math.cos(math.radians(pd[0])))]
        if step * 12 in res:
            jt = idx.get((sid, (tt + dt.timedelta(hours=12 * step)).strftime('%Y-%m-%dT%H')))
            truth = (keys[jt][2], keys[jt][3]) if jt is not None else None
            if truth is None:
                # truth may exist in best track even without a steering sample: skip
                ok = False; break
            for R, q in ((res, pos), (resp, pp), (resd, pd)):
                R[step * 12].append(math.hypot((q[0] - truth[0]) * 111.2, (q[1] - truth[1]) * 111.2 * math.cos(math.radians(truth[0]))))
for h in (24, 48, 72):
    print(h, 'h: ours', round(np.mean(res[h])), 'km | persistence', round(np.mean(resp[h])), '| deep-layer mean wind', round(np.mean(resd[h])), '| cases', len(res[h]))
json.dump({str(h): dict(ours=float(np.mean(res[h])), persistence=float(np.mean(resp[h])), dlm=float(np.mean(resd[h])), n=len(res[h])) for h in (24, 48, 72)}, open('data/steer_multi.json', 'w'))
import pickle; pickle.dump(fit(XH[has], Y[has]), open('data/steer_model_h.pkl', 'wb'))
