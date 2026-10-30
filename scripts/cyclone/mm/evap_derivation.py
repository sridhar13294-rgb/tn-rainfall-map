"""Rain re-evaporation: MEGAM's formula vs the Kessler (1969) form used in ECMWF IFS (Tiedtke 1993; IFS Cy4x Part IV):
  current mm2 fall():  e = k_evap (1 - RH) sqrt(a P) m           [kg m-2 s-1 per layer], k_evap 2e-5, a = ev_frac 0.3
  Kessler / IFS:       e = a k_E (qs - q) [ sqrt(p/ps) / alpha2 * P / a ]^alpha3 * m   , k_E 5.44e-4 s-1, alpha2 5.09e-3, alpha3 0.5777
P = rain flux entering the layer from above (kg m-2 s-1), a = precipitation area fraction, m = layer mass.
Column = the model's own TN coastal-sea column with F2 (tn-tnr-f2 5-day means: RH 925/850/700/500 = 0.88/0.81/0.73/0.71,
lowest-layer T 298.0 K) and a control-like column (0.54/0.55/0.80/0.72, 302.4 K); rain leaving cloud base ~850 hPa.
python evap_derivation.py"""
import numpy as np
G = 9.80616
def bounds(n=32):
    e = np.linspace(0, 1, n + 1); return 0.6 * e + 0.4 * (1 - (1 - e) ** 2)
sb = bounds(); sig = 0.5 * (sb[1:] + sb[:-1]); ps = 101000.0; p = sig * ps; m = np.diff(sb) * ps / G
def qsat(T, pp): es = 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / (pp - 0.378 * es)
def column(rh_pts, T1):
    T = T1 - 6.5e-3 * (287.04 * T1 / G) * np.log(ps / p)                       # ~moist-ish lapse, fine for evaporation
    rh = np.interp(-p, -np.array([92500, 85000, 70000, 50000.0]), rh_pts); rh = np.where(p > 92500, rh_pts[0], rh)
    return T, rh
def evap(rain_mmday, T, rh, form, a=0.3, base=85000.0):
    P = rain_mmday / 86400.0; out = np.zeros_like(p)
    for k in np.where(p > base)[0]:                                          # layers below cloud base, top -> bottom
        qs = qsat(T[k], p[k]); dq = (1 - rh[k]) * qs
        if form == 'mm2': e = 2e-5 * (1 - rh[k]) * np.sqrt(max(P, 0) * a) * m[k]
        else: e = a * 5.44e-4 * dq * (np.sqrt(p[k] / ps) / 5.09e-3 * max(P, 0) / a) ** 0.5777 * m[k]
        e = min(e, P); out[k] = e; P -= e
    return out
for lab, rhp, T1 in (('F2 coastal sea', [0.88, 0.81, 0.73, 0.71], 298.0), ('control coastal sea', [0.54, 0.55, 0.80, 0.72], 302.4)):
    T, rh = column(rhp, T1)
    for R in (5.0, 20.0):
        e1 = evap(R, T, rh, 'mm2'); e2 = evap(R, T, rh, 'kessler')
        f = lambda e: e.sum() * 86400 / R * 100
        cool = lambda e: (e * 2.5e6 / 1004.6 / m * 86400)[p > 85000].max()
        print(f'{lab:20s} rain {R:4.0f} mm/day: re-evaporated below 850 hPa  mm2 {f(e1):5.1f}%  Kessler/IFS {f(e2):5.1f}%   | peak layer cooling mm2 {cool(e1):5.2f}  Kessler {cool(e2):5.2f} K/day')
