"""Our own 51-member scenario ensemble (no forecast model, no past-storm winds).
python ours_live_s.py LIVE_NPZ SST_JSON LIVE_INPUTS_JSON OUT_JSON
Member 0: today's observed environment held. Members 1-50: seven storylines of how the environment could change from
today (ridge holds / weakens / breaks / breaks and rebuilds, westerly trough pulls the storm, the storm pushes the ridge,
a weak sheared system), each given a share of the 50 members from the current state and from what similar storms did
in similar climate states (El Nino, positive IOD, active MJO). Within a storyline the timing, strength, formation,
start position, sea temperature, shear and storm size are spread evenly with a fixed Halton sequence."""
import sys, os, json, math, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S, live_env_s as ES
from ours_live import detect, ridge_now, MJO_STATE, SEGS
def halton(i, b):
    f, r = 1.0, 0.0
    while i > 0: f /= b; r += f * (i % b); i //= b
    return r
# storylines: key, name, members, what happens, schedules (days from the analysis)
STORIES = [
 ('hold', 'Ridge holds, monsoon easterlies persist', 9,
  'The ridge stays near its present latitude and the north-east monsoon easterlies keep or gain strength. The system stays weak to moderate and is carried west.',
  dict(east_scale=[(0, 1.0), (5, 1.1)], surge=[(0, 0), (1, -1.5), (5, -2.5)], ridge_shift=0, erosion=0.0, shear=1.0, sst=0.0)),
 ('weaken', 'Ridge weakens slowly, no full break', 10,
  'The easterlies ease over 3-5 days and the ridge edges north. The system slows and bends north-west into Andhra Pradesh.',
  dict(east_scale=[(0, 1.0), (2, 0.8), (4, 0.6), (6, 0.5)], ridge_shift=[(0, 0), (5, 1.5)], wd_amp=4, wd_day80=5, wd_reach=20, erosion=0.5, shear=1.0, sst=0.0)),
 ('break', 'Westerly trough breaks the ridge (day 2-3)', 8,
  'A western disturbance digs south and opens a gap in the ridge over the central Bay; south-westerlies set in and the storm turns north.',
  dict(east_scale=[(0, 1.0), (3, 0.7)], break_=[(0, 0), (1.5, 0), (3, 5), (6, 6)], wd_amp=7, wd_day80=3.5, wd_reach=16, erosion=1.0, shear=1.0, sst=0.0)),
 ('pull', 'Deep trough pulls a fast-strengthening storm', 8,
  'The system strengthens quickly over the warm Bay (active MJO), a deep trough arrives early and the storm is pulled north-north-east (Hamoon-type).',
  dict(east_scale=[(0, 1.0), (2, 0.6)], break_=[(0, 0), (1, 0), (2.5, 7), (6, 8)], wd_amp=10, wd_day80=2.75, wd_reach=13, erosion=1.5, shear=0.75, sst=0.2, gen=12, size=1.2)),
 ('rebuild', 'Ridge breaks, then rebuilds', 7,
  'A brief break stalls the storm in mid-Bay; the ridge then rebuilds behind the trough and pushes it west again (Michaung / Nivar-type).',
  dict(east_scale=[(0, 1.0), (2, 0.6), (4, 0.6), (5.5, 1.1)], break_=[(0, 0), (2, 5), (3.5, 5), (5, 0)], wd_amp=5, wd_day80=3, wd_reach=17, erosion=0.5, shear=1.0, sst=0.0)),
 ('push', 'Strong storm pushes the ridge', 4,
  'No trough needed: the system becomes very severe and its own outflow erodes the ridge, so it drifts north under its own weight.',
  dict(east_scale=[(0, 1.0), (4, 0.8)], erosion=2.5, shear=0.75, sst=0.2, size=1.3, gen=12)),
 ('weak', 'Weak, sheared system', 4,
  'Dry air and shear keep it a depression; it follows the low-level easterlies with a southward push and may die at sea.',
  dict(east_scale=[(0, 1.0), (4, 1.15)], surge=[(0, 0), (1, -2), (5, -3)], ridge_shift=[(0, 0), (5, -1.0)], shear=1.5, sst=-0.2, gen=54))]
