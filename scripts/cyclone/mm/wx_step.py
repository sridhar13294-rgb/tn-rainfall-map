"""One-step coupling check: from the same state, take one model step with physics and one without; the difference in
mass-weighted mean temperature (as W/m2) is the physics heating the model actually receives. Compare with the physics
heating computed by column() on that state (rad fresh). Done at hour 0 and after 24 h, globe and tropics; also per
sigma level (tropics) to see where any gap sits.
python wx_step.py LIBM_WX_NPZ OUT_JSON [SETTINGS_JSON]"""
import sys, os, json, datetime as dt, numpy as np, jax, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
LIB, OUT = sys.argv[1], sys.argv[2]; SET = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
BASE = dict(rad='radcloud', rad_every=1, **SET)
MF = mm2.Model('T85', 32, None, BASE); M0 = mm2.Model('T85', 32, None, dict(BASE, phys_off=True))
key = TT[0]; t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = 0; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}; res = {}
args = (f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')])
st, cr = MF.init(*args, when=t0, **landinit.land_kwargs(Z['f2'][k], V2)); MF.build(t0); st = MF.dfi(st)
st0, cr0 = M0.init(*args, when=t0, **landinit.land_kwargs(Z['f2'][k], V2)); M0.build(t0)
hor = MF.coords.horizontal; LA = np.asarray(MF.LA); W = np.cos(np.radians(LA)); trop = np.abs(LA) < 20
def Tnod(s): return np.asarray((hor.to_nodal(s.temperature_variation) + MF.ref_t[:, None, None]) / MF.K)
def psn(s): return np.asarray(jnp.exp(hor.to_nodal(s.log_surface_pressure))[0] / MF.PA)
def one(M, s, c):
    M._carry = dict(c, doy0=jnp.float32(MF.doy0), utc0=jnp.float32(MF.utc0)); return jax.jit(M.step)(s)
for lab, hrs in (('h0', 0), ('h24', 24)):
    if hrs: st, cr = mm2.integrate(MF, st, cr, hrs)
    c = dict(cr, doy0=jnp.float32(MF.doy0), utc0=jnp.float32(MF.utc0))
    T = Tnod(st); ps = psn(st); m = np.asarray(MF.dsig)[:, None, None] * ps[None] / 9.81
    u, v = mm2.spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
    tend, d = MF.column(jnp.asarray(T), st.tracers['specific_humidity'], u / MF.MPS, v / MF.MPS, jnp.asarray(ps), c, rad_fresh=True, div=hor.to_nodal(st.divergence) * MF.SEC)
    comp = np.asarray(tend['T']) * 1004.6 * m
    s1 = one(MF, st, cr); s0 = one(M0, st, cr)
    real = (Tnod(s1) - Tnod(s0)) / MF.dt_s * 1004.6 * m
    out = {}
    for name, mask in (('globe', np.ones_like(trop)), ('tropics', trop)):
        w = W * mask; f = lambda X: float((X.sum(0) * w).sum() / w.sum())
        out[name] = dict(computed=round(f(comp), 1), realised=round(f(real), 1))
    w = W * trop; out['tropics_by_level_K_day'] = dict(sig=np.asarray(MF.sig).round(3).tolist(),
        computed=[round(float((np.asarray(tend['T'])[i] * w).sum() / w.sum() * 86400), 2) for i in range(len(MF.sig))],
        realised=[round(float(((Tnod(s1) - Tnod(s0))[i] / MF.dt_s * w).sum() / w.sum() * 86400), 2) for i in range(len(MF.sig))])
    res[lab] = out; print(lab, json.dumps({k_: out[k_] for k_ in ('globe', 'tropics')}), flush=True)
    print(lab, 'by level computed', out['tropics_by_level_K_day']['computed'], flush=True)
    print(lab, 'by level realised', out['tropics_by_level_K_day']['realised'], flush=True)
json.dump(res, open(OUT, 'w'))
