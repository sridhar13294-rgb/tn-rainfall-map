"""Diagnostic clouds + few-band radiation for the moist multi-level model (mm2.py).

Works with numpy (local tests) and jax.numpy (inside jit on the GPU): every function takes `xp` (the array module).
Only operations common to both are used; the vertical sweeps use _scan (jax.lax.scan under JAX, a python loop
under numpy). Arrays are [L, X, Y] with level 0 = model top, as in mm2.py. SI units.

CLOUDS (diagnostic)
  large-scale  Sundqvist: c = 1 - sqrt((1 - RH) / (1 - RHc)), RHc(sigma) = RHc_up + (RHc_low - RHc_up) exp(1 - sigma^-4)
               (ECHAM5 profile: 0.8 near the ground, 0.7 aloft); in-cloud water b_ls * qsat + condensation x residence time
  convective   Slingo (1987) type: total convective cover C_cv = 0.245 + 0.125 ln(P_conv [mm/day]) in [0, 0.8];
               tower layers get f_tow * C_cv; in-cloud water = convective rain production x residence time / cover
  anvil        at the detrainment top of deep convection (top above 400 hPa): fraction 2 (C_cv - 0.3) in the layers
               within 100 hPa of the top; ice path = detrained fraction x P_conv x anvil lifetime
  phase        liquid above -10 C, ice below -20 C, linear between; r_e liquid 10 um (sea) / 7 um (land),
               ice 20 um (-60 C) .. 60 um (-20 C)
  overlap      maximum-random (Geleyn & Hollingsworth 1979)
LONG-WAVE  17 spectral terms in 4 bands (H2O rotation 10-560 [5 terms], CO2 560-800 [5], window 800-1250 [2: ozone
           980-1100 and the rest], H2O vibration-rotation 1250-3000 cm-1 [5]). Absorption spectra: the simple spectral
           model (SSM) of Jeevanjee & Fueglistaler (2020) / Williams (2025, arXiv:2508.09353): H2O lines and CO2 (420 ppm)
           with linear pressure broadening (p / 500 hPa), H2O continuum ~ e exp(0.02 (260 - T)), all x 1.5 (calibration,
           see SSM_LINE_FAC); each band split into terms by absorption strength (k-distribution style) whose effective
           coefficients are fitted to the 1 cm-1 model; Planck fraction of sigma T^4 per term from a polynomial in T.
           Two-stream, diffusivity 1.66, linear-in-tau layer source, separate clear/cloudy streams per layer with
           maximum-random transfer between layers. Cloud absorption 1 - exp(-1.66 (k_l LWP + k_i IWP)),
           k_l = 0.0903 m2/g, k_i = 0.005 + 1/r_e(um) m2/g (CCM3: Kiehl et al. 1998; Ebert & Curry 1992).
SHORT-WAVE 7 terms: UV (ozone, Rayleigh), visible (Chappuis ozone, Rayleigh), 5 near-IR water-vapour terms
           (Lacis & Hansen 1974 exponential sum, pressure-scaled path). Delta-Eddington layers (Joseph et al. 1976;
           Briegleb 1992 formulas), adding method; cloud tau = 3 W / (2 rho r_e) x 0.7 (inhomogeneity, Tiedtke 1996),
           g = 0.85 liquid / 0.80 ice; clear and cloudy columns weighted by the max-random total cover with in-cloud tau
           spread over the cloudy area; sea albedo 0.037 / (1.1 mu0^1.4 + 0.15) (Taylor et al. 1996), land 0.2;
           Earth-curvature corrected slant path (mu_eff = sqrt(1224 mu0^2 + 1) / 35)."""
import numpy as np

G, RD, CP, SB = 9.80616, 287.04, 1004.6, 5.67e-8
RHO_W, RHO_I = 1000.0, 917.0
D_LW = 1.66                                                      # diffusivity factor
PREF_LINE = 5.0e4                                                # SSM reference pressure for line absorption (Pa)

DEFAULTS = dict(
    co2_ppm=420.0, s0=1361.0,
    # clouds
    rhc_low=0.80, rhc_up=0.70, rhc_n=4.0, sig_min=0.06, b_ls=0.01, tau_ls=3600.0,
    cv_a=0.245, cv_b=0.125, cv_max=0.8, f_tow=0.5, tau_cv=1800.0, q_cap=3e-3,
    anv_a=2.0, anv_c0=0.3, anv_max=0.95, anv_ptop=4.0e4, anv_dp=1.0e4, eps_det=0.1, tau_anv=3 * 3600.0,
    re_sea=10.0, re_land=7.0, re_ice_min=20.0, re_ice_max=60.0, c_max=0.999,
    # long-wave
    k_liq=0.0903, k_ice0=0.005, lw_line=1.0, lw_cnt=1.0, k_o3_lw=60.0,
    # short-wave
    alb_land=0.2, alb_sea_dif=0.06, sw_inhom=0.7, g_liq=0.85, g_ice=0.80,
)


# ------------------------------------------------------------------------------------------------ backend helpers
def _scan(xp, f, init, xs, reverse=False):
    """jax.lax.scan semantics (ys stacked in the order of xs, also when reverse) for numpy and jax."""
    if xp is np:
        n = xs[0].shape[0]; ys = [None] * n; c = init
        for i in (range(n - 1, -1, -1) if reverse else range(n)):
            c, y = f(c, tuple(x[i] for x in xs)); ys[i] = y
        if isinstance(ys[0], tuple): return c, tuple(np.stack([y[j] for y in ys]) for j in range(len(ys[0])))
        return c, np.stack(ys)
    import jax
    return jax.lax.scan(f, init, xs, reverse=reverse)


def qsat(T, p, xp=np):
    """same saturation formula as mm2.py (over water)."""
    es = 611.2 * xp.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / xp.maximum(p - 0.378 * es, 1.0)


