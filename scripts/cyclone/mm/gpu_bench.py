"""Speed and memory benchmark of model v2 on whatever JAX finds (GPU/TPU on Kaggle, CPU elsewhere).
python gpu_bench.py LIBM_NPZ OUT_JSON [GRIDS] [HOURS] [STORM]
For each grid: one storm start, control run (compile + run) then a second member with other settings (run only, compiled
model reused). Records seconds, peak device memory, and the control track."""
import sys, os, json, time, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import jax, mm2, ourens as O
LIB, OUT = sys.argv[1], sys.argv[2]
GRIDS = (sys.argv[3] if len(sys.argv) > 3 else 'T85,T119,T170,T213').split(','); HRS = int(sys.argv[4]) if len(sys.argv) > 4 else 120
NAME = sys.argv[5] if len(sys.argv) > 5 else 'Hamoon'
dev = jax.devices(); info = dict(backend=jax.default_backend(), devices=[str(d) for d in dev], jax=jax.__version__); print(info, flush=True)
def mem():
    try: s = dev[0].memory_stats(); return dict(peak_gb=round(s.get('peak_bytes_in_use', 0) / 1e9, 2), limit_gb=round(s.get('bytes_limit', 0) / 1e9, 2))
    except Exception: return None
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
s = next(x for x in O.LIBL if x['name'] == NAME); g = O.gen_time(s); k = TT.index(g.strftime('%Y-%m-%dT%H')); P0 = O.path_of(s)
f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; res = dict(info=info, storm=NAME, t0=str(g), hours=HRS, real=[((p[0] - g).total_seconds() / 3600, p[1], p[2], p[3]) for p in P0], grids={})
for grid in GRIDS:
    r = {}
    try:
        t = time.time(); M = mm2.Model(grid, 32, 30.0 if grid in ('T85', 'T106', 'T119') else 20.0, dict(sppt_on=True))
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], storm=dict(lat=s['gen'][0], lon=s['gen'][1], vmax_kt=25.0))
        M.build(g); st = jax.block_until_ready(M.dfi(st)); r['setup_s'] = round(time.time() - t, 1)
        t = time.time(); out = M.run(st, cr, HRS); r['first_run_s'] = round(time.time() - t, 1)          # includes compiling
        r['finite'] = bool(np.isfinite(out['mslp']).all()); r['trk'] = M.track(out, s['gen'][0], s['gen'][1])[::2]
        t = time.time(); out2 = M.run(st, M.with_params(cr, dict(rh_deep=0.85, sppt=0.2, sppt_seed=7)), HRS); r['member_run_s'] = round(time.time() - t, 1)
        r['finite2'] = bool(np.isfinite(out2['mslp']).all()); r['mem'] = mem(); r['dt_min'] = M.dt_s / 60
        r['sec_per_day'] = round(r['member_run_s'] / (HRS / 24), 1)
    except Exception as e:
        import traceback; traceback.print_exc(); r['err'] = repr(e)[:400]; r['mem'] = mem()
    res['grids'][grid] = r; print(grid, {kk: v for kk, v in r.items() if kk != 'trk'}, flush=True)
    json.dump(res, open(OUT, 'w'), default=float)
