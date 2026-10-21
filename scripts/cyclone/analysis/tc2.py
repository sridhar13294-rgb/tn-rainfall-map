"""Two-layer physics track model (our own; no forecast model, no past-storm winds).
Lower layer = 850/700 hPa, upper layer = 500/200 hPa. Each layer carries potential vorticity
    q1 = zeta1 + f + F (psi2 - psi1)   (upper)        q2 = zeta2 + f + F (psi1 - psi2)   (lower)
stepped forward with dq_i/dt = -J(psi_i, q_i) + heating + diffusion on a Mercator grid (0.5 deg). F = 1/Ld^2 grows with
latitude as f^2 (Ld about 1,200 km at 15N), so the layers are loosely tied near the equator and more tightly further
north. Opposite low- and high-level winds, vertical shear and the storm's tilt are now possible; a weak, shallow storm
feels mostly the lower layer, a deep one both.
'Heating': the storm's vortex is spun up toward the strength model as a cyclone in the lower layer; as it strengthens
the cyclone deepens into the upper layer (weak storms are shallow, strong ones deep) with an outflow anticyclone far out aloft."""
import math, numpy as np
from scipy.fft import dstn, idstn
from scipy import ndimage as nd
import tcmodel as T
class TC2(T.TC):
    def __init__(self, *a, Ld15=1.2e6, **k):
        super().__init__(*a, **k)
        s15 = math.sin(math.radians(15)); self.F0 = (np.sin(np.radians(self.LAT)) / s15) ** 2 / Ld15 ** 2; self.F = self.F0.copy()
        self.cF = 2 * self.F / self.m ** 2; self.cbar = float(self.cF.mean())
        self.eigH = self.eig - self.cbar
    def helm(self, rhs, Pb, iters=4):
        """solve (lap_xy - 2F/m^2) psi = rhs/m^2 with psi = Pb on the edge (variable coefficient by fixed-point iteration)."""
        h2 = self.h ** 2; P = Pb.copy(); R0 = rhs / self.m ** 2
        for _ in range(iters):
            r = (R0 + (self.cF - self.cbar) * P)[1:-1, 1:-1].copy()
            r[0, :] -= Pb[0, 1:-1] / h2; r[-1, :] -= Pb[-1, 1:-1] / h2; r[:, 0] -= Pb[1:-1, 0] / h2; r[:, -1] -= Pb[1:-1, -1] / h2
            P[1:-1, 1:-1] = idstn(dstn(r, type=1) / self.eigH, type=1)
        return P
    def invert(self, q1, q2, Bt, Bc):
        Pt = self.poisson(0.5 * (q1 + q2) - self.f, Bt); Pc = self.helm(0.5 * (q1 - q2), Bc); return Pt + Pc, Pt - Pc
    def run2(self, uL, vL, uU, vU, start, hours, vmax_fn, rmw=120.0, size=700.0, dt=450.0, nu=1.0e4, robert=0.1, tau_h=9.0,
             every=6, land_fn=None, xo=0.5, size_grow=0.0, sppt=None, kmh_track=None, tau_v=1.5):
        """vmax_fn(t_hours, lat, lon, over_land) -> storm max wind in kt. Returns [(hour, lat, lon)]."""
        if sppt:
            rs = np.random.default_rng(sppt['seed']); K = 6; amp = sppt['amp']; Lw = sppt.get('scale_deg', 10.0); Th = sppt.get('hours', 36.0)
            kx = rs.uniform(0.5, 1.5, K) * 2 * np.pi / Lw; ky = rs.uniform(0.5, 1.5, K) * 2 * np.pi / Lw * rs.choice([-1, 1], K)
            ph = rs.uniform(0, 2 * np.pi, (2, K)); om = rs.uniform(0.5, 1.5, K) * 2 * np.pi / (2 * Th)
            pert = lambda th, i: amp * np.sqrt(2.0 / K) * sum(np.sin(kx[k] * self.LON + ky[k] * self.LAT + om[k] * th + ph[i, k]) for k in range(K))
        else: pert = None
        z1 = self.vort(uU, vU); z2 = self.vort(uL, vL); B1 = self.boundary_psi(uU, vU); B2 = self.boundary_psi(uL, vL)
        Bt, Bc = 0.5 * (B1 + B2), 0.5 * (B1 - B2); la, lo = start; edges = np.arange(0, 1801, 50.0); rc = 0.5 * (edges[1:] + edges[:-1])
        def targets(vkt, sz):
            vl = 0.6 * vkt * 0.5144; s = float(np.clip((vkt - 34) / 60, 0, 1))
            tl = T.vortex_zeta(rc, vl, rmw, sz, xo)
            # weak storms are shallow (little upper cyclone); strong ones are deep, with an outflow anticyclone far out aloft
            tu = T.vortex_zeta(rc, (0.2 + 0.55 * s) * vl, rmw, 0.8 * sz, xo) + T.vortex_zeta(rc, -0.15 * vl * s, 500.0, 1400.0, 0.5)
            return tu, tl
        def nudge(z, tgt, la, lo):
            d, idx, prof = self.sym_profile(z, la, lo, edges); ok = (idx >= 0) & (idx < len(tgt)); f = np.zeros_like(z)
            f[ok] = (tgt - prof)[idx[ok]] * np.clip(1 - d[ok] / 1800, 0, 1); return f
        v0 = vmax_fn(0, la, lo, False); tu, tl = targets(v0, size)
        z1 = z1 + nudge(z1, tu, la, lo); z2 = z2 + nudge(z2, tl, la, lo)
        P1 = self.poisson(z1, B1); P2 = self.poisson(z2, B2)                  # starting stream functions from each layer's winds
        q1 = z1 + self.f + self.F * (P2 - P1); q2 = z2 + self.f + self.F * (P1 - P2)
        Bt = 0.5 * (P1 + P2); Bc = 0.5 * (P1 - P2)                             # keep the edges at their starting values
        q1o, q2o = q1.copy(), q2.copy(); q1i, q2i = q1.copy(), q2.copy()
        out = [(0, la, lo)]; nstep = int(round(hours * 3600 / dt)); per = int(round(every * 3600 / dt)); vel = (0.0, 0.0); f1 = f2 = 0
        lap = lambda a: self.m ** 2 * ((np.roll(a, 1, 1) + np.roll(a, -1, 1) + np.roll(a, 1, 0) + np.roll(a, -1, 0) - 4 * a) / self.h ** 2)
        for n in range(1, nstep + 1):
            th = n * dt / 3600; z2now = lap(P2)
            if n % 4 == 0:
                # the storm's centre: lower- and upper-layer vortex centres weighted by how deep the storm is now; heating then
                # rebuilds both layers' vortex at that shared centre (this is what keeps a real storm upright and makes a deep
                # storm feel the upper winds and a shallow one only the lower winds)
                g = (la + vel[0] * 0.5, lo + vel[1] * 0.5); cl = self.center(z2now, g)
                vk = vmax_fn(th, la, lo, land_fn(lo, la) if land_fn else False); s_ = float(np.clip((vk - 34) / 60, 0, 1)); au = 0.2 + 0.55 * s_
                cu = self.center(lap(P1), cl, rad=1.5); wu = au / (1 + au)

                la2, lo2 = (1 - wu) * cl[0] + wu * cu[0], (1 - wu) * cl[1] + wu * cu[1]; vel = (la2 - la, lo2 - lo); la, lo = la2, lo2
                tu, tl = targets(vk, size * (1 + size_grow * vk / 64.0))
                f1 = nudge(lap(P1), tu, la, lo) / (tau_v * 3600); f2 = nudge(z2now, tl, la, lo) / (tau_v * 3600)
            a1 = -self.m ** 2 * self.jac(P1, q1); a2 = -self.m ** 2 * self.jac(P2, q2)
            if pert is not None:
                if n % 2 == 0: self._p1, self._p2 = 1 + pert(th, 0), 1 + pert(th, 1)
                a1 = a1 * self._p1; a2 = a2 * self._p2
            t1 = a1 + f1 - self.sponge * (q1 - q1i)
            t2 = a2 + f2 - self.sponge * (q2 - q2i)
            t1 = t1 + nu * lap(q1 - self.f); t2 = t2 + nu * lap(q2 - self.f)
            for t in (t1, t2): t[0, :] = t[-1, :] = t[:, 0] = t[:, -1] = 0
            if n == 1: n1, n2 = q1 + dt * t1, q2 + dt * t2
            else: n1, n2 = q1o + 2 * dt * t1, q2o + 2 * dt * t2
            if n > 1: q1f = q1 + robert * (n1 - 2 * q1 + q1o); q2f = q2 + robert * (n2 - 2 * q2 + q2o)
            else: q1f, q2f = q1, q2
            q1o, q2o, q1, q2 = q1f, q2f, n1, n2
            P1, P2 = self.invert(q1, q2, Bt, Bc)
            if n % per == 0: out.append((th, la, lo))
            if not (self.lat[3] < la < self.lat[-4] and self.lon[3] < lo < self.lon[-4]): break
        return out
