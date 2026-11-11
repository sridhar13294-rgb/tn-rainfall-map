import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/mm'); sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/analysis')
import mm2, landinit, ifs_phys
from dinosaur import primitive_equations
Z = dict(np.load('/kaggle/working/libm_wx2020_fields.npz')); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
k = 36; S = {'rad':'radcloud','rad_every':2,'cmt_mf':1.0,'rd_si':1.0,'phys_ifs':1.0,'rad_dbg':1}
M = mm2.Model('T42', 32, 20.0, S); t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st); st, cr = mm2.integrate(M, st, cr, float(os.environ.get('HRS', 24))); hor = M.coords.horizontal
aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl = hor.cos_lat
u = aux.cos_lat_u[0]/cl/M.MPS; v = aux.cos_lat_u[1]/cl/M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA
crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence)*M.SEC)
C = ifs_phys.convection(*M._ifs_in); D = {k_: np.asarray(v_) for k_, v_ in C['dbg'].items()}
LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); land = np.asarray(M._ifs_in[10]); Tn = np.asarray(M._ifs_in[0]); qn = np.asarray(M._ifs_in[1]); pn = np.asarray(M._ifs_in[2]); mass = np.asarray(M._ifs_in[3])
H = np.asarray(M._ifs_in[6]); E = np.asarray(M._ifs_in[7])
tpw = (qn * mass).sum(0)
m = (np.abs(LA) <= 30) & ~land
f = lambda X, mm=m: float((X * W)[mm].sum() / W[mm].sum())
L = Tn.shape[0]
reach = D['kcb_s'] >= 0; Kpos = reach & (D['Kcb_s'] > 0); depth = D['pcb_s'] - D['ptop_s']
print(f'tropical ocean, after 24 h: H {f(H):.1f} W/m2, E {f(E)*86400:.2f} mm/day, w* median {np.median(D["wst"][m]):.2f} m/s, excess dT median {np.median(D["dTx"][m]):.2f} K')
print(f'  surface test parcel: layers alive median {np.median(D["nact_s"][m]):.0f}; reaches LCL {f(reach):.2f}; w>0 at LCL {f(Kpos):.2f}; depth<200 hPa {f(Kpos & (depth < 20000) & (depth > 0)):.2f}')
print(f'  deep {f(np.asarray(C["deep"])):.2f}  shallow {f(np.asarray(C["shallow"])):.2f}  none {f(~np.asarray(C["deep"]) & ~np.asarray(C["shallow"])):.2f}')
for a, b in ((0, 30), (30, 45), (45, 55), (55, 80)):
    mm = m & (tpw >= a) & (tpw < b)
    if mm.sum() > 5: print(f'  TPW {a}-{b} mm (share {W[mm].sum()/W[m].sum():.2f}): deep {f(np.asarray(C["deep"]), mm):.2f} shallow {f(np.asarray(C["shallow"]), mm):.2f} reaches LCL {f(reach, mm):.2f} w>0 at LCL {f(Kpos, mm):.2f}')
Mb = np.asarray(C['Mb']); dq = np.asarray(C['dq']); low = pn > 85000
vent = (dq * mass * low).sum(0) * 86400                               # mm/day change of sub-850 water by convection
for nm, mm in (('deep', m & np.asarray(C['deep'])), ('shallow', m & np.asarray(C['shallow']))):
    print(f'  {nm}: Mb p10/50/90 {np.percentile(Mb[mm], [10, 50, 90]).round(4)}; share with Mb=0 {(Mb[mm] == 0).mean():.2f}; sub-850 water change by convection {f(vent, mm):+.2f} mm/day vs E {f(E, mm)*86400:.2f}; PCAPE median {np.median(D["pcape"][mm]):.0f} Pa, PCAPE_bl {np.median(D["pcape_bl"][mm]):.0f}')
print(f'  all tropical ocean: convection removes {f(vent):+.2f} mm/day below 850 vs evaporation {f(E)*86400:.2f}; conv rain {f(np.asarray(C["P_sfc"]))*86400:.2f} mm/day')
