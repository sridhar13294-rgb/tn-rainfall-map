"""D10 offline: would a physical shallow-cumulus closure (Grant 2001: cloud-base mass flux Mb = 0.03 rho w*) supply the
missing low-level heat of the combined fix? Inputs = the model's own tropical-mean surface fluxes (tn-prof-d1, d5).
Also sizes the day-1 heat deficit of the 800-1000 hPa layer and the candidate terms. python shallow_closure_derivation.py"""
import numpy as np
G, CP, LV, RHO, TH = 9.80616, 1004.6, 2.5e6, 1.15, 300.0
SH, LH = 8.7, 133.5                                    # W m-2, tropics, tn-prof-d1
E = LH / LV
B = G / TH * (SH / (RHO * CP) + 0.61 * TH * E / RHO)   # surface buoyancy flux, m2 s-3
print(f'surface buoyancy flux {B:.2e} m2/s3')
for h in (400.0, 600.0, 800.0):
    ws = (B * h) ** (1 / 3); Mb = 0.03 * RHO * ws
    print(f'  sub-cloud depth {h:.0f} m: w* {ws:.2f} m/s -> Grant Mb {Mb:.4f} kg m-2 s-1 (fixed sh_mflux 0.03; ratio {Mb/0.03:.2f})')
# day-1 deficit of the 800-1000 hPa layer (mass-mean tendency -0.91 K/day in d1 while ERA5 is ~steady)
m = 20000.0 / G
need = 0.91 * CP * m / 86400
print(f'800-1000 hPa layer: day-1 cooling 0.91 K/day = {need:.1f} W/m2 missing')
ev = 1.16 * CP * m / 86400 / LV * 86400
print(f'  rain re-evaporation in the layer: 1.16 K/day = {ev:.2f} mm/day of the 6.2 mm/day rain ({ev/6.2*100:.0f}%)')
print(f'  surface sensible flux 8.7 W/m2 = {8.7/(CP*m)*86400:.2f} K/day; raising it to an observed ~12 W/m2 adds {3.3/(CP*m)*86400:.2f} K/day')
print('  clear-sky LW: radcloud self-test already 0.2-0.7 K/day too strong over 800-300 hPa vs RRTMG (SSM line strength x1.5 calibration) -> up to', round(0.7 * CP * m / 86400, 1), 'W/m2 in this layer')
