# Offline derivation: effect of including the latent heat of fusion (ice phase) on a deep tropical updraft.
# Undilute parcel from 1000 hPa (T 300 K, RH 80%) lifted moist-adiabatically; above 0 C the condensate freezes
# linearly between 0 and -20 C (as the code's fice); frozen condensate releases Lf = 3.34e5 J/kg (and further
# deposition releases Ls = Lv + Lf). Compare parcel T and buoyancy vs a tropical-mean environment.
import numpy as np
cp,Rd,Rv,Lv,Lf,g=1004.6,287.04,461.5,2.5e6,3.34e5,9.81
def esw(T): return 611.2*np.exp(17.67*(T-273.15)/(T-29.65))
def esi(T): return 611.2*np.exp(22.46*(T-273.15)/(T-0.53))
def qs(T,p,e): return 0.622*e/(p-0.378*e)
p=np.arange(100000,9999,-1000.0)
Tenv=np.interp(p[::-1],[10000,15000,20000,25000,30000,40000,50000,60000,70000,85000,100000],[195,206,218,228,242,258,268,276,283,292,300])[::-1]
def lift(ice):
    T=300.0; q=0.8*qs(300,1e5,esw(300)); out=[]; frozen=0.0
    for k in range(1,len(p)):
        p0,p1=p[k-1],p[k]
        # dry/moist step: conserve h = cp T + g z + L q (+ Lf * frozen) with hydrostatic dz
        Tv=T*(1+0.61*q); dz=Rd*Tv/g*np.log(p0/p1)
        T1=T-g/cp*dz; q1=q
        fi=np.clip((273.15-T1)/20,0,1) if ice else 0.0
        e=(1-fi)*esw(T1)+fi*esi(T1); qsat=qs(T1,p1,e)
        if q1>qsat:
            L=Lv+fi*Lf
            for _ in range(20):
                e=(1-fi)*esw(T1)+fi*esi(T1); qsat=qs(T1,p1,e)
                c=(q1-qsat)/(1+L**2*qsat/(cp*Rv*T1**2)); T1+=L*c/cp; q1-=c
                if abs(c)<1e-9: break
        if ice:  # freeze earlier liquid condensate as fi rises: extra Lf
            dfr=max(fi-frozen,0)*0.0  # condensate rained out (pseudo-adiabatic): only new condensate counted above
        T,q=T1,q1; out.append(T)
    return np.array([300.0]+out)
Tw=lift(False); Ti=lift(True)
for P in (60000,50000,40000,30000,25000,20000,15000):
    k=int(np.argmin(abs(p-P))); print(f'{P/100:4.0f} hPa: env {Tenv[k]:6.1f}  parcel water-only {Tw[k]:6.1f} (b {Tw[k]-Tenv[k]:+5.1f})  with ice {Ti[k]:6.1f} (b {Ti[k]-Tenv[k]:+5.1f})  diff {Ti[k]-Tw[k]:+4.1f} K')
cape=lambda Tp: Rd*np.sum(np.maximum(Tp[:-1]-Tenv[:-1],0)*np.log(p[:-1]/p[1:]))
print('CAPE water-only %.0f J/kg, with ice %.0f J/kg'%(cape(Tw),cape(Ti)))
top=lambda Tp: p[np.where(Tp>Tenv)[0].max()]/100
print('level of neutral buoyancy: water-only %.0f hPa, with ice %.0f hPa'%(top(Tw),top(Ti)))
