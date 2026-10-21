"""Past-storm tests of the hemisphere-wide two-layer model (tc2.py on 6S-65N, 0-150E).
python exp_hemi.py LIBH_NPZ CONFIG_JSON CHUNK NCHUNK OUT_JSON
CONFIG_JSON: list of dicts. Keys: name, tag (first entry: output folder), lw/uw level weights, Ld15, tau_v, xo,
kw (extra run2 settings), ens (number of perturbed members; 0 = control only).
Start: ERA5 at the real start time and position (storm's broad circulation removed, model vortex inserted). The only
thing held near the analysis is the deep tropics (env_lat), so mid-latitude troughs and the ridge move by the equations.
Ensemble members: the analysis is perturbed the way it is uncertain (trough strength and position, small random
large-scale wind errors, start position) and the physics settings vary (deformation radius, vortex response, how the
storm's winds fall off, heating, random tendency noise, how firmly the tropics are held) - no storylines."""
import sys, os, json, math, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, tc2, intens as IN
from cyc import on_land
from ours_live_s import halton
LIB, CFG, CH, NCH, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
CFGS = json.load(open(CFG)) if os.path.exists(CFG) else json.loads(CFG)
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']; DATA = Z['data']; LEVS = [int(x) for x in Z['levs']]
LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
DOM = (-6.0, 65.0, 0.0, 150.0, 0.75)
def rmv(f, la, lo, R=5.0):
    d = np.hypot(LAg - la, (LOg - lo) * math.cos(math.radians(la))); m = d <= R; f = f.copy(); f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
    for _ in range(60): f[m] = nd.uniform_filter(f, 3, mode='nearest')[m]
    return f
def real_at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
def perturb(U, V, k, amp_ic=1.0):
    """member k's analysis: (1) mid-latitude waves (deviation from the zonal mean north of 25N) 80-120% as strong and
    shifted up to 3 deg east/west - the trough's strength and position are the least certain part of the analysis;
    (2) smooth random wind errors of 1-2 m/s (more aloft), rotational, on 1,500-4,000 km scales."""
    h = lambda b: halton(k, b)
    sc = 0.8 + 0.4 * h(2); sh = (h(3) - 0.5) * 6.0; wm = np.clip((LAg - 25) / 10, 0, 1)
    rs = np.random.default_rng(500 + k); out = []
    Kx = rs.uniform(2 * np.pi / 40, 2 * np.pi / 13, 8); Ky = rs.uniform(2 * np.pi / 40, 2 * np.pi / 13, 8) * rs.choice([-1, 1], 8); ph = rs.uniform(0, 2 * np.pi, 8)
    psi = sum(np.sin(Kx[i] * LOg + Ky[i] * LAg + ph[i]) for i in range(8)) / np.sqrt(4)
    du = -np.gradient(psi, axis=0) / 1.5; dv = np.gradient(psi, axis=1) / 1.5; nrm = np.sqrt((du ** 2 + dv ** 2).mean())
    du, dv = du / nrm, dv / nrm
    for l in range(len(LEVS)):
        a = amp_ic * (1.0 if LEVS[l] >= 700 else 2.0)
        uu, vv = [], []
        for X, dX in ((U[l], du), (V[l], dv)):
            zm = X.mean(1, keepdims=True); dev = nd.shift(X - zm, (0, sh / 1.5), order=1, mode='nearest')
            Y = X + wm * (zm + sc * dev - X) + a * dX; (uu if X is U[l] else vv).append(Y)
        out.append((uu[0], vv[0]))
    return [o[0] for o in out], [o[1] for o in out]
def phys(k):
    h = lambda b: halton(k, b)
    return dict(Ld15=0.9e6 + 0.6e6 * h(5), tau_v=3 + 6 * h(7), xo=0.4 + 0.2 * h(11), heat_f=0.5 + h(13), sppt=0.25 * h(17),
                tau_env=1 + 3 * h(19), free=18 + 6 * h(23), dla=(h(29) - 0.5) * 1.0, dlo=(h(31) - 0.5) * 1.0)