E_REF = float(611.2 * np.exp(17.67 * (260.0 - 273.15) / (260.0 - 29.65)))   # vapour pressure at 260 K, 100 % RH (SSM reference)


# ------------------------------------------------------------------------------------------------ long-wave spectral setup
_NU = np.arange(10.0, 3000.0) + 0.5                              # 1 cm-1 bins
def _k_h2o_line(nu):
    rot = np.where(nu < 200, 37.0, 37.0 * np.exp(-(nu - 200.0) / 56.0))
    vr = np.where(nu < 1450, 5.0 * np.exp(-(1450.0 - nu) / 37.0), np.where(nu < 1700, 5.0, 5.0 * np.exp(-(nu - 1700.0) / 52.0)))
    return np.where(nu < 1000, rot, vr)
def _k_co2(nu):
    return np.where((nu > 500) & (nu < 850), 110.0 * np.exp(-np.abs(nu - 667.0) / 12.0), 0.0)
def _k_cnt(nu):
    return np.where(nu < 1700, 0.004, 0.0002)

_KH, _KC, _KN = _k_h2o_line(_NU), _k_co2(_NU), _k_cnt(_NU)
_O3 = (_NU >= 980) & (_NU < 1100)
# bands: (name, lo, hi, key array, thresholds on the key, descending)
_BANDS = [('h2o_rot', 10, 560, _KH, [20.0, 3.0, 0.5, 0.15]),
          ('co2', 560, 800, _KC, [12.0, 1.6, 0.2, 0.03]),
          ('window', 800, 1250, _O3.astype(float), [0.5]),
          ('h2o_vr', 1250, 3000, _KH, [1.5, 0.3, 0.05, 0.005])]

def _lw_terms():
    groups, names = [], []
    for name, lo, hi, key, th in _BANDS:
        inb = (_NU >= lo) & (_NU < hi); edges = [np.inf] + th + [-np.inf]
        for j in range(len(edges) - 1):
            m = inb & (key < edges[j]) & (key >= edges[j + 1])
            if m.any(): groups.append(m); names.append(f'{name}{j}')
    logmean = lambda k, m: float(np.exp(np.mean(np.log(k[m] + 1e-12))))
    kh = np.array([logmean(_KH, m) for m in groups]); kc = np.array([logmean(_KC, m) for m in groups])
    kc = np.where(kc < 1e-6, 0.0, kc); kn = np.array([_KN[m].mean() for m in groups])
    ko = np.array([1.0 if (_O3[m].mean() > 0.5) else 0.0 for m in groups])
    # Planck fractions on a temperature grid, normalised to sum 1, fitted by a degree-5 polynomial in x = (T - 250) / 100
    h, c, kb = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    Tg = np.arange(140.0, 361.0, 1.0); nu_m = _NU * 100.0
    piB = 2 * np.pi * h * c ** 2 * nu_m[None] ** 3 / np.expm1(h * c * nu_m[None] / (kb * Tg[:, None])) * 100.0   # W m-2 per 1 cm-1 bin
    fr = np.stack([piB[:, m].sum(1) for m in groups], 1); fr = fr / fr.sum(1, keepdims=True)
    x = (Tg - 250.0) / 100.0; coef = np.stack([np.polyfit(x, fr[:, g], 5) for g in range(len(groups))], 0)   # [G, 6], highest power first
    err = np.abs(np.stack([np.polyval(coef[g], x) for g in range(len(groups))], 1) - fr).max()
    return names, kh, kc, kn, ko, coef, float(err), groups

LW_NAMES, LW_KH2O_LOGMEAN, LW_KCO2_LOGMEAN, LW_KCNT_MEAN, LW_O3, LW_PCOEF, LW_PFIT_ERR, _LW_GROUPS = _lw_terms()
NG_LW = len(LW_NAMES)
# Calibration of the spectral model (SSM) itself: H2O lines, CO2 and the continuum x 1.5. The SSM fits the MEDIAN absorption
# of 25 cm-1 bins and has no foreign continuum, CH4, N2O, CFCs or CO2 window bands; x 1.5 brings the 1 cm-1 SSM to the
# targets (tropical clear OLR 286, surface down 410 W m-2). Then the effective coefficients of each term were fitted
# (grid search, test_radcloud.py --refit) to the 1 cm-1 calibrated SSM on four columns (AFGL tropical, mid-latitude
# summer, tropical with a dry free troposphere, warmer moister tropical): fluxes within 1.3 W m-2, heating within 0.22 K/day.
SSM_LINE_FAC, SSM_CNT_FAC = 1.5, 1.5
#                     H2O line (m2/kg at 500 hPa)  CO2 (m2/kg at 500 hPa)  continuum (m2/kg at e = E_REF, 260 K)
_LW_FIT = np.array([[48.71, 0.0, 0.03], [10.69, 0.0, 0.0012], [1.684, 0.0, 0.0012], [0.4442, 0.0, 0.0012], [0.131, 0.02141, 0.006],   # h2o_rot0-4
                    [0.001326, 49.23, 0.006], [0.04329, 5.88, 0.006], [0.006467, 0.7633, 0.006], [0.0196, 0.1478, 0.006], [0.002503, 0.0444, 0.006],   # co2 0-4
                    [0.0001539, 0.0, 0.006], [0.001864, 0.0, 0.006],                                                         # window: ozone part, rest
                    [6.725, 0.0, 0.0009994], [0.9224, 0.0, 0.0005337], [0.17, 0.0, 0.0005332], [0.04804, 0.0, 0.000288], [8.863e-08, 0.0, 0.000788]])  # h2o_vr0-4
assert len(_LW_FIT) == NG_LW, 'term definitions changed: refit (test_radcloud.py --refit)'
LW_KH2O, LW_KCO2, LW_KCNT = _LW_FIT[:, 0], _LW_FIT[:, 1], _LW_FIT[:, 2]

