"""D1 + D2 offline derivation (P1: 850 hPa cold in the combined fix; P4).  python cloud_derivation.py
Question: is the -3.0 K/day radiative cooling at sigma 0.862 (tropics, day 5, pbl_tm 1 + sh_mflux 0.03; control -1.1)
physical, and what do (D1) a consistent cloud scheme and (D2) cloud-top entrainment change?

Current scheme (radcloud.clouds): Sundqvist fraction c = 1 - sqrt((1-RH)/(1-RHc)), RHc ~ 0.8 low down, with in-cloud
water c * b_ls * qs + cond * tau_ls. That water is not part of the model's water budget (q is never reduced, no latent
heat), while grid-scale condensation only starts at RH = 1. => two different clouds: radiation's (from 80%) and rain's (100%).

D1 consistent cloud: one sub-grid total-water PDF for both (uniform, Smith 1990 / Le Treut & Li 1991): half-width
b = (1 - RHc) qs, so cloud starts at RH = RHc exactly as the Sundqvist curve does, and
   c  = clip((q + b - qs) / (2 b), 0, 1)
   ql = (q + b - qs)^2 / (4 b)                    (grid mean, partial cover);  q - qs when q >= qs + b
i.e. the radiation water is the model's own water above saturation in the moist part of the box, not an invented b_ls*qs.

D2 cloud-top entrainment (Lilly 1968; Lock et al. 2000; Stevens 2002): cloud-top long-wave cooling drives turbulence
that entrains warm, dry inversion air. Energy closure: rho w_e cp dtheta = A * dF_cld, with dF_cld the cloud part of the
cloud-top layer's LW flux divergence (all-sky minus clear-sky) and A the entrainment efficiency. A from observation:
DYCOMS-II RF01 (Stevens et al. 2003): w_e 3.8 mm/s, dtheta_l 8.75 K, rho 1.13, LW jump ~70 W/m2 -> A = 0.54
(ASTEX/FIRE 0.4-0.6). Tendency: exchange flux F = rho w_e (X_above - X_top) for X = s (dry static energy) and q, between
the cloud-top layer and the layer above: energy and water conserved exactly.
"""
import numpy as np, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radcloud as RC
G, CP, LV, RD, RV = 9.80616, 1004.6, 2.5e6, 287.04, 461.5

def bounds(n=32):
    e = np.linspace(0, 1, n + 1); return 0.6 * e + 0.4 * (1 - (1 - e) ** 2)
sb = bounds(); sig = 0.5 * (sb[1:] + sb[:-1]); dsig = np.diff(sb); ps = 101000.0; p = sig * ps; dp = dsig * ps; mass = dp / G
# mean tropical sounding (Jordan 1958, approximate): p hPa, T C, q g/kg
JP = np.array([1010, 1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 70, 50, 30, 10]) * 100.0
JT = np.array([26.5, 26.0, 21.8, 17.4, 8.6, 0.0, -6.7, -17.3, -32.6, -42.9, -54.8, -67.6, -73.5, -68.0, -62.0, -55.0, -45.0]) + 273.15
JQ = np.array([18.8, 18.0, 14.8, 11.6, 6.6, 4.4, 2.4, 1.2, 0.4, 0.15, 0.05, 0.01, 0.004, 0.003, 0.003, 0.003, 0.003]) * 1e-3
lp = np.log(p); T0 = np.interp(lp, np.log(JP[::-1]), JT[::-1]); q0 = np.exp(np.interp(lp, np.log(JP[::-1]), np.log(JQ[::-1])))
qs_ = lambda T: RC.qsat(T, p)
K = lambda s_: int(np.argmin(np.abs(sig - s_)))
k862, k837, k885 = K(0.862), K(0.837), K(0.885)
DECK = [K(x) for x in (0.812, 0.837, 0.862, 0.885)]          # layers of the measured cooling peak (tropics d5)
mu_list = [max(np.cos(np.radians(15 * (h - 12))), 0.0) for h in range(24)]       # equator, equinox, hourly

def rad(T, q, cond=None, prm=None, clear=False):
    S = lambda a: a.reshape(-1, 1, 1)
    out = []
    for mu in mu_list:
        R = RC.radiation(S(T), S(q), S(p), S(dp), np.array([[ps]]), np.array([[301.0]]), np.array([[True]]), np.array([[mu]]),
                         ls_cond=None if cond is None else S(cond), prm=prm, clear_sky=clear)
        out.append(R)
    m = lambda k: np.mean([o[k] for o in out], 0)
    r = dict(heat=m('heating')[:, 0, 0] * 86400, lw=m('lw_heating')[:, 0, 0] * 86400, cloud=out[0]['cloud'][:, 0, 0])
    if clear: r['lw_clr'] = m('lw_heating_clr')[:, 0, 0] * 86400
    return r

def column(rh_top, dT=0.0, lsc_Kday=0.0):
    T = T0 + dT; q = np.minimum(q0, 0.95 * qs_(T))
    for k in DECK: q[k] = rh_top * qs_(T)[k]                             # the boundary-layer-top cloud layers
    cond = np.zeros_like(T); cond[DECK] = lsc_Kday * CP / LV / 86400.0
    return T, q, cond

