"""IFS Part III item D1 offline test (5 Nov 22:20): spurious temperature tendency from horizontal diffusion acting on
SIGMA surfaces. On a sigma level over steep terrain T varies with surface pressure even in an atmosphere with no
horizontal T gradient on pressure surfaces; diffusing that terrain imprint creates heating/cooling (IFS applies the
diffusion to T - Tc, Simmons 1987, to avoid it). Measure: apply MEGAM's own step filter (mm2.build -> M.filt) to
Tterr = Tref(sigma * ps) built from the GLOBAL-MEAN T(p) profile of a real start and the real model ps, i.e. the part of
T that is pure terrain imprint, and report the tendency (K/day) over Tibet (28-38 N 78-100 E) by level.
Registered threshold (rootcause / ifs_review 18:20): material if > 0.5 K/day over Tibet.
python d1_sigma_diffusion.py START_NPZ GRID"""
import sys, datetime as dt, numpy as np, jax.numpy as jnp
sys.path.insert(0, '.'); import mm2, landinit
Z = dict(np.load(sys.argv[1])); GR = sys.argv[2] if len(sys.argv) > 2 else 'T85'
V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]; levs = np.asarray(Z['levs'], float)
M = mm2.Model(GR, 32, None, {'rad': 'radcloud', 'rad_every': 2, 'rd_si': 1})
k = 1; key = str(Z['times'][k]); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: Z['f3'][k, V3.index(v)] for v in V3}
st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
M.build(t0); hor = M.coords.horizontal
ps = np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0]) / M.PA                       # Pa, model terrain
lat_w = np.cos(np.radians(np.asarray(Z['lats'], float)))
Tm = np.array([(f3['temperature'][i] * lat_w[:, None]).sum() / (lat_w.sum() * f3['temperature'].shape[-1]) for i in range(len(levs))])  # global-mean T(p)
sig = np.asarray(M.sig); P = sig[:, None, None] * ps[None]                                          # Pa on sigma levels
Tterr = np.interp(np.log(P.ravel()), np.log(levs * 100.0), Tm).reshape(P.shape)                     # terrain imprint only
ref = np.asarray(M.ref_t)[:, None, None] / M.K
st2 = st.replace(temperature_variation=hor.to_modal((jnp.asarray(Tterr) - ref) * M.K)) if hasattr(st, 'replace') else None
import dataclasses
st2 = dataclasses.replace(st, temperature_variation=hor.to_modal(jnp.asarray((Tterr - ref) * M.K)))
out = M.filt(st2, st2) if M.filt.__code__.co_argcount >= 2 else M.filt(st2)
T0n = np.asarray(hor.to_nodal(st2.temperature_variation)) / M.K; T1n = np.asarray(hor.to_nodal(out.temperature_variation)) / M.K
steps_day = 86400.0 / M.dt_s; tend = (T1n - T0n) * steps_day                                        # K/day per level
LO, LA = M.LO, M.LA; box = (LA >= 28) & (LA <= 38) & (LO >= 78) & (LO <= 100); plains = (LA >= 20) & (LA <= 27) & (LO >= 75) & (LO <= 88)
print(GR, key, 'dt', M.dt_s, 's  | spurious T tendency from sigma-surface diffusion of the terrain imprint (K/day)')
for i in range(0, len(sig), 2):
    t = tend[i]; print(f'sigma {sig[i]:.3f}: Tibet mean {t[box].mean():+.3f} max|.| {np.abs(t[box]).max():.3f} | N-India plains mean {t[plains].mean():+.3f} | global max|.| {np.abs(t).max():.3f}')
print('Tibet column mean', round(float(tend[:, box].mean()), 3), 'K/day; max |tendency| anywhere', round(float(np.abs(tend).max()), 3))
