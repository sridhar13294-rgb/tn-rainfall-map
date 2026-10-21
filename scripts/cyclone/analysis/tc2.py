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
    def __init__(self, *a, Ld15=1.2e6, Ld_min=7.0e5, **k):
        super().__init__(*a, **k)
        # 1/Ld^2 grows as f^2 away from the equator, but the real deformation radius stays ~700+ km in the mid-latitudes
        s15 = math.sin(math.radians(15)); self.F0 = np.minimum((np.sin(np.radians(self.LAT)) / s15) ** 2 / Ld15 ** 2, 1 / Ld_min ** 2); self.F = self.F0.copy()
        self.cF = 2 * self.F / self.m ** 2; self.cbar = float(self.cF.max())      # max (not mean) so the iteration always converges
        self.eigH = self.eig - self.cbar
    def helm(self, rhs, Pb):
        """solve (lap_xy - 2F/m^2) psi = rhs/m^2 with psi = Pb on the edge. F and m vary only with latitude, so: sine
        transform across longitude, then an exact tridiagonal solve along latitude for every wavenumber (Thomas, vectorised)."""
        h2 = self.h ** 2; r = (rhs / self.m ** 2)[1:-1, 1:-1].copy(); c = self.cF[1:-1, 1]                     # c(lat)
        r[0, :] -= Pb[0, 1:-1] / h2; r[-1, :] -= Pb[-1, 1:-1] / h2; r[:, 0] -= Pb[1:-1, 0] / h2; r[:, -1] -= Pb[1:-1, -1] / h2
        nx = r.shape[1]; lx = (2 * np.cos(np.pi * np.arange(1, nx + 1) / (nx + 1)) - 2) / h2
        R = dstn(r, type=1, axes=[1])                                                                          # (ny, nx)
        ny = r.shape[0]; a_ = 1 / h2; bdiag = -2 / h2 + lx[None, :] - c[:, None]                                # (ny, nx)
        cp = np.zeros((ny, nx)); dp = np.zeros((ny, nx))
        cp[0] = a_ / bdiag[0]; dp[0] = R[0] / bdiag[0]
        for j in range(1, ny):
            den = bdiag[j] - a_ * cp[j - 1]; cp[j] = a_ / den; dp[j] = (R[j] - a_ * dp[j - 1]) / den
        X = np.zeros((ny, nx)); X[-1] = dp[-1]
        for j in range(ny - 2, -1, -1): X[j] = dp[j] - cp[j] * X[j + 1]
        P = Pb.copy(); P[1:-1, 1:-1] = idstn(X, type=1, axes=[1]); return P
    def invert(self, q1, q2, Bt, Bc):
        Pt = self.poisson(0.5 * (q1 + q2) - self.f, Bt); Pc = self.helm(0.5 * (q1 - q2), Bc); return Pt + Pc, Pt - Pc
    def run2(self, uL, vL, uU, vU, start, hours, vmax_fn, rmw=120.0, size=700.0, dt=450.0, nu=1.0e4, robert=0.1, tau_h=9.0,
             every=6, land_fn=None, xo=0.5, size_grow=0.0, sppt=None, kmh_track=None, tau_v=1.5, cmul=1.0, tau_env=None, env_r=(600.0, 1200.0), env_fn=None, resid=False, resid_upd=True,
             env_lat=None, heat=0.0, heat_r=300.0, nudge_upper=True, tau_cool=None, steady_ls=None, env_decay=None):
        """vmax_fn(t_hours, lat, lon, over_land) -> storm max wind in kt. Returns [(hour, lat, lon)].
        Hemisphere-wide use: env_lat=(lat_full, lat_free) holds the flow near its analysis only in the tropics (fully south
        of lat_full, free north of lat_free), so mid-latitude troughs and ridges move by the equations alone.
        heat: the storm's heating (m^2/s^3 at full strength) moves mass from the lower to the upper layer inside heat_r km:
        a cyclone below, an outflow anticyclone above that spreads and is carried by the upper winds (this is how a strong
        storm erodes the ridge). With nudge_upper=False the upper layer is shaped by heating alone. tau_cool (h): the upper
        layer relaxes back toward the analysis everywhere (radiative cooling), so heating cannot pile up forever."""
        if sppt:
            rs = np.random.default_rng(sppt['seed']); K = 6; amp = sppt['amp']; Lw = sppt.get('scale_deg', 10.0); Th = sppt.get('hours', 36.0)
            kx = rs.uniform(0.5, 1.5, K) * 2 * np.pi / Lw; ky = rs.uniform(0.5, 1.5, K) * 2 * np.pi / Lw * rs.choice([-1, 1], K)
            ph = rs.uniform(0, 2 * np.pi, (2, K)); om = rs.uniform(0.5, 1.5, K) * 2 * np.pi / (2 * Th)
            pert = lambda th, i: amp * np.sqrt(2.0 / K) * sum(np.sin(kx[k] * self.LON + ky[k] * self.LAT + om[k] * th + ph[i, k]) for k in range(K))
        else: pert = None
        z1 = self.vort(uU, vU); z2 = self.vort(uL, vL); B1 = self.boundary_psi(uU, vU); B2 = self.boundary_psi(uL, vL)
        def resid_of(uL_, vL_, uU_, vU_):
            # the part of the analysed wind a stream function cannot carry (the divergent, in/outflow part and edge effects):
            # u_in - u_rot. It can be several m/s near the storm, so it is kept and carries the PV along with the rest
            R = []
            for (uu, vv) in ((uU_, vU_), (uL_, vL_)):
                Pp = self.poisson(self.vort(uu, vv), self.boundary_psi(uu, vv)); R.append((nd.uniform_filter(uu + self.m * self.dy(Pp), 3), nd.uniform_filter(vv - self.m * self.dx(Pp), 3)))
            return R
        if resid: self.resid_w = resid_of(uL, vL, uU, vU)
        Bt, Bc = 0.5 * (B1 + B2), 0.5 * (B1 - B2); la, lo = start; edges = np.arange(0, 1801, 50.0); rc = 0.5 * (edges[1:] + edges[:-1])
        def targets(vkt, sz):
            vl = 0.6 * vkt * 0.5144; s = float(np.clip((vkt - 34) / 60, 0, 1))
            tl = T.vortex_zeta(rc, vl, rmw, sz, xo)
            # weak storms are shallow (little upper cyclone); strong ones are deep, with an outflow anticyclone far out aloft
            tu = T.vortex_zeta(rc, (0.2 + 0.55 * s) * vl, rmw, 0.8 * sz, xo) + T.vortex_zeta(rc, -0.15 * vl * s, 400.0, 900.0, 0.5)
            return tu, tl
        def psi_r(zt):                     # stream function profile of a symmetric vorticity profile (zero far out)
            r = rc * 1e3; dr = 50e3; V = np.cumsum(zt * r * dr) / r; return -np.cumsum((V * dr)[::-1])[::-1]
        Fc = lambda la: float(np.interp(la, self.lat, self.F0[:, 0]))
        def qtargets(vkt, sz, la):
            # the same storm written as potential vorticity in each layer: vorticity plus the layer-thickness part. Nudging
            # PV (not vorticity) toward this keeps the storm's PV fixed; any PV the shear carries away is not refilled forever
            tu, tl = targets(vkt, sz); pu, pl = psi_r(tu), psi_r(tl); F_ = Fc(la)
            return tu + F_ * (pl - pu), tl + F_ * (pu - pl)
        def nudge(z, tgt, la, lo):
            # only the storm's own part: the symmetric vorticity relative to its surroundings (1,000-1,400 km ring, outside the nudged area so the
            # nudge cannot feed back on its own reference), within 900 km
            d, idx, prof = self.sym_profile(z, la, lo, edges); ring = (rc >= 1000) & (rc <= 1400); base = prof[ring].mean()
            ok = (idx >= 0) & (idx < len(tgt)) & (d <= 900); f = np.zeros_like(z)
            f[ok] = (tgt - (prof - base))[idx[ok]] * np.clip(1 - d[ok] / 900, 0, 1); return f
        # the large-scale flow without the storm, as PV: the target the far-away flow is kept near (tau_env hours). A one- or
        # two-layer model lets the big monsoon/ridge patterns run off as fast Rossby waves that the real (3-D, heated,
        # damped) atmosphere does not do; holding the far field near its analysis (or near a storyline's changed state via
        # env_fn(t_hours, (lat, lon, vmax_kt)) -> (uL, vL, uU, vU) or None) keeps the steering realistic while the storm and its surroundings interact freely.
        def env_q(uL_, vL_, uU_, vU_):
            a1 = self.vort(uU_, vU_); a2 = self.vort(uL_, vL_); b1 = self.poisson(a1, self.boundary_psi(uU_, vU_)); b2 = self.poisson(a2, self.boundary_psi(uL_, vL_))
            return a1 + self.f + self.F * (b2 - b1), a2 + self.f + self.F * (b1 - b2)
        qe1, qe2 = env_q(uL, vL, uU, vU) if (tau_env or tau_cool) else (None, None)
        G1 = G2 = 0.0
        if steady_ls:
            # the planetary-scale pattern (smoothed over steady_ls degrees) is made a steady state by a constant forcing that
            # cancels its own initial tendency (like the forcing that keeps the real monsoon / subtropical highs in place:
            # heating, mountains, friction, none of which a two-layer model has). Troughs and ridges smaller than that
            # still move and grow by the equations. Classic forced-barotropic idea.
            sg = steady_ls / float(self.lon[1] - self.lon[0])
            def ls(uu, vv): return nd.gaussian_filter(uu, sg, mode='nearest'), nd.gaussian_filter(vv, sg, mode='nearest')
            a, b = ls(uU, vU); c_, d_ = ls(uL, vL)
            s1 = self.vort(a, b); s2 = self.vort(c_, d_); p1 = self.poisson(s1, self.boundary_psi(a, b)); p2 = self.poisson(s2, self.boundary_psi(c_, d_))
            qs1 = s1 + self.f + self.F * (p2 - p1); qs2 = s2 + self.f + self.F * (p1 - p2)
            G1 = self.m ** 2 * self.jac(p1, qs1); G2 = self.m ** 2 * self.jac(p2, qs2)
            if resid:                                           # the kept divergent wind's push on that pattern is cancelled too
                (ru1, rv1), (ru2, rv2) = self.resid_w
                G1 = G1 + self.m * (ru1 * self.dx(qs1) + rv1 * self.dy(qs1)); G2 = G2 + self.m * (ru2 * self.dx(qs2) + rv2 * self.dy(qs2))
        latw = np.clip((env_lat[1] - self.LAT) / (env_lat[1] - env_lat[0]), 0, 1) if env_lat else 1.0
        kc = max(1, int(round(1800 / dt))); hf = 0.0
        v0 = vmax_fn(0, la, lo, False); vnow_ = v0; tu, tl = targets(v0, size)
        z1 = z1 + nudge(z1, tu, la, lo); z2 = z2 + nudge(z2, tl, la, lo)
        P1 = self.poisson(z1, B1); P2 = self.poisson(z2, B2)                  # starting stream functions from each layer's winds
        q1 = z1 + self.f + self.F * (P2 - P1); q2 = z2 + self.f + self.F * (P1 - P2)
        Bt = 0.5 * (P1 + P2); Bc = 0.5 * (P1 - P2)                             # keep the edges at their starting values
        q1o, q2o = q1.copy(), q2.copy(); q1i, q2i = q1.copy(), q2.copy()
        out = [(0, la, lo)]; nstep = int(round(hours * 3600 / dt)); per = int(round(every * 3600 / dt)); vel = (0.0, 0.0); f1 = f2 = 0
        lap = lambda a: self.m ** 2 * ((np.roll(a, 1, 1) + np.roll(a, -1, 1) + np.roll(a, 1, 0) + np.roll(a, -1, 0) - 4 * a) / self.h ** 2)
        for n in range(1, nstep + 1):
            th = n * dt / 3600; z2now = lap(P2)
            if n % kc == 0:
                # the storm's centre: lower- and upper-layer vortex centres weighted by how deep the storm is now; heating then
                # rebuilds both layers' vortex at that shared centre (this is what keeps a real storm upright and makes a deep
                # storm feel the upper winds and a shallow one only the lower winds)
                g = (la + vel[0] * 0.5, lo + vel[1] * 0.5); cl = self.center(z2now, g)
                vk = vmax_fn(th, la, lo, land_fn(lo, la) if land_fn else False); vnow_ = vk; s_ = float(np.clip((vk - 34) / 60, 0, 1)); au = 0.2 + 0.55 * s_
                cu = self.center(lap(P1), cl, rad=1.5); wu = cmul * au / (1 + au)

                if math.hypot(cu[0] - cl[0], cu[1] - cl[1]) > 1.0: cu = cl                 # upper centre not found near the storm: ignore it
                la2, lo2 = (1 - wu) * cl[0] + wu * cu[0], (1 - wu) * cl[1] + wu * cu[1]
                st_ = math.hypot(la2 - la, lo2 - lo)
                cap = 0.3 * kc * dt / 1800
                if st_ > cap: la2, lo2 = la + (la2 - la) * cap / st_, lo + (lo2 - lo) * cap / st_   # no jumps: at most 0.3 deg per half hour (~65 km/h)
                vel = (la2 - la, lo2 - lo); la, lo = la2, lo2
                tq1, tq2 = qtargets(vk, size * (1 + size_grow * vk / 64.0), la)
                f1 = nudge(q1 - self.f, tq1, la, lo) / (tau_v * 3600) if nudge_upper else 0.0; f2 = nudge(q2 - self.f, tq2, la, lo) / (tau_v * 3600)
                if heat: hf = heat * float(np.clip((vk - 17) / 60, 0, 1.5)) * np.exp(-(self.dist_km(la, lo) / heat_r) ** 2) * self.F
            a1 = -self.m ** 2 * self.jac(P1, q1); a2 = -self.m ** 2 * self.jac(P2, q2)
            if resid:
                (ru1, rv1), (ru2, rv2) = self.resid_w
                a1 = a1 - self.m * (ru1 * self.dx(q1) + rv1 * self.dy(q1)); a2 = a2 - self.m * (ru2 * self.dx(q2) + rv2 * self.dy(q2))
            if pert is not None:
                if n % 2 == 0: self._p1, self._p2 = 1 + pert(th, 0), 1 + pert(th, 1)
                a1 = a1 * self._p1; a2 = a2 * self._p2
            t1 = a1 + f1 + G1 - self.sponge * (q1 - q1i)
            t2 = a2 + f2 + G2 - self.sponge * (q2 - q2i)
            t1 = t1 + nu * lap(q1 - self.f); t2 = t2 + nu * lap(q2 - self.f)
            if heat: t1 = t1 - hf; t2 = t2 + hf
            if tau_cool: t1 = t1 - (q1 - qe1) / (tau_cool * 3600)
            if tau_env:
                if n % kc == 1 or kc == 1:
                    if env_fn is not None and n % (6 * kc) == 1:
                        ef = env_fn(th, (la, lo, vnow_))
                        if ef is not None:
                            qe1, qe2 = env_q(*ef)
                            if resid and resid_upd: self.resid_w = resid_of(*ef)      # the divergent part changes with the environment too
                    wenv = (math.exp(-th / env_decay) if env_decay else 1.0) * latw * np.clip((self.dist_km(la, lo) - env_r[0]) / (env_r[1] - env_r[0]), 0, 1) / (tau_env * 3600)
                t1 = t1 - wenv * (q1 - qe1); t2 = t2 - wenv * (q2 - qe2)
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
