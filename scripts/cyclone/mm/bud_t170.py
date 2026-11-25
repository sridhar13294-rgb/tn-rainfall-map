"""25 Nov (T170 rain decline / S.India 850 cooling): physics budget by process at sigma 0.925/0.85/0.7 over South India (8-18N, 74-84E,
wxscore 'india_south') and Bay/TN (5-20N, 75-95E), 3-hourly, days 1-3 of the Nov starts, plus dT. python bud_t170.py LIB 'SET' TAG OUT"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
from dinosaur import spherical_harmonic
LIB, TAG, OUT = sys.argv[1], sys.argv[3], sys.argv[4]
SET = dict(json.load(open(os.path.join(HERE, '..', '..', '..', 'data', 'cyclone', 'kaggle_cfg', 'suite_lcmix_wx.json')))['variants'][0]['set'], **json.loads(sys.argv[2]))
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
gla = np.linspace(-90, 90, 121); glo = np.arange(240) * 1.5; Wg = np.cos(np.radians(gla))[:, None] * np.ones((1, 240))
BOX = {'india_south': (gla[:, None] >= 8) & (gla[:, None] < 18) & (glo[None] >= 74) & (glo[None] <= 84), 'bay_tn': (gla[:, None] >= 5) & (gla[:, None] <= 20) & (glo[None] >= 75) & (glo[None] <= 95)}
KEYS = ('h_bl', 'h_shal', 'h_deep', 'h_lsc', 'h_evap', 'rad_app'); SIGS = (0.925, 0.85, 0.7); acc = {}
for KEY in os.environ.get('STARTS', '2020-11-01T00,2020-11-11T00,2020-11-16T00').split(','):
    M = mm2.Model(os.environ.get('GRID', 'T170'), 32, 20.0, SET); k = TT.index(KEY); t0 = dt.datetime.strptime(KEY, '%Y-%m-%dT%H')
    f2 = Z['f2'][k]; F = Z['f3'][k].astype(np.float32); f3 = {v: F[V3.index(v)] for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); hor = M.coords.horizontal; sig = np.asarray(M.sig); h0 = 0
    for h in range(0, 73, 3):
        if h: st, cr = mm2.integrate(M, st, cr, h - h0); h0 = h
        T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
        ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
        tn, d = M.column(T, q, u / M.MPS, v / M.MPS, ps, dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
        for sl in SIGS:
            i = int(np.argmin(np.abs(sig - sl)))
            fl = {'T': np.asarray(T[i]), 'phys': np.asarray(tn['T'][i]) * 86400, **{kk: np.asarray(d[kk][i]) * 86400 for kk in KEYS}}
            for b, m in BOX.items():
                for nm, X in fl.items():
                    Xg = WS.to_grid(X, M.lon, M.lat); acc.setdefault(f'{b}|{sl}|{nm}|{h}', []).append(float((np.where(m, Xg, 0) * Wg).sum() / (Wg * m).sum()))
    print(KEY, 'done', flush=True)
mean = {k_: float(np.mean(v_)) for k_, v_ in acc.items()}; json.dump(mean, open(OUT, 'w'))
for b in BOX:
    for sl in SIGS:
        for dday in (1, 2, 3):
            hs = list(range(3 * 8 * (dday - 1), 3 * 8 * dday + 1, 3))
            tr = lambda nm: float(np.trapezoid([mean[f'{b}|{sl}|{nm}|{h}'] for h in hs], dx=3 / 24))
            dT = mean[f'{b}|{sl}|T|{hs[-1]}'] - mean[f'{b}|{sl}|T|{hs[0]}']; ph = tr('phys')
            print('#', TAG, b, 'sigma', sl, 'day', dday, 'dT %+.2f = phys %+.2f + dyn %+.2f |' % (dT, ph, dT - ph), ' '.join('%s %+.2f' % (kk, tr(kk)) for kk in KEYS), flush=True)
