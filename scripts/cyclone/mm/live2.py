"""Live 51-member ensemble of model version 2 (mm2.py), with forecaster products.
python live2.py run LIVEM_NPZ LIVE_NPZ PART NPART OUT_JSON [CONFIG_JSON]      members PART, PART+NPART, ...
python live2.py merge LIVE_NPZ SST_JSON LIVE_INPUTS_JSON STATIONS_JSON OUT_JSON PARTS...
Member 0 (control): today's GFS analysis, standard physics (optionally on the finer grid, config "control_grid").
Members 1-50 differ where things are genuinely uncertain, spread evenly with a fixed sequence:
  starting state - a share of today's ECMWF-minus-GFS analysis difference (when ECMWF's analysis is available) plus a mix of
                   bred vectors (the model's own fastest-growing differences over 12 h, scaled to ~1 m/s);
  physics        - convection humidity and time scale, sea-surface exchange, ocean mixing, rain re-evaporation, and
                   SPPT-style random multipliers on the physics during the run.
Products: each member's storm track and strength, landfall; rain at every TN rain-gauge site (daily totals)."""
import sys, os, json, math, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
from ours_live_s import halton
HOURS = 168
def lvl(x): return min(2, int(x * 3))
FACTORS = [('Starting state: share of ECMWF analysis (when available)', ['GFS side', 'between', 'ECMWF side']),
           ('Starting state: growing differences (bred vectors)', ['pattern set A', 'set B', 'set C']),
           ('Humidity convection leaves', ['70-77%', '77-83%', '83-90%']),
           ('Convection time scale', ['fast', 'medium', 'slow']),
           ('Sea-surface heat and moisture exchange', ['20% less', 'standard', '20% more']),
           ('Ocean stirring under the storm', ['weak', 'medium', 'strong']),
           ('Rain re-evaporation', ['less', 'standard', 'more']),
           ('Random physics noise (SPPT)', ['small', 'medium', 'large'])]
def member(k):
    if k == 0: return dict(h=[0.5] * 8, alpha=0.0, set={})
    h = [halton(k, b) for b in (2, 3, 5, 7, 11, 13, 17, 19)]
    return dict(h=h, alpha=-0.5 + 2.0 * h[0], set=dict(rh_deep=0.7 + 0.2 * h[2], tau_deep=1800 + 3600 * h[3], ck=1.2e-3 * (0.8 + 0.4 * h[4]), ent=0.3 + 0.6 * h[5],
                                                        k_evap=2e-5 * (0.5 + h[6]), sppt=0.1 + 0.2 * h[7], sppt_seed=1000 + k))
