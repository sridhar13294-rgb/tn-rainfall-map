"""Our own hemispheric physics ensemble (two-layer model over 6S-65N, 0-150E; tc2.py). No forecast model, no storylines.
python ours_live_h.py LIVE_NPZ LIVEH_NPZ SST_JSON LIVE_INPUTS_JSON OUT_JSON
Start: today's GFS analysis over the hemisphere (only the observed state). The westerly troughs already over Iran,
Afghanistan and Central Asia are inside the model and move east by the equations; the planetary-scale pattern
(monsoon flow, subtropical highs) is held steady by a constant forcing. (A storm-heating option exists in tc2.py but did
not improve the past-storm score, so it is off.)
Member 0 = the analysis as it is. Members 1-50: the analysis changed where it is uncertain (trough depth and position,
small random wind errors, start position, which circulation develops) and the model settings varied (deformation radius,
vortex response, how far the storm's winds reach, random tendency noise), spread evenly with a fixed sequence."""
import sys, os, json, math, pickle, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S, intens as IN, tc2
from cyc import on_land
from ours_live import detect, ridge_now, MJO_STATE, SEGS
from ours_live_s import precursors
from hemi_pert import perturb, phys
HOURS = 168; LEVS = [850, 700, 500, 200]
LW = {850: 0.3, 700: 0.3, 500: 0.25, 200: 0.15}; UW = {200: 1.0}
SET = dict(steady_ls=10, resid=False, cmul=0.0)          # best-scoring setting on the 84 past storms (heating did not help there; see the page)
def lvl(x): return min(2, int(x * 3))
FACTORS = [('Which circulation becomes the depression', ['southern seedling', 'merger of the two', 'east-central Bay circulation']),
           ('Westerly trough depth (start)', ['up to 20% shallower', 'about as analysed', 'up to 20% deeper']),
           ('Westerly trough position (start)', ['up to 3 deg further west', 'about as analysed', 'up to 3 deg further east']),
           ('Start position', ['0.5 deg south-west side', 'near observed', '0.5 deg north-east side']),
           ('Deformation radius (how the layers couple)', ['900-1,100 km', '1,100-1,300 km', '1,300-1,500 km']),
           ('Vortex response to the strength model', ['quick (3-5 h)', 'medium (5-7 h)', 'slow (7-9 h)']),
           ('How far out the storm’s winds reach', ['fall off fast', 'typical', 'fall off slowly']),
           ('Random model noise during the run', ['small', 'medium', 'large']),
           ('How fast it strengthens', ['slowly', 'normally', 'fast']),
           ('When the depression forms', ['in 12-24 h', 'in 24-42 h', 'in 42-54 h'])]
