"""Our moist multi-level global model.
Dynamics: Dinosaur (open-source spectral primitive-equation core, Google Research): hydrostatic primitive equations on
terrain-following sigma levels over the whole globe, with water vapour carried as a tracer and its effect on density
(virtual temperature) included.
Physics (ours, column by column, the 'simple-physics' family used for tropical-cyclone studies; Reed & Jablonowski 2012,
Frierson 2007):
  1. sea surface: evaporation, heat and friction from bulk formulas using the real sea temperature (land: friction only)
  2. boundary layer: the lowest ~20% of the atmosphere is mixed (wind, potential temperature, moisture)
  3. deep convection: simplified Betts-Miller - where a surface parcel is buoyant, the column relaxes toward the moist
     adiabat and 80% humidity over ~2 h, with the heating balanced by the rain that falls out (energy conserved)
  4. large-scale condensation: any supersaturation condenses, releases latent heat and rains out
  5. radiation: steady tropospheric cooling of 1.5 K/day; stratosphere relaxed to its starting temperature
  6. a sponge on the top layers' winds.
No forecast model, no past-storm statistics: only the starting analysis, the sea temperature and the equations."""
import math, numpy as np, jax, jax.numpy as jnp
from scipy.interpolate import RegularGridInterpolator as RGI
from dinosaur import coordinate_systems, spherical_harmonic, sigma_coordinates, primitive_equations, scales, time_integration, filtering, vertical_interpolation
units = scales.units
G, RD, RV, CP, LV = 9.80616, 287.0, 461.5, 1004.0, 2.5e6; KAP = RD / CP
BOUNDS = np.array([0, .03, .07, .11, .16, .21, .27, .33, .39, .45, .51, .57, .63, .69, .75, .80, .85, .89, .93, .965, 1.0], np.float32)
def qsat(T, p):
    es = 611.2 * jnp.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / jnp.maximum(p - 0.378 * es, 1.0)
