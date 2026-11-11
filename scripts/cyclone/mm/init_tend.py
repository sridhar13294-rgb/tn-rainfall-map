"""First-hours (initial) tendency diagnosis (10 Nov, 'how to find the WHY'; Klinker & Sardeshmukh 1992, Rodwell & Palmer 2007).
Start from ERA5 (init + DFI as in every forecast). Over many starts the real atmosphere has no large systematic tendency, so a
systematic model tendency in the first hours, at the place where an error later appears, points at the process making it.
Per step, at the sigma level nearest 0.85 (and 0.5), the model's u/v/T change is split into:
  TOTAL     (state after one real model step - before) / dt
  PHYS      the column-physics tendencies at the state (exact): u/v by BL, CMT, rest (gravity-wave drag etc.); T by radiation,
            BL, deep, shallow, large-scale condensation, re-evaporation
  PGF       pressure-gradient force on sigma levels, -grad(Phi) - R Tv grad(ln ps)  (Phi by hydrostatic sum from the surface)
  COR       Coriolis f v (u) / -f u (v)
  REST      TOTAL - PHYS - PGF - COR = transport (semi-Lagrangian advection, metric terms), diffusion, coupling, numerics
Time means over windows 0-6 h and 6-24 h; mean over starts; box means; maps saved (.npz). Real reference: ERA5 day-0 -> day-1
change of u850/v850 (truth file) over the same starts.  python init_tend.py LIB TRUTH GRID N_STARTS OUT_NPZ"""
import sys, os, json, datetime as dt, numpy as np, jax, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit
from dinosaur import primitive_equations
G, RD, A = 9.80616, 287.04, 6.37122e6
LIB, TRU, GR, N, OUT = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = np.load(TRU); DI = {str(d): i for i, d in enumerate(TR['days'])}; tla = np.asarray(Z['lats'], float); tlo = np.asarray(Z['lons'], float)
EXTRA = json.loads(os.environ.get('EXTRA', '{}'))   # candidate settings on top of base2 (10 Nov)
NLEV = os.environ.get('NLEV', '32'); NLEV = int(NLEV) if NLEV.isdigit() else NLEV   # 11 Nov: 'tp75' allowed
M = mm2.Model(GR, NLEV, None, dict({'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1, 'rd_si': 1}, **EXTRA))
hor = M.coords.horizontal; sig = np.asarray(M.sig, float); sigb = np.asarray(M.sigb, float)
K85, K50 = int(np.argmin(np.abs(sig - 0.85))), int(np.argmin(np.abs(sig - 0.5))); K20 = int(np.argmin(np.abs(sig - 0.2)))   # 11 Nov: + 200 hPa (jet)
LA, LO = np.asarray(M.LA, float), np.asarray(M.LO, float); lat_r = np.radians(np.asarray(M.lat, float)); lon_r = np.radians(np.asarray(M.lon, float))
cosl = np.cos(np.radians(LA)); f = 2 * 7.292e-5 * np.sin(np.radians(LA))
def fields(S):
    aux = primitive_equations.compute_diagnostic_state_sigma(S.replace(tracers={}), M.coords)
    T = np.asarray((aux.temperature_variation + M.ref_t[:, None, None]) / M.K, float); cl = np.asarray(hor.cos_lat)
    u = np.asarray(aux.cos_lat_u[0] / cl / M.MPS, float); v = np.asarray(aux.cos_lat_u[1] / cl / M.MPS, float)
    q = np.asarray(S.tracers['specific_humidity'], float); ps = np.asarray(jnp.exp(hor.to_nodal(S.log_surface_pressure))[0] / M.PA, float)
    return T, q, u, v, ps
def ddlon(X): return np.gradient(X, lon_r, axis=-2)                       # nodal arrays are [.., lon, lat]
def ddlat(X): return np.gradient(X, lat_r, axis=-1)
def pgf(T, q, ps, k):
    Tv = T * (1 + 0.608 * q); phis = G * np.asarray(M.zs, float)
    # Phi at full level k: surface + layers below k (interfaces) + half layer
    lnb = np.log(np.maximum(sigb, 1e-6)); ln_c = np.log(sig)
    phi = phis.copy()
    for j in range(len(sig) - 1, k, -1): phi = phi + RD * Tv[j] * (lnb[j + 1] - lnb[j])
    phi = phi + RD * Tv[k] * (lnb[k + 1] - ln_c[k])
    lnps = np.log(ps)
    pu = -(ddlon(phi) + RD * Tv[k] * ddlon(lnps)) / (A * cosl)
    pv = -(ddlat(phi) + RD * Tv[k] * ddlat(lnps)) / A
    return pu, pv
WIN = {'0-6h': (0, 6), '6-24h': (6, 24)}
starts = [k for k, t in enumerate(TT) if t[5:7] in ('10', '11') and t.endswith('T00')][:N]
acc = {}                                                               # (window, name) -> list of per-start mean maps
def add(w, name, X): acc.setdefault((w, name), []).append(X)
obs = {'u': [], 'v': [], 'T': []}
for k in starts:
    t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0); st = M.dfi(st); dth = M.dt_s / 3600.0; nstep = int(round(24 / dth)); sums = {}
    for n in range(nstep):
        hr = n * dth; w = '0-6h' if hr < 6 else '6-24h'
        crx = dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)); M._carry = crx
        T, q, u, v, ps = fields(st)
        tend, diag = M.column(*(jnp.asarray(x, jnp.float32) for x in (T, q, u, v, ps)), crx, want_diag=True, div=hor.to_nodal(st.divergence) * M.SEC)
        st1, cr1 = mm2.integrate(M, st, cr, dth); T1, q1, u1, v1, ps1 = fields(st1)
        for kk, lv in ((K85, '850'), (K50, '500'), (K20, '200')):
            pu, pv = pgf(T, q, ps, kk)
            tu, tv, tT = (u1[kk] - u[kk]) / M.dt_s, (v1[kk] - v[kk]) / M.dt_s, (T1[kk] - T[kk]) / M.dt_s
            phu, phv = np.asarray(tend['u'][kk], float), np.asarray(tend['v'][kk], float)
            cu, cv = f * v[kk], -f * u[kk]
            parts = {f'u{lv}_TOTAL': tu, f'u{lv}_PHYS': phu, f'u{lv}_PGF': pu, f'u{lv}_COR': cu, f'u{lv}_REST': tu - phu - pu - cu,
                     f'u{lv}_PGF+COR': pu + cu, f'v{lv}_TOTAL': tv, f'v{lv}_PHYS': phv, f'v{lv}_PGF+COR': pv + cv, f'v{lv}_REST': tv - phv - pv - cv,
                     f'T{lv}_TOTAL': tT, f'T{lv}_PHYS': np.asarray(tend['T'][kk], float), f'T{lv}_DYN': tT - np.asarray(tend['T'][kk], float)}
            for pk in ('u_bl', 'u_cmt'):
                if pk in diag: parts[f'u{lv}_{pk}'] = np.asarray(diag[pk][kk], float)
            for pk in ('rad_app', 'h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap'):
                if pk in diag: parts[f'T{lv}_{pk}'] = np.asarray(diag[pk][kk], float)
            for nm, X in parts.items():
                s_ = sums.setdefault((w, nm), [0.0, 0]); s_[0] = s_[0] + X; s_[1] += 1
        TRm = np.abs(LA) <= 30; Wt = cosl * TRm; Wg = cosl
        for pk in ('rad_app', 'h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap', 'q_bl', 'q_deep', 'q_shal', 'q_lsc', 'q_evap'):
            if pk in diag:
                X = np.asarray(diag[pk], float)
                for rn, Ww in (('trop', Wt), ('globe', Wg)):
                    s_ = sums.setdefault((w, f'prof_{rn}_{pk}'), [0.0, 0]); s_[0] = s_[0] + (X * Ww[None]).sum((1, 2)) / Ww.sum(); s_[1] += 1
        for rn, Ww in (('trop', Wt), ('globe', Wg)):
            for nm_, X in (('TOTAL', (T1 - T) / M.dt_s), ('qTOTAL', (q1 - q) / M.dt_s), ('p', sig[:, None, None] * ps[None])):
                s_ = sums.setdefault((w, f'prof_{rn}_{nm_}'), [0.0, 0]); s_[0] = s_[0] + (X * Ww[None]).sum((1, 2)) / Ww.sum(); s_[1] += 1
        st, cr = st1, cr1
    for (w, nm), (S_, c_) in sums.items(): add(w, nm, S_ / c_)
    d0 = DI[TT[k]]; d1 = DI[(t0 + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H')]
    obs['u'].append((TR['o_u850'][d1] - TR['o_u850'][d0]) / 86400.0); obs['v'].append((TR['o_v850'][d1] - TR['o_v850'][d0]) / 86400.0); obs['T'].append((TR['o_t850'][d1] - TR['o_t850'][d0]) / 86400.0)
    print(TT[k], 'done', flush=True)
BOX = {'Indochina/S China Sea 12-24N 100-120E': (12, 24, 100, 120), 'Bay of Bengal 10-20N 82-95E': (10, 20, 82, 95),
       'Aleutian 40-65N 160-220E': (40, 65, 160, 220), 'S Atlantic trades 5-20S 330-360E': (-20, -5, 330, 360), 'globe': (-90, 90, 0, 360)}
def bm(X, a, b, c, d, la_, lo_, latfirst=False):
    lo_ = lo_ % 360; m = (la_ >= a) & (la_ <= b) & (((lo_ >= c) & (lo_ <= d)) if c <= d else ((lo_ >= c) | (lo_ <= d)))
    w = np.cos(np.radians(la_)); return float((X * w)[m].sum() / w[m].sum())
TLA, TLO = np.meshgrid(tla, tlo, indexing='ij')
print(f'\nMEAN of {len(starts)} starts, {GR}, sigma {sig[K85]:.3f} (~850 hPa). u/v tendencies in m/s per DAY (negative u = easterly push)')
names = ['TOTAL', 'PHYS', 'u_bl', 'u_cmt', 'PGF', 'COR', 'PGF+COR', 'REST']
for bx, (a, b, c, d) in BOX.items():
    print(f'\n{bx}:  ERA5 real change day0->1: u850 {bm(np.mean(obs["u"], 0) * 86400, a, b, c, d, TLA, TLO):+.2f} m/s/day, T850 {bm(np.mean(obs["T"], 0) * 86400, a, b, c, d, TLA, TLO):+.2f} K/day')
    for w in WIN:
        su = np.array([bm(X * 86400, a, b, c, d, LA, LO) for X in acc[(w, 'u850_TOTAL')]])
        print(f'  {w:6s} per-start u850 TOTAL: ' + ' '.join(f'{x:+5.1f}' for x in su))
    for w in WIN:
        print(f'  {w:6s} u: ' + ' '.join(f'{n} {bm(np.mean(acc[(w, "u850_" + n)], 0) * 86400, a, b, c, d, LA, LO):+6.2f}' for n in names if (w, 'u850_' + n) in acc))
        print(f'  {w:6s} T850 K/day: ' + ' '.join(f'{n} {bm(np.mean(acc[(w, "T850_" + n)], 0) * 86400, a, b, c, d, LA, LO):+5.2f}' for n in ('TOTAL', 'PHYS', 'DYN', 'rad_app', 'h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap') if (w, 'T850_' + n) in acc))
np.savez_compressed(OUT, lat=np.asarray(M.lat), lon=np.asarray(M.lon), starts=np.array([TT[k] for k in starts]),
                    **{f'{w}__{nm}': np.mean(v, 0).astype(np.float32) for (w, nm), v in acc.items()},
                    **{f'per_start__{w}__{nm}': np.array(v, np.float16) for (w, nm), v in acc.items() if nm.startswith(('u850', 'T850', 'u200', 'T200'))},
                    obs_du850=np.mean(obs['u'], 0).astype(np.float32), obs_dv850=np.mean(obs['v'], 0).astype(np.float32), obs_dT850=np.mean(obs['T'], 0).astype(np.float32))
PROF = {f'{w}__{nm}': np.mean(v, 0).tolist() for (w, nm), v in acc.items() if nm.startswith('prof_')}
json.dump(PROF, open(OUT.replace('.npz', '_prof.json'), 'w'))
print('saved', OUT)
