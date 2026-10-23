"""Local Ensemble Transform Kalman Filter (LETKF; Hunt, Kostelich & Szunyogh 2007, Physica D 230, 112-126).

Plain words: every grid column (and every vertical layer group in it) does its own small Kalman-filter analysis in the
K-dimensional space spanned by the ensemble members, using only the observations near it. Observations are down-weighted
smoothly with distance (Gaspari-Cohn), so there is no jump at the edge of the local region. The result for each local
problem is a K x K weight matrix: analysis member k = background mean + sum_j (background perturbation j) x W[j, k].

Array module: every function takes `xp` (numpy or jax.numpy) and uses no in-place writes, so the same code runs on the
CPU (tests, numpy) and on the GPU (jax; the chunk solve is jitted by `Solver`).

Shapes (K members, P observations, n local problems, Pm = max observations kept per local problem):
  Yp   [K, P]    observation-space perturbations  H(x_k) - mean_k H(x_k)
  d    [P]       innovations  y - mean_k H(x_k)
  rinv [P]       1 / sigma_o^2  (R diagonal)
  idx  [n, Pm]   observation indices per local problem; P (one past the end) = empty slot
  loc  [n, Pm]   localisation weight (0..1) for each slot; R-localisation: R^-1 -> loc x R^-1
Outputs: T [n, K, K] = W + wbar (the full transform; column k gives member k's weights)."""
import math, numpy as np

# ---------------------------------------------------------------------------------------------------- localisation
def gaspari_cohn(r, xp=np):
    """Gaspari & Cohn (1999) eq. 4.10, fifth-order piecewise rational; r = distance / c (half-width c, zero beyond 2c).
    Correlation-like: 1 at r=0, ~0.21 at r=1 (half the support)."""
    r = xp.abs(r)
    a = (((-0.25 * r + 0.5) * r + 0.625) * r - 5.0 / 3.0) * r ** 2 + 1.0
    b = ((((r / 12.0 - 0.5) * r + 0.625) * r + 5.0 / 3.0) * r - 5.0) * r + 4.0 - 2.0 / (3.0 * xp.maximum(r, 1e-12))
    return xp.where(r <= 1.0, a, xp.where(r < 2.0, b, 0.0))

REARTH_KM = 6371.0
def unit_xyz(lat, lon):
    la = np.radians(np.asarray(lat, float)); lo = np.radians(np.asarray(lon, float))
    return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)
def great_circle_km(chord):
    """chord length on the unit sphere -> great-circle distance in km."""
    return 2.0 * REARTH_KM * np.arcsin(np.clip(np.asarray(chord) / 2.0, 0.0, 1.0))

def local_obs_sphere(glat, glon, olat, olon, c_km, pmax, vdist=None, c_v=None, overt=None, gvert=None):
    """For each analysis point (glat, glon [n]) the up-to-pmax nearest observations within 2 c_km (great circle), and
    their Gaspari-Cohn weight. Vertical (optional): overt [P] obs vertical coordinate (ln sigma or ln p), gvert scalar or
    [n] the analysis point's; weight x GC(|dv| / c_v), obs beyond 2 c_v dropped *before* choosing the nearest pmax.
    Returns idx [n, pmax] int32 (P = empty) and loc [n, pmax] float32.  numpy + scipy (host side, once per cycle)."""
    from scipy.spatial import cKDTree
    olat = np.asarray(olat, float); olon = np.asarray(olon, float); P = len(olat); n = len(glat)
    keep = np.arange(P)
    if overt is not None and np.ndim(gvert) == 0:
        keep = keep[np.abs(np.asarray(overt)[keep] - gvert) < 2.0 * c_v]
    idx = np.full((n, pmax), P, np.int32); loc = np.zeros((n, pmax), np.float32)
    if len(keep) == 0: return idx, loc
    tree = cKDTree(unit_xyz(olat[keep], olon[keep]))
    rmax = 2.0 * np.sin(min(2.0 * c_km / REARTH_KM, math.pi) / 2.0) * 1.000001          # chord of 2c
    k = min(pmax, len(keep))
    dist, j = tree.query(unit_xyz(glat, glon), k=k, distance_upper_bound=rmax, workers=-1)
    dist = np.asarray(dist).reshape(n, k); j = np.asarray(j).reshape(n, k)
    ok = np.isfinite(dist) & (j < len(keep)); jj = np.where(ok, j, 0)
    w = gaspari_cohn(great_circle_km(np.where(ok, dist, 0.0)) / c_km) * ok
    if overt is not None:
        gv = gvert if np.ndim(gvert) == 0 else np.asarray(gvert)[:, None]
        w = w * gaspari_cohn((np.asarray(overt)[keep][jj] - gv) / c_v)
    idx[:, :k] = np.where(ok & (w > 0), keep[jj], P); loc[:, :k] = np.where(ok, w, 0.0).astype(np.float32)
    return idx, loc

