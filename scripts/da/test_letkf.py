"""Tests for letkf.py on the CPU (numpy; run: python test_letkf.py, or pytest). A few seconds to ~1 min.
1. Exactness: one local problem with every observation at weight 1 gives exactly the Kalman-filter analysis with the
   ensemble's sample covariance (mean and covariance), for a linear observation operator.
2. Gaspari-Cohn: 1 at 0, 0 beyond 2c, smooth and monotone; sphere localisation finds the right neighbours.
3. Lorenz-96 (40 variables, F = 8): LETKF with 20 members, localisation and RTPS keeps the analysis error far below the
   observation error and the free run (all variables observed every 0.05 time units, sigma_o = 1; and every second
   variable). Published numbers for this set-up: analysis RMSE ~0.18-0.20 (all observed); here ~0.21.
4. Under jax (when installed): the jitted chunked solver gives the numpy result."""
import os, sys, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import letkf as LK

def test_kalman_exact():
    rs = np.random.default_rng(1); K, N, P = 12, 6, 5
    Xb = rs.standard_normal((K, N)) + np.arange(N)
    H = rs.standard_normal((P, N)); R = np.diag(rs.uniform(0.3, 1.5, P)); y = rs.standard_normal(P)
    xm = Xb.mean(0); Xp = (Xb - xm).T                                            # [N, K]
    Pb = Xp @ Xp.T / (K - 1); Kg = Pb @ H.T @ np.linalg.inv(H @ Pb @ H.T + R)
    xa_kf = xm + Kg @ (y - H @ xm); Pa_kf = (np.eye(N) - Kg @ H) @ Pb
    Yb = Xb @ H.T; Yp = Yb - Yb.mean(0); d = y - Yb.mean(0)
    idx = np.arange(P)[None].astype(np.int32); loc = np.ones((1, P), np.float32)
    T = LK.Solver().weights(Yp, d, 1 / np.diag(R), idx, loc)                     # one local problem
    Xa = np.stack([LK.apply_weights(Xb[:, i:i + 1], T)[:, 0] for i in range(N)], 1)  # same T for every variable
    am = Xa.mean(0); Ap = (Xa - am).T
    assert np.allclose(am, xa_kf, atol=1e-5), np.abs(am - xa_kf).max()
    assert np.allclose(Ap @ Ap.T / (K - 1), Pa_kf, atol=1e-5)
    # mean-preserving symmetric square root: analysis perturbations sum to zero
    assert np.allclose((Xa - am).sum(0), 0, atol=1e-6)

def test_gaspari_cohn():
    r = np.linspace(0, 2.5, 501); g = LK.gaspari_cohn(r)
    assert abs(g[0] - 1) < 1e-12 and np.all(g[r >= 2] == 0) and np.all(np.diff(g) <= 1e-12)
    assert abs(LK.gaspari_cohn(np.array([1.0]))[0] - 0.2083) < 1e-3
    assert np.abs(np.diff(g)).max() < 0.02                                       # continuous
    # sphere: points 0, 500, 1500 km east along the equator; c = 500 km -> weights 1, 0.21, 0
    olon = np.array([0.0, 500, 1500]) / 111.195; idx, loc = LK.local_obs_sphere(np.array([0.0]), np.array([0.0]), np.zeros(3), olon, 500.0, 5)
    w = dict(zip(idx[0].tolist(), loc[0].tolist()))
    assert abs(w[0] - 1) < 1e-6 and abs(w[1] - 0.2083) < 2e-3 and 2 not in w

# ---------------------------------------------------------------------------------------------------- Lorenz-96
def l96_tend(x, F=8.0):
    return (np.roll(x, -1, -1) - np.roll(x, 2, -1)) * np.roll(x, 1, -1) - x + F
def l96_step(x, dt=0.05, F=8.0):
    k1 = l96_tend(x, F); k2 = l96_tend(x + dt / 2 * k1, F); k3 = l96_tend(x + dt / 2 * k2, F); k4 = l96_tend(x + dt * k3, F)
    return x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)

