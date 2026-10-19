import sys, json, pickle, glob, os; sys.path.insert(0, '.')
from cyc import *
OUT = {}
for fn in sorted(glob.glob('data/fc_*.npz')):
    F = Fc(fn); res = []
    for mi, m in enumerate(F.members):
        trs = track_member(F, mi)
        # the Bay system of interest: forms 20-28 Oct east of 85E, south of 17N
        cand = [tr for tr in trs if dt.datetime(2026, 10, 20) <= tr['pts'][0]['t'] <= dt.datetime(2026, 10, 30) and tr['pts'][0]['lon'] >= 85 and tr['pts'][0]['lat'] <= 17]
        if not cand: res.append(None); continue
        tr = max(cand, key=lambda t: max(p['depth'] for p in t['pts']))
        res.append(dict(pts=[dict(t=p['t'].isoformat(), lat=p['lat'], lon=p['lon'], p=p['p'], depth=p['depth'], vo=p['vo'], s=p['s']) for p in tr['pts']],
                        lf=(lambda L: dict(t=L['t'].isoformat(), lat=L['lat'], lon=L['lon']) if L else None)(landfall(tr['pts']))))
    OUT[F.src] = dict(run=F.run.isoformat(), n=len(F.members), tracks=res)
    n = sum(r is not None for r in res); print(F.src, F.run, 'members with the system', n, 'of', len(res), flush=True)
json.dump(OUT, open('data/tracks.json', 'w'))
