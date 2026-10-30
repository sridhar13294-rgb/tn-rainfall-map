"""MEGAM - Multi-scale Engine for Global Atmospheric Modelling (Sridhar & Adhitya). Core atmosphere model."""
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
from ocean import step as ocean_step, profile_from_clim
import os as _os, sys as _sys                                                     # stage 2 ocean (scripts/ocean3d)
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', 'ocean3d'))
try:
    import currents as ocur, rgo as orgo
except Exception:                                                                 # ocean3d optional
    ocur = orgo = None
import radcloud
import cloudtop                                   # D2 cloud-top entrainment (numpy / jax)
import landinit                                   # starting land state from analysed soil fields (numpy; test_land_init.py)
from dinosaur import coordinate_systems, spherical_harmonic, sigma_coordinates, primitive_equations, scales, time_integration, filtering, vertical_interpolation
units = scales.units
G, RD, RV, CP, LV, SB, KARM = 9.80616, 287.04, 461.5, 1004.6, 2.5e6, 5.67e-8, 0.4; KAP = RD / CP
def sigma_bounds(n=32):
    """n (int): the original spacing. 'tpNN' (str): NN levels packed near the tropopause (~170 hPa), the boundary layer
    and the model top (ECMWF-style), so the 100-300 hPa band and the lowest km get thin layers."""
    if isinstance(n, str) and n.startswith('tp'):
        m = int(n[2:]); s = np.linspace(0, 1, 20001)
        dens = 1.0 + 1.3 * np.exp(-((s - 0.17) / 0.08) ** 2) + 1.5 * np.exp(-((1 - s) / 0.08) ** 2) + 1.0 * np.exp(-(s / 0.05) ** 2)
        cum = np.concatenate([[0], np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(s))]); cum /= cum[-1]
        return np.interp(np.linspace(0, 1, m + 1), cum, s).astype(np.float32)
    e = np.linspace(0, 1, n + 1); return (0.6 * e + 0.4 * (1 - (1 - e) ** 2)).astype(np.float32)
SND_LEVS = (1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200, 150, 100)   # sounding levels (hPa) for the map viewer
def load_gwd(path, LA, LO):
    """Sub-grid orography (ARCO ERA5, 0.5 deg: geo_gwd.npz from release era5-cases) to the model grid (nearest point):
    mu = std dev of filtered sub-grid orography (m), gam = anisotropy, the = angle of the principal axis (rad), slo = slope."""
    cands = [path] if path else []
    cands += ['/kaggle/working/geo_gwd.npz', _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'data', 'geo_gwd.npz'), 'geo_gwd.npz']
    fn = next((c for c in cands if c and _os.path.exists(c)), None)
    if fn is None: print('gwd: geo_gwd.npz not found - drag OFF', flush=True); return None
    Z = np.load(fn); la, lo = np.asarray(Z['lat']), np.asarray(Z['lon']) % 360
    i = np.clip(np.searchsorted(-la, -LA), 0, len(la) - 1) if la[0] > la[-1] else np.clip(np.searchsorted(la, LA), 0, len(la) - 1)
    j = np.clip(np.round((LO % 360 - lo[0]) / (lo[1] - lo[0])).astype(int), 0, len(lo) - 1)
    g = lambda k: jnp.asarray(np.nan_to_num(np.asarray(Z[k])[i, j]), jnp.float32)
    out = dict(mu=g('standard_deviation_of_filtered_subgrid_orography'), gam=jnp.clip(g('anisotropy_of_sub_gridscale_orography'), 0.05, 1.0),
               the=g('angle_of_sub_gridscale_orography'), slo=jnp.clip(g('slope_of_sub_gridscale_orography'), 0.0, 0.2))
    print('gwd: loaded', fn, 'mu max', float(out['mu'].max()), flush=True); return out
def gwd_tend(gw, u, v, T, p, zc, ps, dsig, dt, Gw=1.0, Cb=1.0):
    """Lott & Miller (1997) as in IFS: (1) blocking - below the blocking height Zb the flow goes around the mountains and
    is decelerated (implicit); (2) gravity waves launched by the unblocked part of the mountains carry a stress upward that
    is deposited where the waves saturate (stress limited by rho U^3 / N) or reach a critical level (wind turns or stops).
    u, v, T, p, zc [L, X, Y] (level 0 = top); returns du, dv (m/s per s)."""
    mu = gw['mu']; gam = gw['gam']; slo = gw['slo']; on = mu > 50.0
    Hm = 2.0 * mu                                                                               # sub-grid peaks ~2 std dev above the mean
    th = T * (ps / p) ** KAP; rho = p / (RD * T)
    lay = (zc <= jnp.maximum(Hm, zc[-2])[None]); wl = lay * dsig                                   # low-level layer (at least 2 levels)
    sw = jnp.maximum(wl.sum(0), 1e-6); uL = (u * wl).sum(0) / sw; vL = (v * wl).sum(0) / sw; rL = (rho * wl).sum(0) / sw
    UL = jnp.sqrt(uL ** 2 + vL ** 2) + 1e-3; ex = uL / UL; ey = vL / UL
    ktop = jnp.argmax(lay, axis=0)                                                              # top level of the low-level layer
    thT = jnp.take_along_axis(th, ktop[None], 0)[0]; zT = jnp.take_along_axis(zc, ktop[None], 0)[0]
    NL = jnp.sqrt(jnp.maximum(G / th[-1] * (thT - th[-1]) / jnp.maximum(zT - zc[-1], 10.0), 1e-6))
    psi = gw['the'] - jnp.arctan2(vL, uL); c2 = jnp.cos(psi) ** 2; s2 = jnp.sin(psi) ** 2
    B = 1 - 0.18 * gam - 0.04 * gam ** 2; C = 0.48 * gam + 0.3 * gam ** 2; geo = B * c2 + C * s2
    Zb = jnp.where(on, jnp.maximum(Hm - 0.5 * UL / NL, 0.0), 0.0)                              # blocking height (critical inverse Froude 0.5)
    r = (c2 + gam * s2) / (gam * c2 + s2)
    fb = Cb * jnp.maximum(2 - 1 / r, 0.0) * slo / (2 * jnp.maximum(mu, 1.0)) * geo * 0.5
    a = fb[None] * jnp.sqrt(jnp.maximum(Zb[None] - zc, 0.0) / (zc + jnp.maximum(mu, 1.0)[None])) * jnp.sqrt(u ** 2 + v ** 2)
    dub = -u * a / (1 + dt * a); dvb = -v * a / (1 + dt * a)                                   # blocked-flow drag (implicit, never reverses the wind)
    Heff = jnp.where(on, jnp.minimum(Hm, 0.5 * UL / NL), 0.0)                                 # mountain height seen by the waves
    k = slo / (4 * jnp.maximum(mu, 1.0))
    tau0 = Gw * rL * NL * UL * Heff ** 2 * k * geo                                              # launched wave stress (N/m2)
    N = jnp.sqrt(jnp.maximum(G / th * jnp.gradient(th, axis=0) / jnp.minimum(jnp.gradient(zc, axis=0), -1.0), 1e-6))   # both gradients negative (level 0 = top)
    Up = u * ex[None] + v * ey[None]
    tsat = jnp.where(Up > 0.5, Gw * rho * Up ** 3 / N * k[None] * 0.25 * geo[None], 0.0)          # saturation stress (inverse Froude 0.5); 0 at a critical level
    prof = jnp.where(lay, tau0[None], jnp.minimum(tsat, tau0[None]))
    prof = jax.lax.cummin(prof[::-1], axis=0)[::-1]                                            # stress can only decrease upward
    dtau = jnp.concatenate([prof[:1], prof[1:] - prof[:-1]], 0) * (~lay)                       # deposited in each level above the layer (top keeps the rest)
    acc = jnp.clip(G * dtau / (dsig * ps), 0.0, 1e-3)                                            # m/s2, capped at ~86 m/s per day
    acc = jnp.minimum(acc, jnp.maximum(Up, 0.0) / dt)                                           # never reverse the projected wind in one step
    return dub - acc * ex[None], dvb - acc * ey[None]
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
                h_ml=40.0, ent=0.6, tau_strat=15 * 86400.0, sponge=86400.0, sst_off=0.0, sppt=0.0, sppt_seed=0, gust=1.0, sppt_on=None,
                conv='mf', entr=1.5e-4, mf_cap=0.3, mf_closure='cape', rad='radcloud', rad_every=2,
                mf_kick_t=0.5, mf_kick_q=0.0005, mf_org=0.0, mf_wup=0.0, mf_dd=0.5, shallow='mse', sh_top=0.0, bmj_dt=0.5, rad_prm=None, bmj_ice=0.0, ck_z=0.5, sh_taper=0.0, pbl_tm=0.0, sh_trig=0.0, sh_clos=0.0, ev_frac=0.3, mf_wke=0.0, rad_top=0.12, mf_capdp=0.0, sp_quad=0.0, sp_top=0.05, src_dp=0.0, mf_dmin=25000.0, sh_dtop=0.0, sh_cap=0.0, sh_mflux=0.0, cmt_mf=0.0, cmt_cu=0.7, cld_pdf=0.0, ent_top=0.0, phys_off=False, mono=True, mf_ice=0.0, ocean3d=None)
