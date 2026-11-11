"""Sigma vs hybrid vertical coordinate, real ERA5 start, dynamics only (12 Nov). Tests the hypothesis that the EXTRA Asian
jet loss (~3.5 m/s/day beyond Pacific/Atlantic) comes from MEGAM's pure sigma levels sloping over Tibet.
Three cores, same horizontal grid, step, diffusion, off-centering, monotone SL, 32 layers with the SAME reference pressures:
  sigma  : mm2's SemiLagrangianPrimitiveEquations on SigmaCoordinates (what MEGAM runs)
  hybA0  : SemiLagrangianPrimitiveEquationsHybrid with A = 0 (sigma levels in the hybrid core: isolates core-implementation effects)
  hybrid : SemiLagrangianPrimitiveEquationsHybrid, B = ((s - 0.1)/0.9)^1.3, A = (s - B) p0 (near-pressure levels above ~250 hPa)
Each start interpolated from ERA5 pressure levels to its own levels. Jet peak per sector vs ERA5 day 1 (TRUTH o_u200).
python hyb_jet.py LIB TRUTH STARTS   env GRID (T42), DT (20 min), CORES (comma list)"""
import sys, os, datetime as dt, numpy as np, jax, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, wxscore as WS
from dinosaur import primitive_equations, time_integration, coordinate_systems, hybrid_coordinates, spherical_harmonic, vertical_interpolation, scales
units = scales.units
Z = dict(np.load(sys.argv[1])); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(TR['days'])}
KS = [int(x) for x in sys.argv[3].split(',')]; GR = os.environ.get('GRID', 'T42'); DTM = float(os.environ.get('DT', 20))
CORES = os.environ.get('CORES', 'sigma,hybA0,hybrid').split(',')
lat = np.linspace(-90, 90, 121); lon = np.arange(240) * 1.5; band = (lat >= 20) & (lat <= 50)
SECTORS = {'Asia': (60, 140), 'Pacific': (150, 220), 'Atlantic': (280, 340)}
def jet(u, s):
    sec = (lon >= SECTORS[s][0]) & (lon <= SECTORS[s][1]); prof = u[:, sec].mean(1); return float(np.where(band, prof, -99).max())
M = mm2.Model(GR, 32, DTM, {'rd_si': 1.0}); hor = M.coords.horizontal; sb = M.sigb.astype(np.float64); P0 = 1013.25
Bb = np.clip((sb - 0.1) / 0.9, 0, 1) ** 1.3; Ab = (sb - Bb) * P0
HY = {'hybA0': hybrid_coordinates.HybridCoordinates(a_boundaries=np.zeros_like(sb), b_boundaries=sb),
      'hybrid': hybrid_coordinates.HybridCoordinates(a_boundaries=Ab, b_boundaries=Bb)}
interp = vertical_interpolation.vectorize_vertical_interpolation(vertical_interpolation._linear_interp_with_safe_extrap)
res = hor.latitude_nodes / 128; tau = M.ps.nondimensionalize(8.6 / (2.4 ** np.log2(res)) * units.hours)
nday = int(round(float(os.environ.get("HRS", 24)) * 3600.0 / M.dt_s))   # HRS: run length (h); ERA5 still day 1
def make(core):
    if core == 'sigma':
        coords = M.coords
        eq = primitive_equations.SemiLagrangianPrimitiveEquations(M.ref_t, M.oro, coords, M.ps, humidity_key='specific_humidity', monotone_tracers=True,
                                                                  nodal_tracers=('specific_humidity',), monotone_dynamics=True)
        pc = lambda ps: M.sig[:, None, None] * ps
    else:
        lev = HY[core]; coords = coordinate_systems.CoordinateSystem(hor, lev)
        eq = primitive_equations.SemiLagrangianPrimitiveEquationsHybrid(M.ref_t, M.oro, coords, M.ps, humidity_key='specific_humidity', monotone_tracers=True,
                                                                        nodal_tracers=('specific_humidity',), monotone_dynamics=True, interpolation_order='cubic')
        ac = 0.5 * (lev.a_boundaries[1:] + lev.a_boundaries[:-1]); bc = 0.5 * (lev.b_boundaries[1:] + lev.b_boundaries[:-1])
        pc = lambda ps: ac[:, None, None] + bc[:, None, None] * ps
    filt = primitive_equations.step_filter_excluding_nodal_tracers(time_integration.horizontal_diffusion_step_filter(hor, dt=M.dt, tau=tau, order=2), nodal_tracers=('specific_humidity',))
    step = time_integration.step_with_filters(time_integration.semi_lagrangian_crank_nicolson_rk2(eq, M.dt, off_centering=0.05, warm_start_corrector=True), [filt])
    run = jax.jit(lambda s: jax.lax.fori_loop(0, nday, lambda i, x: step(x), s))
    return coords, pc, run
