"""Closed total-energy audit of one MEGAM time step (10 Nov, Sridhar/peer: 'close the energy budget first').
Total energy per unit area  E = sum_k dsig_k ps/g (cp T + Lv q + (u^2 + v^2)/2) + Phi_s ps/g   (hydrostatic: internal + potential
of the column = cp T + surface term; latent with Lv q; kinetic). For a state S along a forecast, one step dt is split:
  FULL      E(step(S)) - E(S)                           physics + dynamics + diffusion + coupling, the real model step
  DYN       E(step_dyn(S)) - E(S)                       same step with physics off (core: semi-Lagrangian + semi-implicit + diffusion)
  FILT      E(filter(S)) - E(S)                         spectral horizontal diffusion alone, applied once
  PHYS      sum dsig ps/g (cp dT + Lv dq + u du + v dv) * dt   from the physics tendencies at S (exact, nodal)
    of which RAD (cp * radiative heating), SFC (H + Lv E surface fluxes = what turbulence/convection may add net),
    KE (u du + v dv: kinetic energy removed by drag/CMT without heating it back)
  COUPLING  FULL - DYN - PHYS                            what is lost/gained when the physics tendencies enter the step
All as global (and band) means in W/m2. Also global mean layer thicknesses 1000-850 / 850-500 / 500-200 hPa and T by layer at
each audit time (thermal vs mass/coordinate drift, peer point).  python energy_audit.py LIB_NPZ GRID START[,START] HOURS OUT_JSON"""
import sys, os, json, datetime as dt, numpy as np, jax, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit, pickle
MODE = os.environ.get('MODE', 'full')   # 10 Nov: 'full' (model + saves states) then 'dyn' (physics-off model on the saved states): one model per process (7 GB OOM)
from dinosaur import primitive_equations
G, CP, LV, RD = 9.80616, 1004.6, 2.5e6, 287.04
LIB, GR, STARTS, HOURS, OUT = sys.argv[1], sys.argv[2], sys.argv[3].split(','), int(sys.argv[4]), sys.argv[5]
B2 = {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1, 'rd_si': 1}
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
M = mm2.Model(GR, 32, None, dict(B2, phys_off=(MODE == 'dyn')))
hor = M.coords.horizontal; dsig = np.asarray(M.dsig); sig = np.asarray(M.sig)
LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); BANDS = {'globe': np.abs(LA) <= 90, 'tropics 30S-30N': np.abs(LA) <= 30,
                                                          'NH 30-90N': LA > 30, 'SH 30-90S': LA < -30}
def gm(X, m): return float((X * W)[m].sum() / W[m].sum())
def fields(S):
    aux = primitive_equations.compute_diagnostic_state_sigma(S.replace(tracers={}), M.coords)
    T = np.asarray((aux.temperature_variation + M.ref_t[:, None, None]) / M.K, float); cl = np.asarray(hor.cos_lat)
    u = np.asarray(aux.cos_lat_u[0] / cl / M.MPS, float); v = np.asarray(aux.cos_lat_u[1] / cl / M.MPS, float)
    q = np.asarray(S.tracers['specific_humidity'], float); ps = np.asarray(jnp.exp(hor.to_nodal(S.log_surface_pressure))[0] / M.PA, float)
    return T, q, u, v, ps
def energy(S):
    T, q, u, v, ps = fields(S); m = dsig[:, None, None] * ps[None] / G
    parts = dict(cpT=(m * CP * T).sum(0), Lq=(m * LV * q).sum(0), K=(m * 0.5 * (u ** 2 + v ** 2)).sum(0), PHIs=G * np.asarray(M.zs, float) * ps / G)
    parts['E'] = parts['cpT'] + parts['Lq'] + parts['K'] + parts['PHIs']; return parts
def thick(S):
    T, q, u, v, ps = fields(S); Tv = T * (1 + 0.608 * q); p = sig[:, None, None] * ps[None]
    lnp = np.log(p); out = {}
    for a, b in ((100000., 85000.), (85000., 50000.), (50000., 20000.)):
        ok = ps >= a                                          # only columns where the whole layer is above ground
        # thickness = R/g * integral Tv dlnp over [b, a], by trapezoid on sigma levels inside the layer (plus end interpolation)
        x = np.linspace(np.log(b), np.log(a), 40); TvI = np.empty((40,) + ps.shape)
        for i in range(ps.shape[0]):
            for j in range(ps.shape[1]):
                TvI[:, i, j] = np.interp(x, lnp[:, i, j], Tv[:, i, j])
        dz = RD / G * np.trapezoid(TvI, x, axis=0); out[f'{int(a/100)}-{int(b/100)}'] = (gm(dz, ok), gm(TvI.mean(0), ok))
    return out
