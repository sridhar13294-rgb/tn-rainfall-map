"""Dynamical-core jet check against an ANALYTIC reference (12 Nov): Jablonowski-Williamson (2006) steady state.
The JW state is an exact balanced solution with two 35 m/s mid-latitude jets: a perfect core keeps u unchanged.
We run MEGAM's core configuration (semi-Lagrangian, sigma levels, off-centering 0.05, the same horizontal diffusion filter,
the same step) with physics OFF and measure the jet-peak loss per day. Variants (env VARIANTS json list of [name, dict]):
  vcubic (0/1), mono (0/1), oc (off-centering), diff (0/1), dt_min, ref ('mm2' = isothermal 250 K as in mm2, 'jw' = JW profile),
  iters (departure iterations), NL (levels), grid.
Output: jet peak (max over latitudes of zonal-mean u at the level nearest sigma 0.25) at days 0..DAYS, and the change.
"""
import os, sys, json, functools, time
import numpy as np, jax, jax.numpy as jnp
sys.path.insert(0, os.path.dirname(__file__))
from dinosaur import primitive_equations, primitive_equations_states, time_integration, coordinate_systems, spherical_harmonic, sigma_coordinates, xarray_utils
from dinosaur import scales
import mm2
units = scales.units
DAYS = int(os.environ.get('DAYS', 3))
VARIANTS = json.loads(os.environ.get('VARIANTS', '[["mm2 default", {}]]'))

def run(name, o):
    grid = o.get('grid', 'T42'); NL = int(o.get('NL', 32)); dt_min = float(o.get('dt_min', 60.0 if grid == 'T42' else 20.0))
    M = mm2.Model(grid=grid, layers=NL, dt_min=dt_min, set_={'rd_si': 1})
    coords = M.coords; ps = M.ps; hor = coords.horizontal
    fn, aux = primitive_equations_states.steady_state_jw(coords, ps)
    st = fn()
    oro = hor.to_modal(aux[xarray_utils.OROGRAPHY])
    ref = aux[xarray_utils.REF_TEMP_KEY] if o.get('ref', 'mm2') == 'jw' else np.full(NL, 250.0) * M.K
    # JW gives T' relative to ITS reference; re-express relative to the chosen reference
    Tfull = hor.to_nodal(st.temperature_variation) + aux[xarray_utils.REF_TEMP_KEY][:, None, None]
    st = st.replace(temperature_variation=hor.to_modal(Tfull - np.asarray(ref)[:, None, None]))
    kw = dict(monotone_tracers=True, departure_iterations=int(o.get('iters', 1)), monotone_dynamics=bool(o.get('mono', 1)))
    if o.get('vcubic', 0): kw['vertical_interpolation_order'] = 'cubic'
    eq = primitive_equations.SemiLagrangianPrimitiveEquations(np.asarray(ref, np.float32), oro, coords, ps, **kw)
    res = hor.latitude_nodes / 128; tau = ps.nondimensionalize(8.6 / (2.4 ** np.log2(res)) * units.hours)
    filt = [time_integration.horizontal_diffusion_step_filter(hor, dt=M.dt, tau=tau, order=2)] if o.get('diff', 1) else []
    step = time_integration.step_with_filters(time_integration.semi_lagrangian_crank_nicolson_rk2(eq, M.dt, off_centering=float(o.get('oc', 0.05)), warm_start_corrector=True), filt)
    nday = int(round(86400.0 / M.dt_s))
    @jax.jit
    def day(s):
        return jax.lax.fori_loop(0, nday, lambda i, x: step(x), s)
    k = int(np.argmin(np.abs(M.sig - 0.25)))
    def jet(s):
        aux_ = primitive_equations.compute_diagnostic_state_sigma(s, coords)
        u = np.asarray(aux_.cos_lat_u[0][k]) / np.asarray(hor.cos_lat) / M.MPS
        zm = u.mean(0); nh = M.lat > 0
        return float(zm[nh].max()), float(zm[~nh].max()), float(np.abs(u - zm).max())
    out = [jet(st)]; t0 = time.time()
    for d in range(DAYS):
        st = day(st); out.append(jet(st))
    j0 = out[0][0]
    print(f'{name:38s} sig {M.sig[k]:.3f} dt {dt_min:.0f} min | NH jet ' + ' '.join(f'{x[0]:.2f}' for x in out) +
          f' | change/day {(out[-1][0] - j0) / DAYS:+.3f} | max |u-zonal| {out[-1][2]:.3f} | {time.time() - t0:.0f}s', flush=True)
    return out

if __name__ == '__main__':
    R = {}
    for name, o in VARIANTS:
        try: R[name] = run(name, o)
        except Exception as e: print(name, 'FAILED', repr(e)[:300], flush=True)
    json.dump(R, open(os.environ.get('OUT', '/tmp/claude-0/jw_out.json'), 'w'))