def run_l96(K=20, every=1, c=5.0, alpha=0.2, rho=1.0, ncyc=600, spin=100, seed=0, xp=np, sigo=1.0, adaptive=False):
    rs = np.random.default_rng(seed); N = 40
    x = 8.0 + rs.standard_normal(N)
    for _ in range(1000): x = l96_step(x)                                        # truth on the attractor
    clim = []; xx = x.copy()
    for _ in range(2000): xx = l96_step(xx); clim.append(xx)
    E = np.array(clim)[rs.integers(0, 2000, K)]                                   # climatological start
    free = E.mean(0).copy()
    opos = np.arange(0, N, every); idx, loc = LK.local_obs_ring(N, opos, c, 64); rinv = np.full(len(opos), 1 / sigo ** 2)
    S = LK.Solver(xp=xp, chunk=64); ea, ef, sp = [], [], []; r = rho
    for t in range(ncyc):
        x = l96_step(x); E = l96_step(E); free = l96_step(free)
        y = x[opos] + sigo * rs.standard_normal(len(opos))
        Yb = E[:, opos]; Yp = Yb - Yb.mean(0); d = y - Yb.mean(0)
        if adaptive: r = LK.adaptive_inflation(d, Yp, rinv, prev=r, lo=1.0, hi=1.5)
        T = np.asarray(S.weights(Yp, d, rinv, idx, loc, rho=r))
        Ea = LK.apply_weights(E, T); E = LK.rtps(E, Ea, alpha)
        if t >= spin:
            ea.append(np.sqrt(((E.mean(0) - x) ** 2).mean())); ef.append(np.sqrt(((free - x) ** 2).mean())); sp.append(np.sqrt(E.var(0, ddof=1).mean()))
    return float(np.mean(ea)), float(np.mean(ef)), float(np.mean(sp))

def test_l96_all_observed():
    ea, ef, sp = run_l96()
    print('L96 all obs: analysis RMSE %.3f  spread %.3f  free run %.3f  (sigma_o 1)' % (ea, sp, ef))
    assert ea < 0.25 and ef > 3.0 and 0.6 * ea < sp < 1.6 * ea

def test_l96_half_observed():
    ea, ef, sp = run_l96(every=2, c=4.0, alpha=0.3)
    print('L96 every 2nd obs: analysis RMSE %.3f  spread %.3f  free run %.3f' % (ea, sp, ef))
    assert ea < 0.45 and ef > 3.0

def test_l96_adaptive():
    ea, ef, sp = run_l96(alpha=0.0, adaptive=True)
    assert ea < 0.30
    print('L96 adaptive inflation (no RTPS): analysis RMSE %.3f  spread %.3f' % (ea, sp))

def test_jax_matches_numpy():
    try:
        import jax, jax.numpy as jnp; jax.config.update('jax_enable_x64', False)
    except ImportError:
        print('jax not installed: jax-equals-numpy check skipped'); return
    rs = np.random.default_rng(3); K, P, n, Pm = 16, 300, 500, 40
    Yp = rs.standard_normal((K, P)).astype(np.float32); Yp -= Yp.mean(0); d = rs.standard_normal(P).astype(np.float32)
    rinv = rs.uniform(0.5, 2, P).astype(np.float32); idx = rs.integers(0, P + 1, (n, Pm)).astype(np.int32); loc = rs.uniform(0, 1, (n, Pm)).astype(np.float32)
    Tn = LK.Solver(np, 128).weights(Yp, d, rinv, idx, loc, 1.1); Tj = np.asarray(LK.Solver(jnp, 128).weights(Yp, d, rinv, idx, loc, 1.1))
    assert np.allclose(Tn, Tj, atol=2e-4), np.abs(Tn - Tj).max()
    print('jax == numpy: max diff %.2e' % np.abs(Tn - Tj).max())

if __name__ == '__main__':
    import time
    for f in [test_kalman_exact, test_gaspari_cohn, test_l96_all_observed, test_l96_half_observed, test_l96_adaptive, test_jax_matches_numpy]:
        t = time.time(); f(); print('ok', f.__name__, '%.1fs' % (time.time() - t))
