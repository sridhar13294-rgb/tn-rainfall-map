"""Hour-0 vs day-1 MSLP bias map near the Bay (10 Nov, P5): is the high-pressure error NE of the Bay (24N 90-105E) already in
the start state (init + DFI, exactly as in the forecasts) or does it grow during day 1?
python h0_map.py LIB TRUTH GRID [N]  (Oct-Nov 2020 T00 starts)"""
import sys, datetime as dt, numpy as np
sys.path.insert(0, '.'); import mm2, landinit
LIB, TRU, GR = sys.argv[1], sys.argv[2], sys.argv[3]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 12
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = np.load(TRU); DI = {str(d): i for i, d in enumerate(TR['days'])}
la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
starts = [k for k, t in enumerate(TT) if t[5:7] in ('10', '11') and t.endswith('T00')][:N]
M = mm2.Model(GR, 32, None, {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1, 'rd_si': 1})
def g(F):                                   # model nodal [lon, lat] -> library grid [lat, lon] (nearest)
    F = np.asarray(F); mla, mlo = np.asarray(M.lat), np.asarray(M.lon)
    ii = np.abs(mla[None, :] - la[:, None]).argmin(1); jj = np.abs(mlo[None, :] - lo[:, None]).argmin(1)
    return F[np.ix_(jj, ii)].T
acc = {0: [], 1: []}
for k in starts:
    t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); out = M.run_wx(st, cr, 24, 24)
    for d in (0, 1):
        key = (t0 + dt.timedelta(days=d)).strftime('%Y-%m-%dT%H'); acc[d].append(g(out['mslp'][d]) / 100.0 - TR['o_mslp'][DI[key]] / 100.0)
    print(TT[k], 'done', flush=True)
for d in (0, 1):
    F = np.mean(acc[d], 0); print(f'\nMSLP bias hour {24*d} (hPa), mean of {len(starts)} starts, {GR}; rows lat, cols lon 80..120 E')
    for lat in range(33, 2, -3):
        i = int(np.argmin(np.abs(la - lat))); print(f'{lat:3d} ' + ' '.join(f'{F[i, int(np.argmin(np.abs(lo - x)))]:+5.1f}' for x in range(80, 121, 5)))
    box = np.ix_((la >= 21) & (la <= 27), (lo >= 90) & (lo <= 105)); print(f'box 21-27N 90-105E mean {np.nanmean(F[box]):+.2f} hPa')
