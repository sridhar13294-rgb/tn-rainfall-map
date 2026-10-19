import json, sys, datetime as dt, numpy as np
sys.path.insert(0, '.')
from analogs import storms, score, NAMES
C = json.load(open('data/consensus.json'))
cen = {c['h']: (c['lat'], c['lon']) for c in C['central']}
T = dict(t0=dt.datetime.fromisoformat(C['genesis']['t']), gen=(C['genesis']['lat'], C['genesis']['lon']),
         track={h: cen.get(h) for h in (24, 48, 72, 96, 120)}, cat='SCS', mjo=(5, 0.83), oni=2.3, dmi=0.6)
S = storms(); print('storms with depression stage', len(S))
R = score(S, T)
rows = []
for r in R[:25]:
    s = r['s']; c = r['c']
    rows.append(dict(name=s['name'], season=s['season'], sid=s['sid'], t0=s['t0'].strftime('%d %b %Y'), gen=[round(x, 1) for x in s['gen']], cat=s['cat'], peak=s['peak'], pmin=s['pmin'],
                     land=s['land_region'], lf=s['landfall'], mjo=s['mjo'], oni=s['oni'], dmi=s['dmi'], total=round(r['total'], 2), phys=round(r['phys'], 2), bg=round(r['bg'], 2),
                     c={k: round(v, 2) for k, v in c.items()}, path=s['path']))
    print(f"{s['name']:12} {s['season']} {s['t0']:%d %b} gen {s['gen'][0]:.1f},{s['gen'][1]:.1f} {s['cat']:5} peak {s['peak']} land {s['land_region']:12} MJO {s['mjo']} ONI {s['oni']} DMI {s['dmi']} | total {r['total']:.2f} phys {r['phys']:.2f} bg {r['bg']:.2f} {{{', '.join(f'{k}:{v:.2f}' for k, v in c.items())}}}")
# physical-only ranking too
P = sorted(R, key=lambda r: r['phys'])[:10]
print('--- physical only (timing, genesis, track, intensity)')
for r in P: s = r['s']; print(f"{s['name']:12} {s['season']} {s['t0']:%d %b} {s['cat']} {s['land_region']} phys {r['phys']:.2f} bg {r['bg']:.2f} ONI {s['oni']} DMI {s['dmi']} MJO {s['mjo']}")
json.dump(dict(target=dict(t0=T['t0'].isoformat(), gen=T['gen'], track=T['track'], cat=T['cat'], mjo=T['mjo'], oni=T['oni'], dmi=T['dmi']), top=rows,
               phys=[dict(name=r['s']['name'], season=r['s']['season'], phys=r['phys'], bg=r['bg']) for r in P]), open('data/analogs.json', 'w'), default=str)
