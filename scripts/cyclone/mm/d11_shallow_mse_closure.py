"""D11 offline: ECMWF shallow-convection closure (IFS Cy50r1 Part IV sec. 6.4.2, eqs. 6.35-6.37, Bechtold et al. 2014)
evaluated on MEGAM's own sub-cloud-layer budget, before any code or GPU test.

  M_base (h_up - h_bar)_base = -(1/g) int_{psurf}^{pbase} (dh/dt)_bl dp            (6.35/6.37, beta = 0: shallow, no downdraught)

(dh/dt)_bl = the NON-convective MSE tendency of the sub-cloud layer = advection + radiation + boundary-layer diffusion
(surface fluxes). The denominator is limited to >= 0.75 cp when the CFL limit is hit.

Inputs (no tuning; every number is read or stated):
 - the model's own budget windows (tn-evo-ctl, tn-evo-f2: 6 January 2020 starts, tropics |lat| < 20, K/day and g/kg/day per
   sigma layer; dyn = total - physics), surface LH/SH at day 5;
 - ERA5 (the same 6 start times, libm_wx2020_fields.npz) for the absolute h profile, used for (h_up - h_bar)_base.
Stated assumptions (sensitivity shown): sub-cloud layer = sigma >= 0.94 (cloud base ~950 hPa, ~550 m, tropical
 oceans); boundary-layer moisture flux leaving through cloud base by diffusion = 0 or 30 % of E; updraught leaves the
 lowest level with the IFS surface-flux perturbation (~0.2 K, ~0.2 g/kg) and no sub-cloud entrainment.
python d11_shallow_mse_closure.py EVO_DIR LIB_NPZ"""
import json, sys, numpy as np
G, CP, LV = 9.80616, 1004.6, 2.501e6
EVO, LIB = sys.argv[1], sys.argv[2]
SIGB = 0.94
# ---------- ERA5 absolute profiles: tropics mean h at 1000 / 925 / 850 hPa for the 6 starts ----------
Z = np.load(LIB); TT = [str(t) for t in Z['times']]; V3 = [str(v) for v in Z['v3']]; lev = Z['levs'].astype(float)
lat = Z['lats']; w = np.cos(np.radians(lat)) * (np.abs(lat) < 20)
starts = ['2020-01-01T00', '2020-01-06T00', '2020-01-11T00', '2020-01-16T00', '2020-01-21T00', '2020-01-26T00']
H = []
for s in starts:
    k = TT.index(s); f = Z['f3'][k]
    T, q, zg = f[V3.index('temperature')], f[V3.index('specific_humidity')], f[V3.index('geopotential')]
    h = CP * T + LV * q + zg                                                             # J/kg, [lev, lat, lon]
    hm = (h.mean(2) * w).sum(1) / w.sum(); Tm = (T.mean(2) * w).sum(1) / w.sum(); qm = (q.mean(2) * w).sum(1) / w.sum()
    H.append((hm, Tm, qm))
hm, Tm, qm = [np.mean([x[i] for x in H], 0) for i in range(3)]
i1000, i925, i850 = [list(lev).index(v) for v in (1000, 925, 850)]
print('ERA5 tropics (6 starts): h 1000/925/850 = %.1f / %.1f / %.1f kJ/kg; T %.1f/%.1f/%.1f K; q %.1f/%.1f/%.1f g/kg' % (
    hm[i1000] / 1e3, hm[i925] / 1e3, hm[i850] / 1e3, *Tm[[i1000, i925, i850]], *(qm[[i1000, i925, i850]] * 1e3)))
pbase = 950.0
hbar_b = np.interp(pbase, lev[[i925, i1000]], hm[[i925, i1000]])
pert = CP * 0.2 + LV * 2e-4                                                              # IFS surface-flux perturbation of the test parcel
dh = {}
for nm, hup in (('h(1000)+pert', hm[i1000] + pert), ('h(1000)', hm[i1000]), ('mixed 1000-950', 0.5 * (hm[i1000] + hbar_b))):
    dh[nm] = max(hup - hbar_b, 0.75 * CP)
    print(f'  (h_up - h_bar)_base at {pbase:.0f} hPa, updraught = {nm:15s}: {dh[nm] / 1e3:.2f} kJ/kg')
# ---------- the model's own sub-cloud non-convective MSE source ----------
out = {}
for run in ('ctl', 'f2'):
    J = json.load(open(f'{EVO}/tn-evo-{run}/prof.json'))[run]
    sig = np.array(J[0]['sig']); edges = np.concatenate([[0.0], 0.5 * (sig[1:] + sig[:-1]), [1.0]]); ds = np.diff(edges)
    ps = 101000.0; m = ds * ps / G                                                       # kg/m2 per layer
    sub = edges[:-1] >= SIGB - 1e-3                                                      # layers whose top is below sigma 0.94
    LH = np.mean([j['lh_trop'] for j in J]); SH = np.mean([j['sh_trop'] for j in J])
    print(f'\n### {run}: sub-cloud layers sigma {sig[sub].round(3).tolist()} ({m[sub].sum() * G / 100:.0f} hPa); day-5 LH {LH:.0f}, SH {SH:.1f} W/m2')
    for win in ('0-24h', '48-72h', '96-120h'):
        B = lambda p: np.mean([np.array(j['budget'][win]['tropics'][p], float) for j in J], 0)
        Wm = lambda Kday: float((Kday * m)[sub].sum() * CP / 86400)                     # K/day -> W/m2
        Wq = lambda gkgday: float((gkgday * m)[sub].sum() * LV / 86400 / 1000)          # g/kg/day -> W/m2
        adv = Wm(B('dyn')) + Wq(B('dynq')); rad = Wm(B('rad')); blT = Wm(B('h_bl'))
        conv_T = Wm(B('h_shal') + B('h_deep')); evap = Wm(B('h_evap')); lsc = Wm(B('h_lsc'))
        for ftop in (0.0, 0.3):
            S = adv + rad + blT + LH * (1 - ftop)                                         # non-convective MSE source, W/m2
            Mb = {k: S / v for k, v in dh.items()}
            out[f'{run} {win} ftop{ftop}'] = dict(adv=adv, rad=rad, blT=blT, LE=LH * (1 - ftop), S=S, Mb=Mb)
            print(f'  {win:7s} ftop {ftop:.1f}: advection {adv:7.1f}  radiation {rad:6.1f}  BL sensible {blT:5.1f}  L*E {LH * (1 - ftop):6.1f}'
                  f'  => source {S:6.1f} W/m2 | Mb ' + ' / '.join(f'{v:.4f}' for v in Mb.values()) + ' kg m-2 s-1')
        print(f'          (for reference: convective T-heating {conv_T:.1f}, rain evaporation {evap:.1f}, grid condensation {lsc:.1f} W/m2 in the layer)')
    # the closure MEGAM already has (sh_clos 0.6): surface flux only
    for nm, v in dh.items():
        print(f'  existing sh_clos 0.6 (surface flux only): Mb = {0.6 * (SH + LH) / v:.4f} ({nm})')
json.dump(out, open('d11_result.json', 'w'), indent=1, default=float)
print('\nfixed sh_mflux (F2) = 0.03 kg m-2 s-1; observed trade-cumulus cloud-base mass flux ~0.02-0.03 (BOMEX/RICO LES)')
