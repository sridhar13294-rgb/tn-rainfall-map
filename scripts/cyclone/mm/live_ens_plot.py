import pickle, json, numpy as np, datetime as dt, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
S='/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad/andaman/'
O=pickle.load(open(S+'out.pkl','rb')); B=json.load(open('/home/claude/tn-rainfall-map/data/cyclone/kaggle/tn-maps-borders/borders.json'))
LON=(75,100); LAT=(4,24)
def base(ax):
    for k,c,lw in (('coast','0.25',0.8),('countries','0.55',0.5),('states','0.75',0.3)):
        for ln in B[k]:
            a=np.array(ln)
            if a.ndim==2 and ((a[:,0]>LON[0]-2)&(a[:,0]<LON[1]+2)&(a[:,1]>LAT[0]-2)&(a[:,1]<LAT[1]+2)).any(): ax.plot(a[:,0],a[:,1],color=c,lw=lw)
    ax.set_xlim(*LON); ax.set_ylim(*LAT); ax.set_aspect('equal'); ax.grid(alpha=0.2)
    ax.axhspan(11.7,13.6,xmin=(78.5-LON[0])/25,xmax=(80.6-LON[0])/25,color='green',alpha=0.15)
    ax.text(77.3,12.6,'North TN',fontsize=7,color='green',ha='center')
    ax.text(78.3,15.0,'South AP',fontsize=7,color='purple',ha='center')
fig=plt.figure(figsize=(16,11))
ax1=fig.add_subplot(2,2,1); base(ax1)
col={'80 km 12Z':'tab:blue','80 km 18Z':'tab:orange','140 km 12Z':'0.6'}
for name in ('140 km 12Z','80 km 12Z','80 km 18Z'):
    for m in O[name]['mem']:
        a=np.array([[t[2],t[1]] for t in m['pts']]); ax1.plot(a[:,0],a[:,1],color=col[name],lw=0.5 if '80' in name else 0.3,alpha=0.55 if '80' in name else 0.3)
        if m['lf'] and '80' in name: ax1.plot(m['lf'][2],m['lf'][1],'v',color=col[name],ms=4)
for name in ('80 km 12Z','80 km 18Z'):
    hs=range(0,169,12); mean=[]
    for h in hs:
        p=[[t[2],t[1]] for m in O[name]['mem'] for t in m['pts'] if t[0]==h]
        if len(p)>=len(O[name]['mem'])//2: mean.append(np.mean(p,0))
    mean=np.array(mean); ax1.plot(mean[:,0],mean[:,1],color=col[name],lw=3,label=f'{name} mean ({len(O[name]["mem"])} members)')
ax1.plot(97.0,8.5,'*',color='red',ms=15,label='observed low 29 Oct (8.5N 97E)')
ax1.annotate('IMD: depression ~31 Oct,\nWNW towards Andhra Pradesh',xy=(84,15.5),xytext=(88,19),arrowprops=dict(arrowstyle='->',color='crimson'),color='crimson',fontsize=9)
ax1.plot([],[],color='0.6',label='140 km 12Z members'); ax1.legend(fontsize=8,loc='lower left'); ax1.set_title('Member tracks (v = landfall)')
# strike probability (80 km, both runs)
ax2=fig.add_subplot(2,2,2); base(ax2)
gx,gy=np.meshgrid(np.arange(LON[0],LON[1]+0.01,0.5),np.arange(LAT[0],LAT[1]+0.01,0.5)); hit=np.zeros_like(gx); n=0
for name in ('80 km 12Z','80 km 18Z'):
    for m in O[name]['mem']:
        n+=1; h=np.zeros_like(gx,bool)
        for t in m['pts']:
            d=np.hypot((gx-t[2])*np.cos(np.radians(t[1])),gy-t[1])*111.2; h|=d<=120
        hit+=h
cs=ax2.contourf(gx,gy,100*hit/n,levels=[5,10,20,30,40,50,60,80,100],cmap='YlOrRd',alpha=0.85); plt.colorbar(cs,ax=ax2,shrink=0.8,label='% of members within 120 km')
ax2.set_title(f'Strike probability, 7 days (80 km, 12Z+18Z, {n} members)')
# pressure / wind vs time
ax3=fig.add_subplot(2,2,3)
for name in ('80 km 12Z','80 km 18Z'):
    t0=O[name]['t0']
    for m in O[name]['mem']:
        ax3.plot([t0+dt.timedelta(hours=t[0]) for t in m['pts']],[t[4] for t in m['pts']],color=col[name],lw=0.4,alpha=0.35)
    d=O[name]['daily']; ax3.plot([t0+dt.timedelta(hours=h) for h in d],[v[3] for v in d.values()],color=col[name],lw=3,label=f'{name} median')
ax3.invert_yaxis(); ax3.set_ylabel('central pressure (hPa)'); ax3.legend(fontsize=8); ax3.grid(alpha=0.3)
ax3.axvline(dt.datetime(2026,10,31,3),color='crimson',ls='--'); ax3.text(dt.datetime(2026,10,31,4),1001,'IMD: depression\nexpected ~31 Oct',color='crimson',fontsize=8)
ax3.set_title('Central pressure of each member (lower = stronger)'); fig.autofmt_xdate()
# table
ax4=fig.add_subplot(2,2,4); ax4.axis('off')
order=['north TN','south TN','south AP','north AP/Odisha','Sri Lanka','no landfall / at sea']
rows=[[s]+[f"{100*O[k]['segs'].get(s,0)/len(O[k]['mem']):.0f}%" for k in ('80 km 12Z','80 km 18Z','140 km 12Z')] for s in order]
tb=ax4.table(cellText=rows,colLabels=['Landfall segment','80 km 12Z','80 km 18Z','140 km 12Z'],loc='upper center',cellLoc='center'); tb.scale(1,1.6); tb.set_fontsize(10)
txt=("MEGAM live ensemble - South Andaman low (start 29 Oct 12Z and 18Z)\n"
     "80 km grid, 32 levels; 12Z: 36 of 51 members (one job refused - GPU quota); 18Z: 51 members; 140 km: 51 members.\n"
     "Honest reading: our storms run too weak (known problem) - judge formation, timing and track, not strength.\n"
     "North TN = Cuddalore-Chennai-Pulicat; south AP = Sriharikota-Nellore-Ongole.")
ax4.text(0.0,0.05,txt,fontsize=9,va='bottom',wrap=True)
fig.suptitle('MEGAM ensemble: South Andaman low, run 29 Oct 2026 12Z + 18Z',fontsize=14)
plt.tight_layout(); plt.savefig(S+'megam_andaman_low_ensemble.png',dpi=110)
print('ok')
