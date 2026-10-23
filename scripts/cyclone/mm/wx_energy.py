"""Energy check: does the dynamical core lose heat? Mass-weighted mean temperature (globe, tropics 20S-20N) every 6 h
for 48 h from exam starts, for: physics off (dynamics only), physics off with non-monotone semi-Lagrangian dynamics,
and the full model. With physics off the global mean temperature should stay almost constant (only kinetic<->heat
conversion, ~0.1 K/day); a drift of ~-1 K/day would be the missing heat.
python wx_energy.py LIBM_WX_NPZ OUT_JSON [N_STARTS]"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
LIB, OUT = sys.argv[1], sys.argv[2]; NS = int(sys.argv[3]) if len(sys.argv) > 3 else 2
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
VARS = {'dyn_only': dict(phys_off=True), 'dyn_only_nonmono': dict(phys_off=True, mono=False), 'full': {}, 'full_nonmono': dict(mono=False)}
BASE = dict(rad='radcloud', rad_every=2); res = {}
for vn, vs in VARS.items():
    M = mm2.Model('T85', 32, None, dict(BASE, **vs)); hor = M.coords.horizontal; res[vn] = []
    for key in TT[:NS]:
        t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
        M.build(t0); st = M.dfi(st); LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); trop = np.abs(LA) < 20; row = []
        for h in range(0, 49, 6):
            if h: st, cr = mm2.integrate(M, st, cr, 6)
            T = np.asarray((hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K); ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA)
            m = np.asarray(M.dsig)[:, None, None] * ps[None]
            g = float((T * m * W).sum() / (m * W).sum()); tr = float((T * m * W * trop).sum() / (m * W * trop).sum())
            u, v = mm2.spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence); ke = float(((np.asarray(u) ** 2 + np.asarray(v) ** 2) / M.MPS ** 2 * 0.5 * m * W).sum() / (m * W).sum())
            row.append(dict(h=h, Tg=round(g, 3), Ttrop=round(tr, 3), ke=round(ke, 2), ps=round(float((ps * W).sum() / W.sum()), 1)))
        res[vn].append(dict(start=key, series=row)); json.dump(res, open(OUT, 'w'))
        print(vn, key, 'dT globe/trop over 48 h', round(row[-1]['Tg'] - row[0]['Tg'], 3), round(row[-1]['Ttrop'] - row[0]['Ttrop'], 3), 'KE', row[0]['ke'], '->', row[-1]['ke'], 'mean ps', row[0]['ps'], '->', row[-1]['ps'], flush=True)
json.dump(res, open(OUT, 'w'))
