"""IFS Cy50r1 convection (Part IV chapter 6) for MEGAM, v1 (11 Nov 2026). Design and the list of v1 simplifications: docs/ifs_package.md.
Column-vectorised jax: arrays [L, X, Y] with index 0 = model top, L-1 = lowest layer. Interface j = bottom of layer j (j = L-1: ground).
Variables: h = cp T + g z + Lv q (moist static energy), qt = q + condensate. Environment tendencies in flux form with an implicit
(bi-diagonal, top-down) solve (eq. 6.69); sources: precipitation (sink of water), freezing/sublimation/melting (Lf), rain evaporation.
Energy (h + precipitation) and water conserved per column."""
import jax, jax.numpy as jnp

G, RD, RV, CP, LV, LF = 9.80616, 287.04, 461.5, 1004.6, 2.5e6, 3.34e5
T0, TICE, TBF = 273.16, 235.16, 268.16
EPS_UP, DELTA_DEEP = 1.75e-3, 0.75e-4            # (6.7), (6.8)
BCD, F1G = 1.949, 3.0                             # (1 + beta Cd), f (1 + gamma)   (6.10)
C00, LCRIT = 1.4e-3, 5e-4                         # (6.44)
EPS_DD = 2e-4                                     # (6.15)
A1, A2, A3 = 5.44e-4, 5.09e-3, 0.5777             # Kessler (6.52)


def qsat(T, p):
    es = 611.2 * jnp.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / jnp.maximum(p - 0.378 * es, 1.0)


def t_from_h(h, z, p, qt, T_guess):
    """Temperature and vapour of a parcel with moist static energy h and total water qt at (z, p): dry if unsaturated, else saturation
    adjustment (Newton, 4 iterations). Returns T, qv, l (condensate)."""
    Td = jnp.clip((h - G * z - LV * qt) / CP, 120.0, 400.0)
    Tu = jnp.clip(T_guess, 150.0, 350.0)
    for _ in range(4):
        qs_ = qsat(Tu, p); f_ = CP * Tu + G * z + LV * qs_ - h; df = CP + LV * qs_ * 17.67 * 243.5 / (Tu - 29.65) ** 2
        Tu = jnp.clip(Tu - f_ / df, 150.0, 350.0)
    sat = qt > qsat(Td, p)
    T = jnp.where(sat, Tu, Td); qv = jnp.where(sat, jnp.minimum(qsat(Tu, p), qt), qt)
    return T, qv, jnp.maximum(qt - qv, 0.0)


def alpha_liq(T):                                 # (6.43): liquid share of condensate
    return jnp.where(T >= T0, 1.0, jnp.where(T <= TICE, 0.0, ((T - TICE) / (T0 - TICE)) ** 2))


