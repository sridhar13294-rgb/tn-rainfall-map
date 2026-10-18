"""Which warning signs really work?  Every Oct-Dec day 2000-2024: ERA5 measures at 00 UTC, L days before the rain day,
against TN SMART (any gauge >= THR mm in the region in the 24 h to 08:30 IST next morning)."""
import json, os, sys, datetime as dt, numpy as np, warnings
warnings.filterwarnings('ignore')
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import indices
HERE = os.path.dirname(os.path.abspath(__file__))
F = json.load(open(os.path.join(HERE, 'days_features.json'))); OC = json.load(open(os.path.join(HERE, 'outcomes.json')))
THR = float(os.environ.get('THR', '150'))
GEN = ['u850_swbay', 'u850_swbay_anom', 'sst_anom_swbay', 'steer_mid', 'u200_south', 'westerly_edge200', 'wd_anom', 'trough_south', 'jet', 'vo_max', 'msl_anom_min']
REGF = ['pw', 'pw_anom', 'onshore925', 'wind850', 'conv850', 'div200', 'rise500', 'rh700', 'cape', 'olr', 'vo_near', 'vo_dist']
NAMES = dict(pw='water vapour offshore', pw_anom='water vapour vs normal offshore', onshore925='onshore wind at ~750 m', wind850='wind speed at 1.5 km offshore',
             conv850='air converging at 1.5 km', div200='air spreading out at 12 km', rise500='air rising at 5.8 km', rh700='humidity at 3 km', cape='storm energy (CAPE)',
             olr='cloud-top heat loss (low = deep cloud)', vo_near='strongest spin within 600 km', vo_dist='distance to the strongest spin in the Bay',
             u850_swbay='NE monsoon wind over SW Bay (u, negative = easterly)', u850_swbay_anom='NE monsoon wind vs normal', sst_anom_swbay='sea temperature vs normal, SW Bay',
             steer_mid='steering wind at 3-6 km over SW Bay', u200_south='12 km wind over the south (negative = easterly)', westerly_edge200='how far south the 12 km westerlies reach',
             wd_anom='western-disturbance trough depth (25-35N)', trough_south='trough reach at 15-25N', jet='jet stream speed', vo_max='strongest spin anywhere in the SW Bay',
             msl_anom_min='lowest surface pressure vs normal in the SW Bay', mjo_fav='MJO strength when in phases 2-4', oni='El Nino index', dmi='IOD index')
def rows(region, L):
    X, y, yrs, days = [], [], [], []
    for T, o in OC.items():
        Td = dt.date.fromisoformat(T); a = Td - dt.timedelta(days=1 + L); k = a.strftime('%Y%m%d') + '00'
        if k not in F or o[region if region != 'tn' else 'tn']['max'] is None: continue
        f = F[k]; rg = region if region != 'tn' else None
        x = [f[g] for g in GEN]
        if rg: x += [f[f'{rg}_{g}'] for g in REGF]
        else: x += [np.nanmax([f[f'{r}_{g}'] for r in ('north', 'delta', 'south')]) if g not in ('vo_dist', 'olr') else np.nanmin([f[f'{r}_{g}'] for r in ('north', 'delta', 'south')]) for g in REGF]
        m = indices.mjo(a); ph, amp = (m['omi_phase'], m['omi_amp']) if m['omi_phase'] else (m['rmm_phase'], m['rmm_amp'])
        x += [amp if ph in (2, 3, 4) else 0.0, indices.enso(a) or 0.0, indices.iod(a) or 0.0]
        X.append([np.nan if v is None else v for v in x]); y.append(o[region]['max'] >= THR); yrs.append(Td.year); days.append(T)
    return np.array(X, float), np.array(y), np.array(yrs), days
FEAT = GEN + REGF + ['mjo_fav', 'oni', 'dmi']
out = {}
for region in ('north', 'delta', 'south', 'tn'):
    out[region] = {}
    for L in (0, 1, 2, 3, 5, 7):
        X, y, yrs, days = rows(region, L)
        X[~np.isfinite(X)] = np.nan; col_med = np.nanmedian(X, 0); col_med = np.where(np.isfinite(col_med), col_med, 0.0); X = np.where(np.isnan(X), col_med, X)
        uni = {}
        for j, f in enumerate(FEAT):
            try: a = roc_auc_score(y, X[:, j])
            except Exception: continue
            uni[f] = dict(auc=round(max(a, 1 - a), 3), sign='+' if a >= .5 else '-', mean_event=round(float(X[y, j].mean()), 2), mean_other=round(float(X[~y, j].mean()), 2))
        # leave-one-year-out logistic regression on all signs
        p = np.zeros(len(y))
        for Y in np.unique(yrs):
            tr, te = yrs != Y, yrs == Y
            sc = StandardScaler().fit(X[tr]); m = LogisticRegression(C=0.3, max_iter=2000, class_weight=None).fit(sc.transform(X[tr]), y[tr])
            p[te] = m.predict_proba(sc.transform(X[te]))[:, 1]
        auc = roc_auc_score(y, p); bs = brier_score_loss(y, p); bs0 = brier_score_loss(y, np.full(len(y), y.mean()))
        thr = np.sort(p[y])[int(len(p[y]) * 0.25)]                     # alert level that catches 75% of events
        alert = p >= thr; hits = int((alert & y).sum()); fa = int((alert & ~y).sum())
        sc = StandardScaler().fit(X); m = LogisticRegression(C=0.3, max_iter=2000).fit(sc.transform(X), y)
        coef = sorted(zip(FEAT, m.coef_[0]), key=lambda t: -abs(t[1]))[:8]
        out[region][L] = dict(n=int(len(y)), events=int(y.sum()), auc=round(auc, 3), bss=round(1 - bs / bs0, 3), catch75_alerts=int(alert.sum()), catch75_hits=hits, catch75_false=fa,
                              top=[(f, round(float(c), 2)) for f, c in coef], uni=dict(sorted(uni.items(), key=lambda t: -t[1]['auc'])))
        print(region, 'lag', L, 'events', int(y.sum()), 'of', len(y), 'AUC', round(auc, 3), 'BSS', round(1 - bs / bs0, 3), 'catch 75%:', int(alert.sum()), 'alerts', hits, 'hits', fa, 'false', flush=True)
        print('   best single signs:', [(f, v['auc'], v['sign']) for f, v in list(out[region][L]['uni'].items())[:6]])
json.dump(dict(thr=THR, names=NAMES, res=out), open(os.path.join(HERE, f'test_signs_{int(THR)}.json'), 'w'), indent=1)
