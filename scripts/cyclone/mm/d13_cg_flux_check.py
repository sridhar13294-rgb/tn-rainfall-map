"""D13 offline check (P2, 75-level blow-up): size of the explicit Troen-Mahrt counter-gradient flux in mm2 (pbl_tm = 1)
with Kh = max(Kbl, Kfree) clipped at 500 (code before 3 Nov) vs the profile K (Kbl) of the published form
(Troen & Mahrt 1986; Hong & Pan 1996): F = rho K gamma, gamma = 6.5 w'x'_0 / (ws h).
With K = Kbl = kappa ws z (1 - z/h)^2 the ws cancels and F / (rho w'x'_0) = 6.5 kappa (z/h)(1 - z/h)^2 <= 0.385.
The formulas below are copied from mm2.py (same constants); the conditions span calm-to-windy daytime boundary layers.
Lowest interfaces: 32 levels ~ 80 / 230 m, 75 levels (tp75) ~ 30 / 90 / 150 m (lowest sigmas 0.9964, 0.9893, 0.982, 0.9746).
python d13_cg_flux_check.py"""
import itertools, numpy as np
KARM, G = 0.4, 9.80616
rows = []
for ust, H, hbl, dU, dz, zh in itertools.product((0.05, 0.1, 0.2, 0.4), (10.0, 50.0, 200.0), (100.0, 300.0, 1000.0),
                                                  (0.3, 1.0, 2.0), (60.0, 150.0), (30.0, 60.0, 80.0, 150.0, 230.0)):
    if zh >= hbl: continue
    rho, cp, th = 1.15, 1004.6, 300.0
    bflux = G / th * H / (rho * cp)
    wstar = np.cbrt(bflux * hbl); ws = np.cbrt(ust ** 3 + 7.0 * 0.1 * KARM * wstar ** 3)
    Kbl = KARM * ws * zh * (1 - min(zh / hbl, 1)) ** 2
    dUdz = dU / dz; rii = -G * (0.3) / th * dz / max(dU ** 2, 1e-6)          # unstable interface (theta_v decreasing 0.3 K across dz)
    rii = max(rii, -5.0)
    Kfree = 30.0 ** 2 * dUdz * np.sqrt(1 - 18 * min(rii, 0))
    Kh = np.clip(max(Kbl, Kfree), 0, 500)
    wsh = max(ws * hbl, 1e-3)
    ratio_old = Kh * 6.5 / wsh                                                    # F / (rho w'x'_0)
    ratio_new = min(Kbl, 500) * 6.5 / wsh
    rows.append((ust, H, hbl, dU, dz, zh, ws, Kbl, Kfree, ratio_old, ratio_new))
R = np.array(rows)
print(f'{len(R)} daytime cases; F_cg / surface flux:  old (Kh) max {R[:, 9].max():.1f}, median {np.median(R[:, 9]):.2f}, '
      f'share > 1 = {np.mean(R[:, 9] > 1) * 100:.0f} %;  new (Kbl) max {R[:, 10].max():.3f} (bound 0.385)')
for zz in (30.0, 60.0, 80.0, 150.0, 230.0):
    m = R[:, 5] == zz
    print(f'  interface {zz:4.0f} m: old max {R[m, 9].max():7.1f}  share>1 {np.mean(R[m, 9] > 1) * 100:4.0f} %  | Kfree > Kbl in {np.mean(R[m, 8] > R[m, 7]) * 100:3.0f} % of cases')
# what a ratio means for the thin lowest layer at 75 levels: moisture taken per 20-min step
mass75, mass32, E, dt, q1 = 700.0 / G, 1400.0 / G * 1.0, 1e-4, 1200.0, 0.018
for r in (0.385, 5.0, 20.0, R[:, 9].max()):
    print(f'  ratio {r:6.1f}: lowest 75L layer (7 hPa) loses {r * E * dt / mass75 * 1e3:6.2f} g/kg per step vs q1 {q1 * 1e3:.0f} g/kg'
          f' (surface supplies {E * dt / mass75 * 1e3:.2f})')
worst = R[np.argmax(R[:, 9])]
print('worst case: ust %.2f H %.0f hbl %.0f dU %.1f dz %.0f z %.0f ws %.2f Kbl %.1f Kfree %.1f' % tuple(worst[:9]))
