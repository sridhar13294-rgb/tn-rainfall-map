"""Our moist multi-level global model, version 2.
Dynamics: Dinosaur (Google Research's open-source spectral core): hydrostatic primitive equations on 32 terrain-following
levels over the whole globe, semi-Lagrangian transport (moisture carried on the grid, kept positive), 30-min steps.
Physics (ours, column by column; SI units inside):
  surface layer   - bulk fluxes with sea roughness from the wind (Charnock, high-wind drag cap) and stability (Louis);
                    land: soil temperature and a soil-moisture bucket; ocean: mixed layer that cools under strong wind
  boundary layer  - K-profile mixing up to a diagnosed boundary-layer height (Richardson number), implicit solver
  convection      - Betts-Miller-Janjic type: deep convection relaxes toward a moist-adiabatic reference with cloud-
                    efficiency humidity, energy conserved; shallow convection mixes; convective momentum mixing
  condensation    - saturation adjustment; rain falls and partly re-evaporates in dry air below (dry-air effect)
  radiation       - gray two-stream long-wave with water vapour and cloud; short-wave with the real sun position
                    (day-night cycle), water-vapour absorption and cloud reflection; stratosphere held near its start
  storm start     - optional balanced Holland vortex at the observed position and strength (replaces the coarse analysis vortex)
  model noise     - optional SPPT-like multiplier on the physics tendencies (ensemble members)
No forecast model and no past-storm statistics: the starting analysis, the sea temperature and the equations."""
import math, functools, numpy as np, jax, jax.numpy as jnp
from scipy.interpolate import RegularGridInterpolator as RGI
from scipy import ndimage as ndi
from dinosaur import coordinate_systems, spherical_harmonic, sigma_coordinates, primitive_equations, scales, time_integration, filtering, vertical_interpolation
units = scales.units
G, RD, RV, CP, LV, SB, KARM = 9.80616, 287.04, 461.5, 1004.6, 2.5e6, 5.67e-8, 0.4; KAP = RD / CP
def sigma_bounds(n=32):
    e = np.linspace(0, 1, n + 1); return (0.6 * e + 0.4 * (1 - (1 - e) ** 2)).astype(np.float32)
def qsat(T, p):
    es = 611.2 * jnp.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / jnp.maximum(p - 0.378 * es, 1.0)
def relax(x, ref, tau, dt):                       # stable relaxation over one step, returned as a rate
    return (ref - x) * (1.0 - jnp.exp(-dt / tau)) / dt
def tridiag(a, b, c, d):
    """Thomas algorithm along axis 0 (levels); a: sub, b: main, c: super diagonals."""
    def fwd(carry, x):
        cp_, dp_ = carry; ai, bi, ci, di = x; den = bi - ai * cp_; cn = ci / den; dn = (di - ai * dp_) / den; return (cn, dn), (cn, dn)
    z = jnp.zeros_like(b[0]); _, (C, D) = jax.lax.scan(fwd, (z, z), (a, b, c, d))
    def bwd(xn, x):
        ci, di = x; xi = di - ci * xn; return xi, xi
    _, X = jax.lax.scan(bwd, z, (C[::-1], D[::-1])); return X[::-1]
DEFAULTS = dict(rh_deep=0.8, tau_deep=2400.0, tau_shallow=3600.0, tau_cmt=6 * 3600.0, k_evap=2e-5, ck=1.2e-3, charnock=0.018, cd_cap=2.4e-3,
                z0_land=0.1, cap_land=2e5, bucket=0.15, alb_sea=0.07, alb_land=0.2, k_wv=0.1, k_dry=2.2e-4, k_cld=0.08, k_sw=0.012,
                h_ml=40.0, ent=0.6, tau_strat=15 * 86400.0, sponge=86400.0, sst_off=0.0, sppt=0.0, sppt_seed=0, gust=1.0, sppt_on=None)
