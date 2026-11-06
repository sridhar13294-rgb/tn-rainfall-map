"""DFI on vs off (6 Nov 13:15, registered rootcause 13:10): T42, Oct 2020 starts. Hour-0 C-India MSLP bias, day-1 global
MSLP and z500 RMSE vs ERA5, and a noise measure (global mean |d ps / dt| over the first 3 h, hPa/h)."""
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
LIB, TRU, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = np.load(TRU); DI = {str(d): i for i, d in enumerate(TR['days'])}
la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float); w = np.cos(np.radians(la))[:, None] * np.ones((1, len(lo)))
box = np.ix_((la >= 18) & (la <= 26), (lo >= 74) & (lo <= 86))
rmse = lambda d: float(np.sqrt(np.nansum(w * d ** 2) / np.nansum(w * np.isfinite(d))))
M = mm2.Model('T42', 32, None, {'rad': 'radcloud', 'rad_every': 2, 'rd_si': 1})
res = {True: [], False: []}
for key in [k for k in TT if k[5:7] == '10' and k.endswith('T00')][:N]:
    k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    d1 = (t0 + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H')
    if key not in DI or d1 not in DI: continue
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); hor = M.coords.horizontal
    for dfi in (True, False):
        s0 = M.dfi(st) if dfi else st
        out = M.run_wx(s0, cr, 24, 24); o3 = M.run_wx(s0, cr, 3, 3)
        g = lambda F: np.asarray(WS.to_grid(F, M.lon, M.lat))
        h0 = float(np.nanmean((g(out['mslp'][0]) - TR['o_mslp'][DI[key]])[box])) / 100
        m1 = rmse((g(out['mslp'][1]) - TR['o_mslp'][DI[d1]]) / 100); z1 = rmse(g(out['z500'][1]) - TR['o_z500'][DI[d1]])
        noise = float(np.mean(np.abs(np.asarray(o3['mslp'][1]) - np.asarray(o3['mslp'][0])))) / 100 / 3
        res[dfi].append((h0, m1, z1, noise))
        print(f'{key} DFI={dfi}: hour-0 C-India MSLP {h0:+.2f} hPa | day-1 MSLP RMSE {m1:.2f} hPa | z500 RMSE {z1:.2f} m | |dMSLP/dt| first 3 h {noise:.3f} hPa/h', flush=True)
for dfi in (True, False):
    a = np.array(res[dfi]); print(f'MEAN DFI={dfi}:', np.round(a.mean(0), 3).tolist())