def planck_fractions(T, xp=np):
    """Planck fraction of each long-wave term, shape T.shape[:-2] + (G,) + T.shape[-2:] (T at least 2-D)."""
    x = xp.expand_dims((T - 250.0) / 100.0, -3); f = 0.0
    for j in range(LW_PCOEF.shape[1]): f = f * x + LW_PCOEF[:, j].astype(np.float32).reshape(-1, 1, 1)
    return xp.maximum(f, 0.0)

# ------------------------------------------------------------------------------------------------ short-wave terms
#                 UV       VIS      NIR0      NIR1     NIR2     NIR3     NIR4
SW_NAMES = ['uv', 'vis', 'nir0', 'nir1', 'nir2', 'nir3', 'nir4']
SW_W = np.array([0.040, 0.430, 0.2468, 0.1443, 0.0584, 0.0335, 0.0470])          # fraction of the solar constant
SW_KH2O = np.array([0.0, 0.0, 0.0006, 0.035, 0.377, 1.95, 30.0]) * 0.1           # m2/kg (Lacis & Hansen cm2/g x 0.1), x p/1013 hPa
SW_KO3 = np.array([150.0, 4.7, 0.0, 0.0, 0.0, 0.0, 0.0])                          # m2/kg ozone
SW_TAUR = np.array([0.80, 0.13, 0.02, 0.005, 0.002, 0.001, 0.001])               # Rayleigh optical depth of a 1013 hPa column
SW_COALB = np.array([0.0, 0.0, 5e-5, 1e-3, 1e-2, 4e-2, 0.15])                     # cloud co-albedo (liquid, r_e = 10 um)
NG_SW = len(SW_NAMES)

def _c(a): return np.asarray(a, np.float32).reshape(-1, 1, 1)

# ------------------------------------------------------------------------------------------------ ozone
def ozone_mmr(p, xp=np):
    """climatological tropical ozone mass mixing ratio (kg/kg) vs pressure: peak 8 ppmv near 10 hPa, ~40 ppbv in the troposphere."""
    lp = xp.log(xp.maximum(p, 1.0) / 1000.0)
    w = xp.where(lp < 0, 1.3, 0.9).astype(lp.dtype)
    vmr = 8e-6 * xp.exp(-lp ** 2 / (2 * w ** 2)) + 4e-8
    return vmr * 48.0 / 28.96

def ozone_layer_mass(p, dp, xp=np, n=6):
    """ozone mass per layer (kg m-2), averaging the mixing ratio over n points across each layer."""
    pt = p - 0.5 * dp; acc = 0.0
    for j in range(n): acc = acc + ozone_mmr(pt + (j + 0.5) / n * dp, xp)
    return acc / n * dp / G

# ------------------------------------------------------------------------------------------------ clouds
def total_cover(c, xp=np):
    """maximum-random total cloud cover (Geleyn & Hollingsworth 1979); c [L, X, Y] top first."""
    cprev = xp.concatenate([xp.zeros_like(c[:1]), c[:-1]], 0)
    r = (1.0 - xp.maximum(c, cprev)) / xp.maximum(1.0 - cprev, 1e-6)
    return 1.0 - xp.prod(r, axis=0)

def clouds(T, q, p, dp, ps, sea, conv_mask=None, conv_rain=None, conv_src=None, ls_cond=None, xp=np, prm=None):
    """Diagnostic cloud fraction and in-cloud condensate.
    conv_mask [L,X,Y] bool: layers inside active convection (mm2: cm = reg & ok[None]); conv_rain [X,Y] kg m-2 s-1;
    conv_src [L,X,Y] kg m-2 s-1 convective rain production per layer (mm2: Pconv_src); ls_cond [L,X,Y] kg/kg/s
    (mm2: cond). Returns dict: c (fraction), lwp/iwp (in-cloud, kg m-2 per layer), re_l/re_i (m), cover, fractions."""
    P = dict(DEFAULTS); P.update(prm or {})
    mass = dp / G; sig = p / ps; qs = qsat(T, p, xp); rh = xp.clip(q / qs, 0.0, 1.0)
    rhc = P['rhc_up'] + (P['rhc_low'] - P['rhc_up']) * xp.exp(1.0 - xp.maximum(sig, 0.05) ** (-P['rhc_n']))
    c_ls = 1.0 - xp.sqrt(xp.clip((1.0 - rh) / (1.0 - rhc), 0.0, 1.0))
    c_ls = xp.where(sig > P['sig_min'], c_ls, 0.0)
    qg = c_ls * P['b_ls'] * qs                                               # grid-mean condensate, kg/kg
    if ls_cond is not None: qg = qg + xp.maximum(ls_cond, 0.0) * P['tau_ls']
    c_tow = xp.zeros_like(T); c_anv = xp.zeros_like(T)
    if conv_mask is not None and conv_rain is not None:
        cm = conv_mask; Pr = xp.maximum(conv_rain, 0.0); Pmm = Pr * 86400.0
        cct = xp.clip(P['cv_a'] + P['cv_b'] * xp.log(xp.maximum(Pmm, 1e-6)), 0.0, P['cv_max'])
        cct = xp.where(xp.any(cm, axis=0) & (Pmm > 0), cct, 0.0)
        c_tow = xp.where(cm, P['f_tow'] * cct, 0.0)
        mtow = xp.maximum(xp.sum(xp.where(cm, mass, 0.0), axis=0), 1.0)
        src = conv_src if conv_src is not None else xp.where(cm, Pr * mass / mtow, 0.0)
        qg = qg + xp.where(cm, xp.minimum(xp.maximum(src, 0.0) / mass * P['tau_cv'], c_tow * P['q_cap']), 0.0)
        ptop = xp.min(xp.where(cm, p, 1e7), axis=0)
        anv = cm & (p <= ptop + P['anv_dp']) & (ptop < P['anv_ptop'])
        c_anv = xp.where(anv, xp.clip(P['anv_a'] * (cct - P['anv_c0']), 0.0, P['anv_max']), 0.0)
        manv = xp.maximum(xp.sum(xp.where(anv, mass, 0.0), axis=0), 1.0)
        W_anv = P['eps_det'] * Pr * P['tau_anv'] * (xp.max(c_anv, axis=0) > 0)         # kg m-2, grid mean
        qg = qg + xp.where(anv, W_anv / manv, 0.0)
    c_st = xp.maximum(c_ls, c_anv)
    c = xp.clip(1.0 - (1.0 - c_st) * (1.0 - c_tow), 0.0, P['c_max'])
    qin = xp.where(c > 1e-3, xp.minimum(qg / xp.maximum(c, 1e-3), P['q_cap']), 0.0)
    c = xp.where(qin > 0, c, 0.0)
    fl = xp.clip((T - 253.15) / 10.0, 0.0, 1.0)
    lwp = qin * fl * mass; iwp = qin * (1.0 - fl) * mass                  # in-cloud paths, kg m-2
    re_l = xp.where(sea, P['re_sea'], P['re_land']).astype(T.dtype) * 1e-6 * xp.ones_like(T)
    re_i = xp.clip(P['re_ice_min'] + (P['re_ice_max'] - P['re_ice_min']) * (T - 213.15) / 40.0, P['re_ice_min'], P['re_ice_max']) * 1e-6
    return dict(c=c, lwp=lwp, iwp=iwp, re_l=re_l, re_i=re_i, cover=total_cover(c, xp), c_ls=c_ls, c_tow=c_tow, c_anv=c_anv)

