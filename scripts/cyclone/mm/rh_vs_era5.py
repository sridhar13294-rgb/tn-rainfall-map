"""A (12 Nov): model relative humidity by level vs ERA5 relative humidity (rh_truth_2020.npz, daily means of days 0-2; IFS
mixed-phase saturation, which the model's RH here also uses), and T850/T700. Splits the forecast cloud excess into 'RH too high'
vs 'cloud scheme maps RH to too much cloud': the RH-cloud fraction the scheme gives for ERA5's RH vs for the model's RH at the same
level.  python rh_vs_era5.py LIB RH_TRUTH GRID STARTS   env CANDS, DT"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, radcloud as R, wxscore as WS
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
FT = dict(np.load(sys.argv[2])); FD = {str(d): i for i, d in enumerate(FT['days'])}
GR, KS = sys.argv[3], [int(x) for x in sys.argv[4].split(',')]
B2 = {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0}
CANDS = json.loads(os.environ.get('CANDS', 'null')) or {'base2': {}}
tla = np.linspace(-90, 90, 121); TLA = np.repeat(tla[:, None], 240, 1); TW = np.cos(np.radians(TLA))
def qs_mix(T, p):
    es_w = 611.21 * np.exp(17.502 * (T - 273.16) / (T - 32.19)); es_i = 611.21 * np.exp(22.587 * (T - 273.16) / (T + 0.7))
    a = np.clip((T - 250.16) / 23.0, 0, 1) ** 2; es = a * es_w + (1 - a) * es_i; return 0.622 * es / np.maximum(p - 0.378 * es, 1.0)
P_ = R.DEFAULTS
def c_of(rh, sig):
    rhc = P_['rhc_up'] + (P_['rhc_low'] - P_['rhc_up']) * np.exp(1.0 - np.maximum(sig, 0.05) ** (-P_['rhc_n']))
    return 1.0 - np.sqrt(np.clip((1.0 - np.clip(rh, 0, 1)) / (1.0 - rhc), 0.0, 1.0))
for nm, ex in CANDS.items():
    M = mm2.Model(GR, 32, float(os.environ.get('DT', 20)), dict(B2, **ex)); hor = M.coords.horizontal; acc = {}
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); i = FD[TT[k]]
        for d in (0, 1, 2):
            if d: st, cr = mm2.integrate(M, st, cr, 24)
            aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
            T = np.asarray((aux.temperature_variation + M.ref_t[:, None, None]) / M.K, float); q = np.asarray(st.tracers['specific_humidity'], float)
            ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA, float); p = np.asarray(M.sig, float)[:, None, None] * ps[None]
            rh = q / qs_mix(T, p); lp = np.log(p)
            for P in (925, 850, 700, 500):
                x = np.log(P * 100.0); j_ = np.clip((lp < x).sum(0), 1, len(p) - 1)
                g2 = lambda X: np.take_along_axis(X, j_[None] - 1, 0)[0], lambda X: np.take_along_axis(X, j_[None], 0)[0]
                w = (x - g2[0](lp)) / (g2[1](lp) - g2[0](lp)); itp = lambda X: g2[0](X) + w * (g2[1](X) - g2[0](X))
                fld = {f'rh{P}': np.where(ps > P * 100.0, itp(rh), np.nan)}
                if P in (850, 700): fld[f't{P}'] = np.where(ps > P * 100.0, itp(T), np.nan)
                for key, X in fld.items():
                    Xg = WS.to_grid(X, M.lon, M.lat); Ob = FT['o_' + key][i, d].astype(float)
                    if key.startswith('rh') and np.nanmax(Ob) > 5: Ob = Ob / 100.0
                    land = WS.to_grid(np.asarray(M.land, float), M.lon, M.lat) > 0.5
                    for reg, m in (('globe', np.ones_like(land)), ('ocean 40S-40N', (~land) & (np.abs(TLA) <= 40)), ('poleward 40', np.abs(TLA) > 40)):
                        ok = m & np.isfinite(Xg) & np.isfinite(Ob); gg = lambda Y: float((np.where(ok, Y, 0.0) * TW).sum() / (TW * ok).sum())
                        acc.setdefault((key, reg, d), []).append((gg(Xg), gg(Ob)))
                        if key.startswith('rh'):
                            sg = P / 1013.0
                            acc.setdefault(('cRH' + key[2:], reg, d), []).append((gg(c_of(Xg, sg)), gg(c_of(Ob, sg))))
        print(nm, TT[k], 'done', flush=True)
    print(f'\n{nm}: model / ERA5 (day d; ERA5 = daily mean; cRHxxx = the scheme RH-cloud fraction at that level from model RH / from ERA5 RH)')
    for (a, reg, d), v in sorted(acc.items()):
        m_, o_ = np.mean(v, 0); print(f'  {a:7s} {reg:14s} d{d}  {m_:8.3f} / {o_:8.3f}   diff {m_ - o_:+7.3f}')
