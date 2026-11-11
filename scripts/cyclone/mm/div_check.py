"""Upper-level divergence / low-level convergence vs ERA5 (11 Nov, Sridhar): is the model making too much (or too little) divergence aloft
and convergence near the ground? Divergence of the 200 and 850 hPa wind on the 1.5-deg grid, model (day 1, 2) vs ERA5 at the same valid
time; tropical means of the divergent part (|div|, positive part at 200, negative part at 850) and regional boxes, per start.
python div_check.py LIB TRUTH GRID STARTS   env CANDS (json {name: settings})"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
TR = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(TR['days'])}
GR, KS = sys.argv[3], [int(x) for x in sys.argv[4].split(',')]
CANDS = json.loads(os.environ.get('CANDS', 'null')) or {'base2': {}}
A = 6.371e6; lat = np.linspace(-90, 90, 121); lon = np.arange(240) * 1.5; LAT = np.repeat(lat[:, None], 240, 1); cl = np.cos(np.radians(LAT))
def div(u, v):
    dudx = (np.roll(u, -1, 1) - np.roll(u, 1, 1)) / (2 * np.radians(1.5) * A * np.maximum(cl, 0.05))
    dvdy = np.gradient(v * cl, np.radians(lat), axis=0) / (A * np.maximum(cl, 0.05))
    return dudx + dvdy
W = cl; TROP = np.abs(LAT) <= 25
BOX = {'tropics 25S-25N': TROP, 'Indian Ocean+Bay 0-20N 60-100E': (LAT >= 0) & (LAT <= 20) & (lon[None] >= 60) & (lon[None] <= 100),
       'W Pacific warm pool 10S-10N 120-160E': (np.abs(LAT) <= 10) & (lon[None] >= 120) & (lon[None] <= 160),
       'E Pacific/Atlantic trades 5-25N 200-340E': (LAT >= 5) & (LAT <= 25) & (lon[None] >= 200) & (lon[None] <= 340)}
for nm, ex in CANDS.items():
    M = mm2.Model(GR, 32, float(os.environ.get('DT', 20)), dict({'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0}, **ex))
    acc = {}
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st)
        out = M.run_wx(st, cr, 48, 24)
        for ld in (1, 2):
            j = DI[(t0 + dt.timedelta(days=ld)).strftime('%Y-%m-%dT%H')]
            G_ = lambda key: WS.to_grid(out[key][ld], M.lon, M.lat)
            dm2, dm8 = div(G_('u200'), G_('v200')), div(G_('u850'), G_('v850'))
            do2, do8 = div(TR['o_u200'][j], TR['o_v200'][j]), div(TR['o_u850'][j], TR['o_v850'][j])
            for bx, m in BOX.items():
                g = lambda X: float((X * W)[m].sum() / W[m].sum()) * 1e6
                acc.setdefault((ld, bx), []).append((g(np.maximum(dm2, 0)), g(np.maximum(do2, 0)), g(np.minimum(dm8, 0)), g(np.minimum(do8, 0)),
                                                     g(np.abs(dm2)), g(np.abs(do2))))
        print(nm, TT[k], 'done', flush=True)
    print(f'\n{nm}: units 1e-6 /s. 200 hPa divergence (positive part) and 850 hPa convergence (negative part), model / ERA5, mean of {len(KS)} starts')
    for (ld, bx), r in sorted(acc.items()):
        r = np.array(r); mm = r.mean(0)
        print(f'  day {ld} {bx:40s} div200 {mm[0]:5.2f} / {mm[1]:5.2f} ({100*(mm[0]/mm[1]-1):+4.0f} %, model higher in {(r[:,0]>r[:,1]).sum()}/{len(r)}) | conv850 {mm[2]:+5.2f} / {mm[3]:+5.2f} ({100*(mm[2]/mm[3]-1):+4.0f} %, stronger in {(r[:,2]<r[:,3]).sum()}/{len(r)})')
