"""Combine exp_tc2.py chunks: score per config."""
import sys, os, json, glob, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
R = [r for f in sorted(glob.glob(sys.argv[1])) for r in json.load(open(f))]
names = sorted({k for r in R for k in r['runs']})
for nm in names:
    hit, E, S, TE = [], [], [], {h: [] for h in ('24', '48', '72', '96')}
    for r in R:
        x = r['runs'].get(nm)
        if not x or 'err' in x: continue
        hit.append(x['seg'] == r['truth'])
        if x['lf'] and r['truth_lf'] and r['truth_lf'][1] < 89 and x['lf'][1] < 89: E.append(abs(x['lf'][0] - r['truth_lf'][0])); S.append(x['lf'][0] - r['truth_lf'][0])
        for h, v in x['te'].items(): TE[str(int(float(h)))].append(v)
    print(f"{nm:28s} n={len(hit)} right stretch {np.mean(hit):.0%} | lat err {np.median(E):.1f} bias {np.mean(S):+.1f} | track err " + ' '.join(f"{h}h {np.median(v):.0f}" for h, v in TE.items() if v))
