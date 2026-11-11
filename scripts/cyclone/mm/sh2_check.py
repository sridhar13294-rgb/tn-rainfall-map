"""sh_ifs2 column check (11 Nov): after HRS h of ifs_sh (+ sh_ifs2) at the T170 time step on a T42 grid, tropical ocean: cloud-base
mass flux, energy/water closure of the shallow tendencies, sub-cloud-layer venting vs surface evaporation."""
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
k = int(os.environ.get('K', 36)); HRS = float(os.environ.get('HRS', 24)); GR = os.environ.get('GR', 'T42'); NL = os.environ.get('NL', '32'); NL = int(NL) if NL.isdigit() else NL
ifs={'rad':'radcloud','rad_every':2,"cmt_mf":1.0,"rd_si":1.0,"shallow":"mf","sh_trig":1.0,"sh_dmax":20000.0,"sh_eps":3.5e-3,"sh_det":1.0,"sh_clos":1.0,"sh_ifs2":1.0}
ifs.update(__import__('json').loads(os.environ.get('EXTRA', '{}')))
M = mm2.Model(GR, NL, float(os.environ.get('DT', 20)), ifs); t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st); st, cr = mm2.integrate(M, st, cr, HRS); hor = M.coords.horizontal
aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl = hor.cos_lat
u = aux.cos_lat_u[0]/cl/M.MPS; v = aux.cos_lat_u[1]/cl/M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA
crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
tend, diag = M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence)*M.SEC)
LA = np.asarray(M.LA); land = np.asarray(M.land); sig = np.asarray(M.sig); W = np.cos(np.radians(LA)); E = np.asarray(diag['E'])
psn = np.asarray(ps); mass = np.asarray(M.dsig)[:, None, None] * psn[None] / 9.80616; p = sig[:, None, None] * psn[None]
qs = np.asarray(diag['q_shal']); hs = np.asarray(diag['h_shal']); on_sh = np.asarray(diag['on_sh'])
Tn = np.asarray(T); rh = np.asarray(q) / np.asarray(mm2.qsat(jnp.asarray(Tn), jnp.asarray(p)))
print('max |column water change| by shallow (kg/m2/day):', np.abs((qs * mass).sum(0)).max() * 86400, ' max |column energy| (W/m2):', np.abs(((1004.6 * hs + 2.5e6 * qs) * mass).sum(0)).max())
Mb = np.asarray(getattr(M, '_sh2_diag', {}).get('Mb', np.zeros_like(E)))
for nm, m in (('tropical ocean', (np.abs(LA) <= 30) & ~land), ('trade belts 10-30 ocean', (np.abs(LA) >= 10) & (np.abs(LA) <= 30) & ~land)):
    f = lambda X, mm=m: float((X * W)[mm].sum() / W[mm].sum())
    a = m & (on_sh > 0)
    low = p > 85000
    print(f'== {nm}: shallow applied {f(on_sh):.2f}; E {f(E)*86400:.2f} mm/day; sub-850 water change by shallow {f((qs*mass*low).sum(0))*86400:+.2f} mm/day; RH>850 {f((rh*mass*low).sum(0)/(mass*low).sum(0)):.3f}')
    if a.any(): print(f'   Mb p10/50/90 where applied {np.percentile(Mb[a], [10, 50, 90]).round(4)}  (observed shallow Cu ~0.02-0.03)')
