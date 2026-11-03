"""Trace the 75-level + F2 blow-up (P2): run one start step by step and report, per physics process, the first
non-finite or extreme tendency (level, column count, max |rate|), plus state checks after init, DFI and each step.
python trace75.py LIBM_WX_NPZ SETTINGS_JSON NSTEPS   (SETTINGS like {"layers": "tp75", "pbl_tm": 1.0, "sh_mflux": 0.03})"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
from dinosaur import spherical_harmonic
LIB, VS, NSTEP = sys.argv[1], json.loads(sys.argv[2]), int(sys.argv[3]); OUTJ = sys.argv[4] if len(sys.argv) > 4 else None; SUM = []   # OUTJ: full per-step summary (logs are cut to 30 kB)
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
VS = dict(VS); NL = VS.pop('layers', 32); GR = VS.pop('grid', 'T170')
M = mm2.Model(GR, NL, None, dict({'rad': 'radcloud', 'rad_every': 2}, **VS))
key = os.environ.get('TRACE_START', TT[0]); k = TT.index(key); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
hor = M.coords.horizontal; sig = np.asarray(M.sig)
def state(s):
    T = np.asarray((hor.to_nodal(s.temperature_variation) + M.ref_t[:, None, None]) / M.K); q = np.asarray(s.tracers['specific_humidity'])
    ps = np.asarray(jnp.exp(hor.to_nodal(s.log_surface_pressure))[0] / M.PA); u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, s.vorticity, s.divergence)
    return T, q, ps, u, v
def check(tag, s, c):
    T, q, ps, u, v = state(s)
    bad = {n: int((~np.isfinite(np.asarray(x))).sum()) for n, x in (('T', T), ('q', q), ('ps', ps), ('u', u), ('v', v))}
    print(f'[{tag}] nonfinite {bad} | T {np.nanmin(T):.1f}..{np.nanmax(T):.1f} q max {np.nanmax(q)*1e3:.1f} g/kg min {np.nanmin(q)*1e3:.3f} | ps {np.nanmin(ps)/100:.0f}..{np.nanmax(ps)/100:.0f}', flush=True)
    rec = dict(tag=tag, nonfinite=bad, qmin_gkg=float(np.nanmin(q) * 1e3), Tmin=float(np.nanmin(T)), Tmax=float(np.nanmax(T))); SUM.append(rec)
    if OUTJ: json.dump(SUM, open(OUTJ, 'w'))
    if any(bad.values()): return False
    tn, dd = M.column(jnp.asarray(T), jnp.asarray(q), u / M.MPS, v / M.MPS, jnp.asarray(ps), dict(c, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)),
                      rad_fresh=True, div=hor.to_nodal(s.divergence) * M.SEC)
    rows = dict(tot_T=tn['T'], tot_q=tn['q'], **{kk: dd[kk] for kk in ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap') if kk in dd})
    if 'rad' in dd: rows['rad'] = dd['rad']['heating']
    for n, x in rows.items():
        x = np.asarray(x); nf = ~np.isfinite(x); a = np.where(nf, 0, np.abs(x)) * (86400 if n != 'tot_q' else 86400e3)
        kmax = np.unravel_index(np.argmax(a), a.shape)
        lev_nf = sorted(set(np.where(nf)[0].tolist()))[:5]
        rec[n] = dict(maxrate=float(a.max()), level=int(kmax[0]), sigma=float(sig[kmax[0]]), cols200=int((a.max(0) > 200).sum()), lon=float(np.asarray(M.lon)[kmax[1]]), lat=float(np.asarray(M.lat)[kmax[2]]))
        print(f'   {n:7s} nonfinite {int(nf.sum()):7d} (levels {lev_nf}) | max |rate| {a.max():9.1f} at level {kmax[0]} (sigma {sig[kmax[0]]:.3f}) | columns >200/day {int((a.max(0) > 200).sum())}', flush=True)
    if OUTJ: json.dump(SUM, open(OUTJ, 'w'))
    return True
print('settings', VS, 'layers', NL, 'levels', len(sig), 'dt_s', M.dt_s, 'lowest sigmas', sig[-4:].round(4).tolist(), flush=True)
M.build(t0)                                              # sets doy0/utc0 (needed by the column call)
ok = check('init', st, cr)
st = M.dfi(st); ok = check('after DFI', st, cr) and ok
for n in range(1, NSTEP + 1):
    if not ok: break
    st, cr = mm2.integrate(M, st, cr, M.dt_s / 3600.0)
    ok = check(f'step {n}', st, cr)
