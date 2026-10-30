"""L2 for evapifs.fall_ifs: same columns as evap_derivation.py, convective rain only (src_cv at cloud base 850 hPa),
numpy, compared with the hand formula; then grid-scale stream; water conservation (rain in = rain out + evaporation).
Also runs with jax.numpy when available (GPU-path check). python l2_evap.py"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evap_derivation as D, evapifs
def scan_np(f, c, xs):
    ys = []
    for i in range(xs[0].shape[0]):
        c, y = f(c, tuple(x[i] for x in xs)); ys.append(y)
    return c, tuple(np.stack([y[j] for y in ys]) for j in range(len(ys[0])))
mods = [('numpy', np, scan_np)]
try:
    import jax, jax.numpy as jnp; mods.append(('jax', jnp, jax.lax.scan))
except ImportError: pass
S = lambda a: np.asarray(a, np.float64).reshape(-1, 1, 1)
for lab, rhp, T1, land in (('F2 coastal sea', [0.88, 0.81, 0.73, 0.71], 298.0, False), ('control coastal sea', [0.54, 0.55, 0.80, 0.72], 302.4, False), ('control TN land', [0.55, 0.57, 0.82, 0.55], 299.8, True)):
    T, rh = D.column(rhp, T1); qs = D.qsat(T, D.p); q = rh * qs
    kb = int(np.where(D.p > 85000.0)[0][0])                            # rain enters the first layer below 850 hPa (as the hand calculation)
    for R in (5.0, 20.0):
        hand = D.evap(R, T, rh, 0.70 if land else 0.85).sum() * 86400 / R * 100
        for name, xp, sc in mods:
            src_cv = np.zeros_like(T); src_cv[kb - 1] = R / 86400.0; src_ls = np.zeros_like(T)
            Ps, ev, lim = evapifs.fall_ifs(xp.asarray(S(src_ls)), xp.asarray(S(src_cv)), xp.asarray(S(q)), xp.asarray(S(qs)), xp.asarray(S(D.p)), xp.asarray(np.array([[D.ps]])),
                                           xp.asarray(S(D.m)), xp.asarray(S(D.sig)), xp.asarray(np.array([[land]])), 0.3, 1200.0, sc, xp)
            ev = np.asarray(ev)[:, 0, 0]; code = ev.sum() * 86400 / R * 100; bal = float(np.asarray(Ps)[0, 0] + ev.sum() - R / 86400.0)
            print(f'{lab:20s} {R:4.0f} mm/d [{name}] convective re-evaporated: hand {hand:5.1f}%  code {code:5.1f}%  | water balance {bal:+.1e}  limiter binds {int(np.asarray(lim).sum())}')
        src_ls = np.zeros_like(T); src_ls[kb] = R / 86400.0
        Ps, ev, lim = evapifs.fall_ifs(S(src_ls), S(np.zeros_like(T)), S(q), S(qs), S(D.p), np.array([[D.ps]]), S(D.m), S(D.sig), np.array([[land]]), 0.3, 1200.0, scan_np, np)
        print(f'{"":20s} {R:4.0f} mm/d [numpy] grid-scale re-evaporated: {ev.sum()*86400/R*100:5.1f}%   (old mm2 formula {D.evap(R, T, rh, "mm2").sum()*86400/R*100:5.1f}%)')
