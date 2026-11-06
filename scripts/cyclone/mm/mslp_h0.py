"""Hour-0 MSLP check (6 Nov): central India (18-26 N, 74-86 E) model MSLP at hour 0 vs ERA5 msl, Oct-Dec 2020 starts.
Decomposition: (a) total MSLP bias; (b) surface-pressure bias (state: model ps on model terrain vs ERA5 ps); (c) the
reduction itself: ERA5's own ps reduced with MEGAM's IFS-style formula (lowest-level T = ERA5 T at the pressure level
just above the surface) vs ERA5 msl -> formula difference independent of the model state.
python mslp_h0.py LIB TRUTH GRID N_STARTS"""
import sys, os, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
LIB, TRU, GR, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = np.load(TRU); DI = {str(d): i for i, d in enumerate(TR['days'])}; OM = TR['o_mslp']
la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float); levs = np.asarray(Z['levs'], float)
box = np.ix_((la >= 18) & (la <= 26), (lo >= 74) & (lo <= 86))
import json; M = mm2.Model(GR, 32, None, dict({'rad': 'radcloud', 'rad_every': 2, 'rd_si': 1}, **(json.loads(sys.argv[5]) if len(sys.argv) > 5 else {})))
RD, G = 287.04, 9.80665
starts = [k for k in TT if k[5:7] in ('10', '11', '12') and k.endswith('T00')][::max(1, 1)][:N]
A = []; B = []; C = []
for key in starts:
    k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    if key not in DI: continue
    ps_e = f2[V2.index('surface_pressure')]; zs_e = f2[V2.index('geopotential_at_surface')] / 9.80616
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], ps_e, zs_e, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st_raw = st; st = M.dfi(st); out = M.run_wx(st, cr, 24, 24); out_raw = M.run_wx(st_raw, cr, 24, 24)
    hor = M.coords.horizontal; import jax.numpy as jnp
    def low(s_):
        T = (np.asarray(hor.to_nodal(s_.temperature_variation))[-1] + np.asarray(M.ref_t)[-1]) / M.K
        ps = np.asarray(jnp.exp(hor.to_nodal(s_.log_surface_pressure))[0]) / M.PA
        return np.asarray(WS.to_grid(T, M.lon, M.lat)), np.asarray(WS.to_grid(ps, M.lon, M.lat))
    Tl_d, ps_d = low(st); Tl_r, ps_r = low(st_raw)
    msl_r = np.asarray(WS.to_grid(out_raw['mslp'][0], M.lon, M.lat))
    msl_m = np.asarray(WS.to_grid(out['mslp'][0], M.lon, M.lat)); msl_e = OM[DI[key]]
    # ERA5's own ps reduced with the IFS-style formula: T at the lowest pressure level above the ground
    T3 = f3['temperature']; Tlow = np.full(ps_e.shape, np.nan)
    for i in range(len(levs)):                                   # levels ordered top->bottom or bottom->top: take the highest-pressure level <= ps
        ok = levs[i] * 100 <= ps_e
        better = ok & (np.isnan(Tlow) | (levs[i] > np.nanmax([0])))
    order = np.argsort(levs)[::-1]
    for i in order:
        m = np.isnan(Tlow) & (levs[i] * 100 <= ps_e); Tlow[m] = T3[i][m]
    a0 = 0.0065 * RD / G; Tst = Tlow; T0 = Tst + 0.0065 * zs_e
    alpha = np.where((T0 > 290.5) & (Tst <= 290.5), RD * (290.5 - Tst) / np.maximum(G * zs_e, 1.0), 0.0065 * RD / G)
    alpha = np.where((T0 > 290.5) & (Tst > 290.5), 0.0, alpha); Tst = np.where((T0 > 290.5) & (Tst > 290.5), 0.5 * (290.5 + Tst), Tst)
    Tst = np.where(Tst < 255.0, 0.5 * (255.0 + Tst), Tst); x = G * zs_e / (RD * Tst)
    msl_f = np.where(zs_e > 1.0, ps_e * np.exp(x * (1 - alpha * x / 2 + (alpha * x) ** 2 / 3)), ps_e)
    a = float(np.nanmean((msl_m - msl_e)[box])) / 100; c = float(np.nanmean((msl_f - msl_e)[box])) / 100
    A.append(a); C.append(c)
    pl = float(levs.max()) * 100
    print(f'   no-DFI MSLP bias {float(np.nanmean((msl_r - msl_e)[box]))/100:+.2f} hPa | lowest-level T: DFI-raw {float(np.nanmean((Tl_d - Tl_r)[box])):+.2f} K | ps DFI-raw {float(np.nanmean((ps_d - ps_r)[box]))/100:+.2f} hPa | ps raw-ERA5 {float(np.nanmean((ps_r - ps_e)[box]))/100:+.2f} hPa (terrain differs)')
    print(f'{key} {GR}: hour-0 C-India MSLP bias model {a:+.2f} hPa | ERA5 ps with MEGAM formula vs ERA5 msl {c:+.2f} hPa | mean terrain {float(zs_e[box].mean()):.0f} m', flush=True)
print('MEAN model', round(np.mean(A), 2), 'formula-only', round(np.mean(C), 2))