def local_obs_ring(n_grid, opos, c, pmax):
    """Lorenz-96-style periodic 1-D grid: analysis points 0..n_grid-1, observation positions opos [P] (grid units)."""
    opos = np.asarray(opos, float); P = len(opos); g = np.arange(n_grid, dtype=float)[:, None]
    dd = np.abs(g - opos[None]); dd = np.minimum(dd, n_grid - dd); w = gaspari_cohn(dd / c)
    order = np.argsort(-w, 1)[:, :pmax]; ws = np.take_along_axis(w, order, 1)
    idx = np.where(ws > 0, order, P).astype(np.int32); return idx, ws.astype(np.float32)

# ---------------------------------------------------------------------------------------------------- the local solve
def transform(Yl, dl, rl, rho=1.0, xp=np):
    """Batched LETKF solve. Yl [n, Pm, K] local obs perturbations, dl [n, Pm] innovations, rl [n, Pm] localised R^-1
    (0 for empty slots). rho: multiplicative prior inflation (scalar or [n]). Returns T [n, K, K] = W + wbar 1^T."""
    K = Yl.shape[-1]
    C = xp.swapaxes(Yl * rl[..., None], -1, -2)                                   # [n, K, Pm] = Yb^T R^-1
    rho = xp.asarray(rho, Yl.dtype)
    rho_ = rho[..., None, None] if rho.ndim else rho
    A = (K - 1) / rho_ * xp.eye(K, dtype=Yl.dtype) + C @ Yl                       # [n, K, K]
    lam, Q = xp.linalg.eigh(A)
    lam = xp.maximum(lam, 1e-6 * (K - 1))
    Pa = (Q / lam[..., None, :]) @ xp.swapaxes(Q, -1, -2)                         # (A)^-1
    W = (Q * xp.sqrt((K - 1) / lam)[..., None, :]) @ xp.swapaxes(Q, -1, -2)       # sqrt((K-1) Pa), symmetric
    wbar = (Pa @ (C @ dl[..., None]))[..., 0]                                     # [n, K]
    return W + wbar[..., :, None]

def gather_local(Yp, d, rinv, idx, loc, xp=np):
    """Yp [K, P], d [P], rinv [P] + slots idx/loc [n, Pm] -> Yl [n, Pm, K], dl, rl [n, Pm] (empty slots -> 0)."""
    K = Yp.shape[0]
    Ypad = xp.concatenate([Yp, xp.zeros((K, 1), Yp.dtype)], 1)
    dpad = xp.concatenate([d, xp.zeros((1,), d.dtype)]); rpad = xp.concatenate([rinv, xp.zeros((1,), rinv.dtype)])
    Yl = xp.moveaxis(Ypad[:, idx], 0, -1)                                         # [n, Pm, K]
    return Yl, dpad[idx], rpad[idx] * loc

