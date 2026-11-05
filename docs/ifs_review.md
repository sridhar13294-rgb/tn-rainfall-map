# MEGAM vs ECMWF IFS documentation - equation-by-equation review
Reference texts (local only, not in the repo): IFS Cy49r1 Part IV Physical Processes (273 p), IFS Cy48r1 Part III
Dynamics and Numerical Procedures (40 p), GFSv16 CCB evaluation (98 slides). Each finding: same / different / missing,
page ref, the Stage-1 item it bears on, and the test it implies (derive -> offline -> code check -> register -> test).

## Part III (Dynamics), first pass 5 Nov 18:20 IST - three P5 suspects (steering / parked trough over South Asia)
| # | IFS (Cy48r1 Part III) | MEGAM (Dinosaur core as configured in mm2.build) | Verdict | Bears on |
|---|---|---|---|---|
| D1 | Horizontal diffusion of T is modified "to approximate diffusion on surfaces of constant pressure rather than on the sloping hybrid coordinate surfaces (Simmons 1987)" (Ch 2, eq 2.58-2.59 + text) | time_integration.horizontal_diffusion_step_filter applied to every modal field ON SIGMA SURFACES; no pressure-surface correction for T | DIFFERENT (missing correction) | P5 (Tibet / Himalaya heights), global drift |
| D2 | Semi-Lagrangian thermodynamic equation advects (T - Tb), Tb = orography-dependent reference (eq 3.37-3.39), "avoiding spurious warming over mountain tops in sigma or hybrid coordinates" | Dinosaur has the Ritchie-Tanguay smoothing for ln ps (terrain_smoothed_log_sp, default on) but advects T' = T - T_ref(level) only: no orography-dependent Tb | DIFFERENT (half of the IFS fix) | P5, hot/cold terrain bias |
| D3 | SL with Courant > 1 over mountains -> spurious orographic resonance; IFS cures it in continuity (eq 3.31-3.36) | same cure present (terrain_smoothed_log_sp) | SAME | - |
| D4 | Vertical coordinate: hybrid eta (Simmons & Burridge 1981), pressure levels aloft | pure sigma to the model top | DIFFERENT | P5 (pressure-gradient error over steep terrain), stratosphere over Tibet |

Proposed order (cheapest first; no code change before the offline numbers):
1. D1 offline: one T170 state (2020-10-27 + 24 h), compute the T tendency of the step filter on sigma surfaces vs the
   same operator applied to T interpolated to pressure surfaces; map the difference over 25-40 N 70-105 E (K/day) and the
   implied z500 change. Material if > 0.5 K/day over Tibet (registered threshold, set before the numbers).
2. D2/D4 evidence from existing runs: Tibet / Himalaya T bias by level at day 1 vs ERA5 (exam bias maps) - a warm or cold
   terrain-following signature at 400-600 hPa that is absent over the plains points to D1/D2/D4.
3. Physics-off core test (tn-core-adiab, running): if day-1 z500 error over South Asia stays large with physics off,
   the D-items move up.

### D1 result (5 Nov 22:25, offline, scripts/cyclone/mm/d1_sigma_diffusion.py, start 2020-10-27, base2 constants)
Spurious T tendency from MEGAM's step filter acting on the pure terrain imprint of T on sigma levels:
T42: Tibet (28-38 N, 78-100 E) mean +0.10 K/day by level (max |.| 0.54); T85: mean +0.07 (local max 1.1 K/day);
global mean ~0. Registered threshold: material if > 0.5 K/day over Tibet (box mean) -> NOT MET at T42/T85 (local
grid-scale extremes ~1 K/day at T85, likely ~2 at T170). => D1 is a real but small, local noise source, a WARMING over
Tibet (opposite to the falling northern heights) and globally neutral -> NOT the cause of the parked trough or of the
adiabatic -4.5 m/day z500 drop. Kept as a correctness item (Simmons 1987 correction) for later; next: D2 and the
adiabatic-drop lead (DFI / virtual-T handling without physics), then D4.
