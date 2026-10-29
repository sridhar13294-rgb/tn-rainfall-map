"""Where in the column does the model drift? Tropical (20S-20N) and India mean temperature and humidity profiles after
1 and 5 days against ERA5 at the same time (exam starts are 5 days apart), plus the tropical-mean radiative heating and
total physics heating profiles (K/day) at day 5.
python wx_prof.py LIBM_WX_NPZ OUT_JSON [N_STARTS] [SETTINGS_JSON]"""
import sys, os, json, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mm2, landinit
from dinosaur import spherical_harmonic
LIB, OUT = sys.argv[1], sys.argv[2]; NS = int(sys.argv[3]) if len(sys.argv) > 3 else 4
VARS = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {'ctl': {}}
BASE = {'rad': 'radcloud', 'rad_every': 2}
Z = dict(np.load(LIB)); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
LEV = np.asarray(Z['levs'], float); la = np.asarray(Z['lats'], float); lo = np.asarray(Z['lons'], float)
LAg, LOg = np.meshgrid(la, lo, indexing='ij'); Wg = np.cos(np.radians(LAg))
REG = {'tropics': lambda A, O: np.abs(A) < 20, 'india': lambda A, O: (A >= 5) & (A <= 35) & (O >= 65) & (O <= 100), 'trop_pacific': lambda A, O: (np.abs(A) < 20) & (O % 360 >= 160) & (O % 360 <= 260)}
def era_mean(k, v, reg):
    m = REG[reg](LAg, LOg); a = Z['f3'][k, V3.index(v)]; return [float((a[i] * Wg * m).sum() / (Wg * m).sum()) for i in range(len(LEV))]