# ------------------------------------------------------------------------------------------------ long-wave
def _interface_T(T, p, dp, ps, xp):
    pt = p - 0.5 * dp
    w = xp.log(pt[1:] / p[:-1]) / xp.log(p[1:] / p[:-1])
    Tin = T[:-1] + (T[1:] - T[:-1]) * w
    Tb = T[-1] + (T[-1] - T[-2]) * xp.log(ps / p[-1]) / xp.log(p[-1] / p[-2])
    return xp.concatenate([T[:1], Tin, Tb[None]], 0)                       # [L+1]

def _lin_tau_source(tau, t, Bt, Bb, xp):
    r = xp.where(tau > 1e-4, (1.0 - t) / xp.maximum(tau, 1e-4), 1.0 - 0.5 * tau)
    return Bt * (1.0 - t) + (Bb - Bt) * (1.0 - r), Bb * (1.0 - t) + (Bt - Bb) * (1.0 - r)     # (down at bottom, up at top)

def longwave(T, q, p, dp, ps, Ts, cl, xp=np, prm=None, o3=None, clear_sky=False):
    """cl: output of clouds(). Returns heating (K/s), OLR, surface down/up, fluxes at interfaces (summed over terms).
    GPU note: per-term optics ([G,X,Y]) are computed level by level inside the sweeps from [X,Y] inputs (and again in
    the second sweep) instead of being stored as [L,G,X,Y] arrays: little memory, little memory traffic."""
    P = dict(DEFAULTS); P.update(prm or {})
    mass = dp / G
    if o3 is None: o3 = ozone_layer_mass(p, dp, xp)
    e = q * p / (0.622 + 0.378 * q)
    qco2 = P['co2_ppm'] * 1e-6 * 44.01 / 28.96
    a_line = P['lw_line'] * D_LW * p / PREF_LINE * q * mass                    # absorber amounts per layer [L,X,Y]
    a_cnt = P['lw_cnt'] * D_LW * e / E_REF * xp.exp(0.02 * (260.0 - T)) * q * mass
    a_co2 = D_LW * p / PREF_LINE * qco2 * mass; a_o3 = D_LW * P['k_o3_lw'] * o3
    kap_i = P['k_ice0'] + 1.0 / xp.maximum(cl['re_i'] * 1e6, 1.0)
    tcl = D_LW * 1000.0 * (P['k_liq'] * cl['lwp'] + kap_i * cl['iwp'])        # in-cloud absorption optical depth, g m-2 x m2 g-1
    Ti = _interface_T(T, p, dp, ps, xp)
    KH, KN, KC, KO = _c(LW_KH2O), _c(LW_KCNT), _c(LW_KCO2), _c(LW_O3)
    Bs = planck_fractions(Ts, xp) * (SB * Ts ** 4)                            # [G, X, Y]
    def layer(al, an, ac, ao, tc, tt, tb):
        tau = KH * al + KN * an + KC * ac + KO * ao                           # [G, X, Y], diffusivity included
        Bt = planck_fractions(tt, xp) * (SB * tt ** 4); Bb = planck_fractions(tb, xp) * (SB * tb ** 4)
        t_c = xp.exp(-tau); dn_c, up_c = _lin_tau_source(tau, t_c, Bt, Bb, xp)
        tau_k = tau + tc; t_k = xp.exp(-tau_k); dn_k, up_k = _lin_tau_source(tau_k, t_k, Bt, Bb, xp)
        return t_c, t_k, dn_c, dn_k, up_c, up_k
    def transfer(Fc, Fk, ca, cb):
        """max-random hand-over of clear/cloudy area-weighted fluxes from a layer with cloud ca to the next with cb."""
        ov = xp.minimum(ca, cb); akk = ov / xp.maximum(ca, 1e-6); ack = (cb - ov) / xp.maximum(1.0 - ca, 1e-6)
        return Fk * (1.0 - akk) + Fc * (1.0 - ack), Fk * akk + Fc * ack
    def sweeps(c):
        xs = (a_line, a_cnt, a_co2, a_o3, tcl, Ti[:-1], Ti[1:], c)
        def fdn(carry, x):
            Dc, Dk, cp = carry; ck = x[-1]
            t_c, t_k, dn_c, dn_k, _, _ = layer(*x[:-1])
            Dc, Dk = transfer(Dc, Dk, cp, ck)
            Dc = Dc * t_c + (1.0 - ck) * dn_c; Dk = Dk * t_k + ck * dn_k
            return (Dc, Dk, ck), xp.sum(Dc + Dk, axis=-3)
        z = xp.zeros_like(Bs)
        _, Dbot = _scan(xp, fdn, (z, z, xp.zeros_like(Ts)), xs)                 # downward flux at each layer's bottom
        def fup(carry, x):
            Uc, Uk, cb = carry; ck = x[-1]
            t_c, t_k, _, _, up_c, up_k = layer(*x[:-1])
            Uc, Uk = transfer(Uc, Uk, cb, ck)
            Uc = Uc * t_c + (1.0 - ck) * up_c; Uk = Uk * t_k + ck * up_k
            return (Uc, Uk, ck), xp.sum(Uc + Uk, axis=-3)
        _, Utop = _scan(xp, fup, ((1.0 - c[-1]) * Bs, c[-1] * Bs, c[-1]), xs, reverse=True)   # upward flux at each layer's top
        Usfc = xp.sum(Bs, axis=-3)                                         # = sigma Ts^4 to the Planck-fit accuracy
        Ubot = xp.concatenate([Utop[1:], Usfc[None]], 0); Dtop = xp.concatenate([xp.zeros_like(Ts)[None], Dbot[:-1]], 0)
        hr = ((Ubot - Dbot) - (Utop - Dtop)) * G / (CP * dp)
        return dict(heating=hr, olr=Utop[0], dn_sfc=Dbot[-1], up_sfc=Usfc, Utop=Utop, Dbot=Dbot)
    out = sweeps(cl['c'])
    if clear_sky:
        cs = sweeps(xp.zeros_like(cl['c'])); out.update(olr_clr=cs['olr'], dn_sfc_clr=cs['dn_sfc'], heating_clr=cs['heating'])
    return out

