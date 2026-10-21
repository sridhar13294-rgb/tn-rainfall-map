"""Score the two-layer physics model driven by our storylines, on the past storms (51 members each).
python hind_tc2s.py LIB_NPZ CHUNK NCHUNK OUT_JSON
Start: ERA5 winds at the real genesis (storm's broad circulation removed, model vortex inserted).
Member 0 holds the starting far field. Members 1-50 follow the seven storylines (ridge holds / weakens / breaks /
deep trough pulls / breaks and rebuilds / storm pushes the ridge / weak sheared system), shared out as on the live page,
each spread in timing, strength and start position with the same fixed Halton sequence. The storyline changes the far
field through time; the storm and its surroundings are free physics (two-layer model, tc2.py).
Strength: ramps to the storm's real peak in 2.5 days (we are scoring the track), weaker for the 'weak' storyline and a
bit stronger for 'pull'/'push'. MJO and sea temperature are held neutral."""
import sys, os, json, math, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, intens as IN, tc2, live_env_s as ES
from ours_live_s import STORIES, vary
from cyc import on_land
LIB, CH, NCH, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']; DATA = Z['data']; LEVS = [int(x) for x in Z['levs']]
LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
LW = (0.35, 0.35, 0.3, 0.0); UW = (0.0, 0.0, 0.0, 1.0)            # lower layer 850/700/500, upper layer 200 hPa
SET = dict(tau_v=6.0, cmul=0.0, resid=True, tau_env=2.0, env_r=(300.0, 700.0))
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
def members(t0, la0, lo0):
    obs = dict(formed=True, mjo_u=0.0, mjo_kt=0.0, sst=0.0)
    PS = [dict(member=0, story='control', start_lat=la0, start_lon=lo0)]
    w = np.array([st[2] for st in STORIES], float); c = np.floor(w / w.sum() * 50).astype(int)
    for i in np.argsort(-(w / w.sum() * 50 - c))[: 50 - c.sum()]: c[i] += 1
    kk = 0
    for st, cnt in zip(STORIES, c):
        for j in range(1, cnt + 1):
            kk += 1; PS.append(vary(st, j, cnt, t0, (la0, lo0), obs, k=kk + 20))
    return PS
def one(s, M):
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: return None
    F0 = DATA[TT.index(key), 1:3].astype(float)
    if not np.isfinite(F0).all(): return None
    P0 = O.path_of(s); la0, lo0 = real_at(P0, g) or (P0[0][1], P0[0][2]); Fc = rmv(F0, la0, lo0); peak = max(25.0, max((p[3] or 0) for p in P0))
    reg = lambda a: M.regrid(a, lats, lons); lay = lambda X, wts: reg(sum(w * X[i] for i, w in enumerate(wts) if w))
    mem = []
    for P in members(g, la0, lo0):
        env = ES.EnvS(Fc, lats, lons, g, P)
        def env_fn(th, storm=None, env=env):
            U, V = env.at(g + dt.timedelta(hours=th), storm=storm); return lay(U, LW), lay(V, LW), lay(U, UW), lay(V, UW)
        uL, vL, uU, vU = env_fn(0.0)
        fac = dict(weak=0.6, pull=1.15, push=1.2).get(P['story'], 1.0); top = max(25.0, peak * fac)
        if P['story'] == 'weak': top = min(top, 33.0)
        st = dict(v=25.0, h=0.0, landh=0.0, vlf=None)
        def vfn(th, la, lo, land, st=st, top=top):
            if land: st['landh'] += max(0.0, th - st['h']); st['vlf'] = st['vlf'] or st['v']; st['v'] = IN.inland(st['vlf'], st['landh'])
            else: st['v'] = min(top, 25 + (top - 25) * min(1.0, th / 60))
            st['h'] = th; return st['v']
        out = M.run2(uL, vL, uU, vU, (P['start_lat'], P['start_lon']), 120, vfn, land_fn=on_land, env_fn=env_fn,
                     sppt=dict(seed=1000 + P['member'], amp=0.15) if P['member'] else None, **SET)
        lf = None
        for (h1, a1, b1), (h2, a2, b2) in zip(out, out[1:]):
            if not on_land(b1, a1) and on_land(b2, a2): lf = ((a1 + a2) / 2, (b1 + b2) / 2); break
        mem.append(dict(story=P['story'], seg=O.segment(*lf) if lf else 'no landfall', lf=lf,
                        pos={int(h): (round(a, 2), round(b, 2)) for h, a, b in out if abs(h - round(h)) < 1e-6 and int(round(h)) % 12 == 0 and h > 0}))
    real = {h: real_at(P0, g + dt.timedelta(hours=h)) for h in (24, 48, 72, 96, 120)}
    return dict(name=s['name'], season=s['season'], truth=O.segment(*s['lf']) if s['lf'] else 'no landfall', truth_lf=s['lf'], members=mem, real=real)
if __name__ == '__main__':
    M = tc2.TC2(-2.5, 38.5, 61.5, 108.5, res=0.5); res = []
    for i, s in enumerate(O.LIBL):
        if i % NCH != CH: continue
        try:
            r = one(s, M)
            if r: res.append(r); print(s['name'], s['season'], 'done', flush=True)
        except Exception as e:
            print(s['name'], s['season'], 'FAILED', repr(e)[:300], flush=True)
    json.dump(res, open(OUT, 'w'), default=float)
