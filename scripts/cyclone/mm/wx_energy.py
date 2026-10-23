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
VARS = {'dyn_only': dict(phys_off=True), 'full': {}, 'full_split': dict(_split=True)}
if len(sys.argv) > 4: VARS = json.loads(sys.argv[4])                      # named settings to compare
BASE = dict(rad='radcloud', rad_every=2); res = {}
for vn, vs in VARS.items():
    SPLIT = bool(vs.pop('_split', False)); M = mm2.Model('T85', 32, None, dict(BASE, **vs)); hor = M.coords.horizontal; res[vn] = []
    for key in TT[:NS]:
        t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
        M.build(t0, split=SPLIT); st = M.dfi(st); LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); trop = np.abs(LA) < 20; row = []
        for h in range(0, 49, 6):
            if h: st, cr = mm2.integrate(M, st, cr, 6)
            T = np.asarray((hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K); ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA)
            m = np.asarray(M.dsig)[:, None, None] * ps[None]
            g = float((T * m * W).sum() / (m * W).sum()); tr = float((T * m * W * trop).sum() / (m * W * trop).sum())
            u, v = mm2.spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence); ke = float(((np.asarray(u) ** 2 + np.asarray(v) ** 2) / M.MPS ** 2 * 0.5 * m * W).sum() / (m * W).sum())
            u_, v_ = mm2.spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
            tend, dd = M.column(jnp.asarray(T), st.tracers['specific_humidity'], u_ / M.MPS, v_ / M.MPS, jnp.asarray(ps), dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
            phys = float((np.asarray(tend['T']) * m / 9.81 * 1004.6 * W).sum() / W.sum()); rainW = float((np.asarray(dd['rain']) * 2.5e6 * W).sum() / W.sum())
            row.append(dict(physW=round(phys, 1), rainW=round(rainW, 1), h=h, Tg=round(g, 3), Ttrop=round(tr, 3), ke=round(ke, 2), ps=round(float((ps * W).sum() / W.sum()), 1)))
        res[vn].append(dict(start=key, series=row)); json.dump(res, open(OUT, 'w'))
        dTW = (row[-1]['Tg'] - row[0]['Tg']) / (48 * 3600) * 1004.6 * float((m * W).sum() / W.sum()) / 9.81
        print(vn, key, 'realised heating W/m2', round(dTW, 1), 'physics computed W/m2 (mean of 6-hourly)', round(float(np.mean([x['physW'] for x in row])), 1), 'rain W/m2', round(float(np.mean([x['rainW'] for x in row])), 1), 'dT globe/trop over 48 h', round(row[-1]['Tg'] - row[0]['Tg'], 3), round(row[-1]['Ttrop'] - row[0]['Ttrop'], 3), 'KE', row[0]['ke'], '->', row[-1]['ke'], 'mean ps', row[0]['ps'], '->', row[-1]['ps'], flush=True)
json.dump(res, open(OUT, 'w'))
