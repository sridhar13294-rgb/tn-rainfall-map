"""Past-storm test of the two-layer model (control run only), for comparing settings.
python exp_tc2.py LIB_NPZ CONFIG_JSON CHUNK NCHUNK OUT_JSON
CONFIG_JSON: list of dicts, e.g. [{"name": "Ld1200_tau9", "Ld15": 1.2e6, "tau_v": 9}]. Every config runs on this chunk's storms."""
import sys, os, json, math, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, tc2, intens as IN
from cyc import on_land, km
LIB, CFG, CH, NCH, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
CFGS = json.load(open(CFG)) if os.path.exists(CFG) else json.loads(CFG)
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']; DATA = Z['data']; LEVS = [int(x) for x in Z['levs']]
LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
def rmv(f, la, lo, R=5.0):
    d = np.hypot(LAg - la, (LOg - lo) * math.cos(math.radians(la))); m = d <= R; f = f.copy(); f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
    for _ in range(60): f[m] = nd.uniform_filter(f, 3, mode='nearest')[m]
    return f
def real_at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
res = []
for i, s in enumerate(O.LIBL):
    if i % NCH != CH: continue
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    F = DATA[TT.index(key)].astype(float)
    if not np.isfinite(F).all(): continue
    P0 = O.path_of(s); la0, lo0 = P0[0][1], P0[0][2]
    W = {l: (rmv(F[1, LEVS.index(l)], la0, lo0), rmv(F[2, LEVS.index(l)], la0, lo0)) for l in LEVS}
    peak = max((p[3] or 0) for p in P0)
    row = dict(name=s['name'], season=s['season'], truth=O.segment(*s['lf']) if s['lf'] else 'no landfall', truth_lf=s['lf'], runs={})
    real = {h: real_at(P0, g + dt.timedelta(hours=h)) for h in (24, 48, 72, 96)}
    for c in CFGS:
        try:
            M = tc2.TC2(1.5, 38.5, 61.5, 108.5, res=0.5, Ld15=c.get('Ld15', 1.2e6))
            # level weights for each layer, e.g. "lw": {"850": 0.4, "700": 0.4, "500": 0.2}, "uw": {"500": 0.5, "200": 0.5}
            lw = {int(k): v for k, v in c.get('lw', {'850': 0.5, '700': 0.5}).items()}; uw = {int(k): v for k, v in c.get('uw', {'500': 0.5, '200': 0.5}).items()}
            uL = sum(w * W[l][0] for l, w in lw.items()); vL = sum(w * W[l][1] for l, w in lw.items())
            uU = sum(w * W[l][0] for l, w in uw.items()); vU = sum(w * W[l][1] for l, w in uw.items())
            st = dict(v=25.0, h=0.0, landh=0.0, vlf=None)
            def vfn(th, la, lo, land):           # strength: the storm's real peak reached after 2-3 days (we test track, not strength)
                if land: st['landh'] += max(0.0, th - st['h']); st['vlf'] = st['vlf'] or st['v']; st['v'] = IN.inland(st['vlf'], st['landh'])
                else: st['v'] = min(max(25.0, peak), 25 + (max(25.0, peak) - 25) * min(1.0, th / 60))
                st['h'] = th; return st['v']
            reg = lambda a: M.regrid(a, lats, lons)
            out = M.run2(reg(uL), reg(vL), reg(uU), reg(vU), (la0, lo0), 120, vfn, tau_v=c.get('tau_v', 9.0), tau_h=c.get('tau_h', 9.0), land_fn=on_land, xo=c.get('xo', 0.5), **c.get('kw', {}))
            lf = None
            for (h1, a1, b1), (h2, a2, b2) in zip(out, out[1:]):
                if not on_land(b1, a1) and on_land(b2, a2): lf = ((a1 + a2) / 2, (b1 + b2) / 2); break
            te = {h: km((x[1], x[2]), real[h]) for h in real for x in out if abs(x[0] - h) < 0.1 and real[h]}
            row['runs'][c['name']] = dict(seg=O.segment(*lf) if lf else 'no landfall', lf=lf, te=te)
        except Exception as e:
            row['runs'][c['name']] = dict(err=repr(e)[:200])
    res.append(row); print(s['name'], s['season'], {k: (v.get('seg'), {h: round(x) for h, x in v.get('te', {}).items()}) for k, v in row['runs'].items()}, flush=True)
json.dump(res, open(OUT, 'w'), default=float)
