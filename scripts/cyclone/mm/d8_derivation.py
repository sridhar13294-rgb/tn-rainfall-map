"""D8 offline: sea-surface heat/moisture exchange coefficient at the model's lowest level (z1 ~ 80 m).
Current mm2: Cd at z1 from the log law with Charnock z0m (consistent); Ck = 1.2e-3 (a 10-m value) x [ln(10/z0m)/ln(z1/z0m)]^(2 ck_z),
ck_z = 0.5 -> HALF of the height correction, and it uses z0m for heat/moisture.
Derived (COARE 3.0, Fairall et al. 2003; neutral): CHn(z1) = kappa^2 / [ln(z1/z0m) ln(z1/z0t)], z0t = z0q = min(1.1e-4, 5.5e-5 Rr^-0.6),
Rr = u* z0m / nu (roughness Reynolds number), z0m = alpha u*^2/g + 0.11 nu/u* (alpha = 0.011-0.018; mm2 uses 0.018 + 1.5e-5).
python d8_derivation.py"""
import numpy as np
K, G, NU = 0.4, 9.80616, 1.5e-5
def mm2(V1, z1, ckz=0.5, charnock=0.018, ck=1.2e-3):
    ust = 0.04 * V1
    for _ in range(3):
        z0 = charnock * ust ** 2 / G + 1.5e-5; cdn = (K / np.log(z1 / z0)) ** 2; ust = np.sqrt(cdn) * V1
    zfac = (np.log(10.0 / z0) / np.log(z1 / z0)) ** 2
    return cdn, ck * zfac ** ckz, z0
def coare(V1, z1, charnock=0.011):
    ust = 0.04 * V1
    for _ in range(20):
        z0 = charnock * ust ** 2 / G + 0.11 * NU / ust; ust = K * V1 / np.log(z1 / z0)
    Rr = ust * z0 / NU; z0t = min(1.1e-4, 5.5e-5 * Rr ** -0.6)
    return (K / np.log(z1 / z0)) ** 2, K ** 2 / (np.log(z1 / z0) * np.log(z1 / z0t)), z0, z0t
z1 = 80.0
print(f'lowest level z1 = {z1:.0f} m; neutral coefficients')
print(f'{"V1 m/s":>7s} | {"mm2 Cd":>8s} {"mm2 Ck":>8s} {"Ck/Cd":>5s} | {"COARE Cd":>8s} {"COARE Ck":>8s} {"Ck/Cd":>5s} | Ck ratio mm2/COARE | Ck at ck_z=1 / COARE')
for V in (3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0):
    cd, ck, _ = mm2(V, z1); cd1, ck1, _ = mm2(V, z1, ckz=1.0); cdc, ckc, z0, z0t = coare(V, z1)
    print(f'{V:7.0f} | {cd:8.2e} {ck:8.2e} {ck/cd:5.2f} | {cdc:8.2e} {ckc:8.2e} {ckc/cdc:5.2f} | {ck/ckc:5.2f} | {ck1/ckc:5.2f}   (z0m {z0:.1e} z0t {z0t:.1e})')
# what it means for the fluxes in the F2 coastal-sea state (air 298.0 K, SST ~302 K, q1 17.0 g/kg; V1 ~ 7 m/s)
rho, cp, Lv = 1.15, 1004.6, 2.5e6
def qs(T, p=101000.0): es = 611.2 * np.exp(17.67 * (T - 273.15) / (T - 29.65)); return 0.622 * es / (p - 0.378 * es)
for V in (5.0, 7.0, 10.0):
    _, ck, _ = mm2(V, z1); _, ckc, _, _ = coare(V, z1)
    for lab, c in (('mm2', ck), ('COARE', ckc)):
        H = rho * cp * c * V * (302.0 - 298.0 * (101000 / 100000) ** 0.0); E = rho * Lv * c * V * (qs(302.0) - 0.017)
        print(f'V1 {V:4.0f} m/s {lab:5s}: SH {H:6.1f} W/m2  LH {E:6.1f} W/m2  total {H+E:6.1f}')
