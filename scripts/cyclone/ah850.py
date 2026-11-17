"""17 Nov: 850-hPa Arabian/NW-India high bias, westward vs turning storms (registered in rootcause 11:15)."""
import sys, json, datetime as dt, numpy as np
sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/mm'); sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/analysis')
import mm2, landinit, ourens as O
NAMES = sys.argv[1].split(',')
Z = dict(np.load('/tmp/claude-0/dl/libm_fields.npz')); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
M = mm2.Model('T42', 32, 20.0, dict(cmt_mf=1, rd_si=1, map_out=True))
BOX = {'Arab/NWInd 15-28N 55-75E': (15, 28, 55, 75), 'C/NW India 18-28N 70-85E': (18, 28, 70, 85), 'Indochina 12-25N 95-110E': (12, 25, 95, 110)}
def unq(z, k): return z[k].astype(np.float64) * float(z[k + '__scale']) + float(z[k + '__off'])
def truth(y, t, var):
    z = np.load(f'/tmp/claude-0/cases/days_{y}.npz'); T = [dt.datetime.strptime(s, '%Y%m%d%H') for s in z['times']]
    near = sorted(range(len(T)), key=lambda i: abs((T[i] - t).total_seconds()))[:2]
    w = [1 / (1 + abs((T[i] - t).total_seconds()) / 3600) for i in near]
    if abs((T[near[0]] - t).total_seconds()) < 60: near, w = near[:1], [1]
    F = sum(wi * unq(z, var)[i] for i, wi in zip(near, w)) / sum(w); return np.asarray(z['lat']), np.asarray(z['lon']), F
res = {}
for s in O.LIBL:
    if s['name'] not in NAMES: continue
    g = O.gen_time(s); k = TT.index(g.strftime('%Y-%m-%dT%H')); P0 = O.path_of(s)
    st0 = next((p[1], p[2], p[3]) for p in P0 if p[0] >= g)
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; f2 = Z['f2'][k]
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], storm=dict(lat=st0[0], lon=st0[1], vmax_kt=st0[2] or 25.0),
                    when=g, **landinit.land_kwargs(f2, V2))
    M.build(g); st = M.dfi(st); out = M.run_wx(st, cr, 120, 24)
    ML, MA = np.asarray(M.lon), np.asarray(M.lat); zs = np.asarray(M.zs)
    zs = zs if zs.shape == (len(ML), len(MA)) else zs.T
    r = {}
    for d in range(0, 6):
        t = g + dt.timedelta(days=d)
        for var in ('z850', 'u850'):
            la, lo, F = truth(g.year, t, var)
            Ton = F[np.abs(la[:, None] - MA[None]).argmin(0)][:, np.abs(lo[:, None] - ML[None]).argmin(0)].T
            D = np.asarray(out[var])[d] - Ton
            boxes = BOX if var == 'z850' else {'Bay 10-22N 80-95E': (10, 22, 80, 95)}
            for b, (a0, a1, o0, o1) in boxes.items():
                m = (ML[:, None] >= o0) & (ML[:, None] <= o1) & (MA[None] >= a0) & (MA[None] <= a1) & (zs < 800)
                r.setdefault(f'{var} {b}', []).append(round(float(D[m].mean()), 1))
    res[s['name']] = r; print(s['name'], g, json.dumps(r), flush=True)
json.dump(res, open(sys.argv[2], 'w'))
