"""Our own 51-member ensemble, input-driven version (no forecast model, no past-storm winds).
python ours_live_k.py LIVE_NPZ SST_JSON LIVE_INPUTS_JSON OUT_JSON
Today's analysis winds are changed over time by each member's settings of the 13 wind inputs (live_env_k.py), arranged
as an orthogonal design (control + 2 x L27). Formation time, start position, sea temperature and shear are spread evenly
over their ranges with a Halton sequence (deterministic, no random numbers)."""
import sys, os, json, math, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S, live_env_k as K
from ours_live import detect, ridge_now, MJO_STATE, SEGS
def halton(i, b):
    f, r = 1.0, 0.0
    while i > 0: f /= b; r += f * (i % b); i //= b
    return r
def factors(obs):
    A, G = obs['arabian'], obs['sw_bay']
    return [
        ('rlat', 'Ridge position north-south (now)', ['1 deg south', 'as observed', '1 deg north'], [-1, 0, 1]),
        ('rrate', 'Ridge movement', ['drifts south 0.4 deg/day', 'stays', 'drifts north 0.4 deg/day'], [-0.4, 0, 0.4]),
        ('rtrend', 'Ridge strength trend (easterlies)', ['weakens 15% in 3 days', 'steady', 'strengthens 15% in 3 days'], [-0.15, 0, 0.15]),
        ('rlon', 'Ridge position east-west', ['1.5 deg west', 'as observed', '1.5 deg east'], [-1.5, 0, 1.5]),
        ('wdday', 'Next westerly trough reaches 80E', ['in 3 days', 'in 5 days', 'in 7 days'], [3, 5, 7]),
        ('wdamp', 'Next westerly trough depth', ['none', 'moderate', 'deep'], [0, 5, 10]),
        ('wdreach', 'How far south the trough digs', ['to 22N', 'to 18N', 'to 14N'], [22, 18, 14]),
        ('mjo', 'MJO over the next days', ['fades and moves east', 'holds over the Bay', 'strengthens over the Bay'], [0, 1, 2]),
        ('surge', 'NE-monsoon easterlies', ['weaker', 'as now', 'stronger'], [2, 0, -2]),
        ('jet', 'Upper westerly jet (200 hPa)', ['20% weaker', 'as now', '20% stronger'], [0.8, 1.0, 1.2]),
        ('as', 'Arabian Sea low', ['stalls', 'moves north', 'moves north-west'] if A['present'] else ['none observed'] * 3, [0, 1, 2]),
        ('sw', 'South-west Bay circulation', ['fades in a day', 'drifts into Tamil Nadu', 'lingers, moving north'] if G['present'] else ['none observed'] * 3, [0, 1, 2]),
        ('size', 'Storm size (beta drift)', ['smaller', 'typical', 'bigger'], [0.8, 1.0, 1.2])]
def build(obs, t0, sd):
    F = factors(obs); out = []; A, G = obs['arabian'], obs['sw_bay']
    for m, lv in enumerate(S.design51()):
        v = {k: vals[lv[i]] for i, (k, _, _, vals) in enumerate(F)}
        h = (lambda b: 0.5) if m == 0 else (lambda b: halton(m, b))
        formed = obs['formed']
        gen_h = 0 if formed else 12 + 42 * h(2)
        slat = (h(3) - 0.5) * (0.8 if formed else 2.0); slon = (h(5) - 0.5) * (0.8 if formed else 3.0)
        sst = obs['sst'] - 0.2 + 0.4 * h(7); shs = 0.75 + 0.6 * h(11)
        mu = obs['mjo_u']; mt, mc = [(-1.0, 5.0), (0.0, 0.0), (0.5, 0.0)][v['mjo']]
        P = dict(member=m, levels=lv, start_t=t0, start_lat=round(sd[0] + slat, 2), start_lon=round(sd[1] + slon, 2),
                 gen_t=t0 + dt.timedelta(hours=round(gen_h)), gen_lat=None, gen_lon=None,
                 ridge_dlat=v['rlat'], ridge_rate=v['rrate'], ridge_trend=v['rtrend'], ridge_dlon=v['rlon'], ridge_str=1.0,
                 wd_amp=v['wdamp'], wd_day80=v['wdday'], wd_speed=8.0, wd_reach=v['wdreach'], surge_u=v['surge'], jet=v['jet'],
                 mjo_u=mu, mjo_trend=mt, mjo_move=mc, mjo_kt=obs['mjo_kt'] + (-1.0, 0.0, 0.5)[v['mjo']], mjo_i=0,
                 sst=round(sst, 2), shear_scale=round(shs, 2), shear=None, beta=v['size'], speed=1.0)
        if A['present']:
            a, b = A['lat'], A['lon']
            P['as_path'] = {0: [(0, a, b, 1), (6, a + 0.8, b - 0.3, 1)], 1: [(0, a, b, 1), (3, a + 4.5, b - 1.5, 1), (6, a + 9.5, b - 3, 0.6)],
                            2: [(0, a, b, 1), (2, a + 1.5, b - 3.5, 1), (6, a + 5, b - 11.5, 0.8)]}[v['as']]
        if G['present']:
            a, b = G['lat'], G['lon']
            P['sw_path'] = {0: [(0, a, b, 1), (1, a + 0.1, b - 0.3, 0)], 1: [(0, a, b, 1), (1.5, a + 0.4, b - 1.9, 0.3)],
                            2: [(0, a, b, 1), (2, a + 1, b - 0.2, 0.8), (4, a + 2, b - 0.3, 0.5)]}[v['sw']]
        if formed: P['start_v'] = 17.0
        out.append(P)
    return F, out
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
    Fb = S.ana_raw(LIVE); Fb = S.remove_vortex(Fb, sd[0], sd[1])
    for key, R in (('arabian', 4.5), ('sw_bay', 3.5)):
        o = obs[key]
        if o['present'] and O.LA[0] <= o['lat'] <= O.LA[-1] and O.LO[0] <= o['lon'] <= O.LO[-1]: Fb = S.remove_vortex(Fb, o['lat'], o['lon'], R=R)
    F, PS = build(obs, t0, sd); RES = []
    for P in PS:
        pts, lf = S.run_track(M, K.EnvK(Fb, O.LA, O.LO, t0, P), P)
        g = P.get('gen_pos')
        RES.append(dict(member=P['member'], levels=P['levels'], seg=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                        gen=dict(t=P['gen_t'].isoformat(), lat=round(g[0], 2), lon=round(g[1], 2)) if g else None,
                        lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), wind=lf.get('wind')) if lf else None,
                        vmax=max(p[3] for p in pts), pts=[(p[0].isoformat(), round(p[1], 2), round(p[2], 2), p[3]) for p in pts]))
    from collections import Counter
    c = Counter(r['seg'] for r in RES); L = sorted(r['lf']['lat'] for r in RES if r['lf'] and r['lf']['lon'] < 89)
    summ = dict(shares={s: c[s] for s in SEGS if c[s]}, tn=c['south TN'] + c['north TN'], lf_lat_mid=round(float(np.median(L)), 1) if L else None,
                vmax_mid=round(float(np.median([r['vmax'] for r in RES])), 1), control=dict(seg=RES[0]['seg'], lf=RES[0]['lf'], vmax=RES[0]['vmax']))
    json.dump(dict(run=t0.isoformat(), method='inputs', obs=obs, analogs=[], factors=[[t, labs] for _, t, labs, _ in F], runs=RES, summary=summ), open(OUTJ, 'w'), default=str)
    print(t0, summ)