RADKEYS = ('heating', 'sw_net_sfc', 'lw_dn_sfc', 'olr', 'cover')       # kept in the carry between radiation calls (rad_every > 1)
# settings an ensemble member may change without recompiling: carried as numbers inside the run (carry['prm'])
DT_MAX = {'T42': 60.0, 'T63': 40.0, 'T85': 30.0, 'T106': 20.0, 'T119': 20.0, 'T170': 20.0, 'T213': 15.0, 'T255': 12.0}
DYN = ('rh_deep', 'tau_deep', 'tau_shallow', 'ck', 'k_evap', 'ent', 'sppt', 'entr', 'mf_kick_t', 'mf_kick_q', 'mf_org', 'mf_wup', 'mf_dd', 'sh_top', 'bmj_dt', 'bmj_ice', 'ck_z', 'mf_ice', 'sh_taper', 'pbl_tm', 'sh_trig', 'sh_clos', 'ev_frac', 'mf_wke', 'rad_top', 'mf_capdp', 'sp_quad', 'sp_top', 'sponge', 'tau_strat', 'src_dp', 'mf_dmin', 'sh_dtop', 'sh_cap', 'sh_mflux')
NWAVE = 8
class Model:
    def __init__(self, grid='T170', layers=32, dt_min=None, set_=None):
        self.S = dict(DEFAULTS); self.S.update(set_ or {})
        if dt_min is None or (dt_min > DT_MAX.get(grid, 15.0)): dt_min = DT_MAX.get(grid, 15.0)   # longest stable step per grid (Kaggle benchmark: T119 blew up at 30 min)
        self.coords = coordinate_systems.CoordinateSystem((spherical_harmonic.Grid.construct(max_wavenumber=255, gaussian_nodes=192) if grid == 'T255' else getattr(spherical_harmonic.Grid, grid)()), sigma_coordinates.SigmaCoordinates(sigma_bounds(layers)))
        self.ps = primitive_equations.PrimitiveEquationsSpecs.from_si(); nd = self.ps.nondimensionalize
        self.K, self.SEC, self.MPS, self.PA, self.M = [float(nd(1 * u)) for u in (units.degK, units.s, units.m / units.s, units.pascal, units.m)]
        self.dt_s = dt_min * 60.0; self.dt = nd(dt_min * units.minute)
        lon, sinlat = self.coords.horizontal.nodal_axes; self.lon = np.degrees(lon); self.lat = np.degrees(np.arcsin(sinlat))
        self.LO, self.LA = np.meshgrid(self.lon, self.lat, indexing='ij')
        self.fcor = jnp.asarray(2 * 7.292e-5 * np.sin(np.radians(self.LA)), jnp.float32)
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
    def init(self, f3, levs, lats, lons, ps_pa, zs_m, sst_k, lsm, storm=None, ocean=None, when=None, soil_vol=None, soil_t=None, skin_t=None):
        """f3: temperature, specific_humidity, u/v_component_of_wind, geopotential -> [lev, lat, lon]. storm: dict(lat, lon,
        vmax_kt, rmw_km) to replace the analysis vortex with a balanced one. soil_vol (top-layer volumetric soil water, m3 m-3),
        soil_t / skin_t (K), [lat, lon] like sst_k: analysed land state for land points (landinit.py); None = the old guesses."""
        levs = np.asarray(levs, float); N = lambda x: self.to_nodes(x, lats, lons)
        T3, Q3, U3, V3 = [N(f3[k]) for k in ('temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind')]
        ps = N(ps_pa); zs = np.maximum(N(zs_m), 0.0); land = N(lsm) > 0.5
        sst = N(np.where(np.isfinite(sst_k), sst_k, 0.0)); sst = np.where(land | (sst < 260), 0.0, sst)
        if storm and storm.get('vmax_kt', 0) >= 15: T3, Q3, U3, V3, ps = self.bogus(T3, Q3, U3, V3, ps, levs, **storm)
        # the model's own terrain is the spectrally smoothed one (self.oro); the analysis' surface pressure belongs to the real
        # terrain. Move the surface pressure to the model terrain hypsometrically (temperature and humidity of the analysis at
        # the surface), as ECMWF/GFS do. Without this the start had false pressure gradients near mountains and their spectral
        # ripples (500 hPa height off by up to 1400 m over the Andes, 250 m over India, at hour 0).
        hor = self.coords.horizontal
        self.oro = filtering.exponential_filter(hor, order=2)(hor.to_modal(zs[None] * self.M))
        zs_mod = np.asarray(hor.to_nodal(self.oro))[0] / self.M
        lp = np.log(levs)[:, None, None]; lps = np.log(ps / 100.0)[None]; L = len(levs)
        k1 = np.clip((lp < lps).sum(0), 1, L - 1); k0 = k1 - 1
        g_ = lambda X, k: np.take_along_axis(X, k[None], 0)[0]
        wgt = np.clip((lps[0] - g_(lp * np.ones_like(T3), k0)) / (g_(lp * np.ones_like(T3), k1) - g_(lp * np.ones_like(T3), k0)), 0.0, 1.0)
        Ts = g_(T3, k0) + wgt * (g_(T3, k1) - g_(T3, k0)); Qs = np.maximum(g_(Q3, k0) + wgt * (g_(Q3, k1) - g_(Q3, k0)), 0.0)
        dz = zs_mod - zs; Tm = (Ts - 0.0065 * dz / 2) * (1 + 0.608 * Qs)
        ps = ps * np.exp(-G * dz / (RD * Tm)); zs = zs_mod
        pc = vertical_interpolation.PressureCoordinates(levs)
        sg = vertical_interpolation.interp_pressure_to_sigma({'t': T3, 'q': np.maximum(Q3, 0), 'u': U3, 'v': V3}, pc, self.coords.vertical, ps[None] / 100.0)
        sg = {k: np.asarray(v, np.float32) for k, v in sg.items()}
        vor, div = spherical_harmonic.uv_nodal_to_vor_div_modal(hor, sg['u'] * self.MPS, sg['v'] * self.MPS)
        st = primitive_equations.State(vorticity=vor, divergence=div, temperature_variation=hor.to_modal(sg['t'] * self.K - self.ref_t[:, None, None]),
                                       log_surface_pressure=hor.to_modal(np.log(ps[None] * self.PA)), tracers={'specific_humidity': jnp.asarray(sg['q'])})
        self.zs = jnp.asarray(zs, jnp.float32); self.land = jnp.asarray(land); self.T0 = jnp.asarray(sg['t'])
        if self.S.get('gwd', 0) and getattr(self, 'gw', None) is None: self.gw = load_gwd(self.S.get('gwd_file'), np.asarray(self.LA), np.asarray(self.LO))
        sst = sst + self.S['sst_off'] * (sst > 0); self.sst0 = jnp.asarray(sst, jnp.float32)
        # land temperature and soil-moisture bucket: analysed values on land when given (bucket = soil water / porosity 0.45 x
        # capacity; skin, else soil temperature); otherwise, and at sea, the old start (lowest-level temperature, bucket 60 % full)
        tl0, w0 = landinit.land_start(N, sg['t'][-1], land, self.S['bucket'], soil_vol, soil_t, skin_t)
        carry = dict(sst=jnp.asarray(sst, jnp.float32), tl=jnp.asarray(tl0, jnp.float32), w=jnp.asarray(w0, jnp.float32),
                     rain=jnp.zeros(zs.shape, jnp.float32), t=jnp.float32(0.0), sst0=jnp.asarray(sst, jnp.float32), T0=jnp.asarray(sg['t'], jnp.float32),
                     prm=self.params())
        if ocean is not None:                                                                       # 1-D ocean column under every sea point (ocean.py)
            oc0 = profile_from_clim(ocean, when, self.LA, self.LO, sst, sst > 0)
            carry['ocean'] = {k: jnp.asarray(v, jnp.float32) for k, v in oc0.items()}
            if self.S.get('ocean3d'):                                                               # stage 2: currents / reduced-gravity layer
                self.ocg = ocur.make_geom(self.LA, self.LO, oc0['dz'], sst > 0)
                if self.S['ocean3d'] == 'rgo':
                    self.rgg = orgo.make_geom(self.LA, self.LO, sst > 0)
                    rg0 = orgo.init_state(self.rgg, orgo.d20(np.asarray(oc0['T'], float), np.asarray(oc0['dz'], float)))
                    carry['rgo'] = {k: jnp.asarray(v, jnp.float32) for k, v in rg0.items()}
        if self.S['rad'] == 'radcloud' and self.S['rad_every'] > 1:                               # radiation cache, refreshed in surface()
            z2 = jnp.zeros(zs.shape, jnp.float32)
            carry['rad'] = dict(heating=jnp.zeros((len(self.sig),) + zs.shape, jnp.float32), sw_net_sfc=z2, lw_dn_sfc=z2, olr=z2, cover=z2)
            if self.S.get('ent_top', 0): carry['rad'].update(lw_cld=jnp.zeros((len(self.sig),) + zs.shape, jnp.float32), cloud=jnp.zeros((len(self.sig),) + zs.shape, jnp.float32))
        return st, carry
    def bogus(self, T3, Q3, U3, V3, ps, levs, lat, lon, vmax_kt, rmw_km=None, R_out=None, B=1.4, t_hours=None):
        """Replace the analysis vortex by a balanced Holland vortex: lowest-level max wind vmax_kt/0.85 at radius rmw_km,
        decaying upward (weak above 400 hPa), in gradient balance; warm core from hydrostatic balance; moist core."""
        cosl = math.cos(math.radians(lat)); d = np.hypot(self.LA - lat, ((self.LO - lon + 180) % 360 - 180) * cosl) * 111.2      # km
        grid_km = 111.2 * 180.0 / len(self.lat); rm = max(rmw_km or (150.0 if vmax_kt < 34 else 100.0), 1.3 * grid_km)
        def fill(X, R=4.0, dd=None):
            dd = d if dd is None else dd; m = dd <= R * 111.2; X = X.copy()
            for k in range(X.shape[0] if X.ndim == 3 else 1):
                f = X[k] if X.ndim == 3 else X; f[m] = np.nanmean(f[(dd > R * 111.2) & (dd <= (R + 2) * 111.2)])
                for _ in range(80): f[m] = ndi.uniform_filter(f, 5, mode='wrap')[m]
            return X
        if self.S.get('storm_mode', 'bogus') == 'relocate':
            # NCEP-style relocation: split each field into environment (vortex filled in from the ring 4-6 deg out) and the
            # analysis' own vortex, move the vortex to the observed centre, put it back. Keeps the analysed structure and size.
            P = ndi.uniform_filter(ps, 3, mode='wrap'); near = d <= 350.0
            ja = np.unravel_index(np.argmin(np.where(near, P, np.inf)), P.shape)
            dlon = ((lon - self.LO[ja] + 180) % 360) - 180; dlat = lat - self.LA[ja]
            dx = float(np.mean(np.diff(self.lon))); dy = float(np.mean(np.diff(self.lat)))
            sh = (dlon / dx, dlat / dy)
            da = np.hypot(self.LA - self.LA[ja], ((self.LO - self.LO[ja] + 180) % 360 - 180) * cosl) * 111.2   # around the analysis' own centre
            def move(X):
                E_ = fill(X, dd=da); return E_ + ndi.shift(X - E_, ((0,) if X.ndim == 3 else ()) + sh, order=1, mode='nearest')
            T3, Q3, U3, V3 = move(T3), np.maximum(move(Q3), 0.0), move(U3), move(V3); ps = move(ps[None])[0]
            return T3, Q3, U3, V3, ps
        U3, V3 = fill(U3), fill(V3)
        # remove the analysis' own low too (pressure and warm core, within 3 deg): otherwise its centre, often 50-100 km from
        # the observed one, stays as a second low and the start position is a blend of the two (72 km median at 0 h in tests)
        T3 = fill(T3, R=3.0); ps = fill(ps[None], R=3.0)[0]
        f0 = 2 * 7.292e-5 * math.sin(math.radians(lat)); Vm = vmax_kt * 0.5144 / 0.85; rho = 1.15
        # wind profile (modified Rankine, decay exponent x, tapered to calm beyond R_out), then the balancing geopotential from
        # gradient balance. The outer winds (300-1000 km) set the beta drift: the old profile (x 0.5, taper from 600 km over
        # 400 km) was far broader than real depressions and drifted the storm ~0.4 deg/day too far north in past-storm tests.
        R_out = R_out or float(self.S.get('bogus_rout', 180.0)); xd = float(self.S.get('bogus_x', 0.4))
        rr = np.linspace(0, R_out + 900, 600) * 1e3; rk = rr / 1e3
        Vr = np.where(rk < rm, Vm * rk / rm, Vm * (rm / np.maximum(rk, 1e-3)) ** xd) * np.exp(-(np.maximum(rk - R_out, 0) / 150.0) ** 2)
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
    def conv_mf(self, Tn, qn, p, mass, zc, sig, dsig, ps, ksrc, S, dt, div=None, E=None, shallow=False, Hs=None):
        """Bulk mass-flux deep convection (Tiedtke/Bechtold type). One entraining updraft per column rises from the most
        unstable low level; entrainment grows in dry air (eps = entr x (1.3 - RH)), so convection needs a moist column -
        the moistening feedback that lets a weak low organise. Condensate rains out (re-evaporating below in the rain
        step). Environment changes from the updraft-environment flux differences (energy and water conserved, with the
        rain as the only sink); compensating subsidence warms and dries. Closure: the plume's CAPE is removed over
        tau_deep. Returns dT, dq (per s), rain production per layer (kg m-2 s-1), cloud mask, deep flag.
        shallow=True (setting shallow='mf'): the same plume for shallow cumulus (ECMWF style) - clouds less than 250 hPa deep,
        closure over tau_shallow, no rain and no downdraft: the plume's condensate evaporates where it forms/detrains, which
        cools and moistens the cloud layer while the updraft carries heat and moisture up from the boundary layer."""
        L = Tn.shape[0]; ii = jnp.arange(L)[:, None, None]; h_e = CP * Tn + G * zc + LV * qn
        rh_e = jnp.clip(qn / qsat(Tn, p), 0, 1); sig_src = jnp.take_along_axis(sig * jnp.ones_like(Tn), ksrc[None], 0)[0]
        qs_e = qsat(Tn, p); qs_src = jnp.maximum(jnp.take_along_axis(qs_e, ksrc[None], 0)[0], 1e-6)
        # parcel kick (mf_kick_t K, mf_kick_q kg/kg): the extra warmth and moisture of rising boundary-layer thermals, as in
        # ECMWF's trigger test; organised entrainment (mf_org > 0): mixing falls off with height as (qsat / qsat at the
        # source)^(3 mf_org) (Bechtold et al. 2008), so a deep moist plume can reach the upper troposphere
        h_kick = CP * S['mf_kick_t'] + LV * S['mf_kick_q']
        def plume(c, x):
            hu, qu, alive, lfc, started, zp, Kw = c; Te, qe, he, pk, zk, sk, rk, k = x
            src = (k == ksrc); dz = jnp.maximum(zk - zp, 0.0)
            eps = S['entr'] * (1.3 - rk) * jnp.power(jnp.clip(qsat(Te, pk) / qs_src, 1e-3, 1.0), 3.0 * S['mf_org'])
            hu1 = jnp.where(src, he + h_kick, hu + eps * dz * (he - hu)); qu1 = jnp.where(src, qe + S['mf_kick_q'], qu + eps * dz * (qe - qu))
            Td = (hu1 - G * zk - LV * qu1) / CP; sat = qu1 > qsat(Td, pk); Tu = Te
            for _ in range(4):
                qs_ = qsat(Tu, pk); f_ = CP * Tu + G * zk + LV * qs_ - hu1; df = CP + LV * qs_ * 17.67 * 243.5 / (Tu - 29.65) ** 2
                Tu = jnp.clip(Tu - f_ / df, 150.0, 350.0)
            Tu = jnp.where(sat, Tu, Td); qv = jnp.where(sat, qsat(Tu, pk), qu1); cond = jnp.maximum(qu1 - qv, 0.0)
            b = Tu * (1 + 0.61 * qv) - Te * (1 + 0.61 * qe)
            st2 = started | src; run = started & alive & ~src                                         # above the source, still rising
            lfc2 = jnp.where(run, lfc | (b > 0), lfc)
            # mf_wke > 0 (ECMWF IFS Cy50r1 eq. 6.10): updraught kinetic energy K = w^2/2, starting at 0.5 (w = 1 m/s) when the plume
            # first becomes buoyant: dK/dz = -eps (1 + beta Cd) 2K + g b / (f (1 + gamma) Tv), beta Cd = 0.949, f (1 + gamma) = 3.
            # The cloud top is where K reaches zero, so plumes can push through thin stable layers (e.g. near the 0 C level)
            # instead of stopping at the first level of negative buoyancy (old rule: plumes died in mid-levels, heating too low)
            Kn = jnp.where(lfc, (Kw + dz * G * b / (3.0 * Te)) / (1.0 + dz * eps * 2.0 * 1.949), 0.5)
            ok_k = jnp.where(S['mf_wke'] > 0, jnp.where(lfc, Kn > 0, b > 0), b > 0)
            alv2 = jnp.where(src, True, jnp.where(run, alive & (ok_k | (~lfc & (sig_src - sk < 0.2))) & (sk > 0.08), alive & ~started))
            Kw2 = jnp.where(run & (lfc | (b > 0)), jnp.maximum(Kn, 0.0), Kw)
            act = st2 & alv2 & (run | src)
            # freezing (mf_ice = share of the new condensate that freezes in the updraft): above 0 C its latent heat of fusion
            # warms the plume, as in the old scheme's bmj_ice; without it the tropical upper troposphere runs 3-5 K cold
            hu1 = hu1 + S['mf_ice'] * 3.34e5 * jnp.clip((273.15 - Tu) / 20.0, 0.0, 1.0) * cond
            nh = jnp.where(act, jnp.where(src, he + h_kick, hu1), hu); nq = jnp.where(act, jnp.where(src, qe + S['mf_kick_q'], qv), qu)
            return (nh, nq, alv2, lfc2, st2, jnp.where(act | ~st2, zk, zp), Kw2), (act, jnp.where(run & act, b, 0.0), jnp.where(run & act, cond, 0.0), nh, nq)
        z0 = jnp.zeros_like(ps); f0 = jnp.zeros(ps.shape, bool)
        # src_dp > 0 (Pa): the rising parcel starts from the mass-weighted mean moist static energy and humidity of a src_dp-thick
        # layer centred on the source level (ECMWF-style mixed departure layer), not one model layer - so the trigger and the
        # plume do not change when layers get thinner (50/75 levels)
        win = (jnp.abs(sig - sig_src[None]) * ps[None] <= 0.5 * S['src_dp']) | (ii == ksrc[None])
        wm = mass * win; h_avg = (h_e * wm).sum(0) / wm.sum(0); q_avg = (qn * wm).sum(0) / wm.sum(0)
        use = (S['src_dp'] > 0) & (ii == ksrc[None])
        h_in = jnp.where(use, h_avg[None], h_e); q_in = jnp.where(use, q_avg[None], qn)
        xs = tuple(a[::-1] for a in (Tn, q_in, h_in, p * jnp.ones_like(Tn), zc, sig * jnp.ones_like(Tn), rh_e, ii * jnp.ones(Tn.shape, jnp.int32)))
        (_, _, _, lfc, _, _, _), (inc, b, cond, hu, qu) = jax.lax.scan(plume, (z0, z0, f0, f0, f0, z0 - 1.0, z0 + 0.5), xs)
        inc, b, cond, hu, qu = [a[::-1] for a in (inc, b, cond, hu, qu)]
        sig_top = jnp.min(jnp.where(inc, sig, 1.0), axis=0); cape = (RD * jnp.maximum(b, 0) * dsig / sig * inc).sum(0)
        deep = lfc & ((sig_src - sig_top) * ps > S['mf_dmin']) & (cape > 50.0)   # mf_dmin: minimum cloud depth (Pa) for deep convection (ECMWF ~20000)
        if shallow: deep = lfc & ((sig_src - sig_top) * ps <= 25000.0) & (cape > 0.0) & (sig_src > 0.8)      # 'deep' = this plume is active
        if shallow:
            # sh_trig > 0 (ECMWF-type trigger): shallow cumulus wherever the boundary-layer parcel reaches its condensation level
            # (the plume makes cloud) and the cloud stays under 300 hPa deep - it need not become buoyant first. The old test
            # (positive buoyancy and CAPE > 0) almost never passed: the shallow plume did nothing (h_shal ~0 in the budget).
            cloud = (cond > 0).any(0)
            deep = jnp.where(S['sh_trig'] > 0, cloud & ((sig_src - sig_top) * ps <= 30000.0) & (sig_src > 0.8), deep)
        frac = (sig_src - sig) / jnp.maximum(sig_src - sig_top, 1e-3)
        eta = jnp.where(inc & (ii != ksrc), jnp.clip(jnp.where(frac < 0.6, 1.0, (1 - frac) / 0.4), 0, 1), 0.0) * deep    # mass flux entering each cloud layer from below
        sh = lambda a: jnp.concatenate([a[1:], a[-1:]], 0)                                          # value of the layer below
        Fh = eta * (sh(hu) - h_e); Fq = eta * (sh(qu) - qn)                                         # across each layer's bottom interface, per unit Mb
        top = lambda F: jnp.concatenate([jnp.zeros_like(F[:1]), F[:-1]], 0)                        # = bottom flux of the layer above
        dh1 = (Fh - top(Fh)) / mass; P1 = eta * cond; dq1 = (Fq - top(Fq)) / mass - (0.0 if shallow else P1 / mass)   # shallow: condensate re-evaporates in place
        # the source layer: air leaves upward through its top (handled: its top flux = the bottom flux of the layer above)
        dT1 = (dh1 - LV * dq1) / CP
        gam = LV / CP * qsat(Tn, p) * 17.67 * 243.5 / (Tn - 29.65) ** 2
        dhs = jnp.take_along_axis(dh1, ksrc[None], 0)[0]
        dcape = (RD * (dhs[None] / (CP * (1 + gam)) - dT1) * dsig / sig * (inc & (ii != ksrc))).sum(0)    # CAPE change per unit mass flux
        mmin = jnp.min(jnp.where(eta > 0, mass, 1e9), axis=0)
        # mf_capdp > 0 (Pa): the stability cap on the cloud-base mass flux uses at least the mass of a mf_capdp-thick layer
        # instead of the thinnest cloud layer - otherwise thinner model layers (more levels) cap convection lower (it was
        # tuned on 32 levels; 50 levels cut TN rain skill)
        mmin = jnp.maximum(mmin, S['mf_capdp'] / G)
        # CAPE closure (Bechtold / ECMWF): CAPE removed over tau; with mf_wup > 0, tau = cloud depth / updraft speed (ECMWF's
        # convective turnover time), between 10 min and tau_deep
        zsrc = jnp.take_along_axis(zc, ksrc[None], 0)[0]; ztop = jnp.max(jnp.where(inc, zc, 0.0), axis=0)
        tau = jnp.where(S['mf_wup'] > 0, jnp.clip((ztop - zsrc) / jnp.maximum(S['mf_wup'], 1e-3), 600.0, S['tau_deep']), S['tau_deep'])
        if shallow: tau = S['tau_shallow'] * jnp.ones_like(tau)
        Mb = cape / (tau * jnp.maximum(-dcape, 1e-6))
        if shallow and Hs is not None and E is not None:
            # sh_clos > 0 (ECMWF shallow closure, boundary-layer moist static energy budget): the cloud-base mass flux carries
            # away sh_clos x the surface moist-static-energy flux (H + L E): Mb = sh_clos (H + L E) / (h_updraft - h_env) at the
            # level above the source (difference kept >= 1 kJ/kg)
            kb = jnp.maximum(ksrc - 1, 0)
            dhb = jnp.maximum(jnp.take_along_axis(hu - h_e, kb[None], 0)[0], 1000.0)
            Mb = jnp.where(S['sh_clos'] > 0, S['sh_clos'] * jnp.maximum(Hs + LV * E, 0.0) / dhb, Mb)
        if S['mf_closure'] == 'hybrid' and div is not None:
            # moisture-convergence closure (Tiedtke 1989, ECMWF's original scheme): the updraft carries away at least the moisture
            # that the boundary layer gathers by low-level inflow plus surface evaporation. This ties convection to the low's
            # convergence - the feedback by which a weak low organises.
            pbl = sig >= 0.85
            conv_q = jnp.maximum(-(qn * div * mass * pbl).sum(0) + (E if E is not None else 0.0), 0.0)        # kg m-2 s-1
            kb = jnp.maximum(ksrc - 1, 0); Tb = jnp.take_along_axis(Tn, kb[None], 0)[0]; qb = jnp.take_along_axis(qn, kb[None], 0)[0]
            pb = jnp.take_along_axis(p * jnp.ones_like(Tn), kb[None], 0)[0]
            Mb = jnp.maximum(Mb, conv_q / jnp.maximum(qsat(Tb, pb) - qb, 5e-4))
        Mb = jnp.clip(Mb, 0.0, jnp.minimum(S['mf_cap'] * mmin / dt, 1.0)) * deep
        if not shallow: self._cmt_M = eta * Mb[None]                                               # updraft mass flux per layer (kg m-2 s-1), for mass-flux momentum transport
        # downdraft (mf_dd = its mass flux as a share of the updraft's, ECMWF ~0.3): air from the level of free sink (lower
        # third of the cloud) is cooled to saturation by evaporating rain and sinks moist-adiabatically (moist static energy of
        # that level kept) to the ground, where it spreads out: cools and moistens the lowest layers, takes rain back up.
        sig_lfs = sig_src - 0.35 * (sig_src - sig_top); k_lfs = jnp.argmin(jnp.abs(sig - sig_lfs[None]), axis=0)
        h_d = jnp.take_along_axis(h_e, k_lfs[None], 0)[0]
        ind = (ii >= k_lfs[None]) & deep[None]                                                     # LFS down to the ground
        Td = Tn
        for _ in range(4):
            qs_ = qsat(Td, p); f_ = CP * Td + G * zc + LV * qs_ - h_d[None]; df = CP + LV * qs_ * 17.67 * 243.5 / (Td - 29.65) ** 2
            Td = jnp.clip(Td - f_ / df, 150.0, 350.0)
        q_d = qsat(Td, p); hd3 = h_d[None] * jnp.ones_like(Tn)
        last = ii == L - 1
        Fhd = jnp.where(ind & ~last, hd3 - sh(h_e), 0.0); Fqd = jnp.where(ind & ~last, q_d - sh(qn), 0.0)          # down across each layer's bottom
        q_prev = jnp.concatenate([qn[:1], q_d[:-1]], 0)
        Ev = jnp.where(ind, jnp.maximum(jnp.where(ii == k_lfs[None], q_d - qn, q_d - q_prev), 0.0), 0.0)             # evaporation into the downdraft, per unit flux
        Ed = (Ev).sum(0); Pu = (P1 * Mb).sum(0)
        a_dd = S['mf_dd'] * jnp.minimum(1.0, Pu / jnp.maximum(S['mf_dd'] * Mb * Ed, 1e-12)) * (0.0 if shallow else 1.0)   # cannot evaporate more rain than the updraft made; none for shallow
        Md = a_dd * Mb
        dh_dd = (top(Fhd) - Fhd) / mass * Md; dq_dd = ((top(Fqd) - Fqd) + Ev) / mass * Md
        Pscale = jnp.clip(1.0 - Md * Ed / jnp.maximum(Pu, 1e-12), 0.0, 1.0)
        dT_dd = (dh_dd - LV * dq_dd) / CP
        if shallow: return dT1 * Mb, dq1 * Mb, jnp.zeros_like(P1), inc & deep[None], deep
        return dT1 * Mb + dT_dd, dq1 * Mb + dq_dd, P1 * Mb * Pscale, inc & deep[None], deep
    def column(self, T, q, u, v, ps, cr, want_diag=False, rad_fresh=False, div=None):
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
        cd = cdn * fst
        # ck is a 10-m-height value (bulk formulas, COARE): brought to the lowest model level (~80 m) with the log law;
        # using it directly with the faster wind up there overstated sea evaporation by ~30% (ck_z=1 on, 0 off; off until tested)
        zfac = jnp.where(sea, (jnp.log(10.0 / z0) / jnp.log(z1 / z0)) ** 2, 1.0) ** S['ck_z']
        ckn = jnp.where(sea, S['ck'] * zfac, 0.8 * cdn); ck = ckn * fst
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
        # pbl_tm = 1: Troen & Mahrt (1986) / Hong & Pan (1996) as in NCEP and ECMWF-type K-profiles: w* from the actual
        # boundary-layer height, ws = (u*^3 + 7 eps kappa w*^3)^(1/3) with eps = 0.1 (the old line had 0.6 x 0.1 x kappa:
        # ~12x too small, so daytime mixing was ~2.3x too weak), and a counter-gradient heat/moisture flux (below)
        bflux = jnp.maximum(G / thv1 * (H / (rho * CP) + 0.61 * th1 * E / rho), 0)
        wstar = jnp.where(S['pbl_tm'] > 0, jnp.cbrt(bflux * hbl), wstar)
        ws = jnp.where(S['pbl_tm'] > 0, jnp.cbrt(ust ** 3 + 7.0 * 0.1 * KARM * wstar ** 3), jnp.cbrt(ust ** 3 + 0.6 * KARM * wstar ** 3 * 0.1))
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
        dth = diffuse(th, H / CP * (ps / p1) ** KAP)
        # counter-gradient transport (pbl_tm): upward flux rho K gamma inside the boundary layer, gamma = 6.5 w'x'_0 / (ws h)
        inbl = (zh < hbl[None]) & (S['pbl_tm'] > 0) & (H > 0)[None]
        wsh = jnp.maximum(ws * hbl, 1e-3)
        g_th = 6.5 * (H / (rho * CP)) * (ps / p1) ** KAP / wsh; g_q = 6.5 * (E / rho) / wsh
        def cg(gam):
            F = jnp.where(inbl, rhoh * Kh * gam[None], 0.0)                                          # kg m-2 s-1 x unit, upward, at interfaces
            z0_ = jnp.zeros_like(F[:1]); return (jnp.concatenate([F, z0_], 0) - jnp.concatenate([z0_, F], 0)) / mass
        dth = dth + cg(g_th); dq = dq + cg(g_q)
        dT = dth * (p / ps) ** KAP
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
        # freezing: above the 0 C level part of the cloud water freezes and gives up its latent heat of fusion (3.34e5 J/kg),
        # warming the rising air (ignored by a liquid-only moist adiabat: tropical upper troposphere ~2-3 K too cold).
        # bmj_ice = share of the condensed water that freezes in the updraft (the rest has rained out first).
        fice = jnp.clip((273.15 - Tm) / 20.0, 0.0, 1.0); qs_m = qsat(Tm, p); gam_m = 1 + LV ** 2 * qs_m / (CP * RV * Tm ** 2)
        Tm = Tm + S['bmj_ice'] * 3.34e5 * fice * jnp.maximum(qsrc[None] - qs_m, 0.0) / (CP * gam_m)
        Tp = jnp.where(qsrc < qsat(Td, p), Td, Tm)
        abovesrc = sig < jnp.take_along_axis(sig * jnp.ones_like(Tn), ksrc[None], axis=0)[0]
        buoy = (Tp > Tn) & abovesrc & (sig > 0.08)
        cape = (RD * jnp.maximum(Tp - Tn, 0) * dsig / sig * buoy).sum(0)
        sig_top = jnp.min(jnp.where(buoy, sig, 1.0), axis=0)
        sat_base = qsrc >= qsat(Td, p); sig_base = jnp.max(jnp.where(sat_base & (sig <= 1.0), sig, 0.0), axis=0)
        depth = (sig_base - sig_top) * ps
        deep = (cape > 100.0) & (depth > 20000.0)
        shallow = (cape > 0.0) & (~deep) & (sig_base > 0.75) & ((sig_top > S['sh_dtop']) | (S['sh_cap'] > 0))           # sh_cap > 0: deep-parcel columns keep boundary-layer mixing, capped at sh_cap; sh_dtop > 0: no 'shallow' mixing in columns whose parcel top is above sh_dtop (those are deep clouds, not shallow)
        reg = (sig >= sig_top) & (cape > 0)
        Tref = Tp - S['bmj_dt']; qref = S['rh_deep'] * qsat(Tref, p)
        dTc = jnp.where(reg & deep, relax(Tn, Tref, S['tau_deep'], dt), 0.0); dqc = jnp.where(reg & deep, relax(qn, qref, S['tau_deep'], dt), 0.0)
        Pq = -(dqc * mass).sum(0); PT = (CP / LV * dTc * mass).sum(0)
        ok = deep & (Pq > 0) & (PT > 0)
        nmass = jnp.maximum((reg * mass).sum(0), 1.0)
        dTc = jnp.where(reg & ok, dTc - (PT - Pq) * LV / CP / nmass, 0.0); dqc = jnp.where(reg & ok, dqc, 0.0)
        Pc = jnp.where(ok, Pq, 0.0)                                                                  # convective rain, kg m-2 s-1
        # shallow: mix heat and moisture over the shallow cloud layer (no rain)
        if S['shallow'] == 'theta':                                                                  # old: mixes potential temperature - creates heat
            sreg = shallow[None] & (sig >= sig_top - 0.05)                                           # (moving theta down a deep layer raises enthalpy): +2 K/day at 850 hPa
            mth = ((th * mass) * sreg).sum(0) / jnp.maximum((mass * sreg).sum(0), 1.0); mq = ((qn * mass) * sreg).sum(0) / jnp.maximum((mass * sreg).sum(0), 1.0)
            dTs = jnp.where(sreg, relax(th, mth, S['tau_shallow'], dt) * (p / ps) ** KAP, 0.0); dqs = jnp.where(sreg, relax(qn, mq, S['tau_shallow'], dt), 0.0)
        else:                                                                                        # mixes moist static energy h = cp T + g z + L q and water: column
            # sh_taper > 0: the mixing fades out linearly over sh_taper (sigma) above sh_top instead of stopping in one layer
            # (a hard top left a cold, moist 850 hPa layer); tendencies re-centred so energy and water stay conserved
            top_ = jnp.maximum(sig_top, S['sh_top'] - S['sh_taper'])
            top_ = jnp.where((S['sh_cap'] > 0) & (sig_top <= S['sh_dtop']), jnp.maximum(top_, S['sh_cap']), top_)   # deep parcel: mix only up to sh_cap (e.g. 0.8 = ~800 hPa), leave the instability aloft to the deep scheme
            sreg = shallow[None] & (sig >= top_)                                                     # energy and water conserved exactly (no rain from shallow cloud); sh_top caps its depth
            wgt = jnp.where(S['sh_taper'] > 0, jnp.clip((sig - (S['sh_top'] - S['sh_taper'])) / jnp.maximum(S['sh_taper'], 1e-6), 0.0, 1.0), 1.0) * sreg
            hs_ = CP * Tn + G * zc + LV * qn; msum = jnp.maximum((mass * sreg).sum(0), 1.0)
            mh = ((hs_ * mass) * sreg).sum(0) / msum; mq = ((qn * mass) * sreg).sum(0) / msum
            # sh_mflux > 0 (kg m-2 s-1): the mixing time is set by a realistic shallow-cumulus mass flux (observed ~0.02-0.03,
            # e.g. BOMEX) instead of a fixed tau_shallow: relaxing a layer of mass m to its mean in tau is an exchange of ~m / (2 tau);
            # with tau_shallow = 1 h over 200-600 hPa that is 0.3-0.9 kg m-2 s-1, i.e. 10-40x too strong
            tsh = jnp.where(S['sh_mflux'] > 0, jnp.maximum(msum / (2.0 * jnp.maximum(S['sh_mflux'], 1e-6)), S['tau_shallow']), S['tau_shallow'])[None]
            dhs = wgt * relax(hs_, mh, tsh, dt); dqs = wgt * relax(qn, mq, tsh, dt)
            dhs = jnp.where(sreg, dhs - (dhs * mass * sreg).sum(0) / msum, 0.0); dqs = jnp.where(sreg, dqs - (dqs * mass * sreg).sum(0) / msum, 0.0)
            dTs = (dhs - LV * dqs) / CP
        # convective momentum mixing
        if S['conv'] == 'mf':                                                                       # mass-flux scheme replaces the adjustment
            dTc, dqc, Pmf, regmf, okmf = self.conv_mf(Tn, qn, p, mass, zc, sig, dsig, ps, ksrc, S, dt, div=div, E=E)
            reg, ok = regmf, okmf
            on_dp = okmf.astype(jnp.float32); on_sh = jnp.zeros_like(on_dp)
            if S['shallow'] == 'mf':                                                                 # shallow cumulus as a non-raining mass-flux plume
                dTs, dqs, _, _, oks = self.conv_mf(Tn, qn, p, mass, zc, sig, dsig, ps, ksrc, S, dt, shallow=True, E=E, Hs=H)
                on_sh = (oks & ~okmf).astype(jnp.float32)
            dTs = jnp.where(okmf[None], 0.0, dTs); dqs = jnp.where(okmf[None], 0.0, dqs)
        cm = reg & ok[None]
        mu = ((u * mass) * cm).sum(0) / jnp.maximum((mass * cm).sum(0), 1.0); mv = ((v * mass) * cm).sum(0) / jnp.maximum((mass * cm).sum(0), 1.0)
        dT = dT + dTc + dTs; dq = dq + dqc + dqs
        if self.S.get('cmt_mf', 0) and S['conv'] == 'mf' and getattr(self, '_cmt_M', None) is not None:
            # mass-flux convective momentum transport (Gregory et al. 1997; ECMWF IFS): du/dt = g d/dp [M (u_u - u)],
            # updraft wind from the source up: du_u/dz = -eps (u_u - u) + C_u du/dz (C_u = 0.7: pressure-gradient effect).
            # Strength follows the actual mass flux M, so it acts strongly only in strong, organised convection.
            Mf = self._cmt_M; Cu = float(self.S.get('cmt_cu', 0.7))
            rhq = jnp.clip(q / qsat(T, p), 0, 1); epsq = S['entr'] * (1.3 - rhq)
            dzl = jnp.concatenate([jnp.maximum(zc[:-1] - zc[1:], 1.0), jnp.ones_like(zc[:1])], 0)        # height from the level below
            def upd(c, x):
                uu_b, vu_b, u_b, v_b = c; u_k, v_k, M_k, dz_k, e_k = x
                act = M_k > 0
                uu_k = jnp.where(act, uu_b + dz_k * (-e_k * (uu_b - u_b) + Cu * (u_k - u_b) / dz_k), u_k)
                vu_k = jnp.where(act, vu_b + dz_k * (-e_k * (vu_b - v_b) + Cu * (v_k - v_b) / dz_k), v_k)
                return (uu_k, vu_k, u_k, v_k), (uu_k, vu_k)
            xs = (u[::-1], v[::-1], Mf[::-1], dzl[::-1], epsq[::-1])
            _, (uu_r, vu_r) = jax.lax.scan(upd, (u[-1], v[-1], u[-1], v[-1]), xs)
            uu_, vu_ = uu_r[::-1], vu_r[::-1]
            def cmt_tend(F):
                Fi = jnp.concatenate([jnp.zeros_like(F[:1]), 0.5 * (F[1:] + F[:-1]), jnp.zeros_like(F[:1])], 0)   # interfaces, top -> bottom
                return G * (Fi[1:] - Fi[:-1]) / dp
            du = du + cmt_tend(Mf * (uu_ - u)); dv = dv + cmt_tend(Mf * (vu_ - v))
        else:
            du = du + jnp.where(cm, relax(u, mu, S['tau_cmt'], dt), 0.0); dv = dv + jnp.where(cm, relax(v, mv, S['tau_cmt'], dt), 0.0)
        # ---------------- large-scale condensation (adjustment) + rain re-evaporation
        Tn = T + dt * dT; qn = jnp.maximum(q + dt * dq, 0)
        qs = qsat(Tn, p); gam = 1 + LV ** 2 * qs / (CP * RV * Tn ** 2); cond = jnp.maximum(qn - qs, 0) / gam / dt
        src = cond * mass + jnp.where(reg & ok, -dqc * mass, 0.0) * 0.0                              # large-scale rain source per layer
        rh = jnp.clip(qn / qs, 0, 1)
        af = jnp.where(S['ev_frac'] > 0, S['ev_frac'], 1.0)
        def fall(P, x):
            # ev_frac > 0: precipitation-area fraction (ECMWF; default 0.3 since 27 Oct: exam z500 tropics d5 34.4 -> 28.0, TN rain kept,
            # genesis 26%, tracks within noise, Bay day-5 shear error 7.1 -> 4.1 m/s): rain covers only a share a of the box, so the local rain rate is
            # P / a and the box-mean evaporation is a k (1 - RH) sqrt(P / a) = k (1 - RH) sqrt(a P); off (a = 1) by default
            s_, rh_, m_ = x; P = P + s_; e_ = jnp.minimum(S['k_evap'] * (1 - rh_) * jnp.sqrt(jnp.maximum(P, 0) * af) * m_, P); return P - e_, e_
        Pconv_src = jnp.where(reg & ok, -dqc * mass, 0.0) / jnp.maximum(Pq, 1e-12) * Pc                # where convective rain forms
        if S['conv'] == 'mf': Pconv_src = Pmf
        Psurf, ev = jax.lax.scan(fall, jnp.zeros_like(ps), (src + Pconv_src, rh, mass))
        evap = ev / mass
        dq = dq - cond + evap; dT = dT + LV / CP * (cond - evap)
        # ---------------- radiation
        Tn = T + dt * dT; qn = jnp.maximum(q + dt * dq, 0)
        doy0 = cr['doy0'] if 'doy0' in cr else self.doy0; utc0 = cr['utc0'] if 'utc0' in cr else self.utc0   # start date as data: no recompile per start
        t_h = cr['t'] / 3600.0; doy = doy0 + t_h / 24.0; decl = math.radians(23.44) * jnp.sin(2 * jnp.pi * (doy - 81) / 365.0)
        hour = (utc0 + t_h) % 24.0; ha = jnp.radians(15.0 * (hour - 12.0) + jnp.asarray(self.LO))
        latr = jnp.radians(jnp.asarray(self.LA)); mu0 = jnp.maximum(jnp.sin(latr) * jnp.sin(decl) + jnp.cos(latr) * jnp.cos(decl) * jnp.cos(ha), 0.0)
        if S['rad'] == 'radcloud':
            # radcloud.py: diagnostic clouds (Sundqvist large-scale, Slingo convective + anvil, max-random overlap),
            # 17-term long-wave, 7-term delta-Eddington short-wave
            ecc = 1.0 + 0.0334 * jnp.cos(2 * jnp.pi * (doy - 3.0) / 365.0)                          # Earth-Sun distance factor
            def fresh():
                ent_on = bool(self.S.get('ent_top', 0))                                              # D2 needs the cloud part of the LW heating
                rprm = dict(dict(alb_land=S['alb_land']), **(self.S.get('rad_prm') or {}))
                if self.S.get('cld_pdf', 0): rprm['pdf'] = 1.0                                       # D1: one sub-grid water PDF for cloud fraction and water
                Rr = radcloud.radiation(Tn, qn, p, dp, ps, Ts, sea, mu0, conv_mask=cm, conv_rain=Pconv_src.sum(0), conv_src=Pconv_src,
                                        ls_cond=cond, xp=jnp, s0=1361.0 * ecc, prm=rprm, clear_sky=ent_on)
                o = {k: Rr[k] for k in RADKEYS}
                if ent_on: o.update(lw_cld=Rr['lw_heating'] - Rr['lw_heating_clr'], cloud=Rr['cloud'])
                return o
            if S['rad_every'] <= 1: Rr = fresh()                                                     # every call
            elif rad_fresh:                                                                          # surface(): once per step, every rad_every steps
                nstep = jnp.round(cr['t'] / dt).astype(jnp.int32)
                Rr = jax.lax.cond(nstep % int(S['rad_every']) == 0, fresh, lambda: cr['rad'])
            else: Rr = cr['rad']                                                                     # inside the dynamics step: the cache
            rad = jnp.where(sig > S['rad_top'], Rr['heating'], -(Tn - cr['T0']) / S['tau_strat'])   # rad_top: computed radiation above this sigma only (default 0.12 = stratosphere held near its start)
            sw_sfc, lw_dn = Rr['sw_net_sfc'], Rr['lw_dn_sfc']
        else:                                                                                        # old gray scheme, unchanged
            rhn = jnp.clip(qn / qsat(Tn, p), 0, 1); Rr = None
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
            S0 = 1361.0 * mu0; ccol = 1 - jnp.prod(1 - 0.6 * cld, axis=0); alb = 0.45 * ccol
            absw = 1 - jnp.exp(-S['k_sw'] * qn * mass / jnp.maximum(mu0, 0.05))
            def sw(Fd, x):
                a_ = x; ab = Fd * a_; return Fd - ab, ab
            Fsfc, swab = jax.lax.scan(sw, S0 * (1 - alb), absw)
            swh = swab * G / (CP * dp)
            rad = jnp.where(sig > 0.12, lw + swh, -(Tn - cr['T0']) / S['tau_strat'])
            sw_sfc = Fsfc * (1 - jnp.where(sea, S['alb_sea'], S['alb_land'])); lw_dn = Dbot[-1]
        dT = dT + rad; h_ent = None
        if self.S.get('ent_top', 0) and Rr is not None and 'lw_cld' in Rr:
            # D2 cloud-top entrainment (cloudtop.py): rho w_e cp dtheta = A x cloud-top LW cooling; exchanges s and q with the layer above
            dTe, dqe, _ = cloudtop.cloud_top_entrainment(Tn, qn, p, ps, zc, mass, Rr['lw_cld'], Rr['cloud'], float(self.S['ent_top']), dt, jnp, no_deep=~ok)
            dT = dT + dTe; dq = dq + dqe; h_ent = dTe
        dq = dq + jnp.maximum(-q, 0) / dt                                                            # keep humidity non-negative
        # ---------------- sub-grid orography: low-level blocking + gravity-wave drag (Lott & Miller 1997 / IFS style; off unless gwd > 0)
        if self.S.get('gwd', 0) and getattr(self, 'gw', None) is not None:
            dug, dvg = gwd_tend(self.gw, u, v, T, p, zc, ps, dsig, dt, float(self.S.get('gwd', 1.0)), float(self.S.get('gwd_blk', 1.0)))
            du = du + dug; dv = dv + dvg
        # ---------------- top sponge
        # sp_quad > 0: deeper sponge (as NCEP/ECMWF): damping grows quadratically from sp_top up to the model top, so
        # upward-moving waves are absorbed over several layers instead of reflecting off a thin lid (old: constant above 0.05)
        # sp_quad >= 2: confined sin^2 sponge (as ECMWF/GFS): zero below sp_top (e.g. 0.03 = 30 hPa), rising smoothly to
        # 1/sponge at sigma 0.004 (~4 hPa) and above; winds only, no temperature relaxation
        rmp = jnp.clip((S['sp_top'] - sig) / jnp.maximum(S['sp_top'] - 0.004, 1e-4), 0.0, 1.0)
        spg = jnp.where(S['sp_quad'] >= 2, jnp.sin(0.5 * jnp.pi * rmp) ** 2 / S['sponge'],
                        jnp.where(S['sp_quad'] > 0, jnp.clip((S['sp_top'] - sig) / S['sp_top'], 0.0, 1.0) ** 2 / S['sponge'],
                        jnp.where(sig < 0.05, 1.0 / S['sponge'], 0.0))); du = du - spg * u; dv = dv - spg * v
        # ---------------- SPPT-like noise on the physics (not radiation)
        if self.sppt_on:
            lonr = jnp.radians(jnp.asarray(self.LO, jnp.float32)); latr2 = jnp.radians(jnp.asarray(self.LA, jnp.float32))
            pat = sum(jnp.sin(S['kx'][i] * lonr + S['ky'][i] * latr2 + S['ph'][i] + S['om'][i] * cr['t']) for i in range(NWAVE)) / math.sqrt(NWAVE / 2)
            taper = jnp.clip((sig - 0.1) / 0.15, 0, 1) * jnp.clip((0.97 - sig) / 0.1, 0, 1)            # off near the ground and in the stratosphere (as ECMWF's SPPT)
            fac = 1 + jnp.clip(S['sppt'] * pat, -0.5, 0.5) * taper
            # noise on convection, condensation and rain only: scaling the implicit boundary-layer mixing past 1 overshoots
            # and blows the run up (seen in 1 of 3 test runs)
            dT = dTbl + (dT - rad - dTbl) * fac + rad; dq = dqbl + (dq - dqbl) * fac
        diag = dict(rain=Psurf + Pc * 0.0, H=H, E=E, ust=ust, V1=V1, sw_sfc=sw_sfc, lw_dn=lw_dn, Ts=Ts)
        if S['conv'] == 'mf': diag.update(on_dp=on_dp, on_sh=on_sh, on_bmjsh=(shallow & ~okmf).astype(jnp.float32))   # share of columns: deep plume / shallow plume / old shallow test
        diag.update(h_bl=dTbl, h_deep=dTc, h_shal=dTs, h_lsc=LV / CP * cond, h_evap=-LV / CP * evap)        # heating by process (K/s), for budget diagnostics
        if Rr is not None: diag['rad'] = Rr
        if h_ent is not None: diag['h_ent'] = h_ent
        return dict(T=dT, q=dq, u=du, v=dv), diag
    # ------------------------------------------------------------------------------------------------ dynamics + time loop
    def build(self, when_utc, split=False):
        """when_utc: datetime of the start (sun position)."""
        self.doy0 = float(when_utc.timetuple().tm_yday); self.utc0 = float(when_utc.hour); hor = self.coords.horizontal; M = self
        same = (getattr(self, '_built', None) is not None and self._built[0] == split and np.array_equal(self._built[1], np.asarray(self.oro))
                and np.array_equal(self._built[2], np.asarray(self.zs)) and np.array_equal(self._built[3], np.asarray(self.land)))
        self.built_for = when_utc
        if same: return                                                                             # same grid, terrain and coast: reuse the compiled model
        self._jit = {}; self._built = (split, np.asarray(self.oro), np.asarray(self.zs), np.asarray(self.land))
        self.eq = primitive_equations.SemiLagrangianPrimitiveEquations(self.ref_t, self.oro, self.coords, self.ps, humidity_key='specific_humidity',
                                                                       monotone_tracers=True, nodal_tracers=('specific_humidity',), departure_iterations=1, monotone_dynamics=bool(self.S.get('mono', True)))
        cl = hor.cos_lat
        class Phys(time_integration.ExplicitODE):
            def explicit_terms(self_, state):
                aux = primitive_equations.compute_diagnostic_state_sigma(state.replace(tracers={}), M.coords)
                T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; q = state.tracers['specific_humidity']
                u = aux.cos_lat_u[0] / cl / M.MPS; v = aux.cos_lat_u[1] / cl / M.MPS
                ps = jnp.exp(hor.to_nodal(state.log_surface_pressure))[0] / M.PA
                tend, _ = M.column(T, q, u, v, ps, M._carry, div=hor.to_nodal(state.divergence) * M.SEC)
                if M.S.get('phys_off'): tend = jax.tree_util.tree_map(jnp.zeros_like, tend)        # dynamics only (energy checks)
                vt = hor.to_modal(jax.tree_util.tree_map(lambda x: x * M.MPS / M.SEC / cl, (tend['u'], tend['v'])))
                return primitive_equations.State(vorticity=hor.curl_cos_lat(vt), divergence=hor.div_cos_lat(vt),
                                                 temperature_variation=hor.to_modal(tend['T'] * M.K / M.SEC), log_surface_pressure=jnp.zeros_like(state.log_surface_pressure),
                                                 tracers={'specific_humidity': tend['q'] / M.SEC}, sim_time=None if state.sim_time is None else 0.0)
        self.phys = Phys()
        res = hor.latitude_nodes / 128; tau = self.ps.nondimensionalize(8.6 / (2.4 ** np.log2(res)) * float(self.S.get('diff_x', 1.0)) * units.hours)   # diff_x: e-folding time multiplier (larger = weaker damping of the smallest scales)
        self.filt = primitive_equations.step_filter_excluding_nodal_tracers(time_integration.horizontal_diffusion_step_filter(hor, dt=self.dt, tau=tau, order=int(self.S.get('diff_order', 2))), nodal_tracers=('specific_humidity',))
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
        _, d = self.column(T, q, u, v, ps, cr, rad_fresh=True, div=hor.to_nodal(state.divergence) * self.SEC); dt = self.dt_s; sea = (~self.land) & (cr['sst'] > 0)
        # mixed layer: strong winds stir up cooler water (about ent K/day at 25 m/s), recovering slowly toward the start
        if 'ocean' in cr:                                                                           # ocean column: heat, wind stirring, cold wake
            p1 = self.sig[-1] * ps; rho1 = p1 / (RD * T[-1] * (1 + 0.61 * q[-1]))
            kt = rho1 * d['ust'] ** 2 / d['V1']                                                     # stress on the sea = rho cd V1 (u1, v1)
            Qns = d['lw_dn'] - SB * cr['sst'] ** 4 - d['H'] - LV * d['E']
            ocn, sst_o = ocean_step(cr['ocean'], Qns, d['sw_sfc'], kt * u[-1], kt * v[-1], self.fcor, dt, mask=sea, fw=d['E'] - d['rain'], xp=jnp)
            sst = jnp.where(sea, sst_o, cr['sst'])
            if self.S.get('ocean3d'):                                                               # stage 2: currents, upwelling, thermocline waves
                tx, ty = kt * u[-1], kt * v[-1]; q_ = None
                if self.S['ocean3d'] == 'rgo':
                    rg = orgo.step(cr['rgo'], tx, ty, self.rgg, dt, xp=jnp)
                    q_ = orgo.column_transports(rg, self.rgg, self.ocg, tx, ty, self.fcor, xp=jnp)
                ocn = ocur.step(ocn, tx, ty, self.fcor, self.ocg, dt, xp=jnp, q=q_)
                sst = jnp.where(sea, ocn['T'][0], cr['sst'])
        else:                                                                                       # old slab
            cool = -S['ent'] / 86400.0 * jnp.maximum(d['V1'] - 10.0, 0) ** 2 / 225.0 * (40.0 / S['h_ml'])
            warm = (cr['sst0'] - cr['sst']) / (5 * 86400.0)
            sst = jnp.where(sea, jnp.maximum(cr['sst'] + dt * (cool + warm), cr['sst0'] - 5.0), cr['sst'])
        net = d['sw_sfc'] + d['lw_dn'] - SB * cr['tl'] ** 4 - d['H'] - LV * d['E']
        tl = jnp.where(self.land, jnp.clip(cr['tl'] + dt * net / S['cap_land'], 230.0, 330.0), cr['tl'])
        w = jnp.where(self.land, jnp.clip(cr['w'] + dt * (d['rain'] - d['E']), 0.0, S['bucket'] * 1000), cr['w'])
        out = dict(cr, sst=sst, tl=tl, w=w, rain=cr['rain'] + dt * d['rain'], t=cr['t'] + dt)
        if 'ocean' in cr: out['ocean'] = ocn
        if 'rgo' in cr: out['rgo'] = rg
        if 'rad' in cr: out['rad'] = d['rad']
        return out
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
            phi = primitive_equations.get_geopotential_on_sigma(T * (1 + 0.608 * state.tracers['specific_humidity']) * self.K, nodal_orography=zs_n[None] * self.M, sigma=self.coords.vertical,   # virtual temperature: moist air is lighter (~50 m at 500 hPa in the tropics)
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
        carry = dict(carry, doy0=jnp.float32(self.doy0), utc0=jnp.float32(self.utc0))
        (sN, cN), traj = f(state, carry); first = fpost(state, carry)
        return {k: np.concatenate([np.asarray(first[k])[None], np.asarray(v)], 0) for k, v in traj.items()}
    def run_wx(self, state, carry, hours, every_h=24):
        """General-weather output for verification against ERA5 (whole globe, on the model grid [lon, lat]):
        z500 (m), t850 (K), mslp (Pa), rain total since start (mm), t2 (K, lowest level brought down to 2 m with 6.5 K/km),
        u850/v850 and u200/v200 (m/s), every every_h hours from 0."""
        hor = self.coords.horizontal; zs_n = jnp.asarray(self.zs)
        def to_p(F, lp, P):                                                                        # linear in log pressure; below ground -> lowest level
            lt = jnp.log(P); idx = jnp.sum(lp < lt, axis=0); k1 = jnp.clip(idx, 1, F.shape[0] - 1); k0 = k1 - 1
            g = lambda X, k: jnp.take_along_axis(X, k[None], 0)[0]
            w = jnp.clip((lt - g(lp, k0)) / (g(lp, k1) - g(lp, k0)), 0.0, 1.0); return g(F, k0) + w * (g(F, k1) - g(F, k0))
        def t_below(T, lp, P, v):                                                                  # below ground: ECMWF/ERA5 style, 6.5 K/km from the lowest level
            return jnp.where(jnp.log(P) > lp[-1], T[-1] * (P / jnp.exp(lp[-1])) ** (RD * 0.0065 / G), v)
        def post(state, cr):
            u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, state.vorticity, state.divergence); u, v = u / self.MPS, v / self.MPS
            T = (hor.to_nodal(state.temperature_variation) + self.ref_t[:, None, None]) / self.K
            ps = jnp.exp(hor.to_nodal(state.log_surface_pressure))[0] / self.PA
            phi = primitive_equations.get_geopotential_on_sigma(T * (1 + 0.608 * state.tracers['specific_humidity']) * self.K, nodal_orography=zs_n[None] * self.M, sigma=self.coords.vertical,   # virtual temperature: moist air is lighter (~50 m at 500 hPa in the tropics)
                                                                gravity_acceleration=self.ps.gravity_acceleration, ideal_gas_constant=self.ps.ideal_gas_constant) / (self.M ** 2 / self.SEC ** 2)
            lp = jnp.log(jnp.asarray(self.sig)[:, None, None] * ps[None])
            # mean sea-level pressure the ECMWF way (IFS documentation): T* at the surface from the lowest level, warm and
            # cold limits so high warm plateaus (Tibet) do not give absurd values.
            a0 = 0.0065 * RD / G; Tst = T[-1] * (1 + a0 * (1.0 / float(self.sig[-1]) - 1)); T0 = Tst + 0.0065 * zs_n
            alpha = jnp.where((T0 > 290.5) & (Tst <= 290.5), RD * (290.5 - Tst) / jnp.maximum(G * zs_n, 1.0), 0.0065 * RD / G)
            alpha = jnp.where((T0 > 290.5) & (Tst > 290.5), 0.0, alpha); Tst = jnp.where((T0 > 290.5) & (Tst > 290.5), 0.5 * (290.5 + Tst), Tst)
            Tst = jnp.where(Tst < 255.0, 0.5 * (255.0 + Tst), Tst); x = G * zs_n / (RD * Tst)
            mslp = jnp.where(zs_n > 1.0, ps * jnp.exp(x * (1 - alpha * x / 2 + (alpha * x) ** 2 / 3)), ps)
            z1 = RD * T[-1] / G * jnp.log(1.0 / float(self.sig[-1]))                                # height of the lowest level above ground
            # 2-m temperature from the surface-layer (log) profile between the skin and the lowest level, as forecast centres do
            land = self.land; Tsk = jnp.where((~land) & (cr['sst'] > 0), cr['sst'], cr['tl']); z0 = jnp.where(land, 0.1, 2e-4)
            th1 = T[-1] + G / CP * z1; f = jnp.log(2.0 / z0) / jnp.log(jnp.maximum(z1, 3.0) / z0)
            t2 = Tsk + f * (th1 - Tsk) - G / CP * 2.0
            t850 = t_below(T, lp, 85000.0, to_p(T, lp, 85000.0))
            return dict(z500=to_p(phi, lp, 50000.0) / G, t850=t850, mslp=mslp, rain=cr['rain'], t2=t2, t2_old=T[-1] + 0.0065 * (z1 - 2.0),
                        u850=to_p(u, lp, 85000.0), v850=to_p(v, lp, 85000.0), u200=to_p(u, lp, 20000.0), v200=to_p(v, lp, 20000.0),
                        **(self._map_extras(state, T, u, v, ps, lp, phi, to_p) if self.S.get('map_out') else {}))
        inner = int(round(every_h * 3600 / self.dt_s)); outer = int(hours // every_h)
        def one(c, _):
            st, cr = c; self._carry = cr; st2 = self.step(st); cr2 = self.surface(st2, cr); return (st2, cr2), None
        def block(c, _):
            c, _ = jax.lax.scan(one, c, None, length=inner); return c, post(*c)
        key = ('wx', hours, every_h)
        if key not in self._jit: self._jit[key] = (jax.jit(lambda s, c: jax.lax.scan(block, (s, c), None, length=outer)), jax.jit(post))
        f, fpost = self._jit[key]
        carry = dict(carry, doy0=jnp.float32(self.doy0), utc0=jnp.float32(self.utc0))
        (sN, cN), traj = f(state, carry); first = fpost(state, carry)
        return {k: np.concatenate([np.asarray(first[k])[None], np.asarray(v)], 0) for k, v in traj.items()}
    def _map_extras(self, state, T, u, v, ps, lp, phi, to_p):
        """extra fields for the forecast maps (setting map_out=True): humidity, column water, 10 m wind, 850/700 heights."""
        q = state.tracers['specific_humidity']; rh = q / qsat(T, jnp.exp(lp))
        tcw = (q * jnp.asarray(self.dsig)[:, None, None]).sum(0) * ps / G
        return dict(rh850=to_p(rh, lp, 85000.0), rh700=to_p(rh, lp, 70000.0), rh500=to_p(rh, lp, 50000.0), tcw=tcw,
                    u10=u[-1] * 0.85, v10=v[-1] * 0.85, z850=to_p(phi, lp, 85000.0) / G, t500=to_p(T, lp, 50000.0),
                    u500=to_p(u, lp, 50000.0), v500=to_p(v, lp, 50000.0),
                    **({f'snd_{n}{P}': to_p(X, lp, P * 100.0) for P in SND_LEVS for n, X in (('t', T), ('q', q), ('u', u), ('v', v))} | {'snd_ps': ps}
                       if self.S.get('map_snd') else {}))
    # ------------------------------------------------------------------------------------------------ storm tracker (GFDL style)
    def track(self, out, la0, lo0, every_h=6, keep_h=0):
        subgrid = subgrid_peak
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
                if np.isfinite(m[j]): fixes.append(subgrid(F, j, LA, LO))
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

# ---------------------------------------------------------------------------------------------------- tracker helper
def subgrid_peak(F, j, LA, LO):
    """position of a field maximum to a fraction of a grid cell: least-squares quadratic surface over the 3x3 cells around
    the highest grid point; its vertex if it is a true maximum within one cell, else the grid point. (A centroid pulls the
    centre toward the grid point; on a 140-km grid that alone gave ~60 km error at the start.)"""
    i0, k0 = j; ni, nk = F.shape
    if not (0 < i0 < ni - 1 and 0 < k0 < nk - 1): return float(LA[j]), float(LO[j])
    cl = math.cos(math.radians(LA[j])); sub = F[i0 - 1:i0 + 2, k0 - 1:k0 + 2]
    x = (((LO[i0 - 1:i0 + 2, k0 - 1:k0 + 2] - LO[j] + 180) % 360) - 180) * cl; y = LA[i0 - 1:i0 + 2, k0 - 1:k0 + 2] - LA[j]   # degrees
    A = np.stack([np.ones(9), x.ravel(), y.ravel(), x.ravel() ** 2, x.ravel() * y.ravel(), y.ravel() ** 2], 1)
    try: c = np.linalg.lstsq(A, sub.ravel(), rcond=None)[0]
    except Exception: return float(LA[j]), float(LO[j])
    H = np.array([[2 * c[3], c[4]], [c[4], 2 * c[5]]])
    if np.linalg.det(H) <= 0 or H[0, 0] >= 0: return float(LA[j]), float(LO[j])
    vx, vy = np.linalg.solve(H, -c[1:3]); dx = abs(LO[i0 + 1, k0] - LO[j]) * cl or 1.0; dy = abs(LA[i0, k0 + 1] - LA[j]) or 1.0
    if abs(vx) > dx or abs(vy) > dy: return float(LA[j]), float(LO[j])
    return float(LA[j] + vy), float(LO[j] + vx / cl)
# ---------------------------------------------------------------------------------------------------- ensemble helpers
def integrate(M, state, carry, hours):
    """run without saving output; returns the final (state, carry)."""
    n = int(round(hours * 3600 / M.dt_s)); key = ('int', n)
    def one(c, _):
        st, cr = c; M._carry = cr; st2 = M.step(st); return (st2, M.surface(st2, cr)), None
    if key not in M._jit: M._jit[key] = jax.jit(lambda s, c: jax.lax.scan(one, (s, c), None, length=n)[0])
    return M._jit[key](state, dict(carry, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)))
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

