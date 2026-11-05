"""MEGAM health run (5 Nov, Sridhar + peer: 'detect errors at the point they are created'). Detectors 2 (physical limits)
and 3 (numerical stability), cheap enough to run locally before any Kaggle job: T42 grid at the T170 time step (20 min),
24 h, from two real starts with the ERA5 land state (15 Apr dry season, 27 Oct NE monsoon onset; data/cyclone/health_in.npz).
Every step: per-process heating/moistening/momentum maxima, surface fluxes, skin temperature jumps, wind runaway,
explicit-coupling overshoot numbers, water closure. HARD flags fail the run; SOFT flags are reported.
For each flag the FIRST occurrence is reported (step, hour, process, value, level, lat, lon) = the first process that
produced the abnormal value.
python health.py 'SETTINGS_JSON' [LAYERS=32] [HOURS=24]   -> prints the report, writes data/cyclone/health/<id>.json,
exit 0 = pass, 1 = HARD flag. The id is a hash of (model code, settings, layers, hours): a candidate is checked once."""
import datetime as dt, glob, hashlib, json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MM = os.path.join(ROOT, 'scripts/cyclone/mm'); sys.path.insert(0, MM)
IN = os.path.join(ROOT, 'data/cyclone/health_in.npz'); OUTD = os.path.join(ROOT, 'data/cyclone/health')
G, RD, CP, LV, SB = 9.80616, 287.04, 1004.6, 2.5e6, 5.67e-8
HARD = dict(rate=1000.0, total=500.0, wind=80.0, skin_jump=20.0, H_hi=1500.0, H_lo=-1000.0, q_neg=-1e-6, le_excess=300.0, water=2.0)
SOFT = dict(rate=300.0, wind=50.0, skin_jump=10.0, le_excess=0.0, overshoot=1.0, dwind=15.0)
def run_id(settings, layers, hours):
    h = hashlib.sha256()
    for f in sorted(glob.glob(MM + '/*.py')): h.update(open(f, 'rb').read())
    h.update(json.dumps([settings, layers, hours], sort_keys=True).encode()); return h.hexdigest()[:16]
