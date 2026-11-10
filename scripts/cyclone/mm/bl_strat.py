# Daytime boundary-layer stratification: ERA5 start (00 UTC = US afternoon) vs 24-h forecasts valid 00 UTC next day, same columns
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/mm'); sys.path.insert(0, '/tmp/claude-0/disp/scripts/cyclone/analysis')
import mm2, landinit
from dinosaur import primitive_equations
Z = dict(np.load('/kaggle/working/libm_wx2020_fields.npz')); TT=[str(t) for t in Z['times']]; V3=[str(v) for v in Z['v3']]; V2=[str(v) for v in Z['v2']]
GR = os.environ.get('GR', 'T42'); KS = [int(x) for x in os.environ.get('KS', '36').split(',')]
B2 = {'rad':'radcloud','rad_every':2,"cmt_mf":1.0,"rd_si":1.0}
IFS = dict(B2, shallow="mf", sh_trig=1.0, sh_dmax=20000.0, sh_eps=3.5e-3, sh_det=1.0, sh_clos=1.0)
CANDS = {'base2': B2, 'ifs_sh': IFS, 'ifs_sh+edmf': dict(IFS, edmf=1.0)}
BOX = {'E US 30-42N 265-285E (afternoon)': (30, 42, 265, 285), 'Amazon 15S-0 290-315E (afternoon)': (-15, 0, 290, 315)}
def prof(M, st):
    hor = M.coords.horizontal; aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
    T = np.asarray((aux.temperature_variation + M.ref_t[:, None, None]) / M.K, float); ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA, float)
    p = np.asarray(M.sig, float)[:, None, None] * ps[None]; th = T * (1e5 / p) ** 0.2857
    out = {}
    for P in (97500., 92500., 85000., 70000.):
        lp = np.log(p); x = np.log(P); i = np.clip((lp < x).sum(0), 1, len(M.sig) - 1)   # p increases downward: levels above P are lp<x
        a = np.take_along_axis(lp, i[None] - 1, 0)[0]; b = np.take_along_axis(lp, i[None], 0)[0]
        ta = np.take_along_axis(th, i[None] - 1, 0)[0]; tb = np.take_along_axis(th, i[None], 0)[0]
        out[P] = ta + (tb - ta) * (x - a) / (b - a)
    return out, ps
res = {}
for nm, setx in CANDS.items():
    M = mm2.Model(GR, 32, None, setx)
    for k in KS:
        t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')]/9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); P0, ps0 = prof(M, st)
        for h in (24, 48):
            st, cr = mm2.integrate(M, st, cr, 24); P1, _ = prof(M, st)
            LA, LO = np.asarray(M.LA), np.asarray(M.LO) % 360; land = np.asarray(M.land); W = np.cos(np.radians(LA))
            for bx, (a, b, c, d) in BOX.items():
                m = (LA >= a) & (LA <= b) & (LO >= c) & (LO <= d) & land & (ps0 > 98000)
                f = lambda X: float((X * W)[m].sum() / W[m].sum())
                for lab, PP in (('ERA5 h0', P0), (f'{nm} h{h}', P1)):
                    res.setdefault((bx, lab), []).append((f(PP[92500.] - PP[97500.]), f(PP[85000.] - PP[92500.]), f(PP[70000.] - PP[85000.]), f(PP[85000.])))
for (bx, lab), v in res.items():
    v = np.mean(v, 0); print(f'{bx:36s} {lab:18s} dtheta 975->925 {v[0]:+5.2f} K, 925->850 {v[1]:+5.2f} K, 850->700 {v[2]:+5.2f} K | theta850 {v[3]:.2f}')
