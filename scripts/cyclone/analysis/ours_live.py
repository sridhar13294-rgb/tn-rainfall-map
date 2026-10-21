"""Our own 51-member ensemble from live data (no model forecast). One run per GFS analysis cycle.
python ours_live.py LIB_NPZ LIVE_NPZ SST_JSON LIVE_INPUTS_JSON OUT_JSON
LIVE_NPZ: GFS analysis (step 0) over 0-35N 50-110E from ours_fetch.py. SST_JSON: the site's data/sst_indices.json (main).
Every input's middle setting is today's observed value; low/high are fixed steps either side (see FACTORS)."""
import sys, os, json, math, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S, live_env as LE
from cyc import on_land
SEGS = ['Sri Lanka', 'south TN', 'north TN', 'south AP', 'central AP', 'north AP', 'Odisha/WB', 'Bangladesh/Myanmar', 'no landfall']
def remove_vortex_grid(F, lats, lons, la, lo, R=4.5):
    LA, LO = np.meshgrid(lats, lons, indexing='ij'); d = np.hypot(LA - la, (LO - lo) * math.cos(math.radians(la))); m = d <= R; F = F.copy()
    for idx in np.ndindex(F.shape[:-2]):
        f = F[idx]; f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
        for _ in range(120): f[m] = nd.uniform_filter(f, 5, mode='nearest')[m]
        F[idx] = f
    return F
def detect(fn):
    """observed circulations in the analysis: (lat, lon, vort850, vort700 [1e-5/s], closed-low depth hPa)"""
    Z = np.load(fn); V = [str(v) for v in Z['vars']]; X = Z['data'][0, 0].astype(float); la, lo = Z['lats'], Z['lons']
    res = float(la[1] - la[0]); dy = res * 111e3; dx = dy * np.cos(np.radians(la))[:, None]
    def vo(l):
        u, v = X[V.index('u' + l)], X[V.index('v' + l)]
        return nd.uniform_filter((np.gradient(v, axis=1) / dx - np.gradient(u, axis=0) / dy) * 1e5, int(round(3.5 / res)) | 1)
    v8, v7 = vo('850'), vo('700'); p = nd.uniform_filter(X[V.index('msl')], 3)                     # hPa
    LA, LO = np.meshgrid(la, lo, indexing='ij')
    def find(box, need):
        k = (LA >= box[0]) & (LA <= box[1]) & (LO >= box[2]) & (LO <= box[3])
        sea = np.vectorize(lambda a, b: not on_land(b, a))(LA[k], LO[k])
        s = np.where(k, (v8 + v7) / 2, -99); s[k] = np.where(sea, s[k], -99)
        j = np.unravel_index(np.argmax(s), s.shape); a, b = float(la[j[0]]), float(lo[j[1]])
        d = np.hypot(LA - a, (LO - b) * math.cos(math.radians(a)))
        cmin = float(np.nanmin(p[d <= 1.5])); ring = float(np.nanmean(p[(d >= 2.5) & (d <= 4)]))
        out = dict(lat=a, lon=b, vort850=round(float(v8[j]), 1), vort700=round(float(v7[j]), 1), depth=round(ring - cmin, 1), msl=round(cmin, 1))
        edge = a in (box[0], box[1]) or b in (box[2], box[3])        # a maximum on the box edge is not a circulation inside it
        out['present'] = bool(out['vort850'] >= need[0] and out['depth'] >= need[1] and not edge) if need else True
        return out
    return dict(bay=find((4, 20, 80.5, 99), None), arabian=find((5, 20, 60, 77), (4.0, 1.0)), sw_bay=find((7, 14, 78, 83.5), (3.0, 0.0)))
def O_ridge(u, lo0=80, lo1=96):
    import bgdiag_ridge as BR
    return BR.ridge(u, O.LA, O.LO, lo0, lo1)
def ridge_now(fn):
    """500 hPa ridge from the analysis: axis latitude (highest height) per longitude band, the east-west wind turning
    line over 80-96E, and the main closed highs."""
    import bgdiag_ridge as BR
    Z = np.load(fn); V = [str(v) for v in Z['vars']]; X = Z['data'][0, 0].astype(float); la, lo = Z['lats'], Z['lons']
    z5 = X[V.index('z500')]; u5 = X[V.index('u500')]
    bands = {f'{a}-{b}E': round(BR.ridge_z(z5, la, lo, a, b), 1) for a, b in ((70, 80), (80, 88), (88, 96), (96, 105))}
    zs = nd.uniform_filter(z5, 5); mx = nd.maximum_filter(zs, size=21); hs = []
    for j, i in np.argwhere(zs >= mx - 1e-6):
        if 8 < la[j] < 30 and 62 < lo[i] < 106 and all(abs(la[j] - h[1]) + abs(lo[i] - h[0]) > 6 for h in hs):
            hs.append((float(lo[i]), float(la[j]), round(float(zs[j, i]))))
    u0 = BR.ridge(u5, la, lo, 80, 96)
    return dict(axis=bands, u0_80_96=round(u0, 1) if u0 else None, highs=sorted(hs, key=lambda h: -h[2])[:4])
