# Cloud-water stage for MEGAM - design (5 Nov 2026, Stage 1 item (f))

## Why (evidence, not taste)
- All condensate rains out in the same 20-min step (mm2 large-scale saturation adjustment + convective rain): nothing is
  stored, nothing re-evaporates as cloud, rain forms as fast as condensation happens.
- Radiation therefore uses DIAGNOSTIC cloud water (radcloud.clouds): grid-mean condensate b_ls x qsat x Sundqvist
  fraction (+ condensation x 1 h, + convective rain production x 30 min, + anvil). With RHc = 0.8 near the surface,
  every moist boundary layer is "cloudy". Measured 5 Nov (T170, rad_check): cover 0.83-0.84 (obs ~0.67), grid-mean
  liquid water path 237-249 g/m2 (obs ocean ~80, MAC-LWP), LW cloud effect 39-40 W/m2 (CERES ~26), OLR 212-217 (~240),
  atmospheric radiative cooling -112..-120 W/m2 (~-105) -> part of the global rain excess (0.25-0.5 mm/day).
- Clouds and rain are decoupled: the cloud the radiation sees is not the water the model actually holds.

## Choice: one prognostic cloud-condensate variable, Zhao & Carr (1997) / Sundqvist (1978, 1989)
The scheme of the operational NCEP GFS 1997-2019 (and Eta/NAM): proven at global NWP resolution, one extra tracer,
cheap. Alternatives considered: Tiedtke (1993) prognostic cloud fraction + condensate (two tracers, more parameters);
full multi-species microphysics (GFDL, Thompson) - too expensive and too many parameters for Stage 1.

Variable: qc (kg/kg) = cloud liquid + ice; phase by temperature (liquid above -15 C, ice below -40 C, linear between;
same ramp idea as radcloud).

## Equations (per layer, each physics step, after convection and before radiation)
1. Condensation (large scale). The current saturation adjustment stays, but its product goes INTO qc instead of rain:
   C = max(q - qs, 0) / (1 + L^2 qs / (cp Rv T^2)) / dt  ->  dq = -C, dqc = +C, dT = +L C / cp.
2. Cloud evaporation in sub-saturated air (Sundqvist 1989; Zhao-Carr eq. 9 form):
   E_c = min(qc, (qs - q)) / tau_e  where RH < 1,  tau_e = 900 s  ->  dqc = -E_c, dq = +E_c, dT = -L E_c / cp.
   (limited so that it never over-saturates and never removes more than qc.)
3. Autoconversion to rain (Sundqvist 1989):
   P_auto = c0 qc [1 - exp(-(qc / (b q_crit))^2)],  b = cloud fraction (>= 0.05),
   c0 = 1e-4 s-1, q_crit = 3e-4 kg/kg (liquid, sea), 5e-4 (land, more CCN); ice: c0_i = 1e-3 s-1 exp(0.025 (T - 273.15)),
   q_crit_i = 5e-5 kg/kg (Zhao-Carr aggregation form).
   Collection by rain falling from above (Sundqvist): c0 -> c0 (1 + 300 sqrt(P_above [kg m-2 s-1]))  (Bergeron
   enhancement x(1 + 0.5 phase-mix) between -15 and -40 C).
   P_auto per layer is the rain SOURCE that replaces 'cond' in the existing falling-rain scan (rain evaporation below
   cloud unchanged: k_evap form or evap_ifs).
4. Convective detrainment: the deep scheme keeps its own rain; a fraction eps_det (radcloud's 0.1) of the convective
   condensate production at the cloud-top (detrainment) layers is put into qc instead of rain -> anvils become
   prognostic (no 'anvil lifetime' guess).
5. Cloud fraction for radiation: Xu & Randall (1996), as used with Zhao-Carr in GFS:
   b = RH^0.25 [1 - exp(-100 qc / ((1 - RH) qs)^0.49)]  (b = 1 at RH >= 1; 0 when qc = 0),
   in-cloud water = qc / b. Convective tower cover (Slingo) stays for active deep convection columns.
6. Advection: qc is a second NODAL tracer in the semi-Lagrangian dynamics with monotone_tracers (same as q):
   positive, no spectral ringing. Horizontal diffusion excluded like q.
7. Start: qc = 0 (libraries have no cloud water); spin-up time ~ condensate lifetime (~1 h) -> inside DFI + first hours.

## Conservation (audit extended before any test)
Total water q + qc: column change = E - P (P = surface rain). Moist enthalpy cp T + L q (+ L_f ice later) conserved by
1-2-4; budget_audit gets 'q_cld' terms; the regression check gets a qc field when the option is on.

## Code plan (option cloud_qc, default off; control bit-identical)
- mm2.Model: tracers dict gets 'cloud_condensate' when cloud_qc (static option: changes the state structure);
  SemiLagrangianPrimitiveEquations nodal_tracers + step_filter exclusion include it; physics tendency injection adds
  tend['qc'].
- mm2.column: steps 1-4 replace the rain source 'src = cond * mass' by P_auto * mass and add dqc; diag q_cld, P_auto,
  E_c for budgets.
- radcloud.clouds: when qc is passed, use Xu-Randall b and qc/b (skip the diagnostic b_ls/tau_ls/anvil water).
- Output: LWP/IWP (grid-mean) in run_wx and rad diagnostics.

## Registered checks (to be fixed before the first run)
Offline (column prototype on model states): steady-state qc and LWP from the model's own condensation rates.
Model (T170 suite vs base): global ocean grid-mean LWP 50-110 g/m2; cloud cover 0.60-0.72; OLR >= 225 W/m2;
LW CRE 20-32 W/m2; atmospheric radiative cooling within -100..-110; global rain falls by >= 0.2 mm/day; plus the 8
Stage-1 checks (no worse than base) and the 24-start TN rain (noise +-0.13).

## Risks
- Rain delayed by ~cloud lifetime: storm intensity / genesis can change (less instant latent heating in the core).
- More clouds where the old scheme had rain (anvils): SW cooling changes -> z500 drift.
- Interaction with the evaporation fix and the continuum fix (energy budget): final judgement on the combination.

## Offline check 1 (5 Nov 12:50, T42, control state at +24 h, 19 Jul / 6 Dec) - ORDER CHANGED
Steady state of the Sundqvist autoconversion driven by the model's OWN large-scale condensation: ocean grid-mean LWP
~400 g/m2 without collection, 256 g/m2 with collection by rain from above (obs ~80) - i.e. a prognostic cloud would hold
3-5x too much water. Where: condensation over ocean 3.6 mm/day of which 2.72 mm/day at sigma 0.5-0.85 (mid-troposphere),
0.39 below 850 hPa, 0.46 above 500 hPa; grid-scale cloud in 65 % of columns. Real tropical-ocean rain is mostly
convective. => The model saturates the mid-troposphere over whole grid boxes because deep convection rarely fires (5 %
of tropical columns) - the same root as P1 and the false land rain (over-active shallow scheme takes the instability).
A cloud-water stage on the current convection would store this excess and make radiation WORSE.
Decision (design): implement cloud_qc now (default off), but TEST it on top of the shallow fix (sh_mflux 0.03) once that
passes; registered precondition: mid-level (0.5-0.85) grid-scale condensation over ocean falls by >= 50 % with the
shallow fix (rerun this check on its state), and the steady-state LWP estimate falls to <= 110 g/m2.
