"""Ensemble version of the past-storm test (model v2): control + N perturbed members per storm, exactly as the live
ensemble builds them (bred vectors + physics settings + SPPT; no ECMWF analysis for past dates).
python hindens2.py LIBM_NPZ CONFIG_JSON CHUNK NCHUNK OUT_JSON      CONFIG: {"tag", "grid", "members", "hours", "bogus", "split", "storms", "nchunk", "from_year"}"""
import sys, os, json, time, math, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, ourens as O
from live2 import member
LIB, CFG, CH, NCH, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
C = json.load(open(CFG)); NCH = C.get('nchunk', NCH)
if CH >= NCH: json.dump([], open(OUT, 'w')); sys.exit(0)
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
def at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds())
            return tuple(a[i] + f * (b[i] - a[i]) if a[i] is not None and b[i] is not None else (a[i] or b[i]) for i in (1, 2, 3))
    return None
storms = [s for s in O.LIBL if (not C.get('storms') or s['name'] in C['storms']) and O.gen_time(s).year >= C.get('from_year', 0)]; res = []
for i, s in enumerate(storms):
    if i % NCH != CH: continue
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    k = TT.index(key); P0 = O.path_of(s); st0 = at(P0, g)
    if not st0: continue
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; mems = []; bv = None; t = time.time()
    if 'M' not in dir(): M = mm2.Model(C.get('grid', 'T85'), 32, 30.0, dict(sppt_on=True))   # compiled once per job, reused by every storm and member
    for m in range(0, C.get('members', 10) + 1):
        try:
            mb = member(m); tm = time.time()
            ins = C.get('bogus', False) or (C.get('bogus_mix', False) and m % 2 == 1)          # storm insertion in half the members: the start vortex is uncertain too
            storm = dict(lat=st0[0], lon=st0[1], vmax_kt=st0[2] or 25.0) if ins else None
            st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                            Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], storm=storm, ocean=C.get('ocean'), when=g)
            cr = M.with_params(cr, mb['set'])
            if m == 0: M.build(g, split=C.get('split', False))                                     # new start date (no recompile)
            st = M.dfi(st)
            if m:
                if bv is None: bv = mm2.bred_vectors(M, st, M.with_params(cr, {}), n=6, hours=12.0, seed=77, amp=1.0)
                rs = np.random.default_rng(3000 + m); st = mm2.add_perturbation(st, bv, rs.standard_normal(6) / math.sqrt(6))
            out = M.run(st, cr, C.get('hours', 120))
            if not np.isfinite(out['mslp']).all(): raise RuntimeError('blew up')
            mems.append(dict(member=m, trk=M.track(out, st0[0], st0[1]), sec=round(time.time() - tm)))
        except Exception as e:
            mems.append(dict(member=m, err=repr(e)[:300])); print(s['name'], m, 'FAILED', repr(e)[:300], flush=True)
    res.append(dict(name=s['name'], season=s['season'], t0=key, real=[((p[0] - g).total_seconds() / 3600, p[1], p[2], p[3]) for p in P0],
                    truth=O.segment(*s['lf']) if s['lf'] else 'no landfall', truth_lf=s['lf'], members=mems, sec=round(time.time() - t)))
    print(s['name'], s['season'], 'members ok', sum(1 for x in mems if 'trk' in x), 'sec', round(time.time() - t), flush=True)
    json.dump(res, open(OUT, 'w'), default=float)
json.dump(res, open(OUT, 'w'), default=float)
