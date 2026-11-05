# Stage 1 status table (kept current every cycle; Sridhar 4 Nov 23:17: "Keep on updating this table")
Last update: 5 Nov 19:55 IST. Target: 15 Nov (Sridhar 5 Nov 18:57). Stage 3 paused until Stage 1 is done.

| Item | Stage | Where it stands |
|---|---|---|
| P3, cyclone intensity | Nearly done | cmt_mf fix works (Nivar on target). Michaung/Vardah residuals are track consequences. |
| P2, 75-level stability | Fixed; 32 L check running | Andes 125 -> 19.5 m/s, BL heating 390 -> 161 K/day; 10 days without blow-up. drag_imp 32 L suite running (tn-s-drg-*). |
| P4, Tamil Nadu rain | Causes 2-3 under test | Base 1.70 vs control 1.51 (24 starts, noise +-0.13); Oct-Dec 1.20 (inside +-25 %); dry season ~2x. Evaporation fix rejected alone. Continuum fix (cnt): z500 better (72.3/118.6 vs 73.1/119.2), TN easterly smaller (-2.05 vs -2.41), stable, but tracks 329 vs 297 km (+11 %, over the 6 % round-off) -> not adopted so far; rain/genesis pending. |
| P1, warm/dry low levels | Tall-shallow cause confirmed; fix as coded over-corrects | sh_depth: 925/1000 hPa fixed (-0.79 / -0.01 K vs +2.47 / +2.74) BUT 850 hPa -2.26 K (gate +-1.5), q850 +0.67 (gate +-0.5), Nivar 3.4 hPa weaker, tracks +10 % -> NOT adopted. The tall-shallow heating was holding 850 hPa up: the heating it supplied is needed, but from the right process. |
| Tracks (new check, Sridhar 19:05) | Main open item | Pass = track TREND matches (12-h headings within 30 deg, every real turn reproduced within +-12 h, no false turns; 5 of 6 storms) AND 72-h mean error <= 200 km (now 297). Recurving storms (Hamoon, Sidr, Nivar) go W/SW -> fails the trend part too until P5 is fixed. |
| P5, large-scale steering | Diagnosing | Michaung: ERA5 trough moves 63 -> 76.5 E, model trough parked at 71-72 E. IFS Part III review: 3 core differences over the Himalaya (T smoothing on sloping levels, no orographic T reference in transport, pure sigma levels) - offline test D1 next. Bias-map and case jobs collected, analysis next cycle. |
| Core / day-1 error | NEW ROOT CAUSE found | Day-1 z500 error 20.4 m = global bias -13.8 m + ~15 m random. Part of the bias exists at hour 0 (-5.5 m everywhere): Dinosaur's gas constant 286.86 vs 287.04 (thicknesses 0.07 % short). Fix rd_si offline: hour-0 offset -5.5 -> -2.0 m (predicted +4.0, measured +3.7). Full suite queued (tn-s-rd-*). Physics-off test: 24.9 / 24.6 m on 2 starts (OOM; 4-chunk rerun queued). |
| Your F2 condition (6 items) | Item 1 rejected | Item 5 (BL formula alone) after. |
| Global health (rain, OLR, drift) | Diagnosing | Atmosphere cools ~20 W/m2; day-1 drift -7 m (tropics) / -14 m (globe) on top of the hour-0 offset. |
| GPU pipeline | Fixed 5 Nov 18:00 | Push-only launches + collector; GitHub's 20-runner cap removed; duplicate-launch bug fixed. |
