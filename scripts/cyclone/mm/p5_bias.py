"""P5 (5 Nov, peer suggestion): large-scale steering circulation audit - SYSTEMATIC part. For many starts, mean forecast
bias MAPS vs ERA5 over the India / Bay of Bengal / Arabian Sea box (40-120 E, 0-45 N) at lead days 1, 3, 5:
z500, u850, v850, u200, v200, mslp. From the mean maps: (a) 500-hPa ridge strength = z500 difference 25 N minus 12 N
along 80-95 E (subtropical-ridge gradient -> deep easterly steering), (b) deep-layer steering bias over the Bay
(0.25 u850 + ... simplified: mean of 850 and 200 hPa winds, 10-20 N 82-95 E), (c) 200-hPa jet latitude and the
NW-India upper trough (v200 over 20-35 N 65-80 E). python p5_bias.py LIB TRUTH OUT_JSON 'START,START,...' SETTINGS_JSON"""
import sys, os, json, datetime as dt, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
LIB, TRU, OUT, STARTS, SET = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4].split(','), json.loads(sys.argv[5])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = dict(np.load(TRU)); DI = {str(d): i for i, d in enumerate(TR['days'])}
la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
iy = np.where((la >= 0) & (la <= 45))[0]; ix = np.where((lo >= 40) & (lo <= 120))[0]
SET = dict(SET); GR = SET.pop('grid', 'T170'); M = mm2.Model(GR, 32, None, dict({'rad': 'radcloud', 'rad_every': 2}, **SET))
KEYS = ('z500', 'u850', 'v850', 'u200', 'v200', 'mslp'); acc = {d: {k: [] for k in KEYS} for d in (1, 3, 5)}; used = []
for key in STARTS:
    key = key if 'T' in key else key + 'T00'
    if key not in TT: continue
    k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); out = M.run_wx(st, cr, 120, 24)
    if not np.isfinite(out['mslp']).all(): print(key, 'blew up', flush=True); continue
    for d in (1, 3, 5):
        v = (t0 + dt.timedelta(days=d)).strftime('%Y-%m-%dT%H')
        if v not in DI: continue
        j = DI[v]
        for kk in KEYS:
            f = WS.to_grid(out[kk][d], M.lon, M.lat); o = TR['o_' + kk][j]
            if not np.isfinite(o).any(): continue
            acc[d][kk].append((np.asarray(f) - np.asarray(o))[np.ix_(iy, ix)])
    used.append(key); print(key, 'done', flush=True)
LA, LO = la[iy], lo[ix]
def box(F, a, b, c, d_): return float(np.nanmean(F[np.ix_((LA >= a) & (LA <= b), (LO >= c) & (LO <= d_))]))
res = dict(settings=SET, starts=used, lat=LA.tolist(), lon=LO.tolist(), days={})
for d in (1, 3, 5):
    m = {kk: np.nanmean(np.stack(v), 0) if v else None for kk, v in acc[d].items()}
    if m['z500'] is None: continue
    r = dict(n=len(acc[d]['z500']))
    r['z500_bias_25N'] = box(m['z500'], 24, 26, 80, 95); r['z500_bias_12N'] = box(m['z500'], 11, 13, 80, 95)
    r['ridge_gradient_bias_25N_minus_12N_m'] = r['z500_bias_25N'] - r['z500_bias_12N']
    r['geostrophic_u500_bias_from_gradient_ms'] = -9.80616 * r['ridge_gradient_bias_25N_minus_12N_m'] / (2 * 7.292e-5 * np.sin(np.radians(18.5)) * 13 * 111200)
    r['bay_steering_bias_u_v'] = [round((box(m['u850'], 10, 20, 82, 95) + box(m['u200'], 10, 20, 82, 95)) / 2, 2), round((box(m['v850'], 10, 20, 82, 95) + box(m['v200'], 10, 20, 82, 95)) / 2, 2)]
    r['bay_u850_v850_bias'] = [round(box(m['u850'], 10, 20, 82, 95), 2), round(box(m['v850'], 10, 20, 82, 95), 2)]
    r['bay_u200_v200_bias'] = [round(box(m['u200'], 10, 20, 82, 95), 2), round(box(m['v200'], 10, 20, 82, 95), 2)]
    r['nw_india_v200_bias'] = box(m['v200'], 20, 35, 65, 80); r['central_india_mslp_bias_hPa'] = box(m['mslp'], 18, 26, 74, 86) / 100
    r['maps'] = {kk: np.round(v, 2).tolist() for kk, v in m.items() if v is not None}
    res['days'][d] = r
    print(f'day {d} n {r["n"]}:', json.dumps({kk: (round(vv, 2) if isinstance(vv, float) else vv) for kk, vv in r.items() if kk != 'maps'}), flush=True)
json.dump(res, open(OUT, 'w'))
