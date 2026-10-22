"""Same-storm, same-start comparison of our model with ECMWF and NCEP (TIGGE tracks).
python score_vs_tigge.py OUR_GLOB VARIANT [ENS_GLOB]
Track errors against the best track at 24/48/72/96/120 h, only where both models have a forecast for that storm and lead."""
import sys, os, json, glob, math, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
from cyc import km
REPO = os.path.join(HERE, '..', '..', '..')
TG = json.load(open(os.path.join(REPO, 'data', 'cyclone', 'tigge_tracks.json')))
OUR = [r for f in sorted(glob.glob(sys.argv[1])) for r in json.load(open(f)) if r.get('var') == sys.argv[2] and 'trk' in r]
ENS = [r for f in sorted(glob.glob(sys.argv[3])) for r in json.load(open(f))] if len(sys.argv) > 3 else []
H = (24, 48, 72, 96, 120)
def at(tr, h):
    for a, b in zip(tr, tr[1:]):
        if a[0] <= h <= b[0]:
            f = (h - a[0]) / max(1e-6, b[0] - a[0]); return (a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2]))
    return None
def mean_at(trs, h, need):
    P = [at(t, h) for t in trs]; P = [p for p in P if p]
    if len(P) < need: return None, None, 0
    m = (float(np.mean([p[0] for p in P])), float(np.mean([p[1] for p in P]))); return m, float(np.mean([km(p, m) for p in P])), len(P)
rows = {}
for r in OUR:
    key = f"{r['name']}|{r['season']}|{r['t0']}"
    if key not in TG: continue
    real = [p[:3] for p in r['real']]; T = TG[key]
    for h in H:
        tru = at(real, h)
        if not tru: continue
        cand = {}
        x = at([t[:3] for t in r['trk']], h); cand['ours control'] = x
        e = next((e for e in ENS if f"{e['name']}|{e['season']}|{e['t0']}" == key), None)
        if e:
            m, s, n = mean_at([[q[:3] for q in mm['trk']] for mm in e['members'] if 'trk' in mm], h, 5); cand['ours ens mean'] = m
        ec = T.get('ECMWF', {}).get('members', {}); ge = T.get('GEFS', {}).get('members', {})
        le = T.get('ECMWF', {}).get('lag', 0.0) or 0.0; lg = T.get('GEFS', {}).get('lag', 0.0) or 0.0     # their run started lag h before ours
        ecm = [v for k, v in ec.items() if k.startswith('m') and k != 'm0']
        if ecm: cand['ECMWF ens mean'] = mean_at([[q[:3] for q in v] for v in ecm], h + le, 10)[0]
        det = [v for k, v in ec.items() if k.startswith('det')]
        if det: cand['ECMWF HRES'] = at([q[:3] for q in det[0]], h + le)
        gm = [v for k, v in ge.items() if k.startswith('m') and k != 'm0' and not k.startswith('GFS')]
        if gm: cand['GEFS mean'] = mean_at([[q[:3] for q in v] for v in gm], h + lg, 5)[0]
        gd = [v for k, v in ge.items() if k.startswith('GFS-det')]
        if gd: cand['GFS'] = at([q[:3] for q in gd[0]], h + lg)
        rows.setdefault(h, []).append((key, {k: (km(v, tru) if v else None) for k, v in cand.items()}))
for ref in ('ECMWF ens mean', 'ECMWF HRES', 'GEFS mean', 'GFS'):
    print(f'--- storms where {ref} exists (same storms, same leads)')
    for h in H:
        R = [d for _, d in rows.get(h, []) if d.get(ref) is not None and d.get('ours control') is not None]
        if len(R) < 3: continue
        line = f'{h:3d}h n={len(R):2d} ' + ' | '.join(f"{k} {np.median([d[k] for d in R if d.get(k) is not None]):4.0f}" for k in ('ours control', 'ours ens mean', ref) if any(d.get(k) is not None for d in R))
        o = np.median([d['ours control'] for d in R]); rf = np.median([d[ref] for d in R])
        print(line + f'   ours/{ref} = {o / max(rf, 1):.2f}')
