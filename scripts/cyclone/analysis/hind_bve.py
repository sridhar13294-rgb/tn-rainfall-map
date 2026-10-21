"""Test the barotropic environment on the 84 past storms: start from ERA5 24 h before genesis (storm swirl removed),
let the barotropic model move the steering flow, run our track + strength model from the real genesis point."""
import sys, os, json, math, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S, live_env as LE
from cyc import on_land
Z = np.load(sys.argv[1]); T = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']; DATA = Z['data']
LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
def rm(F, la, lo, R=4.5):
    d = np.hypot(LAg - la, (LOg - lo) * math.cos(math.radians(la))); m = d <= R; F = F.copy()
    for idx in np.ndindex(F.shape[:-2]):
        f = F[idx]; f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
        for _ in range(40): f[m] = __import__('scipy.ndimage', fromlist=['x']).uniform_filter(f, 3, mode='nearest')[m]
        F[idx] = f
    return F
M = S.train(); rows = []
DN = float(os.environ.get('DN', 0)); DE = float(os.environ.get('DE', 0))
for s in O.LIBL:
    if not s['lf']: continue
    g = O.gen_time(s); ti = g - dt.timedelta(hours=24); key = ti.strftime('%Y-%m-%dT%H')
    if key not in T: continue
    F = DATA[T.index(key), 1:3].astype(float)
    if not np.isfinite(F).all(): continue
    P0 = O.path_of(s); F = rm(F, P0[0][1], P0[0][2])
    P = dict(gen_lat=P0[0][1], gen_lon=P0[0][2], gen_t=P0[0][0], sst=0.3, mjo_i=0, mjo_kt=0.0, shear_scale=1.0, beta=1.0, speed=1.0, dn=DN, de=DE)
    env = LE.EnvB(F, lats, lons, O.LA, O.LO, ti, P, hours=264, box=(1.5, 38.5, 61.5, 108.5))
    pts, lf = S.run_track(M, env, P)
    truth = s['lf']; e = abs(lf['lat'] - truth[0]) if lf and truth[1] < 89 else None; sgn = (lf['lat'] - truth[0]) if lf and truth[1] < 89 else None
    rows.append(dict(sgn=sgn, month=g.month, name=s['name'], season=s['season'], truth=O.segment(*truth), ours=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall', e=e))
    print(f"{s['name'][:10]:10s} {s['season']} truth {rows[-1]['truth']:18s} ours {rows[-1]['ours']:18s} err {e}", flush=True)
hit = np.mean([r['ours'] == r['truth'] for r in rows]); E = [r['e'] for r in rows if r['e'] is not None]
print(f'BAROTROPIC environment: right coast stretch {hit:.0%} of {len(rows)} | median landfall-lat error {np.median(E):.1f} deg (n={len(E)})')
G = [r for r in rows if r['sgn'] is not None]
print('mean signed landfall-lat error (ours - real):', round(float(np.mean([r['sgn'] for r in G])), 2), 'deg; landed south of the real point in', sum(r['sgn'] < 0 for r in G), 'of', len(G))
for mo in (10, 11, 12):
    g = [r['sgn'] for r in G if r['month'] == mo]
    if g: print(' month', mo, 'n', len(g), 'mean signed', round(float(np.mean(g)), 2), 'median abs', round(float(np.median(np.abs(g))), 2))
O_ = [r for r in rows if r['month'] == 10]; print(' October right stretch', round(np.mean([r['ours'] == r['truth'] for r in O_]), 2), 'of', len(O_))