# settings an ensemble member may change without recompiling: carried as numbers inside the run (carry['prm'])
DYN = ('rh_deep', 'tau_deep', 'tau_shallow', 'ck', 'k_evap', 'ent', 'sppt')
NWAVE = 8
class Model:
    def __init__(self, grid='T170', layers=32, dt_min=30.0, set_=None):
        self.S = dict(DEFAULTS); self.S.update(set_ or {})
        self.coords = coordinate_systems.CoordinateSystem(getattr(spherical_harmonic.Grid, grid)(), sigma_coordinates.SigmaCoordinates(sigma_bounds(layers)))
        self.ps = primitive_equations.PrimitiveEquationsSpecs.from_si(); nd = self.ps.nondimensionalize
        self.K, self.SEC, self.MPS, self.PA, self.M = [float(nd(1 * u)) for u in (units.degK, units.s, units.m / units.s, units.pascal, units.m)]
        self.dt_s = dt_min * 60.0; self.dt = nd(dt_min * units.minute)
        lon, sinlat = self.coords.horizontal.nodal_axes; self.lon = np.degrees(lon); self.lat = np.degrees(np.arcsin(sinlat))
        self.LO, self.LA = np.meshgrid(self.lon, self.lat, indexing='ij')
        self.sig = self.coords.vertical.centers.astype(np.float32); self.dsig = self.coords.vertical.layer_thickness.astype(np.float32)
        self.sigb = self.coords.vertical.boundaries.astype(np.float32)
        self.ref_t = np.full(len(self.sig), 250.0, np.float32) * self.K
        # SPPT code is compiled in when any member may use it (set sppt_on=True for an ensemble whose control has sppt=0)
        self.sppt_on = bool(self.S['sppt'] > 0) if self.S.get('sppt_on') is None else bool(self.S['sppt_on'])
        self._jit = {}                                                                              # compiled functions, reused across members
    def params(self, set_=None):
        """the member-varying settings as numbers (plus the SPPT wave pattern drawn from sppt_seed)."""
        S = dict(self.S); S.update(set_ or {}); rs = np.random.default_rng(int(S['sppt_seed'])); K = NWAVE
        P = {k: jnp.float32(S[k]) for k in DYN}
        P.update(kx=jnp.asarray(rs.integers(2, 12, K), jnp.float32), ky=jnp.asarray(rs.uniform(-1, 1, K) * 10, jnp.float32),
                 ph=jnp.asarray(rs.uniform(0, 2 * np.pi, K), jnp.float32), om=jnp.asarray(rs.uniform(0.5, 1.5, K) * 2 * np.pi / (2 * 86400.0), jnp.float32))
        return P
    def with_params(self, carry, set_):
        """same start, different member settings: no recompiling."""
        c = dict(carry); c['prm'] = self.params(set_); return c
    # ------------------------------------------------------------------------------------------------ start state
    def to_nodes(self, a, lats, lons):
        la2 = lats[::-1] if lats[0] > lats[-1] else lats; a = a[..., ::-1, :] if lats[0] > lats[-1] else a
        ext = np.concatenate([a, a[..., :1]], -1); lo2 = np.concatenate([lons, [lons[0] + 360]]); pts = np.stack([self.LA.ravel(), self.LO.ravel()], -1)
        f = lambda x: RGI((la2, lo2), x, bounds_error=False, fill_value=None)(pts).reshape(self.LO.shape)
        return np.stack([f(x) for x in ext]) if ext.ndim == 3 else f(ext)
    def init(self, f3, levs, lats, lons, ps_pa, zs_m, sst_k, lsm, storm=None):
        """f3: temperature, specific_humidity, u/v_component_of_wind, geopotential -> [lev, lat, lon]. storm: dict(lat, lon,
        vmax_kt, rmw_km) to replace the analysis vortex with a balanced one."""
        levs = np.asarray(levs, float); N = lambda x: self.to_nodes(x, lats, lons)
        T3, Q3, U3, V3 = [N(f3[k]) for k in ('temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind')]
        ps = N(ps_pa); zs = np.maximum(N(zs_m), 0.0); land = N(lsm) > 0.5
        sst = N(np.where(np.isfinite(sst_k), sst_k, 0.0)); sst = np.where(land | (sst < 260), 0.0, sst)
        if storm and storm.get('vmax_kt', 0) >= 15: T3, Q3, U3, V3, ps = self.bogus(T3, Q3, U3, V3, ps, levs, **storm)
        pc = vertical_interpolation.PressureCoordinates(levs)
        sg = vertical_interpolation.interp_pressure_to_sigma({'t': T3, 'q': np.maximum(Q3, 0), 'u': U3, 'v': V3}, pc, self.coords.vertical, ps[None] / 100.0)
        sg = {k: np.asarray(v, np.float32) for k, v in sg.items()}; hor = self.coords.horizontal
        vor, div = spherical_harmonic.uv_nodal_to_vor_div_modal(hor, sg['u'] * self.MPS, sg['v'] * self.MPS)
        st = primitive_equations.State(vorticity=vor, divergence=div, temperature_variation=hor.to_modal(sg['t'] * self.K - self.ref_t[:, None, None]),
                                       log_surface_pressure=hor.to_modal(np.log(ps[None] * self.PA)), tracers={'specific_humidity': jnp.asarray(sg['q'])})
        self.oro = filtering.exponential_filter(hor, order=2)(hor.to_modal(zs[None] * self.M))
        self.zs = jnp.asarray(zs, jnp.float32); self.land = jnp.asarray(land); self.T0 = jnp.asarray(sg['t'])
        sst = sst + self.S['sst_off'] * (sst > 0); self.sst0 = jnp.asarray(sst, jnp.float32)
        carry = dict(sst=jnp.asarray(sst, jnp.float32), tl=jnp.asarray(sg['t'][-1], jnp.float32), w=jnp.full(zs.shape, 0.6 * self.S['bucket'] * 1000, jnp.float32),
                     rain=jnp.zeros(zs.shape, jnp.float32), t=jnp.float32(0.0), sst0=jnp.asarray(sst, jnp.float32), T0=jnp.asarray(sg['t'], jnp.float32),
                     prm=self.params())
        return st, carry
    def bogus(self, T3, Q3, U3, V3, ps, levs, lat, lon, vmax_kt, rmw_km=None, R_out=600.0, B=1.4, t_hours=None):
        """Replace the analysis vortex by a balanced Holland vortex: lowest-level max wind vmax_kt/0.85 at radius rmw_km,
        decaying upward (weak above 400 hPa), in gradient balance; warm core from hydrostatic balance; moist core."""
        cosl = math.cos(math.radians(lat)); d = np.hypot(self.LA - lat, ((self.LO - lon + 180) % 360 - 180) * cosl) * 111.2      # km
        grid_km = 111.2 * 180.0 / len(self.lat); rm = max(rmw_km or (150.0 if vmax_kt < 34 else 100.0), 1.3 * grid_km)
        def fill(X, R=4.0):
            m = d <= R * 111.2; X = X.copy()
            for k in range(X.shape[0] if X.ndim == 3 else 1):
                f = X[k] if X.ndim == 3 else X; f[m] = np.nanmean(f[(d > R * 111.2) & (d <= (R + 2) * 111.2)])
                for _ in range(80): f[m] = ndi.uniform_filter(f, 5, mode='wrap')[m]
            return X
        U3, V3 = fill(U3), fill(V3)
        f0 = 2 * 7.292e-5 * math.sin(math.radians(lat)); Vm = vmax_kt * 0.5144 / 0.85; rho = 1.15
        # wind profile (modified Rankine, gently tapered beyond R_out), then the balancing geopotential from gradient balance
        rr = np.linspace(0, R_out + 900, 600) * 1e3; rk = rr / 1e3
        Vr = np.where(rk < rm, Vm * rk / rm, Vm * (rm / np.maximum(rk, 1e-3)) ** 0.5) * np.exp(-(np.maximum(rk - R_out, 0) / 400.0) ** 2)
        dph1 = Vr ** 2 / np.maximum(rr, 1.0) + abs(f0) * Vr
        ph1 = -np.cumsum((dph1 * np.gradient(rr))[::-1])[::-1]                                  # phi(r) - phi(far), negative
        r = np.maximum(d, 1.0) * 1e3
        dpth = float(np.clip((vmax_kt - 20.0) / 50.0, 0.0, 1.0)) if self.S.get('bogus_depth', 'auto') == 'auto' else float(self.S['bogus_depth'])
        hi = np.array([0.0, 0.05, 0.25, 0.6, 0.85, 1.0, 1.0]); lo_ = np.array([0.0, 0.0, 0.03, 0.2, 0.6, 1.0, 1.0])   # deep (strong) vs shallow (weak)
        Fp = np.interp(levs, [100, 150, 250, 400, 600, 850, 1100], lo_ + dpth * (hi - lo_))      # vertical structure: depressions are shallow
        dF = np.gradient(Fp) / np.gradient(np.log(levs)); sgn = 1.0 if lat >= 0 else -1.0
        for k, p in enumerate(levs):
            g_ = np.interp(r, rr, dph1) * Fp[k]                                                 # d(phi)/dr at this level
            Vt = -abs(f0) * r / 2 + np.sqrt((f0 * r / 2) ** 2 + np.maximum(r * g_, 0))          # gradient wind
            ang = np.arctan2((self.LA - lat), ((self.LO - lon + 180) % 360 - 180) * cosl)
            U3[k] = U3[k] - sgn * Vt * np.sin(ang); V3[k] = V3[k] + sgn * Vt * np.cos(ang)
            dT = -(np.interp(r, rr, ph1) * dF[k]) / RD                                          # warm core
            T3[k] = T3[k] + np.where(d < R_out + 900, dT, 0.0)
            if p >= 400:
                qs = 0.622 * 611.2 * np.exp(17.67 * (T3[k] - 273.15) / (T3[k] - 29.65)) / (p * 100.0)
                core = np.clip(1 - d / (2.5 * rm), 0, 1); Q3[k] = Q3[k] + core * np.maximum(0.9 * qs - Q3[k], 0)
        ps = ps + rho * np.interp(r, rr, ph1)                                                   # pressure deficit at the surface
        return T3, Q3, U3, V3, ps
    # ------------------------------------------------------------------------------------------------ column physics
    def column(self, T, q, u, v, ps, cr, want_diag=False):
        """All arrays nodal: T, q, u, v [L, X, Y] (SI); ps [X, Y] Pa; cr = surface carry. Returns tendencies (per second)
        and diagnostics (surface rain, surface fluxes)."""
        S = dict(self.S); S.update(cr['prm']); dt = self.dt_s; sig = jnp.asarray(self.sig)[:, None, None]; dsig = jnp.asarray(self.dsig)[:, None, None]
        sb = jnp.asarray(self.sigb)[:, None, None]; p = sig * ps; dp = dsig * ps; mass = dp / G; L = T.shape[0]
        land = self.land; sea = (~land) & (cr['sst'] > 0)
        Ts = jnp.where(sea, cr['sst'], cr['tl'])
        # heights of layer centres and interfaces above the ground
        lnr = jnp.log(jnp.maximum(sb[1:], 1e-6) / jnp.maximum(sb[:-1], 1e-6)); lnr = lnr.at[0].set(jnp.log(sb[1, 0, 0] / jnp.maximum(sig[0, 0, 0], 1e-6)) * 2.0)
        dz = RD * T * lnr / G; zi = jnp.cumsum(dz[::-1], axis=0)[::-1]                               # height of each layer's top interface
        zc = zi - dz / 2
        # ---------------- surface layer
        z1 = zc[-1]; u1, v1, T1, q1, p1 = u[-1], v[-1], T[-1], q[-1], p[-1]
        V1 = jnp.sqrt(u1 ** 2 + v1 ** 2 + S['gust'] ** 2)
        th1 = T1 * (ps / p1) ** KAP; thv1 = th1 * (1 + 0.61 * q1); thvs = Ts * (1 + 0.61 * qsat(Ts, ps))
        z0 = jnp.full_like(V1, S['z0_land'])
        ust = 0.04 * V1
        for _ in range(3):
            z0 = jnp.where(sea, S['charnock'] * ust ** 2 / G + 1.5e-5, S['z0_land'])
            cdn = (KARM / jnp.log(z1 / z0)) ** 2; ust = jnp.sqrt(cdn) * V1
        cdn = jnp.where(sea, jnp.minimum(cdn, S['cd_cap']), cdn)
        rib = G * z1 * (thv1 - thvs) / (thv1 * V1 ** 2)
        fst = jnp.where(rib > 0, 1.0 / (1 + 10 * rib) ** 2, 1 - 10 * rib / (1 + 75 * cdn * jnp.sqrt(z1 / z0 * jnp.abs(rib))))
        cd = cdn * fst; ckn = jnp.where(sea, S['ck'], 0.8 * cdn); ck = ckn * fst
        rho = p1 / (RD * T1 * (1 + 0.61 * q1)); ust = jnp.sqrt(cd) * V1
        beta = jnp.where(sea, 1.0, jnp.clip(cr['w'] / (0.75 * S['bucket'] * 1000), 0, 1))
        E = rho * ck * V1 * beta * jnp.maximum(qsat(Ts, ps) - q1, -1e-3)                           # kg m-2 s-1
        H = rho * CP * ck * V1 * (Ts - th1)                                                         # W m-2 (lowest-level air brought to surface pressure)
        taux = -rho * cd * V1 * u1; tauy = -rho * cd * V1 * v1
        # ---------------- boundary layer: K-profile with implicit diffusion
        th = T * (ps / p) ** KAP; thv = th * (1 + 0.61 * q)
        wstar = jnp.cbrt(jnp.maximum(G / thv1 * (H / (rho * CP) + 0.61 * th1 * E / rho), 0) * 1000.0)
        Vz2 = u ** 2 + v ** 2 + 1e-2; excess = jnp.where(H > 0, 6.5 * H / (rho * CP) / jnp.maximum(ust, 0.1), 0.0)
        rib_z = G * zc * (thv - (thv1 + excess)) / (thv1 * Vz2)
        above = rib_z > 0.25
        hbl = jnp.clip(jnp.min(jnp.where(above, zc, 3000.0), axis=0), 100.0, 3000.0)
        ws = jnp.cbrt(ust ** 3 + 0.6 * KARM * wstar ** 3 * 0.1)
        zh = zi[1:]                                                                                 # interior interfaces (between k and k+1), height above ground
        Kbl = KARM * ws * zh * (1 - jnp.clip(zh / hbl, 0, 1)) ** 2
        dUdz = jnp.sqrt((u[:-1] - u[1:]) ** 2 + (v[:-1] - v[1:]) ** 2) / jnp.maximum(zc[:-1] - zc[1:], 1.0)
        rii = G * (thv[:-1] - thv[1:]) / (thv[1:] * (zc[:-1] - zc[1:])) / jnp.maximum(dUdz ** 2, 1e-6)
        Kfree = 30.0 ** 2 * dUdz * jnp.where(rii > 0, 1.0 / (1 + 10 * rii) ** 2, jnp.sqrt(1 - 18 * jnp.minimum(rii, 0)))
        Kh = jnp.clip(jnp.maximum(Kbl, Kfree), 0.0, 500.0)
        rhoh = 0.5 * (p[:-1] / (RD * T[:-1]) + p[1:] / (RD * T[1:])); coef = rhoh * Kh / jnp.maximum(zc[:-1] - zc[1:], 1.0)   # kg m-2 s-1
        A = jnp.concatenate([jnp.zeros_like(coef[:1]), coef], 0); C_ = jnp.concatenate([coef, jnp.zeros_like(coef[:1])], 0)
        a = -dt * A / mass; c = -dt * C_ / mass; b = 1 - a - c
        def diffuse(X, sfc):
            rhs = X.at[-1].add(dt * sfc / mass[-1]); return (tridiag(a, b, c, rhs) - X) / dt
        du = diffuse(u, taux); dv = diffuse(v, tauy); dq = diffuse(q, E)
        dth = diffuse(th, H / CP * (ps / p1) ** KAP); dT = dth * (p / ps) ** KAP
        dTbl, dqbl = dT, dq                                                                         # boundary-layer part (kept out of SPPT)
        # ---------------- convection (Betts-Miller-Janjic type)
        Tn = T + dt * dT; qn = jnp.maximum(q + dt * dq, 0)
        the_l = Tn * (100000.0 / p) ** KAP * jnp.exp(LV * qn / (CP * Tn))
        low = sig >= 0.87; ksrc = jnp.argmax(jnp.where(low, the_l, -1.0), axis=0)
        take = lambda X: jnp.take_along_axis(X, ksrc[None], axis=0)[0]
        Tsrc, qsrc, psrc = take(Tn), take(qn), take(p * jnp.ones_like(Tn)); the = take(the_l)
        Td = Tsrc * (p / psrc) ** KAP; Tm = Tn
        for _ in range(6):
            qs_ = qsat(Tm, p); ex = (100000.0 / p) ** KAP * jnp.exp(LV * qs_ / (CP * Tm))
            f_ = Tm * ex - the; df = ex * (1 + LV ** 2 * qs_ / (CP * RV * Tm ** 2) - LV * qs_ / (CP * Tm)); Tm = jnp.clip(Tm - f_ / df, 150.0, 350.0)
        Tp = jnp.where(qsrc < qsat(Td, p), Td, Tm)
        abovesrc = sig < jnp.take_along_axis(sig * jnp.ones_like(Tn), ksrc[None], axis=0)[0]
        buoy = (Tp > Tn) & abovesrc & (sig > 0.08)
        cape = (RD * jnp.maximum(Tp - Tn, 0) * dsig / sig * buoy).sum(0)
        sig_top = jnp.min(jnp.where(buoy, sig, 1.0), axis=0)
        sat_base = qsrc >= qsat(Td, p); sig_base = jnp.max(jnp.where(sat_base & (sig <= 1.0), sig, 0.0), axis=0)
        depth = (sig_base - sig_top) * ps
        deep = (cape > 100.0) & (depth > 20000.0)
        shallow = (cape > 0.0) & (~deep) & (sig_base > 0.75)
        reg = (sig >= sig_top) & (cape > 0)
        Tref = Tp - 0.5; qref = S['rh_deep'] * qsat(Tref, p)
        dTc = jnp.where(reg & deep, relax(Tn, Tref, S['tau_deep'], dt), 0.0); dqc = jnp.where(reg & deep, relax(qn, qref, S['tau_deep'], dt), 0.0)
        Pq = -(dqc * mass).sum(0); PT = (CP / LV * dTc * mass).sum(0)
        ok = deep & (Pq > 0) & (PT > 0)
        nmass = jnp.maximum((reg * mass).sum(0), 1.0)
        dTc = jnp.where(reg & ok, dTc - (PT - Pq) * LV / CP / nmass, 0.0); dqc = jnp.where(reg & ok, dqc, 0.0)
        Pc = jnp.where(ok, Pq, 0.0)                                                                  # convective rain, kg m-2 s-1
        # shallow: mix heat and moisture over the shallow cloud layer (no rain)
        sreg = shallow[None] & (sig >= sig_top - 0.05)
        mth = ((th * mass) * sreg).sum(0) / jnp.maximum((mass * sreg).sum(0), 1.0); mq = ((qn * mass) * sreg).sum(0) / jnp.maximum((mass * sreg).sum(0), 1.0)
        dTs = jnp.where(sreg, relax(th, mth, S['tau_shallow'], dt) * (p / ps) ** KAP, 0.0); dqs = jnp.where(sreg, relax(qn, mq, S['tau_shallow'], dt), 0.0)
        # convective momentum mixing
        cm = reg & ok[None]
        mu = ((u * mass) * cm).sum(0) / jnp.maximum((mass * cm).sum(0), 1.0); mv = ((v * mass) * cm).sum(0) / jnp.maximum((mass * cm).sum(0), 1.0)
        dT = dT + dTc + dTs; dq = dq + dqc + dqs
        du = du + jnp.where(cm, relax(u, mu, S['tau_cmt'], dt), 0.0); dv = dv + jnp.where(cm, relax(v, mv, S['tau_cmt'], dt), 0.0)
        # ---------------- large-scale condensation (adjustment) + rain re-evaporation
        Tn = T + dt * dT; qn = jnp.maximum(q + dt * dq, 0)
        qs = qsat(Tn, p); gam = 1 + LV ** 2 * qs / (CP * RV * Tn ** 2); cond = jnp.maximum(qn - qs, 0) / gam / dt
        src = cond * mass + jnp.where(reg & ok, -dqc * mass, 0.0) * 0.0                              # large-scale rain source per layer
        rh = jnp.clip(qn / qs, 0, 1)
        def fall(P, x):
            s_, rh_, m_ = x; P = P + s_; e_ = jnp.minimum(S['k_evap'] * (1 - rh_) * jnp.sqrt(jnp.maximum(P, 0)) * m_, P); return P - e_, e_
        Pconv_src = jnp.where(reg & ok, -dqc * mass, 0.0) / jnp.maximum(Pq, 1e-12) * Pc                # where convective rain forms
        Psurf, ev = jax.lax.scan(fall, jnp.zeros_like(ps), (src + Pconv_src, rh, mass))
        evap = ev / mass
        dq = dq - cond + evap; dT = dT + LV / CP * (cond - evap)
        # ---------------- radiation
        Tn = T + dt * dT; qn = jnp.maximum(q + dt * dq, 0); rhn = jnp.clip(qn / qsat(Tn, p), 0, 1)
        cld = jnp.clip((rhn - 0.85) / 0.15, 0, 1) * (sig > 0.1)
        dtau = (S['k_wv'] * qn + S['k_dry']) * mass + S['k_cld'] * cld * mass / 10.0
        tr = jnp.exp(-1.66 * dtau); Bk = SB * Tn ** 4
        def dn(D, x):
            t_, b_ = x; D = D * t_ + b_ * (1 - t_); return D, D
        _, Dbot = jax.lax.scan(dn, jnp.zeros_like(ps), (tr, Bk))                                      # downward flux at each layer's bottom
        def up(U, x):
            t_, b_ = x; U = U * t_ + b_ * (1 - t_); return U, U
        Usfc = SB * Ts ** 4
        _, Utop_r = jax.lax.scan(up, Usfc, (tr[::-1], Bk[::-1])); Utop = Utop_r[::-1]                # upward flux at each layer's top
        Ubot = jnp.concatenate([Utop[1:], Usfc[None]], 0); Dtop = jnp.concatenate([jnp.zeros_like(ps)[None], Dbot[:-1]], 0)
        lw = ((Ubot - Dbot) - (Utop - Dtop)) * G / (CP * dp)                                          # K/s
        t_h = cr['t'] / 3600.0; doy = self.doy0 + t_h / 24.0; decl = math.radians(23.44) * jnp.sin(2 * jnp.pi * (doy - 81) / 365.0)
        hour = (self.utc0 + t_h) % 24.0; ha = jnp.radians(15.0 * (hour - 12.0) + jnp.asarray(self.LO))
        latr = jnp.radians(jnp.asarray(self.LA)); mu0 = jnp.maximum(jnp.sin(latr) * jnp.sin(decl) + jnp.cos(latr) * jnp.cos(decl) * jnp.cos(ha), 0.0)
        S0 = 1361.0 * mu0; ccol = 1 - jnp.prod(1 - 0.6 * cld, axis=0); alb = 0.45 * ccol
        absw = 1 - jnp.exp(-S['k_sw'] * qn * mass / jnp.maximum(mu0, 0.05))
        def sw(Fd, x):
            a_ = x; ab = Fd * a_; return Fd - ab, ab
        Fsfc, swab = jax.lax.scan(sw, S0 * (1 - alb), absw)
        swh = swab * G / (CP * dp)
        rad = jnp.where(sig > 0.12, lw + swh, -(Tn - cr['T0']) / S['tau_strat'])
        dT = dT + rad
        dq = dq + jnp.maximum(-q, 0) / dt                                                            # keep humidity non-negative
        # ---------------- top sponge
        spg = jnp.where(sig < 0.05, 1.0 / S['sponge'], 0.0); du = du - spg * u; dv = dv - spg * v
        # ---------------- SPPT-like noise on the physics (not radiation)
        if self.sppt_on:
            lonr = jnp.radians(jnp.asarray(self.LO, jnp.float32)); latr2 = jnp.radians(jnp.asarray(self.LA, jnp.float32))
            pat = sum(jnp.sin(S['kx'][i] * lonr + S['ky'][i] * latr2 + S['ph'][i] + S['om'][i] * cr['t']) for i in range(NWAVE)) / math.sqrt(NWAVE / 2)
            fac = 1 + jnp.clip(S['sppt'] * pat, -0.5, 0.5)
            # noise on convection, condensation and rain only: scaling the implicit boundary-layer mixing past 1 overshoots
            # and blows the run up (seen in 1 of 3 test runs)
            dT = dTbl + (dT - rad - dTbl) * fac + rad; dq = dqbl + (dq - dqbl) * fac
        diag = dict(rain=Psurf + Pc * 0.0, H=H, E=E, ust=ust, V1=V1, sw_sfc=Fsfc * (1 - jnp.where(sea, S['alb_sea'], S['alb_land'])), lw_dn=Dbot[-1], Ts=Ts)
        return dict(T=dT, q=dq, u=du, v=dv), diag
    # ------------------------------------------------------------------------------------------------ dynamics + time loop
    def build(self, when_utc, split=False):
        """when_utc: datetime of the start (sun position)."""
        self.doy0 = float(when_utc.timetuple().tm_yday); self.utc0 = float(when_utc.hour); hor = self.coords.horizontal; M = self
        self._jit = {}; self.built_for = when_utc                                                 # new start: compile afresh
        self.eq = primitive_equations.SemiLagrangianPrimitiveEquations(self.ref_t, self.oro, self.coords, self.ps, humidity_key='specific_humidity',
                                                                       monotone_tracers=True, nodal_tracers=('specific_humidity',), departure_iterations=1, monotone_dynamics=True)
        cl = hor.cos_lat
        class Phys(time_integration.ExplicitODE):
            def explicit_terms(self_, state):
                aux = primitive_equations.compute_diagnostic_state_sigma(state.replace(tracers={}), M.coords)
                T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; q = state.tracers['specific_humidity']
                u = aux.cos_lat_u[0] / cl / M.MPS; v = aux.cos_lat_u[1] / cl / M.MPS
                ps = jnp.exp(hor.to_nodal(state.log_surface_pressure))[0] / M.PA
                tend, _ = M.column(T, q, u, v, ps, M._carry)
                vt = hor.to_modal(jax.tree_util.tree_map(lambda x: x * M.MPS / M.SEC / cl, (tend['u'], tend['v'])))
                return primitive_equations.State(vorticity=hor.curl_cos_lat(vt), divergence=hor.div_cos_lat(vt),
                                                 temperature_variation=hor.to_modal(tend['T'] * M.K / M.SEC), log_surface_pressure=jnp.zeros_like(state.log_surface_pressure),
                                                 tracers={'specific_humidity': tend['q'] / M.SEC}, sim_time=None if state.sim_time is None else 0.0)
        self.phys = Phys()
        res = hor.latitude_nodes / 128; tau = self.ps.nondimensionalize(8.6 / (2.4 ** np.log2(res)) * units.hours)
        self.filt = primitive_equations.step_filter_excluding_nodal_tracers(time_integration.horizontal_diffusion_step_filter(hor, dt=self.dt, tau=tau, order=2), nodal_tracers=('specific_humidity',))
        if split:
            # process splitting: dynamics first, then the physics once per step from the new state (half the physics cost;
            # how most operational models couple their physics)
            dyn = time_integration.step_with_filters(time_integration.semi_lagrangian_crank_nicolson_rk2(self.eq, self.dt, off_centering=0.05, warm_start_corrector=True), [self.filt])
            def step(st):
                st = dyn(st); tnd = self.phys.explicit_terms(st)
                return jax.tree_util.tree_map(lambda a, b: a + self.dt * b, st, tnd)
            self.step = step
        else:
            eqs = time_integration.compose_equations([self.eq, self.phys])
            self.step = time_integration.step_with_filters(time_integration.semi_lagrangian_crank_nicolson_rk2(eqs, self.dt, off_centering=0.05, warm_start_corrector=True), [self.filt])
    def dfi(self, state):
        if 'dfi' in self._jit: return self._jit['dfi'](state)
        f = self._jit['dfi'] = jax.jit(time_integration.digital_filter_initialization(equation=self.eq, ode_solver=functools.partial(time_integration.semi_lagrangian_crank_nicolson_rk2, warm_start_corrector=True, off_centering=0.05),
                                                                  filters=[self.filt], time_span=self.ps.nondimensionalize(6 * units.hour), cutoff_period=self.ps.nondimensionalize(6 * units.hour), dt=self.dt))
        return f(state)
    def surface(self, state, cr):
        """after each step: ocean mixed layer, land temperature and soil moisture, rain total."""
        hor = self.coords.horizontal; cl = hor.cos_lat; S = dict(self.S); S.update(cr['prm'])
        aux = primitive_equations.compute_diagnostic_state_sigma(state.replace(tracers={}), self.coords)
        T = (aux.temperature_variation + self.ref_t[:, None, None]) / self.K; q = state.tracers['specific_humidity']
        u = aux.cos_lat_u[0] / cl / self.MPS; v = aux.cos_lat_u[1] / cl / self.MPS; ps = jnp.exp(hor.to_nodal(state.log_surface_pressure))[0] / self.PA
        _, d = self.column(T, q, u, v, ps, cr); dt = self.dt_s; sea = (~self.land) & (cr['sst'] > 0)
        # mixed layer: strong winds stir up cooler water (about ent K/day at 25 m/s), recovering slowly toward the start
        cool = -S['ent'] / 86400.0 * jnp.maximum(d['V1'] - 10.0, 0) ** 2 / 225.0 * (40.0 / S['h_ml'])
        warm = (cr['sst0'] - cr['sst']) / (5 * 86400.0)
        sst = jnp.where(sea, jnp.maximum(cr['sst'] + dt * (cool + warm), cr['sst0'] - 5.0), cr['sst'])
        net = d['sw_sfc'] + d['lw_dn'] - SB * cr['tl'] ** 4 - d['H'] - LV * d['E']
        tl = jnp.where(self.land, jnp.clip(cr['tl'] + dt * net / S['cap_land'], 230.0, 330.0), cr['tl'])
        w = jnp.where(self.land, jnp.clip(cr['w'] + dt * (d['rain'] - d['E']), 0.0, S['bucket'] * 1000), cr['w'])
        return dict(cr, sst=sst, tl=tl, w=w, rain=cr['rain'] + dt * d['rain'], t=cr['t'] + dt)
    def run(self, state, carry, hours, every_h=6, box=(40.0, 120.0, -10.0, 45.0)):
        """returns per-output dict of cropped fields (lon/lat box): mslp, vo850, vo700, z850, z700, u/v lowest level, rain total."""
        hor = self.coords.horizontal; k850 = int(np.argmin(abs(self.sig - 0.85))); k700 = int(np.argmin(abs(self.sig - 0.70)))
        ix = np.where((self.lon >= box[0]) & (self.lon <= box[1]))[0]; iy = np.where((self.lat >= box[2]) & (self.lat <= box[3]))[0]
        self.blon, self.blat = self.lon[ix], self.lat[iy]; crop = lambda a: a[..., ix[0]:ix[-1] + 1, iy[0]:iy[-1] + 1]
        zs_n = jnp.asarray(self.zs)
        def post(state, cr):
            u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, state.vorticity, state.divergence); u, v = u / self.MPS, v / self.MPS
            T = (hor.to_nodal(state.temperature_variation) + self.ref_t[:, None, None]) / self.K
            ps = jnp.exp(hor.to_nodal(state.log_surface_pressure))[0] / self.PA
            phi = primitive_equations.get_geopotential_on_sigma(T * self.K, nodal_orography=zs_n[None] * self.M, sigma=self.coords.vertical,
                                                                gravity_acceleration=self.ps.gravity_acceleration, ideal_gas_constant=self.ps.ideal_gas_constant) / (self.M ** 2 / self.SEC ** 2)
            mslp = ps * jnp.exp(G * zs_n / (RD * (T[-1] + 0.0065 * zs_n / 2)))
            vo = hor.to_nodal(state.vorticity) * self.SEC
            return dict(mslp=crop(mslp), vo850=crop(vo[k850]), vo700=crop(vo[k700]), z850=crop(phi[k850] / G), z700=crop(phi[k700] / G),
                        ul=crop(u[-1]), vl=crop(v[-1]), u850=crop(u[k850]), v850=crop(v[k850]), rain=crop(cr['rain']), sst=crop(cr['sst']))
        inner = int(round(every_h * 3600 / self.dt_s)); outer = int(hours // every_h)
        def one(c, _):
            st, cr = c; self._carry = cr; st2 = self.step(st); cr2 = self.surface(st2, cr); return (st2, cr2), None
        def block(c, _):
            c, _ = jax.lax.scan(one, c, None, length=inner); return c, post(*c)
        key = ('run', hours, every_h, tuple(box))
        if key not in self._jit: self._jit[key] = (jax.jit(lambda s, c: jax.lax.scan(block, (s, c), None, length=outer)), jax.jit(post))
        f, fpost = self._jit[key]
        (sN, cN), traj = f(state, carry); first = fpost(state, carry)
        return {k: np.concatenate([np.asarray(first[k])[None], np.asarray(v)], 0) for k, v in traj.items()}
    # ------------------------------------------------------------------------------------------------ storm tracker (GFDL style)
    def track(self, out, la0, lo0, every_h=6, keep_h=0):
        """centre from up to five fixes near the expected position (last position + 0.75 x last motion): minimum MSLP, maximum
        850 and 700 hPa vorticity, minimum 850 and 700 hPa height; each a weighted centroid within 150 km of its extremum.
        Fixes further than 225 km from their mean are dropped; the rest are averaged. Stops when fewer than 2 fixes agree or
        the vortex is too weak for 12 h. Also: min MSLP (hPa), max lowest-level wind within 300 km (kt, x0.85 for 10 m)."""
        LO, LA = np.meshgrid(self.blon, self.blat, indexing='ij'); sgn = 1 if la0 >= 0 else -1
        dist = lambda a, b: np.hypot(LA - a, ((LO - b + 180) % 360 - 180) * math.cos(math.radians(a))) * 111.2
        res = []; la, lo = la0, lo0; vel = (0.0, 0.0); weak = 0
        for i in range(out['mslp'].shape[0]):
            g = (la + 0.75 * vel[0], lo + 0.75 * vel[1]); d = dist(*g); fixes = []
            for key, s_ in (('mslp', -1), ('vo850', sgn), ('vo700', sgn), ('z850', -1), ('z700', -1)):
                F = ndi.uniform_filter(np.asarray(out[key][i], float), 3) * s_
                m = np.where(d <= (330 if i else 250), F, -np.inf); j = np.unravel_index(np.argmax(m), m.shape)
                dj = dist(LA[j], LO[j]); w = np.clip(F - np.percentile(F[dj <= 400], 75), 0, None) * (dj <= 160) * np.exp(-(dj / 120.0) ** 2)
                if w.sum() > 0: fixes.append(((w * LA).sum() / w.sum(), LO[j] + (w * ((LO - LO[j] + 180) % 360 - 180)).sum() / w.sum()))
                elif np.isfinite(m[j]): fixes.append((float(LA[j]), float(LO[j])))
            if not fixes: break
            fa = np.array(fixes); mla, mlo = np.median(fa, 0)                                    # median first: one stray fix cannot drag the mean
            keep = [f for f in fixes if math.hypot(f[0] - mla, (f[1] - mlo) * math.cos(math.radians(mla))) * 111.2 <= 225]
            if not keep: keep = [min(fixes, key=lambda f: math.hypot(f[0] - g[0], (f[1] - g[1]) * math.cos(math.radians(g[0]))))]
            nl, no = np.array(keep).mean(0)
            if i:
                vel = (nl - la, ((no - lo + 180) % 360) - 180); sp = math.hypot(*vel)
                if sp > 3.0: nl, no = la + vel[0] * 3.0 / sp, lo + vel[1] * 3.0 / sp; vel = (vel[0] * 3.0 / sp, vel[1] * 3.0 / sp)   # no jumps over 3 deg in 6 h
            la, lo = float(nl), float(no % 360); dd = dist(la, lo)
            wmax = float(np.hypot(out['ul'][i], out['vl'][i])[dd <= 300].max()) * 0.85 / 0.5144 if (dd <= 300).any() else 0.0
            pmin = float(np.asarray(out['mslp'][i])[dd <= 200].min()) / 100 if (dd <= 200).any() else None
            vo = float(np.asarray(out['vo850'][i])[dd <= 150].mean()) * sgn * 1e5 if (dd <= 150).any() else 0.0
            weak = weak + 1 if vo < 1.0 else 0
            res.append((i * every_h, round(la, 2), round(lo, 2), round(wmax, 1), None if pmin is None else round(pmin, 1), round(vo, 1), len(keep)))
            if weak >= 4 and i * every_h >= keep_h: break                                         # vortex gone for 24 h (after keep_h: a seedling may be weak at first)
        return res

# ---------------------------------------------------------------------------------------------------- ensemble helpers
def integrate(M, state, carry, hours):
    """run without saving output; returns the final (state, carry)."""
    n = int(round(hours * 3600 / M.dt_s)); key = ('int', n)
    def one(c, _):
        st, cr = c; M._carry = cr; st2 = M.step(st); return (st2, M.surface(st2, cr)), None
    if key not in M._jit: M._jit[key] = jax.jit(lambda s, c: jax.lax.scan(one, (s, c), None, length=n)[0])
    return M._jit[key](state, carry)
def bred_vectors(M, state, carry, n=6, hours=12.0, seed=0, amp=1.0):
    """bred vectors (NCEP-style): small random seeds are grown by the model itself for `hours`; what grows is the part of
    today's uncertainty that matters (troughs, the storm's surroundings). Each is scaled so its 850-hPa-ish wind
    difference is `amp` m/s rms over the tropics and subtropics (40S-40N)."""
    hor = M.coords.horizontal; rs = np.random.default_rng(seed)
    ctl, _ = integrate(M, state, carry, hours); k = int(np.argmin(abs(M.sig - 0.85)))
    band = jnp.asarray(np.abs(M.LA) <= 40)
    def wind_rms(d):
        u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, d.vorticity, d.divergence)
        return jnp.sqrt(((u[k] / M.MPS) ** 2 + (v[k] / M.MPS) ** 2)[band].mean())
    out = []
    for j in range(n):
        noise = rs.standard_normal(np.asarray(state.vorticity).shape).astype(np.float32)
        L = np.arange(noise.shape[-1])[None, None, :]; noise = noise * (L < 40) * (L > 3)
        seedp = state.replace(vorticity=state.vorticity + 0.02 * jnp.std(state.vorticity) * noise)
        pj, _ = integrate(M, seedp, carry, hours)
        d = jax.tree_util.tree_map(lambda a, b: a - b, pj, ctl)
        out.append(jax.tree_util.tree_map(lambda x: x * (amp / jnp.maximum(wind_rms(d), 1e-6)), d))
    return out
