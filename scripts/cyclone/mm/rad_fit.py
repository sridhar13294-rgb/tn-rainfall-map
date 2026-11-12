"""Short-wave water-vapour absorption: MEGAM vs RRTMG on the SAME clear-sky columns, and a fit of the 5 near-IR water-vapour
absorption coefficients (SW_KH2O, Lacis & Hansen 1974 form, band weights unchanged) to RRTMG (12 Nov; A + P1: the model atmosphere
absorbs 5-9 W m-2 less sunlight than RRTMG, rad_allsky.py). Reference-model calibration, done the way the LW terms were built
(fitted to a line-by-line-type reference): TRAINING columns from some starts, VALIDATION on other starts never used in the fit.
python rad_fit.py LIB TRAIN_STARTS VAL_STARTS OUT_JSON   (ERA5 start states, T42 grid, day-side columns only)"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit, radcloud as R
from dinosaur import primitive_equations
import jax.numpy as jnp
import climlab; from climlab.radiation import RRTMG
from scipy.optimize import minimize
LIB = sys.argv[1]; TR_S = sys.argv[2].split(','); VA_S = sys.argv[3].split(','); OUT = sys.argv[4]
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
M = mm2.Model('T42', 32, 20.0, {'rad': 'radcloud', 'rad_every': 1, 'cmt_mf': 1.0, 'rd_si': 1.0, 'rad_dbg': 1})
def columns(keys, stride=3):
    cols = []
    for key in keys:
        key = key if 'T' in key else key + 'T00'; k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]
        f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); hor = M.coords.horizontal
        aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
        T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl_ = hor.cos_lat
        u = aux.cos_lat_u[0] / cl_ / M.MPS; v = aux.cos_lat_u[1] / cl_ / M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
        crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
        M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence) * M.SEC)
        I = {k_: (np.asarray(v_, np.float64) if not isinstance(v_, dict) else v_) for k_, v_ in M._rad_in.items()}
        nx, ny = I['T'].shape[1:]; LA = np.asarray(M.LA)
        for i in range(0, nx, stride):
            for j in range(0, ny, stride):
                if I['mu0'][i, j] < 0.1: continue
                cols.append(dict(T=I['T'][:, i, j], q=I['q'][:, i, j], p=I['p'][:, i, j], dp=I['dp'][:, i, j], ps=float(I['ps'][i, j]),
                                 sea=bool(I['sea'][i, j]), mu0=float(I['mu0'][i, j]), s0=float(I['s0']), Ts=float(I['Ts'][i, j]), w=float(np.cos(np.radians(LA[i, j])))))
    return cols
def rrtmg_sw(c):
    pb = np.concatenate([np.maximum(c['p'] - 0.5 * c['dp'], 0.0), [c['ps']]]) / 100.0
    st = climlab.column_state(lev=climlab.domain.Axis(axis_type='lev', bounds=pb), water_depth=1.0); st['Tatm'][:] = c['T']; st['Ts'][:] = c['Ts']
    o3 = np.asarray(R.ozone_mmr(c['p'], np)) * 28.96 / 48.0
    vmr = dict(CO2=420e-6, O3=o3, CH4=1.9e-6, N2O=3.3e-7, O2=0.21, CFC11=0.0, CFC12=0.0, CFC22=0.0, CCL4=0.0)
    alb = 0.037 / (1.1 * c['mu0'] ** 1.4 + 0.15) if c['sea'] else float(M.S['alb_land'])
    r = RRTMG(state=st, specific_humidity=c['q'], absorber_vmr=vmr, albedo=alb, coszen=c['mu0'], insolation=c['s0'] * c['mu0'], timestep=3600.0)
    r.compute_diagnostics(); D = r.diagnostics
    return np.ravel(np.asarray(D['TdotSW_clr'], float)), float(np.ravel(D['ASRclr'])[0]) - float(np.ravel(D['SW_flux_down_clr'])[-1] - np.ravel(D['SW_flux_up_clr'])[-1])
def megam_sw(cs, kh):
    R.SW_KH2O = np.array([0.0, 0.0] + list(kh)) * 0.1
    L = len(cs[0]['T']); n = len(cs); A = lambda k_: np.stack([c[k_] for c in cs], 1)[:, :, None]
    T, q, p, dp = A('T'), A('q'), A('p'), A('dp'); ps = np.array([c['ps'] for c in cs])[:, None]
    sea = np.array([c['sea'] for c in cs])[:, None]; mu0 = np.array([c['mu0'] for c in cs])[:, None]
    z = np.zeros_like(T); cl = dict(c=z, lwp=z, iwp=z, re_l=np.full_like(T, 10e-6), re_i=np.full_like(T, 30e-6), cover=np.zeros_like(ps))
    sw = R.shortwave(T, q, p, dp, ps, sea, mu0, cl, np, dict(alb_land=float(M.S['alb_land'])), None, cs[0]['s0'])
    return np.asarray(sw['heating_clr'])[:, :, 0] * 86400.0, np.asarray(sw['toa_dn'] - sw['toa_up_clr'] - sw['net_sfc_clr'])[:, 0]
K0 = [0.0006, 0.035, 0.377, 1.95, 30.0]
tr = columns(TR_S); va = columns(VA_S); print('columns train', len(tr), 'validation', len(va), flush=True)
for c in tr + va: c['rr_h'], c['rr_abs'] = rrtmg_sw(c)
def stats(cs, kh):
    h, a = megam_sw(cs, kh); w = np.array([c['w'] for c in cs]); rr_h = np.stack([c['rr_h'] for c in cs], 1); rr_a = np.array([c['rr_abs'] for c in cs])
    p = np.stack([c['p'] for c in cs], 1); dpm = np.stack([c['dp'] for c in cs], 1); low = (p >= 85000)
    lowm = lambda H: float(((H * dpm * low).sum(0) / np.maximum((dpm * low).sum(0), 1) * w).sum() / w.sum())
    return dict(abs_megam=float((a * w).sum() / w.sum()), abs_rrtmg=float((rr_a * w).sum() / w.sum()),
                low_megam=lowm(h), low_rrtmg=lowm(rr_h), rms_profile=float(np.sqrt((((h - rr_h) ** 2 * dpm).sum(0) / dpm.sum(0) * w).sum() / w.sum())))
res = {'K0': K0, 'train0': stats(tr, K0), 'val0': stats(va, K0)}; print('before', json.dumps(res), flush=True)
def cost(lk):
    kh = np.exp(lk); h, a = megam_sw(tr, kh); rr_h = np.stack([c['rr_h'] for c in tr], 1); dpm = np.stack([c['dp'] for c in tr], 1); w = np.array([c['w'] for c in tr])
    return float(((((h - rr_h) ** 2 * dpm).sum(0) / dpm.sum(0)) * w).sum() / w.sum())
o = minimize(cost, np.log(K0), method='Nelder-Mead', options=dict(maxiter=400, xatol=1e-3, fatol=1e-6))
K1 = list(np.exp(o.x)); res.update(K1=K1, train1=stats(tr, K1), val1=stats(va, K1), opt=dict(fun=float(o.fun), nit=int(o.nit)))
print('after', json.dumps(res), flush=True); json.dump(res, open(OUT, 'w'))
