"""Step 1(c), 4 Nov: global water and energy budget over a 10-day run (is the excess rain a drift, and where does the water
come from?). Every 6 h: global means of rain (accumulated, mm/day), evaporation E, sensible heat H, OLR, total column water
(TCW), column dry+moist energy; daily: TCW change vs (E - P) -> water closure; all also for tropics (|lat| < 20) and
ocean/land separately.  python global_budget.py LIB_NPZ OUT_JSON 'START1,START2' SETTINGS_JSON"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
from dinosaur import spherical_harmonic
G, CP, LV = 9.80616, 1004.6, 2.5e6
LIB, OUT, STARTS, VS = sys.argv[1], sys.argv[2], sys.argv[3].split(','), json.loads(sys.argv[4])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
VS = dict(VS); NL = VS.pop('layers', 32); GR = VS.pop('grid', 'T170')
M = mm2.Model(GR, NL, None, dict({'rad': 'radcloud', 'rad_every': 2}, **VS)); res = {'settings': VS}
for key in STARTS:
    key = key if 'T' in key else key + 'T00'; k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H')
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; f2 = Z['f2'][k]
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / G,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); hor = M.coords.horizontal
    LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); land = np.asarray(M.land) > 0.5; trop = np.abs(LA) < 20
    dsig = np.asarray(M.dsig)[:, None, None]
    def gm(x, m=None): w = W if m is None else W * m; return float((np.asarray(x) * w).sum() / w.sum())
    rows = []; h = 0; rain_prev = np.asarray(cr['rain']).copy()
    while h <= 240:
        T = np.asarray((hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K); q = np.asarray(st.tracers['specific_humidity'])
        ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA); u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
        tn, d = M.column(jnp.asarray(T), jnp.asarray(q), u / M.MPS, v / M.MPS, jnp.asarray(ps), dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)),
                         rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
        mass = dsig * ps[None] / G; tcw = (q * mass).sum(0); cpT = (CP * T * mass).sum(0)
        rain_acc = np.asarray(cr['rain']); P6 = (rain_acc - rain_prev) / (6 * 3600) if h > 0 else np.asarray(d['rain']); rain_prev = rain_acc.copy()
        E = np.asarray(d['E']); H = np.asarray(d['H']); olr = np.asarray(d['rad']['olr']) if 'rad' in d else np.zeros_like(E)
        r = dict(h=h)
        for nm, m in (('glob', None), ('trop', trop), ('ocean', ~land), ('land', land)):
            r[nm] = dict(P_mmday=round(gm(P6, m) * 86400, 3), E_mmday=round(gm(E, m) * 86400, 3), H=round(gm(H, m), 2), OLR=round(gm(olr, m), 1),
                         tcw=round(gm(tcw, m), 3), cpT_MJ=round(gm(cpT, m) / 1e6, 4))
        rows.append(r); print(key, h, json.dumps(r['glob']), flush=True)
        if h == 240: break
        st, cr = mm2.integrate(M, st, cr, 6); h += 6
    res[key] = rows; json.dump(res, open(OUT, 'w'))
