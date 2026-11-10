"""P5 geostrophic check (10 Nov): same as u850_denial.py but saves the mean model-minus-ERA5 bias MAPS of u850, v850, mslp
(days 1-3) over 40-120 E, 0-40 N to OUT (.npz). P5 mechanism-denial (6 Nov 17:30): which process makes the Bay 850-hPa easterly (-4 m/s by day 3, P5 table).
T42, Oct-Nov 2020 starts, 3 days. For each variant: Bay (10-20 N, 82-95 E) u850 / v850 bias and central-India MSLP bias
vs ERA5 at days 1-3. Variants change ONE process from base2. python u850_denial.py LIB TRUTH N_STARTS"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
LIB, TRU, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = np.load(TRU); DI = {str(d): i for i, d in enumerate(TR['days'])}
la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
W0, W1, W2, W3 = [float(x) for x in os.environ.get('WIN', '0,40,40,120').split(',')]; win = np.ix_((la >= W0) & (la <= W1), (lo >= W2) & (lo <= W3)); bay = np.ix_((la >= 10) & (la <= 20), (lo >= 82) & (lo <= 95)); ci = np.ix_((la >= 18) & (la <= 26), (lo >= 74) & (lo <= 86))
B2 = {'cmt_mf': 1, 'rd_si': 1}
VAR0 = [('base2', {}), ('physics off', {'phys_off': True}), ('no CMT', {'cmt_mf': 0, 'cmt_cu': 0.0}), ('shallow <=200 hPa', {'sh_depth': 1}),
       ('implicit drag', {'drag_imp': 1}), ('land module', json.loads(sys.argv[4]) if len(sys.argv) > 4 else {'soil_fr': 1, 'land_rs': 1}), ('no DFI', {'dfi_off': 1}),
       ('base2 noise1', {'sppt': 0.02, 'sppt_seed': 1}), ('base2 noise2', {'sppt': 0.02, 'sppt_seed': 2})]   # 10 Nov: spread from a tiny perturbation
VAR = [v for v in VAR0 if v[0] in os.environ.get('ONLY', '|'.join(n for n, _ in VAR0)).split('|')]
starts = [k for k in TT if k[5:7] in ('10', '11') and k.endswith('T00')][::int(os.environ.get('STRIDE', '6'))][:N]
res = {}
for name, extra in VAR:
    M = mm2.Model(os.environ.get('GR', 'T42'), 32, None, {'rad': 'radcloud', 'rad_every': 2, **B2, **extra}); acc = []; MAP = {}
    for key in starts:
        k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); NDAY = int(os.environ.get('NDAY', '3')); out = M.run_wx(st, cr, 24 * NDAY, 24); row = []
        for d in range(0, NDAY + 1):
            v = (t0 + dt.timedelta(days=d)).strftime('%Y-%m-%dT%H'); j = DI[v]; g = lambda F: np.asarray(WS.to_grid(F, M.lon, M.lat))
            for nm, scale in (('u850', 1.0), ('v850', 1.0), ('mslp', 0.01), ('z500', 1.0)):
                MAP.setdefault((nm, d), []).append(((g(out[nm][d]) - TR['o_' + nm][j]) * scale)[win])
            if d < 1 or d > 3: continue
            row.append([float(np.nanmean((g(out['u850'][d]) - TR['o_u850'][j])[bay])), float(np.nanmean((g(out['v850'][d]) - TR['o_v850'][j])[bay])),
                        float(np.nanmean((g(out['mslp'][d]) - TR['o_mslp'][j])[ci])) / 100])
        acc.append(row)
    a = np.mean(np.array(acc), 0); res[name] = a.tolist()
    print(f'{name:18s}', ' | '.join(f'd{d}: u850 {a[d-1,0]:+.2f} v850 {a[d-1,1]:+.2f} C-India MSLP {a[d-1,2]:+.2f}' for d in range(1, len(a) + 1)), flush=True)
json.dump(dict(starts=starts, res=res, grid=os.environ.get('GR', 'T42')), open(os.environ.get('OUT', 'p5_geo.json'), 'w'))
np.savez_compressed(os.environ.get('OUT', 'p5_geo.json').replace('.json', '.npz'), lat=la[(la >= W0) & (la <= W1)], lon=lo[(lo >= W2) & (lo <= W3)],
                    **{f'{nm}_d{d}': np.nanmean(np.array(v), 0) for (nm, d), v in MAP.items()})
