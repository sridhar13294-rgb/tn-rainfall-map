"""Rain re-evaporation in the IFS form (IFS Cy50r1 Part IV): numpy or jax.numpy (pass xp).
Convective rain, below cloud base only (eq. 6.49-6.52, Kessler 1969): e = C_conv a1 (RHcr qs - q)+ [sqrt(p/ps) / a2 * P / C_conv]^a3,
  C_conv = 0.05, a1 = 5.44e-4 s-1, a2 = 5.09e-3, a3 = 0.5777; RHcr 0.85 over water, 0.70 over land (deep convection);
  zero where q > RHcr qs.
Grid-scale rain: same Kessler rate with the precipitation fraction a (ev_frac), and the IFS threshold (eq. 7.58)
  RHcrit = min(0.7 + 0.3 a / (1 - a), RHcrit_bl, 0.9), RHcrit_bl = 0.8 above sigma 0.7 rising linearly to 1 at the surface.
  (IFS Cy50r1 computes the grid-scale rate from the drop-size integral, eq. 7.56; the Kessler rate here is the older
  IFS form - documented approximation.)
Both rain streams fall separately; per layer the evaporation cannot exceed the flux, nor the water that would take the
layer to its threshold within one step (limiter; whether it binds is returned)."""
A1, A2, A3, CCONV = 5.44e-4, 5.09e-3, 0.5777, 0.05


def fall_ifs(src_ls, src_cv, q, qs, p, ps, mass, sig, land, a, dt, scan, xp):
    """src_ls, src_cv, q, qs, p, mass, sig [L,X,Y] (sources kg m-2 s-1 per layer, top -> bottom); ps [X,Y]; land bool [X,Y].
    Returns surface rain [X,Y], evaporation per layer [L,X,Y] (kg m-2 s-1), share of (layer, column) points where the
    one-step limiter binds."""
    rh_cv = xp.where(land, 0.70, 0.85)
    rh_bl = xp.where(sig > 0.7, 0.8 + 0.2 * (sig - 0.7) / 0.3, 0.8)
    rh_ls = xp.minimum(xp.minimum(0.7 + 0.3 * a / (1.0 - a), rh_bl), 0.9)
    pr = xp.sqrt(p / ps[None])
    # convective rain evaporates only BELOW cloud base (IFS eq. 6.49: 'below cloud base'): cloud base = the lowest layer
    # that produces convective rain; layers at or above it are inside the convective column
    below = xp.cumsum((src_cv > 0)[::-1].astype(p.dtype), axis=0)[::-1] <= 0

    def step(c, x):
        Pl, Pc = c
        sl, sc, q_, qs_, pr_, m_, rls, bl_ = x
        Pl = Pl + sl; Pc = Pc + sc
        dcv = xp.where(bl_, xp.maximum(rh_cv * qs_ - q_, 0.0), 0.0); dls = xp.maximum(rls * qs_ - q_, 0.0)
        ec = CCONV * A1 * dcv * (pr_ / A2 * xp.maximum(Pc, 0.0) / CCONV) ** A3 * m_
        el = a * A1 * dls * (pr_ / A2 * xp.maximum(Pl, 0.0) / a) ** A3 * m_
        cap = xp.maximum(dcv, dls) * m_ / dt                                  # cannot overshoot the threshold in one step
        tot = ec + el; lim = tot > cap
        f = xp.where(lim, cap / xp.maximum(tot, 1e-30), 1.0)
        ec = xp.minimum(ec * f, Pc); el = xp.minimum(el * f, Pl)
        return (Pl - el, Pc - ec), (el + ec, lim)
    z = xp.zeros_like(ps)
    (Pl, Pc), (ev, lim) = scan(step, (z, z), (src_ls, src_cv, q, qs, pr, mass, rh_ls, below))
    return Pl + Pc, ev, lim
