import sys, json, os, datetime as dt, importlib.util
SP = '/tmp/claude-0/-home-claude/2c3b34a9-cc00-53e0-8864-49737f9cdb93/scratchpad'
R = SP + '/wtmain'; sys.path.insert(0, R + '/scripts'); import forecast
spec = importlib.util.spec_from_file_location('vh', SP + '/daily23/verify_hg.py'); vh = importlib.util.module_from_spec(spec); spec.loader.exec_module(vh)
vh.ROOT = R; vh.P = lambda *a: os.path.join(R, *a); vh.OBS = vh.P
vh.FC_DIR = vh.P('data', 'verify', 'fc'); vh.SCORES = SP + '/daily23/hg23.json'
pts = forecast.tn_points(json.load(open(R + '/data/geo.json')))
now = dt.datetime(2026, 10, 23, 5, 0, tzinfo=dt.timezone.utc)
out = vh.verify(pts, now)
D = out['districts']
print('district heavy (>=64.5 mm at the heaviest gauge) scores, all days:')
for n, by in D['scores'].items():
    for l in ('1', '2'):
        if l in by: print(f"  {n:14s} L{l} heavy hit/miss/false {by[l]['heavy']['hit']}/{by[l]['heavy']['miss']}/{by[l]['heavy']['false']}  vheavy {by[l]['vheavy']['hit']}/{by[l]['vheavy']['miss']}/{by[l]['vheavy']['false']}  days {by[l]['days']}")
print('district events 18-19 Oct:')
for e in D['events']:
    if e['date'] >= "2026-10-21": print(' ', e['date'], e['district'], e['obs'], e['gauge'], e['fc'])
# squares >= 20 mm on 19 Oct, by area
cells = vh.gauge_cells(pts); dg, dc, st = vh.district_cells(pts)
cell_d = {}
for d, ii in dc.items():
    for i in ii: cell_d.setdefault(i, d)
obs = json.load(open(R + '/data/daily/2026-10-23.json'))
WEST = {'Nilgiris', 'The Nilgiris', 'Coimbatore', 'Tiruppur', 'Theni', 'Dindigul', 'Tenkasi', 'Tirunelveli', 'Kanniyakumari', 'Kanyakumari', 'Virudhunagar', 'Erode', 'Krishnagiri', 'Dharmapuri', 'Salem', 'Namakkal'}
COAST = {'Chennai', 'Tiruvallur', 'Chengalpattu', 'Kancheepuram', 'Viluppuram', 'Villupuram', 'Cuddalore', 'Mayiladuthurai', 'Nagapattinam', 'Tiruvarur', 'Thanjavur', 'Pudukkottai', 'Ramanathapuram', 'Thoothukudi', 'Puducherry', 'Karaikal'}
def area(d): return 'west/hills' if d in WEST else ('coast' if d in COAST else 'interior')
heavy = []
for i, sids in cells.items():
    v = [obs[s] for s in sids if obs.get(s) is not None]
    if v and sum(v) / len(v) >= 20: heavy.append((i, round(sum(v) / len(v), 1), cell_d.get(i, '?')))
print('squares >= 20 mm on 19 Oct:', [(h[1], h[2], area(h[2])) for h in heavy])
# forecast heavy squares from the lead-1 run used by verify (latest run before the window start)
runs = sorted(f for f in os.listdir(vh.FC_DIR))
ws = vh.window_start(dt.date(2026, 10, 23))
for lead in (1, 2):
    cand = [f for f in runs if ws - dt.timedelta(hours=24 * lead) <= vh.utc(f[:10]) < ws - dt.timedelta(hours=24 * (lead - 1))]
    if not cand: continue
    fc = json.load(open(os.path.join(vh.FC_DIR, cand[-1])))['days'].get('2026-10-23') or {}
    print('lead', lead, 'run', cand[-1])
    for n, arr in fc.items():
        fh = [i for i in cells if arr[i] / 10 >= 20]
        by = {}
        for i in fh: by[area(cell_d.get(i, '?'))] = by.get(area(cell_d.get(i, '?')), 0) + 1
        hit = [i for i, _, _ in heavy if arr[i] / 10 >= 20]
        print(f"   {n:14s} >=20mm squares forecast {len(fh)} {by}  obs-heavy squares hit {len(hit)}/{len(heavy)}  fc there {[round(arr[i]/10,1) for i,_,_ in heavy]}")
# observed totals by area
agg = {}
for i, sids in cells.items():
    v = [obs[s] for s in sids if obs.get(s) is not None]
    if v: agg.setdefault(area(cell_d.get(i, '?')), []).append(sum(v) / len(v))
print('obs mean by area 19 Oct:', {k: (round(sum(v) / len(v), 1), len(v)) for k, v in agg.items()})
top = sorted(((v, s) for s, v in obs.items() if isinstance(v, (int, float))), reverse=True)[:8]
print('top gauges 19 Oct:', [(v, st.get(s, {}).get('name', s), st.get(s, {}).get('district', '')) for v, s in top])
print('first_run', out['first_run'], 'weights', out['weights'], 'note', out['note'])