MJO_STATE = lambda ph, amp: (0.0, 0.0, 'weak (amplitude below 1)') if amp < 1 else \
    ((1.5, 1.0, f'active over the Indian Ocean (phase {ph})') if ph in (2, 3, 4) else
     ((0.8, 0.0, f'over the Maritime Continent (phase {ph})') if ph in (5, 6) else (-0.8, -1.0, f'suppressed over the Indian Ocean (phase {ph})')))
def factors(obs, t0):
    formed = obs['formed']
    return [
        ('gen', 'When the depression forms', ['already formed'] * 3 if formed else ['in 12 h', 'in 30 h', 'in 54 h'], [0, 0, 0] if formed else [12, 30, 54]),
        ('slat', 'Start position north-south', ['%.1f deg south' % (0.4 if formed else 1.0), 'as observed', '%.1f deg north' % (0.4 if formed else 1.0)], [-0.4, 0, 0.4] if formed else [-1.0, 0, 1.0]),
        ('slon', 'Start position west-east', ['%.1f deg west' % (0.4 if formed else 1.5), 'as observed', '%.1f deg east' % (0.4 if formed else 1.5)], [-0.4, 0, 0.4] if formed else [-1.5, 0, 1.5]),
        ('rlat', 'Ridge north-south', ['1 deg south', 'as now', '1 deg north'], [-1, 0, 1]),
        ('rlon', 'Ridge east-west', ['1.5 deg west', 'as now', '1.5 deg east'], [-1.5, 0, 1.5]),
        ('rstr', 'Ridge strength', ['15% weaker', 'as now', '15% stronger'], [0.85, 1, 1.15]),
        ('sst', 'Bay sea temperature anomaly', ['%+.1f C' % (obs['sst'] - 0.2), '%+.1f C (observed)' % obs['sst'], '%+.1f C' % (obs['sst'] + 0.2)], [obs['sst'] - 0.2, obs['sst'], obs['sst'] + 0.2]),
        ('mjo', 'MJO effect', ['weaker than now', 'as now: ' + obs['mjo_label'], 'stronger than now'], [-1, 0, 1]),
        ('shear', 'Wind shear / dry air', ['more hostile', 'as now', 'more favourable'], [1.35, 1.0, 0.75]),
        ('wd', 'Westerly trough over NW India', ['weaker', 'as now', 'deeper'], [-4, 0, 4]),
        ('surge', 'NE-monsoon easterlies', ['weaker', 'as now', 'stronger'], [2, 0, -2]),
        ('as', 'Arabian Sea system', ['weaker', 'as observed', 'stronger'] if obs['arabian']['present'] else ['none in the analysis'] * 3, [-8, 0, 8]),
        ('size', 'Storm size (beta drift)', ['smaller', 'typical', 'bigger'], [0.8, 1.0, 1.2])]
DRIFT_N = float(os.environ.get('OURS_DN', 0.0))       # optional northward calibration drift, km/h (hind_bve.py)
def build(obs, t0, sd):
    F = factors(obs, t0); out = []
    a = obs['arabian']; g = obs['sw_bay']
    for m, lv in enumerate(S.design51()):
        v = {k: vals[lv[i]] for i, (k, _, _, vals) in enumerate(F)}
        jr = np.random.default_rng(100 + m); j = (lambda w: float(jr.uniform(-w, w))) if m else (lambda w: 0.0)
        js, jt = (0.2, 0) if obs['formed'] else (0.4, 4)
        P = dict(member=m, levels=lv, start_t=t0, start_lat=round(sd[0] + v['slat'] + j(js), 2), start_lon=round(sd[1] + v['slon'] + j(js), 2),
                 gen_t=t0 + dt.timedelta(hours=v['gen'] + round(j(jt))), gen_lat=None, gen_lon=None,
                 ridge_dlat=v['rlat'], ridge_dlon=v['rlon'], ridge_str=v['rstr'], ridge_dt=0, sst=round(v['sst'], 2),
                 mjo=F[7][2][lv[7]], mjo_i=0, mjo_u=obs['mjo_u'] + 0.75 * v['mjo'], mjo_kt=obs['mjo_kt'] + 1.0 * v['mjo'],
                 shear=F[8][2][lv[8]], shear_i=0, shear_scale=v['shear'], wd_amp=v['wd'], wd_lon=72.0, surge_u=v['surge'],
                 beta=v['size'], speed=1.0, as_sys=F[11][2][lv[11]], vortices=[(a['lat'], a['lon'], v['as'])] if (a['present'] and v['as']) else [])
        P['dn'] = DRIFT_N
        if obs['formed']: P['start_v'] = 17.0
        out.append(P)
    return F, out
