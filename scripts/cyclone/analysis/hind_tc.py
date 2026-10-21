"""Score the storm-in-the-physics model (tcmodel.py) on the past storms: ERA5 deep-layer winds at genesis (storm left in,
strengthened to a standard starting vortex), one control run per storm, landfall vs what really happened."""
import sys, os, json, math, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, tcmodel as T, bve
from cyc import on_land, km as KM
Z = np.load(sys.argv[1]); TT = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']; DATA = Z['data']; LEVS = list(Z['levs'])
M = T.TC(1.5, 38.5, 61.5, 108.5, res=0.5)
from scipy import ndimage as nd
LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
def rmv(f, la, lo, R=5.0):
    d = np.hypot(LAg - la, (LOg - lo) * math.cos(math.radians(la))); m = d <= R; f = f.copy(); f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
    for _ in range(60): f[m] = nd.uniform_filter(f, 3, mode='nearest')[m]
    return f
def vfn(th, a, b, land):
    v = min(20.0, 5 + max(0.0, th) / 6 * 0.9); return v * 0.35 if land else v
def landfall(out):
    for (h1, a1, b1), (h2, a2, b2) in zip(out, out[1:]):
        if not on_land(b1, a1) and on_land(b2, a2): return dict(h=(h1 + h2) / 2, lat=(a1 + a2) / 2, lon=(b1 + b2) / 2)
    return None
rows = []
for s in O.LIBL:
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    F = DATA[TT.index(key)].astype(float)
    if not np.isfinite(F).all(): continue
    P0 = O.path_of(s)
    u = sum(w * rmv(F[1, LEVS.index(l)], P0[0][1], P0[0][2]) for l, w in bve.WTS.items()); v = sum(w * rmv(F[2, LEVS.index(l)], P0[0][1], P0[0][2]) for l, w in bve.WTS.items()); out = M.run_storm(M.regrid(u, lats, lons), M.regrid(v, lats, lons), (P0[0][1], P0[0][2]), 192, vfn, land_fn=on_land)
    lf = landfall(out); truth = O.segment(*s['lf']) if s['lf'] else 'no landfall'
    ours = O.segment(lf['lat'], lf['lon']) if lf else 'no landfall'
    e = abs(lf['lat'] - s['lf'][0]) if (lf and s['lf'] and s['lf'][1] < 89) else None; sgn = (lf['lat'] - s['lf'][0]) if e is not None else None
    # 24/48/72 h track error vs IBTrACS
    te = {}
    for h in (24, 48, 72):
        o = next((x for x in out if abs(x[0] - h) < 0.1), None); t = g + dt.timedelta(hours=h)
        r = next(((a[1] + (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()) * (b[1] - a[1]), a[2] + (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()) * (b[2] - a[2])) for a, b in zip(P0, P0[1:]) if a[0] <= t <= b[0]), None)
        if o and r: te[h] = KM((o[1], o[2]), r)
    rows.append(dict(name=s['name'], season=s['season'], truth=truth, ours=ours, e=e, sgn=sgn, te=te))
    print(f"{s['name'][:10]:10s} {s['season']} truth {truth:18s} ours {ours:18s} err {e} track {te}", flush=True)
R = [r for r in rows]; E = [r['e'] for r in R if r['e'] is not None]
print(f"\nSTORM-IN-PHYSICS model, {len(R)} past storms: right coast stretch {np.mean([r['ours'] == r['truth'] for r in R]):.0%}; landfall latitude error median {np.median(E):.1f} deg, mean signed {np.mean([r['sgn'] for r in R if r['sgn'] is not None]):+.1f} deg (n={len(E)})")
for h in (24, 48, 72):
    x = [r['te'][h] for r in R if h in r['te'] and r['te'][h] is not None]; print(f"  track error {h} h: median {np.median(x):.0f} km (n={len(x)})")
json.dump(rows, open('tc_hindcast.json', 'w'), default=float)