def run(LIVEM, LIVE, PART, NPART, OUT, CFG=None):
    import mm2, jax.numpy as jnp
    from ours_live import detect
    from ours_live_s import precursors
    C = json.load(open(CFG)) if CFG and os.path.exists(CFG) else {}
    Z = np.load(LIVEM); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; t0 = dt.datetime.strptime(str(Z['times'][0]), '%Y-%m-%dT%H')
    obs = detect(LIVE); b = obs['bay']; PR = precursors(LIVE, (b['lat'], b['lon'])); formed = bool(b['vort850'] >= 7.0 and b['depth'] >= 2.5)
    f3 = {v: Z['f3'][0, V3.index(v)].astype(float) for v in V3}
    ecm = os.path.join(os.path.dirname(LIVEM), os.path.basename(LIVEM).replace('GFSM', 'ECM'))
    D = None
    if os.path.exists(ecm):
        E = np.load(ecm); EV = [str(v) for v in E['v3']]
        D = {v: np.nan_to_num(E['f3'][0, EV.index(v)].astype(float) - f3[v]) for v in V3 if v in EV}
    st_names = json.load(open(os.path.join(HERE, '..', '..', '..', 'data', 'cyclone', 'mm', 'tn_sites.json'))) if os.path.exists(os.path.join(HERE, '..', '..', '..', 'data', 'cyclone', 'mm', 'tn_sites.json')) else None
    res = []; bv_cache = {}; models = {}; import time
    for k in range(int(PART), 51, int(NPART)):
        try:
            t_a = time.time()
            mb = member(k); grid = C.get('control_grid', 'T85') if k == 0 else C.get('grid', 'T85')
            if grid not in models: models[grid] = mm2.Model(grid, 32, 30.0, dict(sppt_on=True))           # one compiled model per grid, reused by every member
            M = models[grid]
            fk = {v: f3[v] + (mb['alpha'] * D[v] if D is not None and v in D else 0.0) for v in V3}
            storm = dict(lat=b['lat'], lon=b['lon'], vmax_kt=25.0) if (formed and k % 2 == 1) else None     # balanced storm inserted in half the members
            st, cr = M.init(fk, Z['levs'], Z['lats'], Z['lons'], Z['f2'][0, V2.index('surface_pressure')], Z['f2'][0, V2.index('geopotential_at_surface')] / 9.80616,
                            Z['f2'][0, V2.index('sea_surface_temperature')], Z['f2'][0, V2.index('land_sea_mask')], storm=storm)
            cr = M.with_params(cr, mb['set'])
            if getattr(M, 'built_for', None) != t0: M.build(t0)
            st = M.dfi(st)
            if k:
                if grid not in bv_cache: bv_cache[grid] = mm2.bred_vectors(M, st, M.with_params(cr, {}), n=6, hours=12.0, seed=77, amp=1.0)
                rs = np.random.default_rng(3000 + k); c = rs.standard_normal(6) / math.sqrt(6) * (1 if lvl(mb['h'][1]) != 1 else 1.2)
                st = mm2.add_perturbation(st, bv_cache[grid], c)
            out = M.run(st, cr, HOURS)
            if not np.isfinite(out['mslp']).all(): raise RuntimeError('model blew up')
            T = {pk: M.track(out, p['lat'], p['lon'], keep_h=0 if formed else 96) for pk, p in PR.items()}
            T['peak'] = mm2.track_from_peak(M, out)                                                   # the Bay system at its strongest, followed both ways
            systems = mm2.track_all(M, out)                                                           # every Bay / Arabian Sea system, with mergers
            rain = None
            if st_names:                                                                              # cumulative rain (mm) at each TN site, every 6 h
                from scipy.interpolate import RegularGridInterpolator as RGI
                pts = np.array([[s_[2], s_[1]] for s_ in st_names])                                  # (lon, lat)
                rain = [np.round(RGI((M.blon, M.blat), np.asarray(out['rain'][i]), bounds_error=False, fill_value=0.0)(pts), 1).tolist() for i in range(out['rain'].shape[0])]
            res.append(dict(member=k, h=mb['h'], alpha=mb['alpha'], grid=grid, tracks=T, rain=rain, systems=systems)); print(k, grid, {pk: max([t[3] for t in v] or [0]) for pk, v in T.items()}, '%.0fs' % (time.time() - t_a), flush=True)
        except Exception as e:
            import traceback; traceback.print_exc(); res.append(dict(member=k, err=repr(e)[:300])); print(k, 'FAILED', repr(e)[:300], flush=True)
    json.dump(dict(obs=obs, precursors=PR, ecm=D is not None, members=res), open(OUT, 'w'), default=float)
