import json, numpy as np, sys
T = json.load(open('data/cyclone/wx/peak_targets.json'))
rows = []
for f in sys.argv[1:]: rows += json.load(open(f))
out = []
for r in rows:
    k = f"{r['name']}|{r['t0']}"
    if k not in T: out.append((k, None, None, 'no target')); continue
    tg = min(v['msl_min'] for h, v in T[k]['rows'].items() if float(h) <= 72 and v.get('msl_min') is not None)
    tr = [p for p in (r.get('trk') or []) if p[0] <= 72]
    if not tr: out.append((k, tg, None, 'lost')); continue
    mp = min(p[4] for p in tr); out.append((k, tg, mp, ''))
ok = [o for o in out if o[2] is not None]; err = np.array([o[2] - o[1] for o in ok])
for o in sorted(out, key=lambda o: (o[2] - o[1]) if o[2] else 99): print(f"{o[0]:32s} ERA5 {o[1]} model {o[2]} {'' if o[2] is None else round(o[2]-o[1],1)} {o[3]}")
n = len(out); w = int((np.abs(err) <= 5).sum())
print(f"N={n} scored={len(ok)} within+-5={w} ({100*w/n:.0f}% of all) mean err {err.mean():+.2f} mean|err| {np.abs(err).mean():.2f} median {np.median(err):+.2f}")
print('too weak (>+5):', int((err > 5).sum()), ' too deep (<-5):', int((err < -5).sum()))
