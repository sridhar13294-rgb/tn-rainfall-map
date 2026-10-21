"""Our own physics track model with the storm inside it (no forecast model, no past-storm winds).
The deep-layer (850-200 hPa) flow AND the storm's own vortex are stepped forward together with the vorticity equation on
the rotating Earth (Mercator grid, 0.5 deg):  d(zeta + f)/dt = -J(psi, zeta + f) + forcing - diffusion.
Because the storm is part of the flow, it is carried by the steering, drifts north-west under its own beta gyres,
can stall where the steering is weak, loop when the steering changes direction while it is slow, and rotate around a
second circulation (Fujiwhara). A symmetric vorticity source spins the vortex up or down toward the strength given by
the strength model (warm sea, MJO, shear, landfall), since a one-layer model has no heating of its own.
Classic family: VICBAR / BAM-type nested-vortex barotropic models."""
import math, numpy as np
from scipy.fft import dstn, idstn
from scipy.interpolate import RegularGridInterpolator as RGI
from scipy import ndimage as nd
import bve
A = 6.371e6
def vortex_zeta(r_km, vmax, rmw=120.0, size=700.0, xo=0.5):
    """relative vorticity (1/s) of a modified-Rankine vortex V(r) = vmax*(r/rmw) inside, vmax*(rmw/r)^0.5 outside,
    tapered by exp(-(r/size)^2) so it carries no net circulation far out."""
    r = np.maximum(r_km, 1.0) * 1e3; rm = rmw * 1e3; R = size * 1e3
    V = np.where(r < rm, vmax * r / rm, vmax * (rm / r) ** xo) * np.exp(-(r / R) ** 2)
    dr = 1e3; r2 = r + dr
    V2 = np.where(r2 < rm, vmax * r2 / rm, vmax * (rm / r2) ** xo) * np.exp(-(r2 / R) ** 2)
    return (r2 * V2 - r * V) / dr / r                           # (1/r) d(rV)/dr