# ------------------------------------------------------------------------------------------------ short-wave terms
#                 UV       VIS      NIR0      NIR1     NIR2     NIR3     NIR4
SW_NAMES = ['uv', 'vis', 'nir0', 'nir1', 'nir2', 'nir3', 'nir4']
SW_W = np.array([0.040, 0.430, 0.2468, 0.1443, 0.0584, 0.0335, 0.0470])          # fraction of the solar constant
SW_KH2O = np.array([0.0, 0.0, 0.0006, 0.035, 0.377, 1.95, 30.0]) * 0.1           # m2/kg (Lacis & Hansen cm2/g x 0.1), x p/1013 hPa
SW_KO3 = np.array([150.0, 4.7, 0.0, 0.0, 0.0, 0.0, 0.0])                          # m2/kg ozone
SW_TAUR = np.array([0.80, 0.13, 0.02, 0.005, 0.002, 0.001, 0.001])               # Rayleigh optical depth of a 1013 hPa column
SW_COALB = np.array([0.0, 0.0, 5e-5, 1e-3, 1e-2, 4e-2, 0.15])                     # cloud co-albedo (liquid, r_e = 10 um)
NG_SW = len(SW_NAMES)

def _c(a): return np.asarray(a, np.float32).reshape(-1, 1, 1)

# ------------------------------------------------------------------------------------------------ ozone
def ozone_mmr(p, xp=np):
    """climatological tropical ozone mass mixing ratio (kg/kg) vs pressure: peak 8 ppmv near 10 hPa, ~40 ppbv in the troposphere."""
    lp = xp.log(xp.maximum(p, 1.0) / 1000.0)
    w = xp.where(lp < 0, 1.3, 0.9).astype(lp.dtype)
    vmr = 8e-6 * xp.exp(-lp ** 2 / (2 * w ** 2)) + 4e-8
    return vmr * 48.0 / 28.96

def ozone_layer_mass(p, dp, xp=np, n=6):
    """ozone mass per layer (kg m-2), averaging the mixing ratio over n points across each layer."""
    pt = p - 0.5 * dp; acc = 0.0
    for j in range(n): acc = acc + ozone_mmr(pt + (j + 0.5) / n * dp, xp)
    return acc / n * dp / G

# ------------------------------------------------------------------------------------------------ clouds
def total_cover(c, xp=np):
    """maximum-random total cloud cover (Geleyn & Hollingsworth 1979); c [L, X, Y] top first."""
    cprev = xp.concatenate([xp.zeros_like(c[:1]), c[:-1]], 0)
    r = (1.0 - xp.maximum(c, cprev)) / xp.maximum(1.0 - cprev, 1e-6)
    return 1.0 - xp.prod(r, axis=0)

