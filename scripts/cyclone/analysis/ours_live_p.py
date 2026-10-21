"""Our own physics ensemble (storm inside the physics, tcmodel.py). No forecast model and no past-storm winds.
python ours_live_p.py LIVE_NPZ SST_JSON LIVE_INPUTS_JSON OUT_JSON
Each member changes today's starting state by realistic amounts (which circulation develops, its position, size and
strengthening, the ridge, a westerly trough, the easterlies, formation time); the physics then moves everything."""
import sys, os, json, math, pickle, datetime as dt, numpy as np
from scipy import ndimage as nd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ourens as O, scen as S, intens as IN, tcmodel as T, bve, live_env as LE
from cyc import on_land
from ours_live import detect, ridge_now, MJO_STATE, SEGS
from ours_live_s import precursors
FACT = [('prec', 'Which circulation becomes the depression', ['southern seedling', 'merger of the two', 'east-central Bay circulation'], ['south', 'merge', 'north']),
        ('slat', 'Start position north-south', ['0.5 deg south', 'as observed', '0.5 deg north'], [-0.5, 0, 0.5]),
        ('slon', 'Start position west-east', ['0.5 deg west', 'as observed', '0.5 deg east'], [-0.5, 0, 0.5]),
        ('size', 'Storm size (outer circulation)', ['small (500 km)', 'medium (700 km)', 'large (900 km)'], [500, 700, 900]),
        ('rlat', 'Ridge position north-south (start)', ['1 deg south', 'as observed', '1 deg north'], [-1, 0, 1]),
        ('rstr', 'Ridge strength (start)', ['15% weaker', 'as observed', '15% stronger'], [0.85, 1.0, 1.15]),
        ('wd', 'Westerly trough over NW India (start)', ['none added', 'moderate', 'deep'], [0, 5, 10]),
        ('surge', 'NE-monsoon easterlies (start)', ['weaker', 'as observed', 'stronger'], [2, 0, -2]),
        ('rate', 'How fast it strengthens', ['slowly (dry air, shear)', 'normally', 'fast (warm sea, active MJO)'], [-1, 0, 1]),
        ('gen', 'When the depression forms', ['in 12 h', 'in 30 h', 'in 54 h'], [12, 30, 54]),
        ('ana', 'Starting data (analysis)', ['GFS analysis', 'half-way to ECMWF', 'ECMWF analysis'], [0.0, 0.5, 1.0]),
        ('depth', 'Steering layer used', ['shallow (mostly 850-700 hPa)', 'standard (850-200 hPa)', 'deep (more 500-200 hPa)'], [(0.45, 0.35, 0.15, 0.05), (0.3, 0.3, 0.25, 0.15), (0.2, 0.25, 0.3, 0.25)]),
        ('sppt', 'Model uncertainty during the run', ['small (15%)', 'medium (30%)', 'large (45%)'], [0.15, 0.3, 0.45]),
        ('xo', 'How far out the storm’s winds reach', ['fall off fast', 'typical', 'fall off slowly'], [0.6, 0.5, 0.4]),
        ('grow', 'Storm widens as it strengthens', ['no', 'some', 'a lot'], [0.0, 0.3, 0.6]),
        ('phys', 'Model smoothing / vortex response', ['less smoothing, quick response', 'standard', 'more smoothing, slow response'], [(0.5e4, 6.0), (1.0e4, 9.0), (2.0e4, 14.0)])]
