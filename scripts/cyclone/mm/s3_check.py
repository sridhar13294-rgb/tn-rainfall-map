"""S3 (12 Nov): hour-0 central-India MSLP excess WITHOUT any time step (no DFI, no run): the model's initial state reduced to sea level
with the model's own IFS-style formula, vs ERA5 msl (truth), at the model grid (T170 by default; init only, no compile of the stepper).
Decomposes the box bias by terrain change dz = model terrain - ERA5 terrain and by lowest-level temperature, and checks the
reduction formula on ERA5's own state. python s3_check.py LIB TRUTH GRID N_STARTS"""
import sys, os, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
import jax.numpy as jnp
LIB, TRU, GR, N = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = np.load(TRU); DI = {str(d): i for i, d in enumerate(TR['days'])}; OM = TR['o_mslp']
RD, G = 287.04, 9.80665
M = mm2.Model(GR, 32, None, {'rad': 'radcloud', 'rad_every': 2, 'rd_si': 1}); hor = M.coords.horizontal
tla = np.linspace(-90, 90, 121); tlo = np.arange(240) * 1.5
box = ((tla >= 18) & (tla <= 26))[:, None] & ((tlo >= 74) & (tlo <= 86))[None, :]
def reduce(ps, Tl, zs, sig_low):
    a0 = 0.0065 * RD / G; Tst = Tl * (1 + a0 * (1.0 / sig_low - 1)); T0 = Tst + 0.0065 * zs
    alpha = np.where((T0 > 290.5) & (Tst <= 290.5), RD * (290.5 - Tst) / np.maximum(G * zs, 1.0), 0.0065 * RD / G)
    alpha = np.where((T0 > 290.5) & (Tst > 290.5), 0.0, alpha); Tst = np.where((T0 > 290.5) & (Tst > 290.5), 0.5 * (290.5 + Tst), Tst)
    Tst = np.where(Tst < 255.0, 0.5 * (255.0 + Tst), Tst); x = G * zs / (RD * Tst)
    return np.where(zs > 1.0, ps * np.exp(x * (1 - alpha * x / 2 + (alpha * x) ** 2 / 3)), ps)
starts = [k for k in TT if k[5:7] in ('10', '11', '12') and k.endswith('T00') and k in DI][:N]
rows = []
for key in starts:
    k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    ps_e = f2[V2.index('surface_pressure')]; zs_e = f2[V2.index('geopotential_at_surface')] / 9.80616
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], ps_e, zs_e, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    T = (np.asarray(hor.to_nodal(st.temperature_variation)) + np.asarray(M.ref_t)[:, None, None]) / M.K
    ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]) / M.PA
    zs_m = np.asarray(M.zs, float); zs_ea = np.maximum(np.asarray(M.to_nodes(zs_e, Z['lats'], Z['lons'])), 0.0)
    msl_m = reduce(ps, T[-1], zs_m, float(M.sig[-1]))
    G_ = lambda X: np.asarray(WS.to_grid(np.asarray(X, float), M.lon, M.lat))
    om = OM[DI[key]].astype(float)
    om = om * 100.0 if np.nanmax(om) < 2000 else om
    b = G_(msl_m) - om; dz = G_(zs_m - zs_ea); Tl = G_(T[-1])
    rows.append(dict(key=key, bias=float(np.nanmean(b[box])) / 100, dz=float(np.nanmean(dz[box])), dzabs=float(np.nanmean(np.abs(dz[box]))),
                     corr_dz=float(np.corrcoef(b[box], dz[box])[0, 1]), corr_T=float(np.corrcoef(b[box], Tl[box])[0, 1]),
                     slope_dz=float(np.polyfit(dz[box], b[box] / 100, 1)[0] * 100), bias_dz_small=float(np.nanmean((b / 100)[box & (np.abs(dz) < 30)]))))
    print(rows[-1], flush=True)
print('mean box bias %.2f hPa; where |dz| < 30 m %.2f hPa; mean dz %.1f m; corr(bias,dz) %.2f; corr(bias,T_low) %.2f' % tuple(
    np.mean([r[k_] for r in rows]) for k_ in ('bias', 'bias_dz_small', 'dz', 'corr_dz', 'corr_T')))
