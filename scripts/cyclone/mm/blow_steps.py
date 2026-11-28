"""28 Nov: cldpkg runaway at 16.5N 42.2E - per model STEP: cloud tracer before the dynamics step, after it, after surface(), after cloud_apply.
python blow_steps.py GRID LIB   env H0 (default 92), NSTEP (default 15)"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); import mm2, landinit
B = json.load(open(os.path.join(HERE, '..', '..', '..', 'data', 'cyclone', 'kaggle_cfg', 'cand_cldpkg.json')))['variants'][0]['set']
Z = np.load(sys.argv[2]); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; TT = [str(t) for t in Z['times']]; KEY = '2020-08-23T00'; K = TT.index(KEY)
F = Z['f3'][K].astype(np.float32); f2 = Z['f2'][K]; f3 = {v: F[V3.index(v)] for v in V3}; t0 = dt.datetime.strptime(KEY, '%Y-%m-%dT%H')
M = mm2.Model(sys.argv[1], 32, 20.0, B); st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                                                         f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st); LA, LO = np.meshgrid(np.asarray(M.lat), np.asarray(M.lon)); sig = np.asarray(M.sig)
H0 = int(os.environ.get('H0', 92)); st, cr = mm2.integrate(M, st, cr, H0)
cr = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0))
step = jax_step = None
import jax
@jax.jit
def one(st, cr):
    M._carry = cr; st2 = M.step(st); cr2 = M.surface(st2, cr); st3, cr3 = M.cloud_apply(st2, cr2)
    return st2, cr2, st3, cr3
for n in range(int(os.environ.get('NSTEP', 15))):
    c0 = np.asarray(st.tracers['cloud_water']); i, j = np.unravel_index(np.argmax(c0.max(0)), c0.shape[1:]); k = int(np.argmax(c0[:, i, j]))
    st2, cr2, st3, cr3 = one(st, cr)
    g = lambda x: float(np.asarray(x)[k, i, j]) * 1000
    print(f"step {n} t={H0 + n * M.dt_s / 3600:.2f}h pt {LA[i, j]:.1f}N {LO[i, j]:.1f}E sig {sig[k]:.3f} | tracer before {g(st.tracers['cloud_water']):.2f} after dyn {g(st2.tracers['cloud_water']):.2f}"
          f" | carry cql_in {g(cr2['cql_in']):.2f} cql(phys out) {g(cr2['cql']):.2f} | after cloud_apply {g(st3.tracers['cloud_water']):.2f} | global max before {c0.max()*1000:.1f} after {float(np.asarray(st3.tracers['cloud_water']).max())*1000:.1f}", flush=True)
    st, cr = st3, cr3
