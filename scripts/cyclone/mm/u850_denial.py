"""P5 mechanism-denial (6 Nov 17:30): which process makes the Bay 850-hPa easterly (-4 m/s by day 3, P5 table).
T42, Oct-Nov 2020 starts, 3 days. For each variant: Bay (10-20 N, 82-95 E) u850 / v850 bias and central-India MSLP bias
vs ERA5 at days 1-3. Variants change ONE process from base2. python u850_denial.py LIB TRUTH N_STARTS"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
LIB, TRU, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = np.load(TRU); DI = {str(d): i for i, d in enumerate(TR['days'])}
la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
bay = np.ix_((la >= 10) & (la <= 20), (lo >= 82) & (lo <= 95)); ci = np.ix_((la >= 18) & (la <= 26), (lo >= 74) & (lo <= 86))
B2 = {'cmt_mf': 1, 'rd_si': 1}
VAR0 = [('base2', {}), ('physics off', {'phys_off': True}), ('no CMT', {'cmt_mf': 0, 'cmt_cu': 0.0}), ('shallow <=200 hPa', {'sh_depth': 1}),
       ('implicit drag', {'drag_imp': 1}), ('land module', json.loads(sys.argv[4]) if len(sys.argv) > 4 else {'soil_fr': 1, 'land_rs': 1}), ('no DFI', {'dfi_off': 1})]
VAR = [v for v in VAR0 if v[0] in os.environ.get('ONLY', '|'.join(n for n, _ in VAR0)).split('|')]
starts = [k for k in TT if k[5:7] in ('10', '11') and k.endswith('T00')][::6][:N]
res = {}
for name, extra in VAR:
    M = mm2.Model(os.environ.get('GR', 'T42'), 32, None, dict({'rad': 'radcloud', 'rad_every': 2}, **B2, **extra)); acc = []
    for key in starts:
        k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); out = M.run_wx(st, cr, 72, 24); row = []
        for d in (1, 2, 3):
            v = (t0 + dt.timedelta(days=d)).strftime('%Y-%m-%dT%H'); j = DI[v]; g = lambda F: np.asarray(WS.to_grid(F, M.lon, M.lat))
            row.append([float(np.nanmean((g(out['u850'][d]) - TR['o_u850'][j])[bay])), float(np.nanmean((g(out['v850'][d]) - TR['o_v850'][j])[bay])),
                        float(np.nanmean((g(out['mslp'][d]) - TR['o_mslp'][j])[ci])) / 100])
        acc.append(row)
    a = np.mean(np.array(acc), 0); res[name] = a.tolist()
    print(f'{name:18s}', ' | '.join(f'd{d}: u850 {a[d-1,0]:+.2f} v850 {a[d-1,1]:+.2f} C-India MSLP {a[d-1,2]:+.2f}' for d in (1, 2, 3)), flush=True)
json.dump(dict(starts=starts, res=res), open('/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/u850_denial.json', 'w'))