def calibrate(target, dT, lsc, prm=None):
    lo, hi = 0.6, 0.999
    for _ in range(30):
        m = 0.5 * (lo + hi); T, q, c = column(m, dT, lsc); h = rad(T, q, c, prm)['heat'][DECK].mean()
        lo, hi = (m, hi) if h > target else (lo, m)
    return 0.5 * (lo + hi)

if __name__ == '__main__':
    # day-5 tropics: T bias at 850 (ctl +0.8 K, combo -2.4 K), grid-scale heating at 0.862 (ctl 0.33, combo 1.56 K/day)
    print('clear-sky-like reference (RH 0.70 at the cloud layers):', round(rad(*column(0.70))['heat'][k862], 2), 'K/day at sigma', round(sig[k862], 3))
    r_c = calibrate(-0.95, 0.8, 0.30); r_x = calibrate(-2.83, -2.4, 1.32)   # measured means over the 4 deck layers
    print(f'calibrated RH at the cloud layers: control {r_c:.3f}, combo {r_x:.3f}')
    Tc, qc, cc = column(r_c, 0.8, 0.33); Tx, qx, cx = column(r_x, -2.4, 1.56)
    dq850 = (qx - qc)[k862] * 1e3
    print(f'  signature check: implied q change at 0.862 combo-ctl {dq850:+.2f} g/kg (measured d5 tropics 850 hPa: +0.78 g/kg ctl->combo; ctl -1.38, combo +0.78 vs ERA5)')
    R0 = rad(Tx, qx, cx, clear=True)
    print(f'combo, current scheme: heat {R0["heat"][k862]:.2f}, LW {R0["lw"][k862]:.2f}, LW clear {R0["lw_clr"][k862]:.2f} K/day, cloud c={R0["cloud"][k862]:.2f} (0.862) {R0["cloud"][k837]:.2f} (0.837)')
    # D1: consistent PDF cloud
    R1 = rad(Tx, qx, cx, prm=dict(pdf=1.0), clear=True)
    print(f'D1 PDF cloud:          heat {R1["heat"][k862]:.2f}, LW {R1["lw"][k862]:.2f}, c={R1["cloud"][k862]:.2f} / {R1["cloud"][k837]:.2f}   change {R1["heat"][k862]-R0["heat"][k862]:+.2f} K/day')
    # D2: entrainment at the cloud top (top layer of the deck = k837 here; the layer above = k837 - 1)
    for lab, R in (('current', R0), ('D1', R1)):
        kt = k837; ka = kt - 1
        th = Tx * (ps / p) ** 0.2857; dth = max(th[ka] - th[kt], 1.0)
        dF = max(R['lw_clr'][kt] - R['lw'][kt], 0.0) / 86400 * CP * mass[kt]        # W m-2, cloud part of the LW divergence
        for A in (0.4, 0.54, 0.6):
            rwe = A * dF / (CP * dth)                                               # kg m-2 s-1
            s = CP * Tx + G * (RD * Tx / G * np.log(ps / p)).cumsum()[::-1][::-1] * 0 + 0.0
            z = np.zeros_like(p); z[-1] = RD * Tx[-1] / G * np.log(ps / p[-1])
            for k in range(len(p) - 2, -1, -1): z[k] = z[k + 1] + RD * 0.5 * (Tx[k] + Tx[k + 1]) / G * np.log(p[k + 1] / p[k])
            s = CP * Tx + G * z
            hT = rwe * (s[ka] - s[kt]) / mass[kt] / CP * 86400; hTa = -rwe * (s[ka] - s[kt]) / mass[ka] / CP * 86400
            dqt = rwe * (qx[ka] - qx[kt]) / mass[kt] * 86400 * 1e3
            drh = dqt / (qs_(Tx)[kt] * 1e3) - 0.0
            print(f'  D2 on {lab:7s} A={A:.2f}: dF_cld {dF:5.1f} W/m2, dtheta {dth:.1f} K, w_e {rwe/1.0*1000/ (p[kt]/(RD*Tx[kt])):.1f} mm/s -> top layer {hT:+.2f} K/day & {dqt:+.2f} g/kg/day (RH {drh:+.3f}/day), layer above {hTa:+.2f} K/day')
    # what RH would the drying bring the deck to after one day, and the radiation then
    kt = k837; th = Tx * (ps / p) ** 0.2857
    dF = max(R1['lw_clr'][kt] - R1['lw'][kt], 0.0) / 86400 * CP * mass[kt]; rwe = 0.54 * dF / (CP * max(th[kt - 1] - th[kt], 1.0))
    for days in (0.25, 0.5, 1.0):
        q2 = qx.copy(); T2 = Tx.copy()
        for k_ in (k837, k862):
            q2[k_] += rwe * (qx[kt - 1] - qx[kt]) / mass[kt] * days * 86400
        R2 = rad(T2, q2, cx, prm=dict(pdf=1.0))
        print(f'  D1+D2 after {days:.2f} d of entrainment drying alone: c={R2["cloud"][k862]:.2f}/{R2["cloud"][k837]:.2f}, heat at 0.862 {R2["heat"][k862]:.2f} K/day')