ALL = {}
for VN, VS in VARS.items():
  VS = dict(VS); SPLIT = bool(VS.pop('_split', False)); BUDGET = bool(VS.pop('_budget', False)); NL = VS.pop('layers', 32); GR = VS.pop('grid', 'T85')
  M = mm2.Model(GR, NL, None, dict(BASE, **VS)); res = []
  def model_profiles(st, cr):
      hor = M.coords.horizontal
      T = np.asarray((hor.to_nodal(st.temperature_variation) + M.ref_t[:, None, None]) / M.K); q = np.asarray(st.tracers['specific_humidity'])
      ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA); p = np.asarray(M.sig)[:, None, None] * ps[None]
      LA, LO = np.asarray(M.LA), np.asarray(M.LO); W = np.cos(np.radians(LA)); out = {}
      for reg, f in REG.items():
          m = f(LA, LO) & (ps > 0); prof = {}
          for name, X in (('T', T), ('q', q)):
              vals = []
              for P in LEV * 100:
                  lp = np.log(p); x = np.log(P); k1 = np.clip((lp < x).sum(0), 1, len(M.sig) - 1); k0 = k1 - 1
                  g = lambda A, k: np.take_along_axis(A, k[None], 0)[0]
                  w = np.clip((x - g(lp, k0)) / (g(lp, k1) - g(lp, k0)), 0, 1); v = g(X, k0) + w * (g(X, k1) - g(X, k0))
                  ok = m & (P < ps); vals.append(float((v * W * ok).sum() / max((W * ok).sum(), 1e-9)))
              prof[name] = vals
          out[reg] = prof
      return out, T, q, ps
  for n, key in enumerate(TT[:NS]):
      t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); k = TT.index(key); f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
      k5 = TT.index((t0 + dt.timedelta(days=5)).strftime('%Y-%m-%dT%H')) if (t0 + dt.timedelta(days=5)).strftime('%Y-%m-%dT%H') in TT else None
      if k5 is None: continue
      st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], Z['f2'][k, V2.index('surface_pressure')], Z['f2'][k, V2.index('geopotential_at_surface')] / 9.80616,
                      Z['f2'][k, V2.index('sea_surface_temperature')], Z['f2'][k, V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(Z['f2'][k], V2))
      M.build(t0, split=SPLIT); st = M.dfi(st); r = dict(start=key, levs=LEV.tolist())
      p0, *_ = model_profiles(st, cr); r['h0'] = {reg: {kk: (np.array(p0[reg][kk]) - np.array(era_mean(k, 'temperature' if kk == 'T' else 'specific_humidity', reg))).round(4).tolist() for kk in ('T', 'q')} for reg in REG}
      if BUDGET:   # T budget on model levels: total dT/dt from states 3 h apart, physics (by process) from the column every 3 h
          # (trapezoid mean), dynamics = total - physics; regions tropics / TN (8-14N 76-81E) / Western Ghats (8-21N 73-77.5E, land)
          hor = M.coords.horizontal; LAm, LOm = np.asarray(M.LA), np.asarray(M.LO) % 360
          RB = {'tropics': np.abs(LAm) < 20, 'tn': (LAm >= 8) & (LAm <= 14) & (LOm >= 76) & (LOm <= 81), 'ghats': (LAm >= 8) & (LAm <= 21) & (LOm >= 73) & (LOm <= 77.5)}
          PR = ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap')
          def snap(s_, c_):
              Ts = np.asarray((hor.to_nodal(s_.temperature_variation) + M.ref_t[:, None, None]) / M.K); qs = np.asarray(s_.tracers['specific_humidity'])
              pss = np.asarray(jnp.exp(hor.to_nodal(s_.log_surface_pressure))[0] / M.PA); uu, vv = spherical_harmonic.vor_div_to_uv_nodal(hor, s_.vorticity, s_.divergence)
              tn_, dd = M.column(jnp.asarray(Ts), jnp.asarray(qs), uu / M.MPS, vv / M.MPS, jnp.asarray(pss), dict(c_, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(s_.divergence) * M.SEC)
              o = {}
              for rg, mk in RB.items():
                  W_ = np.cos(np.radians(LAm)) * mk; mn = lambda X: np.array([(np.asarray(X)[i] * W_).sum() / W_.sum() for i in range(len(M.sig))])
                  e = dict(T=mn(Ts), q=mn(qs), phys=mn(tn_['T']) * 86400, physq=mn(tn_['q']) * 86400 * 1000)
                  if 'rad' in dd: e['rad'] = mn(dd['rad']['heating']) * 86400
                  for kk in PR:
                      if kk in dd: e[kk] = mn(dd[kk]) * 86400
                  e['rain'] = float((np.asarray(dd['rain']) * W_).sum() / W_.sum() * 86400)
                  for kk in ('on_dp', 'on_sh'):
                      if kk in dd: e[kk] = float((np.asarray(dd[kk]) * W_).sum() / W_.sum())
                  o[rg] = e
              return o
          B = {}; sA, cA = st, cr; hA = 0
          for w0, w1 in ((0, 24), (96, 120)):
              if hA < w0: sA, cA = mm2.integrate(M, sA, cA, w0 - hA); hA = w0
              snaps = [snap(sA, cA)]
              for h in range(w0 + 3, w1 + 1, 3): sA, cA = mm2.integrate(M, sA, cA, 3); snaps.append(snap(sA, cA))
              hA = w1; win = {}
              for rg in RB:
                  tm = lambda k: (0.5 * snaps[0][rg][k] + sum(x[rg][k] for x in snaps[1:-1]) + 0.5 * snaps[-1][rg][k]) / (len(snaps) - 1)
                  tot = (snaps[-1][rg]['T'] - snaps[0][rg]['T']) / ((w1 - w0) / 24.0); ph = tm('phys'); e = dict(total=tot, phys=ph, dyn=tot - ph)
                  totq = (snaps[-1][rg]['q'] - snaps[0][rg]['q']) * 1000 / ((w1 - w0) / 24.0); e['totq'] = totq; e['physq'] = tm('physq'); e['dynq'] = totq - e['physq']
                  for kk in ('rad',) + PR:
                      if kk in snaps[0][rg]: e[kk] = tm(kk)
                  e = {k: np.round(v, 3).tolist() for k, v in e.items()}
                  e['rain'] = round(float(np.mean([x[rg]['rain'] for x in snaps])), 2)
                  for kk in ('on_dp', 'on_sh'):
                      if kk in snaps[0][rg]: e[kk] = round(float(np.mean([x[rg][kk] for x in snaps])), 3)
                  win[rg] = e
              B[f'{w0}-{w1}h'] = win
          r['budget'] = B; st5, cr5 = sA, cA
          print(VN, key, 'BUDGET tropics dyn', {k: dict(zip(np.asarray(M.sig).round(3).tolist(), np.round(v['tropics']['dyn'], 2))) for k, v in B.items()}, flush=True)
      else: st5, cr5 = mm2.integrate(M, st, cr, 120)
      p5, T, q, ps = model_profiles(st5, cr5)
      r['d5'] = {reg: {kk: (np.array(p5[reg][kk]) - np.array(era_mean(k5, 'temperature' if kk == 'T' else 'specific_humidity', reg))).round(4).tolist() for kk in ('T', 'q')} for reg in REG}
      hor = M.coords.horizontal; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st5.vorticity, st5.divergence)
      tend, d = M.column(jnp.asarray(T), jnp.asarray(q), u / M.MPS, v / M.MPS, jnp.asarray(ps), dict(cr5, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st5.divergence) * M.SEC)
      trop = np.abs(np.asarray(M.LA)) < 20; W = np.cos(np.radians(np.asarray(M.LA))) * trop
      mean = lambda X: [round(float((np.asarray(X)[i] * W).sum() / W.sum()) * 86400, 3) for i in range(len(M.sig))]
      r['sig'] = np.asarray(M.sig).round(4).tolist(); r['phys_dT_Kday'] = mean(tend['T'])
      if 'rad' in d: r['rad_Kday'] = mean(d['rad']['heating'])
      for kk in ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap'):
          if kk in d: r[kk] = mean(d[kk])
      for kk in ('on_dp', 'on_sh', 'on_bmjsh'):
          if kk in d: r[kk + '_trop'] = round(float((np.asarray(d[kk]) * W).sum() / W.sum()), 3)
      r['rain_trop_mmday'] = round(float((np.asarray(d['rain']) * W).sum() / W.sum() * 86400), 2)
      r['lw_dn_sfc_trop'] = round(float((np.asarray(d['lw_dn']) * W).sum() / W.sum()), 1); r['sw_sfc_trop'] = round(float((np.asarray(d['sw_sfc']) * W).sum() / W.sum()), 1)
      r['lh_trop'] = round(float((np.asarray(d['E']) * W).sum() / W.sum() * 2.5e6), 1); r['sh_trop'] = round(float((np.asarray(d['H']) * W).sum() / W.sum()), 1)
      if 'rad' in d: r['rad_col_Wm2'] = round(float((np.asarray((d['rad']['heating'] * jnp.asarray(M.dsig)[:, None, None] * jnp.asarray(ps)[None] / 9.81 * 1004.6).sum(0)) * W).sum() / W.sum()), 1)
      Wm = np.cos(np.radians(np.asarray(M.LA))); gm = lambda X: float((np.asarray(X) * Wm).sum() / Wm.sum())
      r['globe'] = dict(rain_Wm2=round(gm(d['rain']) * 2.5e6, 1), LH=round(gm(d['E']) * 2.5e6, 1), SH=round(gm(d['H']), 1),
                        radcol=round(gm((d['rad']['heating'] * jnp.asarray(M.dsig)[:, None, None] * jnp.asarray(ps)[None] / 9.81 * 1004.6).sum(0)), 1) if 'rad' in d else None,
                        physcol=round(gm((tend['T'] * jnp.asarray(M.dsig)[:, None, None] * jnp.asarray(ps)[None] / 9.81 * 1004.6).sum(0)), 1),
                        olr=round(gm(d['rad']['olr']), 1) if 'rad' in d else None)
      r['olr_trop'] = round(float((np.asarray(d['rad']['olr']) * W).sum() / W.sum()), 1) if 'rad' in d else None
      res.append(r); ALL[VN] = res; json.dump(ALL, open(OUT, 'w'))
      print(VN, key, 'd5 T bias tropics', dict(zip(LEV.astype(int).tolist(), np.round(r['d5']['tropics']['T'], 2).tolist())), 'rad', r.get('rad_Kday'), 'rain', r['rain_trop_mmday'], 'olr', r['olr_trop'], 'lwdn', r['lw_dn_sfc_trop'], 'swsfc', r['sw_sfc_trop'], 'LH', r['lh_trop'], 'on dp/sh/oldsh', r.get('on_dp_trop'), r.get('on_sh_trop'), r.get('on_bmjsh_trop'), 'SH', r['sh_trop'], 'radcol', r.get('rad_col_Wm2'), 'GLOBE', r['globe'], flush=True)
  ALL[VN] = res; json.dump(ALL, open(OUT, 'w'))
  if res:
      for reg in REG:
          print(VN, reg, 'mean d5 T bias', dict(zip(LEV.astype(int).tolist(), np.round(np.mean([x['d5'][reg]['T'] for x in res], 0), 2).tolist())))
          print(VN, reg, 'mean d5 q bias g/kg', dict(zip(LEV.astype(int).tolist(), np.round(np.mean([x['d5'][reg]['q'] for x in res], 0) * 1000, 2).tolist())))
      print(VN, 'rad K/day by sigma', dict(zip(res[0]['sig'], np.round(np.mean([x['rad_Kday'] for x in res if 'rad_Kday' in x], 0), 2).tolist())))
      for kk in ('h_bl', 'h_deep', 'h_shal', 'h_lsc', 'h_evap'):
          if all(kk in x for x in res): print(VN, kk, 'K/day by sigma', dict(zip(res[0]['sig'], np.round(np.mean([x[kk] for x in res], 0), 2).tolist())))
      if all('budget' in x for x in res):
          for kb in res[0]['budget']:
              for rg in res[0]['budget'][kb]:
                  for part in [k for k in res[0]['budget'][kb][rg] if isinstance(res[0]['budget'][kb][rg][k], list)]:
                      print(VN, 'BUDGET', kb, rg, part, 'per day by sigma', dict(zip(res[0]['sig'], np.round(np.mean([x['budget'][kb][rg][part] for x in res], 0), 2).tolist())))
                  print(VN, 'BUDGET', kb, rg, 'rain mm/day', np.mean([x['budget'][kb][rg]['rain'] for x in res]).round(2), 'on_dp', np.mean([x['budget'][kb][rg].get('on_dp', np.nan) for x in res]).round(3), 'on_sh', np.mean([x['budget'][kb][rg].get('on_sh', np.nan) for x in res]).round(3))
      print(VN, 'phys K/day by sigma', dict(zip(res[0]['sig'], np.round(np.mean([x['phys_dT_Kday'] for x in res], 0), 2).tolist())))
