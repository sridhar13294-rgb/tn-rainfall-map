# Stage 1 status table (kept current every cycle; Sridhar 4 Nov 23:17: "Keep on updating this table")
Last update: 10 Nov 20:40 IST (see docs/rootcause.md 10 Nov and the status PDF). Standing rule 10 Nov: every candidate also screened at 75 L. Earlier: 5 Nov 22:15 IST. Target 15 Nov no longer reachable (GPU: own account + partner account only); realistic ~2 weeks. Stage 3 paused until Stage 1 is done.

## Decisions 13 Nov 20:57 IST: critical path only; adopt on all registered checks passing; track rule = 3-member means. Target: first week of Dec (Claude's estimate ~25-40 %; 70 % 10 Jan; 90 % end Feb).

## One-word status (Sridhar 12 Nov 09:53: include in EVERY report; every row has a reason/suspect - no bare Open/Rejected)
Updated 13 Nov 11:40 IST. New storm rules registered 13 Nov 11:40 (docs/rootcause.md).
| Problem | Status | Reason / suspects |
|---|---|---|
| A Cloud | Cause found; fixing | Day-1 energy loss: slow first-day rain, no aerosols, cloud-radiation feedback |
| B Low-level moisture | Fixed | bl_lcl, 32 and 75 L |
| P1 Low-level T/q | Cause found; fixing | Same as A + bl_lcl and low-level radiation |
| P2 TN rain / 75 L | Measuring | Moisture excess fixed by B; convection at 75 L |
| P3 Storm intensity | Re-judge (new rule) | Needs 41-storm peak-intensity run; suspects: slow storm-core rain at start, cold/dry low levels |
| P4 Dry-season rain | Measuring | False rain from moist low levels (fixed by B) |
| P5a Jets | Narrowing | D1 + unexplained ~-6 m/s day 1 Asia at T170 |
| P5b Bay steering | Suspects identified | Cold land low levels raise C-India high; SE-Tibet terrain pressure error |
| Tracks | Measuring | Steering winds (P5b) |
| D1 Linear vertical SL | Re-test (new rule) | Cubic fixes jets/S1; re-run storms under rule 2 |
| D2 SL-Eulerian gap | Closed | Gone at T85 with cubic |
| D3 Sigma over Tibet | Not adopted | T170 Asia gain +0.1 only; option kept |
| D4 250 K T_ref | Closed | No jet effect |
| S1 First-6-h jet loss | Explained | = D1 |
| S2 DFI removes tide | Re-test (new rule) | dfi_off failed old rule by 0.1 hPa |
| S3 Hour-0 C-India MSLP | Closed | T170 start right; rest = S2 |
| S4 Lowest-level start cooling | Not a bug | Physical, both cores |
| 75 L stability | Fixed | 19/19 |

| Item | Stage | Where it stands |
|---|---|---|
| P3, cyclone intensity | Nearly done | cmt_mf fix works (Nivar on target). Michaung/Vardah residuals are track consequences. |
| P2, 75-level stability | Fixed; 32 L check running | Andes 125 -> 19.5 m/s, BL heating 390 -> 161 K/day; 10 days without blow-up. drag_imp 32 L suite running (tn-s-drg-*). |
| P4, Tamil Nadu rain | Causes 2-3 under test | Base 1.70 vs control 1.51 (24 starts, noise +-0.13); Oct-Dec 1.20 (inside +-25 %); dry season ~2x. Evaporation fix rejected alone. Continuum fix (cnt): z500 better (72.3/118.6 vs 73.1/119.2), TN easterly smaller (-2.05 vs -2.41), stable, but tracks 329 vs 297 km (+11 %, over the 6 % round-off) -> not adopted so far; rain/genesis pending. |
| P1, warm/dry low levels | Tall-shallow cause confirmed; fix as coded over-corrects | sh_depth: 925/1000 hPa fixed (-0.79 / -0.01 K vs +2.47 / +2.74) BUT 850 hPa -2.26 K (gate +-1.5), q850 +0.67 (gate +-0.5), Nivar 3.4 hPa weaker, tracks +10 % -> NOT adopted. The tall-shallow heating was holding 850 hPa up: the heating it supplied is needed, but from the right process. |
| Tracks (new check, Sridhar 19:05) | Main open item | Pass = track TREND matches (12-h headings within 30 deg, every real turn reproduced within +-12 h, no false turns; 5 of 6 storms) AND 72-h mean error <= 280 km (now 297; Sridhar 9 Nov 23:48 IST: 280-290 km, Claude set 280 = beyond the ~6 % round-off noise; registered before any new track result; 200 km kept as the Stage 1+ aim, 150 km Stage 3). Recurving storms (Hamoon, Sidr, Nivar) go W/SW -> fails the trend part too until P5 is fixed. |
| P5, large-scale steering | Diagnosing | Michaung: ERA5 trough moves 63 -> 76.5 E, model trough parked at 71-72 E. IFS Part III review: 3 core differences over the Himalaya (T smoothing on sloping levels, no orographic T reference in transport, pure sigma levels) - offline test D1 next. Bias-map and case jobs collected, analysis next cycle. |
| Core / day-1 error | Gas-constant fix ADOPTED (base2) | Day-1 z500 error 20.4 m = global bias -13.8 m + ~15 m random. Part of the bias exists at hour 0 (-5.5 m everywhere): Dinosaur's gas constant 286.86 vs 287.04 (thicknesses 0.07 % short). Fix rd_si offline: hour-0 offset -5.5 -> -2.0 m (predicted +4.0, measured +3.7). Full suite: day-1 z500 20.0 -> 17.8 m, d5 73.1 -> 71.6, d10 119.2 -> 117.8; tracks/intensity unchanged within round-off -> ADOPTED. Physics-off (73 starts): 22.4 m, bias -10 m -> rule says core/initialisation first; lead: the core alone lowers z500 ~4.5 m/day with no physics (T smoothing on sloping levels suspected, IFS Part III D1). |
| Your F2 condition (6 items) | Item 1 rejected | Item 5 (BL formula alone) after. |
| Global health (rain, OLR, drift) | Diagnosing | Atmosphere cools ~20 W/m2; day-1 drift -7 m (tropics) / -14 m (globe) on top of the hour-0 offset. |
| GPU pipeline | Fixed 5 Nov 18:00 | Push-only launches + collector; GitHub's 20-runner cap removed; duplicate-launch bug fixed. |
