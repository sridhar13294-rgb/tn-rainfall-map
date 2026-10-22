"""General weather exam for our model: 10-day forecasts from ERA5 starts (2020, every 5 days), scored against ERA5 with
the same code used for ECMWF's HRES (wxscore.py), so the two compare directly.
python wx2.py LIBM_WX_NPZ CONFIG_JSON CHUNK NCHUNK OUT_JSON
CONFIG: {"tag", "truth": wx_truth_2020.npz path, "grid", "dt_min", "days": 10, "ocean": path?, "variants": [{"name", "set"?}]}"""
import sys, os, json, time, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, wxscore as WS, landinit
LIB, CFG, CH, NCH, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
C = json.load(open(CFG)); ND = int(C.get('days', 10)); TRU = C['truth']
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = dict(np.load(TRU)); DI = {str(d): i for i, d in enumerate(TR['days'])}
KEYS = ['z500', 't850', 'mslp', 't2', 'rain24', 'u850', 'v850', 'u200', 'v200']
res = []; MODELS = {}
for n, key in enumerate(TT):
    if n % NCH != CH: continue
    t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    for var in (C.get('variants') or [dict(name='control')]):
        try:
            t = time.time()
            if var['name'] not in MODELS: MODELS[var['name']] = mm2.Model(var.get('grid', C.get('grid', 'T85')), 32, C.get('dt_min'), var.get('set'))
            M = MODELS[var['name']]
            st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                            Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], ocean=C.get('ocean'), when=t0,
                            **(landinit.land_kwargs(Z['f2'][k], V2) if C.get('land_init', True) else {}))
            M.build(t0); st = M.dfi(st)
            out = M.run_wx(st, cr, 24 * ND, 24)
            if not np.isfinite(out['mslp']).all(): raise RuntimeError('blew up')
            row = dict(start=t0.strftime('%Y-%m-%d'), var=var['name'], days={}, sec=0)
            for ld in range(1, ND + 1):
                v = (t0 + dt.timedelta(days=ld)).strftime('%Y-%m-%dT%H')
                if v not in DI: continue
                j = DI[v]; sc = {}
                for kk in KEYS:
                    if kk == 'rain24': f = out['rain'][ld] - out['rain'][ld - 1]
                    elif kk in out: f = out[kk][ld]
                    else: continue
                    o = TR['o_' + kk][j]; c = TR['c_' + kk][j]
                    if not np.isfinite(o).any(): continue
                    sc[kk] = WS.scores(WS.to_grid(f, M.lon, M.lat), o, c if np.isfinite(c).any() else None)
                row['days'][ld] = sc
            row['sec'] = round(time.time() - t); res.append(row)
            print(row['start'], var['name'], 'sec', row['sec'], 'z500 rmse d1/d5/d10', [round(row['days'].get(d, {}).get('z500', {}).get('globe', {}).get('rmse', -1), 1) for d in (1, 5, 10)], flush=True)
        except Exception as e:
            import traceback; traceback.print_exc(); res.append(dict(start=key, var=var['name'], err=repr(e)[:300])); print(key, var['name'], 'FAILED', repr(e)[:300], flush=True)
    json.dump(res, open(OUT, 'w'))
json.dump(res, open(OUT, 'w'))
