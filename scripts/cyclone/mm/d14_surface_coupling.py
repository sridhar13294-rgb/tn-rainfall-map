"""D14 offline (P2 runaway over the Andes): stability of the explicit surface heat exchange vs the implicit form (sfc_imp).
Air layer: dT1/dt = chv cp (Ts - T1) / (cp m1); land: dTs/dt = -(chv cp + 4 sigma Ts^3)(Ts - T1)/C (other terms fixed).
Explicit Euler is stable only if dt * k / C_eff < 2 for each; implicit (backward Euler) is stable for any dt.
Values from the 9 Jun hot spot (tn-tr75-0609c): V1 50-100 m/s, lowest layer 7 hPa (75 L) vs 20 hPa (32 L), land C = 2e5 J m-2 K-1."""
import numpy as np
cp, G, SB, dt = 1004.6, 9.81, 5.67e-8, 1200.0
def run(m1, V1, ch, C, imp, n=12, T1=270.0, Ts=285.0):
    T1, Ts = np.float64(T1), np.float64(Ts); np.seterr(all='ignore')
    chv = 1.0 * ch * V1; out = []
    for _ in range(n):
        ka = chv / m1; kl = chv * cp / C                                      # land side of the same exchange (other terms held fixed)
        if imp:   # backward Euler on the 2x2 linear exchange
            A = np.array([[1 + dt * ka, -dt * ka], [-dt * chv * cp / C, 1 + dt * kl]])
            T1, Ts = np.linalg.solve(A, [T1, Ts])
        else:
            T1, Ts = T1 + dt * ka * (Ts - T1), Ts - dt * kl * (Ts - T1)
        out.append(Ts - T1)
    return np.array(out)
for lab, m1 in (('75 levels (7 hPa)', 700 / G), ('32 levels (20 hPa)', 2000 / G)):
    for V1 in (10.0, 50.0, 100.0):
        ch = 0.01
        r = dt * ch * V1 / m1
        e, i = run(m1, V1, ch, 2e5, False), run(m1, V1, ch, 2e5, True)
        print(f'{lab:18s} V1 {V1:5.0f} m/s: dt*chv/m1 = {r:5.2f}, dt*chv*cp/C = {dt*ch*V1*cp/2e5:5.2f} (explicit stable if < 2) | Ts-T1 after 12 steps: explicit {e[-1]:12.3g} K, implicit {i[-1]:7.3f} K')