def clouds(T, q, p, dp, ps, sea, conv_mask=None, conv_rain=None, conv_src=None, ls_cond=None, xp=np, prm=None):
    """Diagnostic cloud fraction and in-cloud condensate.
    conv_mask [L,X,Y] bool: layers inside active convection (mm2: cm = reg & ok[None]); conv_rain [X,Y] kg m-2 s-1;
    conv_src [L,X,Y] kg m-2 s-1 convective rain production per layer (mm2: Pconv_src); ls_cond [L,X,Y] kg/kg/s
    (mm2: cond). Returns dict: c (fraction), lwp/iwp (in-cloud, kg m-2 per layer), re_l/re_i (m), cover, fractions."""
    P = dict(DEFAULTS); P.update(prm or {})
    mass = dp / G; sig = p / ps; qs = qsat(T, p, xp); rh = xp.clip(q / qs, 0.0, 1.0)
    rhc = P['rhc_up'] + (P['rhc_low'] - P['rhc_up']) * xp.exp(1.0 - xp.maximum(sig, 0.05) ** (-P['rhc_n']))
    c_ls = 1.0 - xp.sqrt(xp.clip((1.0 - rh) / (1.0 - rhc), 0.0, 1.0))
    c_ls = xp.where(sig > P['sig_min'], c_ls, 0.0)
    qg = c_ls * P['b_ls'] * qs                                               # grid-mean condensate, kg/kg
    if ls_cond is not None: qg = qg + xp.maximum(ls_cond, 0.0) * P['tau_ls']
    c_tow = xp.zeros_like(T); c_anv = xp.zeros_like(T)
    if conv_mask is not None and conv_rain is not None:
        cm = conv_mask; Pr = xp.maximum(conv_rain, 0.0); Pmm = Pr * 86400.0
        cct = xp.clip(P['cv_a'] + P['cv_b'] * xp.log(xp.maximum(Pmm, 1e-6)), 0.0, P['cv_max'])
        cct = xp.where(xp.any(cm, axis=0) & (Pmm > 0), cct, 0.0)
        c_tow = xp.where(cm, P['f_tow'] * cct, 0.0)
        mtow = xp.maximum(xp.sum(xp.where(cm, mass, 0.0), axis=0), 1.0)
        src = conv_src if conv_src is not None else xp.where(cm, Pr * mass / mtow, 0.0)
        qg = qg + xp.where(cm, xp.minimum(xp.maximum(src, 0.0) / mass * P['tau_cv'], c_tow * P['q_cap']), 0.0)
        ptop = xp.min(xp.where(cm, p, 1e7), axis=0)
        anv = cm & (p <= ptop + P['anv_dp']) & (ptop < P['anv_ptop'])
        c_anv = xp.where(anv, xp.clip(P['anv_a'] * (cct - P['anv_c0']), 0.0, P['anv_max']), 0.0)
        manv = xp.maximum(xp.sum(xp.where(anv, mass, 0.0), axis=0), 1.0)
        W_anv = P['eps_det'] * Pr * P['tau_anv'] * (xp.max(c_anv, axis=0) > 0)         # kg m-2, grid mean
        qg = qg + xp.where(anv, W_anv / manv, 0.0)
    c_st = xp.maximum(c_ls, c_anv)
    c = xp.clip(1.0 - (1.0 - c_st) * (1.0 - c_tow), 0.0, P['c_max'])
    qin = xp.where(c > 1e-3, xp.minimum(qg / xp.maximum(c, 1e-3), P['q_cap']), 0.0)
    c = xp.where(qin > 0, c, 0.0)
    fl = xp.clip((T - 253.15) / 10.0, 0.0, 1.0)
    lwp = qin * fl * mass; iwp = qin * (1.0 - fl) * mass                  # in-cloud paths, kg m-2
    re_l = xp.where(sea, P['re_sea'], P['re_land']).astype(T.dtype) * 1e-6 * xp.ones_like(T)
    re_i = xp.clip(P['re_ice_min'] + (P['re_ice_max'] - P['re_ice_min']) * (T - 213.15) / 40.0, P['re_ice_min'], P['re_ice_max']) * 1e-6
    return dict(c=c, lwp=lwp, iwp=iwp, re_l=re_l, re_i=re_i, cover=total_cover(c, xp), c_ls=c_ls, c_tow=c_tow, c_anv=c_anv)

# ------------------------------------------------------------------------------------------------ long-wave
def _interface_T(T, p, dp, ps, xp):
    pt = p - 0.5 * dp
    w = xp.log(pt[1:] / p[:-1]) / xp.log(p[1:] / p[:-1])
    Tin = T[:-1] + (T[1:] - T[:-1]) * w
    Tb = T[-1] + (T[-1] - T[-2]) * xp.log(ps / p[-1]) / xp.log(p[-1] / p[-2])
    return xp.concatenate([T[:1], Tin, Tb[None]], 0)                       # [L+1]

def _lin_tau_source(tau, t, Bt, Bb, xp):
    r = xp.where(tau > 1e-4, (1.0 - t) / xp.maximum(tau, 1e-4), 1.0 - 0.5 * tau)
    return Bt * (1.0 - t) + (Bb - Bt) * (1.0 - r), Bb * (1.0 - t) + (Bt - Bb) * (1.0 - r)     # (down at bottom, up at top)

