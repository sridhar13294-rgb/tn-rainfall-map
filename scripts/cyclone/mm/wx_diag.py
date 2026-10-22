"""Check the general-exam pipeline: our model's hour-0 fields (straight from the start, after the start filter) against ERA5
at the SAME time. They must agree closely (a few m for 500 hPa height); a large difference means a bug in extraction,
units, orientation or regridding, not forecast error. Also: day-1 RMSE of persistence (ERA5 start vs ERA5 +1 day).
python wx_diag.py LIBM_WX_NPZ TRUTH_NPZ OUT_JSON [N_STARTS]"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, wxscore as WS
LIB, TRU, OUT = sys.argv[1], sys.argv[2], sys.argv[3]; NS = int(sys.argv[4]) if len(sys.argv) > 4 else 3
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; LEV = [int(x) for x in Z['levs']]
TR = dict(np.load(TRU)); DI = {str(d): i for i, d in enumerate(TR['days'])}
la_lib = np.asarray(Z['lats'], float); lo_lib = np.asarray(Z['lons'], float)
def lib_grid(a):                                                     # lib field [lat, lon] -> 121x240 ascending lat
    a = np.asarray(a, float)
    if la_lib[0] > la_lib[-1]: a = a[::-1]
    return a
res = []; M = None
for key in TT[:NS]:
    t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    if M is None: M = mm2.Model('T85', 32, None, {'rad': 'radcloud'})
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                    Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')])
    M.build(t0); st0 = st; st = M.dfi(st)
    out = M.run_wx(st, cr, 24, 24)
    e_z500 = lib_grid(f3['geopotential'][LEV.index(500)]) / 9.80665; e_t850 = lib_grid(f3['temperature'][LEV.index(850)])
    r = dict(start=key, lib_lat_order='desc' if la_lib[0] > la_lib[-1] else 'asc', lib_shape=list(np.shape(f3['temperature'])),
             model_lat_first_last=[float(M.lat[0]), float(M.lat[-1])], model_lon_first_last=[float(M.lon[0]), float(M.lon[-1])])
    z0 = WS.to_grid(out['z500'][0], M.lon, M.lat); t0g = WS.to_grid(out['t850'][0], M.lon, M.lat)
    r['h0_vs_era5_start'] = dict(z500=WS.scores(z0, e_z500)['globe'], t850=WS.scores(t0g, e_t850)['globe'], t850_tropics=WS.scores(t0g, e_t850)['tropics'])
    r['h0_flipped_lat'] = WS.scores(z0[::-1], e_z500)['globe']
    r['h0_z500_regions'] = {k: round(v['rmse'], 1) for k, v in WS.scores(z0, e_z500).items()}
    dz = z0 - e_z500; bands = {}
    for a0 in range(-90, 90, 10):
        m = (WS.LA >= a0) & (WS.LA < a0 + 10); bands[a0] = [round(float(np.sqrt(np.mean(dz[m] ** 2))), 1), round(float(np.mean(dz[m])), 1)]
    r['h0_z500_bands_rmse_bias'] = bands
    j_ = np.unravel_index(np.argmax(np.abs(dz)), dz.shape); r['h0_z500_worst'] = [float(WS.LA[j_]), float(WS.LO[j_]), float(dz[j_])]
    oro = lib_grid(Z['f2'][k, V2.index('geopotential_at_surface')]) / 9.80665
    for lim in (500, 1500):
        m = oro < lim; r[f'h0_z500_rmse_oro_lt_{lim}'] = round(float(np.sqrt(np.mean(dz[m] ** 2))), 1)
    m2 = np.abs(WS.LA) < 60; r['h0_z500_rmse_60S_60N'] = round(float(np.sqrt(np.mean(dz[m2] ** 2))), 1)
    j = DI.get((t0 + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H'))
    if j is not None:
        o1 = TR['o_z500'][j]; r['persistence_d1_z500'] = WS.scores(e_z500, o1)['globe']
        r['ours_d1_z500'] = WS.scores(WS.to_grid(out['z500'][1], M.lon, M.lat), o1)['globe']
        r['truth_d1_vs_lib_start_shape'] = [list(o1.shape), float(np.nanmean(o1)), float(np.nanmean(e_z500))]
    for lab, ix in (('h0', 0), ('d1', 1)):                                                     # surface fields and t850 vs ERA5 truth (bias, rmse by region)
        jj = DI.get((t0 + dt.timedelta(days=ix)).strftime('%Y-%m-%dT%H'))
        if jj is None: continue
        for kk in ('t2', 't2_old', 'mslp', 't850'):
            if kk not in out or ('o_' + kk.replace('_old', '')) not in TR: continue
            sc = WS.scores(WS.to_grid(out[kk][ix], M.lon, M.lat), TR['o_' + kk.replace('_old', '')][jj])
            r[f'{lab}_{kk}'] = {g_: [round(v_['rmse'], 2), round(v_['bias'], 2)] for g_, v_ in sc.items()}
    r['means'] = dict(model_z500_h0=float(np.mean(z0)), era5_z500=float(np.mean(e_z500)), model_t850_h0=float(np.mean(t0g)), era5_t850=float(np.mean(e_t850)))
    res.append(r); print(json.dumps(r)[:1500], flush=True)
json.dump(res, open(OUT, 'w'), default=float)
