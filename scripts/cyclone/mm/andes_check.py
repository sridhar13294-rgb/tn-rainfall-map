"""P2 Andes hot spot (5 Nov): every 3 h over the central Andes (18-34 S, 65-75 W): max lowest-level wind, max |h_bl|, max |du_bl|,
H at the windiest point; global max lowest wind. python andes_check.py LIB GRID LAYERS SETTINGS HOURS [START] [OUT_JSON]"""
import sys, json, datetime as dt, numpy as np, jax.numpy as jnp
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import mm2, landinit
from dinosaur import spherical_harmonic
LIB, GR, NL, SET, HRS = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4]), int(sys.argv[5]); KEY = sys.argv[6] if len(sys.argv) > 6 else '2020-06-09T00'; OUT = sys.argv[7] if len(sys.argv) > 7 else None; REC = []
Z = dict(np.load(LIB)); V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]; TT=[str(t) for t in Z['times']]; K=TT.index(KEY); t0=dt.datetime.strptime(KEY,'%Y-%m-%dT%H'); f2=Z['f2'][K]
M = mm2.Model(GR, NL if NL=='tp75' else int(NL), None, dict({'rad':'radcloud','rad_every':2}, **SET))
f3={v:Z['f3'][K,V3.index(v)] for v in V3}
st,cr=M.init(f3,Z['levs'],Z['lats'],Z['lons'],f2[V2.index('surface_pressure')],f2[V2.index('geopotential_at_surface')]/9.80616,f2[V2.index('sea_surface_temperature')],f2[V2.index('land_sea_mask')],when=t0,**landinit.land_kwargs(f2,V2))
M.build(t0); st=M.dfi(st); hor=M.coords.horizontal
LA=np.asarray(M.LA); LO=np.asarray(M.LO)%360; box=(LA>-34)&(LA<-18)&(LO>285)&(LO<295)
print('dt_s', M.dt_s, 'lowest sigma', np.asarray(M.sig)[-3:].round(4).tolist(), flush=True)
h0=0
for hh in range(0, HRS+1, 3):
    if hh: st,cr=mm2.integrate(M,st,cr,hh-h0); h0=hh
    T=(hor.to_nodal(st.temperature_variation)+M.ref_t[:,None,None])/M.K; q=st.tracers['specific_humidity']
    ps=jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA; u,v=spherical_harmonic.vor_div_to_uv_nodal(hor,st.vorticity,st.divergence)
    U=np.asarray(u/M.MPS); V_=np.asarray(v/M.MPS); W=np.hypot(U,V_)
    tn,d=M.column(T,q,u/M.MPS,v/M.MPS,ps,dict(cr,doy0=jnp.float32(M.doy0),utc0=jnp.float32(M.utc0)),rad_fresh=True,div=hor.to_nodal(st.divergence)*M.SEC)
    hbl=np.abs(np.asarray(d['h_bl']))*86400; ub=np.asarray(d['u_bl'])*86400
    w1=W[-1][box]; i=np.argmax(w1)
    REC.append(dict(h=hh, wmax=float(w1.max()), w2=float(W[-2][box].max()), hbl=float(hbl[:, box].max()), dubl=float(np.abs(ub[:, box]).max()), H=float(np.asarray(d['H'])[box][i]), wglob=float(W[-1].max())))
    if OUT: json.dump(REC, open(OUT, 'w'))
    print(f"+{hh:3d}h Andes: max lowest-level wind {w1.max():6.1f} m/s (2nd-lowest {W[-2][box].max():5.1f}, 5th {W[-5][box].max():5.1f}) | max |h_bl| {hbl[:, box].max():7.1f} K/day | max |du_bl| {np.abs(ub[:, box]).max():7.1f} m/s/day | H at windiest {float(np.asarray(d['H'])[box][i]):7.1f} | global max lowest wind {W[-1].max():6.1f}", flush=True)
