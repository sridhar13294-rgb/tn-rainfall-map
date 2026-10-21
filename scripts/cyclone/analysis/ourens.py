"""Our own ensemble: no model forecast is used. Today's observed state (GFS/ECMWF analysis, step 0 only) is matched
against the ERA5 state of every Oct-Dec Bay of Bengal system 2000-2025, 3 days to 1 day before it formed. The closest
analogues' real tracks become the members (start time set by the matching lag, small position jitter).

Usage: python ourens.py LIB_NPZ ANALYSIS_NPZ [ANALYSIS_NPZ ...]       (last analysis = 'today'; earlier ones are checks)
       python ourens.py LIB_NPZ --hindcast                            (leave-one-season-out test of the method)"""
import sys, json, math, datetime as dt, numpy as np
from collections import Counter, defaultdict
sys.path.insert(0, '/home/claude/tn-rainfall-map/scripts/cyclone/analysis')
from cyc import on_land
from scipy import ndimage as nd
LIBL = json.load(open('/home/claude/tn-rainfall-map/data/cyclone/lib_list.json'))
SEG = [(12.0, 'south TN'), (13.6, 'north TN'), (15.9, 'south AP'), (17.1, 'central AP'), (19.1, 'north AP'), (99, 'Odisha/WB')]
ORDER = ['Sri Lanka', 'south TN', 'north TN', 'south AP', 'central AP', 'north AP', 'Odisha/WB', 'Bangladesh/Myanmar', 'no landfall']
def segment(lat, lon):
    if lat is None: return 'no landfall'
    if lon >= 89.0: return 'Bangladesh/Myanmar'
    if lat < 10.0 and lon > 79.8: return 'Sri Lanka'
    for lim, n in SEG:
        if lat < lim: return n
LA = np.arange(0, 30.1, 1.5); LO = np.arange(70, 105.1, 1.5)
LAGS = [-72, -60, -48, -36, -24]                     # analysis time relative to the analogue's genesis (hours)
# ---------- fields on the common grid ----------
def vort(u, v):
    dy = 1.5 * 111e3; dx = dy * np.cos(np.radians(LA))[:, None]
    return (np.gradient(v, axis=1) / dx - np.gradient(u, axis=0) / dy) * 1e5
def pack(z500, z200, u850, v850, u700, v700, u500, v500, u200, v200):
    """dict of feature groups (2-D arrays on LA x LO)."""
    return dict(z500=z500 - np.nanmean(z500), z200=z200 - np.nanmean(z200),
                uv500=np.stack([u500, v500]), uv200=np.stack([u200, v200]), uv850=np.stack([u850, v850]),
                vo=np.stack([nd.uniform_filter(vort(u850, v850), 3), nd.uniform_filter(vort(u700, v700), 3)]))
