"""General weather exam table: our model vs ECMWF HRES on the same 2020 starts, by variable, region and day.
python score_wx.py OUR_GLOB [VARIANT] [HRES_JSON]
Prints RMSE (and ACC where a climate exists) averaged over the starts both have, plus ours/ECMWF ratio of RMSE."""
import sys, json, glob, numpy as np
OUR = [r for f in sorted(glob.glob(sys.argv[1])) for r in json.load(open(f)) if 'days' in r and (len(sys.argv) < 3 or not sys.argv[2] or r['var'] == sys.argv[2])]
H = json.load(open(sys.argv[3] if len(sys.argv) > 3 else 'data/cyclone/wx/hres_2020_scores.json'))['results']
HB = {r['start']: r for r in H}
for kk, reg in (('z500', 'globe'), ('z500', 'n_extratropics'), ('z500', 'tropics'), ('t850', 'globe'), ('t850', 'india'), ('mslp', 'globe'),
                ('t2', 'india'), ('rain24', 'india'), ('rain24', 'tamil_nadu'), ('u850', 'india'), ('u200', 'tropics')):
    line = []
    for d in (1, 3, 5, 7, 10):
        o, h, oa, ha = [], [], [], []
        for r in OUR:
            hr = HB.get(r['start']); a = r['days'].get(str(d), r['days'].get(d, {})).get(kk, {}).get(reg)
            b = (hr or {}).get('days', {}).get(str(d), {}).get(kk, {}).get(reg) if hr else None
            if a and b: o.append(a['rmse']); h.append(b['rmse']); oa.append(a.get('acc')); ha.append(b.get('acc'))
        if o:
            acc = '' if None in oa + ha else f' acc {np.mean(oa):.2f}/{np.mean(ha):.2f}'
            line.append(f'd{d}: {np.mean(o):.4g}/{np.mean(h):.4g} ({np.mean(o) / np.mean(h):.2f}x){acc}')
    if line: print(f'{kk:6s} {reg:15s} n={len(o):2d}  ' + ' | '.join(line))
print('(ours/ECMWF RMSE; acc ours/ECMWF)')
# Indian rain regions (ours only - the archived ECMWF scores do not have these regions): rmse / bias / acc
for reg in ('india_nw', 'india_central', 'india_ne', 'india_south', 'west_coast', 'tamil_nadu', 'india'):
    line = []
    for d in (1, 3, 5, 7, 10):
        xs = [r['days'].get(str(d), r['days'].get(d, {})).get('rain24', {}).get(reg) for r in OUR]; xs = [x for x in xs if x]
        if xs:
            ac = [x.get('acc') for x in xs if x.get('acc') is not None]
            line.append(f"d{d}: rmse {np.mean([x['rmse'] for x in xs]):.2f} bias {np.mean([x['bias'] for x in xs]):+.2f}" + (f" acc {np.mean(ac):.2f}" if ac else ''))
    if line: print(f'rain24 {reg:15s} n={len(xs):2d}  ' + ' | '.join(line))
