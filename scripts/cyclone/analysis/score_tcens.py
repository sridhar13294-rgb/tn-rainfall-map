"""Combine the chunks of hind_tcens.py and print the ensemble's score."""
import sys, os, json, glob, numpy as np
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O
from cyc import km
R = [r for f in sorted(glob.glob(sys.argv[1])) for r in json.load(open(f))]
ORDER = O.ORDER; clim = Counter(O.segment(*s['lf']) if s['lf'] else 'no landfall' for s in O.LIBL); pc = {k: clim[k] / len(O.LIBL) for k in ORDER}
bs, bc, pt, pct, mode, inside, ctl, latE, latS, spr = [], [], [], [], [], [], [], [], [], []
TE = {h: [] for h in (24, 48, 72, 96, 120)}; CE = {h: [] for h in TE}; SP = {h: [] for h in TE}
for r in R:
    segs = [m['seg'] for m in r['members']]; c = Counter(segs); n = len(segs); p = {k: c[k] / n for k in ORDER}
    bs.append(sum((p[k] - (k == r['truth'])) ** 2 for k in ORDER)); bc.append(sum((pc[k] - (k == r['truth'])) ** 2 for k in ORDER))
    pt.append(p[r['truth']]); pct.append(pc[r['truth']]); mode.append(c.most_common(1)[0][0] == r['truth']); inside.append(c[r['truth']] > 0); ctl.append(segs[0] == r['truth'])
    L = [m['lf'][0] for m in r['members'] if m['lf'] and m['lf'][1] < 89]
    if r['truth_lf'] and r['truth_lf'][1] < 89 and L: latE.append(abs(np.median(L) - r['truth_lf'][0])); latS.append(np.median(L) - r['truth_lf'][0])
    for h in TE:
        rp = r['real'].get(str(h)) or r['real'].get(h)
        P = [m['pos'].get(str(h)) or m['pos'].get(h) for m in r['members']]; P = [x for x in P if x]
        if rp and len(P) >= 26:
            mean = (np.mean([x[0] for x in P]), np.mean([x[1] for x in P])); TE[h].append(km(mean, rp)); SP[h].append(np.mean([km(x, mean) for x in P]))
            c0 = r['members'][0]['pos'].get(str(h)) or r['members'][0]['pos'].get(h)
            if c0: CE[h].append(km(c0, rp))
print(f'PHYSICS ENSEMBLE, {len(R)} past storms x 51 members')
print(f'  chance given to the coast stretch that happened: {np.mean(pt):.0%} (climatology {np.mean(pct):.0%})')
print(f'  Brier: {np.mean(bs):.3f} vs climatology {np.mean(bc):.3f} -> skill {1 - np.mean(bs) / np.mean(bc):+.0%}')
print(f'  most-common outcome right {np.mean(mode):.0%} | control right {np.mean(ctl):.0%} | real outcome inside the 51 members {np.mean(inside):.0%}')
print(f'  middle landfall latitude error {np.median(latE):.1f} deg, bias {np.mean(latS):+.1f} deg (n={len(latE)})')
for h in TE: print(f'  {h} h: ensemble-mean track error {np.median(TE[h]):.0f} km (n={len(TE[h])}), control {np.median(CE[h]):.0f} km, spread {np.median(SP[h]):.0f} km')
