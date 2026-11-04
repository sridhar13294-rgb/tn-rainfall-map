"""Score one candidate's standard suite (scripts/cyclone/suite.sh NAME) against the control on the Stage-1 acceptance criteria.
python scripts/cyclone/score_suite.py NAME   -> table of criteria with PASS / FAIL / pending, written to data/cyclone/suite_NAME.json"""
import glob, json, math, os, re, sys
import numpy as np
K = 'data/cyclone/kaggle/'; N = sys.argv[1]; R = {}
BASE = os.environ.get('BASE', 'ctl2')   # same-code control suite (4 Nov: round-off alone moves noisy metrics; never compare with an older-code control)
dist = lambda a, b, c, d: 111.2 * math.hypot(a - c, ((b - d + 180) % 360 - 180) * math.cos(math.radians((a + c) / 2)))
def have(slug, pat): f = glob.glob(K + slug + '/' + pat); return f[0] if f else None
def exam(prefix):
    Z, rows, fail = {}, [], 0
    for q in range(4):
        lg = have(f'{prefix}{q}', 'kernel_wx_*.log'); js = have(f'{prefix}{q}', 'wx_*.json')
        if not lg or not js: return None
        for l in open(lg).read().replace('\\n', '\n').split('\n'):
            m = re.search(r'(\d{4}-\d\d-\d\d) \S+ sec \d+ z500 rmse d1/d5/d10 \[([\d.]+), ([\d.]+), ([\d.]+)\]', l)
            if m: Z[m.group(1)] = [float(x) for x in m.groups()[1:]]
            if 'FAILED' in l: fail += 1
        rows += json.load(open(js))
    return Z, rows, fail
def tnu(rows):
    X = [r for r in rows if r['start'][5:7] in ('10', '11', '12')]
    return float(np.mean([r['days']['5']['u850']['tamil_nadu']['bias'] for r in X])) if X else None
def gen(slug, var):
    f = have(slug, 'gen_*.json')
    if not f: return None
    rr = [r for r in json.load(open(f)) if var in r['runs'] and 'dist' in r['runs'][var]]
    return 100 * sum(1 for r in rr if r['runs'][var]['dist'] <= 300 and r['runs'][var]['vo'] >= 5 and r['runs'][var]['depth'] >= 2) / max(len(rr), 1)
def tnr(slug):
    f = have(slug, 'kernel_tnr.log')
    if not f: return None
    m = t = 0
    for l in open(f).read().replace('\\n', '\n').split('\n'):
        for _, a, b in re.findall(r'\((\d), ([\d.]+), ([\d.]+)\)', l): m += float(a); t += float(b)
    return m / t if t else None
def q6(slug):
    f = have(slug, 'q6.json')
    if not f: return None
    e = {24: [], 48: [], 72: []}; south = []
    for r in json.load(open(f)):
        real = {p[0]: p for p in r['real']}; prev = None; ok = True
        for p in r['trk']:
            if prev and dist(prev[0], prev[1], p[1], p[2]) > 250: ok = False
            prev = (p[1], p[2])
            if ok and p[0] in e and float(p[0]) in real:
                e[p[0]].append(dist(real[float(p[0])][1], real[float(p[0])][2], p[1], p[2]))
                if p[0] == 72: south.append(p[1] - real[72.0][1])
    return {h: float(np.mean(v)) if v else None for h, v in e.items()}, (float(np.mean(south)) if south else None)
def evo(slug):
    f = have(slug, 'prof.json')
    if not f: return None
    J = list(json.load(open(f)).values())[0]
    T = np.mean([j['d5']['tropics']['T'] for j in J], 0); q = np.mean([j['d5']['tropics']['q'] for j in J], 0) * 1e3
    return dict(T850=float(T[10]), T925=float(T[11]), T1000=float(T[12]), q850=float(q[10]))
