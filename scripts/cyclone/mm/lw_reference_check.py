"""Clear-sky LW check (P1, 800-1000 hPa heat deficit): MEGAM's fitted 17-term scheme vs the 1 cm-1 simple spectral model (SSM)
it was fitted to, with the SSM calibration x1.5 (as used) and x1.0 (uncalibrated), on the AFGL tropical atmosphere at mm2's
32 sigma levels. Writes the column (T, q, p) to lw_column.json so the same sounding can go to an independent reference
(RRTMGP, rrtmgp_reference.py on Kaggle). python lw_reference_check.py"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0], '--noop']
import radcloud as R
from test_radcloud import on_sigma, TROP, col
T, q, p, dp = on_sigma(TROP); ps, Ts = 101300.0, 300.0
z = col(T) * 0; cl = dict(c=z, lwp=z, iwp=z, re_i=z + 30e-6)
def lw():
    o = R.longwave(col(T), col(q), col(p), col(dp), np.full((1, 1), ps), np.full((1, 1), Ts), cl, np)
    return o['heating'][:, 0, 0] * 86400, float(o['olr'][0, 0]), float(o['dn_sfc'][0, 0])
saved = (R.LW_KH2O, R.LW_KCO2, R.LW_KCNT, R.LW_O3, R.LW_PCOEF)
fit, olr_f, dn_f = lw()
nu = R._NU; h, c, kb = 6.62607015e-34, 2.99792458e8, 1.380649e-23; Tg = np.arange(140.0, 361.0, 1.0); nm = nu * 100
piB = 2 * np.pi * h * c ** 2 * nm[None] ** 3 / np.expm1(h * c * nm[None] / (kb * Tg[:, None])) * 100
x = (Tg - 250) / 100; fr = piB / piB.sum(1, keepdims=True)
# per-bin Planck fractions: polynomial fit per bin (as the scheme does per term)
pc = np.polyfit(x, fr, 5).T
out = {}
for fac in (1.5, 1.0):
    R.LW_KH2O, R.LW_KCO2, R.LW_KCNT, R.LW_O3, R.LW_PCOEF = R._KH * fac, R._KC * fac, R._KN * fac, R._O3.astype(float), pc
    out[fac] = lw()
R.LW_KH2O, R.LW_KCO2, R.LW_KCNT, R.LW_O3, R.LW_PCOEF = saved
sig = p / ps; m8 = sig >= 0.79
mm = lambda hr: float((hr * dp * m8).sum() / (dp * m8).sum())
print(f'{"hPa":>6s} {"fitted":>8s} {"SSM x1.5":>9s} {"SSM x1.0":>9s}  (clear-sky LW heating, K/day)')
for k in range(12, 32): print(f'{p[k]/100:6.0f} {fit[k]:+8.2f} {out[1.5][0][k]:+9.2f} {out[1.0][0][k]:+9.2f}')
print(f'OLR      fitted {olr_f:.1f}  SSMx1.5 {out[1.5][1]:.1f}  SSMx1.0 {out[1.0][1]:.1f}')
print(f'sfc down fitted {dn_f:.1f}  SSMx1.5 {out[1.5][2]:.1f}  SSMx1.0 {out[1.0][2]:.1f}')
print(f'800-1000 hPa mass-mean: fitted {mm(fit):+.2f}  SSMx1.5 {mm(out[1.5][0]):+.2f}  SSMx1.0 {mm(out[1.0][0]):+.2f} K/day'
      f'  -> x1.5 contribution {mm(out[1.5][0]) - mm(out[1.0][0]):+.2f} K/day = {(mm(out[1.5][0]) - mm(out[1.0][0])) * 1004.6 * 20000 / 9.806 / 86400:+.1f} W/m2')
json.dump(dict(p=p.tolist(), dp=dp.tolist(), T=T.tolist(), q=q.tolist(), ps=ps, Ts=Ts, fitted=fit.tolist(), ssm15=out[1.5][0].tolist(), ssm10=out[1.0][0].tolist()),
          open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lw_column.json'), 'w'))
