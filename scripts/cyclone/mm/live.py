"""Live 51-member ensemble of the moist multi-level model.
python live.py run LIVEM_NPZ LIVE_NPZ PART NPART OUT_JSON     (runs members PART, PART+NPART, ...)
python live.py merge LIVE_NPZ SST_JSON LIVE_INPUTS_JSON OUT_JSON PARTS...
Member 0: today's GFS analysis as it is, standard physics. Members 1-50 differ only where things are genuinely uncertain,
spread evenly with a fixed sequence: the starting analysis (smooth errors of ~1 m/s in the winds, ~0.5 K in temperature,
~5% in humidity), the sea temperature (+-0.5 K), and the physics (convection time scale and humidity, sea-surface
evaporation, boundary-layer depth). The model's own storm is followed from each of today's candidate circulations; the
one that becomes strongest is that member's storm."""
import sys, os, json, math, datetime as dt, numpy as np
from scipy import ndimage as nd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
from ours_live_s import halton
HOURS = 168
def lvl(x): return min(2, int(x * 3))
FACTORS = [('Starting winds / temperature / humidity', ['perturbation pattern A', 'pattern B', 'pattern C']),
           ('Sea temperature', ['0.5 K cooler', 'about as analysed', '0.5 K warmer']),
           ('Convection time scale', ['fast (1-2 h)', 'medium (2-3 h)', 'slow (3-4 h)']),
           ('Humidity convection leaves', ['70-77%', '77-83%', '83-90%']),
           ('Sea-surface evaporation', ['20% less', 'standard', '20% more']),
           ('Boundary-layer depth', ['shallow', 'medium', 'deep'])]
def member(k):
    if k == 0: return dict(h=[0.5] * 6, set={})
    h = [halton(k, b) for b in (2, 3, 5, 7, 11, 13)]
    return dict(h=h, set=dict(sst_off=(h[1] - 0.5), tau_bm=3600 * (1 + 3 * h[2]), rh_bm=0.7 + 0.2 * h[3], ce=1.1e-3 * (0.8 + 0.4 * h[4]), ch=1.1e-3 * (0.8 + 0.4 * h[4]),
                                    sig_pbl=0.85 - 0.1 * h[5]))
def perturb(f3, k, lats):
    if k == 0: return f3
    rs = np.random.default_rng(900 + k); out = dict(f3)
    def noise():
        x = nd.gaussian_filter(rs.standard_normal(f3['temperature'].shape[1:]), 3, mode='wrap'); return x / x.std()
    vert = np.linspace(0.5, 1.0, f3['temperature'].shape[0])[:, None, None]
    psi = noise(); du = -np.gradient(psi, axis=0); dv = np.gradient(psi, axis=1); n = np.sqrt((du ** 2 + dv ** 2).mean()); du, dv = du / n, dv / n
    out['u_component_of_wind'] = f3['u_component_of_wind'] + 1.0 * vert * du; out['v_component_of_wind'] = f3['v_component_of_wind'] + 1.0 * vert * dv
    out['temperature'] = f3['temperature'] + 0.5 * noise()[None]
    out['specific_humidity'] = np.maximum(f3['specific_humidity'] * (1 + 0.05 * noise()[None]), 0)
    return out
def run(LIVEM, LIVE, PART, NPART, OUT):
    import mm
    from ours_live import detect
    from ours_live_s import precursors
    Z = np.load(LIVEM); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
    obs = detect(LIVE); b = obs['bay']; PR = precursors(LIVE, (b['lat'], b['lon']))
    f3 = {v: Z['f3'][0, V3.index(v)] for v in V3}; res = []
    for k in range(int(PART), 51, int(NPART)):
        try:
            mb = member(k); M = mm.Model('T85', 6.0, mb['set'])
            st = M.init(perturb(f3, k, Z['lats']), Z['levs'], Z['lats'], Z['lons'], Z['f2'][0, V2.index('surface_pressure')], Z['f2'][0, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][0, V2.index('sea_surface_temperature')], Z['f2'][0, V2.index('land_sea_mask')])
            f, dfi = M.runner(HOURS); _, traj = f(dfi(st)); traj = {a: np.asarray(v) for a, v in traj.items()}
            if not np.isfinite(traj['ps']).all(): raise RuntimeError('blew up')
            T = {pk: M.track(traj, p['lat'], p['lon']) for pk, p in PR.items()}
            res.append(dict(member=k, h=mb['h'], tracks=T)); print(k, {pk: max(t[3] for t in v) for pk, v in T.items()}, flush=True)
        except Exception as e:
            res.append(dict(member=k, err=repr(e)[:300])); print(k, 'FAILED', repr(e)[:300], flush=True)
    json.dump(dict(obs=obs, precursors=PR, members=res), open(OUT, 'w'), default=float)
