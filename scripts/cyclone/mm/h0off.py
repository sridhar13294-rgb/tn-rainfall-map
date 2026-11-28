"""28 Nov (Tracks 5-why): hour-0 centre offset from best track - analysis vortex / relocated / relocated+DFI vs the job tracker. python h0off.py GRID N LIB"""
import sys, os, json, math, numpy as np
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE); sys.path.insert(0,os.path.join(HERE,'..','analysis'))
import mm2, ourens as O, landinit
LIB=sys.argv[3]; C=json.load(open(os.path.join(HERE,'..','..','..','data','cyclone','kaggle_cfg','lib84_cand1.json'))); var=C['variants'][0]
Z=np.load(LIB); F3=Z['f3']; F2=Z['f2']; LEV=Z['levs']; LAT=Z['lats']; LON=Z['lons']; TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
J={(r['name'],r['t0']):r for f in ('tn-r1-cand1-0/h0.json','tn-r1-cand1-1/h1.json') for r in json.load(open(os.path.join(HERE,'..','..','..','data','cyclone','kaggle',f)))}
def at(P0,t):
    for a,b in zip(P0,P0[1:]):
        if a[0]<=t<=b[0]:
            f=(t-a[0]).total_seconds()/max(1,(b[0]-a[0]).total_seconds()); return tuple(a[i]+f*(b[i]-a[i]) if a[i] is not None and b[i] is not None else (a[i] or b[i]) for i in (1,2,3))
hv=lambda a,b,c,d: 6371*2*math.asin(math.sqrt(math.sin(math.radians(c-a)/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(math.radians(d-b)/2)**2))
M=mm2.Model(sys.argv[1],32,C.get('dt_min',30.0),var.get('set')); N=int(sys.argv[2]); rows=[]
storms=[s for s in O.LIBL if s.get('basin','BB') in (C.get('basins') or ['BB','AS'])][:N*3]
for s in storms:
    g=O.gen_time(s); key=g.strftime('%Y-%m-%dT%H')
    if key not in TT or (s['name'],key) not in J: continue
    k=TT.index(key); st0=at(O.path_of(s),g)
    f3={v:F3[k,V3.index(v)] for v in V3}
    for bog in (False,True,'dfi'):
        state,carry=M.init(f3,LEV,LAT,LON,F2[k,V2.index('surface_pressure')],F2[k,V2.index('geopotential_at_surface')]/9.80616,F2[k,V2.index('sea_surface_temperature')],F2[k,V2.index('land_sea_mask')],storm=(dict(lat=st0[0],lon=st0[1],vmax_kt=st0[2] or 25.0) if bog else None),when=g,**landinit.land_kwargs(F2[k],V2))
        M.build(g)
        if bog=='dfi': state=M.dfi(state)
        out=M.run(state,carry,0,box=tuple(C.get('box',(30.0,120.0,-42.0,35.0))))
        trk=M.track(out,st0[0],st0[1])
        e=hv(st0[0],st0[1],trk[0][1],trk[0][2])
        if bog=='dfi': e_dfi=e
        elif bog: e_rel=e
        else: e_ana=e
    tj=J[(s['name'],key)]['trk'][0]; e_job=hv(st0[0],st0[1],tj[1],tj[2])
    rows.append((e_ana,e_rel,e_dfi,e_job)); print(s['name'],key,'analysis %.0f | relocated %.0f | relocated+DFI %.0f | T170 job h0 %.0f km'%(e_ana,e_rel,e_dfi,e_job),flush=True)
    if len(rows)>=N: break
a=np.array(rows); print('MEAN analysis %.0f relocated %.0f relocated+DFI %.0f T170 job %.0f km'%tuple(a.mean(0)))
