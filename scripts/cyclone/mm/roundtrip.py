"""P1 / track offline check (4 Nov): bias at hour 0 (start state as the model sees it, through the same output code) and
hour 24, vs ERA5 truth, with and without the initialisation filter (DFI). A bias already at hour 0 is an initialisation /
output-conversion problem, not a physics problem.  python roundtrip.py LIB TRUTH OUT 'START1,..' [GRID]"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, wxscore as WS, landinit
LIB, TRU, OUT, STARTS = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(','); GR = sys.argv[5] if len(sys.argv) > 5 else 'T170'
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = dict(np.load(TRU)); DI = {str(d): i for i, d in enumerate(TR['days'])}
M = mm2.Model(GR, 32, None, {'rad': 'radcloud', 'rad_every': 2}); res = {}
REG = ('tropics', 'india', 'india_south', 'tamil_nadu', 'india_central')
for key in STARTS:
    key = key if 'T' in key else key + 'T00'; k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    for dfi in (False, True):
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0)
        if dfi: st = M.dfi(st)
        out = M.run_wx(st, cr, 24, 24); r = {}
        for ld in (0, 1):
            v = (t0 + dt.timedelta(days=ld)).strftime('%Y-%m-%dT%H'); j = DI[v]; sc = {}
            for kk in ('t850', 'mslp', 'z500', 'u850', 'v850', 'u200', 'v200'):
                s = WS.scores(WS.to_grid(out[kk][ld], M.lon, M.lat), TR['o_' + kk][j], None)
                sc[kk] = {g: round(float(s[g]['bias']) / (100 if kk == 'mslp' else 1), 2) for g in REG}
            r[f'h{24 * ld}'] = sc
        res[f'{key} dfi={dfi}'] = r
        print(key, 'dfi' if dfi else 'raw', json.dumps({h: {kk: [v_[g] for g in REG] for kk, v_ in x.items()} for h, x in r.items()}), flush=True)
    json.dump(dict(regions=REG, **res), open(OUT, 'w'), indent=1)
