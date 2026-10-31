import json,math,numpy as np
K='data/cyclone/kaggle/'
def dist(a,b,c,d): return 111.2*math.hypot(a-c,((b-d+180)%360-180)*math.cos(math.radians((a+c)/2)))
def load(s):
  R={}; err=0
  for f in ('h0','h1'):
    for r in json.load(open(f'{K}tn-lib84-{s}/{f}.json')):
      if 'trk' in r and r['trk']: R[r['name']]=r
      else: err+=1
  return R,err
def truth(r,h):
  P=r['real']
  for a,b in zip(P,P[1:]):
    if a[0]<=h<=b[0]:
      f=(h-a[0])/max(1e-9,b[0]-a[0]); return [a[i]+f*(b[i]-a[i]) if a[i] is not None and b[i] is not None else None for i in (1,2,3)]
def score(r):
  T={x[0]:x for x in r['trk']}; ok=True; prev=None; e={}
  for h in sorted(T):
    x=T[h]
    if any(v is None or (isinstance(v,float) and math.isnan(v)) for v in x[1:5]): ok=False; continue
    if prev and dist(prev[1],prev[2],x[1],x[2])>250: ok=False
    prev=x
    if h in (24,48,72,96,120):
      t=truth(r,h)
      if t and t[0] is not None: e[h]=(dist(x[1],x[2],t[0],t[1]) if ok else None, x[3], x[4], t[2])
  return e
D={}; 
for s in ('ctl','corr','f2corr'):
  R,err=load(s); D[s]={n:score(r) for n,r in R.items()}; print(s,'storms',len(R),'missing/errored',err)
common=set.intersection(*[set(v) for v in D.values()])
print('common storms',len(common))
for h in (24,48,72,96,120):
  line=f'{h:4d} h |'
  base=[n for n in common if all(h in D[s][n] and D[s][n][h][0] is not None for s in D)]
  for s in D:
    tr=np.mean([D[s][n][h][0] for n in base]) if base else float('nan')
    ws=[D[s][n][h][1] for n in common if h in D[s][n]]; ps=[D[s][n][h][2] for n in common if h in D[s][n]]
    line+=f' {s}: trk {tr:5.0f} (n{len(base)}) wind {np.mean(ws):4.1f} p {np.mean(ps):6.1f} |'
  obs=[D['ctl'][n][h][3] for n in common if h in D['ctl'][n] and D['ctl'][n][h][3] is not None]
  print(line, f'obs wind {np.mean(obs):4.1f}')
# per-storm win counts at 72h track and wind
for s in ('corr','f2corr'):
  for h in (72,120):
    b=[n for n in common if h in D[s][n] and h in D['ctl'][n] and D[s][n][h][0] is not None and D['ctl'][n][h][0] is not None]
    better=sum(D[s][n][h][0]<D['ctl'][n][h][0] for n in b); wb=sum(D[s][n][h][1]>D['ctl'][n][h][1] for n in b)
    jumps=sum(1 for n in common if any(v[0] is None for v in D[s][n].values()))
    print(f'{s} vs ctl {h}h: track better in {better}/{len(b)}, wind higher in {wb}/{len(b)}; storms with a track jump/NaN {jumps} (ctl {sum(1 for n in common if any(v[0] is None for v in D["ctl"][n].values()))})')