res = []
for i, s in enumerate(O.LIBL):
    if i % NCH != CH: continue
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    F = DATA[TT.index(key)].astype(float)
    if not np.isfinite(F[1:]).all(): continue
    P0 = O.path_of(s); st0 = real_at(P0, g)
    if not st0: continue
    la0, lo0 = st0; peak = max(25.0, max((p[3] or 0) for p in P0))
    U0 = [rmv(F[1, l], la0, lo0) for l in range(len(LEVS))]; V0 = [rmv(F[2, l], la0, lo0) for l in range(len(LEVS))]
    row = dict(name=s['name'], season=s['season'], t0=key, truth=O.segment(*s['lf']) if s['lf'] else 'no landfall', truth_lf=s['lf'],
               real=[((p[0] - g).total_seconds() / 3600, p[1], p[2]) for p in P0], runs={})
    for c in CFGS:
        lw = {int(k): v for k, v in c.get('lw', {'850': 0.3, '700': 0.3, '500': 0.25, '200': 0.15}).items()}; uw = {int(k): v for k, v in c.get('uw', {'200': 1.0}).items()}
        mems = []
        for k in range(0, c.get('ens', 0) + 1):
            try:
                kw = dict(c.get('kw', {})); Ld = c.get('Ld15', 1.2e6); tv = c.get('tau_v', 6.0); xo = c.get('xo', 0.5); la_s, lo_s = la0, lo0
                if k == 0: U, V = U0, V0
                else:
                    p = phys(k); U, V = perturb(U0, V0, k, c.get('amp_ic', 1.0)); Ld, tv, xo = p['Ld15'], p['tau_v'], p['xo']
                    if kw.get('heat'): kw['heat'] = kw['heat'] * p['heat_f']
                    if p['sppt'] > 0.02: kw['sppt'] = dict(seed=1000 + k, amp=p['sppt'])
                    if kw.get('tau_env'): kw['tau_env'] = p['tau_env']
                    if kw.get('env_lat'): kw['env_lat'] = (p['free'] - 10, p['free'])
                    la_s, lo_s = la0 + p['dla'], lo0 + p['dlo']
                M = tc2.TC2(DOM[0], DOM[1], DOM[2], DOM[3], res=DOM[4], Ld15=Ld); reg = lambda a: M.regrid(a, lats, lons)
                L_ = lambda X, w: reg(sum(wt * X[LEVS.index(l)] for l, wt in w.items()))
                st = dict(v=25.0, h=0.0, landh=0.0, vlf=None)
                def vfn(th, la, lo, land, st=st):
                    if land: st['landh'] += max(0.0, th - st['h']); st['vlf'] = st['vlf'] or st['v']; st['v'] = IN.inland(st['vlf'], st['landh'])
                    else: st['v'] = min(peak, 25 + (peak - 25) * min(1.0, th / 60))
                    st['h'] = th; return st['v']
                out = M.run2(L_(U, lw), L_(V, lw), L_(U, uw), L_(V, uw), (la_s, lo_s), 120, vfn, dt=c.get('dt', 300.0), tau_v=tv, xo=xo, land_fn=on_land, **kw)
                lf = None
                for (h1, a1, b1), (h2, a2, b2) in zip(out, out[1:]):
                    if not on_land(b1, a1) and on_land(b2, a2): lf = ((a1 + a2) / 2, (b1 + b2) / 2); break
                mems.append(dict(seg=O.segment(*lf) if lf else 'no landfall', lf=lf, trk=[(round(h, 1), round(a, 2), round(b, 2)) for h, a, b in out]))
            except Exception as e:
                mems.append(dict(err=repr(e)[:200]))
        row['runs'][c['name']] = mems
    res.append(row); print(s['name'], s['season'], {k: [m.get('seg') for m in v[:3]] for k, v in row['runs'].items()}, flush=True)
json.dump(res, open(OUT, 'w'), default=float)
