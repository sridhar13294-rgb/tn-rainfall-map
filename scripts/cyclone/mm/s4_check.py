"""S4 (12 Nov): lowest-level cooling with physics OFF (-0.8..-1.1 K/day in both cores, 5 Nov). Where is it - sea/land, tropics/extratropics,
which levels - and is it in ERA5 (o_t925 day0 -> day1)? Physics off, T42, 20 min, DFI as in the forecast (and without: env NODFI).
python s4_check.py LIB MOIST_TRUTH STARTS"""
import sys, os, datetime as dt, numpy as np, jax.numpy as jnp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'analysis'))
import mm2, landinit, wxscore as WS
from dinosaur import primitive_equations
Z = dict(np.load(sys.argv[1])); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
MT = dict(np.load(sys.argv[2])); DI = {str(d): i for i, d in enumerate(MT['days'])}
M = mm2.Model('T42', 32, 20.0, {'rad': 'radcloud', 'rad_every': 2, 'cmt_mf': 1.0, 'rd_si': 1.0, 'phys_off': True}); hor = M.coords.horizontal
LA = np.asarray(M.LA); W = np.cos(np.radians(LA)); sig = np.asarray(M.sig)
tla = np.linspace(-90, 90, 121); TLA = np.repeat(tla[:, None], 240, 1); TW = np.cos(np.radians(TLA))
def Tof(st):
    aux = primitive_equations.compute_diagnostic_state_sigma(st.replace(tracers={}), M.coords)
    return np.asarray((aux.temperature_variation + M.ref_t[:, None, None]) / M.K, float), np.asarray(jnp.exp(hor.to_nodal(st.log_surface_pressure))[0] / M.PA, float)
acc = []
for k in [int(x) for x in sys.argv[3].split(',')]:
    t0 = dt.datetime.strptime(TT[k], '%Y-%m-%dT%H'); f2 = Z['f2'][k]; f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
    st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                    f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
    M.build(t0)
    T_raw, _ = Tof(st)
    if not os.environ.get('NODFI'): st = M.dfi(st)
    T0, ps0 = Tof(st); st1, cr = mm2.integrate(M, st, cr, 24); T1, ps1 = Tof(st1)
    land = np.asarray(M.land); trop = np.abs(LA) <= 30; zs = np.asarray(M.zs)
    g = lambda X, m: float((X * W * m).sum() / (W * m).sum())
    masks = {'globe': np.ones_like(land, bool), 'sea': ~land, 'land<500m': land & (zs < 500), 'land>1500m': land & (zs > 1500), 'trop sea': trop & ~land, 'extratrop sea': ~trop & ~land}
    r = {nm: [g(T1[i] - T0[i], m) for i in range(len(sig))] for nm, m in masks.items()}
    r['dfi'] = [g(T0[i] - T_raw[i], masks['globe']) for i in range(len(sig))]
    j0, j1 = DI.get(t0.strftime('%Y-%m-%dT%H')), DI.get((t0 + dt.timedelta(days=1)).strftime('%Y-%m-%dT%H'))
    e = (MT['o_t925'][j1] - MT['o_t925'][j0]).astype(float) if (j0 is not None and j1 is not None) else None
    r['era5_t925'] = float(np.nansum(e * TW) / np.nansum(TW * np.isfinite(e))) if e is not None else np.nan
    r['dps'] = g(ps1 - ps0, masks['globe']) / 100
    acc.append(r); print(TT[k], 'ERA5 t925 day0->1 %+.2f K, model global ps change %+.3f hPa' % (r['era5_t925'], r['dps']), flush=True)
print('\nmean physics-off T change over 24 h (K), by level (sigma > 0.6); DFI column = change made by the initialisation filter')
names = ['globe', 'sea', 'land<500m', 'land>1500m', 'trop sea', 'extratrop sea', 'dfi']
print('  sigma  ' + ' '.join(f'{n:>13s}' for n in names))
for i in range(len(sig)):
    if sig[i] < 0.6: continue
    print(f'  {sig[i]:.3f}  ' + ' '.join(f'{np.mean([r[n][i] for r in acc]):+13.2f}' for n in names))
print('ERA5 global t925 day0->1 mean %+.2f K' % np.nanmean([r['era5_t925'] for r in acc]))
