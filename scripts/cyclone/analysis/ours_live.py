"""Our own 51-member ensemble from live data (no model forecast). One run per GFS analysis cycle.
python ours_live.py LIB_NPZ LIVE_NPZ SST_JSON LIVE_INPUTS_JSON OUT_JSON
LIVE_NPZ: GFS analysis (step 0) over 0-35N 50-110E from ours_fetch.py. SST_JSON: the site's data/sst_indices.json (main).
Every input's middle setting is today's observed value; low/high are fixed steps either side (see FACTORS)."""
import sys, os, json, math, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S
from cyc import on_land
SEGS = ['Sri Lanka', 'south TN', 'north TN', 'south AP', 'central AP', 'north AP', 'Odisha/WB', 'Bangladesh/Myanmar', 'no landfall']
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
        cmin = float(p[d <= 1.5].min()); ring = float(p[(d >= 2.5) & (d <= 4)].mean())
        out = dict(lat=a, lon=b, vort850=round(float(v8[j]), 1), vort700=round(float(v7[j]), 1), depth=round(ring - cmin, 1), msl=round(cmin, 1))
        edge = a in (box[0], box[1]) or b in (box[2], box[3])        # a maximum on the box edge is not a circulation inside it
        out['present'] = bool(out['vort850'] >= need[0] and out['depth'] >= need[1] and not edge) if need else True
        return out
    return dict(bay=find((4, 20, 80.5, 99), None), arabian=find((5, 20, 60, 77), (4.0, 1.0)), sw_bay=find((7, 14, 78, 83.5), (3.0, 0.0)))
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
        ('wd', 'Western disturbance / trough', ['weaker', 'as now', 'deeper'], [-4, 0, 4]),
        ('surge', 'NE-monsoon easterlies', ['weaker', 'as now', 'stronger'], [2, 0, -2]),
        ('as', 'Arabian Sea system', ['stalls', 'moves north', 'moves north-west'] if obs['arabian']['present'] else ['none in the analysis'] * 3, [0, 1, 2]),
        ('size', 'Storm size (beta drift)', ['smaller', 'typical', 'bigger'], [0.8, 1.0, 1.2])]
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
                 shear=F[8][2][lv[8]], shear_i=0, shear_scale=v['shear'], wd_amp=v['wd'], wd_day=4.0, surge_u=v['surge'], surge_day=1.0,
                 beta=v['size'], speed=1.0, as_sys=F[11][2][lv[11]], gom='observed')
        if obs['formed']: P['start_v'] = 17.0
        if a['present']:
            tr = {0: [(0, a['lat'], a['lon']), (6, a['lat'] + 0.8, a['lon'] - 0.3)], 1: [(0, a['lat'], a['lon']), (3, a['lat'] + 4.5, a['lon'] - 1.5), (6, a['lat'] + 9.5, a['lon'] - 3)],
                  2: [(0, a['lat'], a['lon']), (2, a['lat'] + 1.5, a['lon'] - 3.5), (6, a['lat'] + 5, a['lon'] - 11.5)]}[v['as']]
            P['as_track'] = [(t0 + dt.timedelta(days=d), x, y) for d, x, y in tr]
        else: P['as_track'] = None
        P['gom_track'] = [(t0, g['lat'], g['lon']), (t0 + dt.timedelta(days=1), g['lat'] + 0.1, g['lon'] - 0.3)] if g['present'] else None
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
    M = S.train(); St = O.lib_states(LIB); sc = O.scales(St); RAW = S.lib_raw(LIB)
    now = S.ana_raw(LIVE); st = O.analysis_state(LIVE)[1]; R = O.match(st, St, sc); C, top = S.composite(R, RAW)
    sd = (b['lat'], b['lon']); now = S.remove_vortex(now, sd[0], sd[1])
    if obs['sw_bay']['present']: now = S.remove_vortex(now, obs['sw_bay']['lat'], obs['sw_bay']['lon'], R=3.5)
    E = S.base_env(now, C); F, PS = build(obs, t0, sd); RES = []
    for P in PS:
        pts, lf = S.run_track(M, S.Env(E, t0, P), P)
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
    print('sst', obs['sst'], obs['sst_date'], '| mjo', obs['mjo_label'], obs.get('mjo_date')); print('analogs', top[:5]); print(summ)