def vary(story, j, n, t0, sd, obs, k=None, gen0=None):
    """member j (1..n) of a storyline: spread timing, strength, formation, start, SST, shear, size evenly (Halton)."""
    key, name, _, _, base = story; k = k if k is not None else j + 7 * (STORIES.index(story) + 1)
    h = lambda b: halton(k, b)
    ts = (h(2) - 0.5) * 1.5                                    # whole storyline earlier/later by up to 0.75 day
    mag = 0.75 + 0.5 * h(3)                                    # how strongly it happens: 75-125%
    def S_(s, neutral):
        if s is None or not isinstance(s, (list, tuple)): return s if s is None else neutral + (s - neutral) * mag
        return [(max(0.0, a + ts), neutral + (v - neutral) * mag) for a, v in s]
    gen = (gen0 if gen0 is not None and 'gen' not in base else base.get('gen', 30)) + (h(5) - 0.5) * 24
    P = dict(member=None, story=key, start_t=t0, start_lat=round(sd[0] + (h(7) - 0.5) * 1.6, 2), start_lon=round(sd[1] + (h(11) - 0.5) * 2.4, 2),
             gen_t=t0 + dt.timedelta(hours=0 if obs['formed'] else round(max(6, gen))), gen_lat=None, gen_lon=None,
             east_scale=S_(base.get('east_scale'), 1.0), surge=S_(base.get('surge'), 0.0), ridge_shift=S_(base.get('ridge_shift'), 0.0),
             wd_amp=(base.get('wd_amp', 0) * mag), wd_day80=base.get('wd_day80', 5) + ts, wd_reach=base.get('wd_reach', 18), wd_speed=8.0,
             erosion=base.get('erosion', 0) * mag, mjo=obs['mjo_u'], mjo_kt=obs['mjo_kt'], mjo_i=0,
             sst=round(obs['sst'] + base.get('sst', 0) + (h(13) - 0.5) * 0.3, 2), shear_scale=round(base.get('shear', 1.0) * (0.9 + 0.2 * h(17)), 2), shear=None,
             beta=round(base.get('size', 1.0) * (0.9 + 0.2 * h(19)), 2), speed=1.0, timing=round(ts, 2), magnitude=round(mag, 2))
    P['break'] = S_(base.get('break_'), 0.0)
    if obs['formed']: P['start_v'] = 17.0
    return P
def precursors(fn, south):
    """the circulations that could become the depression: the strongest low-level swirl (south), a circulation in the
    north Andaman Sea / east-central Bay (north) and the pressure dip between them (merge)."""
    Z = np.load(fn); V = [str(v) for v in Z['vars']]; X = Z['data'][0, 0].astype(float); la, lo = Z['lats'], Z['lons']
    res = float(la[1] - la[0]); dy = res * 111e3; dx = dy * np.cos(np.radians(la))[:, None]
    vo = lambda l: nd.uniform_filter((np.gradient(X[V.index('v' + l)], axis=1) / dx - np.gradient(X[V.index('u' + l)], axis=0) / dy) * 1e5, int(round(3.5 / res)) | 1)
    v = (vo('850') + vo('700') + vo('500')) / 3; p = nd.uniform_filter(X[V.index('msl')], 5); LA, LO = np.meshgrid(la, lo, indexing='ij')
    from cyc import on_land
    sea = np.vectorize(lambda a, b: not on_land(b, a))
    def best(score, box):
        k = (LA >= box[0]) & (LA <= box[1]) & (LO >= box[2]) & (LO <= box[3]); k &= sea(LA, LO)
        j = np.unravel_index(np.argmax(np.where(k, score, -1e9)), score.shape); return float(la[j[0]]), float(lo[j[1]])
    n = best(vo('500'), (14, 19, 86, 96)); m = best(-p, (10.5, 14.5, 86, 91.5))     # north: mid-level circulation in the east-central Bay
    return dict(south=dict(lat=south[0], lon=south[1], note='strongest low-level swirl now (south Andaman Sea)'),
                north=dict(lat=n[0], lon=n[1], note='mid-level circulation in the east-central Bay (the area IMD and the models expect the low in)'),
                merge=dict(lat=m[0], lon=m[1], note='the two merge at the pressure dip between them'))
