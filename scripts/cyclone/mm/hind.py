"""Past-storm test of the moist multi-level model.  python hind.py LIBM_NPZ CONFIG_JSON CHUNK NCHUNK OUT_JSON
CONFIG_JSON: {"tag", "grid", "dt_min", "hours", "moist", "dfi", "set": {...physics settings}, "storms": [names] or null,
"nchunk": n}. Each storm: the model starts from ERA5 at the real start time; its storm is followed every 6 h."""
import sys, os, json, time, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'analysis'))
import mm, ourens as O
LIB, CFG, CH, NCH, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
C = json.load(open(CFG)); NCH = C.get('nchunk', NCH)
if CH >= NCH: json.dump([], open(OUT, 'w')); sys.exit(0)
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
def real_at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
storms = [s for s in O.LIBL if not C.get('storms') or s['name'] in C['storms']]
M = mm.Model(C.get('grid', 'T85'), C.get('dt_min', 6.0), C.get('set')); res = []
for i, s in enumerate(storms):
    if i % NCH != CH: continue
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    k = TT.index(key); P0 = O.path_of(s); st0 = real_at(P0, g)
    if not st0: continue
    try:
        t = time.time()
        f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        state = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                       Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')])
        f, dfi = M.runner(C.get('hours', 120), moist=C.get('moist', True))           # rebuilt: sea temperature and terrain differ per storm
        if C.get('dfi', True): state = dfi(state)
        _, traj = f(state); traj = {k_: np.asarray(v) for k_, v in traj.items()}
        if not np.isfinite(traj['ps']).all(): raise RuntimeError('model blew up')
        trk = M.track(traj, *st0)
        res.append(dict(name=s['name'], season=s['season'], t0=key, real=[((p[0] - g).total_seconds() / 3600, p[1], p[2], p[3]) for p in P0],
                        truth=O.segment(*s['lf']) if s['lf'] else 'no landfall', truth_lf=s['lf'], trk=trk, sec=round(time.time() - t)))
        print(s['name'], s['season'], 'sec', round(time.time() - t), trk[::4], flush=True)
    except Exception as e:
        res.append(dict(name=s['name'], season=s['season'], err=repr(e)[:400])); print(s['name'], 'FAILED', repr(e)[:400], flush=True)
json.dump(res, open(OUT, 'w'), default=float)
