"""Genesis test (model v2): start 48 h before each past storm formed and ask whether the model makes the depression, where
and when. Several physics variants per storm share one compiled model (settings carried as numbers).
python genesis2.py LIBM48_NPZ CONFIG_JSON CHUNK NCHUNK OUT_JSON
CONFIG: {"tag", "script": "genesis2.py", "grid", "hours", "lead", "variants": {name: settings}, "nchunk"}
Per storm and variant: the strongest 850-hPa vortex within 500 km of the real formation point between lead-24 and lead+24 h
(distance, time, strength); its track from there (tracker run forward), for track errors after formation."""
import sys, os, json, time, math, datetime as dt, numpy as np
from scipy import ndimage as ndi
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, ourens as O
LIB, CFG, CH, NCH, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
C = json.load(open(CFG)); NCH = C.get('nchunk', NCH); LEAD = C.get('lead', 48); HRS = C.get('hours', 120)
VAR = C.get('variants') or {'ctl': {}}
STATIC = ("conv", "mf_cap")                                                                    # settings fixed at compile time
if CH >= NCH: json.dump([], open(OUT, 'w')); sys.exit(0)
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
def km(a, b, c, d): return math.hypot(a - c, ((b - d + 180) % 360 - 180) * math.cos(math.radians(a))) * 111.2
def at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds())
            return tuple(a[i] + f * (b[i] - a[i]) if a[i] is not None and b[i] is not None else (a[i] or b[i]) for i in (1, 2, 3))
    return None
storms = [s for s in O.LIBL if (not C.get('storms') or s['name'] in C['storms'])]; res = []; MODELS = {}
for i, s in enumerate(storms):
    if i % NCH != CH: continue
    g = O.gen_time(s); g = g.replace(hour=g.hour // 6 * 6); t0 = g - dt.timedelta(hours=LEAD); key = t0.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    k = TT.index(key); P0 = O.path_of(s); gp = tuple(s['gen'])
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; t = time.time(); runs = {}
    started = set()
    for vn, vs in VAR.items():
        try:
            tm = time.time(); stat = {kk: vs[kk] for kk in STATIC if kk in vs}; dyn = {kk: v for kk, v in vs.items() if kk not in STATIC}
            key_s = json.dumps(stat, sort_keys=True)
            if key_s not in MODELS: MODELS[key_s] = [mm2.Model(C.get('grid', 'T85'), 32, None, dict(sppt_on=False, **stat)), None, None]   # compiled once per job
            if key_s not in started:                                                               # this storm's start state for this scheme
                M = MODELS[key_s][0]; started.add(key_s)
                st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                                Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], ocean=C.get('ocean'), when=t0)
                M.build(t0); st = M.dfi(st); MODELS[key_s][1:] = [st, cr]
            M, st, cr = MODELS[key_s]; out = M.run(st, M.with_params(cr, dyn), HRS)
            if not np.isfinite(out['mslp']).all(): raise RuntimeError('blew up')
            LO, LA = np.meshgrid(M.blon, M.blat, indexing='ij'); sgn = 1 if gp[0] >= 0 else -1
            d = np.hypot(LA - gp[0], ((LO - gp[1] + 180) % 360 - 180) * math.cos(math.radians(gp[0]))) * 111.2
            best = None
            for j in range(max(0, (LEAD - 24) // 6), min(out['vo850'].shape[0], (LEAD + 24) // 6 + 1)):
                F = ndi.uniform_filter(np.asarray(out['vo850'][j], float), 3) * sgn * 1e5; m = np.where(d <= 500, F, -np.inf); q = np.unravel_index(np.argmax(m), m.shape)
                pm = float(np.asarray(out['mslp'][j])[np.hypot(LA - LA[q], (LO - LO[q]) * math.cos(math.radians(gp[0]))) * 111.2 <= 200].min()) / 100
                env = float(np.median(np.asarray(out['mslp'][j])[(d > 500) & (d <= 1000)])) / 100
                sc = m[q] + 2.0 * (env - pm)                                               # vorticity plus pressure depth
                if best is None or sc > best[0]: best = (sc, j, float(LA[q]), float(LO[q]), float(m[q]), round(env - pm, 1))
            _, j, la, lo, vo, dep = best
            trk = M.track({kk: v[j:] for kk, v in out.items()}, la, lo, keep_h=48)
            trk = [((j * 6) + tt[0] - LEAD,) + tuple(tt[1:]) for tt in trk]                 # hours after real formation
            runs[vn] = dict(t_form=j * 6 - LEAD, dist=round(km(la, lo, gp[0], gp[1])), vo=round(vo, 1), depth=dep, trk=trk, sec=round(time.time() - tm))
        except Exception as e:
            runs[vn] = dict(err=repr(e)[:300]); print(s['name'], vn, 'FAILED', repr(e)[:300], flush=True)
    res.append(dict(name=s['name'], season=s['season'], t0=key, gen=O.gen_time(s).strftime('%Y-%m-%dT%H'), gp=gp,
                    real=[((p[0] - O.gen_time(s)).total_seconds() / 3600, p[1], p[2], p[3]) for p in P0], runs=runs, sec=round(time.time() - t)))
    print(s['name'], s['season'], {vn: (r.get('dist'), r.get('vo'), r.get('depth')) for vn, r in runs.items()}, 'sec', round(time.time() - t), flush=True)
    json.dump(res, open(OUT, 'w'), default=float)
json.dump(res, open(OUT, 'w'), default=float)