def longwave(T, q, p, dp, ps, Ts, cl, xp=np, prm=None, o3=None, clear_sky=False):
    """cl: output of clouds(). Returns dict with fluxes at interfaces (summed over terms) and heating (K/s)."""
    P = dict(DEFAULTS); P.update(prm or {})
    mass = dp / G; L = T.shape[0]
    if o3 is None: o3 = ozone_layer_mass(p, dp, xp)
    e = q * p / (0.622 + 0.378 * q)
    qco2 = P['co2_ppm'] * 1e-6 * 44.01 / 28.96
    X = lambda a: xp.expand_dims(a, 1)                                     # [L,X,Y] -> [L,1,X,Y]
    tau = D_LW * (P['lw_line'] * _c(LW_KH2O) * X(p / PREF_LINE * q * mass)
                  + P['lw_cnt'] * _c(LW_KCNT) * X(e / E_REF * xp.exp(0.02 * (260.0 - T)) * q * mass)
                  + _c(LW_KCO2) * X(p / PREF_LINE * qco2 * mass) + _c(LW_O3) * P['k_o3_lw'] * X(o3))
    Ti = _interface_T(T, p, dp, ps, xp)
    Bi = planck_fractions(Ti, xp) * X(SB * Ti ** 4)                        # [L+1, G, X, Y]
    Bs = planck_fractions(Ts, xp) * (SB * Ts ** 4)                         # [G, X, Y]
    t_c = xp.exp(-tau); dn_c, up_c = _lin_tau_source(tau, t_c, Bi[:-1], Bi[1:], xp)
    def sweeps(c):
        kap_i = P['k_ice0'] + 1.0 / xp.maximum(cl['re_i'] * 1e6, 1.0)
        tc = D_LW * 1000.0 * (P['k_liq'] * cl['lwp'] + kap_i * cl['iwp'])   # g m-2 x m2 g-1
        tau_k = tau + X(tc); t_k = xp.exp(-tau_k); dn_k, up_k = _lin_tau_source(tau_k, t_k, Bi[:-1], Bi[1:], xp)
        def fdn(carry, x):
            Dc, Dk, cp = carry; tc_, tk_, ec, ek, ck = x
            ov = xp.minimum(cp, ck); akk = ov / xp.maximum(cp, 1e-6); ack = (ck - ov) / xp.maximum(1.0 - cp, 1e-6)
            Dki = Dk * akk + Dc * ack; Dci = Dk * (1.0 - akk) + Dc * (1.0 - ack)
            Dc = Dci * tc_ + (1.0 - ck) * ec; Dk = Dki * tk_ + ck * ek
            return (Dc, Dk, ck), xp.sum(Dc + Dk, axis=-3)
        z = xp.zeros_like(Bs)
        _, Dbot = _scan(xp, fdn, (z, z, xp.zeros_like(Ts)), (t_c, t_k, dn_c, dn_k, c))
        def fup(carry, x):
            Uc, Uk, cb = carry; tc_, tk_, ec, ek, ck = x
            ov = xp.minimum(cb, ck); akk = ov / xp.maximum(cb, 1e-6); ack = (ck - ov) / xp.maximum(1.0 - cb, 1e-6)
            Uki = Uk * akk + Uc * ack; Uci = Uk * (1.0 - akk) + Uc * (1.0 - ack)
            Uc = Uci * tc_ + (1.0 - ck) * ec; Uk = Uki * tk_ + ck * ek
            return (Uc, Uk, ck), xp.sum(Uc + Uk, axis=-3)
        _, Utop = _scan(xp, fup, ((1.0 - c[-1]) * Bs, c[-1] * Bs, c[-1]), (t_c, t_k, up_c, up_k, c), reverse=True)
        Usfc = xp.sum(Bs, axis=-3)                                         # = sigma Ts^4 to the Planck-fit accuracy
        Ubot = xp.concatenate([Utop[1:], Usfc[None]], 0); Dtop = xp.concatenate([xp.zeros_like(Ts)[None], Dbot[:-1]], 0)
        hr = ((Ubot - Dbot) - (Utop - Dtop)) * G / (CP * dp)
        return dict(heating=hr, olr=Utop[0], dn_sfc=Dbot[-1], up_sfc=Usfc, Utop=Utop, Dbot=Dbot)
    out = sweeps(cl['c'])
    if clear_sky:
        cs = sweeps(xp.zeros_like(cl['c'])); out.update(olr_clr=cs['olr'], dn_sfc_clr=cs['dn_sfc'], heating_clr=cs['heating'])
    return out

# ------------------------------------------------------------------------------------------------ short-wave
def _delta_eddington(tau, w, g, mu, xp):
    """layer reflectance/transmittance (Briegleb 1992 / CCM3 form of delta-Eddington). Returns Rdir, Tdir (total
    transmission of the direct beam), Rdif, Tdif, direct transmission e."""
    f = g * g; tau_ = tau * (1.0 - w * f); w_ = xp.minimum(w * (1.0 - f) / (1.0 - w * f), 1.0 - 1e-6); g_ = g / (1.0 + g)
    lm = xp.sqrt(3.0 * (1.0 - w_) * (1.0 - w_ * g_)); ue = 1.5 * (1.0 - w_ * g_) / lm
    ex = xp.exp(-xp.minimum(lm * tau_, 30.0)); ne = (ue + 1.0) ** 2 / ex - (ue - 1.0) ** 2 * ex
    rdif = (ue + 1.0) * (ue - 1.0) * (1.0 / ex - ex) / ne; tdif = 4.0 * ue / ne
    den = 1.0 - lm * lm * mu * mu; den = xp.where(xp.abs(den) < 1e-3, xp.where(den < 0, -1e-3, 1e-3).astype(den.dtype), den)
    alp = 0.75 * w_ * mu * (1.0 + g_ * (1.0 - w_)) / den; gam = 0.5 * w_ * (1.0 + 3.0 * g_ * (1.0 - w_) * mu * mu) / den
    e = xp.exp(-xp.minimum(tau_ / mu, 80.0)); apg = alp + gam; amg = alp - gam
    rdir = xp.clip(amg * (tdif * e - 1.0) + apg * rdif, 0.0, 1.0)
    tdir = xp.clip(apg * tdif + (amg * rdif - (apg - 1.0)) * e, 0.0, 1.0)
    return rdir, xp.maximum(tdir, e), rdif, tdif, e