GROUPS = dict(z500=1.0, z200=0.5, uv500=1.0, uv200=0.5, uv850=0.75, vo=1.0)
BAY = np.zeros((len(LA), len(LO)), bool); BAY[np.ix_((LA >= 3) & (LA <= 22), (LO >= 80) & (LO <= 100))] = True   # precursor area for vorticity
def lib_states(fn):
    Z = np.load(fn); T = [str(t) for t in Z['times']]; lats, lons = Z['lats'], Z['lons']
    J = [int(np.argmin(abs(lats - a))) for a in LA]; I = [int(np.argmin(abs(lons - o))) for o in LO]
    D = Z['data'][:, :, :, J][:, :, :, :, I]; levs = list(Z['levs'])      # time, var(z,u,v), lev, lat, lon
    k = {l: levs.index(l) for l in (850, 700, 500, 200)}
    S = {}
    for s in LIBL:
        t0 = dt.datetime.strptime(s['t0'], '%Y-%m-%dT%H'); t0 = t0.replace(hour=t0.hour // 6 * 6)
        for h in range(-72, 121, 12):
            t = (t0 + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H')
            if t not in T: continue
            x = D[T.index(t)]
            if not np.isfinite(x).all(): continue
            S[(s['sid'], h)] = pack(x[0, k[500]] / 9.80665, x[0, k[200]] / 9.80665, x[1, k[850]], x[2, k[850]], x[1, k[700]], x[2, k[700]],
                                    x[1, k[500]], x[2, k[500]], x[1, k[200]], x[2, k[200]])
    return S
def analysis_state(fn, step=0):
    """Mean over members at the given step (step 0 = the analysis / initial state), regridded to 1.5 deg."""
    Z = np.load(fn); V = [str(v) for v in Z['vars']]; lats, lons = Z['lats'], Z['lons']
    J = [int(np.argmin(abs(lats - a))) for a in LA]; I = [int(np.argmin(abs(lons - o))) for o in LO]
    si = list(Z['steps']).index(step); X = np.nanmean(Z['data'][:, si].astype(float), 0)
    def g(v):
        a = X[V.index(v)]; a = nd.uniform_filter(a, 3)                        # 0.5 -> ~1.5 deg smoothing before thinning
        return a[J][:, I]
    run = dt.datetime.strptime(str(Z['run']), '%Y%m%d%H') + dt.timedelta(hours=step)
    return run, pack(g('z500'), g('z200'), g('u850'), g('v850'), g('u700'), g('v700'), g('u500'), g('v500'), g('u200'), g('v200'))
def scales(S):
    keys = list(S); out = {}
    for g in GROUPS:
        A = np.stack([S[k][g] for k in keys]); out[g] = (A.mean(0), A.std(0) + 1e-6)
    return out
def dist(a, b, sc):
    tot = 0.0
    for g, w in GROUPS.items():
        m, sd = sc[g]; d = (a[g] - b[g]) / sd
        if g == 'vo': d = d[..., BAY]
        tot += w * np.sqrt(np.nanmean(d ** 2))
    return tot / sum(GROUPS.values())
# ---------- tracks ----------
def path_of(s):
    return [(dt.datetime.fromisoformat(p[0]), p[1], p[2], p[3]) for p in s['path'] if p[1] is not None]
def gen_time(s):
    t0 = dt.datetime.strptime(s['t0'], '%Y-%m-%dT%H'); return t0.replace(hour=t0.hour // 6 * 6)
def landfall(P, dlat=0.0, dlon=0.0):
    """first sea->land crossing of the shifted path, after genesis."""
    prev = None
    for p in P:
        la, lo = p[1] + dlat, p[2] + dlon; land = on_land(lo, la)
        if prev is not None and not prev[3] and land:
            return dict(t=prev[0] + (p[0] - prev[0]) / 2, lat=(prev[1] + la) / 2, lon=(prev[2] + lo) / 2)
        prev = (p[0], la, lo, land)
    return None
def match(state, S, sc, exclude_season=None, by_storm=True):
    """best lag per storm -> sorted [(d, sid, lag)]"""
    best = {}
    for (sid, h), x in S.items():
        if h not in LAGS: continue
        s = SID[sid]
        if exclude_season is not None and s['season'] == exclude_season: continue
        d = dist(state, x, sc)
        if sid not in best or d < best[sid][0]: best[sid] = (d, sid, h)
    return sorted(best.values())
def members(ranked, now, n=51, K=12, seed=0):
    top = ranked[:K]; d = np.array([r[0] for r in top]); w = np.exp(-(d - d.min()) / max(0.02, d.std()))
    w = w / w.sum(); cnt = np.floor(w * n).astype(int)
    for i in np.argsort(-(w * n - cnt))[: n - cnt.sum()]: cnt[i] += 1
    rng = np.random.default_rng(seed); out = []
    for (dd, sid, lag), c, ww in zip(top, cnt, w):
        s = SID[sid]; P = path_of(s); shift = now - (gen_time(s) + dt.timedelta(hours=lag))      # move analogue clock to ours
        for j in range(c):
            dlat, dlon = (0.0, 0.0) if j == 0 else tuple(rng.normal(0, 0.6, 2))
            if on_land(P[0][2] + dlon, P[0][1] + dlat): dlat = dlon = 0.0
            lf = landfall(P, dlat, dlon)
            out.append(dict(sid=sid, name=s['name'], season=s['season'], d=dd, w=float(ww), lag=lag, dlat=dlat, dlon=dlon, cat=s['cat'],
                            gen_t=(gen_time(s) + shift).isoformat(), gen=(P[0][1] + dlat, P[0][2] + dlon),
                            lf=dict(t=(lf['t'] + shift).isoformat(), lat=lf['lat'], lon=lf['lon']) if lf else None,
                            seg=segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                            pts=[((p[0] + shift).isoformat(), p[1] + dlat, p[2] + dlon, p[3]) for p in P]))
    return out
SID = {s['sid']: s for s in LIBL}
def summary(M):
    c = Counter(m['seg'] for m in M); n = len(M)
    lf = sorted(m['lf']['lat'] for m in M if m['lf'] and m['lf']['lon'] < 89)
    q = lambda p: round(float(np.percentile(lf, p)), 1) if lf else None
    return dict(n=n, seg={k: round(100 * c[k] / n) for k in ORDER if c[k]}, tn=sum(c[k] for k in ('south TN', 'north TN')),
                lat_mid=q(50), lat_p20=q(20), lat_min=round(lf[0], 1) if lf else None)
if __name__ == '__main__':
    S = lib_states(sys.argv[1]); sc = scales(S)
    print('library states', len(S), 'storms', len({k[0] for k in S}), flush=True)
    if sys.argv[2] == '--hindcast':
        # each storm: its own state 48 h before genesis vs every other season's storms; Brier score for the coast stretch
        rows = []
        for s in LIBL:
            for lead in (-48, -24):
                if (s['sid'], lead) not in S: continue
                truth = segment(*(s['lf'] or (None, None))) if s['lf'] else 'no landfall'
                R = match(S[(s['sid'], lead)], S, sc, exclude_season=s['season'])
                M = members(R, gen_time(s) + dt.timedelta(hours=lead))
                p = Counter(m['seg'] for m in M); pa = {k: p[k] / len(M) for k in ORDER}
                clim = Counter(segment(*o['lf']) if o['lf'] else 'no landfall' for o in LIBL if o['season'] != s['season'])
                pc = {k: clim[k] / sum(clim.values()) for k in ORDER}
                bs = sum((pa[k] - (k == truth)) ** 2 for k in ORDER); bc = sum((pc[k] - (k == truth)) ** 2 for k in ORDER)
                lats = [m['lf']['lat'] for m in M if m['lf'] and m['lf']['lon'] < 89]
                cl = [o['lf'][0] for o in LIBL if o['lf'] and o['season'] != s['season'] and o['lf'][1] < 89]
                e = abs(np.median(lats) - s['lf'][0]) if s['lf'] and lats and s['lf'][1] < 89 else None
                ec = abs(np.median(cl) - s['lf'][0]) if s['lf'] and s['lf'][1] < 89 else None
                rows.append(dict(sid=s['sid'], name=s['name'], season=s['season'], lead=lead, truth=truth, p_truth=pa[truth], pc_truth=pc[truth],
                                 bs=bs, bc=bc, e=e, ec=ec, top=[(SID[r[1]]['name'], SID[r[1]]['season'], r[2]) for r in R[:3]]))
        json.dump(rows, open('data/ourens_hindcast.json', 'w'), default=str)
        for lead in (-48, -24):
            r = [x for x in rows if x['lead'] == lead]
            E = [(x['e'], x['ec']) for x in r if x['e'] is not None]
            print(f"lead {-lead} h before genesis: {len(r)} storms | Brier ours {np.mean([x['bs'] for x in r]):.3f} vs climatology {np.mean([x['bc'] for x in r]):.3f}"
                  f" (skill {1 - np.mean([x['bs'] for x in r]) / np.mean([x['bc'] for x in r]):+.0%}) | prob. given to what happened ours {np.mean([x['p_truth'] for x in r]):.0%} vs clim {np.mean([x['pc_truth'] for x in r]):.0%}"
                  f" | median landfall-lat error ours {np.median([e[0] for e in E]):.1f} deg vs clim {np.median([e[1] for e in E]):.1f} deg (n={len(E)})")
        sys.exit()
    out = {}
    for fn in sys.argv[2:]:
        for f in fn.split(','):
            pass
        run, st = analysis_state(fn)
        R = match(st, S, sc); M = members(R, run)
        sm = summary(M); out[run.isoformat()] = dict(src=fn, ranked=[(r[0], SID[r[1]]['name'], SID[r[1]]['season'], r[2]) for r in R[:15]], members=M, summary=sm)
        print('\n=== analysis', run, fn.split('/')[-1])
        for d, nm, se, lag in out[run.isoformat()]['ranked'][:12]:
            s = next(x for x in LIBL if x['name'] == nm and x['season'] == se)
            print(f"  {d:.3f}  {nm[:10]:10s} {se}  formed {s['t0'][5:10]} at {s['gen'][0]:.1f}N {s['gen'][1]:.1f}E  ({-lag} h after the match)  {s['cat']:5s} -> {segment(*s['lf']) if s['lf'] else 'no landfall'}")
        print('  members', sm)
    json.dump(out, open('data/ourens.json', 'w'), default=str)
