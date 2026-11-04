"""Step 1(a), 4 Nov: is MEGAM's ocean evaporation right? The model's own surface fluxes (latent L*E, sensible H) vs the
COARE 3.5 bulk algorithm (Edson et al. 2013; Fairall et al. 2003 - the reference ocean flux algorithm) computed from the
SAME lowest-level wind, temperature, humidity, height, pressure and SST of the model state. A formula difference shows up
directly as model/COARE ratio, and by wind-speed bin. python flux_check.py LIB_NPZ OUT_JSON 'START1,START2' HOURS [GRID]"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
from dinosaur import spherical_harmonic
from pycoare import coare_35
G, RD, LV = 9.80616, 287.04, 2.5e6
LIB, OUT, STARTS, HRS = sys.argv[1], sys.argv[2], sys.argv[3].split(','), int(sys.argv[4]); GR = sys.argv[5] if len(sys.argv) > 5 else 'T170'
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
M = mm2.Model(GR, 32, None, {'rad': 'radcloud', 'rad_every': 2}); MZ = mm2.Model(GR, 32, None, {'rad': 'radcloud', 'rad_every': 2, 'ck_z': 1.0}); res = {'grid': GR, 'ck': M.S.get('ck'), 'gust': M.S.get('gust'), 'ck_z': M.S.get('ck_z')}
for key in STARTS:
    key = key if 'T' in key else key + 'T00'; k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / G,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); hor = M.coords.horizontal; rows = []
    for h in range(0, HRS + 1, 12):
        if h: st, cr = mm2.integrate(M, st, cr, 12)
        if h < HRS: continue
        T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
        ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
        tn, d = M.column(T, q, u / M.MPS, v / M.MPS, ps, dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True,
                         div=hor.to_nodal(st.divergence) * M.SEC)
        MZ.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / G,
                f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2)); MZ.build(t0)
        _, dz = MZ.column(T, q, u / M.MPS, v / M.MPS, ps, dict(MZ.with_params(cr, {'ck_z': 1.0}), doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True,
                          div=hor.to_nodal(st.divergence) * M.SEC)
        T1 = np.asarray(T)[-1]; q1 = np.asarray(q)[-1]; psn = np.asarray(ps); p1 = np.asarray(M.sig)[-1] * psn
        U1 = np.hypot(np.asarray(u / M.MPS)[-1], np.asarray(v / M.MPS)[-1]); z1 = RD * T1 * (1 + 0.61 * q1) / G * np.log(psn / p1)
        e1 = q1 * p1 / (0.622 + 0.378 * q1); es = 611.2 * np.exp(17.67 * (T1 - 273.15) / (T1 - 29.65)); rh = np.clip(100 * e1 / es, 1, 100)
        sea = ~(np.asarray(M.land) > 0.5); Ts = np.asarray(d['Ts']); LA = np.asarray(M.LA); W = np.cos(np.radians(LA))
        m = sea & (np.abs(LA) < 60) & (U1 > 0.5)
        lw = np.asarray(d['lw_dn']) if 'lw_dn' in d else np.full_like(Ts, 370.0); sw = np.asarray(d['sw_sfc']) if 'sw_sfc' in d else np.full_like(Ts, 150.0)
        c0 = coare_35(U1[m], t=T1[m] - 273.15, rh=rh[m], zu=z1[m], zt=z1[m], zq=z1[m], ts=Ts[m] - 273.15, p=p1[m] / 100, lat=LA[m],
                      rs=sw[m], rl=lw[m], jcool=0)
        LEc = np.asarray(c0.fluxes.hlb, float); Hc = np.asarray(c0.fluxes.hsb, float)
        LEm = LV * np.asarray(d['E'])[m]; Hm = np.asarray(d['H'])[m]; w = W[m]; ok = np.isfinite(LEc) & np.isfinite(Hc)
        wm = lambda x, s=ok: float((x[s] * w[s]).sum() / w[s].sum())
        bins = {}
        for lo_, hi_ in ((0.5, 3), (3, 6), (6, 9), (9, 12), (12, 20), (20, 60)):
            s = ok & (U1[m] >= lo_) & (U1[m] < hi_)
            if s.sum() > 20: bins[f'{lo_}-{hi_}'] = dict(n=int(s.sum()), LE_model=round(wm(LEm, s), 1), LE_coare=round(wm(LEc, s), 1), H_model=round(wm(Hm, s), 1), H_coare=round(wm(Hc, s), 1))
        trop = ok & (np.abs(LA[m]) < 20)
        es_s = 611.2 * np.exp(17.67 * (Ts - 273.15) / (Ts - 29.65)); qss = 0.622 * es_s / (psn - 0.378 * es_s)
        sal = np.clip((0.98 * qss - q1) / np.maximum(qss - q1, 1e-6), 0, 1.5)[m]                     # COARE salinity factor 0.98 on q_sat(SST)
        LEz = LV * np.asarray(dz['E'])[m]
        r = dict(h=h, n=int(ok.sum()), LE_model=round(wm(LEm), 1), LE_coare=round(wm(LEc), 1), H_model=round(wm(Hm), 1), H_coare=round(wm(Hc), 1),
                 trop_LE_model=round(wm(LEm, trop), 1), trop_LE_coare=round(wm(LEc, trop), 1), z1_mean=round(float(np.mean(z1[m])), 1),
                 U1_mean=round(wm(U1[m]), 2), bins=bins, LE_model_ckz1=round(wm(LEz), 1), LE_model_ckz1_sal=round(wm(LEz * sal), 1), LE_model_sal=round(wm(LEm * sal), 1))
        rows.append(r); print(key, h, json.dumps({kk: vv for kk, vv in r.items() if kk != 'bins'}), flush=True)
    res[key] = rows; json.dump(res, open(OUT, 'w'), indent=1)