def merge(LIVE, SSTJ, LIJ, OUT, parts):
    import ourens as O
    from cyc import on_land
    from ours_live import detect, ridge_now, MJO_STATE, SEGS
    from collections import Counter
    t0 = dt.datetime.strptime(str(np.load(LIVE)['run']), '%Y%m%d%H')
    P = [json.load(open(p)) for p in parts]; obs = P[0]['obs']; PR = P[0]['precursors']; obs['precursors'] = PR
    sst = json.load(open(SSTJ)); kk = sorted(sst)[-1]; obs['sst'] = float(sst[kk]['bob']); obs['sst_date'] = kk
    rows = json.load(open(LIJ)).get('mjo', {}).get('rows', [])
    if rows: r = rows[-1]; mu, mk, lab = MJO_STATE(r['phase'], r['amp']); obs.update(mjo_u=mu, mjo_kt=mk, mjo_label=lab, mjo_date=r['date'], mjo_phase=r['phase'], mjo_amp=r['amp'])
    obs['ridge'] = ridge_now(LIVE)
    RES = []
    for m in sorted([m for p in P for m in p['members'] if 'tracks' in m], key=lambda m: m['member']):
        # the member's storm: the candidate circulation whose track reaches the strongest winds while over the Bay
        best = max(m['tracks'].items(), key=lambda kv: max([t[3] for t in kv[1] if 5 <= t[1] <= 22 and 78 <= t[2] <= 99] or [0]))
        pk, tr = best; pts = []
        for t in tr:
            pts.append((t0 + dt.timedelta(hours=t[0]), t[1], t[2], t[3]))
            if on_land(t[2], t[1]) and t[3] < 15 and len(pts) > 2: break
        lf = None
        for a, c in zip(pts, pts[1:]):
            if not on_land(a[2], a[1]) and on_land(c[2], c[1]): lf = dict(t=a[0] + (c[0] - a[0]) / 2, lat=(a[1] + c[1]) / 2, lon=(a[2] + c[2]) / 2, wind=a[3]); break
        RES.append(dict(member=m['member'], prec=pk, levels=[lvl(x) for x in m['h']], seg=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                        gen=dict(t=pts[0][0].isoformat(), lat=pts[0][1], lon=pts[0][2]),
                        lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), wind=lf['wind']) if lf else None,
                        vmax=max(p[3] for p in pts), pts=[(p[0].isoformat(), p[1], p[2], p[3]) for p in pts]))
    c = Counter(r['seg'] for r in RES)
    summ = dict(shares={s: c[s] for s in SEGS if c[s]}, tn=c['south TN'] + c['north TN'], vmax_mid=round(float(np.median([r['vmax'] for r in RES])), 1),
                control=dict(seg=RES[0]['seg'], lf=RES[0]['lf'], vmax=RES[0]['vmax']) if RES and RES[0]['member'] == 0 else None, n=len(RES))
    json.dump(dict(run=t0.isoformat(), method='moist', obs=obs, analogs=[], factors=[[t, l] for t, l in FACTORS], runs=RES, summary=summ), open(OUT, 'w'), default=str)
    print(t0, summ)
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'run': run(*a[1:6])
    else: merge(a[1], a[2], a[3], a[4], a[5:])
