# L2: cloudtop.py vs the hand derivation (d2 formula, same columns, A=0.54); conservation
import sys; sys.path.insert(0,'/home/claude/tn-rainfall-map/scripts/cyclone/mm')
import numpy as np, cloud_derivation as C, cloudtop
r=0.99; T=C.T0-2.4; th=T*(C.ps/C.p)**0.2857
z=np.zeros_like(C.p); z[-1]=C.RD*T[-1]/C.G*np.log(C.ps/C.p[-1])
for k in range(len(C.p)-2,-1,-1): z[k]=z[k+1]+C.RD*0.5*(T[k]+T[k+1])/C.G*np.log(C.p[k+1]/C.p[k])
s=C.CP*T+C.G*z; S=lambda a:a.reshape(-1,1,1)
def colq(kt):
  q=np.minimum(C.q0,0.75*C.qs_(T))                     # free troposphere below RHc: no cloud above the deck
  for k in range(kt+1,C.K(0.95)+1): q[k]=0.85*C.qs_(T)[k]
  q[kt]=r*C.qs_(T)[kt]; return q
out=[]
for kt in C.DECK:
  q=colq(kt); cond=np.zeros_like(T); cond[kt]=1.32*4*C.CP/C.LV/86400
  R=C.rad(T,q,cond,dict(pdf=1.0),clear=True); lwc=(R['lw']-R['lw_clr'])/86400
  # hand formula
  dF=-lwc[kt]*C.CP*C.mass[kt]; dth=max(th[kt-1]-th[kt],0.5); rwe=0.54*dF/(C.CP*dth)
  h_hand=rwe*(s[kt-1]-s[kt])/C.mass[kt]/C.CP*86400; q_hand=rwe*(q[kt-1]-q[kt])/C.mass[kt]*86400e3
  dTt,dqt,d=cloudtop.cloud_top_entrainment(S(T),S(q),S(C.p),np.array([[C.ps]]),S(z),S(C.mass),S(lwc),S(R['cloud']),0.54,1200.0,np,no_deep=np.array([[True]]))
  dTt=dTt[:,0,0]*86400; dqt=dqt[:,0,0]*86400e3; k=int(d['kt'][0,0])
  print(f"top {C.sig[kt]:.3f} found {C.sig[k]:.3f} | dF {dF:5.1f} W/m2 w_e {rwe*C.RD*T[kt]/C.p[kt]*1e3:4.1f} mm/s | heat hand {h_hand:+.3f} code {dTt[k]:+.3f} K/d | dry hand {q_hand:+.3f} code {dqt[k]:+.3f} g/kg/d | energy {(dTt*C.CP*C.mass).sum():+.1e} water {(dqt*C.mass).sum():+.1e}")
  out.append((R['heat'][C.DECK],R['lw'][kt],R['lw_clr'][kt],dTt))
print('deck-mean all-sky rad (pdf) per level',np.round(np.mean([o[0] for o in out],0),2))
print('deck-mean entrainment heating per level',np.round(np.mean([o[3][C.DECK] for o in out],0),2), ' above-deck', np.round(np.mean([o[3][C.K(0.786)] for o in out]),2))
