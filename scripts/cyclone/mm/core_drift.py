"""Core drift test (5 Nov 22:45): physics OFF, 24 h, global area-mean z500 change (the real atmosphere's global-mean z500
changes by ~1 m/day at most), plus global mean surface pressure (mass) and mass-weighted T. One ingredient changed at a
time: DFI on/off, diffusion strength (diff_x), moisture (dry start), time step. python core_drift.py START_NPZ GRID"""
import sys, json, datetime as dt, numpy as np, jax.numpy as jnp
sys.path.insert(0, '.'); import mm2, landinit
Z = dict(np.load(sys.argv[1])); GR = sys.argv[2] if len(sys.argv) > 2 else 'T42'
V3 = [str(v) for v in Z['v3']]; V2 = [str(v) for v in Z['v2']]
VARS = [('base (rd_si, DFI)', {}, True, False, None), ('no DFI', {}, False, False, None), ('weak diffusion x10', {'diff_x': 10.0}, True, False, None),
        ('dry start (q=0)', {}, True, True, None), ('dt half', {}, True, False, 0.5), ('mono off', {'mono': False}, True, False, None), ('cubic vertical', {'sl_vcubic': 1}, True, False, None)]
if len(sys.argv) > 3: VARS = [v for v in VARS if v[0] in sys.argv[3].split('|')]
for k in range(len(Z['times'])):
    key = str(Z['times'][k]); t0 = dt.datetime.strptime(key, '%Y-%m-%dT%H'); f2 = Z['f2'][k]
    for name, extra, dfi, dry, dtf in VARS:
        f3 = {v: np.array(Z['f3'][k, V3.index(v)]) for v in V3}
        if dry: f3['specific_humidity'][:] = 0.0
        S = dict({'rad': 'radcloud', 'rad_every': 2, 'rd_si': 1, 'phys_off': True}, **extra)
        M = mm2.Model(GR, 32, (mm2.DT_MAX[GR] * dtf) if dtf else None, S)
        st, cr = M.init(f3, Z['levs'], Z['lats'], Z['lons'], f2[V2.index('surface_pressure')], f2[V2.index('geopotential_at_surface')] / 9.80616,
                        f2[V2.index('sea_surface_temperature')], f2[V2.index('land_sea_mask')], when=t0, **landinit.land_kwargs(f2, V2))
        M.build(t0)
        if dfi: st = M.dfi(st)
        hor = M.coords.horizontal; w = np.cos(np.radians(M.lat))[None, :]; wm = lambda F: float((np.asarray(F) * w).sum() / (w.sum() * F.shape[0]))
        def masst(s):
            ps = np.asarray(jnp.exp(hor.to_nodal(s.log_surface_pressure))[0]) / M.PA
            T = (np.asarray(hor.to_nodal(s.temperature_variation)) + np.asarray(M.ref_t)[:, None, None]) / M.K
            dsig = np.diff(np.asarray(M.coords.vertical.boundaries))
            return wm(ps) / 100, wm((T * dsig[:, None, None]).sum(0))
        out = M.run_wx(st, cr, 24, 24)
        p0, t0m = masst(st); s24, _ = mm2.integrate(M, st, cr, 24); p1, t1m = masst(s24)
        z0, z1 = wm(out['z500'][0]), wm(out['z500'][1])
        print(f'{key} {GR} {name:22s} global z500 {z0:8.1f} -> {z1:8.1f}  change {z1 - z0:+6.2f} m/day | ps {p0:.3f} -> {p1:.3f} hPa ({p1-p0:+.3f}), mass-weighted T {t0m:.3f} -> {t1m:.3f} K ({t1m-t0m:+.3f})', flush=True)
