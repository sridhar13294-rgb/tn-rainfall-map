"""P1 offline (4 Nov): which process warms 850-925 hPa in the first day? Tropical (|lat|<20) mean heating by process (K/day)
on sigma levels at +3, +12, +24 h (control), plus the total physics, ocean vs land. python heat_prof.py LIB OUT START GRID"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
from dinosaur import spherical_harmonic
LIB, OUT, KEY, GR = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]; SET = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
M = mm2.Model(GR, 32, None, dict({'rad': 'radcloud', 'rad_every': 2}, **SET))
k = TT.index(KEY); t0 = dt.datetime.strptime(KEY, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); st = M.dfi(st); hor = M.coords.horizontal; LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); land = np.asarray(M.land) > 0.5
trop = np.abs(LA) < 20; sig = np.asarray(M.sig); res = dict(sig=sig.round(3).tolist()); h0 = 0
for hh in (3, 12, 24):
    st, cr = mm2.integrate(M, st, cr, hh - h0); h0 = hh
    T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
    ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
    tn, d = M.column(T, q, u / M.MPS, v / M.MPS, ps, dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
    P = {p_: np.asarray(d[p_]) for p_ in ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap', 'rad_app')}; P['total'] = np.asarray(tn['T'])
    out = {}
    for nm, m in (('ocean', trop & ~land), ('land', trop & land)):
        w = W * m; out[nm] = {p_: ((x * w).sum((1, 2)) / w.sum() * 86400).round(2).tolist() for p_, x in P.items()}
    res[f'h{hh}'] = out
    i850 = int(np.argmin(np.abs(sig - 0.85))); i925 = int(np.argmin(np.abs(sig - 0.925)))
    for nm in ('ocean', 'land'):
        print(f'+{hh:2d}h {nm:5s} K/day at sig {sig[i850]:.2f} / {sig[i925]:.2f}:', {p_: (v_[i850], v_[i925]) for p_, v_ in out[nm].items()}, flush=True)
json.dump(res, open(OUT, 'w'))
