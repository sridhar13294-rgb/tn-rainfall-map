"""28 Nov: cldpkg 23 Aug runaway - per-stage carried cloud water at the runaway point (29 N, 348 E), hourly h86-h100, T170.
python blow_terms.py GRID LIB"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import mm2, landinit
from dinosaur import spherical_harmonic
B = json.load(open(os.path.join(HERE, '..', '..', '..', 'data', 'cyclone', 'kaggle_cfg', 'cand_cldpkg.json')))['variants'][0]['set']; B['cld_dbg'] = 1
Z = np.load(sys.argv[2]); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; TT = [str(t) for t in Z['times']]; KEY = '2020-08-23T00'; K = TT.index(KEY)
F = Z['f3'][K].astype(np.float32); f2 = Z['f2'][K]; f3 = {v: F[V3.index(v)] for v in V3}; t0 = dt.datetime.strptime(KEY, '%Y-%m-%dT%H')
M = mm2.Model(sys.argv[1], 32, 20.0, B); st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                                                         f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st); hor = M.coords.horizontal; LA, LO = np.meshgrid(np.asarray(M.lat), np.asarray(M.lon)); sig = np.asarray(M.sig)
H0 = int(os.environ.get('H0', 86)); st, cr = mm2.integrate(M, st, cr, H0); h = H0
while h < int(os.environ.get('H1', 101)):
    T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
    ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
    M.column(T, q, u / M.MPS, v / M.MPS, ps, dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
    cql = np.asarray(cr['cql']); i, j = np.unravel_index(np.argmax(cql.max(0)), cql.shape[1:]); k = int(np.argmax(cql[:, i, j]))
    ct = {n: float(np.asarray(x)[k, i, j]) * 1000 for n, x in M._ct.items()}
    tr = {n: float(np.asarray(st.tracers[n])[k, i, j]) * 1000 for n in ('cloud_water',) if n in st.tracers}
    print(h, 'pt lat %.1f lon %.1f sig %.3f' % (LA[i, j], LO[i, j], sig[k]), 'carry cql %.2f' % (cql[k, i, j] * 1000), 'tracer', tr, 'q %.2f' % (float(np.asarray(q)[k, i, j]) * 1000),
          'stages g/kg', {n: round(x, 3) for n, x in ct.items()}, 'cfa %.2f' % float(np.asarray(cr['cfa'])[k, i, j]), flush=True)
    st, cr = mm2.integrate(M, st, cr, 1); h += 1
