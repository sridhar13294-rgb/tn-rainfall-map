"""Fix #7 live trial: does putting real observations into the start (nudge.py OI analysis) improve MEGAM's forecasts?
For one run time: the multi-centre consensus start, with and without our OI analysis of the open observations
(obs_<run>.npz), each run 5 days; daily fields saved for scoring against the later GFS analyses (live_GFSM_<t>.npz).

python obs_trial.py run  FOLDER YYYYMMDDHH OUT_NPZ [HOURS] [SETTINGS_JSON]   (Kaggle GPU; FOLDER holds live_*_<run>.npz, obs_<run>.npz)
python obs_trial.py score TRIAL_NPZ_GLOB ANALYSIS_FOLDER                      (CPU; prints RMSE vs GFS analysis by day and region)"""
import sys, os, json, glob, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.append(os.path.join(HERE, '..', 'analysis'))
KEEP = ('z500', 't850', 'u850', 'v850', 'u200', 'v200', 'mslp', 't2', 'rain')
REG = {'india': (5, 35, 65, 100), 'bay_as': (0, 25, 50, 100), 'tropics': (-20, 20, 0, 360), 'globe': (-90, 90, 0, 360)}

def run(folder, run_t, out, hours=120, sett=None):
    import mm2, landinit, consensus as CS, nudge as N
    t0 = dt.datetime.strptime(run_t, '%Y%m%d%H'); Z = np.load(os.path.join(folder, f'live_GFSM_{run_t}.npz'))
    V2 = [str(v) for v in Z['v2']]
    CN = CS.consensus(CS.load_centres(folder, run_t)); print('centres used', CN['used'], flush=True)
    obs = os.path.join(folder, f'obs_{run_t}.npz'); CNo, rep = N.analyse_consensus(CN, obs, t0)
    CNb, _ = N.analyse_consensus(CN, obs, t0, cfg=dict(debias_p=True), verbose=False)              # with pressure bias correction
    if rep is None: raise SystemExit('no observations for ' + run_t)
    print('OI report', json.dumps(rep, default=str)[:1500], flush=True)
    M = mm2.Model('T85', 32, 30.0, dict(sett or {})); save = dict(lon=np.asarray(M.lon, np.float32), lat=np.asarray(M.lat, np.float32), run=run_t, hours=np.arange(0, hours + 1, 24))
    for name, C in (('noobs', CN), ('obs', CNo), ('obsdb', CNb)):
        fk, psk = CS.member_start(C, 0)
        st, cr = M.init(fk, Z['levs'], Z['lats'], Z['lons'], psk, Z['f2'][0, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][0, V2.index('sea_surface_temperature')], Z['f2'][0, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][0], V2))
        M.build(t0); st = M.dfi(st); o = M.run_wx(st, cr, hours, 24)
        if not np.isfinite(o['mslp']).all(): raise RuntimeError(name + ' blew up')
        for k in KEEP: save[f'{name}_{k}'] = np.asarray(o[k], np.float32)
        print(name, 'done', flush=True)
    save['oi_report'] = json.dumps(rep, default=str); np.savez_compressed(out, **save); print('saved', out, os.path.getsize(out) // 1024, 'KB')

def analysis_fields(folder, t, lon, lat):
    """GFS analysis at time t on the model grid (bilinear): z500, t850, u850, v850, u200, v200, mslp."""
    fn = os.path.join(folder, f'live_GFSM_{t:%Y%m%d%H}.npz')
    if not os.path.exists(fn): return None
    A = np.load(fn); V3 = [str(v) for v in A['v3']]; V2 = [str(v) for v in A['v2']]; levs = [int(x) for x in A['levs']]
    la, lo = np.asarray(A['lats'], float), np.asarray(A['lons'], float) % 360
    def regrid(F):
        F = np.asarray(F, float); oi = np.argsort(la); la_s = la[oi]; F = F[oi]
        LO, LA = np.meshgrid(lon % 360, lat, indexing='ij'); fy = np.interp(LA, la_s, np.arange(len(la_s))); dlo = lo[1] - lo[0]
        fx = ((LO - lo[0]) % 360) / dlo; x0 = np.floor(fx).astype(int) % len(lo); x1 = (x0 + 1) % len(lo); wx = fx - np.floor(fx)
        y0 = np.clip(np.floor(fy).astype(int), 0, len(la_s) - 2); wy = fy - y0
        return (F[y0, x0] * (1 - wx) + F[y0, x1] * wx) * (1 - wy) + (F[y0 + 1, x0] * (1 - wx) + F[y0 + 1, x1] * wx) * wy
    g = lambda v, p: regrid(A['f3'][0, V3.index(v), levs.index(p)])
    out = dict(z500=g('geopotential', 500) / 9.80665, t850=g('temperature', 850), u850=g('u_component_of_wind', 850), v850=g('v_component_of_wind', 850),
               u200=g('u_component_of_wind', 200), v200=g('v_component_of_wind', 200))
    if 'mean_sea_level_pressure' in V2: out['mslp'] = regrid(A['f2'][0, V2.index('mean_sea_level_pressure')])
    return out

def score(pattern, folder):
    rows = {}
    for f in sorted(glob.glob(pattern)):
        S = np.load(f); t0 = dt.datetime.strptime(str(S['run']), '%Y%m%d%H'); lon, lat = S['lon'], S['lat']; LO, LA = np.meshgrid(lon, lat, indexing='ij')
        W = np.cos(np.radians(LA))
        for i, h in enumerate(S['hours']):
            if h == 0: continue
            A = analysis_fields(folder, t0 + dt.timedelta(hours=int(h)), lon, lat)
            if A is None: continue
            for reg, (a, b, c, d) in REG.items():
                m = (LA >= a) & (LA <= b) & (LO >= c) & (LO <= d)
                for v, tr in A.items():
                    for name in [n for n in ('noobs', 'obs', 'obsdb') if f'{n}_{v}' in S]:
                        e = S[f'{name}_{v}'][i] - tr; r = float(np.sqrt((W * m * e ** 2).sum() / (W * m).sum()))
                        rows.setdefault((reg, v, int(h) // 24, name), []).append(r)
    for (reg, v, d, name) in sorted(rows):
        if name != 'noobs': continue
        a, b = np.mean(rows[(reg, v, d, 'noobs')]), np.mean(rows[(reg, v, d, 'obs')]); c = rows.get((reg, v, d, 'obsdb'))
        extra = f'  bias-corrected {np.mean(c):8.2f} (n={len(c)}, {100 * (np.mean(c) - np.mean(rows[(reg, v, d, "noobs")][-len(c):])) / a:+5.1f}%)' if c else ''
        print(f'{reg:8s} {v:5s} day {d}  n={len(rows[(reg, v, d, name)]):2d}  without obs {a:8.2f}  with obs {b:8.2f}  change {100 * (b - a) / a:+5.1f}%' + extra)

if __name__ == '__main__':
    if sys.argv[1] == 'run': run(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 120, json.loads(sys.argv[6]) if len(sys.argv) > 6 else None)
    else: score(sys.argv[2], sys.argv[3])
