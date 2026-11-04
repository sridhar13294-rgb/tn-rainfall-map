import sys, os, json, datetime as dt, numpy as np, jax, jax.numpy as jnp
CODE, OUT, GR, HRS = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path.insert(0, CODE); import mm2, landinit
Z = dict(np.load(sys.argv[5])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
key = '2020-10-27T00' if '2020-10-27T00' in TT else TT[0]; k=TT.index(key); t0=dt.datetime.strptime(key,'%Y-%m-%dT%H')
M = mm2.Model(GR, 32, None, {'rad':'radcloud','rad_every':2})
f3={v:Z['f3'][k,V3.index(v)] for v in V3}
st,cr=M.init(f3,Z['levs'],Z['lats'],Z['lons'],Z['f2'][k,V2.index('surface_pressure')],Z['f2'][k,V2.index('geopotential_at_surface')]/9.80616,Z['f2'][k,V2.index('sea_surface_temperature')],Z['f2'][k,V2.index('land_sea_mask')],when=t0,**landinit.land_kwargs(Z['f2'][k],V2))
M.build(t0); st=M.dfi(st)
st,cr=mm2.integrate(M,st,cr,HRS)
hor=M.coords.horizontal
T=np.asarray(hor.to_nodal(st.temperature_variation)); q=np.asarray(st.tracers['specific_humidity'])
np.savez(OUT, T=T, q=q, rain=np.asarray(cr['rain']), key=key)
print(CODE[-30:], key, 'rain mean', float(np.asarray(cr['rain']).mean()))
