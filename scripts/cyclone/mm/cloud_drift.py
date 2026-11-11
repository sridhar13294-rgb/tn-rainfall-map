"""Cloud drift (11 Nov, P1/P4/P5 common-cause test): the model's large-scale RH cloud (radcloud.clouds without the convective part) and RH by
pressure band, on the ERA5 start (hour 0, after DFI) and after 24 / 48 h, per candidate. If the cloud excess (energy audit:
cover 0.84 vs ~0.67) is already there at hour 0 the cloud SCHEME is the cause; if it grows with RH it is a moistening PROCESS.
python cloud_drift.py LIB GRID STARTS(comma idx) OUT_JSON   env CANDS (json {name: settings}), NLEV"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit, radcloud
from dinosaur import primitive_equations
LIB, GR, KS, OUT = sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(',')], sys.argv[4]
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
B2 = {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0}
IFS = dict(B2, shallow='mf', sh_trig=1.0, sh_dmax=20000.0, sh_eps=3.5e-3, sh_det=1.0, sh_clos=1.0)
CANDS = json.loads(os.environ.get('CANDS', 'null')) or {'base2': B2, 'ifs_sh': IFS}
NLEV = os.environ.get('NLEV', '32'); NLEV = int(NLEV) if NLEV.isdigit() else NLEV
BINS = [(85000, 110000, '>850'), (70000, 85000, '850-700'), (50000, 70000, '700-500'), (30000, 50000, '500-300'), (0, 30000, '<300')]
res = {}
for nm, setx in CANDS.items():
    M = mm2.Model(GR, NLEV, float(os.environ['DT']) if 'DT' in os.environ else None, setx); hor = M.coords.horizontal; W = np.cos(np.radians(np.asarray(M.LA)))
    TROP = np.abs(np.asarray(M.LA)) <= 30
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st)
        for h in (0, 24, 48):
            if h: st, cr = mm2.integrate(M, st, cr, 24)
            aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
            T = (aux.temperature_variation + M.ref_t[:, None, None]) / M.K; cl = hor.cos_lat
            u = aux.cos_lat_u[0] / cl / M.MPS; v = aux.cos_lat_u[1] / cl / M.MPS; q = st.tracers['specific_humidity']
            ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA
            Tn = np.asarray(T, float); qn = np.asarray(q, float); psn = np.asarray(ps, float)
            p = np.asarray(M.sig, float)[:, None, None] * psn[None]; rh = qn / np.asarray(radcloud.qsat(Tn, p))
            dpn = np.asarray(M.dsig, float)[:, None, None] * psn[None]
            c = radcloud.clouds(Tn, qn, p, dpn, psn, np.asarray(cr['sst']) > 0)['c']   # large-scale (RH) cloud only: the low deck is large-scale
            tot = np.asarray(radcloud.total_cover(c)); low = np.asarray(radcloud.total_cover(np.where(p > 68000, c, 0.0)))
            r = {}
            for reg, m in (('globe', np.ones_like(TROP)), ('tropics', TROP)):
                g = lambda X: float((X * W)[m].sum() / W[m].sum())
                r[reg] = dict(cover=g(tot), low_cover=g(low))
                for a, b, lab in BINS:
                    sel = (p >= a) & (p < b)
                    wsum = (sel * W[None] * m[None]).sum()
                    r[reg]['c ' + lab] = float((c * sel * W[None] * m[None]).sum() / wsum); r[reg]['rh ' + lab] = float((rh * sel * W[None] * m[None]).sum() / wsum); r[reg]['q ' + lab] = 1000 * float((qn * sel * W[None] * m[None]).sum() / wsum); r[reg]['T ' + lab] = float((Tn * sel * W[None] * m[None]).sum() / wsum)
            res.setdefault(nm, {}).setdefault(str(h), []).append(r)
            print(nm, TT[k], f'h{h}', 'globe cover %.3f low %.3f' % (r['globe']['cover'], r['globe']['low_cover']), ' '.join(f"c{lab} {r['globe']['c ' + lab]:.3f}/rh {r['globe']['rh ' + lab]:.2f}" for _, _, lab in BINS), flush=True)
        json.dump(res, open(OUT, 'w'))
