"""Step 1(b), 4 Nov: is MEGAM's radiation right? (global rain 3.7 vs ~2.7 mm/day must be balanced by atmospheric radiative
cooling; OLR 209 vs ~240 W/m2.) Control run to day 3; on ~1500 sampled columns of the SAME state:
  (1) CLEAR SKY, same gases (H2O, CO2, O3 only - what radcloud has): radcloud vs RRTMG (Mlawer 1997 / Iacono 2008, the
      GFS/WRF/CESM reference code, via climlab-rrtmg) -> OLR, surface LW down, LW heating profile, SW absorbed by the
      atmosphere and the surface. Differences here = gas-optics formulation errors in radcloud.
  (2) the same RRTMG with CH4 1.9 ppm and N2O 0.33 ppm -> what the missing gases are worth.
  (3) ALL SKY from the model itself: cloud radiative effects (LW CRE = OLR_clr - OLR, SW CRE), total cover, cloud water
      paths, atmospheric net radiative cooling, vs CERES-EBAF / ISCCP global values (observations; context, not targets).
python rad_check.py LIB_NPZ OUT_JSON 'START1,START2' [HOURS=72]
Needs climlab + climlab-rrtmg (the Kaggle job installs gfortran + meson and builds climlab-rrtmg from source)."""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit, radcloud
from dinosaur import spherical_harmonic
G = 9.80616
LIB, OUT, STARTS = sys.argv[1], sys.argv[2], sys.argv[3].split(','); HRS = int(sys.argv[4]) if len(sys.argv) > 4 else 72
GRID = os.environ.get('RC_GRID', 'T170')
try:
    import climlab; from climlab.radiation import RRTMG; HAVE = True
except Exception as e:
    print('RRTMG not available:', repr(e)[:200], flush=True); HAVE = False
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
M = mm2.Model(GRID, 32, None, {'rad': 'radcloud', 'rad_every': 2})
MC = mm2.Model(GRID, 32, None, {'rad': 'radcloud', 'rad_every': 1, 'ent_top': 1.0})      # same model, fresh radiation + clear-sky outputs (snapshot only)
RK0 = mm2.RADKEYS; RKX = RK0 + ('olr_clr', 'lw_dn_sfc_clr', 'lw_up_sfc', 'lw_heating_clr', 'sw_toa_dn', 'sw_toa_up', 'sw_toa_up_clr', 'sw_net_sfc_clr', 'lwp', 'iwp')
CO2 = radcloud.DEFAULTS.get('co2_ppm', 400.0)
OBS = dict(note='CERES-EBAF Ed4 global annual means (Loeb et al. 2018) and ISCCP/CERES cloud cover; approximate',
           OLR=240.0, OLR_clr=266.0, LW_CRE=26.0, SW_CRE=-47.0, ASR=240.0, cover=0.67, atm_rad_cooling=-105.0)
res = dict(co2_ppm=CO2, obs=OBS, grid=GRID)
def rrtmg_col(p_hpa, T, q, o3_vmr, Ts, alb, coszen, insol, gases_full=False):
    st = climlab.column_state(lev=p_hpa, water_depth=1.0); st['Tatm'][:] = T; st['Ts'][:] = Ts
    vmr = dict(CO2=CO2 * 1e-6, O3=o3_vmr, CH4=1.9e-6 if gases_full else 0.0, N2O=3.3e-7 if gases_full else 0.0, O2=0.21,
               CFC11=0.0, CFC12=0.0, CFC22=0.0, CCL4=0.0)
    r = RRTMG(state=st, specific_humidity=q, absorber_vmr=vmr, albedo=alb, coszen=max(coszen, 1e-4), insolation=insol,
              icld=0, timestep=3600.0)
    r.compute_diagnostics()
    D = r.diagnostics
    return dict(OLRclr=float(D['OLRclr']), LWdn_sfc_clr=float(D['LW_flux_down_clr'][-1]), ASRclr=float(D['ASRclr']),
                SWdn_sfc_clr=float(D['SW_flux_down_clr'][-1]), SWup_sfc_clr=float(D['SW_flux_up_clr'][-1]),
                TdotLW_clr=np.asarray(D['TdotLW_clr'], float))
