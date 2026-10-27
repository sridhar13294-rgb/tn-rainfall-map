import json,sys,glob,collections
def at(tr,h):
    for a,b in zip(tr,tr[1:]):
        if a[0]<=h<=b[0]:
            f=(h-a[0])/max(1e-6,b[0]-a[0]);return (a[1]+f*(b[1]-a[1]),a[2]+f*(b[2]-a[2]))
B=collections.defaultdict(list)
for f in sys.argv[1:]:
    for r in json.load(open(f)):
        tr=r['real'];m=r['trk']
        for h in (24,72):
            a=at(tr,h);b=at(m,h)
            if a and b: B[(r['var'],h)].append((b[0]-a[0],b[1]-a[1]))
for k in sorted(B):
    v=B[k];n=len(v);print(k,n,'dlat %+.2f dlon %+.2f'%(sum(x[0] for x in v)/n,sum(x[1] for x in v)/n))
