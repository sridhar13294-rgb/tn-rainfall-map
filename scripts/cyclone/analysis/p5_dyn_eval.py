"""Jets / westerlies / Rossby waves / MJO check (10 Nov, Sridhar 18:10), per start, from tn-p5-dyn (bias maps; truth adds back).
python p5_dyn_eval.py P5_DYN_NPZ TRUTH_NPZ. Limits registered in docs/rootcause.md 10 Nov 18:30 (before results)."""
import sys, datetime as dt, numpy as np
Z = np.load(sys.argv[1]); TR = np.load(sys.argv[2]); DI = {str(d): i for i, d in enumerate(TR['days'])}
la, lo = Z['lat'], Z['lon'] % 360; starts = [str(s) for s in Z['starts']]
days = sorted({int(k.split('_d')[1]) for k in Z.files if k.startswith('ps_u200_d')})
def truth(var, s, d):
    t = (dt.datetime.strptime(s, '%Y-%m-%dT%H') + dt.timedelta(days=d)).strftime('%Y-%m-%dT%H'); return np.asarray(TR['o_' + var][DI[t]], float)
def pair(var, i, s, d):
    T = truth(var, s, d); return T + np.asarray(Z[f'ps_{var}_d{d}'][i], float), T
def lonsel(c, d): return ((lo >= c) & (lo <= d)) if c <= d else ((lo >= c) | (lo <= d))
SECT = [('Asia', 70, 150), ('Pacific', 150, 240), ('Atlantic', 280, 350)]
def show(title, rows, unit, lim, signed=True):
    print(f'\n--- {title} ({unit}; failing if beyond {lim}) ---')
    print('day        ' + ' '.join(f'{d:>6d}' for d in days))
    A = np.array(rows)                                  # [start, day]
    print('mean       ' + ' '.join(f'{x:+6.1f}' for x in A.mean(0)))
    print('worst      ' + ' '.join(f'{A[np.argmax(np.abs(A[:, j])), j]:+6.1f}' for j in range(len(days))))
    print('n failing  ' + ' '.join(f'{int((np.abs(A[:, j]) > lim).sum()):>6d}' for j in range(len(days))) + f'   of {len(starts)}' +
          ('   (same-sign >= 7 = systematic: ' + ' '.join(str(int(max((A[:, j] > lim).sum(), (A[:, j] < -lim).sum()) >= 7)) for j in range(len(days))) + ')'))
def jet(U, latlo, lathi, om):
    lm = (la >= latlo) & (la <= lathi); prof = np.nanmean(U[np.ix_(lm, om)], 1); k = int(np.nanargmax(prof)); return la[lm][k], prof[k]
for nm, c, d in SECT:
    om = lonsel(c, d)
    for jn, a, b in (('subtropical jet 20-45N', 20, 45), ('eddy-driven/polar jet 45-70N', 45, 70)):
        lat_rows, spd_rows = [], []
        for i, s in enumerate(starts):
            lr, sr = [], []
            for d_ in days:
                Um, Ut = pair('u200', i, s, d_); (lm_, sm_), (lt_, st_) = jet(Um, a, b, om), jet(Ut, a, b, om); lr.append(lm_ - lt_); sr.append(sm_ - st_)
            lat_rows.append(lr); spd_rows.append(sr)
        show(f'{nm} {jn}: core LATITUDE shift', lat_rows, 'deg, + = model too far north', 2.5)
        show(f'{nm} {jn}: core SPEED bias', spd_rows, 'm/s', 5.0)
    rows = []
    for i, s in enumerate(starts):
        lm = (la >= 40) & (la <= 60); w = np.cos(np.radians(la[lm]))[:, None]
        rows.append([float(np.nanmean(np.asarray(Z[f'ps_u850_d{d_}'][i], float)[np.ix_(lm, om)] * w) / np.mean(w)) for d_ in days])
    show(f'{nm} westerlies u850 40-60N', rows, 'm/s', 2.0)
def eddy_profile(F, a, b, om=None):
    lm = (la >= a) & (la <= b); w = np.cos(np.radians(la[lm]))[:, None]; p = np.nansum(F[lm] * w, 0) / w.sum()
    p = p - p.mean(); return p if om is None else p
def phase_amp(pm, pt, om):
    best, lag = -2, 0
    for L in range(-15, 16):                             # grid lags (1.5 deg each), +-22.5 deg
        r = np.corrcoef(np.roll(pt, L)[om], pm[om])[0, 1]
        if r > best: best, lag = r, L
    return lag * float(abs(lo[1] - lo[0])), float(np.std(pm[om]) / max(np.std(pt[om]), 1e-6)), best
for title, om in (('Rossby waves z500 35-60N, GLOBAL', np.ones_like(lo, bool)), ('Rossby waves z500 35-60N, EAST ASIA 60-160E', lonsel(60, 160))):
    ph, am = [], []
    for i, s in enumerate(starts):
        pr, ar = [], []
        for d_ in days:
            Fm, Ft = pair('z500', i, s, d_); p, a_, _ = phase_amp(eddy_profile(Fm, 35, 60), eddy_profile(Ft, 35, 60), om); pr.append(p); ar.append(a_ - 1.0)
        ph.append(pr); am.append(ar)
    show(title + ': PHASE shift', ph, 'deg lon, + = model too far east', 10.0)
    show(title + ': AMPLITUDE ratio - 1', am, 'fraction', 0.2)
for var, title in (('u200', 'MJO-band u200 15S-15N'), ('u850', 'MJO-band u850 15S-15N'), ('rain24', 'MJO-band rain 15S-15N')):
    cr, lg = [], []
    for i, s in enumerate(starts):
        c_, l_ = [], []
        for d_ in days:
            if var == 'rain24' and d_ == 0: c_.append(np.nan); l_.append(np.nan); continue
            Fm, Ft = pair(var, i, s, d_); p, a_, r = phase_amp(eddy_profile(Fm, -15, 15), eddy_profile(Ft, -15, 15), np.ones_like(lo, bool))
            c_.append(r); l_.append(p)
        cr.append(c_); lg.append(l_)
    C = np.array(cr, float); L_ = np.array(lg, float)
    print(f'\n--- {title}: pattern correlation (failing < 0.6) and eastward lag deg (failing |lag| > 10) ---')
    print('day        ' + ' '.join(f'{d:>6d}' for d in days))
    print('mean corr  ' + ' '.join(f'{x:6.2f}' for x in np.nanmean(C, 0)))
    print('n corr<0.6 ' + ' '.join(f'{int(np.nansum(C[:, j] < 0.6)):>6d}' for j in range(len(days))))
    print('mean lag   ' + ' '.join(f'{x:+6.1f}' for x in np.nanmean(L_, 0)))
