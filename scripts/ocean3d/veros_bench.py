"""Stage 2 (3-D ocean): can Veros (https://github.com/team-ocean/veros, JAX ocean model) run fast enough on a Kaggle
T4 / TPU to be coupled to the atmosphere model (scripts/cyclone/mm/mm2.py)?

python veros_bench.py all OUT.json [quick]     runs every configuration below in its own process (Veros reads its
                                                runtime settings - backend, device, precision - once, at import) and
                                                writes timings to OUT.json
python veros_bench.py one NAME OUT.json        one configuration (used by 'all')

Measured per configuration: set-up time (grid, topography, initial state from the setup's own forcing file), the first
step (includes JAX compilation), the mean of the following steps, and from that the wall-clock seconds per simulated day.
Also probes the ERA5 archive of WeatherBench2 (which surface flux variables exist) for the forced ocean-only run."""
import os, sys, json, time, subprocess, traceback

CFG = {   # name: (setup, override settings, backend, device, float type, simulated days)
    'g4_numpy_cpu': ('global_4deg', {}, 'numpy', 'cpu', 'float64', 10),
    'g4_jax_gpu64': ('global_4deg', {}, 'jax', 'gpu', 'float64', 20),
    'flex2_jax_gpu64': ('global_flexible', dict(nx=180, ny=80, nz=40, dt_mom=1800.0, dt_tracer=1800.0), 'jax', 'gpu', 'float64', 2),
    'flex2_jax_gpu32': ('global_flexible', dict(nx=180, ny=80, nz=40, dt_mom=1800.0, dt_tracer=1800.0), 'jax', 'gpu', 'float32', 2),
    'flex1_jax_gpu64': ('global_flexible', dict(nx=360, ny=160, nz=60, dt_mom=900.0, dt_tracer=900.0), 'jax', 'gpu', 'float64', 1),
    'flex1_jax_gpu32': ('global_flexible', dict(nx=360, ny=160, nz=60, dt_mom=900.0, dt_tracer=900.0), 'jax', 'gpu', 'float32', 1),
    'flex2_jax_cpu64': ('global_flexible', dict(nx=180, ny=80, nz=40, dt_mom=1800.0, dt_tracer=1800.0), 'jax', 'cpu', 'float64', 0.5),
}


def one(name, out):
    setup, over, backend, device, ftype, days = CFG[name]
    os.environ.update(VEROS_BACKEND=backend, VEROS_DEVICE=device, VEROS_FLOAT_TYPE=ftype, VEROS_DISKLESS_MODE='1',
                      VEROS_FORCE_OVERWRITE='1', VEROS_LOGLEVEL='warning')
    if backend == 'jax' and ftype == 'float64': os.environ['JAX_ENABLE_X64'] = '1'
    res = dict(name=name, setup=setup, override=over, backend=backend, device=device, float=ftype)
    t0 = time.time()
    if setup == 'global_4deg':
        from veros.setups.global_4deg import GlobalFourDegreeSetup as S
    else:
        from veros.setups.global_flexible import GlobalFlexibleResolutionSetup as S
    res['import_s'] = round(time.time() - t0, 1)                                       # includes the forcing download
    sim = S(override=over or None); t0 = time.time(); sim.setup(); res['setup_s'] = round(time.time() - t0, 1)
    st = sim.state; vs = st.variables; dt = float(st.settings.dt_tracer)
    res.update(nx=int(st.settings.nx), ny=int(st.settings.ny), nz=int(st.settings.nz), dt=dt)
    try:
        import jax; res['devices'] = str(jax.devices())
    except Exception: pass
    def sync():
        x = vs.temp
        if hasattr(x, 'block_until_ready'): x.block_until_ready()
    nsteps = max(3, int(round(days * 86400 / dt))); times = []
    for i in range(nsteps):
        t0 = time.time(); sim.step(st); sync(); times.append(time.time() - t0)
        if i == 0: res['first_step_s'] = round(times[0], 2)
        if sum(times) > 1500: break                                                   # keep every configuration under ~25 min
    rest = times[1:]; per = sum(rest) / len(rest)
    import numpy as np
    T = np.asarray(vs.temp[..., vs.tau]); m = np.asarray(vs.maskT) > 0
    res.update(steps=len(times), step_s=round(per, 4), s_per_model_day=round(per * 86400 / dt, 2),
               model_days_per_wall_hour=round(3600 / (per * 86400 / dt), 2), sst_range=[float(T[..., -1][m[..., -1]].min()), float(T[..., -1][m[..., -1]].max())],
               umax=float(np.abs(np.asarray(vs.u[..., vs.tau])).max()), finite=bool(np.isfinite(T).all()))
    json.dump(res, open(out, 'w'), indent=1); print(json.dumps(res), flush=True)


def probe_era5():
    """which ERA5 variables (in particular surface fluxes and stress) the WeatherBench2 archive offers."""
    out = {}
    for p in ['gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-240x121_equiangular_with_poles_conservative.zarr',
              'gs://weatherbench2/datasets/era5/1959-2023_01_10-6h-64x32_equiangular_conservative.zarr']:
        try:
            import xarray as xr
            d = xr.open_zarr(p, storage_options={'token': 'anon'}, chunks=None); out[p] = sorted(d.data_vars)
        except Exception as e: out[p] = 'failed ' + repr(e)[:300]
    return out


if __name__ == '__main__':
    if sys.argv[1] == 'one': one(sys.argv[2], sys.argv[3]); sys.exit(0)
    out = sys.argv[2]; quick = 'quick' in sys.argv[3:]; R = dict(started=time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()), runs={})
    names = list(CFG) if not quick else ['g4_numpy_cpu', 'flex2_jax_gpu32']
    for n in names:
        tmp = '/tmp/vb_%s.json' % n; t0 = time.time()
        try:
            r = subprocess.run([sys.executable, __file__, 'one', n, tmp], capture_output=True, text=True, timeout=2100)
            R['runs'][n] = json.load(open(tmp)) if r.returncode == 0 and os.path.exists(tmp) else dict(error=(r.stdout[-1500:] + r.stderr[-2500:]))
        except Exception as e: R['runs'][n] = dict(error=repr(e)[:500] + traceback.format_exc()[-500:])
        R['runs'][n]['wall_s'] = round(time.time() - t0, 1); print(n, json.dumps(R['runs'][n])[:600], flush=True)
        json.dump(R, open(out, 'w'), indent=1)
    R['era5_vars'] = probe_era5(); json.dump(R, open(out, 'w'), indent=1); print('done', flush=True)
