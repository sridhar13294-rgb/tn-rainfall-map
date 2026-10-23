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
REG = {'tropics': lambda A, O: np.abs(A) < 20, 'india': lambda A, O: (A >= 5) & (A <= 35) & (O >= 65) & (O <= 100)}
def era_mean(k, v, reg):
    m = REG[reg](LAg, LOg); a = Z['f3'][k, V3.index(v)]; return [float((a[i] * Wg * m).sum() / (Wg * m).sum()) for i in range(len(LEV))]
ALL = {}
for VN, VS in VARS.items():
  M = mm2.Model('T85', 32, None, dict(BASE, **VS)); res = []
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
      M.build(t0); st = M.dfi(st); r = dict(start=key, levs=LEV.tolist())
      p0, *_ = model_profiles(st, cr); r['h0'] = {reg: {kk: (np.array(p0[reg][kk]) - np.array(era_mean(k, 'temperature' if kk == 'T' else 'specific_humidity', reg))).round(4).tolist() for kk in ('T', 'q')} for reg in REG}
      st5, cr5 = mm2.integrate(M, st, cr, 120); p5, T, q, ps = model_profiles(st5, cr5)
      r['d5'] = {reg: {kk: (np.array(p5[reg][kk]) - np.array(era_mean(k5, 'temperature' if kk == 'T' else 'specific_humidity', reg))).round(4).tolist() for kk in ('T', 'q')} for reg in REG}
      hor = M.coords.horizontal; u, v = spherical_harmonic.vor_div_to_uv_nodal(hor, st5.vorticity, st5.divergence)
      tend, d = M.column(jnp.asarray(T), jnp.asarray(q), u / M.MPS, v / M.MPS, jnp.asarray(ps), dict(cr5, doy0=jnp.float32(M.doy0), utc0=jnp.float32(M.utc0)), rad_fresh=True, div=hor.to_nodal(st5.divergence) * M.SEC)
      trop = np.abs(np.asarray(M.LA)) < 20; W = np.cos(np.radians(np.asarray(M.LA))) * trop
      mean = lambda X: [round(float((np.asarray(X)[i] * W).sum() / W.sum()) * 86400, 3) for i in range(len(M.sig))]
      r['sig'] = np.asarray(M.sig).round(4).tolist(); r['phys_dT_Kday'] = mean(tend['T'])
      if 'rad' in d: r['rad_Kday'] = mean(d['rad']['heating'])
      r['rain_trop_mmday'] = round(float((np.asarray(d['rain']) * W).sum() / W.sum() * 86400), 2)
      r['lw_dn_sfc_trop'] = round(float((np.asarray(d['lw_dn']) * W).sum() / W.sum()), 1); r['sw_sfc_trop'] = round(float((np.asarray(d['sw_sfc']) * W).sum() / W.sum()), 1)
      r['lh_trop'] = round(float((np.asarray(d['E']) * W).sum() / W.sum() * 2.5e6), 1); r['sh_trop'] = round(float((np.asarray(d['H']) * W).sum() / W.sum()), 1)
      if 'rad' in d: r['rad_col_Wm2'] = round(float((np.asarray((d['rad']['heating'] * jnp.asarray(M.dsig)[:, None, None] * jnp.asarray(ps)[None] / 9.81 * 1004.6).sum(0)) * W).sum() / W.sum()), 1)
      Wg = np.cos(np.radians(np.asarray(M.LA))); gm = lambda X: float((np.asarray(X) * Wg).sum() / Wg.sum())
      r['globe'] = dict(rain_Wm2=round(gm(d['rain']) * 2.5e6, 1), LH=round(gm(d['E']) * 2.5e6, 1), SH=round(gm(d['H']), 1),
                        radcol=round(gm((d['rad']['heating'] * jnp.asarray(M.dsig)[:, None, None] * jnp.asarray(ps)[None] / 9.81 * 1004.6).sum(0)), 1) if 'rad' in d else None,
                        physcol=round(gm((tend['T'] * jnp.asarray(M.dsig)[:, None, None] * jnp.asarray(ps)[None] / 9.81 * 1004.6).sum(0)), 1),
                        olr=round(gm(d['rad']['olr']), 1) if 'rad' in d else None)
      r['olr_trop'] = round(float((np.asarray(d['rad']['olr']) * W).sum() / W.sum()), 1) if 'rad' in d else None
      res.append(r); ALL[VN] = res; json.dump(ALL, open(OUT, 'w'))
      print(VN, key, 'd5 T bias tropics', dict(zip(LEV.astype(int).tolist(), np.round(r['d5']['tropics']['T'], 2).tolist())), 'rad', r.get('rad_Kday'), 'rain', r['rain_trop_mmday'], 'olr', r['olr_trop'], 'lwdn', r['lw_dn_sfc_trop'], 'swsfc', r['sw_sfc_trop'], 'LH', r['lh_trop'], 'SH', r['sh_trop'], 'radcol', r.get('rad_col_Wm2'), 'GLOBE', r['globe'], flush=True)
  ALL[VN] = res; json.dump(ALL, open(OUT, 'w'))
  if res:
      for reg in REG:
          print(VN, reg, 'mean d5 T bias', dict(zip(LEV.astype(int).tolist(), np.round(np.mean([x['d5'][reg]['T'] for x in res], 0), 2).tolist())))
          print(VN, reg, 'mean d5 q bias g/kg', dict(zip(LEV.astype(int).tolist(), np.round(np.mean([x['d5'][reg]['q'] for x in res], 0) * 1000, 2).tolist())))
      print(VN, 'rad K/day by sigma', dict(zip(res[0]['sig'], np.round(np.mean([x['rad_Kday'] for x in res if 'rad_Kday' in x], 0), 2).tolist())))
      print(VN, 'phys K/day by sigma', dict(zip(res[0]['sig'], np.round(np.mean([x['phys_dT_Kday'] for x in res], 0), 2).tolist())))
