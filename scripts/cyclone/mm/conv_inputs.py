"""What the convection is fed (11 Nov, Sridhar: 'if the scheme is right, check its inputs'). After HRS h with the IFS package, tropical
ocean columns: temperature / humidity / RH at 925 and 850 hPa vs ERA5 at the same valid time (wx_truth_moist), lowest-layer RH,
sub-cloud stratification, the BL + radiation heating profile handed to the closure (where the surface heat sits), H and E.
python conv_inputs.py LIB MOIST GRID START NLEV   (rad_dbg hook)"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
MT = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(MT['days'])}
GR, k, NL = sys.argv[3], int(sys.argv[4]), sys.argv[5]; NL = int(NL) if NL.isdigit() else NL
S = {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0, 'phys_ifs': 1.0, 'ck_z': 1.0, 'sfc_sal': 0.98, 'rad_prm': {'lw_cnt': 0.667, 'qs_mix': 1}, 'rad_dbg': 1}
if NL != 32: S.update(sfc_imp=1.0, drag_imp=1.0)
M = mm2.Model(GR, NL, 20.0, S); t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st); hor = M.coords.horizontal
tla = np.linspace(-90, 90, 121); TLA = np.repeat(tla[:, None], 240, 1); TW = np.cos(np.radians(TLA))
for h in (0, 24):
    if h: st, cr = mm2.integrate(M, st, cr, 24)
    aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
    T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl = hor.cos_lat
    u = aux.cos_lat_u[0]/cl/M.MPS; v = aux.cos_lat_u[1]/cl/M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA
    crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
    M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence)*M.SEC)
    I = [np.asarray(x) if hasattr(x, 'shape') else x for x in M._ifs_in]
    Tn, qn, pn, mass, zc, psn, H, E, ust, rho, land = I[:11]; dTb, dqb = I[13], I[14]
    qs = np.asarray(mm2.qsat(jnp.asarray(Tn), jnp.asarray(pn))); rh = qn / qs
    LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); m = (np.abs(LA) <= 25) & ~land.astype(bool)
    f = lambda X: float((X * W)[m].sum() / W[m].sum())
    # model on pressure levels, regridded, vs ERA5
    lp = np.log(pn); out = {}
    for P in (925, 850):
        x = np.log(P * 100.0); i_ = np.clip((lp < x).sum(0), 1, pn.shape[0] - 1)
        g = lambda A: np.take_along_axis(A, i_[None] - 1, 0)[0] + (np.take_along_axis(A, i_[None], 0)[0] - np.take_along_axis(A, i_[None] - 1, 0)[0]) * (x - np.take_along_axis(lp, i_[None] - 1, 0)[0]) / (np.take_along_axis(lp, i_[None], 0)[0] - np.take_along_axis(lp, i_[None] - 1, 0)[0])
        out[P] = (g(Tn), g(qn))
    j = DI[(t0 + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H')]
    TM = (np.abs(TLA) <= 25)
    Tm925 = WS.to_grid(out[925][0], M.lon, M.lat); qm925 = WS.to_grid(out[925][1], M.lon, M.lat)
    lsm = WS.to_grid(land.astype(float), M.lon, M.lat) < 0.5; mm_ = TM & lsm
    tm = lambda X: float(np.nansum(X * TW * mm_) / np.nansum(TW * mm_))
    import radcloud as R
    rh925_m = qm925 / R.qsat(Tm925, 92500.0); rh925_e = MT['o_q925'][j] / R.qsat(MT['o_t925'][j].astype(float), 92500.0)
    print(f'\n[{NL} levels] hour {h}, tropical ocean 25S-25N:')
    print(f'  925 hPa  T model {tm(Tm925):.2f} ERA5 {tm(MT["o_t925"][j]):.2f} | q model {tm(qm925)*1000:.2f} ERA5 {tm(MT["o_q925"][j])*1000:.2f} g/kg | RH model {tm(rh925_m):.3f} ERA5 {tm(rh925_e):.3f}')
    print(f'  surface fluxes: H {f(H):.1f} W/m2, E {f(E)*86400:.2f} mm/day (LvE {f(E)*2.5e6:.0f} W/m2); lowest layer (sigma {float(M.sig[-1]):.3f}, z {f(zc[-1]):.0f} m) RH {f(rh[-1]):.3f}')
    print('  layer: sigma | z m | RH | theta_v K | BL+rad heating handed to the closure, K/day | BL+rad moistening g/kg/day')
    thv = Tn * (psn[None] / pn) ** 0.2857 * (1 + 0.61 * qn)
    for kk in range(Tn.shape[0] - 1, Tn.shape[0] - (9 if NL == 32 else 20), -1):
        print(f'   {float(M.sig[kk]):.3f} | {f(zc[kk]):6.0f} | {f(rh[kk]):.3f} | {f(thv[kk]):.2f} | {f(dTb[kk])*86400:+7.2f} | {f(dqb[kk])*86400*1000:+6.2f}')