class Model:
    def __init__(self, grid='T85', dt_min=6.0, set_=None):
        self.S = dict(tau_bm=2 * 3600.0, rh_bm=0.8, tau_c=1800.0, tau_pbl=3 * 3600.0, sig_pbl=0.8, cool=1.5, tau_strat=15 * 86400.0,
                      ce=1.1e-3, ch=1.1e-3, cd_land=4e-3, sponge=86400.0, gust=1.0, sst_off=0.0)
        if set_: self.S.update(set_)
        self.coords = coordinate_systems.CoordinateSystem(getattr(spherical_harmonic.Grid, grid)(), sigma_coordinates.SigmaCoordinates(BOUNDS))
        self.ps = primitive_equations.PrimitiveEquationsSpecs.from_si()
        nd = self.ps.nondimensionalize
        self.K, self.SEC, self.MPS, self.PA = float(nd(1 * units.degK)), float(nd(1 * units.s)), float(nd(1 * units.m / units.s)), float(nd(1 * units.pascal))
        self.dt = nd(dt_min * units.minute); self.dt_min = dt_min
        lon, sinlat = self.coords.horizontal.nodal_axes; self.lon = np.degrees(lon); self.lat = np.degrees(np.arcsin(sinlat))
        self.sig = self.coords.vertical.centers.astype(np.float32); self.dsig = self.coords.vertical.layer_thickness.astype(np.float32)
        self.ref_t = np.full(len(self.sig), 250.0, np.float32) * self.K
    # ---------------------------------------------------------------- start state from pressure-level analysis
    def init(self, f3, levs, lats, lons, ps_pa, zs_m, sst_k, lsm):
        """f3: dict temperature, specific_humidity, u, v, geopotential -> [lev, lat, lon] on a regular lat-lon grid."""
        LO, LA = np.meshgrid(self.lon, self.lat, indexing='ij')                               # Dinosaur nodal order: [lon, lat]
        pts = np.stack([LA.ravel(), LO.ravel()], -1); la2 = lats[::-1] if lats[0] > lats[-1] else lats
        def hz(a):
            a = a[::-1] if lats[0] > lats[-1] else a
            ext = np.concatenate([a, a[..., :1]], -1); lo2 = np.concatenate([lons, [lons[0] + 360]])
            return RGI((la2, lo2), ext, bounds_error=False, fill_value=None)(pts).reshape(LO.shape)
        H = lambda X: np.stack([hz(x) for x in X]) if X.ndim == 3 else hz(X)
        T3, Q3, U3, V3 = [H(f3[k]) for k in ('temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind')]
        ps = H(ps_pa); zs = np.maximum(H(zs_m), 0.0); sst = H(np.where(np.isfinite(sst_k), sst_k, np.nan)); land = H(lsm) > 0.5
        sst = np.where(np.isfinite(sst), sst, 0.0); sst = np.where(land | (sst < 260), 0.0, sst)
        pc = vertical_interpolation.PressureCoordinates(np.asarray(levs, float))
        fields = {'t': T3, 'q': np.maximum(Q3, 0.0), 'u': U3, 'v': V3}
        sg = vertical_interpolation.interp_pressure_to_sigma(fields, pc, self.coords.vertical, ps[None] / 100.0)
        sg = {k: np.asarray(v) for k, v in sg.items()}
        hor = self.coords.horizontal
        vor, div = spherical_harmonic.uv_nodal_to_vor_div_modal(hor, sg['u'] * self.MPS, sg['v'] * self.MPS)
        tv = hor.to_modal(sg['t'] * self.K - self.ref_t[:, None, None])
        lsp = hor.to_modal(np.log(ps[None] * self.PA))
        q = hor.to_modal(sg['q'])
        st = primitive_equations.State(vorticity=vor, divergence=div, temperature_variation=tv, log_surface_pressure=lsp, tracers={'specific_humidity': q})
        oro = filtering.exponential_filter(hor, order=2)(hor.to_modal(zs[None] * float(self.ps.nondimensionalize(1 * units.m))))
        self.sst = jnp.asarray(sst + self.S['sst_off'] * (sst > 0)); self.land = jnp.asarray(land); self.T0 = jnp.asarray(sg['t'])
        self.oro = oro; return st
    # ---------------------------------------------------------------- our physics as an explicit forcing
    def physics(self):
        M = self; S = M.S; hor = M.coords.horizontal; sig = jnp.asarray(M.sig)[:, None, None]; dsig = jnp.asarray(M.dsig)[:, None, None]
        cl = hor.cos_lat
        class Phys(time_integration.ExplicitODE):
            def explicit_terms(self_, state):
                aux = primitive_equations.compute_diagnostic_state_sigma(state, M.coords)
                T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; qr = aux.tracers['specific_humidity']; q = jnp.maximum(qr, 0.0)
                u = aux.cos_lat_u[0] / cl / M.MPS; v = aux.cos_lat_u[1] / cl / M.MPS
                ps = jnp.exp(hor.to_nodal(state.log_surface_pressure)) / M.PA; p = sig * ps
                dT = jnp.zeros_like(T); dq = jnp.zeros_like(q); du = jnp.zeros_like(u); dv = jnp.zeros_like(v)
                # 1. sea surface fluxes into the lowest layer
                ul, vl, Tl, ql, pl = u[-1], v[-1], T[-1], q[-1], p[-1]
                V = jnp.sqrt(ul ** 2 + vl ** 2 + S['gust'] ** 2); rho = pl / (RD * Tl); mass = ps[0] * dsig[-1, 0] / G
                sea = (~M.land) & (M.sst > 0)
                cd = jnp.where(sea, jnp.minimum(7e-4 + 6.5e-5 * V, 2.5e-3), S['cd_land'])
                E = jnp.where(sea, S['ce'] * V * rho * jnp.maximum(qsat(M.sst, ps[0]) - ql, 0.0), 0.0)
                Hs = jnp.where(sea, S['ch'] * V * rho * CP * (M.sst - Tl), 0.0)
                dq = dq.at[-1].add(E / mass); dT = dT.at[-1].add(Hs / (CP * mass))
                du = du.at[-1].add(-cd * V * rho * ul / mass); dv = dv.at[-1].add(-cd * V * rho * vl / mass)
                # 2. boundary layer mixing (toward the mass-weighted mean below sig_pbl)
                pb = (sig >= S['sig_pbl']).astype(T.dtype); w = pb * dsig; ws = w.sum(0)
                th = T * sig ** (-KAP)
                for X, dX in ((u, 'u'), (v, 'v'), (q, 'q'), (th, 't')):
                    m = (X * w).sum(0) / ws; tend = -pb * (X - m) / S['tau_pbl']
                    if dX == 'u': du = du + tend
                    elif dX == 'v': dv = dv + tend
                    elif dX == 'q': dq = dq + tend
                    else: dT = dT + tend * sig ** KAP
                # 3. simplified Betts-Miller deep convection
                T0, q0, p0 = T[-1], q[-1], p[-1]
                the = T0 * (100000.0 / p0) ** KAP * jnp.exp(LV * q0 / (CP * T0))                 # parcel equivalent potential temperature
                Td = T0 * (p / p0) ** KAP                                                         # dry ascent
                Tm = T                                                                            # moist adiabat: solve theta_e(Tm, qsat) = the
                for _ in range(6):
                    qs_ = qsat(Tm, p); f = Tm * (100000.0 / p) ** KAP * jnp.exp(LV * qs_ / (CP * Tm)) - the
                    df = (100000.0 / p) ** KAP * jnp.exp(LV * qs_ / (CP * Tm)) * (1 + LV ** 2 * qs_ / (CP * RV * Tm ** 2) - LV * qs_ / (CP * Tm))
                    Tm = jnp.clip(Tm - f / df, 150.0, 350.0)
                Tp = jnp.where(q0 < qsat(Td, p), Td, Tm)
                buoy = (Tp > T) & (sig < 0.95) & (sig > 0.1)
                cape = (RD * jnp.maximum(Tp - T, 0.0) * dsig / sig * buoy).sum(0)
                slzb = jnp.min(jnp.where(buoy, sig, 1.0), axis=0)
                reg = (sig >= slzb) & (cape > 50.0)
                qref = S['rh_bm'] * qsat(Tp, p)
                dTc = jnp.where(reg, -(T - Tp) / S['tau_bm'], 0.0); dqc = jnp.where(reg, -(q - qref) / S['tau_bm'], 0.0)
                Pq = -(dqc * dsig).sum(0) * ps[0] / G; PT = (CP / LV * dTc * dsig).sum(0) * ps[0] / G
                deep = (Pq > 0) & (PT > 0)
                nreg = jnp.maximum((reg * dsig).sum(0), 1e-3)
                corr = (PT - Pq) * LV / CP / (nreg * ps[0] / G)                                   # uniform shift so heating = rain
                dTc = jnp.where(reg & deep, dTc - corr, 0.0); dqc = jnp.where(reg & deep, dqc, 0.0)
                dT = dT + dTc; dq = dq + dqc
                # 4. large-scale condensation
                qs = qsat(T, p); gam = 1 + LV ** 2 * qs / (CP * RV * T ** 2)
                c = jnp.maximum(q - qs, 0.0) / gam / S['tau_c']; dq = dq - c; dT = dT + LV / CP * c
                dq = dq + jnp.maximum(-qr, 0.0) / 3600.0                                        # fill small negative humidity left by spectral advection
                # 5. radiation
                dT = dT + jnp.where(sig > 0.15, -S['cool'] / 86400.0, -(T - M.T0) / S['tau_strat'])
                # 6. sponge
                sp = jnp.where(sig < 0.08, 1.0 / S['sponge'], 0.0); du = du - sp * u; dv = dv - sp * v
                # back to the model's units / spectral form
                vt = hor.to_modal(jax.tree_util.tree_map(lambda x: x * M.MPS / M.SEC / cl, (du, dv)))
                return primitive_equations.State(
                    vorticity=hor.curl_cos_lat(vt), divergence=hor.div_cos_lat(vt),
                    temperature_variation=hor.to_modal(dT * M.K / M.SEC),
                    log_surface_pressure=jnp.zeros_like(state.log_surface_pressure),
                    tracers={'specific_humidity': hor.to_modal(dq / M.SEC)}, sim_time=None if state.sim_time is None else 0.0)
        return Phys()
    # ---------------------------------------------------------------- run
    def runner(self, hours, every_h=6, moist=True):
        hor = self.coords.horizontal
        eq = primitive_equations.PrimitiveEquationsSigma(self.ref_t, self.oro, self.coords, self.ps, humidity_key='specific_humidity')
        eqs = time_integration.compose_equations([eq, self.physics()]) if moist else eq
        res = hor.latitude_nodes / 128
        tau = self.ps.nondimensionalize(8.6 / (2.4 ** np.log2(res)) * units.hours)
        filt = time_integration.horizontal_diffusion_step_filter(hor, dt=self.dt, tau=tau, order=2)
        step = time_integration.step_with_filters(time_integration.imex_rk_sil3(eqs, self.dt), [filt])
        k850 = int(np.argmin(abs(self.sig - 0.85)))
        def post(state):
            u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, state.vorticity, state.divergence)
            return dict(ps=jnp.exp(hor.to_nodal(state.log_surface_pressure))[0] / self.PA, vo=hor.to_nodal(state.vorticity)[k850] * self.SEC,
                        ul=u[-1] / self.MPS, vl=v[-1] / self.MPS, rain_q=hor.to_nodal(state.tracers['specific_humidity'])[k850])
        inner = int(round(every_h * 60 / self.dt_min)); outer = int(hours // every_h) + 1
        f = jax.jit(time_integration.trajectory_from_step(step, outer_steps=outer, inner_steps=inner, start_with_input=True, post_process_fn=post))
        dfi = jax.jit(time_integration.digital_filter_initialization(equation=eq, ode_solver=time_integration.imex_rk_sil3, filters=[filt],
                                                                     time_span=self.ps.nondimensionalize(6 * units.hour), cutoff_period=self.ps.nondimensionalize(6 * units.hour), dt=self.dt))
        return f, dfi
    # ---------------------------------------------------------------- follow the storm
    def track(self, traj, la0, lo0, every_h=6):
        """centre = maximum of smoothed 850 hPa vorticity near where the storm should be (last position + last motion),
        refined to sub-grid by a vorticity-weighted centroid; no jumps over 3.5 deg in 6 h. Strength: max lowest-layer
        wind within 250 km (kt) and the surface-pressure dip against its 600-1000 km surroundings (hPa, sea only)."""
        from scipy import ndimage as ndi
        ps = np.asarray(traj['ps']); vo = np.asarray(traj['vo']); ul = np.asarray(traj['ul']); vl = np.asarray(traj['vl'])
        LO, LA = np.meshgrid(self.lon, self.lat, indexing='ij'); out = []; la, lo = la0, lo0; vel = (0.0, 0.0)
        dist = lambda a, b: np.hypot(LA - a, ((LO - b + 180) % 360 - 180) * math.cos(math.radians(a)))
        for i in range(ps.shape[0]):
            vs = ndi.uniform_filter(vo[i] * np.sign(la0 or 1), 3, mode='wrap')
            g = (la + vel[0], lo + vel[1]); d = dist(*g)
            s_ = np.where(d <= 3.5, vs, -1e9); j = np.unravel_index(np.argmax(s_), s_.shape)
            dj = dist(LA[j], LO[j]); w = np.clip(vs - 0.5 * vs[j], 0, None) * (dj <= 2.0)
            if w.sum() > 0:
                nl = float((w * LA).sum() / w.sum()); dlo = ((LO - LO[j] + 180) % 360 - 180); no = float(LO[j] + (w * dlo).sum() / w.sum())
            else: nl, no = float(LA[j]), float(LO[j])
            if i: vel = (0.7 * (nl - la), 0.7 * (((no - lo + 180) % 360) - 180))
            la, lo = nl, no % 360
            dd = dist(la, lo); wmax = float(np.hypot(ul[i], vl[i])[dd <= 2.3].max()) if (dd <= 2.3).any() else 0.0
            ring = (dd > 5) & (dd < 9); sea = (np.asarray(self.land) == 0)
            dp = float(ps[i][ring & sea].mean() - ps[i][(dd <= 1.5) & sea].min()) / 100 if (ring & sea).any() and ((dd <= 1.5) & sea).any() else None
            out.append((i * every_h, round(la, 2), round(lo, 2), round(wmax / 0.5144, 1), None if dp is None else round(dp, 1), round(float(vs[j]) * 1e5, 1)))
        return out
