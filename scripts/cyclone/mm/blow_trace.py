"""28 Nov: trace the cand_cldpkg 2020-08-23 blow-up hourly (T170 on Kaggle). python blow_trace.py GRID LIB"""
import sys, json, datetime as dt, numpy as np, jax.numpy as jnp
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import mm2, landinit
B=json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','..','data','cyclone','kaggle_cfg','cand_cldpkg.json')))['variants'][0]['set']
Z=np.load(sys.argv[2]); V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]; TT=[str(t) for t in Z['times']]; KEY='2020-08-23T00'; K=TT.index(KEY)
F=Z['f3'][K].astype(np.float32); f2=Z['f2'][K]; f3={v:F[V3.index(v)] for v in V3}; t0=dt.datetime.strptime(KEY,'%Y-%m-%dT%H')
M=mm2.Model(sys.argv[1] if len(sys.argv)>1 else 'T42',32,20.0,B); st,cr=M.init(f3,Z['levs'],Z['lats'],Z['lons'],f2[V2.index('surface_pressure')],f2[V2.index('geopotential_at_surface')]/9.80616,f2[V2.index('sea_surface_temperature')],f2[V2.index('land_sea_mask')],when=t0,**landinit.land_kwargs(f2,V2))
M.build(t0); st=M.dfi(st); hor=M.coords.horizontal; LA,LO=np.meshgrid(np.asarray(M.lat),np.asarray(M.lon)); h0=0
for h in range(1,121,1):
    st,cr=mm2.integrate(M,st,cr,h-h0); h0=h
    T=np.asarray((hor.to_nodal(st.temperature_variation)+M.ref_t[:,None,None])/M.K); ps=np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]/M.PA)
    a=np.asarray(cr['cfa']); q=np.asarray(cr['cql']); bad=~np.isfinite(T).all(0)|~np.isfinite(ps)
    i=np.unravel_index(np.nanargmax(np.where(np.isfinite(T),T,-1).max(0)),T.shape[1:])
    print(h,'finite',bool(np.isfinite(T).all() and np.isfinite(ps).all()),'Tmax %.1f at lat %.1f lon %.1f'%(np.nanmax(T),LA[i],LO[i]),'Tmin %.1f'%np.nanmin(T),'cfa max %.2f cql max %.2f g/kg'%(np.nanmax(a),np.nanmax(q)*1000),'nbad',int(bad.sum()),flush=True)
    if bad.any(): j=np.argwhere(bad)[0]; print(' first bad at lat %.1f lon %.1f'%(LA[tuple(j)],LO[tuple(j)])); break
