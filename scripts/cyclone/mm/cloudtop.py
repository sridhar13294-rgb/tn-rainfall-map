"""D2 cloud-top entrainment for the boundary-layer cloud deck (works with numpy and jax.numpy: pass xp).

Closure (Lilly 1968; Lock et al. 2000; Stevens 2002): the cloud-top long-wave cooling drives turbulence that entrains
warm, dry air from the inversion layer above:  rho w_e cp dtheta = A dF_cld,
  dF_cld = cloud part of the cloud-top layer's LW divergence = -(LW_allsky - LW_clear) cp m   [W m-2]
  A = 0.54 from DYCOMS-II RF01 (Stevens et al. 2003: w_e 3.8 mm/s, dtheta_l 8.75 K, LW jump ~70 W m-2); 0.4-0.6 observed.
The entrainment mass flux exchanges dry static energy s = cp T + g z and water between the cloud-top layer and the
layer above (energy and water conserved exactly). Applied only to the highest cloud-cooled layer between sigma 0.7 and
0.97 in columns without active deep convection (deep towers detrain; this is the stratocumulus / trade-cumulus top).
"""
G, CP = 9.80616, 1004.6

def cloud_top_entrainment(T, q, p, ps, zc, mass, lw_cld, cld, A, dt, xp, no_deep=None):
    """T, q, p, zc, mass, lw_cld, cld [L,X,Y] (lw_cld = all-sky minus clear-sky LW heating, K/s; cld = cloud fraction); ps [X,Y].
    Returns dT, dq (per second) and diagnostics (w_e flux kg m-2 s-1, cloud-top index)."""
    L = T.shape[0]; sig = p / ps[None]
    cand = (sig >= 0.7) & (sig <= 0.97) & (lw_cld < 0.0) & (cld > 0.05)            # a cloud that cools (its top)
    has = xp.any(cand, axis=0)
    if no_deep is not None: has = has & no_deep
    big = 10 ** 6
    kt = xp.min(xp.where(cand, xp.arange(L).reshape(-1, 1, 1), big), axis=0)       # highest (smallest index) cloud-cooled layer
    kt = xp.clip(kt, 1, L - 1); ka = kt - 1
    take = lambda X, k: xp.take_along_axis(X, k[None], axis=0)[0]
    th = T * (ps[None] / p) ** 0.2857
    dth = xp.maximum(take(th, ka) - take(th, kt), 0.5)
    mt, ma = take(mass, kt), take(mass, ka)
    dF = xp.maximum(-take(lw_cld, kt), 0.0) * CP * mt                               # W m-2
    rwe = A * dF / (CP * dth)                                                        # kg m-2 s-1
    rwe = xp.where(has, xp.minimum(rwe, 0.25 * xp.minimum(mt, ma) / dt), 0.0)      # explicit-step stability
    s = CP * T + G * zc
    Fs = rwe * (take(s, ka) - take(s, kt)); Fq = rwe * (take(q, ka) - take(q, kt))
    idx = xp.arange(L).reshape(-1, 1, 1)
    ot = (idx == kt[None]); oa = (idx == ka[None])
    dT = (xp.where(ot, Fs[None] / mass, 0.0) - xp.where(oa, Fs[None] / mass, 0.0)) / CP
    dq = xp.where(ot, Fq[None] / mass, 0.0) - xp.where(oa, Fq[None] / mass, 0.0)
    return dT, dq, dict(rwe=rwe, kt=kt)
