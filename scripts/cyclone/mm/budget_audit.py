"""Conservation audit of MEGAM column physics (hidden-issue search, 4 Nov). For a few states (start + 6 h, 1 d, 3 d) every
column's physics is checked against its boundary fluxes; a residual that is not ~0 points to a coding / conservation defect.
Checks (column integrals, W m-2; global, tropics, and the worst columns):
  BL      cp*int(h_bl) - H            and   L*int(q_bl) - L*E           (turbulence only redistributes; the surface supplies)
  deep    cp*int(h_deep) + L*int(q_deep)                                (moist enthalpy conserved; rain leaves as water)
  shallow cp*int(h_shal) + L*int(q_shal)                                (conserved, no rain)
  lsc     cp*int(h_lsc) + L*int(q_lsc)                                  (condensation: conserved)
  evap    cp*int(h_evap) + L*int(q_evap)                                (re-evaporation: conserved)
  water   int(physics dq) - (E - rain)                                  (includes the q >= 0 clip and anything not in the processes)
  energy  int(cp dT_phys - cp rad + L dq_phys) - (H + L E)              (all non-radiative physics vs the surface fluxes)
  rad     cp*int(rad) - [(SW_toa_dn - SW_toa_up - OLR) - (SW_net_sfc + LW_dn_sfc - LW_up_sfc)]   (radiation vs its own fluxes, below rad_top)
  rain    rain - [-int(q_deep + q_shal + q_lsc + q_evap)]               (surface rain equals the water the processes removed)
python budget_audit.py LIB_NPZ OUT_JSON SETTINGS_JSON"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
from dinosaur import spherical_harmonic
G, CP, LV = 9.80616, 1004.6, 2.5e6
LIB, OUT, VS = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
VS = dict(VS); NL = VS.pop('layers', 32); GR = VS.pop('grid', 'T170')
M = mm2.Model(GR, NL, None, dict({'rad': 'radcloud', 'rad_every': 2}, **VS))
res = {'settings': VS, 'layers': NL}
for key in (TT[0], TT[len(TT) // 2]):
    k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / G,
                    Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
    M.build(t0); st = M.dfi(st); hor = M.coords.horizontal; h_done = 0
    LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); trop = np.abs(LA) < 20; dsig = np.asarray(M.dsig)[:, None, None]; sig = np.asarray(M.sig)[:, None, None]
    for hrs in (6, 24):
        st, cr = mm2.integrate(M, st, cr, hrs - h_done); h_done = hrs
        T = np.asarray((hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K); q = np.asarray(st.tracers['specific_humidity'])
        ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA); u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
        tn, d = M.column(jnp.asarray(T), jnp.asarray(q), u / M.MPS, v / M.MPS, jnp.asarray(ps), dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)),
                         rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
        mass = dsig * ps[None] / G; I = lambda x: (np.asarray(x) * mass).sum(0)
        g = {k_: np.asarray(d[k_]) for k_ in ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap', 'q_bl', 'q_deep', 'q_shal', 'q_lsc', 'q_evap', 'H', 'E', 'rain') if k_ in d}
        R = d['rad']; rad = np.asarray(d['rad_app']); radc = np.asarray(R['heating']); above = sig[:, 0, 0] <= float(M.S.get('rad_top', 0.12))
        res.setdefault('rad_keys', sorted(R.keys()))
        r = {}
        r['BL heat (cp int h_bl - H)'] = CP * I(g['h_bl']) - g['H']
        r['BL water (L int q_bl - L E)'] = LV * (I(g['q_bl']) - g['E'])
        for p_ in ('deep', 'shal', 'lsc', 'evap'):
            r[f'{p_} moist enthalpy'] = CP * I(g['h_' + p_]) + LV * I(g['q_' + p_])
        dTp = np.asarray(tn['T']); dqp = np.asarray(tn['q'])
        r['water (int dq - (E - rain))'] = LV * (I(dqp) - (g['E'] - g['rain']))
        r['energy non-rad (int cp(dT-rad)+L dq - (H+LE))'] = CP * I(dTp - rad) + LV * I(dqp) - (g['H'] + LV * g['E'])
        rad_below = np.where(above[:, None, None], 0.0, rad)
        if all(k_ in R for k_ in ('sw_toa_dn', 'sw_toa_up', 'olr', 'sw_net_sfc', 'lw_dn_sfc', 'lw_up_sfc')):
            col = (np.asarray(R['sw_toa_dn']) - np.asarray(R['sw_toa_up']) - np.asarray(R['olr'])) - (np.asarray(R['sw_net_sfc']) + np.asarray(R['lw_dn_sfc']) - np.asarray(R['lw_up_sfc']))
            r['radiation computed (cp int rad_computed - flux divergence)'] = CP * I(radc) - col
        r['stratosphere: applied minus computed radiation above rad_top'] = CP * I(np.where(above[:, None, None], rad - radc, 0.0))
        r['sum of process heating vs total (cp int(dT - rad_app - sum h_*))'] = CP * I(dTp - rad - sum(g['h_' + p_] for p_ in ('bl', 'deep', 'shal', 'lsc', 'evap')))
        r['rain (rain + int(q_deep+q_shal+q_lsc+q_evap))'] = LV * (g['rain'] + I(g['q_deep'] + g['q_shal'] + g['q_lsc'] + g['q_evap']))
        out = {}
        for n_, x in r.items():
            x = np.asarray(x); gm = float((x * W).sum() / W.sum()); tm = float((x * W * trop).sum() / (W * trop).sum())
            out[n_] = dict(global_mean=round(gm, 3), tropics_mean=round(tm, 3), p99_abs=round(float(np.percentile(np.abs(x), 99)), 2), max_abs=round(float(np.abs(x).max()), 2))
        out['_reference'] = dict(H=round(float((g['H'] * W).sum() / W.sum()), 1), LE=round(float((LV * g['E'] * W).sum() / W.sum()), 1), Lrain=round(float((LV * g['rain'] * W).sum() / W.sum()), 1))
        res[f'{key} +{hrs}h'] = out
        print(key, f'+{hrs}h', json.dumps({k_: (v_['global_mean'], v_['p99_abs'], v_['max_abs']) if 'global_mean' in v_ else v_ for k_, v_ in out.items()}), flush=True)
        json.dump(res, open(OUT, 'w'), indent=1)