DES = json.load(open(os.path.join(O.REPO, 'data', 'cyclone', 'ours', 'design16.json')))
def main(LIVE, SSTJ, LIJ, OUTJ, DIFF=None):
    t0 = dt.datetime.strptime(str(np.load(LIVE)['run']), '%Y%m%d%H')
    obs = detect(LIVE); b = obs['bay']; obs['formed'] = bool(b['vort850'] >= 7.0 and b['depth'] >= 2.5)
    sst = json.load(open(SSTJ)); k = sorted(sst)[-1]; obs['sst'] = float(sst[k]['bob']); obs['sst_date'] = k
    rows = json.load(open(LIJ)).get('mjo', {}).get('rows', [])
    if rows:
        r = rows[-1]; mu, mk, lab = MJO_STATE(r['phase'], r['amp']); obs.update(mjo_u=mu, mjo_kt=mk, mjo_label=lab, mjo_date=r['date'], mjo_phase=r['phase'], mjo_amp=r['amp'])
    else: obs.update(mjo_u=0.0, mjo_kt=0.0, mjo_label='unknown', mjo_date=None)
    obs['ridge'] = ridge_now(LIVE); PR = precursors(LIVE, (b['lat'], b['lon'])); obs['precursors'] = PR
    Z = np.load(LIVE); V = [str(v) for v in Z['vars']]; X = Z['data'][0, 0].astype(float); lats, lons = Z['lats'], Z['lons']
    Fa = np.stack([np.stack([X[V.index(f'{c}{l}')] for l in LE.LEVS]) for c in 'uv'])
    LAg, LOg = np.meshgrid(lats, lons, indexing='ij')
    def rmv(F, la, lo, R=5.0):
        d = np.hypot(LAg - la, (LOg - lo) * math.cos(math.radians(la))); m = d <= R; F = F.copy()
        for idx in np.ndindex(F.shape[:-2]):
            f = F[idx]; f[m] = np.nanmean(f[(d > R) & (d <= R + 2)])
            for _ in range(80): f[m] = nd.uniform_filter(f, 5, mode='nearest')[m]
            F[idx] = f
        return F
    FC = {k: rmv(Fa, v['lat'], v['lon']) for k, v in PR.items()}
    DF = np.zeros_like(Fa)                                          # ECMWF minus GFS analysis (same time), where both exist
    if DIFF and os.path.exists(DIFF):
        dz = np.load(DIFF); from scipy.interpolate import RegularGridInterpolator as RGI
        pts_ = np.stack([LAg.ravel(), LOg.ravel()], -1); inside = (LAg >= dz['lats'][0]) & (LAg <= dz['lats'][-1]) & (LOg >= dz['lons'][0]) & (LOg <= dz['lons'][-1])
        tap = nd.uniform_filter(inside.astype(float), 9)
        for c in range(2):
            for l in range(4): DF[c, l] = RGI((dz['lats'], dz['lons']), dz['d'][c, l], bounds_error=False, fill_value=0.0)(pts_).reshape(LAg.shape) * tap
        obs['ana_diff'] = dict(rms=round(float(np.sqrt((DF ** 2).mean())), 2), run=str(dz['run']))
    shear_now = lambda la, lo: IN.shear_at(*[[S.ana_raw(LIVE)[c, l] for l in range(4)] for c in (0, 1)], la, lo)
    A0 = S.ana_raw(LIVE); U0 = [A0[0, l] for l in range(4)]; V0 = [A0[1, l] for l in range(4)]
    IM = pickle.load(open(os.path.join(O.REPO, 'data', 'cyclone', 'ours', 'intens_model.pkl'), 'rb'))
    M = T.TC(float(lats[0]) + 1, float(lats[-1]) - 1, float(lons[0]) + 1, float(lons[-1]) - 1, res=0.5)
    RES = []
    for mi, lv in enumerate(DES):
        v = {k: vals[lv[i]] for i, (k, _, _, vals) in enumerate(FACT)}
        if obs['formed']: v['gen'] = 0
        pr = PR[v['prec']]; start = (pr['lat'] + v['slat'], pr['lon'] + v['slon'])
        P = dict(ridge_dlat=v['rlat'], ridge_dlon=0, ridge_str=v['rstr'], wd_amp=v['wd'], wd_lon=72.0, surge_u=v['surge'])
        F = LE.perturb(FC[v['prec']] + v['ana'] * DF, lats, lons, P)
        u = sum(w * F[0, i] for i, w in enumerate(v['depth'])); vv = sum(w * F[1, i] for i, w in enumerate(v['depth']))
        off = 1.5 * (obs['sst'] - 0.3) + obs['mjo_kt'] + 1.5 * v['rate']; shs = (1.25, 1.0, 0.8)[v['rate'] + 1]
        st = dict(v=17.0 if obs['formed'] else 12.0, dvp=0.0, h=0.0, vlf=None, landh=0.0, hist=[])
        def vfn(th, la, lo, land):
            dtp = th - st['h']
            if dtp >= 0.49:
                age = th - v['gen']
                if land:
                    st['landh'] += dtp; st['vlf'] = st['vlf'] or st['v']; st['v'] = IN.inland(st['vlf'], st['landh'])
                elif age < 0: st['v'] = min(16.5, st['v'] + 0.1 * dtp)
                else:
                    if st['v'] < 17: st['v'] = 17.0
                    sh = IN.shear_at(U0, V0, min(max(la, 1), 29), min(max(lo, 71), 104)) or 10.0
                    dv = float(IM.predict([IN.feats(st['v'], sh * shs, la, st['dvp'], age)])[0]) + off
                    if st['vlf'] is not None: dv = min(dv, 2.0)
                    st['v'] = min(140.0, max(10.0, st['v'] + dv * dtp / 12)); st['dvp'] = dv
                st['h'] = th
            return max(3.0, 0.3 * st['v'] * 0.5144) * (v['size'] / 700) ** 0.3        # deep-layer vortex wind (m/s) from the storm's max wind (kt)
        hist = []
        def vfn_rec(th, la, lo, land):
            x = vfn(th, la, lo, land); hist.append((th, la, lo, st['v'])); return x
        out = M.run_storm(M.regrid(u, lats, lons), M.regrid(vv, lats, lons), start, 216, vfn_rec, size=v['size'], land_fn=on_land, xo=v['xo'], size_grow=v['grow'],
                          nu=v['phys'][0], tau_h=v['phys'][1], sppt=dict(seed=1000 + mi, amp=v['sppt'], scale_deg=10.0, hours=36.0) if mi else None)
        pts = []
        for h, la, lo in out:
            w = min(hist, key=lambda q: abs(q[0] - h))[3] if hist else 12.0; pts.append((t0 + dt.timedelta(hours=h), la, lo, round(w, 1)))
            if on_land(lo, la) and w < 12: break
        lf = None
        for a, c in zip(pts, pts[1:]):
            if not on_land(a[2], a[1]) and on_land(c[2], c[1]): lf = dict(t=a[0] + (c[0] - a[0]) / 2, lat=(a[1] + c[1]) / 2, lon=(a[2] + c[2]) / 2, wind=a[3]); break
        g = next((p for p in pts if (p[0] - t0).total_seconds() / 3600 >= v['gen']), pts[0])
        RES.append(dict(member=mi, levels=lv, seg=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                        gen=dict(t=g[0].isoformat(), lat=round(g[1], 2), lon=round(g[2], 2)),
                        lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), wind=lf['wind']) if lf else None,
                        vmax=max(p[3] for p in pts), pts=[(p[0].isoformat(), round(p[1], 2), round(p[2], 2), p[3]) for p in pts]))
        print(mi, RES[-1]['seg'], RES[-1]['lf'], flush=True)
    from collections import Counter
    c = Counter(r['seg'] for r in RES)
    summ = dict(shares={s: c[s] for s in SEGS if c[s]}, tn=c['south TN'] + c['north TN'], vmax_mid=round(float(np.median([r['vmax'] for r in RES])), 1),
                control=dict(seg=RES[0]['seg'], lf=RES[0]['lf'], vmax=RES[0]['vmax']))
    F = [[t, labs] for _, t, labs, _ in FACT]
    if obs['formed']: F[-1] = ['When the depression forms', ['already formed'] * 3]
    json.dump(dict(run=t0.isoformat(), method='physics', obs=obs, analogs=[], factors=F, runs=RES, summary=summ), open(OUTJ, 'w'), default=str)
    print(t0, summ)
if __name__ == '__main__': main(*sys.argv[1:6])
