"""Input-driven environment for our ensemble (no forecast model, no past-storm winds).
Start: today's analysis winds at 850/700/500/200 hPa, with the seedling, the Arabian Sea low and the south-west Bay
circulation taken out (those are put back as moving swirls). Every later time is today's winds changed by the member's
inputs, each evolving in time:
  ridge      - position now (N-S, E-W), drift north/south per day, strengthening/weakening trend of the easterlies
  westerly trough (WD) - when it reaches 80E, how deep, how far south it digs; moves east by itself at that speed
  MJO        - low-level westerly anomaly over the south Bay: fades and moves east / holds / strengthens
  NE-monsoon easterly surge - weaker / as now / stronger from day 1
  upper westerly jet (200 hPa, north of 20N) - weaker / as now / stronger
  Arabian Sea low and south-west Bay circulation - each moves along its chosen path (stall / north / north-west etc.)"""
import math, numpy as np
from scipy import ndimage as nd
LEVS = [850, 700, 500, 200]
def swirl(LA, LO, la0, lo0, vmax, rmw=150.0):
    dy = (LA - la0) * 111.2; dx = (LO - lo0) * 111.2 * math.cos(math.radians(la0)); r = np.hypot(dx, dy) + 1e-6
    V = np.where(r < rmw, vmax * r / rmw, vmax * (rmw / r) ** 0.6) * np.exp(-(r / 1500) ** 2)
    return -V * dy / r, V * dx / r
def path_at(path, d):
    """path: [(day, lat, lon, strength factor)] -> position and strength at day d (None after the end = gone)."""
    if d > path[-1][0]: return None
    for a, b in zip(path, path[1:]):
        if a[0] <= d <= b[0]:
            f = (d - a[0]) / max(1e-6, b[0] - a[0]); return tuple(a[i] + f * (b[i] - a[i]) for i in (1, 2, 3))
    return path[0][1:]
class EnvK:
    def __init__(self, F, tla, tlo, t0, P):
        """F: (2, 4, len(tla), len(tlo)) starting winds on the track grid (already cleaned)."""
        self.F = F; self.t0 = t0; self.P = P; self.LA, self.LO = np.meshgrid(tla, tlo, indexing='ij'); self.res = float(tla[1] - tla[0])
        self.wr = np.clip((30 - self.LA) / 6, 0, 1)                      # ridge changes act south of ~27N, fading out by 30N
        if P.get('ridge_dlon'): self.F = nd.shift(self.F, (0, 0, 0, P['ridge_dlon'] / self.res), order=1, mode='nearest')
    def at(self, t):
        P = self.P; d = (t - self.t0).total_seconds() / 86400; LA, LO = self.LA, self.LO
        dl = float(np.clip(P.get('ridge_dlat', 0) + P.get('ridge_rate', 0) * d, -3, 3))
        F = self.F
        if dl:
            Fs = nd.shift(F, (0, 0, dl / self.res, 0), order=1, mode='nearest'); F = self.wr * Fs + (1 - self.wr) * F
        U = [F[0, l].copy() for l in range(4)]; V = [F[1, l].copy() for l in range(4)]
        s = P.get('ridge_str', 1.0) * (1 + P.get('ridge_trend', 0.0) * min(d / 3, 1.5))
        for l in (0, 1, 2): U[l] = np.where((LA < 20) & (U[l] < 0), U[l] * s, U[l])
        j = P.get('jet', 1.0)
        if j != 1.0: U[3] = np.where((LA > 20) & (U[3] > 0), U[3] * j, U[3])
        A = P.get('wd_amp', 0.0)
        if A:
            x = 80 + P.get('wd_speed', 8.0) * (d - P.get('wd_day80', 5.0)); ramp = min(1.0, max(0.0, d + 1) / 2)
            w = np.clip((LA - P.get('wd_reach', 18.0)) / 6, 0, 1); dlo = LO - x
            vv = A * ramp * w * np.sin(np.pi * dlo / 12) * (abs(dlo) < 12)
            for l, fac in ((1, 0.3), (2, 0.6), (3, 1.0)): V[l] = V[l] + fac * vv
        su = P.get('surge_u', 0.0)
        if su and d >= 1:
            m = ((LA >= 9) & (LA <= 19)) * min(1.0, d - 1 + 0.25); U[0] = U[0] + su * m; U[1] = U[1] + 0.7 * su * m
        a0 = P.get('mjo_u', 0.0); mt = P.get('mjo_trend', 0.0); mc = P.get('mjo_move', 0.0)
        if a0 or mt:
            amp = max(0.0, a0 * (1 + mt * min(d / 3, 1.0))); c = 88 + mc * d
            m = amp * np.clip((14 - LA) / 6, 0, 1) * (LA > 2) * np.exp(-((LO - c) / 18) ** 2); U[0] = U[0] + m; U[1] = U[1] + 0.7 * m
        for path, vmax in ((P.get('as_path'), 10.0), (P.get('sw_path'), 6.0)):
            if not path: continue
            p = path_at(path, d)
            if p is None: continue
            u1, v1 = swirl(LA, LO, p[0], p[1], vmax * p[2])
            for l, fac in ((0, 1.0), (1, 1.0), (2, 0.5)): U[l] = U[l] + fac * u1; V[l] = V[l] + fac * v1
        return U, V
