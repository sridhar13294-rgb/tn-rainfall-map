"""Score the storyline ensemble on the past storms: start at each storm's real genesis from its ERA5 winds (storm swirl
removed), run control + 50 storyline members, and score the coast stretch and landfall latitude against what happened.
Leave-one-out is not needed: nothing in the storylines is fitted to these storms (the track and strength models are)."""
import sys, os, json, math, datetime as dt, numpy as np
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S, live_env_s as ES, ours_live_s as L
RAW = S.lib_raw(sys.argv[1]); M = S.train(); rows = []
ORDER = O.ORDER
clim = Counter(O.segment(*s['lf']) if s['lf'] else 'no landfall' for s in O.LIBL)
for s in O.LIBL:
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in RAW: continue
    P0 = O.path_of(s); F = S.remove_vortex(RAW[key].astype(float), P0[0][1], P0[0][2])
    obs = dict(formed=True, sst=0.3, mjo_u=0.0, mjo_kt=0.0)
    PS = [dict(member=0, story='control', start_t=g, start_lat=P0[0][1], start_lon=P0[0][2], gen_t=g, gen_lat=None, gen_lon=None, mjo=0.0, mjo_kt=0.0, mjo_i=0, sst=0.3, shear_scale=1.0, beta=1.0, speed=1.0, start_v=17.0)]
    for st in L.STORIES:
        for j in range(1, st[2] + 1): PS.append(L.vary(st, j, st[2], g, (P0[0][1], P0[0][2]), obs))
    segs, lats = [], []
    for P in PS:
        pts, lf = S.run_track(M, ES.EnvS(F, O.LA, O.LO, g, P), P)
        segs.append(O.segment(lf['lat'], lf['lon']) if lf else 'no landfall')
        if lf and lf['lon'] < 89: lats.append(lf['lat'])
    truth = O.segment(*s['lf']) if s['lf'] else 'no landfall'; c = Counter(segs); n = len(segs)
    p = {k: c[k] / n for k in ORDER}; pc = {k: clim[k] / sum(clim.values()) for k in ORDER}
    bs = sum((p[k] - (k == truth)) ** 2 for k in ORDER); bc = sum((pc[k] - (k == truth)) ** 2 for k in ORDER)
    e = abs(np.median(lats) - s['lf'][0]) if (s['lf'] and s['lf'][1] < 89 and lats) else None
    sgn = (np.median(lats) - s['lf'][0]) if e is not None else None
    ctl = segs[0]
    rows.append(dict(name=s['name'], season=s['season'], truth=truth, p_truth=p[truth], pc_truth=pc[truth], bs=bs, bc=bc, e=e, sgn=sgn, ctl_hit=ctl == truth,
                     mode=c.most_common(1)[0][0], inside=c[truth] > 0))
    print(f"{s['name'][:10]:10s} {s['season']} truth {truth:18s} p={p[truth]:.2f} mode {rows[-1]['mode']:18s} err {e}", flush=True)
R = rows; E = [r['e'] for r in R if r['e'] is not None]
print(f"\nSTORYLINE ENSEMBLE on {len(R)} past storms (start at real genesis):")
print(f"  chance given to the coast stretch that really happened: ours {np.mean([r['p_truth'] for r in R]):.0%} vs climatology {np.mean([r['pc_truth'] for r in R]):.0%}")
print(f"  Brier score (lower is better): ours {np.mean([r['bs'] for r in R]):.3f} vs climatology {np.mean([r['bc'] for r in R]):.3f}  -> skill {1 - np.mean([r['bs'] for r in R]) / np.mean([r['bc'] for r in R]):+.0%}")
print(f"  most-common outcome right: {np.mean([r['mode'] == r['truth'] for r in R]):.0%} | control right: {np.mean([r['ctl_hit'] for r in R]):.0%} | real outcome inside the ensemble: {np.mean([r['inside'] for r in R]):.0%}")
print(f"  middle landfall latitude error: median {np.median(E):.1f} deg, mean signed {np.mean([r['sgn'] for r in R if r['sgn'] is not None]):+.1f} deg (n={len(E)})")
json.dump(R, open('scen_hindcast.json', 'w'), default=float)