def add_perturbation(state, bvs, coefs):
    pert = state
    for c, b in zip(coefs, bvs): pert = jax.tree_util.tree_map(lambda a, x: a + c * x, pert, b)
    q = pert.tracers['specific_humidity']; return pert.replace(tracers={'specific_humidity': jnp.maximum(q, 0.0)})

def track_from_peak(M, out, box=(5.0, 22.0, 78.0, 99.0), every_h=6, t_from=24, t_to=144):
    """The Bay system at its strongest: the highest smoothed 850-hPa vorticity over the Bay sea (box) between t_from and
    t_to h; then followed backward to the start and forward to the end with the same tracker. Useful before a
    depression has formed, when today's seedlings are weak and several compete."""
    from cyc import on_land
    LO, LA = np.meshgrid(M.blon, M.blat, indexing='ij'); inb = (LA >= box[0]) & (LA <= box[1]) & (LO >= box[2]) & (LO <= box[3])
    sea = inb & ~np.vectorize(lambda a, b: on_land(b, a))(LA, LO)
    best = None
    for i in range(int(t_from // every_h), min(out['vo850'].shape[0], int(t_to // every_h) + 1)):
        F = ndi.uniform_filter(np.asarray(out['vo850'][i], float), 3); m = np.where(sea, F, -np.inf); j = np.unravel_index(np.argmax(m), m.shape)
        if best is None or m[j] > best[0]: best = (m[j], i, float(LA[j]), float(LO[j]))
    if best is None: return []
    _, ip, la, lo = best
    fwd = M.track({k: v[ip:] for k, v in out.items()}, la, lo, every_h, keep_h=10 ** 6)
    bwd = M.track({k: v[:ip + 1][::-1] for k, v in out.items()}, la, lo, every_h, keep_h=10 ** 6)
    trk = [((ip - t[0] // every_h) * every_h,) + tuple(t[1:]) for t in bwd[1:]][::-1] + [((ip + t[0] // every_h) * every_h,) + tuple(t[1:]) for t in fwd]
    return trk