# ---------------------------------------------------------------------------------------------------- every system, mergers
def track_all(M, out, box=(0.0, 25.0, 50.0, 100.0), every_h=6, vo_min=3.5, link_km=450.0, merge_km=800.0, min_len=3):
    """All low-level vortices in the Bay of Bengal and Arabian Sea (box: lat0, lat1, lon0, lon1), not just one.
    Each output time: centres = local maxima of smoothed 850-hPa vorticity >= vo_min (1e-5/s) over sea or near the coast,
    at least 500 km apart. Centres are linked into tracks (nearest within link_km of the expected position). When a
    track ends within merge_km of another live track, it is recorded as merged into it (the survivor). Returns tracks
    [{id, basin, pts: [(h, lat, lon, vo, pmin_hPa, wmax_kt)], merged_into, merged_at}] longest-lived first, and the
    dominant one (lowest pressure reached)."""
    LO, LA = np.meshgrid(M.blon, M.blat, indexing='ij'); inb = (LA >= box[0]) & (LA <= box[1]) & (LO >= box[2]) & (LO <= box[3])
    km = lambda a, b, c, d: math.hypot(a - c, ((b - d + 180) % 360 - 180) * math.cos(math.radians((a + c) / 2))) * 111.2
    tracks = []; live = []
    for i in range(out['vo850'].shape[0]):
        sgn = np.where(LA >= 0, 1.0, -1.0); F = ndi.uniform_filter(np.asarray(out['vo850'][i], float) * sgn * 1e5, 3)
        pk = (F == ndi.maximum_filter(F, size=5)) & (F >= vo_min) & inb
        cand = sorted([(F[j], float(LA[j]), float(LO[j])) for j in zip(*np.where(pk))], reverse=True); cent = []
        for c in cand:
            if all(km(c[1], c[2], x[1], x[2]) >= 500 for x in cent): cent.append(c)
        P = np.asarray(out['mslp'][i]) / 100; W = np.hypot(out['ul'][i], out['vl'][i]) * 0.85 / 0.5144
        def info(la, lo):
            d = np.hypot(LA - la, ((LO - lo + 180) % 360 - 180) * math.cos(math.radians(la))) * 111.2
            return float(P[d <= 200].min()), float(W[d <= 300].max())
        used = set(); nxt = []
        for tr in sorted(live, key=lambda t: -t['pts'][-1][3]):                                   # strongest tracks pick first
            h, la, lo = tr['pts'][-1][:3]
            if len(tr['pts']) > 1: la, lo = la + 0.75 * (la - tr['pts'][-2][1]), lo + 0.75 * (lo - tr['pts'][-2][2])
            best = min(((km(la, lo, c[1], c[2]), n) for n, c in enumerate(cent) if n not in used), default=None)
            if best and best[0] <= link_km:
                c = cent[best[1]]; used.add(best[1]); tr['pts'].append((i * every_h, round(c[1], 2), round(c[2], 2), round(c[0], 1)) + tuple(round(x, 1) for x in info(c[1], c[2]))); nxt.append(tr)
            else: tr['end'] = i * every_h
        for n, c in enumerate(cent):
            if n not in used:
                tr = dict(id=len(tracks), basin='Arabian Sea' if c[2] < 77.5 else 'Bay of Bengal', pts=[(i * every_h, round(c[1], 2), round(c[2], 2), round(c[0], 1)) + tuple(round(x, 1) for x in info(c[1], c[2]))])
                tracks.append(tr); nxt.append(tr)
        for tr in live:                                                                           # ended next to a survivor: merged
            if 'end' in tr and 'merged_into' not in tr:
                h, la, lo = tr['pts'][-1][:3]
                near = [(km(la, lo, o['pts'][-1][1], o['pts'][-1][2]), o['id']) for o in nxt]
                if near and min(near)[0] <= merge_km: tr['merged_into'] = min(near)[1]; tr['merged_at'] = i * every_h
        live = nxt
    tracks = [t for t in tracks if len(t['pts']) >= min_len]
    for t in tracks: t.pop('end', None); t['pmin'] = min(p[4] for p in t['pts'])
    dom = min(tracks, key=lambda t: t['pmin'])['id'] if tracks else None
    return dict(tracks=sorted(tracks, key=lambda t: -len(t['pts'])), dominant=dom)