def u200(state, pc):
    cu = spherical_harmonic.get_cos_lat_vector(state.vorticity, state.divergence, hor, clip=False)
    u = np.asarray(hor.to_nodal(cu[0])) / np.asarray(hor.cos_lat) / M.MPS
    ps = np.exp(np.asarray(hor.to_nodal(state.log_surface_pressure))[0]) / M.PA / 100.0
    p = np.asarray(pc(ps)); lp = np.log(p); t = np.log(200.0)
    k1 = np.clip((lp < t).sum(0), 1, len(p) - 1); k0 = k1 - 1; g = lambda X, k: np.take_along_axis(X, k[None], 0)[0]
    w = (t - g(lp, k0)) / (g(lp, k1) - g(lp, k0)); return WS.to_grid(g(u, k0) + w * (g(u, k1) - g(u, k0)), M.lon, M.lat)
CORE = {}
R = {}
for k in KS:
    t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st_s, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                      f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0)
    ps_mod = np.exp(np.asarray(hor.to_nodal(st_s.log_surface_pressure))[0]) / M.PA / 100.0         # hPa, already on model terrain
    N = lambda x: M.to_nodes(x, Z['lats'], Z['lons']); levs = np.asarray(Z['levs'], float)
    T3, Q3, U3, V3_ = [N(f3[v]) for v in ('temperature', 'specific_humidity', 'u_component_of_wind', 'v_component_of_wind')]
    j1 = DI[(t0 + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H')]; era = {s: jet(TR['o_u200'][j1], s) for s in SECTORS}
    for c in CORES:
        if c not in CORE: CORE[c] = make(c)          # needs M.oro from the first init (same terrain every start)
        coords, pc, run = CORE[c]
        if c == 'sigma': st = st_s
        else:
            want = jnp.asarray(pc(ps_mod)); f = {n: np.asarray(interp(want, levs, x)) for n, x in (('t', T3), ('q', np.maximum(Q3, 0)), ('u', U3), ('v', V3_))}
            vor, div = spherical_harmonic.uv_nodal_to_vor_div_modal(hor, f['u'] * M.MPS, f['v'] * M.MPS)
            st = primitive_equations.State(vorticity=vor, divergence=div, temperature_variation=hor.to_modal(f['t'] * M.K - M.ref_t[:, None, None]),
                                           log_surface_pressure=st_s.log_surface_pressure, tracers={'specific_humidity': jnp.asarray(f['q'], jnp.float32)})
        u0 = u200(st, pc); st1 = run(st); u1 = u200(st1, pc)
        r = {s: (jet(u0, s), jet(u1, s), era[s]) for s in SECTORS}
        R.setdefault(c, []).append(r); print(c, TT[k], {s: tuple(round(x, 1) for x in v) for s, v in r.items()}, 'finite', bool(np.isfinite(u1).all()), flush=True)
print('\nday-1 jet-peak error vs ERA5 (m/s), mean over starts; [start value on own levels -> day 1 | ERA5 day 1]')
for c, rs in R.items():
    print(f'  {c:7s} ' + '  '.join(f'{s} {np.mean([r[s][1] - r[s][2] for r in rs]):+.1f} [{np.mean([r[s][0] for r in rs]):.1f}->{np.mean([r[s][1] for r in rs]):.1f}|{np.mean([r[s][2] for r in rs]):.1f}]' for s in SECTORS))
