"""Which physics heats the lower troposphere too fast? 24-h runs from a few exam starts with one process switched off or
changed at a time; 850 hPa temperature and 2-m temperature bias/RMSE against ERA5 after 1 day by region.
python wx_tend.py LIBM_WX_NPZ TRUTH_NPZ OUT_JSON [N_STARTS]"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, wxscore as WS, landinit
LIB, TRU, OUT = sys.argv[1], sys.argv[2], sys.argv[3]; NS = int(sys.argv[4]) if len(sys.argv) > 4 else 4
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = dict(np.load(TRU)); DI = {str(d): i for i, d in enumerate(TR['days'])}
BIG = 1e12
VARS = {'ctl': {}, 'no_deep': dict(tau_deep=BIG), 'no_shallow': dict(tau_shallow=BIG), 'no_conv': dict(tau_deep=BIG, tau_shallow=BIG),
        'ck_low': dict(ck=0.6e-3), 'tau_sh2': dict(tau_shallow=7200.0)}
STATIC = {'shallow_theta': dict(shallow='theta'), 'mf_kick': dict(conv='mf', mf_kick_t=0.5, mf_kick_q=0.0005), 'mf_kick_wup': dict(conv='mf', mf_kick_t=1.0, mf_kick_q=0.001, mf_wup=10.0)}
base = dict(rad='radcloud', rad_every=2); res = {}; models = {}
def score(out, M, t0):
    j = DI.get((t0 + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H')); r = {}
    for kk in ('t850', 't2', 'mslp', 'z500'):
        sc = WS.scores(WS.to_grid(out[kk][1], M.lon, M.lat), TR['o_' + kk][j]); r[kk] = {g: [round(v['rmse'], 2), round(v['bias'], 2)] for g, v in sc.items()}
    return r
for key in TT[:NS]:
    t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    for sname, sset in [('base', {})] + list(STATIC.items()):
        if sname not in models: models[sname] = mm2.Model('T85', 32, None, dict(base, **sset))
        M = models[sname]
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
        M.build(t0); st = M.dfi(st)
        for vn, vs in (VARS.items() if sname == 'base' else [('ctl', {})]):
            name = vn if sname == 'base' else sname
            try:
                out = M.run_wx(st, M.with_params(cr, vs), 24, 24); res.setdefault(name, []).append(score(out, M, t0))
            except Exception as e: print(name, 'FAILED', repr(e)[:200], flush=True)
            print(key, name, {kk: res[name][-1][kk]['tropics'] for kk in ('t850', 't2')} if name in res else '', flush=True)
    json.dump(res, open(OUT, 'w'))
summ = {n: {kk: {g: np.round(np.mean([x[kk][g] for x in L], 0), 2).tolist() for g in ('globe', 'tropics', 'india', 'tamil_nadu')} for kk in ('t850', 't2', 'mslp', 'z500')} for n, L in res.items()}
json.dump(dict(runs=res, mean=summ), open(OUT, 'w'))
for n, v in summ.items(): print(n, 't850 trop/india/TN', v['t850']['tropics'], v['t850']['india'], v['t850']['tamil_nadu'], 't2 globe', v['t2']['globe'])