def shortwave(T, q, p, dp, ps, sea, mu0, cl, xp=np, prm=None, o3=None, s0=None):
    """Two columns (clear; cloudy with the in-cloud optical depth spread over the total cover) weighted by the total
    cover. Adding method: an upward sweep builds the reflectance of everything below each interface, a downward sweep
    the fluxes; layer optics are recomputed in each sweep from [X,Y] inputs (GPU memory traffic, as in longwave)."""
    P = dict(DEFAULTS); P.update(prm or {})
    s0 = P['s0'] if s0 is None else s0
    mass = dp / G
    if o3 is None: o3 = ozone_layer_mass(p, dp, xp)
    mu = xp.maximum(mu0, 0.0); mue = xp.sqrt(1224.0 * mu * mu + 1.0) / 35.0       # slant path with Earth curvature
    a_h2o = q * mass * p / 101325.0; a_r = dp / 101325.0
    adir = xp.where(sea, 0.037 / (1.1 * xp.maximum(mu, 0.01) ** 1.4 + 0.15), P['alb_land'])
    adif = xp.where(sea, P['alb_sea_dif'], P['alb_land']).astype(mu.dtype)
    Sin = _c(SW_W) * (s0 * mu)                                                  # [G,X,Y]
    KH, KO, TR, CO = _c(SW_KH2O), _c(SW_KO3), _c(SW_TAUR), _c(SW_COALB)
    def layer(ah, ao, ar, tl, ti, ca):
        """per-term layer optics [G,X,Y]; tl, ti: cloud optical depths (liquid, ice), ca: co-albedo weight."""
        tau_c = tl + ti; tau_r = TR * ar
        sc = xp.clip(tau_c - CO * ca, 0.0, tau_c)                                 # cloud scattering optical depth
        tau = KH * ah + KO * ao + tau_r + tau_c
        w = (tau_r + sc) / xp.maximum(tau, 1e-12)
        g = (P['g_liq'] * tl + P['g_ice'] * ti) * (sc / xp.maximum(tau_c, 1e-12)) / xp.maximum(tau_r + sc, 1e-12)
        return _delta_eddington(tau, xp.minimum(w, 1.0 - 1e-6), g, mue, xp)
    def column(tl, ti):
        ca = tl * cl['re_l'] / 10e-6 + ti * cl['re_i'] / 20e-6                   # co-albedo weight: absorption grows with r_e
        xs = (a_h2o, o3, a_r, tl, ti, ca)
        def fup(carry, x):
            Rb, Rbd = carry; rdr, tdr, rdf, tdf, e_ = layer(*x)
            den = 1.0 / (1.0 - rdf * Rbd)
            return (rdr + ((tdr - e_) * Rbd + e_ * Rb) * tdf * den, rdf + tdf * tdf * Rbd * den), (Rb, Rbd)
        one = xp.ones_like(Sin)
        _, (Rb, Rbd) = _scan(xp, fup, (adir * one, adif * one), xs, reverse=True)   # reflectance below each layer
        def fdn(carry, x):
            Sd, Dd = carry; rb, rbd = x[-2:]; rdr, tdr, rdf, tdf, e_ = layer(*x[:-2])
            den = 1.0 / (1.0 - rdf * rbd)
            rt = rdr + ((tdr - e_) * rbd + e_ * rb) * tdf * den; rtd = rdf + tdf * tdf * rbd * den
            Sd1 = Sd * e_; Dd1 = ((tdr - e_) * Sd + tdf * Dd + rdf * Sd1 * rb) * den
            Ut = Sd * rt + Dd * rtd; Ub = Sd1 * rb + Dd1 * rbd
            ab = (Sd + Dd - Ut) - (Sd1 + Dd1 - Ub)
            return (Sd1, Dd1), (xp.sum(ab, axis=-3), xp.sum(Ut, axis=-3))
        (Sd, Dd), (ab, Ut) = _scan(xp, fdn, (Sin, xp.zeros_like(Sin)), xs + (Rb, Rbd))
        dn = xp.sum(Sd + Dd, axis=-3); up = xp.sum(Sd * adir + Dd * adif, axis=-3)
        return ab, dn, dn - up, Ut[0]
    z = xp.zeros_like(T)
    ab0, dn0, net0, up0 = column(z, z)
    C = cl['cover']; spread = cl['c'] / xp.maximum(C, 1e-3)
    tl = P['sw_inhom'] * 1.5 * cl['lwp'] / (RHO_W * cl['re_l']) * spread
    ti = P['sw_inhom'] * 1.5 * cl['iwp'] / (RHO_I * cl['re_i']) * spread
    ab1, dn1, net1, up1 = column(tl, ti)
    mix = lambda a, b: (1.0 - C) * a + C * b
    ab = mix(ab0, ab1)
    return dict(heating=ab * G / (CP * dp), dn_sfc=mix(dn0, dn1), net_sfc=mix(net0, net1), toa_up=mix(up0, up1), toa_dn=s0 * mu,
                net_sfc_clr=net0, dn_sfc_clr=dn0, toa_up_clr=up0, heating_clr=ab0 * G / (CP * dp))

# ------------------------------------------------------------------------------------------------ driver
def radiation(T, q, p, dp, ps, Ts, sea, mu0, conv_mask=None, conv_rain=None, conv_src=None, ls_cond=None, xp=np, prm=None,
              s0=None, clear_sky=False):
    """Clouds + long-wave + short-wave for all columns. T, q, p, dp [L,X,Y]; ps, Ts, mu0 [X,Y]; sea bool [X,Y].
    Returns heating (K/s, lw + sw), lw_heating, sw_heating, olr, lw_dn_sfc, lw_up_sfc, sw_dn_sfc, sw_net_sfc, sw_toa_up,
    cloud (fraction per layer), cover (total, max-random), lwp/iwp (grid-mean column paths, kg m-2); with clear_sky also
    clear-sky OLR, surface downward LW and LW heating."""
    cl = clouds(T, q, p, dp, ps, sea, conv_mask, conv_rain, conv_src, ls_cond, xp, prm)
    o3 = ozone_layer_mass(p, dp, xp)
    lw = longwave(T, q, p, dp, ps, Ts, cl, xp, prm, o3, clear_sky)
    sw = shortwave(T, q, p, dp, ps, sea, mu0, cl, xp, prm, o3, s0)
    out = dict(heating=lw['heating'] + sw['heating'], lw_heating=lw['heating'], sw_heating=sw['heating'], olr=lw['olr'],
               lw_dn_sfc=lw['dn_sfc'], lw_up_sfc=lw['up_sfc'], sw_dn_sfc=sw['dn_sfc'], sw_net_sfc=sw['net_sfc'], sw_toa_up=sw['toa_up'],
               sw_toa_dn=sw['toa_dn'], sw_net_sfc_clr=sw['net_sfc_clr'], sw_toa_up_clr=sw['toa_up_clr'], sw_heating_clr=sw['heating_clr'],
               cloud=cl['c'], cover=cl['cover'], lwp=xp.sum(cl['lwp'] * cl['c'], axis=0), iwp=xp.sum(cl['iwp'] * cl['c'], axis=0))
    if clear_sky: out.update(olr_clr=lw['olr_clr'], lw_dn_sfc_clr=lw['dn_sfc_clr'], lw_heating_clr=lw['heating_clr'])
    return out