def plume(env, k0, h0, qt0, K0, mode, qs_ref, land, frac_keep=1.0, f_eps=1.0, micro=False, deep=True):
    """One bulk ascent from layer k0 upward (scan bottom -> top). mode 0: shallow test parcel eps = 0.8/z + 3e-4 (6.18);
    mode 1: deep test parcel eps = 0.4 x 1.75e-3 f_scale (6.4); mode 2: full updraught eps = 1.75e-3 f_eps (1.3 - RH) f_scale (6.7)
    with detrainment (6.8 deep / 6.9 shallow) and organised detrainment from the decrease of K (6.12). Kinetic energy (6.10).
    frac_keep: share of new condensate kept (test deep parcel 0.5). micro: Sundqvist precipitation (6.44-6.46).
    Returns per layer: act, h_u, qt_u (after precipitation), T_u, l_u, b, K, eta (relative mass flux through the TOP of the layer),
    prc (precipitation produced per unit cloud-base mass flux, kg/kg), frz (new frozen condensate per unit flux), sat flag."""
    T, q, qs, p, z, h, rh, Tv = env
    L = T.shape[0]; ii = jnp.arange(L)
    xs = tuple(a[::-1] for a in (T, q, qs, p, z, h, rh, Tv)) + (ii[::-1],)
    zb = jnp.zeros_like(h0)

    def step(c, x):
        hu, qtu, lu, K, eta, alive, started, zp, Tup, cb, bp = c
        Te, qe, qse, pe, ze, he, rhe, Tve, k = x
        src = k == k0; above = started & alive
        dz = jnp.where(src, 0.0, jnp.maximum(ze - zp, 0.0))
        fsc = jnp.clip(qse / jnp.maximum(qs_ref, 1e-7), 1e-3, 1.0) ** 3
        if mode == 0: eps = 0.8 / jnp.maximum(ze, 10.0) + 3e-4
        elif mode == 1: eps = 0.4 * EPS_UP * fsc
        else: eps = EPS_UP * f_eps * jnp.maximum(1.3 - rhe, 0.0) * fsc * (bp > 0)               # (6.3.1) entrainment only where the updraught is buoyant
        if mode == 2: dlt = jnp.where(deep, DELTA_DEEP * jnp.maximum(1.6 - rhe, 0.0), eps * jnp.maximum(1.6 - rhe, 0.0))
        else: dlt = 0.0
        # mass-weighted mixing over the layer (entrainment ~ eps dz of the flux)
        ent = eps * dz
        hu1 = jnp.where(src, h0, (hu + ent * he) / (1.0 + ent)); qt1 = jnp.where(src, qt0, (qtu + lu * 0.0 + ent * qe) / (1.0 + ent))
        Tu, qv, lnew_tot = t_from_h(hu1, ze, pe, qt1, jnp.where(src, Te, Tup))
        cond = jnp.maximum(lnew_tot - jnp.where(src, 0.0, lu / (1.0 + ent)), 0.0)          # new condensate formed in this layer
        lkeep = jnp.where(src, lnew_tot, lu / (1.0 + ent) + frac_keep * cond)
        qt1 = jnp.where(src, qt1, qt1 - (1.0 - frac_keep) * cond)                            # test deep parcel: half the new water removed
        frz = jnp.zeros_like(cond); prc = jnp.zeros_like(cond)
        if micro:
            aT = jnp.where(deep, alpha_liq(Tu), 1.0)                                          # shallow stays liquid (since Cy45r1)
            frz = (1.0 - aT) * cond; hu1 = hu1 + LF * frz                                    # freezing heats the updraught (frozen share of new water)
            Tu, qv, lnew_tot = t_from_h(hu1, ze, pe, qt1, Tu); lkeep = jnp.maximum(qt1 - qv, 0.0)
            w = jnp.clip(jnp.sqrt(2.0 * jnp.maximum(K, 1e-4)), 0.1, 15.0)
            cBF = jnp.where(Tu < TBF, 1.0 + 0.5 * jnp.sqrt(jnp.maximum(jnp.minimum(TBF - Tu, TBF - TICE), 0.0)), 1.0)
            fac = jnp.where(deep, 1.0, jnp.where(land, 0.8, 0.9))
            c0 = C00 * (1.0 + 0.3 * aT) * cBF * fac; lcr = LCRIT / cBF
            thr = jnp.where(land, 5e-4, 3e-4)
            a = c0 / (0.75 * w) * (1.0 - jnp.exp(-(lkeep / lcr) ** 2))
            lafter = jnp.where(lkeep > thr, lkeep * jnp.exp(-a * dz), lkeep)
            prc = jnp.where(src, 0.0, lkeep - lafter); lkeep = lafter; qt1 = qt1 - prc
        Tvu = Tu * (1.0 + 0.608 * qv - lkeep)
        b = (Tvu - Tve) / Tve
        mu_ = jnp.where(eps > 0, eps, dlt)
        K1 = jnp.where(src, K0, (K + dz * G * b / F1G) / (1.0 + dz * mu_ * 2.0 * BCD))
        satn = lnew_tot > 0; cb1 = cb | (satn & ~src)
        if mode == 1: K1 = jnp.where(cb1 & ~cb, K0, jnp.where(cb1, K1, K0))                   # deep test: dry lift to the LCL, w = 1 m/s from cloud base (6.4)
        alive1 = jnp.where(src, True, above & (K1 > 0) & (pe > 5000.0))
        org = jnp.where((K1 < K) & ~src, jnp.clip(jnp.maximum(1.6 - rhe, 0.0) * jnp.sqrt(jnp.maximum(K1, 0.0) / jnp.maximum(K, 1e-8)), 0.0, 1.0), 1.0)
        eta1 = jnp.where(src, 1.0, eta * jnp.exp((eps - dlt) * dz) * org) if mode == 2 else jnp.where(src, 1.0, eta)
        act = jnp.where(src, True, alive1)
        st1 = started | src
        carry = (jnp.where(act, hu1, hu), jnp.where(act, qt1, qtu), jnp.where(act, lkeep, lu), jnp.where(act, K1, K),
                 jnp.where(act, eta1, 0.0), jnp.where(st1, alive1, alive), st1, jnp.where(act | ~st1, ze, zp), jnp.where(act, Tu, Tup), jnp.where(act, cb1, cb), jnp.where(act, b, bp))
        out = (act & st1, hu1, qt1, Tu, lkeep, b, K1, jnp.where(act & st1, eta1, 0.0), jnp.where(act & st1, prc, 0.0) * jnp.where(act & st1, eta, 0.0),
               jnp.where(act & st1, frz, 0.0) * jnp.where(act & st1, eta, 0.0), (lnew_tot > 0) & act & st1 & ~src)
        return carry, out

    c0_ = (zb, zb, zb, zb, zb, jnp.zeros(h0.shape, bool), jnp.zeros(h0.shape, bool), zb - 1.0, zb + 280.0, jnp.zeros(h0.shape, bool), zb + 1.0)
    _, out = jax.lax.scan(step, c0_, xs)
    return tuple(a[::-1] for a in out)


