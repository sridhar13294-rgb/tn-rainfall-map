import sys; sys.path.insert(0,'/home/claude/tn-rainfall-map/scripts/cyclone/mm')
import cloud_derivation as C, numpy as np
def ens(r, dT, lsc, prm=None, rbl=0.85, clear=False, qshift=None):
    H=[];LW=[];LWC=[];CL=[]
    for kt in C.DECK:
        T=C.T0+dT; q=np.minimum(C.q0,0.95*C.qs_(T))
        for k in range(kt+1, C.K(0.95)+1): q[k]=max(q[k], rbl*C.qs_(T)[k])
        q[kt]=r*C.qs_(T)[kt]
        if qshift is not None: q=q+qshift(kt,T,q)
        cond=np.zeros_like(T); cond[kt]=lsc*4*C.CP/C.LV/86400
        R=C.rad(T,q,cond,prm,clear=clear); H.append(R['heat']); LW.append(R['lw']); CL.append(R['cloud'])
        if clear: LWC.append(R['lw_clr'])
    o=dict(heat=np.mean(H,0),lw=np.mean(LW,0),cloud=np.mean(CL,0))
    if clear: o['lw_clr']=np.mean(LWC,0)
    return o
if __name__=='__main__':
    for r in (0.8,0.85,0.9,0.93,0.96,0.99):
        a=ens(r,-2.4,1.32); b=ens(r,-2.4,1.32,dict(pdf=1.0))
        print(r,'cur',np.round(a['heat'][C.DECK],2),round(a['heat'][C.DECK].mean(),2),'| pdf',np.round(b['heat'][C.DECK],2),round(b['heat'][C.DECK].mean(),2))
