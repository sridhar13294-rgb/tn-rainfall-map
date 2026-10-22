"""Compare past-storm test results on the SAME storms and leads.
python score_hind.py [--tune|--final] 'GLOB:VARIANT' 'GLOB:VARIANT' ...      (VARIANT optional = all variants in the files)
--tune: only 2000-2017 storms (all setting choices are made on these); --final: only 2018-2025 (the held-back exam, used
once at the end so the score is honest).
Track error (km) against the best track at 0/24/48/72/96/120 h: median and mean over the cases every set has."""
import sys, os, json, glob, math, numpy as np
def km(a, b): return math.hypot(a[0] - b[0], (a[1] - b[1]) * math.cos(math.radians((a[0] + b[0]) / 2))) * 111.2
def at(tr, h):
    for a, b in zip(tr, tr[1:]):
        if a[0] <= h <= b[0]:
            f = (h - a[0]) / max(1e-6, b[0] - a[0]); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
H = (0, 24, 48, 72, 96, 120); sets = {}
SPLIT = [a for a in sys.argv[1:] if a.startswith('--')]; ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
keep = (lambda y: y <= 2017) if '--tune' in SPLIT else (lambda y: y >= 2018) if '--final' in SPLIT else (lambda y: True)
BAS = next((a.split('=')[1].split(',') for a in SPLIT if a.startswith('--basin=')), None)     # e.g. --basin=AS,SI
for arg in ARGS:
    g, _, var = arg.partition(':')
    for f in sorted(glob.glob(g)):
        for r in json.load(open(f)):
            if 'trk' not in r or (var and r.get('var') != var) or not keep(int(r['season'])) or (BAS and r.get('basin', 'BB') not in BAS): continue
            sets.setdefault(r.get('var', g), {})[(r['name'], r['season'], r['t0'])] = r
names = list(sets); print('sets:', {n: len(v) for n, v in sets.items()})
for h in H:
    common = None
    for n in names:
        ks = {k for k, r in sets[n].items() if at([t[:3] for t in r['trk']], h) and at([p[:3] for p in r['real']], h)}
        common = ks if common is None else common & ks
    if not common: continue
    row = []
    for n in names:
        e = [km(at([t[:3] for t in sets[n][k]['trk']], h), at([p[:3] for p in sets[n][k]['real']], h)) for k in common]
        row.append(f'{n} {np.median(e):4.0f}/{np.mean(e):4.0f}')
    print(f'{h:3d}h n={len(common):2d}  ' + ' | '.join(row) + '   (median/mean km)')
