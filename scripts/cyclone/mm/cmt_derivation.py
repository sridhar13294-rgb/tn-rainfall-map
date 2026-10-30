import numpy as np
g=9.81; Rd=287.0
p=np.arange(100,1001,50.0)*100   # Pa, top -> bottom
T=np.interp(p,[10000,20000,30000,50000,70000,85000,100000],[195,220,240,265,282,292,300]); rho=p/(Rd*T)
dz=np.gradient(-Rd*T/g*np.log(p))  # m between levels (positive downward index)
def eta_profile(psrc=97500,ptop=15000):
    frac=(psrc-p)/(psrc-ptop); e=np.where(frac<0.6,1.0,(1-frac)/0.4); return np.clip(np.where((p<psrc)&(p>=ptop),e,0),0,1)
def old_relax(u,eta,tau):
    cl=eta>0; m=np.gradient(-p)*0+5000/g   # equal mass levels (50 hPa)
    um=(u*cl).sum()/cl.sum(); return np.where(cl,(um-u)/tau,0.0)
def massflux_cmt(u,eta,Mb,eps=1e-4,Cu=0.7):
    # updraft from the source (bottom) upward: d(u_u)/dz = -eps (u_u - u) + Cu du/dz  (Gregory et al. 1997 / ECMWF)
    n=len(p); uu=np.zeros(n); ks=np.where(eta>0)[0].max()+1   # source = level below lowest cloud level
    uu[ks]=u[ks]
    for k in range(ks-1,-1,-1):
        if eta[k]<=0: uu[k]=u[k]; continue
        DZ=Rd*T[k]/g*np.log(p[k+1]/p[k]); dudz=(u[k]-u[k+1])/DZ
        uu[k]=uu[k+1]+DZ*(-eps*(uu[k+1]-u[k+1])+Cu*dudz)
    M=Mb*eta; M[ks]=Mb
    F=M*(uu-u)                       # upward momentum flux excess at each level (kg m-1 s-2)
    # flux at interfaces (mean of neighbours), tendency = g dF/dp  (p increases downward)
    Fi=np.concatenate([[0],0.5*(F[1:]+F[:-1]),[0]])
    dp=np.full(len(p),5000.0)
    return g*(Fi[1:]-Fi[:-1])/dp*-1*-1, uu
def report(name,u,Mb):
    eta=eta_profile(); day=86400
    r6=old_relax(u,eta,6*3600)*day; r2=old_relax(u,eta,2*86400)*day; mf,uu=massflux_cmt(u,eta,Mb); mf*=day
    i=lambda P: int(np.argmin(abs(p-P*100)))
    lo=[i(950),i(900),i(850)]; 
    print(f'== {name}: Mb {Mb} kg/m2/s')
    print('   level      ', ' '.join(f'{int(p[k]/100):5d}' for k in (i(950),i(850),i(700),i(500),i(300),i(200))))
    for lab,a in (('u (m/s)',u),('old 6 h',r6),('old 2 d',r2),('mass-flux',mf)):
        print(f'   {lab:10s}',' '.join(f'{a[k]:5.1f}' for k in (i(950),i(850),i(700),i(500),i(300),i(200))), ' m/s per day' if lab!='u (m/s)' else '')
    sh=lambda a: a[i(200)]-a[i(850)]
    print(f'   change of 850-200 hPa shear per day: old 6 h {sh(r6):+.1f}, old 2 d {sh(r2):+.1f}, mass-flux {sh(mf):+.1f} m/s/day   (shear now {sh(u):+.1f})')
    # column momentum conservation check (equal-mass levels)
    print(f'   column momentum change (should be ~0): old 6 h {r6.sum():+.2e}, mass-flux {mf.sum():+.2e}')
# storm core near the radius of max wind: tangential wind decreasing with height; convective rain ~120 mm/day
uc=np.interp(p,[10000,15000,20000,30000,40000,50000,60000,70000,80000,85000,90000,95000,100000],[1,1.5,2,4,6,8,10,12,13.5,14.5,15,15,14])
Mb_core=(120/86400)/0.015
report('storm core (rain 120 mm/day)',uc,Mb_core)
# ITCZ / monsoon column: 850 westerly 8, 200 easterly -12 (monsoon-like shear), rain 10 mm/day
ui=np.interp(p,[10000,15000,20000,30000,50000,70000,85000,92500,100000],[-8,-12,-12,-8,-2,4,8,7,4])
report('monsoon/ITCZ column (rain 10 mm/day)',ui,(10/86400)/0.015)
report('weak tropical convection (rain 3 mm/day)',ui,(3/86400)/0.015)