if __name__ == '__main__':
    LIB, LIVE, SSTJ, LIJ, OUTJ = sys.argv[1:6]
    t0 = dt.datetime.strptime(str(np.load(LIVE)['run']), '%Y%m%d%H')
    obs = detect(LIVE); b = obs['bay']
    obs['formed'] = bool(b['vort850'] >= 7.0 and b['depth'] >= 2.5)
    sst = json.load(open(SSTJ)); k = sorted(sst)[-1]; obs['sst'] = float(sst[k]['bob']); obs['sst_date'] = k
    li = json.load(open(LIJ)); rows = li.get('mjo', {}).get('rows', [])
    if rows:
        r = rows[-1]; mu, mk, lab = MJO_STATE(r['phase'], r['amp']); obs.update(mjo_u=mu, mjo_kt=mk, mjo_label=lab, mjo_date=r['date'], mjo_phase=r['phase'], mjo_amp=r['amp'])
    else: obs.update(mjo_u=0.0, mjo_kt=0.0, mjo_label='unknown (no MJO data)', mjo_date=None)
    M = S.train()
    # today's analysis on its own grid (0.5 deg); the seedling's own swirl is taken out so it is not steered by itself.
    Zl = np.load(LIVE); V = [str(v) for v in Zl['vars']]; X = Zl['data'][0, 0].astype(float); lats, lons = Zl['lats'], Zl['lons']
    Fa = np.stack([np.stack([X[V.index(f'{c}{l}')] for l in LE.LEVS]) for c in 'uv'])
    sd = (b['lat'], b['lon']); Fa = remove_vortex_grid(Fa, lats, lons, sd[0], sd[1])
    obs['ridge'] = ridge_now(LIVE)
    F, PS = build(obs, t0, sd); RES = []; top = []
    box = (float(lats[0]) + 1, float(lats[-1]) - 1, float(lons[0]) + 1, float(lons[-1]) - 1)
    for P in PS:
        env = LE.EnvB(LE.perturb(Fa, lats, lons, P), lats, lons, O.LA, O.LO, t0, P, hours=264, box=box)
        pts, lf = S.run_track(M, env, P)
        g = P.get('gen_pos')
        RES.append(dict(member=P['member'], levels=P['levels'], seg=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                        gen=dict(t=P['gen_t'].isoformat(), lat=round(g[0], 2), lon=round(g[1], 2)) if g else None,
                        lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), wind=lf.get('wind')) if lf else None,
                        vmax=max(p[3] for p in pts), pts=[(p[0].isoformat(), round(p[1], 2), round(p[2], 2), p[3]) for p in pts]))
    from collections import Counter
    c = Counter(r['seg'] for r in RES); L = sorted(r['lf']['lat'] for r in RES if r['lf'] and r['lf']['lon'] < 89)
    summ = dict(shares={s: c[s] for s in SEGS if c[s]}, tn=c['south TN'] + c['north TN'], lf_lat_mid=round(float(np.median(L)), 1) if L else None,
                lf_lat_p10=round(float(np.percentile(L, 10)), 1) if L else None, lf_lat_p90=round(float(np.percentile(L, 90)), 1) if L else None,
                vmax_mid=round(float(np.median([r['vmax'] for r in RES])), 1), control=dict(seg=RES[0]['seg'], lf=RES[0]['lf'], vmax=RES[0]['vmax']))
    json.dump(dict(run=t0.isoformat(), obs=obs, analogs=top, factors=[[t, labs] for _, t, labs, _ in F], runs=RES, summary=summ), open(OUTJ, 'w'), default=str)
    print(t0, 'formed' if obs['formed'] else 'not yet formed', 'seedling', b, '| arabian', obs['arabian'], '| sw bay', obs['sw_bay'])
    print('sst', obs['sst'], obs['sst_date'], '| mjo', obs['mjo_label'], obs.get('mjo_date')); print(summ)
