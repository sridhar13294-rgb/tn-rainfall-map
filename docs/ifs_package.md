# MEGAM physics package rebuild: IFS Cy50r1 convection + boundary layer as ONE consistent set

Decision: Sridhar, 11 Nov 2026 15:20 IST ("Rebuild package"), after the denial test showed the moistening/cooling drift is a balance
error of the convection + boundary layer + radiation package as a whole (docs/rootcause.md, 11 Nov 15:10).

Source: IFS Documentation Cy50r1 Part IV, chapter 6 (convection) and chapter 3 (turbulent transport, EDMF). Equation numbers below are
from that document. Everything is in physical units (m, Pa, s, kg m-2 s-1); nothing depends on the number of levels or on the time step
except where the IFS itself uses dt (the CFL limit 6.70 and the initial unit mass flux, which cancels in the closure).

Switch: `phys_ifs = 1` (default 0 -> every existing result bit-identical). It REPLACES, when on: `conv_mf` (deep), the shallow scheme
(`shallow='mse'` / 'mf'), the counter-gradient term and the Ri-only BL height. Kept unchanged: surface layer (fluxes), radiation,
large-scale condensation, land, gravity-wave drag, dynamics. Module: `scripts/cyclone/mm/ifs_phys.py` (pure jax functions, column-
vectorised [L, X, Y], index 0 = model top).

## 1. Convection (chapter 6)

| Part | IFS | v1 implementation |
|---|---|---|
| Type detection | 6.4: shallow test parcel from the lowest level, eps = 0.8/z + 3e-4 (6.18), excess dT/dq from surface fluxes with w* (6.19-6.20), kinetic energy 6.10; shallow if LCL found, w > 0 at LCL, cloud depth < 200 hPa | same |
| | deep test: departure levels from the 2nd-lowest level up to 350 hPa; eps = 0.4 x 1.75e-3 (qsat/qsat_sfc)^3; 50 % of condensate removed per level; dT 0.2 K, dq 1e-4 (6.21); source = 50-hPa layer mean inside the lowest 60 hPa; deep if depth > 200 hPa; deep overrides shallow | same, without the moisture-advection term of 6.21 (needs the advective tendency; listed as v2) |
| | mid-level (6.4.3, 6.38) | v2 (not in v1) |
| Updraught | 6.3: bulk plume; E = eps_up f_eps (1.3 - RH) f_scale (6.7), eps_up 1.75e-3, f_eps 1 deep / 2 shallow, f_scale = (qsat/qsat_base)^3; D(1) = 0.75e-4 (1.6 - RH) deep (6.8), = E (1.6 - RH) shallow (6.9); organised detrainment from the decrease of K (6.12); top where w = 0 | same; buoyancy with condensate loading (6.65); centred K equation (6.66) |
| Microphysics | condensation by saturation adjustment (6.42); freezing fraction alpha_T 235-273 K, deep only (6.43); autoconversion Sundqvist c00 1.4e-3, lcrit 0.5 g/kg, thresholds 0.3 (sea)/0.5 (land) g/kg (6.44) with Bergeron 6.45-6.46; fallout V = 21.18 r^0.2 (6.47-6.48) | same, analytic per-layer solution |
| Downdraught | LFS = highest level below the min-MSE level where a 50/50 cloud/environment mix at wet-bulb is negatively buoyant; M_LFS = -0.3 M_base (6.13); eps = delta = 2e-4 (6.15); saturated descent by rain evaporation (6.17); detrain over the lowest 60 hPa or where it turns buoyant | same, without Nordeng organised entrainment (6.16) in v1 |
| Rain evaporation below cloud base | Kessler (6.49-6.52), Cconv 0.05 deep, 0.05-0.45 shallow by mean cloud-layer RH; RHcr 0.85/0.70 deep, 0.90/0.75 shallow (sea/land) | same; Cy50r1's deactivation for deep (6.7 handover to the prognostic cloud scheme) does NOT apply: MEGAM has no prognostic cloud, so we use the pre-Cy50r1 behaviour |
| Melting | relaxation to T0 with tau_melt (6.53-6.55) | same |
| Deep closure | PCAPE removed over tau = (H / w_up) alpha_x, 720-10800 s (6.22-6.26), alpha_x = 1 + 1.6 dx/125 km (6.27); PCAPE_bl from the non-convective BL tendency (6.33-6.34) | same, without QCV (6.29-6.32, Cy47r3) in v1 |
| Shallow closure | sub-cloud MSE budget: M_base = -(1/g) int (dh/dt)_bl dp / (h_up - h)_base (6.35-6.37); denominator >= 0.75 cp only if CFL exceeded | same, (dh/dt)_bl = BL diffusion + radiation tendencies computed before convection (no advection in v1) |
| Sub-cloud layer | fluxes linear in p from cloud base to 0 at the ground (6.39-6.41, m = 1) | same |
| Detrained condensate | Cy50r1: source for the prognostic cloud scheme (6.56) | evaporated where detrained (pre-prognostic IFS, 6.7 first sentence) |
| Momentum | 6.57-6.58, lambda = 0, u_pert 0.3 m/s; KE dissipation as heat (6.59-6.60) | existing mass-flux CMT driven by the new M; dissipation heating added |
| Discretisation | flux form 6.61-6.62; implicit transport 6.69, CFL 3 for T/q, abs. 2 kg m-2 s-1 (6.70); environment stable s(k-1/2) >= s(k+1/2) (6.67) | implicit with shifted (upwind) environment values; moist-adiabatic half-level extrapolation 6.63 in v2 |

## 2. Boundary layer (chapter 3)

| Part | IFS | v1 |
|---|---|---|
| BL height | zi = top of the surface test parcel (same plume as 6.18, entrainment x3 in cloud) where w_u > 0 and Ri < 50 | same |
| Sc / Cu | EIS = max(he700 - he950, he950 - he_sfc) > 5 K with he = hl + cp T* 5.87 qt (3.40-3.41) -> Sc: zi = cloud top | same; Lock cloud-top K (3.48-3.49) needs the cloud-top radiative flux jump -> v1 uses it from the radiation cache |
| Mass flux | M = 0.1 rho sigma_w (z/zn)(1 - z/zi,cb)^2, sigma_w (3.42-3.43); scalars only | as built 10 Nov (`edmf`), plume shared with the convection test parcel |
| K-profile | K_H = kappa u* Phi_H0^-1 z (1 - z/zi)^2 (3.45), Cu-capped form over sea (3.46), Phi from L (3.47); top entrainment -0.2 surface buoyancy flux (3.50) | same |
| Above the mixed layer | local Ri closures (3.56-3.59) | existing free-atmosphere diffusion kept (v2) |

## 3. Order in one physics call
radiation (cached) -> surface layer -> BL (EDMF: K-profile + mass flux, implicit) -> convection (sees BL + radiation tendencies for its
closures) -> large-scale condensation -> rain evaporation. Energy and water conserved per column (checked).

## 4. Checks before any GPU use (local, T42 grid, 20-min step)
1. phys_ifs = 0: regression bit-identical (22.259984322409387).
2. Column conservation: |column water change - (E - P)| and |energy change - (fluxes)| < 1e-3 relative.
3. Single-column sanity (BOMEX-like trade cumulus, tropical deep column): cloud-base mass flux 0.02-0.04 (shallow), deep rain rates
   and heating profile with peak 400-600 hPa.
4. 48-h drift (cloud_drift.py): low-level T and RH, cloud cover, against the ERA5 start.

## 5. Registered predictions for the T170 first-hours test (to be frozen before launch)
Written into docs/rootcause.md before the run.