def main(LIVE, LIVEH, SSTJ, LIJ, OUTJ, NPROC=1, PART=None):
    t0 = dt.datetime.strptime(str(np.load(LIVE)['run']), '%Y%m%d%H')
    obs = detect(LIVE); b = obs['bay']; obs['formed'] = bool(b['vort850'] >= 7.0 and b['depth'] >= 2.5)
    sst = json.load(open(SSTJ)); k = sorted(sst)[-1]; obs['sst'] = float(sst[k]['bob']); obs['sst_date'] = k
    rows = json.load(open(LIJ)).get('mjo', {}).get('rows', [])
    if rows:
        r = rows[-1]; mu, mk, lab = MJO_STATE(r['phase'], r['amp']); obs.update(mjo_u=mu, mjo_kt=mk, mjo_label=lab, mjo_date=r['date'], mjo_phase=r['phase'], mjo_amp=r['amp'])
    else: obs.update(mjo_u=0.0, mjo_kt=0.0, mjo_label='unknown', mjo_date=None)
    obs['ridge'] = ridge_now(LIVE); PR = precursors(LIVE, (b['lat'], b['lon'])); obs['precursors'] = PR
    A0 = S.ana_raw(LIVE); Ur = [A0[0, l] for l in range(4)]; Vr = [A0[1, l] for l in range(4)]                  # regional, for shear
    Z = np.load(LIVEH); HV = [str(v) for v in Z['vars']]; X = Z['data'].astype(float); lats, lons = Z['lats'], Z['lons']
    LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
    U = [X[HV.index(f'u{l}')] for l in LEVS]; V = [X[HV.index(f'v{l}')] for l in LEVS]
    def rmv(f, la, lo, R=5.0):
        d = np.hypot(LAg - la, (LOg - lo) * math.cos(math.radians(la))); m = d <= R; f = f.copy(); f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
        for _ in range(80): f[m] = nd.uniform_filter(f, 5, mode='nearest')[m]
        return f
    BASE = {k: ([rmv(x, v['lat'], v['lon']) for x in U], [rmv(x, v['lat'], v['lon']) for x in V]) for k, v in PR.items()}
    IM = pickle.load(open(os.path.join(O.REPO, 'data', 'cyclone', 'ours', 'intens_model.pkl'), 'rb'))
    RES = []
    todo = range(51) if PART is None else [i for i in range(51) if i % int(NPROC) == int(PART)]
    for mi in todo:
        p = phys(mi) if mi else None
        prec = 'south' if mi == 0 else ['south', 'merge', 'north'][lvl(p['prec'])]
        Ub, Vb = BASE[prec]
        if mi: Ub, Vb = perturb(Ub, Vb, LAg, LOg, LEVS, mi)
        gen = 0 if obs['formed'] else (30 if mi == 0 else 12 + 42 * p['gen'])
        rate = 0 if mi == 0 else lvl(p['rate']) - 1
        kw = dict(SET)
        if mi:
            if SET.get('heat'): kw['heat'] = SET['heat'] * p['heat_f']
            if p['sppt'] > 0.02: kw['sppt'] = dict(seed=1000 + mi, amp=p['sppt'])
        M = tc2.TC2(-6.0, 64.0, 1.0, 149.0, res=0.75, Ld15=p['Ld15'] if mi else 1.2e6); reg = lambda a: M.regrid(a, lats, lons)
        L_ = lambda XX, w: reg(sum(wt * XX[LEVS.index(l)] for l, wt in w.items()))
        start = (PR[prec]['lat'] + (p['dla'] if mi else 0), PR[prec]['lon'] + (p['dlo'] if mi else 0))
        off = 1.5 * (obs['sst'] - 0.3) + obs['mjo_kt'] + 1.5 * rate; shs = (1.25, 1.0, 0.8)[rate + 1]
        st = dict(v=17.0 if obs['formed'] else 12.0, dvp=0.0, h=0.0, vlf=None, landh=0.0); hist = []
        def vfn(th, la, lo, land, st=st):
            dtp = th - st['h']
            if dtp >= 0.49:
                age = th - gen
                if land: st['landh'] += dtp; st['vlf'] = st['vlf'] or st['v']; st['v'] = IN.inland(st['vlf'], st['landh'])
                elif age < 0: st['v'] = min(16.5, st['v'] + 0.1 * dtp)
                else:
                    if st['v'] < 17: st['v'] = 17.0
                    sh = IN.shear_at(Ur, Vr, min(max(la, 1), 29), min(max(lo, 71), 104)) or 10.0
                    dv = float(IM.predict([IN.feats(st['v'], sh * shs, la, st['dvp'], age)])[0]) + off
                    if st['vlf'] is not None: dv = min(dv, 2.0)
                    st['v'] = min(140.0, max(10.0, st['v'] + dv * dtp / 12)); st['dvp'] = dv
                st['h'] = th
            hist.append((th, st['v'])); return max(12.0, st['v'])
        out = M.run2(L_(Ub, LW), L_(Vb, LW), L_(Ub, UW), L_(Vb, UW), start, HOURS, vfn, dt=300.0, land_fn=on_land,
                     tau_v=p['tau_v'] if mi else 6.0, xo=p['xo'] if mi else 0.5, **kw)
        pts = []
        for h, la, lo in out:
            w = min(hist, key=lambda q: abs(q[0] - h))[1] if hist else 12.0; pts.append((t0 + dt.timedelta(hours=h), la, lo, round(w, 1)))
            if on_land(lo, la) and w < 12: break
        lf = None
        for a, c in zip(pts, pts[1:]):
            if not on_land(a[2], a[1]) and on_land(c[2], c[1]): lf = dict(t=a[0] + (c[0] - a[0]) / 2, lat=(a[1] + c[1]) / 2, lon=(a[2] + c[2]) / 2, wind=a[3]); break
        g = next((q for q in pts if (q[0] - t0).total_seconds() / 3600 >= gen), pts[0])
        levels = [1] * len(FACTORS) if mi == 0 else [lvl(p['prec']), lvl((p['trough_scale'] - 0.8) / 0.4), lvl(p['trough_shift'] / 6 + 0.5), lvl(p['dla'] + 0.5),
                                                    lvl((p['Ld15'] - 0.9e6) / 0.6e6), lvl((p['tau_v'] - 3) / 6), 2 - lvl((p['xo'] - 0.4) / 0.2),
                                                    lvl(p['sppt'] / 0.25), lvl(p['rate']), lvl(p['gen'])]
        RES.append(dict(member=mi, levels=levels, prec=prec, seg=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                        gen=dict(t=g[0].isoformat(), lat=round(g[1], 2), lon=round(g[2], 2)),
                        lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), wind=lf['wind']) if lf else None,
                        vmax=max(q[3] for q in pts), pts=[(q[0].isoformat(), round(q[1], 2), round(q[2], 2), q[3]) for q in pts]))
        print(mi, RES[-1]['seg'], RES[-1]['lf'], flush=True)
    if PART is not None:
        json.dump(RES, open(OUTJ + f'.part{PART}', 'w'), default=str)
        if int(PART) == 0: json.dump(obs, open(OUTJ + '.obs', 'w'), default=str)
        return
    finish(t0, obs, RES, OUTJ)
def finish(t0, obs, RES, OUTJ):
    from collections import Counter
    RES = sorted(RES, key=lambda r: r['member']); c = Counter(r['seg'] for r in RES)
    summ = dict(shares={s: c[s] for s in SEGS if c[s]}, tn=c['south TN'] + c['north TN'], vmax_mid=round(float(np.median([r['vmax'] for r in RES])), 1),
                control=dict(seg=RES[0]['seg'], lf=RES[0]['lf'], vmax=RES[0]['vmax']))
    F = [[t, labs] for t, labs in FACTORS]
    if obs['formed']: F[-1] = ['When the depression forms', ['already formed'] * 3]
    json.dump(dict(run=t0.isoformat() if hasattr(t0, 'isoformat') else t0, method='physics', obs=obs, analogs=[], factors=F, runs=RES, summary=summ), open(OUTJ, 'w'), default=str)
    print(t0, summ)
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'merge':                                    # merge LIVE_NPZ OUT_JSON NPROC (after the parts have run)
        LIVE, OUTJ, n = a[1], a[2], int(a[3]); RES = [r for i in range(n) for r in json.load(open(OUTJ + f'.part{i}'))]
        obs = json.load(open(OUTJ + '.obs')) if os.path.exists(OUTJ + '.obs') else {}
        t0 = dt.datetime.strptime(str(np.load(LIVE)['run']), '%Y%m%d%H'); finish(t0, obs, RES, OUTJ)
    else: main(*a)
