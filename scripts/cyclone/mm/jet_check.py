"""Asian subtropical jet in the first day (12 Nov; 200-hPa budget: the jet loses 5-8 m/s/day in the first 6 h from 'transport/numerics',
physics zero). Jet peak = max over 20-50 N of the 60-140 E mean u200. Measured: ERA5 start (our levels, before DFI), after DFI, and day 1
for variants (default, no DFI, weaker horizontal diffusion), vs ERA5 day 1.  python jet_check.py LIB TRUTH GRID STARTS   env VARIANTS (json)"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
TR = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(TR['days'])}
GR, KS = sys.argv[3], [int(x) for x in sys.argv[4].split(',')]
B2 = {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0}
VARS = json.loads(os.environ.get('VARIANTS', 'null')) or {'default': {}, 'no DFI': {'dfi_off': 1}, 'diffusion x4 weaker': {'diff_x': 4.0}}
lat = np.linspace(-90, 90, 121); lon = np.arange(240) * 1.5; sec = (lon >= 60) & (lon <= 140); band = (lat >= 20) & (lat <= 50)
def jet(u):                                                       # u [121, 240] -> (peak speed, latitude)
    prof = u[:, sec].mean(1); i = np.argmax(np.where(band, prof, -99)); return float(prof[i]), float(lat[i])
res = {}
for nm, ex in VARS.items():
    ex = dict(ex); nl = ex.pop('NL', 32)
    M = mm2.Model(GR, nl, float(os.environ.get('DT', 20)), dict(B2, **ex))
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0)
        o0 = M.run_wx(st, cr, 0, 24) if False else None
        st_d = M.dfi(st)
        out_raw = M.run_wx(st, cr, 0, 24); out_dfi = M.run_wx(st_d, cr, 24, 24)
        u_raw = WS.to_grid(out_raw['u200'][0], M.lon, M.lat); u_dfi = WS.to_grid(out_dfi['u200'][0], M.lon, M.lat); u_d1 = WS.to_grid(out_dfi['u200'][1], M.lon, M.lat)
        j1 = DI[(t0 + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H')]
        r = dict(raw=jet(u_raw), dfi=jet(u_dfi), d1=jet(u_d1), era_d1=jet(TR['o_u200'][j1]))
        res.setdefault(nm, []).append(r)
        print(nm, TT[k], {k_: tuple(round(x, 1) for x in v) for k_, v in r.items()}, flush=True)
print('\nmean jet peak (m/s) over starts: ERA5 start on our levels (before DFI) -> after DFI -> model day 1 | ERA5 day 1')
for nm, rs in res.items():
    m = lambda key: np.mean([r[key][0] for r in rs])
    print(f'  {nm:22s} {m("raw"):5.1f} -> {m("dfi"):5.1f} -> {m("d1"):5.1f} | ERA5 {m("era_d1"):5.1f}  (day-1 error {m("d1") - m("era_d1"):+.1f}, from DFI {m("dfi") - m("raw"):+.1f})')
