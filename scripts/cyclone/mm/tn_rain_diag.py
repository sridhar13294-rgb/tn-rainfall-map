"""P4 diagnosis: where does the extra Tamil Nadu rain come from? For chosen starts, run 5 days and every 3 h record, over
TN land / Western Ghats / TN coastal sea / Bay offshore: rain split into convective (deep plume) and grid-scale, deep-
convection share of columns, low-level wind (850 hPa u, v), relative humidity at 925/850/700/500 hPa and lowest-layer
T/q. Daily: model 24-h rain map vs the exam truth (ERA5) for the same TN box, and day-5 q/T profile bias vs ERA5 over TN.
python tn_rain_diag.py LIBM_WX_NPZ TRUTH_NPZ OUT_JSON 'START1,START2,..' SETTINGS_JSON   (SETTINGS: {"name": {settings,
"layers":..., "grid":...}}; one variant per process to save memory)"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit, wxscore as WS
from dinosaur import spherical_harmonic
LIB, TRU, OUT = sys.argv[1], sys.argv[2], sys.argv[3]; STARTS = sys.argv[4].split(','); VARS = json.loads(sys.argv[5])
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
TR = dict(np.load(TRU)); DI = {str(d): i for i, d in enumerate(TR['days'])}
LEV = np.asarray(Z['levs'], float); la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
LAg, LOg = np.meshgrid(la, lo, indexing='ij')
CP, LV, G = 1004.6, 2.5e6, 9.80616
ALL = {}
for VN, VS in VARS.items():
    VS = dict(VS); NL = VS.pop('layers', 32); GR = VS.pop('grid', 'T170')
    M = mm2.Model(GR, NL, None, dict({'rad': 'radcloud', 'rad_every': 2}, **VS)); res = []
    LA, LO = np.asarray(M.LA), np.asarray(M.LO) % 360
    def regions(land):
        box = (LA >= 8) & (LA <= 14) & (LO >= 76) & (LO <= 81)
        return {'tn_land': box & land & (LO >= 77.3), 'ghats': (LA >= 8) & (LA <= 13) & (LO >= 75.5) & (LO <= 77.3) & land,
          'tn_coast_sea': (LA >= 8) & (LA <= 14) & (LO >= 79.5) & (LO <= 82) & ~land, 'bay_off': (LA >= 9) & (LA <= 15) & (LO >= 82) & (LO <= 87) & ~land}
    W = np.cos(np.radians(LA)); sig = np.asarray(M.sig); ds = np.asarray(M.dsig)
    def rmean(X, m): w = W * m; return float((np.asarray(X) * w).sum() / max(w.sum(), 1e-9))
    for key in STARTS:
        key = key if 'T' in key else key + 'T00'
        if key not in TT: print('missing start', key, flush=True); continue
        t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / G,
                        Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
        M.build(t0); st = M.dfi(st); hor = M.coords.horizontal; RG = regions(np.asarray(M.land).astype(bool))
        r = dict(start=key, var=VN, steps=[], daily=[])
        rain_prev = np.asarray(cr['rain']); h = 0
        for step in range(40):                                           # 40 x 3 h = 5 days
            st, cr = mm2.integrate(M, st, cr, 3); h += 3
            T = np.asarray((hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K); q = np.asarray(st.tracers['specific_humidity'])
            ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA); u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st.vorticity, st.divergence)
            tn, d = M.column(jnp.asarray(T), jnp.asarray(q), u / M.MPS, v / M.MPS, jnp.asarray(ps), dict(cr, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st.divergence) * M.SEC)
            colm = ds[:, None, None] * ps[None] / G                                         # kg/m2 per layer
            conv = (np.asarray(d['h_deep']) * colm).sum(0) * CP / LV * 86400                  # mm/day equivalent of deep-convective heating
            lsc = (np.asarray(d['h_lsc']) * colm).sum(0) * CP / LV * 86400
            evp = -(np.asarray(d['h_evap']) * colm).sum(0) * CP / LV * 86400
            p = sig[:, None, None] * ps[None]; es = 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); rh = q / (0.622 * es / np.maximum(p - 0.378 * es, 1.0))
            kk = {P: np.argmin(np.abs(sig - P / 1000.0)) for P in (925, 850, 700, 500)}
            uu, vv = np.asarray(u / M.MPS), np.asarray(v / M.MPS)
            e = dict(h=h)
            for rn, m in RG.items():
                e[rn] = dict(rain=round(rmean(d['rain'], m) * 86400, 2), conv=round(rmean(conv, m), 2), lsc=round(rmean(lsc, m), 2), evap=round(rmean(evp, m), 2),
                             on_dp=round(rmean(d.get('on_dp', np.zeros_like(ps)), m), 3), u850=round(rmean(uu[kk[850]], m), 1), v850=round(rmean(vv[kk[850]], m), 1),
                             rh={P: round(rmean(rh[i], m), 3) for P, i in kk.items()}, T1=round(rmean(T[-1], m), 2), q1=round(rmean(q[-1], m) * 1000, 2))
            r['steps'].append(e)
            if h % 24 == 0:                                                                 # daily: 24 h rain in the exam's TN box vs truth (ERA5)
                rn24 = np.asarray(cr['rain']) - rain_prev; rain_prev = np.asarray(cr['rain'])
                vk = (t0 + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H'); dd = dict(day=h // 24)
                g = WS.to_grid(rn24, M.lon, M.lat)
                mtn = WS.REGIONS['tamil_nadu']
                if vk in DI and mtn is not None:
                    o = TR['o_rain24'][DI[vk]]; w = np.cos(np.radians(WS.LA)) * mtn
                    dd.update(model=round(float((g * w).sum() / w.sum()), 2), truth=round(float((np.nan_to_num(o) * w).sum() / w.sum()), 2))
                r['daily'].append(dd)
        k5 = TT.index((t0 + dt.timedelta(days=5)).strftime('%Y-%m-%dT%H')) if (t0 + dt.timedelta(days=5)).strftime('%Y-%m-%dT%H') in TT else None
        if k5 is not None:                                                                   # day-5 TN T/q profile vs ERA5 (model interpolated in log p)
            m = (LAg >= 8) & (LAg <= 14) & (LOg >= 77) & (LOg <= 81); w = np.cos(np.radians(LAg)) * m
            em = lambda vname: [float((Z['f3'][k5, V3.index(vname)][i] * w).sum() / w.sum()) for i in range(len(LEV))]
            mm_ = RG['tn_land'] | RG['ghats']; lp = np.log(p); prof = {}
            for nm, X in (('T', T), ('q', q)):
                vals = []
                for P in LEV * 100:
                    x = np.log(P); k1 = np.clip((lp < x).sum(0), 1, len(sig) - 1); k0 = k1 - 1; gg = lambda A, kq: np.take_along_axis(A, kq[None], 0)[0]
                    wq = np.clip((x - gg(lp, k0)) / (gg(lp, k1) - gg(lp, k0)), 0, 1); vv_ = gg(X, k0) + wq * (gg(X, k1) - gg(X, k0)); ok = mm_ & (P < ps)
                    vals.append(rmean(vv_, ok))
                prof[nm] = vals
            r['d5_bias'] = dict(levs=LEV.tolist(), T=(np.array(prof['T']) - np.array(em('temperature'))).round(2).tolist(),
                                q_gkg=((np.array(prof['q']) - np.array(em('specific_humidity'))) * 1000).round(3).tolist())
        res.append(r); ALL[VN] = res; json.dump(ALL, open(OUT, 'w'))
        dy = [(x['day'], x.get('model'), x.get('truth')) for x in r['daily']]
        tot = {rn: (round(np.mean([s[rn]['conv'] for s in r['steps']]), 2), round(np.mean([s[rn]['lsc'] for s in r['steps']]), 2), round(np.mean([s[rn]['rain'] for s in r['steps']]), 2)) for rn in RG}
        print(VN, key, 'TN box rain model/truth by day', dy, '| 5-day mean conv/lsc/sfc rain mm/d', tot, '| d5 bias T,q', r.get('d5_bias', {}).get('T'), r.get('d5_bias', {}).get('q_gkg'), flush=True)
