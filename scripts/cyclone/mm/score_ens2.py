"""Score the model-v2 ensemble hindcast: ensemble-mean error, spread vs error, chance given to the right coast stretch
(Brier vs climatology), CRPS-like track score, and the share of storms whose real track lies inside the ensemble."""
import sys, os, json, glob, math, numpy as np
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import ourens as O
from cyc import km, on_land
R = [r for f in sorted(glob.glob(sys.argv[1])) for r in json.load(open(f))]
H = (24, 48, 72, 96, 120)
def at(tr, h):
    for a, b in zip(tr, tr[1:]):
        if a[0] <= h <= b[0]:
            f = (h - a[0]) / max(1e-6, b[0] - a[0]); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
def seg(tr):
    for a, b in zip(tr, tr[1:]):
        if not on_land(a[2], a[1]) and on_land(b[2], b[1]): return O.segment((a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
    return 'no landfall'
ORDER = O.ORDER; clim = Counter(O.segment(*s['lf']) if s['lf'] else 'no landfall' for s in O.LIBL); pc = {k: clim[k] / len(O.LIBL) for k in ORDER}
EM, SP, CT, CR, IN = [{h: [] for h in H} for _ in range(5)]; bs, bc, inside = [], [], []
for r in R:
    tr = [m['trk'] for m in r['members'] if 'trk' in m]
    if len(tr) < 5: continue
    real = [p[:3] for p in r['real']]
    for h in H:
        tru = at(real, h); P = [at([q[:3] for q in t], h) for t in tr]; P = [p for p in P if p]
        if not tru or len(P) < len(tr) // 2: continue
        mn = (np.mean([p[0] for p in P]), np.mean([p[1] for p in P])); EM[h].append(km(mn, tru)); SP[h].append(np.mean([km(p, mn) for p in P]))
        c0 = at([q[:3] for q in tr[0]], h)
        if c0: CT[h].append(km(c0, tru))
        d = np.array([km(p, tru) for p in P]); CR[h].append(d.mean() - 0.5 * np.mean([km(a, b) for a in P for b in P]))   # CRPS-style (energy score)
        IN[h].append(km(mn, tru) <= np.percentile([km(p, mn) for p in P], 90))
    segs = [seg([q[:3] for q in t]) for t in tr]; c = Counter(segs); n = len(segs); p = {k: c[k] / n for k in ORDER}
    bs.append(sum((p[k] - (k == r['truth'])) ** 2 for k in ORDER)); bc.append(sum((pc[k] - (k == r['truth'])) ** 2 for k in ORDER)); inside.append(c[r['truth']] > 0)
print(f'storms {len(bs)}; members per storm ~{np.median([len(r["members"]) for r in R]):.0f}')
for h in H:
    if EM[h]: print(f'{h:3d}h  ensemble mean {np.median(EM[h]):4.0f} km | control {np.median(CT[h]):4.0f} | spread {np.median(SP[h]):4.0f} (spread/error {np.mean(SP[h]) / np.mean(EM[h]):.2f}) | CRPS-like {np.median(CR[h]):4.0f} | truth inside 90% circle {np.mean(IN[h]):.0%}  (n={len(EM[h])})')
print(f'coast stretch: Brier {np.mean(bs):.3f} vs climatology {np.mean(bc):.3f} -> skill {1 - np.mean(bs) / np.mean(bc):+.0%}; real stretch among members {np.mean(inside):.0%}')