res = {}
for key in STARTS:
    key = key if 'T' in key else key + 'T00'; k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]
    f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    args = (f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
            f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')])
    st, cr = M.init(*args, when=t0, **landinit.land_kwargs(f2, V2)); M.build(t0); st = M.dfi(st)
    SPD = os.environ.get('SPDIR', '/tmp/claude-0'); os.makedirs(SPD, exist_ok=True); SP = f'{SPD}/ea_states_{GR}_{key}.pkl'
    if MODE == 'dyn':
        SAVED = pickle.load(open(SP, 'rb')); prev = json.load(open(OUT)); out_rows = prev[key]['rows']
        for r, (h, st_, cr_) in zip(out_rows, SAVED):
            st_ = jax.tree_util.tree_map(jnp.asarray, st_); cr_ = jax.tree_util.tree_map(jnp.asarray, cr_)
            M._carry = cr_; Sd = M.step(st_); E0_ = energy(st_)['E']
            for bn, bm in BANDS.items():
                r[bn]['DYN'] = gm(energy(Sd)['E'] - E0_, bm) / M.dt_s; r[bn]['COUPLING'] = r[bn]['FULL'] - r[bn]['DYN'] - r[bn]['PHYS']
            g_ = r['globe']; print(f'{key} {GR} h{h:3d} globe W/m2: FULL {g_["FULL"]:+7.2f} = DYN {g_["DYN"]:+7.2f} + PHYS {g_["PHYS"]:+7.2f} (RAD {g_["RAD"]:+7.2f} SFC {g_["SFC"]:+6.2f} KE {g_["KE_phys"]:+5.2f}) + COUPLING {g_["COUPLING"]:+6.2f} | FILT {g_["FILT"]:+6.2f}', flush=True)
        json.dump(prev, open(OUT, 'w')); continue
    rows = []; E00 = energy(st); TH0 = thick(st); SAVED = []
    for h in range(0, HOURS + 1, 3):
        if h > 0: st, cr = mm2.integrate(M, st, cr, 3)
        crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0))
        M._carry = crx; SAVED.append((h, jax.device_get(st), jax.device_get(crx)))
        S_full = M.step(st); S_dyn = st; S_f = M.filt(st, st)
        T, q, u, v, ps = fields(st); S_ = st
        tend, diag = M.column(jnp.asarray(T, jnp.float32), jnp.asarray(q, jnp.float32), jnp.asarray(u, jnp.float32), jnp.asarray(v, jnp.float32),
                              jnp.asarray(ps, jnp.float32), crx, want_diag=True, div=hor.to_nodal(st.divergence) * M.SEC)
        m = dsig[:, None, None] * ps[None] / G; tT, tq, tu, tv = [np.asarray(tend[x], float) for x in ('T', 'q', 'u', 'v')]
        P = (m * (CP * tT + LV * tq + u * tu + v * tv)).sum(0); PKE = (m * (u * tu + v * tv)).sum(0)
        PRAD = (m * CP * np.asarray(diag['rad_app'], float)).sum(0) if 'rad_app' in diag else np.zeros_like(ps)
        PSFC = np.asarray(diag['H'], float) + LV * np.asarray(diag['E'], float)
        E0 = energy(st)['E']; dts = M.dt_s
        rc = crx.get('rad', {}); SIGSB = 5.67e-8
        RADC = {k: np.asarray(rc[k], float) for k in ('olr', 'lw_dn_sfc', 'sw_net_sfc') if k in rc}
        if RADC: RADC['lw_up_sfc'] = SIGSB * np.asarray(diag['Ts'], float) ** 4; RADC['H'] = np.asarray(diag['H'], float); RADC['LvE'] = LV * np.asarray(diag['E'], float)
        r = {'hour': h}
        for bn, bm in BANDS.items():
            full = gm(energy(S_full)['E'] - E0, bm) / dts; dyn = gm(energy(S_dyn)['E'] - E0, bm) / dts; fil = gm(energy(S_f)['E'] - E0, bm) / dts
            phys = gm(P, bm); r[bn] = dict(FULL=full, DYN=dyn, FILT=fil, PHYS=phys, RAD=gm(PRAD, bm), SFC=gm(PSFC, bm), KE_phys=gm(PKE, bm),
                                            PHYS_minus_RAD_SFC_KE=phys - gm(PRAD, bm) - gm(PSFC, bm) - gm(PKE, bm), COUPLING=full - dyn - phys)
        if RADC:
            r['rad_parts'] = {k: gm(X, BANDS['globe']) for k, X in RADC.items()}
            r['rad_parts']['LW_atm'] = -r['rad_parts']['olr'] + r['rad_parts']['lw_up_sfc'] - r['rad_parts']['lw_dn_sfc']
            r['rad_parts']['SW_abs_atm (RAD - LW_atm)'] = r['globe']['RAD'] - r['rad_parts']['LW_atm']
            print('   rad parts globe W/m2: ' + ' '.join(f'{k} {x:+.1f}' for k, x in r['rad_parts'].items()), flush=True)
        r['globe']['DYN'] = None; r['globe']['COUPLING'] = None   # filled by MODE=dyn
        Enow = energy(st); r['drift_since_0'] = {c: gm(Enow[c] - E00[c], BANDS['globe']) for c in ('E', 'cpT', 'Lq', 'K', 'PHIs')}
        rows.append(r); g_ = r['globe']
        print(f'{key} {GR} h{h:3d} globe W/m2: FULL {g_["FULL"]:+7.2f} + PHYS {g_["PHYS"]:+7.2f} (RAD {g_["RAD"]:+7.2f} '
              f'SFC {g_["SFC"]:+6.2f} KE {g_["KE_phys"]:+5.2f} rest {g_["PHYS_minus_RAD_SFC_KE"]:+5.2f}) | FILT {g_["FILT"]:+6.2f} '
              f'| drift since h0 E {r["drift_since_0"]["E"] / 1e6:+.3f} MJ/m2', flush=True)
    TH1 = thick(st)
    res[key] = dict(rows=rows, thick0=TH0, thick_end=TH1); pickle.dump(SAVED, open(SP, 'wb'))
    print(f'{key} {GR} layer thickness (m) and mean Tv (K), h0 -> h{HOURS}: ' + ' | '.join(f'{L}: {TH0[L][0]:.1f} -> {TH1[L][0]:.1f} ({TH1[L][0]-TH0[L][0]:+.1f} m), Tv {TH0[L][1]:.2f} -> {TH1[L][1]:.2f}' for L in TH0), flush=True)
    json.dump(res, open(OUT, 'w'))
