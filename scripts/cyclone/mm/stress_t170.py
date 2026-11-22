"""T170 surface-stress check (A/P1 drag branch, 22 Nov): one start (2020-01-06T00, library index 1), 24 h, lc_mix with stress_out
(+ sfc_mo when argv[2] == 'mo'); writes the day-1 mean surface stress on the 1.5-deg grid to argv[3] (npz). Usage on Kaggle:
python stress_t170.py <library.npz> <base|mo> <out.npz>"""
import sys, os, json, datetime as dt, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'analysis'))
import mm2, wxscore as WS, landinit
LIB, MODE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]; K = 1
Z0 = np.load(LIB); TT = [str(t) for t in Z0['times']]; V3 = [str(v) for v in Z0['v3']]; V2 = [str(v) for v in Z0['v2']]
f3 = Z0['f3'][K].astype(np.float32); f2 = Z0['f2'][K]
C = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'cyclone', 'kaggle_cfg', 'suite_lcmix_wx.json')))
var = dict(C['variants'][0]['set'], stress_out=1, **({'sfc_mo': 1} if MODE == 'mo' else {}))
t0 = dt.datetime.strptime(TT[K], '%Y-%m-%dT%H')
M = mm2.Model('T170', 32, C['dt_min'], var)
st, cr = M.init({v: f3[V3.index(v)] for v in V3}, Z0['levs'], Z0['lats'], Z0['lons'], f2[V2.index('surface_pressure')],
                f2[V2.index('geopotential_at_surface')] / 9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')],
                when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st)
out = M.run_wx(st, cr, 24, 24)
sav = {k + '_d1': WS.to_grid((np.asarray(out[k][1]) - np.asarray(out[k][0])) / 86400.0, M.lon, M.lat) for k in ('tx', 'ty', 'txn', 'fsta', 'staba')}
np.savez(OUT, **sav); print('saved', OUT, flush=True)