PREC_SHARE = dict(south=16, north=17, merge=17)       # members out of 50 (see the page for the reasoning)
if __name__ == '__main__':
    LIVE, SSTJ, LIJ, OUTJ = sys.argv[1:5]
    t0 = dt.datetime.strptime(str(np.load(LIVE)['run']), '%Y%m%d%H')
    obs = detect(LIVE); b = obs['bay']; obs['formed'] = bool(b['vort850'] >= 7.0 and b['depth'] >= 2.5)
    sst = json.load(open(SSTJ)); k = sorted(sst)[-1]; obs['sst'] = float(sst[k]['bob']); obs['sst_date'] = k
    rows = json.load(open(LIJ)).get('mjo', {}).get('rows', [])
    if rows:
        r = rows[-1]; mu, mk, lab = MJO_STATE(r['phase'], r['amp']); obs.update(mjo_u=mu, mjo_kt=mk, mjo_label=lab, mjo_date=r['date'], mjo_phase=r['phase'], mjo_amp=r['amp'])
    else: obs.update(mjo_u=0.0, mjo_kt=0.0, mjo_label='unknown (no MJO data)', mjo_date=None)
    obs['ridge'] = ridge_now(LIVE)
    M = S.train(); sd = (b['lat'], b['lon'])
    PR = precursors(LIVE, sd); obs['precursors'] = PR
    F0 = S.ana_raw(LIVE); FB = {k: S.remove_vortex(F0, v['lat'], v['lon']) for k, v in PR.items()}; Fb = FB['south']
    PS = [dict(member=0, story='control', start_t=t0, start_lat=sd[0], start_lon=sd[1], gen_t=t0 + dt.timedelta(hours=0 if obs['formed'] else 30),
               gen_lat=None, gen_lon=None, mjo=obs['mjo_u'], mjo_kt=obs['mjo_kt'], mjo_i=0, sst=obs['sst'], shear_scale=1.0, shear=None, beta=1.0, speed=1.0, timing=0, magnitude=1)]
    kk = 0
    for pk, npk in PREC_SHARE.items():
        w = np.array([st[2] for st in STORIES], float); c = np.floor(w / w.sum() * npk).astype(int)
        for i in np.argsort(-(w / w.sum() * npk - c))[: npk - c.sum()]: c[i] += 1
        pr = PR[pk]
        for st, cnt in zip(STORIES, c):
            for j in range(1, cnt + 1):
                kk += 1; P = vary(st, j, cnt, t0, (pr['lat'], pr['lon']), obs, k=kk + 20, gen0=30 if pk == 'south' else 36); P['prec'] = pk; PS.append(P)
    for i, P in enumerate(PS): P['member'] = i
    RES = []
    for P in PS:
        pts, lf = S.run_track(M, ES.EnvS(FB[P.get('prec', 'south')], O.LA, O.LO, t0, P), P)
        g = P.get('gen_pos')
        RES.append(dict(member=P['member'], story=P['story'], prec=P.get('prec', 'south'), timing=P['timing'], magnitude=P['magnitude'], levels=[],
                        seg=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                        gen=dict(t=P['gen_t'].isoformat(), lat=round(g[0], 2), lon=round(g[1], 2)) if g else None,
                        lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), wind=lf.get('wind')) if lf else None,
                        vmax=max(p[3] for p in pts), pts=[(p[0].isoformat(), round(p[1], 2), round(p[2], 2), p[3]) for p in pts]))
    from collections import Counter
    c = Counter(r['seg'] for r in RES)
    summ = dict(shares={s: c[s] for s in SEGS if c[s]}, tn=c['south TN'] + c['north TN'], vmax_mid=round(float(np.median([r['vmax'] for r in RES])), 1),
                control=dict(seg=RES[0]['seg'], lf=RES[0]['lf'], vmax=RES[0]['vmax']))
    stories = [dict(key='control', name='Control: today’s environment held', n=1, text='Every wind as observed now, unchanged through the run.')] + \
              [dict(key=k, name=nm, n=n, text=tx) for k, nm, n, tx, _ in STORIES]
    for s in stories:
        cc = Counter(r['seg'] for r in RES if r['story'] == s['key']); s['outcome'] = dict(cc); s['n'] = sum(cc.values())
    precs = [dict(key=k, name={'south': 'Southern seedling', 'north': 'Northern circulation', 'merge': 'The two merge'}[k], lat=v['lat'], lon=v['lon'], text=v['note'],
                  n=sum(1 for r in RES if r['prec'] == k and r['member']), outcome=dict(Counter(r['seg'] for r in RES if r['prec'] == k and r['member']))) for k, v in PR.items()]
    json.dump(dict(run=t0.isoformat(), method='scenarios', obs=obs, analogs=[], factors=[], stories=stories, precursors=precs, runs=RES, summary=summ), open(OUTJ, 'w'), default=str)
    print(t0, summ)
    for s in stories + precs: print(f"  {s['name'][:45]:45s} n={s['n']:2d}", s['outcome'])
