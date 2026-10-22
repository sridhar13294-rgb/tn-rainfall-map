"""Model v2 checks (run on Kaggle GPU or any JAX machine).  python test_mm2.py LIBM_NPZ OUT_JSON [GRID]
1. Mass-flux convection on a real start state: energy and water budgets close (rain is the only water sink), how many
   tropical columns convect, cloud-base mass flux and rain rates.
2. 48-h runs with the old (bmj) and new (mf) convection: stable, tropical-mean rain (observed ~4-5 mm/day over 15S-15N oceans)."""
import sys, os, json, time, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import jax, jax.numpy as jnp, mm2, ourens as O
from dinosaur import primitive_equations
LIB, OUT = sys.argv[1], sys.argv[2]; GRID = sys.argv[3] if len(sys.argv) > 3 else 'T85'
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
s = next(x for x in O.LIBL if x['name'] == 'Hamoon'); g = O.gen_time(s); k = TT.index(g.strftime('%Y-%m-%dT%H'))
f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; res = {}
def setup(conv):
    M = mm2.Model(GRID, 32, None, dict(conv=conv))
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                    Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')])
    M.build(g); return M, M.dfi(st), cr
# ---- 1. budgets of the mass-flux scheme on the start state
M, st, cr = setup('mf'); hor = M.coords.horizontal; cl = hor.cos_lat
aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
sig = jnp.asarray(M.sig)[:, None, None]; dsig = jnp.asarray(M.dsig)[:, None, None]; sb = jnp.asarray(M.sigb)[:, None, None]
p = sig * ps; mass = dsig * ps / mm2.G
lnr = jnp.log(jnp.maximum(sb[1:], 1e-6) / jnp.maximum(sb[:-1], 1e-6)); lnr = lnr.at[0].set(jnp.log(sb[1, 0, 0] / jnp.maximum(sig[0, 0, 0], 1e-6)) * 2.0)
dz = mm2.RD * T * lnr / mm2.G; zi = jnp.cumsum(dz[::-1], axis=0)[::-1]; zc = zi - dz / 2
the_l = T * (100000.0 / p) ** mm2.KAP * jnp.exp(mm2.LV * q / (mm2.CP * T)); ksrc = jnp.argmax(jnp.where(sig >= 0.87, the_l, -1.0), axis=0)
S = dict(M.S); S.update(cr['prm'])
dT, dq, P, cm, deep = jax.jit(lambda *a: M.conv_mf(*a, S, M.dt_s))(T, q, p, mass, zc, sig, dsig, ps, ksrc)
E = np.asarray(((mm2.CP * dT + mm2.LV * dq) * mass).sum(0)); W = np.asarray((dq * mass).sum(0) + P.sum(0)); rain = np.asarray(P.sum(0)) * 86400
trop = np.abs(M.LA) <= 15; sea = ~np.asarray(M.land) & trop
res['budget'] = dict(energy_max_Wm2=float(np.abs(E).max()), heating_max_Wm2=float(np.abs(np.asarray((mm2.CP * dT * mass).sum(0))).max()), water_max_mmday=float(np.abs(W).max() * 86400),
                     deep_frac_tropics=float(np.asarray(deep)[trop].mean()), rain_tropsea_mean_mmday=float(rain[sea].mean()), rain_max_mmday=float(rain.max()),
                     dT_max_Kday=float(np.abs(np.asarray(dT)).max() * 86400), finite=bool(np.isfinite(np.asarray(dT)).all()))
print('budget', res['budget'], flush=True)
# ---- 2. 48-h runs
for conv in ('bmj', 'mf'):
    try:
        M, st, cr = setup(conv); t = time.time(); out = M.run(st, cr, 48, box=(0.0, 359.9, -15.0, 15.0))
        r = np.asarray(out['rain'][-1]); LO, LA = np.meshgrid(M.blon, M.blat, indexing='ij')
        res[conv] = dict(finite=bool(np.isfinite(out['mslp']).all()), rain_trop_mean_mmday=float(np.nanmean(r) / 2.0), rain_max_mm48h=float(np.nanmax(r)),
                         mslp_min=float(np.nanmin(out['mslp'][-1]) / 100), sec=round(time.time() - t))
    except Exception as e:
        import traceback; traceback.print_exc(); res[conv] = dict(err=repr(e)[:300])
    print(conv, res[conv], flush=True)
json.dump(res, open(OUT, 'w'), default=float)
