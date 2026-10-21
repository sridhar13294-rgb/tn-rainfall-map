"""Past-storm test of model version 2 (mm2.py).  python hind2.py LIBM_NPZ CONFIG_JSON CHUNK NCHUNK OUT_JSON
CONFIG: {"tag", "grid", "dt_min", "hours", "storms": [names] or null, "nchunk", "variants": [{"name", "grid"?, "bogus"?, "dfi"?, "set"?}]}"""
import sys, os, json, time, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, ourens as O
LIB, CFG, CH, NCH, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
C = json.load(open(CFG)); NCH = C.get('nchunk', NCH)
if CH >= NCH: json.dump([], open(OUT, 'w')); sys.exit(0)
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
def at(P0, t, k=None):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds())
            return tuple(a[i] + f * (b[i] - a[i]) if a[i] is not None and b[i] is not None else (a[i] or b[i]) for i in (1, 2, 3))
    return None
storms = [s for s in O.LIBL if not C.get('storms') or s['name'] in C['storms']]; res = []
for i, s in enumerate(storms):
    if i % NCH != CH: continue
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    k = TT.index(key); P0 = O.path_of(s); st0 = at(P0, g)
    if not st0: continue
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    for var in (C.get('variants') or [dict(name='control')]):
        try:
            t = time.time(); M = mm2.Model(var.get('grid', C.get('grid', 'T170')), var.get('layers', 32), var.get('dt_min', C.get('dt_min', 30.0)), var.get('set'))
            storm = dict(lat=st0[0], lon=st0[1], vmax_kt=st0[2] or 25.0) if var.get('bogus', True) else None
            state, carry = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                                  Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], storm=storm)
            M.build(g, split=var.get('split', C.get('split', False))); print('built', round(time.time() - t), flush=True)
            if var.get('dfi', True): state = M.dfi(state); print('dfi done', round(time.time() - t), flush=True)
            out = M.run(state, carry, C.get('hours', 120))
            if not np.isfinite(out['mslp']).all(): raise RuntimeError('model blew up')
            trk = M.track(out, st0[0], st0[1])
            res.append(dict(name=s['name'], season=s['season'], var=var['name'], t0=key, real=[((p[0] - g).total_seconds() / 3600, p[1], p[2], p[3]) for p in P0],
                            truth=O.segment(*s['lf']) if s['lf'] else 'no landfall', truth_lf=s['lf'], trk=trk, sec=round(time.time() - t)))
            print(s['name'], s['season'], var['name'], 'sec', round(time.time() - t), trk[::4], flush=True)
        except Exception as e:
            import traceback; traceback.print_exc()
            res.append(dict(name=s['name'], season=s['season'], var=var['name'], err=repr(e)[:400])); print(s['name'], var['name'], 'FAILED', repr(e)[:400], flush=True)
json.dump(res, open(OUT, 'w'), default=float)
