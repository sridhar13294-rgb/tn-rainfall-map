"""P5 geostrophic check (10 Nov): is the Bay u850 bias the geostrophic wind of the model's MSLP bias?
python p5_geo_eval.py p5_geo.npz -> per day: Bay (10-20N, 82-95E) mean u850 bias vs u_g' = -(1/(rho f)) dp'/dy from the MSLP bias
(and v_g' = (1/(rho f)) dp'/dx vs v850 bias), plus pattern correlation over 8-25N 70-100E. rho = 1.15 kg/m3 (low levels)."""
import sys, numpy as np
Z = np.load(sys.argv[1]); la, lo = Z['lat'], Z['lon']; R, RHO, OM = 6.371e6, 1.15, 7.292e-5
LA = la[:, None] * np.ones_like(lo)[None, :]; f = 2 * OM * np.sin(np.radians(LA))
dy = R * np.radians(np.gradient(la))[:, None]; dx = R * np.cos(np.radians(LA)) * np.radians(np.gradient(lo))[None, :]
bay = np.ix_((la >= 10) & (la <= 20), (lo >= 82) & (lo <= 95)); big = np.ix_((la >= 8) & (la <= 25), (lo >= 70) & (lo <= 100))
for d in (1, 2, 3):
    p = Z[f'mslp_d{d}'] * 100.0
    ug = -np.gradient(p, axis=0) / dy / (RHO * f); vg = np.gradient(p, axis=1) / dx / (RHO * f)
    u, v = Z[f'u850_d{d}'], Z[f'v850_d{d}']
    cu = np.corrcoef(u[big].ravel(), ug[big].ravel())[0, 1]; cv = np.corrcoef(v[big].ravel(), vg[big].ravel())[0, 1]
    print(f'day {d}: Bay u850 bias {np.nanmean(u[bay]):+.2f}  geostrophic u from MSLP bias {np.nanmean(ug[bay]):+.2f}  '
          f'(share {np.nanmean(ug[bay]) / np.nanmean(u[bay]):.0%}, pattern r {cu:+.2f}) | v850 {np.nanmean(v[bay]):+.2f} vs v_g {np.nanmean(vg[bay]):+.2f} (r {cv:+.2f})')
