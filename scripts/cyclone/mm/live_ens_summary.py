import json, glob, sys, math, datetime as dt, numpy as np
sys.path[:0] = ['/home/claude/tn-rainfall-map/scripts/cyclone', '/home/claude/tn-rainfall-map/scripts/cyclone/analysis']
from cyc import on_land
K = '/home/claude/tn-rainfall-map/data/cyclone/kaggle/'
RUNS = {'80 km 12Z': (dt.datetime(2026,10,29,12), [K+'tn-live80-a', K+'tn-live80-b']),
        '80 km 18Z': (dt.datetime(2026,10,29,18), [K+'tn-live80-18a', K+'tn-live80-18b', K+'tn-live80-18c2']),
        '140 km 12Z': (dt.datetime(2026,10,29,12), ['/home/claude/tn-rainfall-map/data/cyclone/mm/live/2026102912-v2'])}
def seg(lat, lon):
    if lon < 82.5 and 79 <= lon and lat < 10.3 and lon > 79.6 and lat > 5.8: return 'Sri Lanka' if lon > 79.7 and lat < 9.9 else 'south TN'
    if lat < 11.7: return 'south TN'
    if lat < 13.6: return 'north TN'
    if lat < 16.0: return 'south AP'
    return 'north AP/Odisha'
OUT = {}
for name, (t0, dirs) in RUNS.items():
    mem = []; failed = 0
    for d in dirs:
        for f in sorted(glob.glob(d + '/part_*.json')):
            for m in json.load(open(f))['members']:
                if 'tracks' not in m: failed += 1; continue
                T = m['tracks']; cand = [(k, v) for k, v in T.items() if v]
                if not cand: failed += 1; continue
                best = next(((k, v) for k, v in cand if k == 'peak' and len(v) >= 8), None) or max(cand, key=lambda kv: max([t[3] for t in kv[1] if 5 <= t[1] <= 22 and 78 <= t[2] <= 99] or [0]))
                tr = best[1]; pts = []
                for t in tr:
                    pts.append(t)
                    if on_land(t[2], t[1]) and t[3] < 15 and len(pts) > 2: break
                lf = None
                for a, c in zip(pts, pts[1:]):
                    if not on_land(a[2], a[1]) and on_land(c[2], c[1]): lf = ((a[0]+c[0])/2, (a[1]+c[1])/2, (a[2]+c[2])/2, a[3], a[4]); break
                mem.append(dict(member=m['member'], pts=pts, lf=lf))
    segs = {}
    for m in mem:
        s = 'no landfall / at sea' if not m['lf'] else seg(m['lf'][1], m['lf'][2])
        if m['lf'] and m['lf'][2] > 81.9 and m['lf'][1] > 17: s = 'north AP/Odisha'
        if m['lf'] and on_land(m['lf'][2], m['lf'][1]) and m['lf'][2] > 79.6 and m['lf'][2] < 82 and m['lf'][1] < 9.9: s = 'Sri Lanka'
        m['seg'] = s; segs[s] = segs.get(s, 0) + 1
    # daily strength
    daily = {}
    for h in range(0, 169, 24):
        w = [max([t[3] for t in m['pts'] if abs(t[0]-h) <= 3] or [np.nan]) for m in mem]; p = [min([t[4] for t in m['pts'] if abs(t[0]-h) <= 3] or [np.nan]) for m in mem]
        daily[h] = (np.nanmedian(w), np.nanpercentile(w, 10), np.nanpercentile(w, 90), np.nanmedian(p), np.nanmin(p), int(np.sum(np.isfinite(w))))
    lft = [t0 + dt.timedelta(hours=m['lf'][0]) for m in mem if m['lf']]
    OUT[name] = dict(t0=t0, mem=mem, failed=failed, segs=segs, daily=daily, lft=lft)
    print(f'== {name}: members {len(mem)} failed {failed}')
    print('   landfall segments:', dict(sorted(segs.items(), key=lambda kv: -kv[1])))
    if lft: lt = sorted(lft); print('   landfall time median', lt[len(lt)//2], 'range', lt[len(lt)//10], '-', lt[-1 - len(lt)//10])
    for h, v in daily.items(): print(f'   +{h:3d}h ({(t0+dt.timedelta(hours=h)):%d %b %HZ}) wind med {v[0]:.0f} kt (p10-90 {v[1]:.0f}-{v[2]:.0f}) pmin med {v[3]:.0f} min {v[4]:.0f} n {v[5]}')
import pickle; pickle.dump(OUT, open('/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/andaman/out.pkl', 'wb'))
