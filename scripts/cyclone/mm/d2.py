import sys; sys.path.insert(0,'/home/claude/tn-rainfall-map/scripts/cyclone/mm'); sys.path.insert(0,'/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad')
import cloud_derivation as C, numpy as np
from deck_ens import ens
r=0.99; dT=-2.4
a=ens(r,dT,1.32,clear=True); b=ens(r,dT,1.32,dict(pdf=1.0),clear=True)
D=C.DECK
print('levels',np.round(C.sig[D],3))
print('current all-sky ',np.round(a['heat'][D],2),' LW',np.round(a['lw'][D],2),' LW clear',np.round(a['lw_clr'][D],2))
print('D1 pdf  all-sky ',np.round(b['heat'][D],2),' LW',np.round(b['lw'][D],2))
# D2 per deck-top column, with D1 cloud
T=C.T0+dT; th=T*(C.ps/C.p)**0.2857
moist=0.6e-3/86400   # measured combo phys moistening at 0.86 (g/kg/day -> kg/kg/s)
for A in (0.4,0.54,0.6):
  rows=[]
  for kt in D:
    q=np.minimum(C.q0,0.95*C.qs_(T)); 
    for k in range(kt+1,C.K(0.95)+1): q[k]=max(q[k],0.85*C.qs_(T)[k])
    q[kt]=r*C.qs_(T)[kt]
    cond=np.zeros_like(T); cond[kt]=1.32*4*C.CP/C.LV/86400
    R=C.rad(T,q,cond,dict(pdf=1.0),clear=True)
    dF=max(R['lw_clr'][kt]-R['lw'][kt],0)/86400*C.CP*C.mass[kt]
    dth=max(th[kt-1]-th[kt],0.5); dq=q[kt-1]-q[kt]
    rwe=A*dF/(C.CP*dth)
    heat=rwe*C.CP*dth*(T[kt]/th[kt])/C.mass[kt]/C.CP*86400      # ~ A * cloud cooling
    dry=rwe*dq/C.mass[kt]*86400*1e3
    # equilibrium: entrainment drying = moistening from below -> cloud LW driving that can be sustained
    dF_eq=moist*C.mass[kt]*C.CP*dth/(A*max(-dq,1e-4))
    rows.append((C.sig[kt],dF,dth,dq*1e3,rwe/(C.p[kt]/(C.RD*T[kt]))*1e3,heat,dry,dF_eq/(C.CP*C.mass[kt])*86400, (R['lw_clr'][kt]-R['lw'][kt])))
  print(f'A={A}')
  for x in rows: print('  sig %.3f dF_cld %.1f W/m2 dth %.2f K dq %.2f g/kg w_e %.1f mm/s -> heat %+.2f K/d, dry %+.2f g/kg/d | cloud LW cooling now %.2f K/d, sustainable %.2f K/d'%(x[0],x[1],x[2],x[3],x[4],x[5],x[6],x[8],x[7]))
