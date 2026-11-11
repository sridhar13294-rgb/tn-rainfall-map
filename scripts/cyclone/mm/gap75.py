"""75-level day-1 gap (11 Nov): where does the +9 % day-1 z500 / +5 % mslp error of 75 levels vs 32 levels come from?
Scores hour 0 (after init, with and without DFI) and day 1 for: 32L base2, 32L base2 + sfc_imp/drag_imp, 75L + imp, 75L + imp no DFI.
python gap75.py LIB TRUTH GRID STARTS(comma idx) OUT_JSON"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, wxscore as WS, landinit
LIB, TRU, GR, KS, OUT = sys.argv[1], sys.argv[2], sys.argv[3], [int(x) for x in sys.argv[4].split(',')], sys.argv[5]
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = dict(np.load(TRU)); DI = {str(d): i for i, d in enumerate(TR['days'])}
B2 = {'cmt_mf': 1.0, 'rd_si': 1.0}; IMP = dict(B2, sfc_imp=1.0, drag_imp=1.0)
VARS = json.loads(os.environ.get('VARS', 'null')) or [('32L', 32, B2, True), ('32L+imp', 32, IMP, True), ('75L+imp', 'tp75', IMP, True), ('75L+imp noDFI', 'tp75', IMP, False)]
res = []
for name, lay, setx, dfi in VARS:
    M = mm2.Model(GR, lay, 20.0, setx)
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
        M.build(t0)
        if dfi: st = M.dfi(st)
        out = M.run_wx(st, cr, 24, 24)
        row = dict(var=name, start=TT[k])
        for ld in (0, 1):
            j = DI[(t0 + dt.timedelta(days=ld)).strftime('%Y-%m-%dT%H')]
            for kk in ('z500', 'mslp', 't850', 'u850'):
                s = WS.scores(WS.to_grid(out[kk][ld], M.lon, M.lat), TR['o_' + kk][j], None)
                for reg in ('globe', 'tropics', 'n_extratropics', 's_extratropics'):
                    row[f'd{ld}_{kk}_{reg}'] = (round(s[reg]['rmse'], 3), round(s[reg]['bias'], 3))
        res.append(row); print(name, TT[k], 'z500 d0', row['d0_z500_globe'], 'd1', row['d1_z500_globe'], 'mslp d0', row['d0_mslp_globe'], 'd1', row['d1_mslp_globe'], flush=True)
        json.dump(res, open(OUT, 'w'))
