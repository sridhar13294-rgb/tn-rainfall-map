import sys, json, glob, math, datetime as dt, numpy as np
sys.path.insert(0, '.')
from cyc import Fc, on_land
import ourtrack
T = json.load(open('data/tracks.json')); OUT = {}
for fn in sorted(glob.glob('data/fc_*.npz')):
    F = Fc(fn); src = F.src
    if src not in T: continue
    res = []
    for mi, tr in enumerate(T[src]['tracks']):
        if not tr: res.append(None); continue
        p0 = tr['pts'][0]; s0 = p0['s']
        prev = (0.0, 0.0)
        if len(tr['pts']) >= 2:
            p1 = tr['pts'][1]; h = (dt.datetime.fromisoformat(p1['t']) - dt.datetime.fromisoformat(p0['t'])).total_seconds() / 3600
            prev = ((p1['lon'] - p0['lon']) * 111.2 * math.cos(math.radians(p0['lat'])) / h, (p1['lat'] - p0['lat']) * 111.2 / h)
        pts = ourtrack.run(F, mi, s0, p0['lat'], p0['lon'], prev)
        lf = None
        for a, b in zip(pts, pts[1:]):
            if not on_land(a['lon'], a['lat']) and on_land(b['lon'], b['lat']):
                lf = dict(t=(a['t'] + (b['t'] - a['t']) / 2).isoformat(), lat=(a['lat'] + b['lat']) / 2, lon=(a['lon'] + b['lon']) / 2); break
        res.append(dict(pts=[dict(t=p['t'].isoformat(), lat=round(p['lat'], 2), lon=round(p['lon'], 2)) for p in pts], lf=lf))
    OUT[src] = res; print(src, sum(r is not None for r in res), flush=True)
json.dump(OUT, open('data/ours.json', 'w'))
