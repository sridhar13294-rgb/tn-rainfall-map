"""Tamil Nadu watch for the late-October 2026 Bay system: run in a work folder whose data/ holds the latest
fc_<SRC>_<RUN>.npz files (one per source). For every member it finds
  - the main system (forms 21 Oct - 2 Nov over sea at 5-17N, east of 86E; the deepest such track), and where it crosses
    the coast, by stretch of coast;
  - any closed low at all (even weak, formed from 22 Oct on, anywhere in the Bay) that crosses the Tamil Nadu coast.
Prints a short summary and appends it to data/tn_watch_history.json.
Usage: python tn_watch.py [workdir]"""
import sys, os, json, glob, math, datetime as dt, numpy as np
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cyc import Fc, track_member, find_lows, landfall
W = sys.argv[1] if len(sys.argv) > 1 else '.'
SEG = [(12.0, 'south TN'), (13.6, 'north TN'), (15.9, 'south AP'), (17.1, 'central AP'), (19.1, 'north AP'), (99, 'Odisha/WB')]
ORDER = ['south TN', 'north TN', 'south AP', 'central AP', 'north AP', 'Odisha/WB', 'Bangladesh/Myanmar', 'sea/fades', 'no system']
def segment(lf):
    if lf is None: return 'sea/fades'
    if lf['lon'] >= 89.0: return 'Bangladesh/Myanmar'
    for lim, name in SEG:
        if lf['lat'] < lim: return name
def track_weak(F, m):
    """Same tracker as cyc.track_member but starting from any closed low >= 1.5 hPa deep (no spin test)."""
    tracks, active = [], []
    for s, t in enumerate(F.times):
        lows = find_lows(F, m, s); used = set(); hrs = (F.times[s] - F.times[s - 1]).total_seconds() / 3600 if s else 6
        for tr in active:
            last = tr['pts'][-1]; vx = vy = 0.0
            if len(tr['pts']) >= 2:
                a, b = tr['pts'][-2], tr['pts'][-1]; h0 = max(1, (b['t'] - a['t']).total_seconds() / 3600); vx, vy = (b['lon'] - a['lon']) / h0, (b['lat'] - a['lat']) / h0
            g = (last['lat'] + vy * hrs, last['lon'] + vx * hrs); best = None
            for q, L in enumerate(lows):
                if q in used: continue
                d = math.hypot(L['lat'] - g[0], (L['lon'] - g[1]) * math.cos(math.radians(g[0])))
                if d <= 1.0 + 1.5 * hrs / 6 and (best is None or d < best[0]): best = (d, q)
            if best: used.add(best[1]); L = dict(lows[best[1]]); L['t'] = t; tr['pts'].append(L); tr['miss'] = 0
            else: tr['miss'] = tr.get('miss', 0) + hrs
        tracks += [tr for tr in active if tr.get('miss', 0) > 24]; active = [tr for tr in active if tr.get('miss', 0) <= 24]
        for q, L in enumerate(lows):
            if q in used: continue
            if L['sea'] and L['depth'] >= 1.5 and 4 <= L['lat'] <= 17 and 79 <= L['lon'] <= 99:
                L = dict(L); L['t'] = t; active.append(dict(pts=[L]))
    return [tr for tr in tracks + active if len(tr['pts']) >= 3]
def ist(t): return (t + dt.timedelta(hours=5, minutes=30)).strftime('%d %b %H:%M')
OUT = dict(checked=dt.datetime.utcnow().strftime('%Y-%m-%dT%H:%MZ'), sources={})
for fn in sorted(glob.glob(os.path.join(W, 'data', 'fc_*.npz'))):
    F = Fc(fn); n = len(F.members); seg = Counter(); lats, times, pmins = [], [], []; tn_any = set(); tn_main = []
    for mi in range(n):
        main = [tr for tr in track_member(F, mi) if dt.datetime(2026, 10, 21) <= tr['pts'][0]['t'] <= dt.datetime(2026, 11, 2)
                and 5 <= tr['pts'][0]['lat'] <= 17 and tr['pts'][0]['lon'] >= 86]
        if not main: seg['no system'] += 1
        else:
            tr = max(main, key=lambda t: max(p['depth'] for p in t['pts'])); L = landfall(tr['pts']); sname = segment(L); seg[sname] += 1
            pmins.append(min(p['p'] for p in tr['pts']))
            if L and sname not in ('Bangladesh/Myanmar',): lats.append(L['lat']); times.append(L['t'])
            if sname in ('south TN', 'north TN'): tn_main.append((mi, ist(L['t']), round(L['lat'], 1), round(L['lon'], 1), round(min(p['p'] for p in tr['pts']))))
        for tr in track_weak(F, mi):
            if tr['pts'][0]['t'] < dt.datetime(2026, 10, 22): continue
            L = landfall(tr['pts'])
            if L and L['lon'] < 81.5 and L['lat'] < 13.6: tn_any.add(mi)
    r = dict(run=F.run.strftime('%Y-%m-%d %HZ'), members=n, segments={k: seg.get(k, 0) for k in ORDER},
             tn_main=len(tn_main), tn_main_detail=tn_main, tn_any_low=len(tn_any),
             lf_lat_median=round(float(np.median(lats)), 1) if lats else None, lf_lat_p20=round(float(np.percentile(lats, 20)), 1) if lats else None,
             lf_lat_min=round(float(min(lats)), 1) if lats else None,
             lf_time_median=ist(sorted(times)[len(times) // 2]) if times else None, pmin_median=round(float(np.median(pmins)), 1) if pmins else None)
    OUT['sources'][F.src] = r
    pct = lambda k: f"{k} {r['segments'][k]} ({100 * r['segments'][k] / n:.0f}%)"
    print(f"{F.src} {r['run']}: members {n} | " + ', '.join(pct(k) for k in ORDER if r['segments'][k]) +
          f" | middle landfall {r['lf_lat_median']}N (southern 20% {r['lf_lat_p20']}N, southernmost {r['lf_lat_min']}N) around {r['lf_time_median']} IST"
          f" | main system crossing TN: {r['tn_main']} | any low crossing TN: {r['tn_any_low']} | median lowest pressure {r['pmin_median']} hPa", flush=True)
H = os.path.join(W, 'data', 'tn_watch_history.json')
hist = json.load(open(H)) if os.path.exists(H) else []
hist.append(OUT); json.dump(hist, open(H, 'w'), indent=1)
