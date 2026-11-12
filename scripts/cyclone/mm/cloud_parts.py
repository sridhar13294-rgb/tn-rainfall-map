"""cloud_parts.py (12 Nov, Problem A in forecast): which cloud component fills the sky - large-scale RH cloud, convective towers
or anvils - at hours 0/24/48 (global cover of each component alone + total, share of columns with convection, cover by height).
Derived from moist_vs_era5.py.  Humidity / cloud drift against REAL ERA5 (11 Nov; wx_truth_moist_2020.npz): model q at 925/850/700/500 hPa, column water vapour and
total cloud cover (the radiation's own cloud incl. convective/anvil, rad_dbg hook) at hours 0, 24, 48 vs ERA5 at the same valid times;
global / tropics means (bias) per candidate.  python moist_vs_era5.py LIB MOIST_TRUTH GRID STARTS OUT_JSON   env CANDS, DT"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, radcloud as R, wxscore as WS
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
MT = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(MT['days'])}
GR, KS, OUT = sys.argv[3], [int(x) for x in sys.argv[4].split(',')], sys.argv[5]
B2 = {'rad': 'radcloud', 'rad_every': 1, 'cmt_mf': 1.0, 'rd_si': 1.0, 'rad_dbg': 1}
CANDS = json.loads(os.environ.get('CANDS', 'null')) or {'base2': {}}
tla = np.linspace(-90, 90, 121); TLA = np.repeat(tla[:, None], 240, 1); TW = np.cos(np.radians(TLA))
def tm(X, m): return float(np.nansum(X * TW * m) / np.nansum(TW * m * np.isfinite(X)))
res = {}
for nm, ex in CANDS.items():
    NL = os.environ.get('NLEV', '32'); M = mm2.Model(GR, int(NL) if NL.isdigit() else NL, float(os.environ.get('DT', 20)), dict(B2, **ex)); hor = M.coords.horizontal
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616, f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st)
        for h in (0, 24, 48):
            if h: st, cr = mm2.integrate(M, st, cr, 24)
            aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
            T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl_ = hor.cos_lat
            u = aux.cos_lat_u[0] / cl_ / M.MPS; v = aux.cos_lat_u[1] / cl_ / M.MPS; q = st.tracers['specific_humidity']; ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
            crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
            if os.environ.get('NOCLOUD'):                                                         # 12 Nov: 75 levels at T170 run out of GPU memory in the eager column call -> humidity only
                psn = np.asarray(ps, float); pn = np.asarray(M.sig, float)[:, None, None] * psn[None]; mass = np.asarray(M.dsig, float)[:, None, None] * psn[None] / 9.80616
                qn = np.asarray(q, float); fld = {'tcwv': (qn * mass).sum(0)}
            else:
                M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence) * M.SEC)
                I = {k_: (np.asarray(v_, np.float64) if not isinstance(v_, dict) else v_) for k_, v_ in M._rad_in.items()}
                cl = R.clouds(I['T'], I['q'], I['p'], I['dp'], I['ps'], I['sea'].astype(bool), I['cm'].astype(bool), I['Psrc'].sum(0), I['Psrc'], I['cond'], np, I['prm'])
                qn = np.asarray(q, float); pn = I['p']; psn = I['ps']; mass = I['dp'] / 9.80616
                fld = {'tcwv': (qn * mass).sum(0), 'tcc': np.asarray(cl['cover'])}
            if not os.environ.get('NOCLOUD'):
                Wm = np.cos(np.radians(np.asarray(M.LA))); g = lambda X: float((np.asarray(X) * Wm).sum() / Wm.sum())
                tc = lambda c: np.asarray(R.total_cover(c, np))
                pp = I['p']; cmk = I['cm'].astype(bool)
                part = dict(total=g(cl['cover']), ls=g(tc(cl['c_ls'])), tow=g(tc(cl['c_tow'])), anv=g(tc(cl['c_anv'])), conv_cols=g(cmk.any(0)),
                            low=g(tc(np.where(pp > 68000, cl['c'], 0))), mid=g(tc(np.where((pp <= 68000) & (pp > 44000), cl['c'], 0))), high=g(tc(np.where(pp <= 44000, cl['c'], 0))),
                            ls_low=g(tc(np.where(pp > 68000, cl['c_ls'], 0))), ls_mid=g(tc(np.where((pp <= 68000) & (pp > 44000), cl['c_ls'], 0))), ls_high=g(tc(np.where(pp <= 44000, cl['c_ls'], 0))))
                print('PARTS', nm, TT[k], f'h{h}', ' '.join(f'{a} {b:.3f}' for a, b in part.items()), flush=True)
                rhl = I['q'] / np.asarray(R.qsat(I['T'], pp, np)); sg = np.asarray(M.sig)
                print('LEV', f'h{h}', ' '.join(f"s{sg[i]:.3f}: rh {g(rhl[i]):.3f} c {g(cl['c_ls'][i]):.3f} T {g(I['T'][i]):.1f}" for i in range(len(sg)) if sg[i] > 0.7), flush=True)
                res.setdefault('parts_' + nm, {}).setdefault(str(h), []).append(part)
            lp = np.log(pn)
            for P in (925, 850, 700, 500):
                x = np.log(P * 100.0); i_ = np.clip((lp < x).sum(0), 1, pn.shape[0] - 1)
                a_ = np.take_along_axis(lp, i_[None] - 1, 0)[0]; b_ = np.take_along_axis(lp, i_[None], 0)[0]
                qa = np.take_along_axis(qn, i_[None] - 1, 0)[0]; qb = np.take_along_axis(qn, i_[None], 0)[0]
                fld[f'q{P}'] = np.where(psn > P * 100.0, qa + (qb - qa) * (x - a_) / (b_ - a_), np.nan)
                if P == 925 and not os.environ.get('NOCLOUD'):
                    Ta = np.take_along_axis(I['T'], i_[None] - 1, 0)[0]; Tb = np.take_along_axis(I['T'], i_[None], 0)[0]
                    fld['t925'] = np.where(psn > P * 100.0, Ta + (Tb - Ta) * (x - a_) / (b_ - a_), np.nan)
            j = DI.get((t0 + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H'))
            row = {}
            for key, X in fld.items():
                Xg = WS.to_grid(X, M.lon, M.lat)                                                        # NaN (below ground) propagates to neighbours
                Ob = MT.get('o_' + key)
                if Ob is None or j is None: continue
                Ob = Ob[j].astype(float)
                ok = np.isfinite(Xg) & np.isfinite(Ob)
                for reg, m in (('globe', ok), ('tropics', ok & (np.abs(TLA) <= 30))):
                    row[f'{key}_{reg}'] = (tm(Xg, m), tm(Ob, m))
            res.setdefault(nm, {}).setdefault(str(h), []).append(row)
            print(nm, TT[k], f'h{h}', ' '.join(f"{kk} {vv[0]:.4g}/{vv[1]:.4g}" for kk, vv in row.items() if kk.endswith('globe')), flush=True)
        json.dump(res, open(OUT, 'w'))