class Solver:
    """LETKF weights for many local problems, in chunks (memory) - jitted under jax, a plain loop under numpy."""
    def __init__(self, xp=np, chunk=4096):
        self.xp = xp; self.chunk = chunk; self._f = None
        if xp is not np:
            import jax
            def f(Yp, d, rinv, idx, loc, rho):
                Yl, dl, rl = gather_local(Yp, d, rinv, idx, loc, xp); return transform(Yl, dl, rl, rho, xp)
            self._f = jax.jit(f)
    def weights(self, Yp, d, rinv, idx, loc, rho=1.0):
        xp = self.xp; n = idx.shape[0]; out = []
        rho = np.broadcast_to(np.asarray(rho, np.float32), (n,)) if np.ndim(rho) else float(rho)
        Yp = xp.asarray(Yp); d = xp.asarray(d); rinv = xp.asarray(rinv)
        for a in range(0, n, self.chunk):
            b = min(n, a + self.chunk); ii = idx[a:b]; ll = loc[a:b]; rr = rho[a:b] if np.ndim(rho) else rho
            if self._f is not None:
                pad = self.chunk - (b - a)                                             # fixed shapes: one compile
                if pad:
                    ii = np.concatenate([ii, np.full((pad,) + ii.shape[1:], Yp.shape[1], ii.dtype)])
                    ll = np.concatenate([ll, np.zeros((pad,) + ll.shape[1:], ll.dtype)])
                    if np.ndim(rr): rr = np.concatenate([rr, np.ones(pad, np.float32)])
                T = self._f(Yp, d, rinv, xp.asarray(ii), xp.asarray(ll), xp.asarray(rr, np.float32))[: b - a]
            else:
                Yl, dl, rl = gather_local(Yp, d, rinv, ii, ll, xp); T = transform(Yl, dl, rl, rr, xp)
            out.append(T)
        return xp.concatenate(out, 0)

# ---------------------------------------------------------------------------------------------------- update + inflation
def apply_weights(Xb, T, xp=np):
    """Xb [K, ..., n] background (last axis = local problem); T [n, K, K] -> analysis ensemble, same shape."""
    xm = Xb.mean(0); Xp = Xb - xm
    return xm[None] + xp.einsum('j...n,njk->k...n', Xp, T)

def rtps(Xb, Xa, alpha, xp=np):
    """Relaxation to prior spread (Whitaker & Hamill 2012): analysis perturbations scaled so the spread becomes
    alpha x prior spread + (1 - alpha) x analysis spread, point by point. alpha ~0.5-0.9."""
    if not alpha: return Xa
    am = Xa.mean(0); Ap = Xa - am
    sb = xp.sqrt(((Xb - Xb.mean(0)) ** 2).mean(0)); sa = xp.sqrt((Ap ** 2).mean(0))
    fac = xp.where(sa > 0, (alpha * sb + (1 - alpha) * sa) / xp.maximum(sa, 1e-30), 1.0)
    return am[None] + Ap * fac[None]

def adaptive_inflation(d, Yp, rinv, prev=1.0, lo=1.0, hi=2.0, gain=0.3):
    """Global multiplicative inflation from innovation statistics (Li, Kalnay & Miyoshi 2009 style):
    E[d^T R^-1 d] = P + tr(R^-1 H Pb H^T) -> rho_obs = (d'R^-1 d - P) / tr(R^-1 HPbH^T), smoothed with the previous value."""
    d = np.asarray(d, float); Yp = np.asarray(Yp, float); rinv = np.asarray(rinv, float); K = Yp.shape[0]
    tr = float(((Yp ** 2).sum(0) / (K - 1) * rinv).sum())
    if tr <= 0: return prev
    est = (float((d ** 2 * rinv).sum()) - len(d)) / tr
    return float(np.clip((1 - gain) * prev + gain * est, lo, hi))

def vertical_blend(sig, sig_groups, xp=np):
    """weights [L, G] that linearly interpolate (in ln sigma) group weight matrices to each model level."""
    ls = np.log(np.asarray(sig, float)); lg = np.log(np.asarray(sig_groups, float)); order = np.argsort(lg); lg_s = lg[order]
    B = np.zeros((len(ls), len(lg)))
    for i, x in enumerate(ls):
        if x <= lg_s[0]: B[i, order[0]] = 1.0; continue
        if x >= lg_s[-1]: B[i, order[-1]] = 1.0; continue
        j = np.searchsorted(lg_s, x); a = (x - lg_s[j - 1]) / (lg_s[j] - lg_s[j - 1])
        B[i, order[j - 1]] = 1 - a; B[i, order[j]] = a
    return B