def implicit_transport(phi, mass, A, Mnet, Fx, S, use_imp, dt):
    """Top-down bi-diagonal solve of m (phi_new - phi)/dt = F_bot - F_top + S, F_bot = A - Mnet phi_new (implicit, cloud layers,
    use_imp) or Fx (explicit, sub-cloud). Returns the tendency (phi_new - phi)/dt."""
    def stp(Ft, x):
        m_k, p0, a_k, mn, fx, s_k, imp = x
        pn = jnp.where(imp, (m_k * p0 / dt + a_k - Ft + s_k) / (m_k / dt + mn), p0 + dt * (fx - Ft + s_k) / m_k)
        Fb = jnp.where(imp, a_k - mn * pn, fx)
        return Fb, pn
    _, pn = jax.lax.scan(stp, jnp.zeros_like(phi[0]), (mass, phi, A, Mnet, Fx, S, use_imp))
    return (pn - phi) / dt


def convection(T, q, p, mass, zc, ps, H, E, ust, rho, land, dt, dx, dT_bl, dq_bl, u_bl, use_pbl=True, det_prec=0.0, q_adv=None, a_qcv=0.0):
    """IFS convection, one call. dT_bl, dq_bl: non-convective tendencies (BL diffusion + radiation) for the closures.
    Returns dict(dT, dq, prc (convective precipitation production per layer, kg m-2 s-1, for the cloud scheme), P_sfc (convective
    precipitation at the ground), mask (cloud layers), deep, shallow, M (updraught mass flux per layer, for momentum transport))."""
    L = T.shape[0]; ii = jnp.arange(L)[:, None, None]
    qs = qsat(T, p); rh = jnp.clip(q / qs, 0.0, 1.0); h = CP * T + G * zc + LV * q; Tv = T * (1.0 + 0.608 * q)
    env = (T, q, qs, p, zc, h, rh, Tv)
    dp = mass * G
    kL = jnp.full(ps.shape, L - 1)
    # ---- shallow test parcel from the lowest layer (6.18-6.20)
    bflux = G / Tv[-1] * (H / (rho * CP) + 0.61 * T[-1] * E / rho)
    wst = jnp.maximum(jnp.cbrt(1.2 * jnp.maximum(ust, 0.1) ** 3 + 1.5 * 0.4 * zc[-1] * jnp.maximum(bflux, 0.0)), 0.1)
    dTx = jnp.clip(1.5 * H / (rho * CP * wst), 0.2, 1.0); dqx = jnp.clip(1.5 * E / (rho * wst), 1e-4, 5e-4)
    h_s0 = h[-1] + CP * dTx + LV * dqx; qt_s0 = q[-1] + dqx
    a_s, hu_s, qtu_s, Tu_s, lu_s, b_s, K_s, _, _, _, sat_s = plume(env, kL, h_s0, qt_s0, 0.5 * wst ** 2, 0, qs[-1], land)
    kcb_s = jnp.max(jnp.where(sat_s, ii, -1), axis=0)                                            # lowest saturated active layer = cloud base
    p_cb_s = jnp.take_along_axis(p, jnp.maximum(kcb_s, 0)[None], 0)[0]
    p_top_s = jnp.min(jnp.where(a_s, p, 1e7), axis=0)
    K_cb_s = jnp.take_along_axis(K_s, jnp.maximum(kcb_s, 0)[None], 0)[0]
    is_sh = (kcb_s >= 0) & (K_cb_s > 0) & (p_cb_s - p_top_s < 20000.0) & (p_cb_s - p_top_s > 0)
    # ---- deep test parcels: departure layers from the 2nd-lowest up to 350 hPa (6.4); lowest 60 hPa: 50-hPa layer-mean source
    kmax = L - 2; kmin = int(max(0, L - 1 - int(0.75 * L)))                                       # static candidate range (masked by p >= 350 hPa below)
    cand = jnp.arange(kmax, kmin - 1, -1)

    def deep_test(kd):
        pk = jnp.take(p, kd, axis=0); in_ml = (ps - pk) < 6000.0
        win = (jnp.abs(p - pk[None]) <= 2500.0) & (p <= ps[None])
        wm = mass * win; h_av = (h * wm).sum(0) / jnp.maximum(wm.sum(0), 1e-6); q_av = (q * wm).sum(0) / jnp.maximum(wm.sum(0), 1e-6)
        hk = jnp.where(in_ml, h_av, jnp.take(h, kd, axis=0)); qk = jnp.where(in_ml, q_av, jnp.take(q, kd, axis=0))
        first = kd == L - 2
        ddT = jnp.where(first, dTx, 0.2); ddq = jnp.where(first, dqx, 1e-4)
        if q_adv is not None:                                                                      # (6.21): + min(3e-4, dq/dt|adv * 600 s) below 700 hPa
            qa_k = jnp.take(q_adv, kd, axis=0)
            ddq = jnp.where(first | (pk < 70000.0), ddq, 1e-4 + jnp.minimum(3e-4, jnp.maximum(qa_k, 0.0) * 600.0))
        kk = jnp.full(ps.shape, kd)
        a_d, hu_d, qtu_d, Tu_d, lu_d, b_d, K_d, _, _, _, sat_d = plume(env, kk, hk + CP * ddT + LV * ddq, qk + ddq, 0.5, 1, qs[-1], land, frac_keep=0.5)
        kcb = jnp.max(jnp.where(sat_d, ii, -1), axis=0); kcb_ = jnp.maximum(kcb, 0)
        pcb = jnp.take_along_axis(p, kcb_[None], 0)[0]; ptop = jnp.min(jnp.where(a_d, p, 1e7), axis=0)
        ok = (kcb >= 0) & (pcb - ptop > 20000.0) & (pk >= 35000.0)
        tk = lambda X: jnp.take_along_axis(X, kcb_[None], 0)[0]
        return ok, kcb_, tk(hu_d), tk(qtu_d), tk(K_d), kk, in_ml
    res = jax.lax.map(deep_test, cand)                                                             # [n_cand, X, Y] each
    ok_all = res[0]; first_ok = jnp.argmax(ok_all, axis=0); any_deep = ok_all.any(0)
    pick = lambda A: jnp.take_along_axis(A, first_ok[None], 0)[0]
    kcb_d, hcb_d, qtcb_d, Kcb_d, kdep_d, inml_d = (pick(r) for r in res[1:])
    is_deep = any_deep
    is_sh = is_sh & ~is_deep
    active = is_deep | is_sh
    # ---- full updraught from cloud base, initialised with the test-parcel values there
    kcb = jnp.where(is_deep, kcb_d, jnp.maximum(kcb_s, 0))
    tk = lambda X, k_: jnp.take_along_axis(X, k_[None], 0)[0]
    h_cb = jnp.where(is_deep, hcb_d, tk(hu_s, kcb)); qt_cb = jnp.where(is_deep, qtcb_d, tk(qtu_s, kcb))
    K_cb = jnp.maximum(jnp.where(is_deep, Kcb_d, tk(K_s, kcb)), 0.5)                               # w at cloud base >= 1 m/s (6.10 text)
    qs_cb = tk(qs, kcb)
    a_u, hu, qtu, Tu, lu, bu, Ku, eta, prc, frz, _ = plume(env, kcb, h_cb, qt_cb, K_cb, 2, qs_cb, land, f_eps=jnp.where(is_deep, 1.0, 2.0),
                                                        micro=True, deep=is_deep)
    incl = a_u & active[None]
    eta = jnp.where(incl, eta, 0.0); prc = jnp.where(incl, prc, 0.0); frz = jnp.where(incl, frz, 0.0)
    ktop = jnp.min(jnp.where(incl, ii, L), axis=0)
    eta = jnp.where(ii == ktop[None], 0.0, eta)                                                    # everything detrains in the top layer
    # ---- closures
    zcb = tk(zc, kcb); ztop = jnp.max(jnp.where(incl, zc, 0.0), axis=0); Hc = jnp.maximum(ztop - zcb, 100.0)
    wbar = (jnp.sqrt(2.0 * jnp.maximum(Ku, 0.0)) * incl).sum(0) / jnp.maximum(incl.sum(0), 1)
    tau_c = Hc / jnp.maximum(wbar, 0.5)
    ax = 1.0 + 1.6 * dx / 125e3                                                                   # (6.27), dx >= 8 km
    tau = jnp.clip(tau_c * ax, 720.0, 10800.0)
    Tvu = Tu * (1.0 + 0.608 * (qtu - lu) - lu)
    pcape = (jnp.where(incl, (Tvu - Tv) / Tv - lu, 0.0) * dp).sum(0)                               # (6.22), Pa
    dz_up = jnp.concatenate([jnp.maximum(zc[:-1] - zc[1:], 1.0), jnp.ones_like(zc[:1])], 0)         # layer k to k-1
    dTvdz = jnp.concatenate([(Tv[:-1] - Tv[1:]) / jnp.maximum(zc[:-1] - zc[1:], 1.0), jnp.zeros_like(Tv[:1])], 0)
    den = (jnp.where(incl, G / Tv * eta * (dTvdz + G / CP) * dz_up, 0.0)).sum(0)
    subc = (ii > kcb[None]) & (p <= ps[None])
    dTv_bl = dT_bl * (1.0 + 0.608 * q) + 0.608 * T * dq_bl
    tau_bl = jnp.where(land, tau_c, zcb / jnp.maximum(u_bl, 2.0))
    pcape_bl = jnp.where(is_deep & inml_d, tau_bl * (dTv_bl * dp * subc).sum(0), 0.0)               # (6.33-6.34), T* = 1 K
    # IFS 6.33: dTv/dt|bl must include turbulent diffusion, radiation AND ADVECTION. v1 passes diffusion + radiation only (no advective
    # tendency available in the column call), which leaves PCAPE_bl biased high (BL heating not offset by advection) -> use_pbl=False
    # gives the pre-40r1 IFS closure (PCAPE_bl = 0, Gregory et al. 2000) until the advective tendency is passed in.
    if not use_pbl: pcape_bl = jnp.zeros_like(pcape_bl)
    qcv = jnp.zeros_like(pcape)
    if q_adv is not None and a_qcv:
        # (6.29, 6.32) Cy47r3 moisture-convergence term: QCV = -a_qcv Lv tau_c / (g H) int_{psurf}^{psurf-60 hPa} (q/qsat) dq/dt|adv dp;
        # not applied where the column saturation fraction (surface to cloud top) exceeds 0.94 (resolved-convection limit, TC cores)
        low60 = (ps[None] - p <= 6000.0) & (p <= ps[None])
        qcv = a_qcv * LV * tau_c / (G * Hc) * ((q / jnp.maximum(qs, 1e-9)) * q_adv * dp * low60).sum(0)
        top_ = ii >= ktop[None]
        satf = ((q * mass) * top_).sum(0) / jnp.maximum((qs * mass * top_).sum(0), 1e-9)
        qcv = jnp.where(satf > 0.94, 0.0, qcv)
    Mb_deep = jnp.maximum(pcape + qcv - pcape_bl, 0.0) / (tau * jnp.maximum(den, 1e-6))
    hdiff = tk(hu, kcb) - tk(h, kcb)
    Fbl = ((CP * dT_bl + LV * dq_bl) * mass * subc).sum(0)                                         # (6.35) rhs: non-convective sub-cloud MSE tendency
    lim = jnp.minimum(jnp.min(jnp.where(eta > 0, 3.0 * mass / (dt * jnp.maximum(eta, 1e-6)), 1e9), axis=0), 2.0)   # (6.70) CFL 3, abs 2 kg m-2 s-1
    Mb0 = jnp.maximum(Fbl, 0.0) / jnp.maximum(hdiff, 1.0)
    Mb_sh = jnp.where(Mb0 > lim, jnp.maximum(Fbl, 0.0) / jnp.maximum(hdiff, 0.75 * CP), Mb0)
    Mb = jnp.where(is_deep, Mb_deep, jnp.where(is_sh, Mb_sh, 0.0))
    Mb = jnp.where(active & (hdiff > 0), jnp.clip(Mb, 0.0, lim), 0.0)
    Mu = Mb[None] * eta                                                                            # flux through the top of each cloud layer
    P_up = (prc * Mb[None]).sum(0)                                                                 # updraught precipitation, kg m-2 s-1
    # ---- downdraught (deep, 6.3.2 / 6.13-6.17): from the LFS (min-h layer inside the cloud, above cloud base) with M = -0.3 Mb
    hmin_k = jnp.argmin(jnp.where(incl & (ii < kcb[None]), h, 1e12), axis=0)
    has_dd = is_deep & (hmin_k < kcb) & (P_up > 0)
    hd0 = jnp.where(has_dd, 0.5 * (tk(hu, hmin_k) + tk(h, hmin_k)), tk(h, hmin_k)); qd0 = jnp.where(has_dd, 0.5 * (tk(qtu - lu, hmin_k) + tk(q, hmin_k)), tk(q, hmin_k))
    dzd = jnp.concatenate([jnp.ones_like(zc[:1]), jnp.maximum(zc[:-1] - zc[1:], 1.0)], 0)         # layer k from the layer above

    def dstep(c, x):
        hd, qd, on = c; k, he, qe, pe, ze, Tve, Te, dzk = x
        start = k == hmin_k; below = on & (k > hmin_k)
        mix = EPS_DD * dzk                                                                        # entrainment = detrainment (6.15)
        hd1 = jnp.where(start, hd0, (hd + mix * he) / (1.0 + mix)); qm = jnp.where(start, qd0, (qd + mix * qe) / (1.0 + mix))
        Td, _, _ = t_from_h(hd1, ze, pe, 2.0 * qsat(Te, pe) + 0.05, Te)                          # saturated at constant h (evaporating rain)
        qd1 = qsat(Td, pe); Td = jnp.clip((hd1 - G * ze - LV * qd1) / CP, 150.0, 350.0)
        on1 = jnp.where(start, True, below & (Td * (1.0 + 0.608 * qd1) < Tve))                  # stops where it turns buoyant
        return (jnp.where(on1, hd1, hd), jnp.where(on1, qd1, qd), on1), (on1, qd1, hd1, jnp.maximum(qd1 - qm, 0.0))
    _, (on_d, qd_, hd_, evd) = jax.lax.scan(dstep, (hd0, qd0, jnp.zeros(ps.shape, bool)), (jnp.arange(L), h, q, p, zc, Tv, T, dzd))
    on_d = on_d & has_dd[None]
    # mass flux -0.3 Mb (6.13), decreased linearly over the lowest 60 hPa; total evaporation limited to half the updraught precipitation
    p_bot = p + 0.5 * dp
    lin = jnp.clip((ps[None] - p_bot) / 6000.0, 0.0, 1.0)
    Md = -0.3 * Mb[None] * on_d * lin
    need = (evd * jnp.abs(Md) * on_d).sum(0)
    scale_dd = jnp.where(need > 0, jnp.clip(0.5 * P_up / jnp.maximum(need, 1e-12), 0.0, 1.0), 1.0)
    Md = Md * scale_dd[None]
    e_down = evd * jnp.abs(Md) * on_d                                                              # rain evaporated into the downdraught, kg m-2 s-1 per layer
    E_dd = e_down.sum(0)
    # ---- sub-cloud updraught flux (6.39-6.41): linear in p from cloud base to 0 at the departure level / ground
    pcb_ = tk(p_bot, kcb); kdep = jnp.where(is_deep, kdep_d, L - 1); pdep = jnp.minimum(tk(p_bot, kdep), ps)
    Z = jnp.clip((pdep[None] - p_bot) / jnp.maximum(pdep - pcb_, 1.0)[None], 0.0, 1.0) * (ii > kcb[None]) * (ii < kdep[None])
    sh = lambda X: jnp.concatenate([X[1:], X[-1:]], 0)
    # updraught values entering each interface from below (upwind)
    hu_in = sh(jnp.where(incl, hu, h)); qt_in = sh(jnp.where(incl, qtu, q))
    F_h_cb = Mb * hdiff; F_q_cb = Mb * (tk(qtu, kcb) - tk(q, kcb))                          # (M (phi_up - phi))_base
    expl = (ii >= kcb[None]) & active[None]
    Fx_h = jnp.where(ii == kcb[None], F_h_cb[None], Z * F_h_cb[None]) * expl
    Fx_q = jnp.where(ii == kcb[None], F_q_cb[None], Z * F_q_cb[None]) * expl
    # cloud layers (above the base interface): implicit, net flux M_u + M_d >= 0
    Mup_i = jnp.where((ii < kcb[None]) & active[None], sh(Mu), 0.0)
    Mdn_i = jnp.where(ii < kcb[None], jnp.maximum(Md, -Mup_i), 0.0)
    A_h = Mup_i * hu_in + Mdn_i * hd_; A_q = Mup_i * qt_in + Mdn_i * qd_
    Mnet = Mup_i + Mdn_i
    # downdraught below cloud base: explicit flux M_d (phi_d - phi)
    Fx_h = Fx_h + jnp.where(ii >= kcb[None], Md * (hd_ - h), 0.0); Fx_q = Fx_q + jnp.where(ii >= kcb[None], Md * (qd_ - q), 0.0)
    imp = (ii < kcb[None]) & active[None]
    # ---- sources: precipitation (water sink where it forms), downdraught evaporation (water source), Lf terms
    # precipitation flux falling through the column: production minus downdraught evaporation; melting at the 0 C crossing;
    # Kessler evaporation below cloud base (6.49-6.52)
    prod = prc * Mb[None]
    aT = jnp.where(is_deep[None], alpha_liq(Tu), 1.0)
    # det_prec (12 Nov, DIAGNOSTIC sufficiency test for A/P1): v1 evaporates ALL detrained condensate where it detrains (pre-prognostic
    # IFS); in Cy50r1 it feeds the prognostic cloud scheme, from which part precipitates. det_prec = fraction of the detrained condensate
    # turned into precipitation at the detrainment level (1 = upper bound). Default 0 = v1 unchanged.
    if det_prec:
        eta_in0 = jnp.where(ii == kcb[None], 1.0, sh(eta)) * incl
        prod = prod + det_prec * Mb[None] * jnp.maximum(eta_in0 - eta, 0.0) * incl * lu
    snow_frac = jnp.where(incl, 1.0 - aT, 0.0)
    rhcr = jnp.where(is_deep, jnp.where(land, 0.70, 0.85), jnp.where(land, 0.75, 0.90))
    rh_cl = (rh * incl).sum(0) / jnp.maximum(incl.sum(0), 1)
    cconv = jnp.where(is_deep, 0.05, jnp.clip(0.05 * (1.0 + (jnp.maximum(0.8, rh_cl) - 0.8) / 0.025), 0.05, 0.45))

    def fall(c, x):
        Pr, Ps_ = c; prod_k, sf_k, edd_k, T_k, q_k, qs_k, p_k, m_k, k = x
        Pr = Pr + prod_k * (1.0 - sf_k); Ps_ = Ps_ + prod_k * sf_k
        # downdraught evaporation taken from rain first
        tk_ = jnp.minimum(edd_k, Pr + Ps_); fr = jnp.where(Pr + Ps_ > 0, Pr / jnp.maximum(Pr + Ps_, 1e-12), 1.0)
        Pr = Pr - tk_ * fr; Ps_ = Ps_ - tk_ * (1.0 - fr)
        melt = jnp.where(T_k > T0, Ps_, 0.0); Pr = Pr + melt; Ps_ = Ps_ - melt
        below = k > kcb
        Ptot = Pr + Ps_
        e = jnp.where(below & (Ptot > 0), cconv * A1 * jnp.maximum(rhcr * qs_k - q_k, 0.0) * (jnp.sqrt(p_k / ps) * Ptot / (A2 * cconv)) ** A3, 0.0) * m_k
        e = jnp.minimum(e, Pr)
        Pr = Pr - e
        return (Pr, Ps_), (melt, e, tk_ * (1.0 - fr))
    (Pr_s, Ps_s), (melt, e_sub, e_dd_ice) = jax.lax.scan(fall, (jnp.zeros_like(ps), jnp.zeros_like(ps)),
                                                          (prod, snow_frac, e_down, T, q, qs, p, mass, jnp.arange(L)))
    # downdraught evaporation is inside the downdraught's water (q_d) -> the precipitation sink at the LFS..ground: e_down
    S_q = -prod + e_down + e_sub                                                                   # kg m-2 s-1 per layer
    S_h = LF * frz * Mb[None] - LF * melt - LF * e_dd_ice                                          # freezing in updraught, melting, sublimation of snow by downdraught
    # detrained ice sublimates (Lf beyond the Lv inside h): net detrainment per layer x frozen share of the updraught condensate
    eta_in = jnp.where(ii == kcb[None], 1.0, sh(eta)) * incl
    D_rel = jnp.maximum(eta_in - eta, 0.0) * incl
    S_h = S_h - (1.0 - det_prec) * LF * Mb[None] * D_rel * lu * (1.0 - aT)
    dh = implicit_transport(h, mass, A_h, Mnet, Fx_h, S_h, imp, dt)
    dqt = implicit_transport(q, mass, A_q, Mnet, Fx_q, S_q, imp, dt)
    dh = jnp.where(active[None], dh, 0.0); dqt = jnp.where(active[None], dqt, 0.0)
    dT = (dh - LV * dqt) / CP
    mask = (incl | on_d) & active[None]
    return dict(dT=dT, dq=dqt, prc=jnp.where(active[None], prod, 0.0), P_sfc=jnp.where(active, Pr_s + Ps_s, 0.0), mask=mask,
                deep=is_deep, shallow=is_sh, M=jnp.where(active[None], Mu, 0.0), Mb=Mb, e_sub=e_sub, e_down=e_down,
                dbg=dict(pcape=pcape, qcv=qcv, pcape_bl=pcape_bl, den=den, tau=tau, hdiff=hdiff, Fbl=Fbl, lim=lim, Hc=Hc, ncl=incl.sum(0),
                         kcb_s=kcb_s, Kcb_s=K_cb_s, pcb_s=p_cb_s, ptop_s=p_top_s, wst=wst, dTx=dTx, nact_s=a_s.sum(0)))

