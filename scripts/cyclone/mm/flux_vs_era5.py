"""Surface / TOA energy terms vs ERA5 (12 Nov; A + P1 initiator search). Model day-1 mean (hourly samples of the column diagnostics)
of sensible heat flux, latent heat flux, surface net LW, surface net SW, OLR and the boundary-layer height, against ERA5 daily means
(flux_truth_2020.npz, day 1). ERA5 sign convention (downward positive) is applied to the model.
python flux_vs_era5.py LIB FLUX_TRUTH GRID STARTS   env CANDS (json), DT"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
FT = dict(np.load(sys.argv[2])); FD = {str(d): i for i, d in enumerate(FT['days'])}
GR, KS = sys.argv[3], [int(x) for x in sys.argv[4].split(',')]
B2 = {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0}
CANDS = json.loads(os.environ.get('CANDS', 'null')) or {'base2': {}}
tla = np.linspace(-90, 90, 121); TLA = np.repeat(tla[:, None], 240, 1); TW = np.cos(np.radians(TLA))
SB = 5.670374e-8; LV = 2.501e6
for nm, ex in CANDS.items():
    M = mm2.Model(GR, 32, float(os.environ.get('DT', 20)), dict(B2, **ex)); hor = M.coords.horizontal; acc = {}
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); st, cr = mm2.integrate(M, st, cr, 24)          # day 1 = hours 24-48 (ERA5 day index 1)
        S = {}
        for h in range(24):
            st, cr = mm2.integrate(M, st, cr, 1)
            aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords); cl = hor.cos_lat
            T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; u = aux.cos_lat_u[0] / cl / M.MPS; v = aux.cos_lat_u[1] / cl / M.MPS
            q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
            crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
            _, d = M.column(T, q, u, v, ps, crx, want_diag=True, div=hor.to_nodal(st.divergence) * M.SEC)
            Ts = np.asarray(d['Ts'], float)
            f = dict(shf=-np.asarray(d['H'], float), lhf=-LV * np.asarray(d['E'], float), snsw=np.asarray(d['sw_sfc'], float),
                     snlw=np.asarray(d['lw_dn'], float) - SB * Ts ** 4, tnlw=-np.asarray(cr['rad']['olr'], float), blh=np.asarray(d['hbl'], float), tp24=np.asarray(d['rain'], float) * 86400.0)
            for a, b in f.items(): S[a] = S.get(a, 0) + b / 24
        i = FD[TT[k]]
        for a, X in S.items():
            Xg = WS.to_grid(X, M.lon, M.lat); Ob = FT.get('o_' + a)
            if Ob is None: continue
            Ob = Ob[i, 1].astype(float) * (1000.0 if a == 'tp24' else 1.0); land = WS.to_grid(np.asarray(M.land, float), M.lon, M.lat) > 0.5
            for reg, m in (('globe', np.ones_like(land)), ('ocean 40S-40N', (~land) & (np.abs(TLA) <= 40)), ('land', land)):
                ok = m & np.isfinite(Xg) & np.isfinite(Ob)
                g = lambda Y: float((Y * TW * ok).sum() / (TW * ok).sum())
                acc.setdefault((a, reg), []).append((g(Xg), g(Ob)))
        print(nm, TT[k], 'done', flush=True)
    print(f'\n{nm}: day-1 mean, model / ERA5 (W m-2, downward positive; blh m)')
    for (a, reg), v in sorted(acc.items()):
        m_, o_ = np.mean(v, 0); print(f'  {a:5s} {reg:14s} {m_:8.1f} / {o_:8.1f}   diff {m_ - o_:+7.1f}')
