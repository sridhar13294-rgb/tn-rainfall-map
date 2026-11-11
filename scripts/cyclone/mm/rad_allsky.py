"""ALL-SKY radiation vs RRTMG with the SAME clouds (11 Nov). Model state at hour HRS (base2, or EXTRA), the model's own cloud fraction,
in-cloud liquid/ice water and effective radii (radcloud.clouds on the model's radiation inputs) are given to climlab-RRTMG (max-random
overlap, icld=2). Per sampled column: atmospheric radiative heating (all-sky and clear-sky), SW/LW cloud effects at TOA, at the surface and
on the ATMOSPHERE, model vs RRTMG. Question: are MEGAM's cloud optics right (atmospheric CRE ~+5..+10 observed; model -3..-4)?
python rad_allsky.py LIB OUT_JSON STARTS HRS   (needs climlab + climlab-rrtmg; rad_dbg hook in mm2)"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, radcloud as R
from dinosaur import primitive_equations
import climlab; from climlab.radiation import RRTMG
LIB, OUT, STARTS, HRS = sys.argv[1], sys.argv[2], sys.argv[3].split(','), float(sys.argv[4])
GRID = os.environ.get('GRID', 'T170')
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
setx = {'rad': 'radcloud', 'rad_every': 1, 'cmt_mf': 1.0, 'rd_si': 1.0, 'rad_dbg': 1}; setx.update(json.loads(os.environ.get('EXTRA', '{}')))
M = mm2.Model(GRID, 32, None, setx); CO2 = R.DEFAULTS.get('co2_ppm', 400.0)
def rr(pb, T, q, o3v, Ts, alb, cz, ins, cf, clwp, ciwp, rl, ri):
    # explicit interfaces (hPa, model sigma interfaces x ps): climlab.column_state(lev=points) forces the bottom bound to 1000 hPa,
    # which gives the lowest layer a NEGATIVE thickness where ps > 1000 hPa (RRTMG SW then segfaults with cloud there; the 5 Nov
    # clear-sky check rad_check.py used that form too)
    st = climlab.column_state(lev=climlab.domain.Axis(axis_type='lev', bounds=pb), water_depth=1.0); st['Tatm'][:] = T; st['Ts'][:] = Ts
    vmr = dict(CO2=CO2 * 1e-6, O3=o3v, CH4=1.9e-6, N2O=3.3e-7, O2=0.21, CFC11=0.0, CFC12=0.0, CFC22=0.0, CCL4=0.0)
    r = RRTMG(state=st, specific_humidity=q, absorber_vmr=vmr, albedo=alb, coszen=max(cz, 1e-4), insolation=ins, timestep=3600.0,
              cldfrac=cf, clwp=clwp, ciwp=ciwp, r_liq=rl, r_ice=ri, icld=2)
    r.compute_diagnostics(); D = r.diagnostics
    one = lambda x: float(np.ravel(np.asarray(x, float))[0]); sfc = lambda x: float(np.ravel(np.asarray(x, float))[-1])
    o = {}
    for tag, sx in (('', ''), ('_clr', '_clr')):
        asr = one(D['ASR' + sx.replace('_clr', 'clr')]); olr = one(D['OLR' + sx.replace('_clr', 'clr')])
        swn = sfc(D['SW_flux_down' + sx]) - sfc(D['SW_flux_up' + sx]); lwn = sfc(D['LW_flux_down' + sx]) - sfc(D['LW_flux_up' + sx])
        o['asr' + tag] = asr; o['olr' + tag] = olr; o['swsfc' + tag] = swn; o['lwsfc' + tag] = lwn; o['atm' + tag] = asr - olr - swn - lwn
        o['swatm' + tag] = asr - swn; o['lwatm' + tag] = -olr - lwn
    return o
res = {}
for key in STARTS:
    key = key if 'T' in key else key + 'T00'; k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]
    f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st)
    if HRS > 0: st, cr = mm2.integrate(M, st, cr, HRS)
    hor = M.coords.horizontal; aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
    T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl_ = hor.cos_lat
    u = aux.cos_lat_u[0] / cl_ / M.MPS; v = aux.cos_lat_u[1] / cl_ / M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
    crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
    M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence) * M.SEC)
    I = {k_: (np.asarray(v_, np.float64) if not isinstance(v_, dict) else v_) for k_, v_ in M._rad_in.items()}
    sea = I['sea'].astype(bool); cm = I['cm'].astype(bool)
    cl = R.clouds(I['T'], I['q'], I['p'], I['dp'], I['ps'], sea, cm, I['Psrc'].sum(0), I['Psrc'], I['cond'], np, I['prm'])
    o3 = R.ozone_layer_mass(I['p'], I['dp'], np)
    lw = R.longwave(I['T'], I['q'], I['p'], I['dp'], I['ps'], I['Ts'], cl, np, I['prm'], o3, clear_sky=True)
    sw = R.shortwave(I['T'], I['q'], I['p'], I['dp'], I['ps'], sea, I['mu0'], cl, np, I['prm'], o3, I['s0'])
    mass = I['dp'] / 9.80616
    has_o3mmr = hasattr(R, 'ozone_mmr'); o3m = np.asarray(R.ozone_mmr(I['p'], np)) if has_o3mmr else o3 / mass
    LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); nl, nx, ny = I['T'].shape; rows = []
    for i in range(0, nx, max(nx // 24, 1)):
        for j in range(0, ny, max(ny // 64, 1)):
            cz = float(I['mu0'][i, j]); ins = float(I['s0'] * cz); alb = 0.07 if sea[i, j] else float(M.S['alb_land'])
            cf = cl['c'][:, i, j]; clwp = np.where(cf > 0, cl['lwp'][:, i, j] * 1000.0, 0.0); ciwp = np.where(cf > 0, cl['iwp'][:, i, j] * 1000.0, 0.0)
            rl = cl['re_l'][:, i, j] * 1e6; ri = np.clip(cl['re_i'][:, i, j] * 1e6, 13.0, 130.0)
            if os.environ.get('DBG'): np.savez('/tmp/claude-0/lastcol.npz', p=I['p'][:, i, j], T=I['T'][:, i, j], q=I['q'][:, i, j], cf=cf, clwp=clwp, ciwp=ciwp, rl=rl, ri=ri, cz=cz, Ts=I['Ts'][i, j])
            try:
                pbj = np.concatenate([np.maximum(I['p'][:, i, j] - 0.5 * I['dp'][:, i, j], 0.0), [I['ps'][i, j]]]) / 100.0
                a = rr(pbj, I['T'][:, i, j], I['q'][:, i, j], o3m[:, i, j] * 28.96 / 48.0, float(I['Ts'][i, j]), alb, cz, ins, cf, clwp, ciwp, rl, ri)
            except Exception as e:
                print('rrtmg failed', i, j, repr(e)[:200], flush=True); continue
            asr_m = float(sw['toa_dn'][i, j] - sw['toa_up'][i, j]); asr_mc = float(sw['toa_dn'][i, j] - sw['toa_up_clr'][i, j])
            swn_m = float(sw['net_sfc'][i, j]); swn_mc = float(sw['net_sfc_clr'][i, j])
            lwn_m = float(lw['dn_sfc'][i, j] - lw['up_sfc'][i, j]); lwn_mc = float(lw['dn_sfc_clr'][i, j] - lw['up_sfc'][i, j])
            m_ = dict(asr=asr_m, asr_clr=asr_mc, olr=float(lw['olr'][i, j]), olr_clr=float(lw['olr_clr'][i, j]), swsfc=swn_m, swsfc_clr=swn_mc,
                      lwsfc=lwn_m, lwsfc_clr=lwn_mc)
            for tg in ('', '_clr'):
                m_['atm' + tg] = m_['asr' + tg] - m_['olr' + tg] - m_['swsfc' + tg] - m_['lwsfc' + tg]
                m_['swatm' + tg] = m_['asr' + tg] - m_['swsfc' + tg]; m_['lwatm' + tg] = -m_['olr' + tg] - m_['lwsfc' + tg]
            rows.append(dict(lat=float(LA[i, j]), w=float(W[i, j]), cz=cz, cover=float(cl['cover'][i, j]), m=m_, r=a))
    def wm(f, sel=lambda r: True):
        R_ = [r for r in rows if sel(r)]; w_ = np.array([r['w'] for r in R_]); return float((np.array([f(r) for r in R_]) * w_).sum() / w_.sum())
    S = {}
    for src in ('m', 'r'):
        for kk in ('atm', 'atm_clr', 'swatm', 'swatm_clr', 'lwatm', 'lwatm_clr', 'asr', 'asr_clr', 'olr', 'olr_clr', 'swsfc', 'swsfc_clr', 'lwsfc', 'lwsfc_clr'):
            S[f'{src}_{kk}'] = wm(lambda r: r[src][kk])
        S[f'{src}_atmCRE'] = S[f'{src}_atm'] - S[f'{src}_atm_clr']; S[f'{src}_swCRE_toa'] = S[f'{src}_asr'] - S[f'{src}_asr_clr']; S[f'{src}_lwCRE_toa'] = S[f'{src}_olr_clr'] - S[f'{src}_olr']
        S[f'{src}_swCRE_atm'] = S[f'{src}_swatm'] - S[f'{src}_swatm_clr']; S[f'{src}_lwCRE_atm'] = S[f'{src}_lwatm'] - S[f'{src}_lwatm_clr']
    S['n'] = len(rows); S['cover'] = wm(lambda r: r['cover'])
    res[key] = S; json.dump(res, open(OUT, 'w'))
    print(key, f'h{HRS:.0f} n={len(rows)} cover {S["cover"]:.2f}', flush=True)
    for kk in ('atm', 'atm_clr', 'atmCRE', 'swCRE_atm', 'lwCRE_atm', 'swCRE_toa', 'lwCRE_toa', 'swatm', 'swsfc', 'lwsfc', 'olr'):
        print(f'   {kk:10s} MEGAM {S["m_" + kk]:+8.1f}  RRTMG {S["r_" + kk]:+8.1f}  diff {S["m_" + kk] - S["r_" + kk]:+7.1f}', flush=True)