def merge(LIVE, SSTJ, LIJ, SITES, OUT, parts):
    import ourens as O
    from cyc import on_land
    from ours_live import ridge_now, MJO_STATE, SEGS
    from collections import Counter
    t0 = dt.datetime.strptime(str(np.load(LIVE)['run']), '%Y%m%d%H')
    P = [json.load(open(p)) for p in parts]; obs = P[0]['obs']; PR = P[0]['precursors']; obs['precursors'] = PR
    obs['ecm_analysis'] = any(p.get('ecm') for p in P)
    sst = json.load(open(SSTJ)); kk = sorted(sst)[-1]; obs['sst'] = float(sst[kk]['bob']); obs['sst_date'] = kk
    rows = json.load(open(LIJ)).get('mjo', {}).get('rows', [])
    if rows: r = rows[-1]; mu, mk, lab = MJO_STATE(r['phase'], r['amp']); obs.update(mjo_u=mu, mjo_kt=mk, mjo_label=lab, mjo_date=r['date'], mjo_phase=r['phase'], mjo_amp=r['amp'])
    obs['ridge'] = ridge_now(LIVE)
    def bad(m): return bool(m.get('rain')) and not np.isfinite(np.array(m['rain'], float)).all()          # the run went numerically unstable
    mem = sorted([m for p in P for m in p['members'] if 'tracks' in m and not bad(m)], key=lambda m: m['member'])
    failed = sorted([m['member'] for p in P for m in p['members'] if 'err' in m or bad(m)])
    RES = []
    for m in mem:
        cand = [kv for kv in m['tracks'].items() if kv[1]]
        if not cand: failed.append(m['member']); continue
        best = next((kv for kv in cand if kv[0] == 'peak' and len(kv[1]) >= 8), None) or max(cand, key=lambda kv: max([t[3] for t in kv[1] if 5 <= t[1] <= 22 and 78 <= t[2] <= 99] or [0]))
        pk, tr = best; pts = []
        for t in tr:
            pts.append((t0 + dt.timedelta(hours=t[0]), t[1], t[2], t[3], t[4]))
            if on_land(t[2], t[1]) and t[3] < 15 and len(pts) > 2: break
        lf = None
        for a, c in zip(pts, pts[1:]):
            if not on_land(a[2], a[1]) and on_land(c[2], c[1]): lf = dict(t=a[0] + (c[0] - a[0]) / 2, lat=(a[1] + c[1]) / 2, lon=(a[2] + c[2]) / 2, wind=a[3], pmin=a[4]); break
        RES.append(dict(member=m['member'], prec=pk, grid=m.get('grid'), levels=[lvl(x) for x in m['h']], seg=O.segment(lf['lat'], lf['lon']) if lf else 'no landfall',
                        gen=dict(t=pts[0][0].isoformat(), lat=pts[0][1], lon=pts[0][2]),
                        lf=dict(t=lf['t'].isoformat(), lat=round(lf['lat'], 2), lon=round(lf['lon'], 2), wind=lf['wind'], pmin=lf['pmin']) if lf else None,
                        vmax=max(p[3] for p in pts), pmin=min([p[4] for p in pts if p[4]] or [None] or [0]) if any(p[4] for p in pts) else None,
                        pts=[(p[0].isoformat(), p[1], p[2], p[3]) for p in pts]))
    # strike probability: share of members whose storm passes within 120 km of each 0.5-deg point in 7 days
    gl = np.arange(4, 26.01, 0.5); go = np.arange(74, 100.01, 0.5); GO, GL = np.meshgrid(go, gl); hit = np.zeros_like(GO)
    for r in RES:
        h = np.zeros_like(GO, bool)
        for _, la, lo, _ in r['pts']: h |= np.hypot(GL - la, (GO - lo) * math.cos(math.radians(la))) * 111.2 <= 120
        hit += h
    strike = dict(lat=gl.round(2).tolist(), lon=go.round(2).tolist(), p=np.round(hit / max(1, len(RES)), 3).tolist())
    # rain at TN sites -> district daily totals (ensemble median and chance of >= 64.5 mm "heavy" and >= 115.6 mm "very heavy")
    sites = json.load(open(SITES)); dists = sorted({s[3] for s in sites}); dr = None
    R = [np.array(m['rain'], float) for m in mem if m.get('rain')]; R = [x for x in R if np.isfinite(x).all()]      # drop members whose rain went bad
    if R:
        n = min(x.shape[0] for x in R); R = np.stack([x[:n] for x in R])                          # members x times x sites (cumulative mm)
        days = list(range(4, n, 4))                                                              # every 24 h
        daily = np.diff(np.concatenate([np.zeros_like(R[:, :1]), R[:, days]], 1), axis=1)        # members x days x sites
        dr = dict(days=[(t0 + dt.timedelta(hours=6 * d)).isoformat() for d in days], districts=dists, median=[], heavy=[], very_heavy=[], total_median=[])
        for dname in dists:
            idx = [i for i, s in enumerate(sites) if s[3] == dname]; dm = daily[:, :, idx].mean(2)
            dr['median'].append(np.round(np.median(dm, 0), 1).tolist()); dr['heavy'].append(np.round((dm >= 64.5).mean(0), 2).tolist())
            dr['very_heavy'].append(np.round((dm >= 115.6).mean(0), 2).tolist()); dr['total_median'].append(round(float(np.median(dm.sum(1))), 1))
    c = Counter(r['seg'] for r in RES)
    # scenarios: which system ends up dominant (lowest pressure), whether another merged into it, where it lands
    def scen(m):
        sy = m.get('systems') or {}; tr = {t['id']: t for t in sy.get('tracks', [])}
        if sy.get('dominant') is None: return 'no organised system'
        d = tr[sy['dominant']]; merged = [t for t in tr.values() if t.get('merged_into') == d['id']]
        seg = 'stays at sea'
        for a, b in zip(d['pts'], d['pts'][1:]):
            if not on_land(a[2], a[1]) and on_land(b[2], b[1]): seg = O.segment((a[1] + b[1]) / 2, (a[2] + b[2]) / 2); break
        return d['basin'] + ' system dominant' + (' (absorbs the ' + ('Arabian Sea' if merged[0]['basin'] == 'Arabian Sea' else 'other Bay') + ' system)' if merged else '') + ' -> ' + seg
    scenarios = Counter(scen(m) for m in mem if m['member'] not in failed)
    summ = dict(shares={s: c[s] for s in SEGS if c[s]}, tn=c['south TN'] + c['north TN'], vmax_mid=round(float(np.median([r['vmax'] for r in RES])), 1),
                control=dict(seg=RES[0]['seg'], lf=RES[0]['lf'], vmax=RES[0]['vmax']) if RES and RES[0]['member'] == 0 else None, n=len(RES), failed=failed, scenarios=dict(scenarios.most_common()))
    json.dump(dict(run=t0.isoformat(), method='moist2', obs=obs, analogs=[], factors=[[t, l] for t, l in FACTORS], runs=RES, summary=summ, strike=strike, district_rain=dr),
              open(OUT, 'w'), default=str)
    print(t0, summ)
if __name__ == '__main__':
    a = sys.argv[1:]
    if a[0] == 'run': run(*a[1:7]) if len(a) > 6 else run(*a[1:6])
    else: merge(a[1], a[2], a[3], a[4], a[5], a[6:])
