"""Equation-to-code check on the GPU code path (jax.numpy), D1 + D2: the same known columns as l2_check.py, computed
with xp=numpy and xp=jax.numpy through radcloud.radiation (cld_pdf) and cloudtop.cloud_top_entrainment; prints the
largest difference per field. python l2_jax.py"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jax, jax.numpy as jnp
import cloud_derivation as C, radcloud as RC, cloudtop
r = 0.99; T = C.T0 - 2.4
z = np.zeros_like(C.p); z[-1] = C.RD * T[-1] / C.G * np.log(C.ps / C.p[-1])
for k in range(len(C.p) - 2, -1, -1): z[k] = z[k + 1] + C.RD * 0.5 * (T[k] + T[k + 1]) / C.G * np.log(C.p[k + 1] / C.p[k])
S = lambda a: np.asarray(a, np.float32).reshape(-1, 1, 1)
worst = {}
for kt in C.DECK:
    q = np.minimum(C.q0, 0.75 * C.qs_(T))
    for k in range(kt + 1, C.K(0.95) + 1): q[k] = 0.85 * C.qs_(T)[k]
    q[kt] = r * C.qs_(T)[kt]; cond = np.zeros_like(T); cond[kt] = 1.32 * 4 * C.CP / C.LV / 86400
    args = (S(T), S(q), S(C.p), S(C.dp), np.array([[C.ps]], np.float32), np.array([[301.0]], np.float32), np.array([[True]]), np.array([[0.5]], np.float32))
    out = {}
    for name, xp in (('np', np), ('jax', jnp)):
        a = [xp.asarray(x) for x in args]
        R = RC.radiation(*a, ls_cond=xp.asarray(S(cond)), xp=xp, prm=dict(pdf=1.0), clear_sky=True)
        lwc = R['lw_heating'] - R['lw_heating_clr']
        dT, dq, d = cloudtop.cloud_top_entrainment(a[0], a[1], a[2], a[4][0] * 0 + xp.asarray([[C.ps]], dtype=xp.float32), xp.asarray(S(z)), xp.asarray(S(C.mass)), lwc, R['cloud'], 0.54, 1200.0, xp, no_deep=xp.asarray([[True]]))
        out[name] = dict(heat=np.asarray(R['heating']), cloud=np.asarray(R['cloud']), lwc=np.asarray(lwc), dT=np.asarray(dT), dq=np.asarray(dq), kt=int(np.asarray(d['kt'])[0, 0]))
    for f in ('heat', 'cloud', 'lwc', 'dT', 'dq'):
        a, b = out['np'][f], out['jax'][f]; rel = float(np.max(np.abs(a - b)) / max(np.max(np.abs(a)), 1e-30)); worst[f] = max(worst.get(f, 0), rel)
    print(f"deck top {C.sig[kt]:.3f}: cloud-top index np {out['np']['kt']} jax {out['jax']['kt']}; entrainment heat np {out['np']['dT'].max()*86400:+.4f} jax {out['jax']['dT'].max()*86400:+.4f} K/day; energy jax {(out['jax']['dT'][:,0,0]*C.CP*C.mass).sum():+.2e} W/m2")
print('largest relative difference numpy vs jax:', {k: f'{v:.1e}' for k, v in worst.items()}, '-> PASS' if max(worst.values()) < 1e-3 else '-> FAIL')
