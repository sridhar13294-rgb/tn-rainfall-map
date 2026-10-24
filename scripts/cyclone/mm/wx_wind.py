"""Storm steering check: is the model's large-scale wind wrong where our storms move? Mean model-minus-ERA5 u and v at
850/700/500/300/200 hPa and the 850-200 hPa deep-layer mean (what steers a storm), over the Bay, Arabian Sea and South
Indian Ocean, at the start (after DFI) and after 5 days (exam starts are 5 days apart).
python wx_wind.py LIBM_WX_NPZ OUT_JSON [N_STARTS] [SETTINGS_JSON]"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
from dinosaur import spherical_harmonic
LIB, OUT = sys.argv[1], sys.argv[2]; NS = int(sys.argv[3]) if len(sys.argv) > 3 else 20
VARS = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {'ctl': {}}
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
LEV = np.asarray(Z['levs'], float); la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
LAg, LOg = np.meshgrid(la, lo, indexing='ij'); Wg = np.cos(np.radians(LAg))
REG = {'bay': lambda A, O: (A >= 5) & (A <= 25) & (O >= 80) & (O <= 100), 'arabian': lambda A, O: (A >= 5) & (A <= 25) & (O >= 50) & (O <= 78),
       'south_io': lambda A, O: (A >= -25) & (A <= -5) & (O >= 50) & (O <= 100)}
PL = [850, 700, 500, 300, 200]; PI = [int(np.argmin(np.abs(LEV - p))) for p in PL]
def era(k, v, reg):
    m = REG[reg](LAg, LOg); a = Z['f3'][k, V3.index(v)]; return [float((a[i] * Wg * m).sum() / (Wg * m).sum()) for i in PI]
def deep(x): return float(np.mean(x))                                                            # equal weight 850..200 (5 levels)
ALL = {}
for VN, VS in VARS.items():
    M = mm2.Model('T85', 32, None, dict(VS)); res = []
    def model(st):
        hor = M.coords.horizontal; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
        u = np.asarray(u / M.MPS); v = np.asarray(v / M.MPS)
        ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA); lp = np.log(np.asarray(M.sig)[:, None, None] * ps[None])
        LA, LO = np.asarray(M.LA), np.asarray(M.LO); W = np.cos(np.radians(LA)); o = {}
        g = lambda A, k: np.take_along_axis(A, k[None], 0)[0]
        for reg, f in REG.items():
            m = f(LA, LO); r = {}
            for name, X in (('u', u), ('v', v)):
                vals = []
                for P in np.asarray(PL) * 100.0:
                    x = np.log(P); k1 = np.clip((lp < x).sum(0), 1, len(M.sig) - 1); k0 = k1 - 1
                    w = np.clip((x - g(lp, k0)) / (g(lp, k1) - g(lp, k0)), 0, 1); val = g(X, k0) + w * (g(X, k1) - g(X, k0))
                    ok = m & (P < ps); vals.append(float((val * W * ok).sum() / max((W * ok).sum(), 1e-9)))
                r[name] = vals
            o[reg] = r
        return o
    for key in TT[:NS]:
        t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        k5s = (t0 + dt.timedelta(days=5)).strftime('%Y-%m-%dT%H')
        if k5s not in TT: continue
        k5 = TT.index(k5s)
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
        M.build(t0); st = M.dfi(st); r = dict(start=key)
        for lab, s_, kk in (('h0', st, k), ('d5', mm2.integrate(M, st, cr, 120)[0], k5)):
            mo = model(s_); r[lab] = {}
            for reg in REG:
                du = [a - b for a, b in zip(mo[reg]['u'], era(kk, 'u_component_of_wind', reg))]; dv = [a - b for a, b in zip(mo[reg]['v'], era(kk, 'v_component_of_wind', reg))]
                r[lab][reg] = dict(du=[round(x, 2) for x in du], dv=[round(x, 2) for x in dv], deep_du=round(deep(du), 2), deep_dv=round(deep(dv), 2),
                                   era_deep_u=round(deep(era(kk, 'u_component_of_wind', reg)), 2))
        res.append(r); ALL[VN] = res; json.dump(ALL, open(OUT, 'w'))
        print(VN, key, {reg: (r['d5'][reg]['deep_du'], r['d5'][reg]['deep_dv']) for reg in REG}, flush=True)
    for reg in REG:
        for lab in ('h0', 'd5'):
            du = np.mean([x[lab][reg]['du'] for x in res], 0); dv = np.mean([x[lab][reg]['dv'] for x in res], 0)
            print(VN, reg, lab, 'mean du m/s', dict(zip(PL, du.round(2).tolist())), 'dv', dict(zip(PL, dv.round(2).tolist())), 'deep', round(float(du.mean()), 2), round(float(dv.mean()), 2), flush=True)
