"""Scenario environment: today's analysis winds, changed through time along one storyline (a chain of things that
happen to the ridge, the westerly trough, the monsoon easterlies, the MJO and the storm itself).
Schedules are piecewise-linear [(day, value), ...]. The storm can push on the ridge: when it is strong, the ridge around
and north of it weakens and south-westerlies appear on its poleward side (erosion)."""
import math, numpy as np
from scipy import ndimage as nd
def sched(s, d, default=0.0):
    if s is None: return default
    if not isinstance(s, (list, tuple)): return float(s)
    if d <= s[0][0]: return s[0][1]
    for a, b in zip(s, s[1:]):
        if a[0] <= d <= b[0]: return a[1] + (d - a[0]) / max(1e-6, b[0] - a[0]) * (b[1] - a[1])
    return s[-1][1]
class EnvS:
    wants_storm = True
    def __init__(self, F, tla, tlo, t0, P):
        self.F = F; self.t0 = t0; self.P = P; self.LA, self.LO = np.meshgrid(tla, tlo, indexing='ij'); self.res = float(tla[1] - tla[0])
        self.wr = np.clip((30 - self.LA) / 6, 0, 1)
    def at(self, t, storm=None):
        P = self.P; d = (t - self.t0).total_seconds() / 86400; LA, LO = self.LA, self.LO; F = self.F
        dl = sched(P.get('ridge_shift'), d)                                   # ridge moves north (+) / south (-), degrees
        if abs(dl) > 0.05:
            Fs = nd.shift(F, (0, 0, dl / self.res, 0), order=1, mode='nearest'); F = self.wr * Fs + (1 - self.wr) * F
        U = [F[0, l].copy() for l in range(4)]; V = [F[1, l].copy() for l in range(4)]
        es = sched(P.get('east_scale'), d, 1.0)                               # strength of the easterlies south of the ridge
        if es != 1.0:                                                         # the whole anticyclonic flow south of the ridge (incl. the coastal north-easterlies)
            wgt = np.clip((24 - LA) / 4, 0, 1)
            for l in (0, 1, 2): U[l] = U[l] * (1 + (es - 1) * wgt); V[l] = V[l] * (1 + (es - 1) * wgt)
        su = sched(P.get('surge'), d)                                         # extra low-level easterlies (negative = stronger)
        if su:
            m = ((LA >= 8) & (LA <= 19)).astype(float); U[0] = U[0] + su * m; U[1] = U[1] + 0.7 * su * m
        rb = sched(P.get('break'), d)                                         # ridge break: south-westerlies over the central Bay
        if rb:
            bl, bo = P.get('break_at', (15.0, 87.0)); m = np.exp(-((LA - bl) / 5) ** 2 - ((LO - bo) / 8) ** 2)
            for l, k in ((1, 0.5), (2, 1.0), (3, 1.0)):
                U[l] = (1 - m * k * min(1, rb / 6)) * U[l] + m * k * 0.75 * rb; V[l] = V[l] + m * k * rb
        A = P.get('wd_amp', 0.0)                                              # westerly trough moving east; southerlies ahead of it
        if A:
            x = 80 + P.get('wd_speed', 8.0) * (d - P.get('wd_day80', 5.0)); w = np.clip((LA - P.get('wd_reach', 18.0)) / 6, 0, 1); dlo = LO - x
            vv = A * min(1.0, max(0.0, d + 1) / 2) * w * np.sin(np.pi * dlo / 12) * (abs(dlo) < 12)
            for l, fac in ((1, 0.3), (2, 0.6), (3, 1.0)): V[l] = V[l] + fac * vv
        mu = sched(P.get('mjo'), d)                                           # MJO low-level westerlies over the south Bay
        if mu:
            m = mu * np.clip((14 - LA) / 6, 0, 1) * (LA > 2); U[0] = U[0] + m; U[1] = U[1] + 0.7 * m
        e = P.get('erosion', 0.0)                                             # the storm pushes the ridge
        if e and storm is not None and storm[2] > 40:
            la, lo, v = storm; amp = e * min(1.0, (v - 40) / 40) * 4.0
            m = np.exp(-((LA - (la + 5)) / 4) ** 2 - ((LO - lo) / 6) ** 2)
            for l, k in ((1, 0.5), (2, 1.0), (3, 1.0)): V[l] = V[l] + m * k * amp; U[l] = np.where(U[l] < 0, U[l] * (1 - 0.5 * m * k * min(1, e)), U[l])
        return U, V
