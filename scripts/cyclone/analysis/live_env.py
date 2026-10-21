"""Environment for our ensemble driven only by today's analysis and the inputs: the inputs change the starting winds,
then the barotropic model (bve.py) moves the steering flow forward. Winds at each level = starting winds at that level
+ the change of the deep-layer flow since the start (+ the MJO's low-level westerly anomaly, which is held)."""
import math, numpy as np
from scipy import ndimage as nd
from scipy.interpolate import RegularGridInterpolator as RGI
import bve
LEVS = [850, 700, 500, 200]
def perturb(F, lats, lons, P):
    """F: (2, 4, lat, lon) winds on a regular lat-lon grid. Returns a perturbed copy (the member's starting state)."""
    F = F.copy(); res = float(lats[1] - lats[0]); LA, LO = np.meshgrid(lats, lons, indexing='ij')
    if P.get('ridge_dlat') or P.get('ridge_dlon'):
        F = nd.shift(F, (0, 0, P['ridge_dlat'] / res, P['ridge_dlon'] / res), order=1, mode='nearest')
    s = P.get('ridge_str', 1.0)
    if s != 1.0:
        for li in (0, 1, 2): F[0, li] = np.where((LA < 20) & (F[0, li] < 0), F[0, li] * s, F[0, li])
    a = P.get('wd_amp', 0)
    if a:                                        # a trough (or ridge, if negative) in the westerlies over NW India; it moves by itself
        dl = LO - P.get('wd_lon', 72.0); wl = np.clip((LA - 18) / 8, 0, 1) * (LA < 38); vv = a * wl * np.sin(np.pi * dl / 12) * (abs(dl) < 12)
        for li, fac in ((1, 0.3), (2, 0.6), (3, 1.0)): F[1, li] += fac * vv
    su = P.get('surge_u', 0)
    if su:
        m = ((LA >= 9) & (LA <= 19) & (LO >= 78) & (LO <= 100)).astype(float); m = nd.uniform_filter(m, 5)
        F[0, 0] += su * m; F[0, 1] += 0.7 * su * m
    for (la0, lo0, vmax) in P.get('vortices', []):   # extra swirl added to an observed circulation (stronger/weaker settings)
        dy = (LA - la0) * 111.2; dx = (LO - lo0) * 111.2 * math.cos(math.radians(la0)); r = np.hypot(dx, dy) + 1e-6
        V = np.where(r < 150, vmax * r / 150, vmax * (150 / r) ** 0.6) * np.exp(-(r / 1500) ** 2)
        for li, fac in ((0, 1.0), (1, 1.0), (2, 0.5)): F[0, li] += -fac * V * dy / r; F[1, li] += fac * V * dx / r
    return F
class EnvB:
    """at(t) -> (U, V): lists of 4 arrays on the target grid (tla x tlo)."""
    def __init__(self, F, lats, lons, tla, tlo, t0, P, hours=264, box=None):
        self.t0 = t0; self.P = P; TLA, TLO = np.meshgrid(tla, tlo, indexing='ij'); pts = np.stack([TLA.ravel(), TLO.ravel()], -1); sh = TLA.shape
        to_t = lambda a, la, lo: RGI((la, lo), a, bounds_error=False, fill_value=None)(pts).reshape(sh)
        self.F0 = np.stack([np.stack([to_t(F[c, l], lats, lons) for l in range(4)]) for c in range(2)])
        box = box or (lats[0] + 1, lats[-1] - 1, lons[0] + 1, lons[-1] - 1)
        B = bve.BVE(*box); w = [bve.WTS[l] for l in LEVS]
        ud = sum(w[l] * F[0, l] for l in range(4)); vd = sum(w[l] * F[1, l] for l in range(4))
        out = B.run(B.regrid(ud, lats, lons), B.regrid(vd, lats, lons), hours, every=6)
        u0, v0 = out[0][1], out[0][2]
        self.D = [(h, to_t(u - u0, B.lat, B.lon), to_t(v - v0, B.lat, B.lon)) for h, u, v in out]
        self.mjo = P.get('mjo_u', 0.0) * np.clip((14 - TLA) / 6, 0, 1) * (TLA > 2)
    def at(self, t):
        h = (t - self.t0).total_seconds() / 3600; k = min(max(h, 0), self.D[-1][0]) / 6; k0 = int(k); k1 = min(k0 + 1, len(self.D) - 1); f = k - k0
        du = (1 - f) * self.D[k0][1] + f * self.D[k1][1]; dv = (1 - f) * self.D[k0][2] + f * self.D[k1][2]
        U = [self.F0[0, l] + du for l in range(4)]; V = [self.F0[1, l] + dv for l in range(4)]
        U[0] = U[0] + self.mjo; U[1] = U[1] + 0.7 * self.mjo
        return U, V