class TC(bve.BVE):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); n = 2; yy, xx = np.mgrid[-n:n + 1, -n:n + 1]; dk = (yy ** 2 + xx ** 2 <= n * n).astype(float); self.disc = dk / dk.sum()
    def dist_km(self, la, lo):
        return np.hypot((self.LAT - la) * 111.2, (self.LON - lo) * 111.2 * math.cos(math.radians(la)))
    def center(self, z, guess, rad=2.5):
        d = self.dist_km(*guess); k = d <= rad * 111.2
        # the vortex, not a long shear line: vorticity averaged over a 2.5-deg disc (a line scores low, a vortex high)
        zs = nd.convolve(z, self.disc, mode='nearest'); j = np.argmax(np.where(k, zs, -1e9)); jy, jx = np.unravel_index(j, z.shape)
        # sub-grid centre: vorticity-weighted mean around the maximum
        w = np.clip(zs - 0.5 * zs[jy, jx], 0, None) * (self.dist_km(self.LAT[jy, jx], self.LON[jy, jx]) <= 150)
        if w.sum() <= 0: return float(self.LAT[jy, jx]), float(self.LON[jy, jx])
        return float((w * self.LAT).sum() / w.sum()), float((w * self.LON).sum() / w.sum())
    def sym_profile(self, z, la, lo, edges):
        d = self.dist_km(la, lo); idx = np.digitize(d, edges) - 1; prof = np.zeros(len(edges) - 1)
        for i in range(len(prof)):
            m = idx == i; prof[i] = z[m].mean() if m.any() else 0.0
        return d, idx, prof
    def run_storm(self, u0, v0, start, hours, vmax_fn, rmw=120.0, size=700.0, dt=450.0, nu=1.0e4, robert=0.1, tau_h=9.0,
                  every=6, bogus=True, land_fn=None, xo=0.5, size_grow=0.0, sppt=None):
        """start: (lat, lon). vmax_fn(t_hours, lat, lon, over_land) -> deep-layer vortex peak wind (m/s) the vortex is nudged to.
        Model-uncertainty settings (vary inside each member, during the run, like ECMWF's stochastic physics):
          xo        - how slowly the storm's winds fall off outward (sets how hard it drifts north-west under its own spin)
          size_grow - the outer circulation widens as the storm strengthens (fraction per 64 kt)
          sppt      - dict(seed, amp, scale_deg, hours): the flow's own tendencies are multiplied by (1 + r(x, y, t)),
                      r a smooth pattern that drifts and changes through the run (fixed seed, so repeatable)
          nu, tau_h - diffusion and how quickly the vortex follows its target strength
        Returns [(hour, lat, lon)] every `every` hours."""
        if sppt:
            rs = np.random.default_rng(sppt['seed']); K = 6; amp = sppt['amp']; L = sppt.get('scale_deg', 10.0); Th = sppt.get('hours', 36.0)
            kx = rs.uniform(0.5, 1.5, K) * 2 * np.pi / L; ky = rs.uniform(0.5, 1.5, K) * 2 * np.pi / L * rs.choice([-1, 1], K)
            ph = rs.uniform(0, 2 * np.pi, K); om = rs.uniform(0.5, 1.5, K) * 2 * np.pi / (2 * Th); X_, Y_ = self.LON, self.LAT
            pert = lambda th: amp * np.sqrt(2.0 / K) * sum(np.sin(kx[i] * X_ + ky[i] * Y_ + om[i] * th + ph[i]) for i in range(K))
        else: pert = None
        vnow = [0.0]
        z0 = self.vort(u0, v0); Pb = self.boundary_psi(u0, v0)
        la, lo = start; edges = np.arange(0, 901, 50.0)
        if bogus:                                                       # make sure the starting vortex has the measured strength and size
            d, idx, prof = self.sym_profile(z0, la, lo, edges)
            vnow[0] = vmax_fn(0, la, lo, False); tgt = vortex_zeta(0.5 * (edges[1:] + edges[:-1]), vnow[0], rmw, size, xo)
            add = np.zeros_like(z0); ok = (idx >= 0) & (idx < len(tgt)); add[ok] = (tgt - prof)[idx[ok]] * np.clip(1 - d[ok] / 900, 0, 1)
            z0 = z0 + add
        P = self.poisson(z0, Pb); q_old = z0 + self.f; q = q_old.copy(); zinit = z0.copy()
        out = [(0, la, lo)]; nstep = int(round(hours * 3600 / dt)); per = int(round(every * 3600 / dt)); vel = (0.0, 0.0)
        lap = lambda a: self.m ** 2 * ((np.roll(a, 1, 1) + np.roll(a, -1, 1) + np.roll(a, 1, 0) + np.roll(a, -1, 0) - 4 * a) / self.h ** 2)
        for n in range(1, nstep + 1):
            z = q - self.f; th = n * dt / 3600
            if n % 4 == 0:                                              # follow the storm every half hour
                g = (la + vel[0] * 0.5, lo + vel[1] * 0.5); la2, lo2 = self.center(z, g)
                vel = (la2 - la, lo2 - lo); la, lo = la2, lo2
            adv = -self.m ** 2 * self.jac(P, q)
            if pert is not None and n % 2 == 0: self._pp = 1 + pert(th)
            if pert is not None: adv = adv * getattr(self, '_pp', 1.0)
            tend = adv + nu * lap(z) - self.sponge * (z - zinit)
            if n % 4 == 0:                                              # nudge the symmetric vortex toward the strength model
                land = land_fn(lo, la) if land_fn else False
                d, idx, prof = self.sym_profile(z, la, lo, edges)
                vnow[0] = vmax_fn(th, la, lo, land); sz = size * (1 + size_grow * max(0.0, vnow[0]) / 15.0)
                tgt = vortex_zeta(0.5 * (edges[1:] + edges[:-1]), vnow[0], rmw, sz, xo)
                ok = (idx >= 0) & (idx < len(tgt)); f = np.zeros_like(z); f[ok] = (tgt - prof)[idx[ok]] * np.clip(1 - d[ok] / 900, 0, 1)
                self._force = f / (tau_h * 3600)
            tend = tend + getattr(self, '_force', 0)
            tend[0, :] = tend[-1, :] = tend[:, 0] = tend[:, -1] = 0
            q_new = q + dt * tend if n == 1 else q_old + 2 * dt * tend
            q_f = q + robert * (q_new - 2 * q + q_old) if n > 1 else q
            q_old, q = q_f, q_new; P = self.poisson(q - self.f, Pb)
            if n % per == 0: out.append((th, la, lo))
            if not (self.lat[3] < la < self.lat[-4] and self.lon[3] < lo < self.lon[-4]): break
        self._force = 0
        return out
