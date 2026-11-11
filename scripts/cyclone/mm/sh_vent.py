# NOTE: needs a temporary debug hook in mm2.conv_mf (self._dbg_sh = dict(act, Mb, Mb_raw, cap, ninc, dtop, cloud, cloud_t, ...)), not committed.
# Why does ifs_sh vent so little sub-cloud moisture? Snapshot after HRS h (ifs_sh), tropical ocean columns: trigger, plume depth, Mb, vent vs E
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/mm'); sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/analysis')
import mm2, landinit
from dinosaur import primitive_equations
Z = dict(np.load('/kaggle/working/libm_wx2020_fields.npz')); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
k = int(os.environ.get('K', 36)); HRS = float(os.environ.get('HRS', 24)); GR = os.environ.get('GR', 'T42')
ifs={'rad':'radcloud','rad_every':2,"cmt_mf":1.0,"rd_si":1.0,"shallow":"mf","sh_trig":1.0,"sh_dmax":20000.0,"sh_eps":3.5e-3,"sh_det":1.0,"sh_clos":1.0}
M = mm2.Model(GR, int(os.environ.get('NL', 32)) if os.environ.get('NL', '32').isdigit() else os.environ['NL'], float(os.environ['DT']) if 'DT' in os.environ else None, ifs); t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st); st, cr = mm2.integrate(M, st, cr, HRS); hor = M.coords.horizontal
aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl = hor.cos_lat
u = aux.cos_lat_u[0]/cl/M.MPS; v = aux.cos_lat_u[1]/cl/M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA
crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
tend, diag = M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence)*M.SEC)
D = {k_: np.asarray(v_) for k_, v_ in M._dbg_sh.items()}
LA = np.asarray(M.LA); land = np.asarray(M.land); sig = np.asarray(M.sig); W = np.cos(np.radians(LA)); E = np.asarray(diag['E']); H = np.asarray(diag['H'])
psn = np.asarray(ps); mass = np.asarray(M.dsig)[:, None, None] * psn[None] / 9.80616; p = sig[:, None, None] * psn[None]
qs = np.asarray(diag['q_shal']); qd = np.asarray(diag['q_deep']); qb = np.asarray(diag['q_bl'])
on_dp = np.asarray(diag.get('on_dp', np.zeros_like(E))); on_sh = np.asarray(diag.get('on_sh', np.zeros_like(E)))
low = p > 85000
vent = lambda X: (X * mass * low).sum(0)       # kg/m2/s change of sub-850 water
for nm, m in (('tropical ocean', (np.abs(LA) <= 30) & ~land), ('trade belts 10-30 ocean', (np.abs(LA) >= 10) & (np.abs(LA) <= 30) & ~land)):
    f = lambda X, mm=m: float((X * W)[mm].sum() / W[mm].sum())
    print(f'== {nm}: columns {m.sum()}  E {f(E)*86400:.2f} mm/day, H {f(H):.1f} W/m2')
    print(f'  test-parcel cloud {f(D["cloud_t"]):.2f}  test depth<=dmax&cloud (shallow trigger) {f(D["act"]):.2f}  deep active {f(on_dp):.2f}  shallow applied (not deep) {f(on_sh):.2f}')
    print(f'  sub-850 water change by: BL+sfc {f(vent(qb))*86400:+.2f} shallow {f(vent(qs))*86400:+.2f} deep {f(vent(qd))*86400:+.2f} mm/day')
    a = m & (D['act'] > 0) & (on_dp == 0)
    if a.any():
        g = lambda X: np.percentile(X[a], [10, 50, 90]).round(4)
        print(f'  dt {M.dt_s:.0f}s'); print(f'  where shallow applies (n={a.sum()}): Mb_raw (closure) {g(D["Mb_raw"])} Mb {g(D["Mb"])} cap {g(D["cap"])} plume layers above src {g(D["ninc"])} depth Pa {g(D["dtop"])} real-plume cloud {D["cloud"][a].mean():.2f}')
        r = (-vent(qs))[a] / np.maximum(E[a], 1e-7)
        print(f'  shallow vent / E: p10/50/90 {np.percentile(r, [10, 50, 90]).round(2)};  Mb x 1 g/kg = {np.median(D["Mb"][a])*1e-3*86400:.2f} mm/day per g/kg excess')