def main(argv):
    S = json.loads(argv[0]) if argv else {}; NL = argv[1] if len(argv) > 1 else '32'; HRS = int(argv[2]) if len(argv) > 2 else 24
    NL = NL if NL == 'tp75' else int(NL); rid = run_id(S, NL, HRS); os.makedirs(OUTD, exist_ok=True); outf = f'{OUTD}/{rid}.json'
    if os.path.exists(outf):
        R = json.load(open(outf)); print(f"HEALTH (cached {rid}): {'PASS' if R['pass'] else 'FAIL'}"); return 0 if R['pass'] else 1
    import jax, jax.numpy as jnp, mm2, landinit
    from dinosaur import spherical_harmonic
    Z = dict(np.load(IN)); V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; TT = [str(t) for t in Z['times']]
    M = mm2.Model('T42', NL, 20.0, dict({'rad': 'radcloud', 'rad_every': 2}, **S))
    LA = np.asarray(M.LA); LO = np.asarray(M.LO) % 360; W = np.cos(np.radians(LA))
    sig = np.asarray(M.sig); dsig = np.asarray(M.dsig)[:, None, None]; nstep = int(round(HRS * 3600 / M.dt_s))
    flags = {}; summ = {}
    def flag(kind, name, step, val, where, start):
        k = f'{kind}:{name}'
        if k not in flags: flags[k] = dict(kind=kind, name=name, start=start, step=step, hour=round(step * M.dt_s / 3600, 2), value=round(float(val), 2), count=0, **where)
        flags[k]['count'] += 1
    def loc(a3, lev=True):
        i = np.unravel_index(np.nanargmax(a3), a3.shape)
        if lev: return dict(level=int(i[0]), sigma=round(float(sig[i[0]]), 3), lat=round(float(LA[i[1], i[2]]), 1), lon=round(float(LO[i[1], i[2]]), 1))
        return dict(lat=round(float(LA[i]), 1), lon=round(float(LO[i]), 1))
    for k, key in enumerate(TT):
        t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / G,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0); st = M.dfi(st); hor = M.coords.horizontal
        colj = jax.jit(lambda T_, q_, u_, v_, ps_, cr_, dv_: M.column(T_, q_, u_, v_, ps_, cr_, rad_fresh=True, div=dv_))
        stepj = jax.jit(lambda s_, c_: mm2.integrate(M, s_, c_, M.dt_s / 3600.0)) if False else None; land = np.asarray(M.land) > 0.5; prev_w1 = None; prev_tl = np.asarray(cr['tl']); worst = {}
        for n in range(1, nstep + 1):
            st, cr = mm2.integrate(M, st, cr, M.dt_s / 3600.0)
            T = (hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K; q = st.tracers['specific_humidity']
            ps = jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
            Tn, qn, psn = np.asarray(T), np.asarray(q), np.asarray(ps); un, vn = np.asarray(u / M.MPS), np.asarray(v / M.MPS)
            if not (np.isfinite(Tn).all() and np.isfinite(qn).all() and np.isfinite(psn).all() and np.isfinite(un).all()):
                flag('HARD', 'nonfinite state', n, np.nan, {}, key); break
            tn, d = colj(T, q, u / M.MPS, v / M.MPS, ps, dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), hor.to_nodal(st.divergence) * M.SEC)
            # 1 per-process heating (K/day) and the total
            for p_ in ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap', 'rad_app'):
                if p_ not in d: continue
                a = np.abs(np.asarray(d[p_])) * 86400; m = float(a.max()); worst[p_] = max(worst.get(p_, 0), m)
                if m > HARD['rate']: flag('HARD', f'{p_} > {HARD["rate"]:.0f} K/day', n, m, loc(a), key)
                elif m > SOFT['rate']: flag('SOFT', f'{p_} > {SOFT["rate"]:.0f} K/day', n, m, loc(a), key)
            a = np.abs(np.asarray(tn['T'])) * 86400; m = float(a.max()); worst['total_T'] = max(worst.get('total_T', 0), m)
            if m > HARD['total']: flag('HARD', f'total physics heating > {HARD["total"]:.0f} K/day', n, m, loc(a), key)
            # 2 humidity
            if float(qn.min()) < HARD['q_neg']: flag('HARD', 'negative humidity', n, qn.min() * 1e3, loc(-qn), key)
            # 3 winds
            w1 = np.hypot(un[-1], vn[-1]); wm = float(w1.max()); worst['wind_lowest'] = max(worst.get('wind_lowest', 0), wm)
            if wm > HARD['wind']: flag('HARD', f'lowest-level wind > {HARD["wind"]:.0f} m/s', n, wm, loc(w1, False), key)
            elif wm > SOFT['wind']: flag('SOFT', f'lowest-level wind > {SOFT["wind"]:.0f} m/s', n, wm, loc(w1, False), key)
            if prev_w1 is not None:
                dw = np.abs(w1 - prev_w1); m = float(dw.max())
                if m > SOFT['dwind']: flag('SOFT', f'lowest-level wind change > {SOFT["dwind"]:.0f} m/s per step', n, m, loc(dw, False), key)
            prev_w1 = w1
            # 4 surface: skin jumps, flux limits, energy-impossible latent heat over land, explicit overshoot numbers
            tl = np.asarray(cr['tl']); jump = np.where(land, np.abs(tl - prev_tl), 0.0); prev_tl = tl; m = float(jump.max())
            worst['skin_jump'] = max(worst.get('skin_jump', 0), m)
            if m > HARD['skin_jump']: flag('HARD', f'land skin jump > {HARD["skin_jump"]:.0f} K per step', n, m, loc(jump, False), key)
            elif m > SOFT['skin_jump']: flag('SOFT', f'land skin jump > {SOFT["skin_jump"]:.0f} K per step', n, m, loc(jump, False), key)
            H = np.asarray(d['H']); E = np.asarray(d['E']) * LV
            if float(H.max()) > HARD['H_hi'] or float(H.min()) < HARD['H_lo']: flag('HARD', 'sensible heat flux outside -1000..1500 W/m2', n, H.max() if H.max() > HARD['H_hi'] else H.min(), loc(np.abs(H), False), key)
            avail = np.asarray(d['sw_sfc']) + np.asarray(d['lw_dn'])
            ex = np.where(land, E - avail, -1e9); m = float(ex.max()); worst['LE_minus_SWnet_LWdn'] = max(worst.get('LE_minus_SWnet_LWdn', -1e9), m)
            if m > HARD['le_excess']: flag('HARD', 'land latent heat exceeds SWnet + LWdown by > 300 W/m2', n, m, loc(ex, False), key)
            elif m > SOFT['le_excess']: flag('SOFT', 'land latent heat exceeds SWnet + LWdown', n, m, loc(ex, False), key)
            mass1 = dsig[-1, 0, 0] * psn / G; p1 = sig[-1] * psn; rho = p1 / (RD * Tn[-1])
            r_heat = M.dt_s * np.asarray(d['chv']) / mass1; ust = np.asarray(d['ust']); V1 = np.maximum(np.asarray(d['V1']), 0.1)
            r_drag = M.dt_s * rho * ust ** 2 / V1 / mass1
            for nm, r, on in (('heat/moisture', r_heat, M.S.get('sfc_imp', 0) > 0), ('momentum (drag)', r_drag, M.S.get('drag_imp', 0) > 0)):
                m = float(r.max()); worst[f'overshoot_{nm}'] = max(worst.get(f'overshoot_{nm}', 0), m)
                if not on and m > SOFT['overshoot']: flag('SOFT', f'explicit {nm} exchange overshoot number > 1', n, m, loc(r, False), key)
            # 5 water closure: surface rain = water removed by the precipitating processes (global, W/m2)
            if all(k_ in d for k_ in ('q_deep', 'q_shal', 'q_lsc', 'q_evap')):
                mass = dsig * psn[None] / G; I = lambda x: (np.asarray(x) * mass).sum(0)
                res = LV * (np.asarray(d['rain']) + I(np.asarray(d['q_deep']) + np.asarray(d['q_shal']) + np.asarray(d['q_lsc']) + np.asarray(d['q_evap'])))
                g = float((res * W).sum() / W.sum())
                if abs(g) > HARD['water']: flag('HARD', 'global water closure residual > 2 W/m2', n, g, {}, key)
            if float(np.asarray(d['rain']).min()) < -1e-9: flag('HARD', 'negative surface rain', n, np.asarray(d['rain']).min() * 86400, loc(-np.asarray(d['rain']), False), key)
        summ[key] = {k_: round(v_, 2) for k_, v_ in worst.items()}
    hard = [f for f in flags.values() if f['kind'] == 'HARD']
    R = dict(id=rid, settings=S, layers=NL, hours=HRS, grid='T42 (dt 20 min)', pass_=None, flags=sorted(flags.values(), key=lambda f: (f['kind'] != 'HARD', f['start'], f['step'])), worst=summ)
    R['pass'] = not hard; R.pop('pass_')
    json.dump(R, open(outf, 'w'), indent=1)
    print(f"HEALTH {rid}: {'PASS' if R['pass'] else 'FAIL'} | settings {S} | layers {NL} | {HRS} h | {len(hard)} HARD, {len(flags) - len(hard)} SOFT")
    for f in R['flags']:
        w = ', '.join(f'{k_} {f[k_]}' for k_ in ('sigma', 'lat', 'lon') if k_ in f)
        print(f"  {f['kind']:4s} {f['name']:58s} first at {f['start'][:10]} +{f['hour']:5.2f} h  value {f['value']}  ({w})  x{f['count']}")
    print('  worst per start:', json.dumps(summ))
    return 0 if R['pass'] else 1
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
