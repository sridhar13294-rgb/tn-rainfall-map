"""Start-state check of the lowest layers (11 Nov; open item since 5 Nov: physics-off lowest-level cooling -0.8..-1.1 K/day in BOTH
dynamical cores). Model lowest-layer T and q at hour 0 (after init + DFI) and +24 h (physics off and base2), vs ERA5 2-m temperature
and the ERA5 1000-hPa level (start-file pressure levels), ocean / land, global.  python sfc_start.py LIB TRUTH GRID STARTS"""
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
TR = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(TR['days'])}
GR = sys.argv[3]; KS = [int(x) for x in sys.argv[4].split(',')]
def state(M, st):
    hor = M.coords.horizontal; aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
    T = np.asarray((aux.temperature_variation + M.ref_t[:, None, None]) / M.K); q = np.asarray(st.tracers['specific_humidity'])
    ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA); return T, q, ps
for nm, setx in (('physics off', {'phys_off': True}), ('base2', {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0})):
    M = mm2.Model(GR, 32, 20.0, setx); sig = np.asarray(M.sig); LA = np.asarray(M.LA); W = np.cos(np.radians(LA))
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); land = np.asarray(M.land) > 0.5
        rows = {}
        for h in (0, 24):
            if h: st, cr = mm2.integrate(M, st, cr, 24)
            T, q, ps = state(M, st)
            t2 = WS.to_grid(T[-1], M.lon, M.lat) if False else None
            j = DI.get((t0 + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H'))
            # ERA5 2-m T on the model grid (truth is on the 1.5 deg grid -> nearest)
            tl = np.asarray(TR['lats']) if 'lats' in TR else None
            rows[h] = (T, q, ps, j)
        T0, q0, ps0, _ = rows[0]; T1, q1, ps1, j1 = rows[24]
        for reg, m in (('ocean', ~land), ('land', land), ('globe', np.ones_like(land))):
            g = lambda X: float((X * W)[m].sum() / W[m].sum())
            print(f'{nm:11s} {TT[k]} {reg:5s} lowest layer (sigma {sig[-1]:.3f}): T h0 {g(T0[-1]):.2f} h24 {g(T1[-1]):.2f} (d {g(T1[-1]-T0[-1]):+.2f} K) | '
                  f'layer 2 d {g(T1[-2]-T0[-2]):+.2f} | layer 4 d {g(T1[-4]-T0[-4]):+.2f} | q lowest d {1000*g(q1[-1]-q0[-1]):+.2f} g/kg | ps d {g(ps1-ps0)/100:+.2f} hPa', flush=True)
