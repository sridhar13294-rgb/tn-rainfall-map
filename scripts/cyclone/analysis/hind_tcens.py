"""Score the physics ensemble (tcmodel.py, 51 members, design16 settings) on the past storms.
python hind_tcens.py LIB_NPZ CHUNK NCHUNK OUT_JSON
Start: ERA5 winds at the real genesis (storm's broad circulation removed, model vortex inserted). Settings that need
today's data (which circulation, GFS/ECMWF analysis, formation time, MJO, sea temperature) are held neutral."""
import sys, os, json, math, pickle, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, intens as IN, tcmodel as T, live_env as LE, scen as S
from cyc import on_land, km
from ours_live_p import FACT, DES
LIB, CH, NCH, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']; DATA = Z['data']; LEVS = [int(x) for x in Z['levs']]
LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
IM = pickle.load(open(os.path.join(O.REPO, 'data', 'cyclone', 'ours', 'intens_model.pkl'), 'rb'))
M = T.TC(1.5, 38.5, 61.5, 108.5, res=0.5); RAW = S.lib_raw(LIB)
def rmv(F, la, lo, R=5.0):
    d = np.hypot(LAg - la, (LOg - lo) * math.cos(math.radians(la))); m = d <= R; F = F.copy()
    for idx in np.ndindex(F.shape[:-2]):
        f = F[idx]; f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
        for _ in range(60): f[m] = nd.uniform_filter(f, 3, mode='nearest')[m]
        F[idx] = f
    return F
def real_at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
storms = [s for i, s in enumerate(O.LIBL) if i % NCH == CH]; res = []
def one(s):
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: return None
    F0 = DATA[TT.index(key), 1:3].astype(float)
    if not np.isfinite(F0).all(): return None
    P0 = O.path_of(s); la0, lo0 = P0[0][1], P0[0][2]; Fc = rmv(F0, la0, lo0)
    A0 = RAW.get(key); U0 = [A0[0, l] for l in range(4)] if A0 is not None else None; V0 = [A0[1, l] for l in range(4)] if A0 is not None else None
    mem = []
    for mi, lv in enumerate(DES):
        v = {k: vals[lv[i]] for i, (k, _, _, vals) in enumerate(FACT)}
        F = LE.perturb(Fc, lats, lons, dict(ridge_dlat=v['rlat'], ridge_dlon=0, ridge_str=v['rstr'], wd_amp=v['wd'], wd_lon=72.0, surge_u=v['surge']))
        u = sum(w * F[0, i] for i, w in enumerate(v['depth'])); vv = sum(w * F[1, i] for i, w in enumerate(v['depth']))
        off = 1.5 * v['rate']; shs = (1.25, 1.0, 0.8)[v['rate'] + 1]
        st = dict(v=17.0, dvp=0.0, h=0.0, vlf=None, landh=0.0)
        def vfn(th, la, lo, land):
            dtp = th - st['h']
            if dtp >= 0.49:
                if land: st['landh'] += dtp; st['vlf'] = st['vlf'] or st['v']; st['v'] = IN.inland(st['vlf'], st['landh'])
                else:
                    sh = (IN.shear_at(U0, V0, min(max(la, 1), 29), min(max(lo, 71), 104)) if U0 else None) or 10.0
                    dv = float(IM.predict([IN.feats(st['v'], sh * shs, la, st['dvp'], th)])[0]) + off
                    if st['vlf'] is not None: dv = min(dv, 2.0)
                    st['v'] = min(140.0, max(10.0, st['v'] + dv * dtp / 12)); st['dvp'] = dv
                st['h'] = th
            return max(3.0, 0.3 * st['v'] * 0.5144) * (v['size'] / 700) ** 0.3
        out = M.run_storm(M.regrid(u, lats, lons), M.regrid(vv, lats, lons), (la0 + v['slat'], lo0 + v['slon']), 168, vfn, size=v['size'], land_fn=on_land,
                          xo=v['xo'], size_grow=v['grow'], nu=v['phys'][0], tau_h=v['phys'][1], sppt=dict(seed=1000 + mi, amp=v['sppt']) if mi else None)
        lf = None
        for (h1, a1, b1), (h2, a2, b2) in zip(out, out[1:]):
            if not on_land(b1, a1) and on_land(b2, a2): lf = ((a1 + a2) / 2, (b1 + b2) / 2); break
        mem.append(dict(seg=O.segment(*lf) if lf else 'no landfall', lf=lf, pos={int(h): (a, b) for h, a, b in out if int(h) in (24, 48, 72, 96, 120)}))
    real = {h: real_at(P0, g + dt.timedelta(hours=h)) for h in (24, 48, 72, 96, 120)}
    return dict(name=s['name'], season=s['season'], truth=O.segment(*s['lf']) if s['lf'] else 'no landfall', truth_lf=s['lf'], members=mem, real=real)
for s in storms:
    try:
        r = one(s)
        if r: res.append(r); print(s['name'], s['season'], 'done', flush=True)
    except Exception as e:
        print(s['name'], s['season'], 'FAILED', repr(e)[:300], flush=True)
json.dump(res, open(OUT, 'w'), default=float)
