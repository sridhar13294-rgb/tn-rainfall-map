"""Independent clear-sky LW reference for the same column (lw_column.json: AFGL tropical on mm2's 32 sigma levels) with
RRTMGP (pyrte_rrtmgp; Pincus et al. 2019 - accurate to ~1 W/m2 / ~0.1 K/day vs LBLRTM). Gases: H2O, CO2 420 ppm, O3 (AFGL
tropical-like profile), CH4 1.9 ppm, N2O 0.33 ppm. Prints heating by level beside MEGAM's. Runs on Kaggle (needs pip + internet).
python rrtmgp_reference.py"""
import sys, os, json, subprocess, numpy as np
H = os.path.dirname(os.path.abspath(__file__)); C = json.load(open(os.path.join(H, 'lw_column.json')))
p, dp, T, q = (np.array(C[k]) for k in ('p', 'dp', 'T', 'q')); ps, Ts = C['ps'], C['Ts']
pi = np.concatenate([[0.0], np.cumsum(dp)]); pi[0] = max(pi[0], 1.0)            # interfaces, top -> bottom
Ti = np.interp(np.log(pi), np.log(p), T); Ti[-1] = T[-1] + (T[-1] - T[-2]) * 0.5; Ti[0] = T[0]
h2o = q / (1 - q) / 0.622                                                        # vmr
o3 = np.interp(np.log(p), np.log([1e2, 1e3, 3e3, 1e4, 3e4, 1e5]), [1e-6, 8e-6, 8e-6, 2e-7, 5e-8, 3e-8])
try:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'pyrte_rrtmgp'], check=True)
    import pyrte_rrtmgp, xarray as xr
    print('pyrte_rrtmgp', getattr(pyrte_rrtmgp, '__version__', '?'), [m for m in dir(pyrte_rrtmgp) if not m.startswith('_')])
    from pyrte_rrtmgp import rrtmgp_gas_optics
    from pyrte_rrtmgp.data_types import GasOpticsFiles, ProblemTypes
    from pyrte_rrtmgp.rte_solver import rte_solve
    go = rrtmgp_gas_optics.load_gas_optics(gas_optics_file=GasOpticsFiles.LW_G256)
    atm = xr.Dataset(dict(pres_layer=(('site', 'layer'), p[None]), temp_layer=(('site', 'layer'), T[None]),
                          pres_level=(('site', 'level'), pi[None]), temp_level=(('site', 'level'), Ti[None]),
                          surface_temperature=(('site',), np.array([Ts])),
                          h2o=(('site', 'layer'), h2o[None]), co2=(('site', 'layer'), np.full((1, len(p)), 420e-6)),
                          o3=(('site', 'layer'), o3[None]), ch4=(('site', 'layer'), np.full((1, len(p)), 1.9e-6)),
                          n2o=(('site', 'layer'), np.full((1, len(p)), 0.33e-6)), co=(('site', 'layer'), np.zeros((1, len(p)))),
                          n2=(('site', 'layer'), np.full((1, len(p)), 0.781)), o2=(('site', 'layer'), np.full((1, len(p)), 0.209))))
    atm['surface_emissivity'] = (('site',), np.array([0.98]))   # MEGAM uses a black sea surface? (reported below)
    try:
        go.compute_gas_optics(atm, problem_type=ProblemTypes.LW_ABSORPTION)
    except TypeError:
        atm = go.compute_gas_optics(atm, problem_type=ProblemTypes.LW_ABSORPTION, add_to_input=True) or atm
    fl = rte_solve(atm, add_to_input=False)
    print('flux keys', list(fl.data_vars))
    up = np.asarray(fl['lw_flux_up']).ravel(); dn = np.asarray(fl['lw_flux_down']).ravel()
    net = up - dn                                                                  # upward net at interfaces (top -> bottom)
    heat = (net[1:] - net[:-1]) * 9.80616 / (1004.6 * dp) * 86400 * -1 * -1       # dT/dt = g/cp dF_net/dp, F_net upward: cooling when net grows upward
    heat = -(net[:-1] - net[1:]) * 9.80616 / (1004.6 * dp) * 86400
    sig = p / ps; m8 = sig >= 0.79; mm = lambda h: float((h * dp * m8).sum() / (dp * m8).sum())
    fit = np.array(C['fitted']); s15 = np.array(C['ssm15']); s10 = np.array(C['ssm10'])
    print(f'OLR rrtmgp {up[0]:.1f}  surface down {dn[-1]:.1f}')
    print(f'{"hPa":>6s} {"RRTMGP":>8s} {"MEGAM":>8s} {"SSMx1.5":>8s} {"SSMx1.0":>8s}')
    for k in range(10, len(p)): print(f'{p[k]/100:6.0f} {heat[k]:+8.2f} {fit[k]:+8.2f} {s15[k]:+8.2f} {s10[k]:+8.2f}')
    print(f'800-1000 hPa mass-mean K/day: RRTMGP {mm(heat):+.2f} MEGAM {mm(fit):+.2f} SSMx1.5 {mm(s15):+.2f} SSMx1.0 {mm(s10):+.2f}')
    m83 = (p >= 30000) & (p <= 80000); m3 = lambda h: float((h * dp * m83).sum() / (dp * m83).sum())
    print(f'300-800 hPa mass-mean K/day: RRTMGP {m3(heat):+.2f} MEGAM {m3(fit):+.2f}')
except Exception as e:
    import traceback; traceback.print_exc()
    try:
        import pyrte_rrtmgp, pkgutil; print('modules:', [m.name for m in pkgutil.walk_packages(pyrte_rrtmgp.__path__, 'pyrte_rrtmgp.')])
        import inspect, pyrte_rrtmgp.rrtmgp_gas_optics as g; print([n for n in dir(g) if not n.startswith('_')])
    except Exception as e2: print('no pyrte', e2)