for key in STARTS:
    key = key if 'T' in key else key + 'T00'; k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H')
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; f2 = Z['f2'][k]
    args = (f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / G,
            f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')])
    st, cr = M.init(*args, when=t0, **landinit.land_kwargs(f2, V2)); M.build(t0); st = M.dfi(st)
    st, cr = mm2.integrate(M, st, cr, HRS); hor = M.coords.horizontal
    T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
    ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
    _s, _c = MC.init(*args, when=t0, **landinit.land_kwargs(f2, V2)); MC.build(t0)
    crc = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0))
    mm2.RADKEYS = RKX
    tn, d = MC.column(T, q, u / M.MPS, v / M.MPS, ps, crc, rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
    mm2.RADKEYS = RK0
    F = {kk: np.asarray(x) for kk, x in d['rad'].items()}                                         # the model's own radiation on this state (its clouds)
    Tn = np.asarray(T); qn = np.asarray(q); psn = np.asarray(ps); sig = np.asarray(M.sig)[:, None, None]
    p = sig * psn[None]; Ts = np.asarray(d['Ts']); sea = ~(np.asarray(M.land) > 0.5)
    doy = M.doy0 + HRS / 24.0; LA = np.asarray(M.LA); LO = np.asarray(M.LO); latr = np.radians(LA)
    ecc = 1.0 + 0.0334 * np.cos(2 * np.pi * (doy - 3.0) / 365.0); mu0 = F['sw_toa_dn'] / (1361.0 * ecc)
    W = np.cos(latr); gm = lambda x: float((np.asarray(x) * W).sum() / W.sum())
    allsky = dict(OLR=gm(F['olr']), OLR_clr=gm(F['olr_clr']), LW_CRE=gm(F['olr_clr'] - F['olr']),
                  ASR=gm(F['sw_toa_dn'] - F['sw_toa_up']), SW_CRE=gm(F['sw_toa_up_clr'] - F['sw_toa_up']), cover=gm(F['cover']),
                  lwp_gm2=gm(F['lwp']) * 1e3, iwp_gm2=gm(F['iwp']) * 1e3,
                  atm_rad_cooling=gm((F['sw_toa_dn'] - F['sw_toa_up'] - F['olr']) - (F['sw_net_sfc'] + F['lw_dn_sfc'] - F['lw_up_sfc'])))
    allsky['note'] = ('instantaneous snapshot at +%d h; ASR/SW_CRE depend on the time of day of the snapshot - compare LW terms and cover '
                      'directly, SW terms only as fractions' % HRS)
    out = dict(allsky=allsky)
    print(key, 'ALL SKY', json.dumps({kk: (round(v_, 2) if isinstance(v_, float) else v_) for kk, v_ in allsky.items() if kk != 'note'}), flush=True)
    if HAVE:
        rows = []; nl, nx, ny = Tn.shape
        o3m = np.asarray(radcloud.ozone_mmr(p, np)) if hasattr(radcloud, 'ozone_mmr') else None
        step_x = max(nx // 24, 1); step_y = max(ny // 64, 1)
        for i in range(0, nx, step_x):
            for j in range(0, ny, step_y):
                ph = p[:, i, j] / 100.0; o3v = (o3m[:, i, j] * 28.96 / 48.0) if o3m is not None else np.zeros(nl)
                alb = 0.07 if sea[i, j] else float(M.S['alb_land'])
                cz = float(mu0[i, j]); ins = float(1361.0 * ecc * cz)
                try:
                    a = rrtmg_col(ph, Tn[:, i, j], qn[:, i, j], o3v, float(Ts[i, j]), alb, cz, ins)
                    b = rrtmg_col(ph, Tn[:, i, j], qn[:, i, j], o3v, float(Ts[i, j]), alb, cz, ins, gases_full=True)
                except Exception as e:
                    print('rrtmg column failed', i, j, repr(e)[:160], flush=True); continue
                mine_h = np.asarray(F['lw_heating_clr'][:, i, j]) * 86400.0
                rows.append(dict(lat=float(LA[i, j]), lon=float(LO[i, j]), w=float(W[i, j]), sea=bool(sea[i, j]),
                                 OLRclr_m=float(F['olr_clr'][i, j]), OLRclr_r=a['OLRclr'], OLRclr_r_full=b['OLRclr'],
                                 LWdn_m=float(F['lw_dn_sfc_clr'][i, j]), LWdn_r=a['LWdn_sfc_clr'],
                                 ASRclr_m=float(F['sw_toa_dn'][i, j] - F['sw_toa_up_clr'][i, j]), ASRclr_r=a['ASRclr'],
                                 SWnet_sfc_clr_m=float(F['sw_net_sfc_clr'][i, j]), SWnet_sfc_clr_r=a['SWdn_sfc_clr'] - a['SWup_sfc_clr'],
                                 coszen=cz, h_m=mine_h.round(3).tolist(), h_r=np.asarray(a['TdotLW_clr']).round(3).tolist(),
                                 sig=np.asarray(M.sig).round(4).tolist()))
        def wm(f, m=lambda r: True):
            R_ = [r for r in rows if m(r)]; w_ = np.array([r['w'] for r in R_]); return float((np.array([f(r) for r in R_]) * w_).sum() / w_.sum()) if R_ else None
        trop = lambda r: abs(r['lat']) < 20; day = lambda r: r['coszen'] > 0.05
        summ = dict(n=len(rows),
                    OLRclr_model=wm(lambda r: r['OLRclr_m']), OLRclr_rrtmg=wm(lambda r: r['OLRclr_r']), OLRclr_rrtmg_allgases=wm(lambda r: r['OLRclr_r_full']),
                    LWdn_model=wm(lambda r: r['LWdn_m']), LWdn_rrtmg=wm(lambda r: r['LWdn_r']),
                    trop_OLRclr_model=wm(lambda r: r['OLRclr_m'], trop), trop_OLRclr_rrtmg=wm(lambda r: r['OLRclr_r'], trop),
                    trop_LWdn_model=wm(lambda r: r['LWdn_m'], trop), trop_LWdn_rrtmg=wm(lambda r: r['LWdn_r'], trop),
                    day_atm_SWabs_frac_model=wm(lambda r: (r['ASRclr_m'] - r['SWnet_sfc_clr_m']) / max(1361 * r['coszen'], 1), day),
                    day_atm_SWabs_frac_rrtmg=wm(lambda r: (r['ASRclr_r'] - r['SWnet_sfc_clr_r']) / max(1361 * r['coszen'], 1), day))
        H_m = np.array([r['h_m'] for r in rows if trop(r)]); H_r = np.array([r['h_r'] for r in rows if trop(r)])
        if len(H_m): summ['trop_LW_heating_clr_K_per_day'] = dict(sig=rows[0]['sig'], model=H_m.mean(0).round(2).tolist(), rrtmg=H_r.mean(0).round(2).tolist())
        out['clear_sky_vs_rrtmg'] = summ; out['columns'] = rows
        print(key, 'CLEAR SKY vs RRTMG', json.dumps({kk: (round(v_, 2) if isinstance(v_, float) else v_) for kk, v_ in summ.items() if not isinstance(v_, dict)}), flush=True)
    res[key] = out; json.dump(res, open(OUT, 'w'))
