import json, sys, numpy as np, datetime as dt
sys.path.insert(0,'/home/claude/tn-rainfall-map/scripts/cyclone/analysis')
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from collections import Counter
LAND=json.load(open('/home/claude/tn-rainfall-map/data/cyclone/land.json'))
D=json.load(open('data/scen.json')); R=D['runs']; t0=dt.datetime.fromisoformat(D['t0'])
SEGS=['Sri Lanka','south TN','north TN','south AP','central AP','north AP','Odisha/WB','Bangladesh/Myanmar','no landfall']
cm=plt.get_cmap('viridis'); COL={s:cm(i/7) for i,s in enumerate(SEGS[:8])}; COL['no landfall']=(0.6,0.6,0.6,1)
fig=plt.figure(figsize=(8,13),dpi=150); ax=fig.add_axes([0.06,0.42,0.9,0.53])
for r in sorted(R,key=lambda r:SEGS.index(r['seg'])!=1 and SEGS.index(r['seg'])!=2):
    p=np.array([(x[1],x[2]) for x in r['pts']]); tn=r['seg'] in('south TN','north TN')
    ax.plot(p[:,1],p[:,0],color=COL[r['seg']],lw=1.1 if tn else 0.4,alpha=0.9 if tn else 0.18,zorder=4 if tn else 2)
for r in R:
    if r['lf']: ax.plot(r['lf']['lon'],r['lf']['lat'],'o',ms=3,color=COL[r['seg']],mec='white',mew=0.3,zorder=5)
for ring in LAND:
    a=np.array(ring)
    if a[:,0].max()<70 or a[:,0].min()>105 or a[:,1].min()>30: continue
    ax.add_patch(Polygon(a,closed=True,fc='#efe9dc',ec='#5a5345',lw=0.6,zorder=1))
ax.plot(D['seedling'][1],D['seedling'][0],marker='*',ms=16,color='#c0392b',mec='white',zorder=6)
ax.annotate('seedling now\n(700 hPa, 21 Oct)',(D['seedling'][1],D['seedling'][0]),xytext=(8,-14),textcoords='offset points',fontsize=8,zorder=7)
ax.add_patch(plt.Rectangle((85,8),9,6,fill=False,ls='--',ec='#c0392b',lw=1,zorder=6)); ax.text(85.2,7.4,'where the low was allowed to form (22-26 Oct)',fontsize=7,color='#c0392b')
ax.set_xlim(76,96); ax.set_ylim(5,24); ax.set_aspect(1/np.cos(np.radians(15))); ax.set_facecolor('#f4f8fb'); ax.tick_params(labelsize=7)
c=Counter(r['seg'] for r in R); n=len(R)
from matplotlib.lines import Line2D
ax.legend([Line2D([],[],color=COL[s],lw=3) for s in SEGS if c[s]],[f'{s}  {100*c[s]/n:.0f}%' for s in SEGS if c[s]],loc='upper right',fontsize=8,title='Where it crosses the coast',title_fontsize=8,framealpha=0.95)
ax.set_title(f'Our own ensemble: {n} combinations of 11 inputs, no model forecasts\nStart: observed analysis 00Z 21 Oct + ERA5 evolution of the closest past storms',fontsize=10,loc='left',fontweight='bold')
# drivers: spread in % reaching TN or south AP across each input's range
num={'gen_day':'When the low forms (22 → 26 Oct)','gen_lon':'Where it forms: east ↔ west','beta':'Storm size / beta drift','ridge_dlon':'Ridge shifted west ↔ east','peak':'How strong it gets (SST, MJO, shear)','mjo':'MJO state','gen_lat':'Where it forms: south ↔ north','as_sys':'Arabian Sea system','surge_u':'NE-monsoon easterly surge','ridge_str':'Ridge strength','ridge_dt':'Ridge timing','speed':'Forward speed','wd_day':'Western disturbance timing','wd_amp':'Western disturbance depth','sst':'Sea temperature (alone)','shear':'Shear / dry air','ridge_dlat':'Ridge shifted north ↔ south','gom':'Gulf of Mannar circulation'}
for r in R: r['gen_day']=(dt.datetime.fromisoformat(r['gen_t'])-t0).total_seconds()/86400; r['south']=r['seg'] in('south TN','north TN','south AP','Sri Lanka')
out=[]
for k,lab in num.items():
    v=[r[k] for r in R]
    if isinstance(v[0],str) or k in('peak','wd_amp'):
        groups=[[r for r in R if r[k]==u] for u in sorted(set(v),key=str)]
    else:
        q=np.quantile(v,[1/3,2/3]); groups=[[r for r in R if r[k]<=q[0]],[r for r in R if q[0]<r[k]<=q[1]],[r for r in R if r[k]>q[1]]]
    p=[100*np.mean([g['south'] for g in G]) for G in groups if G]; out.append((lab,min(p),max(p)))
out.sort(key=lambda x:x[2]-x[1]); bx=fig.add_axes([0.42,0.04,0.53,0.32])
for i,(lab,lo,hi) in enumerate(out):
    bx.plot([lo,hi],[i,i],color='#2b5d8a',lw=4,solid_capstyle='round'); bx.text(-1,i,lab,ha='right',va='center',fontsize=8)
bx.axvline(100*np.mean([r['south'] for r in R]),color='#888',lw=0.8,ls=':')
bx.set_yticks([]); bx.set_xlim(0,40); bx.set_xlabel('% of runs crossing the coast in TN or south AP (south of 15.9°N)',fontsize=8); bx.tick_params(labelsize=7)
for s in ('top','right','left'): bx.spines[s].set_visible(False)
fig.text(0.02,0.375,'Which inputs matter: each bar spans the lowest to highest chance across that input\'s range (dotted = all runs)',fontsize=9,fontweight='bold')
fig.savefig('scen_map.png',bbox_inches='tight'); print('ok')
