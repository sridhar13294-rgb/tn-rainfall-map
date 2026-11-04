import sys, datetime as dt, numpy as np, jax.numpy as jnp
CODE, OUT = sys.argv[1], sys.argv[2]; sys.path.insert(0, CODE); import mm2, landinit
from dinosaur import spherical_harmonic
Z = dict(np.load(sys.argv[3])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
k=TT.index('2020-10-27T00'); t0=dt.datetime(2020,10,27)
M = mm2.Model('T42', 32, None, {'rad':'radcloud','rad_every':2})
f3={v:Z['f3'][k,V3.index(v)] for v in V3}
st,cr=M.init(f3,Z['levs'],Z['lats'],Z['lons'],Z['f2'][k,V2.index('surface_pressure')],Z['f2'][k,V2.index('geopotential_at_surface')]/9.80616,Z['f2'][k,V2.index('sea_surface_temperature')],Z['f2'][k,V2.index('land_sea_mask')],when=t0,**landinit.land_kwargs(Z['f2'][k],V2))
M.build(t0); hor=M.coords.horizontal
T=(hor.to_nodal(st.temperature_variation)+M.ref_t[:,None,None])/M.K; q=st.tracers['specific_humidity']
ps=jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA; u,v=spherical_harmonic.vor_div_to_uv_nodal(hor,st.vorticity,st.divergence)
tn,d=M.column(T,q,u/M.MPS,v/M.MPS,ps,dict(cr,doy0=jnp.float32(M.doy0),utc0=jnp.float32(M.utc0)),rad_fresh=True,div=hor.to_nodal(st.divergence)*M.SEC)
np.savez(OUT,**{k_:np.asarray(x) for k_,x in tn.items()},rain=np.asarray(d['rain']),H=np.asarray(d['H']),E=np.asarray(d['E']))
