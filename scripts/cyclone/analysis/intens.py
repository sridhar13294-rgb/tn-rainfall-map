"""Intensity model for our ensemble, fitted on the 84 Oct-Dec Bay systems 2000-2025 (IBTrACS winds, ERA5 environment).
Over sea: 12-h change in max wind (kt) from current wind, deep-layer shear (200-850 hPa, storm removed, within 6 deg),
latitude and the mid-level (700 hPa) relative humidity proxy is not available, so shear carries the environment.
Over land: Kaplan-DeMaria inland decay."""
import sys, math, json, datetime as dt, numpy as np
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import ourens as O
from ourens import LIBL, LA, LO
from cyc import on_land
from sklearn.linear_model import Ridge
GLA, GLO = np.meshgrid(LA, LO, indexing='ij')
def shear_at(U, V, la, lo, R=6):
    d = np.hypot(GLA - la, (GLO - lo) * math.cos(math.radians(la))); m = d <= R
    if m.sum() < 5: return None
    return float(math.hypot(U[3][m].mean() - U[0][m].mean(), V[3][m].mean() - V[0][m].mean()))
def feats(v, sh, la, dvp, age):
    return [v, v * v / 100.0, sh, sh * v / 100.0, la - 13, dvp, min(age, 96) / 24]
def wind_at(P, t):
    for a, b in zip(P, P[1:]):
        if a[0] <= t <= b[0] and a[3] is not None and b[3] is not None:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds())
            return a[3] + f * (b[3] - a[3]), a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])
    return None
def samples(RAW, remove_vortex):
    X, Y, S = [], [], []
    for s in LIBL:
        P = O.path_of(s); g = O.gen_time(s)
        for h in range(0, 109, 12):
            t = g + dt.timedelta(hours=h); key = t.strftime('%Y-%m-%dT%H')
            a = wind_at(P, t); b = wind_at(P, t + dt.timedelta(hours=12))
            if key not in RAW or not a or not b: continue
            if on_land(a[2], a[1]) or on_land(b[2], b[1]): continue
            F = remove_vortex(RAW[key].astype(float), a[1], a[2]); sh = shear_at(F[0], F[1], a[1], a[2])
            if sh is None: continue
            p = wind_at(P, t - dt.timedelta(hours=12)); dvp = a[0] - p[0] if p else 0.0
            X.append(feats(a[0], sh, a[1], dvp, h)); Y.append(b[0] - a[0]); S.append(s['season'])
    return np.array(X), np.array(Y), np.array(S)
def fit(X, Y): return Ridge(alpha=1.0).fit(X, Y)
def evaluate(X, Y, S):
    pred = np.zeros_like(Y)
    for y in np.unique(S):
        k = S == y; pred[k] = fit(X[~k], Y[~k]).predict(X[k])
    return float(np.mean(abs(pred - Y))), float(np.mean(abs(Y))), float(np.mean(abs(Y - Y[~np.isnan(Y)].mean())))
def inland(v_landfall, hours):
    """Kaplan-DeMaria decay (kt): V = Vb + (R*V0 - Vb) exp(-a t)"""
    Vb, R, a = 26.7 * math.exp(-0.03 * hours), 0.9, 0.095          # background level itself fades over the Indian landmass
    if v_landfall * R <= Vb: return v_landfall * math.exp(-0.035 * hours)
    return Vb + (R * v_landfall - Vb) * math.exp(-a * hours)
CATS = [(0, 'Low pressure area'), (17, 'Depression'), (28, 'Deep depression'), (34, 'Cyclonic storm'), (48, 'Severe cyclonic storm'),
        (64, 'Very severe cyclonic storm'), (90, 'Extremely severe cyclonic storm'), (120, 'Super cyclonic storm')]
def cat(v):
    c = 0
    for k, (lim, _) in enumerate(CATS):
        if v >= lim: c = k
    return c
if __name__ == '__main__':
    import scen
    RAW = scen.lib_raw(sys.argv[1]); X, Y, S = samples(RAW, scen.remove_vortex)
    print('samples', len(Y), 'mean 12-h change', round(Y.mean(), 1), 'kt')
    e, e0, ec = evaluate(X, Y, S)
    print(f'12-h wind change, leave-one-season-out: model MAE {e:.1f} kt | "no change" {e0:.1f} kt | "average change" {ec:.1f} kt')
    M = fit(X, Y); print('coef [V, V^2/100, shear, shear*V/100, lat-13, dV prev, age d]', np.round(M.coef_, 3), 'intercept', round(M.intercept_, 2))
    import pickle; pickle.dump(M, open(O.REPO + '/data/cyclone/ours/intens_model.pkl', 'wb'))
def iter_test(RAW, remove_vortex, X, Y, S):
    """from genesis: run the model forward 12 h at a time along the real track in the real environment; compare
    with persistence and with the average Oct-Dec intensity curve (by age); leave-one-season-out."""
    res = {24: [], 48: [], 72: [], 96: []}; out = []
    clim = {}
    for s in LIBL:
        P = O.path_of(s); g = O.gen_time(s)
        for h in range(0, 97, 12):
            w = wind_at(P, g + dt.timedelta(hours=h))
            if w: clim.setdefault((s['season'], h), []).append(w[0])
    for s in LIBL:
        k = S != s['season']; M = fit(X[k], Y[k])
        P = O.path_of(s); g = O.gen_time(s); w0 = wind_at(P, g)
        if not w0: continue
        v = w0[0]; dvp = 0.0
        for h in range(0, 96, 12):
            t = g + dt.timedelta(hours=h); key = t.strftime('%Y-%m-%dT%H'); a = wind_at(P, t)
            if not a or key not in RAW: break
            if on_land(a[2], a[1]):
                v = max(10, v * 0.85); dvp = 0
            else:
                F = remove_vortex(RAW[key].astype(float), a[1], a[2]); sh = shear_at(F[0], F[1], a[1], a[2])
                dv = float(M.predict([feats(v, sh, a[1], dvp, h)])[0]); v = max(10, v + dv); dvp = dv
            H = h + 12; b = wind_at(P, g + dt.timedelta(hours=H))
            if H in res and b:
                cm = np.mean([x for (se, hh), xs in clim.items() if hh == H and se != s['season'] for x in xs]) - np.mean([x for (se, hh), xs in clim.items() if hh == 0 and se != s['season'] for x in xs])
                res[H].append((abs(v - b[0]), abs(w0[0] - b[0]), abs(w0[0] + cm - b[0])))
    for H, r in res.items():
        r = np.array(r); print(f'{H} h after genesis: model {r[:,0].mean():.1f} kt | persistence {r[:,1].mean():.1f} | average curve {r[:,2].mean():.1f}  (n={len(r)})')
if __name__ == '__main__':
    iter_test(RAW, scen.remove_vortex, X, Y, S)
