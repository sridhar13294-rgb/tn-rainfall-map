"""Storm-following budget (P3: why do our storms fill and not intensify?). For chosen past storms, run 72 h and every 3 h
record around the model storm centre (lowest surface pressure reduced to sea level, searched within 350 km of the previous
centre): central pressure; surface enthalpy flux (sensible + latent) within 100 km and 300 km; heating by process
(radiation, boundary layer, deep convection, shallow mixing, grid-scale condensation, rain evaporation) by level within
100 km and in the 100-300 km annulus; the warm core = temperature at 300 / 500 hPa within 100 km minus the 300-600 km ring;
deep-convection share of columns; 850 hPa max wind within 300 km; relative humidity 700 hPa core vs ring.
python storm_budget.py LIBM_NPZ CONFIG_JSON OUT_JSON   (CONFIG like hind2: grid, dt_min, storms, hours, variants [{name, set, bogus, layers}])"""
import sys, os, json, time, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, ourens as O, landinit
from dinosaur import spherical_harmonic
LIB, CFG = sys.argv[1], sys.argv[2]
if len(sys.argv) > 5: CH, NCH, OUT = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]        # GitHub CPU queue form: LIB CFG CHUNK NCHUNK OUT
else: CH, NCH, OUT = 0, 1, sys.argv[3]
C = json.load(open(CFG)); NCH = min(NCH, C.get('nchunk', NCH)); Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
G, CP, LV, RD = 9.80616, 1004.6, 2.5e6, 287.04
def at(P0, t):
    for a, b in zip(P0, P0[1:]):
        if a[0] <= t <= b[0]:
            f = (t - a[0]).total_seconds() / max(1, (b[0] - a[0]).total_seconds())
            return tuple(a[i] + f * (b[i] - a[i]) if a[i] is not None and b[i] is not None else (a[i] or b[i]) for i in (1, 2, 3))
    return None
storms = [s for s in O.LIBL if (not C.get('storms') or s['name'] in C['storms'])]
res = []; MODELS = {}
for i_s, s in enumerate(storms):
    if i_s % NCH != CH: continue
    g = O.gen_time(s); key = g.strftime('%Y-%m-%dT%H')
    if key not in TT: continue
    k = TT.index(key); P0 = O.path_of(s); st0 = at(P0, g)
    if not st0: continue
    f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
    for var in C['variants']:
        try:
            t = time.time()
            if var['name'] not in MODELS: MODELS[var['name']] = mm2.Model(var.get('grid', C.get('grid', 'T170')), var.get('layers', 32), var.get('dt_min', C.get('dt_min', 20.0)), var.get('set'))
            M = MODELS[var['name']]
            storm = dict(lat=st0[0], lon=st0[1], vmax_kt=st0[2] or 25.0) if var.get('bogus', True) else None
            st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / G,
                            Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], storm=storm, when=g, **landinit.land_kwargs(Z['f2'][k], V2))
            M.build(g)
            if var.get('dfi', True): st = M.dfi(st)
            hor = M.coords.horizontal; LA, LO = np.asarray(M.LA), np.asarray(M.LO); sig = np.asarray(M.sig); ds = np.asarray(M.dsig); zs = np.asarray(M.zs)
            k300, k500, k700, k850 = (int(np.argmin(np.abs(sig - x))) for x in (0.3, 0.5, 0.7, 0.85))
            clat, clon = st0[0], st0[1]; rows = []
            for h in range(0, C.get('hours', 72) + 1, 3):
                if h: st, cr = mm2.integrate(M, st, cr, 3)
                T = np.asarray((hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K); q = np.asarray(st.tracers['specific_humidity'])
                ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA); u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
                uu, vv = np.asarray(u / M.MPS), np.asarray(v / M.MPS)
                mslp = ps * np.exp(G * zs / (RD * T[-1]))
                dist = lambda la0, lo0: np.hypot((LO - lo0 + 180) % 360 - 180, 0) * 0 + 111.2 * np.hypot(LA - la0, ((LO - lo0 + 180) % 360 - 180) * np.cos(np.radians(la0)))
                d0 = dist(clat, clon); srch = d0 <= 350
                i = np.argmin(np.where(srch, mslp, 1e9)); clat, clon = float(LA.flat[i]), float(LO.flat[i]); d = dist(clat, clon)
                core, inner, ring, wide = d <= 100, (d > 100) & (d <= 300), (d >= 300) & (d <= 600), d <= 300
                W = np.cos(np.radians(LA))
                mean2 = lambda X, m: float((np.asarray(X) * W * m).sum() / max((W * m).sum(), 1e-9))
                tn, dd = M.column(jnp.asarray(T), jnp.asarray(q), u / M.MPS, v / M.MPS, jnp.asarray(ps), dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
                prof = lambda X, m: [round(float((np.asarray(X)[l] * W * m).sum() / max((W * m).sum(), 1e-9)) * 86400, 2) for l in range(len(sig))]
                es = 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); p = sig[:, None, None] * ps[None]; rh = q / (0.622 * es / np.maximum(p - 0.378 * es, 1.0))
                H = np.asarray(dd['H']); E = np.asarray(dd['E']) * LV
                e = dict(h=h, lat=round(clat, 2), lon=round(clon, 2), pmin=round(float(mslp.flat[i]) / 100, 1),
                         vmax850=round(float(np.max(np.where(wide, np.hypot(uu[k850], vv[k850]), 0))), 1), vmax_lowest=round(float(np.max(np.where(wide, np.hypot(uu[-1], vv[-1]), 0))), 1),
                         flux_core=round(mean2(H + E, core), 1), flux_300=round(mean2(H + E, wide), 1),
                         wc300=round(mean2(T[k300], core) - mean2(T[k300], ring), 2), wc500=round(mean2(T[k500], core) - mean2(T[k500], ring), 2),
                         rh700_core=round(mean2(rh[k700], core), 3), rh700_ring=round(mean2(rh[k700], ring), 3),
                         on_dp_core=round(mean2(dd.get('on_dp', np.zeros_like(ps)), core), 3), on_dp_300=round(mean2(dd.get('on_dp', np.zeros_like(ps)), wide), 3),
                         rain_core=round(mean2(dd['rain'], core) * 86400, 1), rain_300=round(mean2(dd['rain'], wide) * 86400, 1))
                for kk in ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap'):
                    if kk in dd: e[kk + '_core'] = prof(dd[kk], core); e[kk + '_ann'] = prof(dd[kk], inner)
                if 'rad' in dd: e['rad_core'] = prof(dd['rad']['heating'], core)
                rows.append(e)
                print(s['name'], var['name'], f"+{h:2d}h p {e['pmin']} v850 {e['vmax850']} wc300 {e['wc300']} wc500 {e['wc500']} flux {e['flux_core']}/{e['flux_300']} deep {e['on_dp_core']}/{e['on_dp_300']} rain {e['rain_core']}/{e['rain_300']} rh700 {e['rh700_core']}/{e['rh700_ring']}", flush=True)
            res.append(dict(name=s['name'], season=s['season'], var=var['name'], t0=key, sig=sig.round(4).tolist(), real=[((p_[0] - g).total_seconds() / 3600, p_[1], p_[2], p_[3]) for p_ in P0], rows=rows, sec=round(time.time() - t)))
        except Exception as ex:
            import traceback; traceback.print_exc(); res.append(dict(name=s['name'], var=var['name'], err=repr(ex)[:300]))
        json.dump(res, open(OUT, 'w'), default=float)
