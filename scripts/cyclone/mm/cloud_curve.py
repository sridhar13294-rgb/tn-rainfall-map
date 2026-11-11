"""How does the diagnostic cloud scheme turn humidity into cloud, compared with ERA5? (11 Nov) On ERA5 start states (hour 0, our
levels, humidity verified within 1 %), per column: the scheme's total cover (large-scale RH cloud + convective/anvil, rad_dbg hook)
vs ERA5 total cloud cover at the same time, binned by the column's mass-weighted RH (1000-300 hPa) and by max layer RH.
Also: the same with the model state after 24 h (to see the curve the forecast lives on).  python cloud_curve.py LIB MOIST GRID STARTS"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, radcloud as R, wxscore as WS
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
MT = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(MT['days'])}
GR, KS = sys.argv[3], [int(x) for x in sys.argv[4].split(',')]
M = mm2.Model(GR, 32, 20.0, dict({'rad': 'radcloud', 'rad_every': 1, 'cmt_mf': 1.0, 'rd_si': 1.0, 'rad_dbg': 1}, **json.loads(os.environ.get('EXTRA', '{}')))); hor = M.coords.horizontal
HOURS = [int(x) for x in os.environ.get('HOURS', '0,24').split(',')]
tla = np.linspace(-90, 90, 121); TLA = np.repeat(tla[:, None], 240, 1); TW = np.cos(np.radians(TLA))
BINS = np.arange(0.2, 1.01, 0.1)
acc = {h: {'rh': [], 'mod': [], 'ls': [], 'era': [], 'w': [], 'trop': []} for h in HOURS}
for k in KS:
    t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st)
    for h in HOURS:
        if h: st, cr = mm2.integrate(M, st, cr, 24)
        aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
        T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl_ = hor.cos_lat
        u = aux.cos_lat_u[0] / cl_ / M.MPS; v = aux.cos_lat_u[1] / cl_ / M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
        crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
        M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence) * M.SEC)
        I = {k_: (np.asarray(v_, np.float64) if not isinstance(v_, dict) else v_) for k_, v_ in M._rad_in.items()}
        cl = R.clouds(I['T'], I['q'], I['p'], I['dp'], I['ps'], I['sea'].astype(bool), I['cm'].astype(bool), I['Psrc'].sum(0), I['Psrc'], I['cond'], np, I['prm'])
        cls = R.clouds(I['T'], I['q'], I['p'], I['dp'], I['ps'], I['sea'].astype(bool), None, None, None, None, np, I['prm'])
        rh = np.clip(I['q'] / np.asarray(R.qsat(I['T'], I['p'])), 0, 1.2); m3 = (I['p'] > 30000) * I['dp']
        rhc = (rh * m3).sum(0) / m3.sum(0)
        G_ = lambda X: WS.to_grid(np.asarray(X, float), M.lon, M.lat)
        j = DI[(t0 + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H')]
        A = acc[h]; A['rh'].append(G_(rhc).ravel()); A['mod'].append(G_(cl['cover']).ravel()); A['ls'].append(G_(cls['cover']).ravel())
        A['era'].append(MT['o_tcc'][j].astype(float).ravel()); A['w'].append(TW.ravel()); A['trop'].append((np.abs(TLA) <= 30).ravel())
        print(TT[k], 'h', h, flush=True)
for h, A in acc.items():
    rh, mod, ls, era, w = (np.concatenate(A[x]) for x in ('rh', 'mod', 'ls', 'era', 'w'))
    wm = lambda X, m: float((X * w)[m].sum() / w[m].sum())
    print(f'\nhour {h}: global cover scheme {wm(mod, np.ones_like(mod, bool)):.2f} (large-scale only {wm(ls, np.ones_like(ls, bool)):.2f}) vs ERA5 {wm(era, np.ones_like(era, bool)):.2f}')
    print('  column RH (1000-300 hPa) bin | share of globe | scheme cover | large-scale part | ERA5 cover')
    for a, b in zip(BINS[:-1], BINS[1:]):
        m = (rh >= a) & (rh < b)
        if m.sum() > 50: print(f'  {a:.1f}-{b:.1f} | {w[m].sum() / w.sum():5.2f} | {wm(mod, m):.2f} | {wm(ls, m):.2f} | {wm(era, m):.2f}')
if len(HOURS) < 2: sys.exit(0)
# paired per-column analysis (peer 11 Nov 18:22): the same location at hour 0 and hour 24 (same starts, same order)
r0, r1 = (np.concatenate(acc[h]['rh']) for h in (0, 24)); c0, c1 = (np.concatenate(acc[h]['mod']) for h in (0, 24))
e0, e1 = (np.concatenate(acc[h]['era']) for h in (0, 24)); w = np.concatenate(acc[0]['w'])
b0 = np.digitize(r0, BINS); b1 = np.digitize(r1, BINS); same = b0 == b1
wm = lambda X, m: float((X * w)[m].sum() / max(w[m].sum(), 1e-9))
print(f'\npaired columns: share staying in the same RH bin {w[same].sum() / w.sum():.2f}, moving up {w[b1 > b0].sum() / w.sum():.2f}, down {w[b1 < b0].sum() / w.sum():.2f}')
print(f'  same-bin columns: scheme cover {wm(c0, same):.2f} -> {wm(c1, same):.2f}; ERA5 {wm(e0, same):.2f} -> {wm(e1, same):.2f}')
print(f'  moved-up columns: scheme cover {wm(c0, b1 > b0):.2f} -> {wm(c1, b1 > b0):.2f}; ERA5 {wm(e0, b1 > b0):.2f} -> {wm(e1, b1 > b0):.2f}')
print(f'  global change explained: within-bin {wm(c1 - c0, same) * w[same].sum() / w.sum():+.3f}, by moving bins {wm(c1 - c0, ~same) * w[~same].sum() / w.sum():+.3f}')