def sb(slug):
    f = have(slug, 'sb*.json')
    if not f: return None
    T = json.load(open('data/cyclone/era5_p3_targets.json')); out = {}
    for r in json.load(open(f)):
        x = {k['h']: k for k in r['rows']}
        if 72 in x: out[r['name']] = dict(pmin=x[72]['pmin'], v850=x[72]['vmax850'], target_p=T[r['name']]['72']['msl_min'], target_v=T[r['name']]['72']['v850_smooth'])
    return out
# ---------------- criteria
c_ex, s_ex = exam(f'tn-s-{BASE}-wx'), exam(f'tn-s-{N}-wx')
if s_ex:
    common = sorted(set(c_ex[0]) & set(s_ex[0])); A = np.mean([s_ex[0][x] for x in common], 0); B = np.mean([c_ex[0][x] for x in common], 0)
    R['1 forecast z500 d5/d10'] = dict(cand=A[1:].round(1).tolist(), ctl=B[1:].round(1).tolist(), ok=bool(A[1] <= B[1] and A[2] <= B[2]))
    R['8a stability: exam starts complete'] = dict(cand=len(s_ex[0]), failed=s_ex[2], ok=s_ex[2] == 0 and len(s_ex[0]) >= 73)
    u = tnu(s_ex[1]); R['7 steering Oct-Dec TN u850 d5 bias'] = dict(cand=u, ctl=tnu(c_ex[1]), ok=bool(u is not None and abs(u) < abs(tnu(c_ex[1]))))
e = evo(f'tn-s-{N}-evo')
if e: R['2 low-level T / q850 (d5 tropics)'] = dict(cand=e, ok=bool(all(abs(e[k]) <= 1.5 for k in ('T850', 'T925', 'T1000')) and abs(e['q850']) <= 0.5))
s = sb(f'tn-s-{N}-sb')
if s: R['3 cyclone intensity vs ERA5 (+-5 hPa)'] = dict(cand=s, ok=all(abs(v['pmin'] - v['target_p']) <= 5 for v in s.values()))
q, qc = q6(f'tn-s-{N}-q6'), q6(f'tn-s-{BASE}-q6')
if q: R['4 tracks quick6 72 h (km), mean 72 h lat error'] = dict(cand=q[0], ctl=qc[0], south=q[1], ok=bool(q[0][72] is not None and q[0][72] <= qc[0][72] and (q[1] or 0) > -1.0))
g0, g1 = gen(f'tn-s-{N}-gen0', f'T170_{N}'), gen(f'tn-s-{N}-gen1', f'T170_{N}')
c0, c1 = gen(f'tn-s-{BASE}-gen0', f'T170_{BASE}'), gen(f'tn-s-{BASE}-gen1', f'T170_{BASE}')
if g0 is not None and g1 is not None: R['5 genesis gen0/gen1 %'] = dict(cand=[round(g0), round(g1)], ctl=[round(c0), round(c1)], ok=g0 >= c0 and g1 >= c1)
t = tnr(f'tn-s-{N}-tnr')
if t: R['6 TN rain 5-day ratio'] = dict(cand=round(t, 2), ctl=round(tnr(f'tn-s-{BASE}-tnr'), 2), ok=abs(t - 1) <= 0.25)
names = ['1 forecast z500 d5/d10', '2 low-level T / q850 (d5 tropics)', '3 cyclone intensity vs ERA5 (+-5 hPa)', '4 tracks quick6 72 h (km), mean 72 h lat error',
         '5 genesis gen0/gen1 %', '6 TN rain 5-day ratio', '7 steering Oct-Dec TN u850 d5 bias', '8a stability: exam starts complete']
for n in names:
    r = R.get(n); print(f"{n:48s} {'pending' if r is None else ('PASS' if r['ok'] else 'FAIL'):8s} {'' if r is None else {k: v for k, v in r.items() if k != 'ok'}}")
json.dump(dict(R, baseline=BASE), open(f'data/cyclone/suite_{N}.json', 'w'), indent=1, default=float)
