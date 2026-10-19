import json, numpy as np, sys, datetime as dt, math
from collections import defaultdict
sys.path.insert(0, '.')
from analogs import region
O = json.load(open('data/ours.json')); T = json.load(open('data/tracks.json'))
W = {'ENS': 0.5 / T['ENS']['n'], 'GEFS': 0.5 / T['GEFS']['n']}
def interp(pts, t):
    P = [(dt.datetime.fromisoformat(p['t']), p['lat'], p['lon']) for p in pts]
    for a, b in zip(P, P[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds()); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
def wmedian(vals, w):
    o = np.argsort(vals); v = np.array(vals)[o]; c = np.cumsum(np.array(w)[o]); return v[np.searchsorted(c, c[-1] / 2)]
res = {}
for kind, SRC in (('raw', T), ('ours', None)):
    land = defaultdict(float); lft, lfla, lflo, lfw = [], [], [], []; form = 0
    for src in ('ENS', 'GEFS'):
        for i, t in enumerate(T[src]['tracks']):
            if not t: continue
            form += W[src]
            lf = t['lf'] if kind == 'raw' else (O[src][i]['lf'] if O[src][i] else None)
            if lf:
                land[region(lf['lat'], lf['lon'])] += W[src]; lft.append(dt.datetime.fromisoformat(lf['t']).timestamp()); lfla.append(lf['lat']); lflo.append(lf['lon']); lfw.append(W[src])
            else: land['stays at sea / fades'] += W[src]
    res[kind] = dict(form=form, land={k: round(v * 100) for k, v in sorted(land.items(), key=lambda x: -x[1])},
                     lf_time=dt.datetime.utcfromtimestamp(wmedian(lft, lfw)).isoformat(), lf_lat=float(wmedian(lfla, lfw)), lf_lon=float(wmedian(lflo, lfw)),
                     lf_time_q=[dt.datetime.utcfromtimestamp(np.percentile(lft, q)).isoformat() for q in (20, 80)])
# genesis, intensity
g_t, g_la, g_lo, g_w, pmin = [], [], [], [], []
for src in ('ENS', 'GEFS'):
    for t in T[src]['tracks']:
        if not t: continue
        p0 = t['pts'][0]; g_t.append(dt.datetime.fromisoformat(p0['t']).timestamp()); g_la.append(p0['lat']); g_lo.append(p0['lon']); g_w.append(W[src])
        pmin.append((src, min(p['p'] for p in t['pts'])))
G = dict(t=dt.datetime.utcfromtimestamp(wmedian(g_t, g_w)), lat=float(wmedian(g_la, g_w)), lon=float(wmedian(g_lo, g_w)),
         t_q=[dt.datetime.utcfromtimestamp(np.percentile(g_t, q)).isoformat() for q in (20, 80)])
# central track of our model: mean displacement from each member's own genesis, placed at the consensus genesis
H = list(range(0, 169, 12)); disp = {h: [] for h in H}; wts = {h: [] for h in H}
for src in ('ENS', 'GEFS'):
    for i, r in enumerate(O[src]):
        if not r: continue
        t0 = dt.datetime.fromisoformat(r['pts'][0]['t']); la0, lo0 = r['pts'][0]['lat'], r['pts'][0]['lon']
        for h in H:
            q = interp(r['pts'], t0 + dt.timedelta(hours=h))
            if q: disp[h].append((q[0] - la0, (q[1] - lo0))); wts[h].append(W[src])
central = []
for h in H:
    if len(disp[h]) < 10: break
    d = np.array(disp[h]); w = np.array(wts[h]); m = (d * w[:, None]).sum(0) / w.sum()
    la, lo = G['lat'] + m[0], G['lon'] + m[1]
    spread = float(np.sqrt((((d[:, 0] - m[0]) * 111.2) ** 2 + ((d[:, 1] - m[1]) * 111.2 * math.cos(math.radians(la))) ** 2) @ w / w.sum()))
    central.append(dict(h=h, t=(G['t'] + dt.timedelta(hours=h)).isoformat(), lat=round(float(la), 2), lon=round(float(lo), 2), spread_km=round(spread), n=len(disp[h])))
det = {}
for src in ('GFS', 'HRES'):
    t = [x for x in T[src]['tracks'] if x][0]; o = [x for x in O[src] if x][0]
    det[src] = dict(run=T[src]['run'], genesis=t['pts'][0], pmin=min(p['p'] for p in t['pts']), raw_lf=t['lf'], ours_lf=o['lf'])
out = dict(genesis=dict(t=G['t'].isoformat(), lat=G['lat'], lon=G['lon'], t_q=G['t_q']), raw=res['raw'], ours=res['ours'], central=central, det=det,
           pmin=dict(ENS=float(np.median([p for s, p in pmin if s == 'ENS'])), GEFS=float(np.median([p for s, p in pmin if s == 'GEFS'])),
                     ENS_q=[float(np.percentile([p for s, p in pmin if s == 'ENS'], q)) for q in (20, 80)], GEFS_q=[float(np.percentile([p for s, p in pmin if s == 'GEFS'], q)) for q in (20, 80)]),
           members=dict(ENS=sum(1 for t in T['ENS']['tracks'] if t), ENS_n=T['ENS']['n'], GEFS=sum(1 for t in T['GEFS']['tracks'] if t), GEFS_n=T['GEFS']['n']))
json.dump(out, open('data/consensus.json', 'w'), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)[:3500])
