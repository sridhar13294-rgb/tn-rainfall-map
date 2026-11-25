"""25 Nov (Tracks v850 5-why, registered 18:4x): day-1 difference lc_mix minus old mse scheme (p5b_no_shmf) at T170, 3 Nov starts, box means of
v850/u850/rain/t850/mslp and the 850 hPa physics heating. Decision: local (TN/Bay, co-located with heating/rain) vs basin-wide.
python map_t170.py LIB OUT"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit, wxscore as WS
LIB, OUT = sys.argv[1], sys.argv[2]; CF = os.path.join(HERE, '..', '..', '..', 'data', 'cyclone', 'kaggle_cfg')
SETS = {'lcm': json.load(open(os.path.join(CF, 'suite_lcmix_wx.json')))['variants'][0]['set'], 'old': json.load(open(os.path.join(CF, 'p5b_no_shmf.json')))['variants'][0]['set']}
Z = np.load(LIB); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; TT = [str(t) for t in Z['times']]
LA, LO = WS.LA, WS.LO
BOX = {'TN': (8, 14, 76, 81), 'Bay': (8, 20, 82, 95), 'Arabian': (8, 20, 60, 73), 'CIndia': (18, 26, 75, 85), 'SIO': (-5, 5, 60, 95), 'WPac': (8, 20, 125, 150), 'Atl': (8, 20, 320, 340)}
res = {}
for KEY in ('2020-11-01T00', '2020-11-11T00', '2020-11-16T00'):
    K = TT.index(KEY); F = Z['f3'][K].astype(np.float32); f2 = Z['f2'][K]; f3 = {v: F[V3.index(v)] for v in V3}; t0 = dt.datetime.strptime(KEY, '%Y-%m-%dT%H')
    for nm, S in SETS.items():
        M = mm2.Model('T170', 32, 20.0, S)
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); out = M.run_wx(st, cr, 24, 24)
        g = {k: WS.to_grid(np.asarray(out[k][1]), M.lon, M.lat) for k in ('v850', 'u850', 't850', 'mslp')}
        g['rain'] = WS.to_grid(np.asarray(out['rain'][1]) - np.asarray(out['rain'][0]), M.lon, M.lat)
        for k, X in g.items():
            for b, (a, bb, c, d) in BOX.items():
                m = (LA >= a) & (LA <= bb) & (LO >= c) & (LO <= d); res.setdefault(f'{nm}|{k}|{b}', []).append(float(X[m].mean()))
        print(KEY, nm, 'done', flush=True); json.dump(res, open(OUT, 'w'))
