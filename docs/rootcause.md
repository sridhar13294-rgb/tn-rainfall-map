# MEGAM root-cause log (5-Why / fault tree before any test)
Rule (Sridhar, 28 Oct): no trial-and-error screening. For each problem: 1) symptom in numbers; 2) 5-Why / fault tree using the heat-budget, the code and reference documents (ECMWF IFS Part IV, papers); 3) each hypothesis with the signature it predicts; 4) at most 1-2 discriminating tests; 5) confirm, then fix; 6) adoption gate (budget + genesis + tracks + exam incl. TN rain).

## P1 Cold tropical upper troposphere (day 5: 250 hPa -5.8 K, 100 hPa +7 K)
Why 1: model upper air loses heat faster than the real one. Start state OK (day-0 bias ~0 at 200-300 hPa) -> it is the forecast, not the analysis.
Why 2: physics or dynamics? Physics-off run still -2.5 K at 250-300 and +8 K at 100 hPa -> about half is dynamics/vertical discretisation; undiluted-plume and weaker-LW tests changed <0.5 K -> convection depth and LW strength are NOT the main physics part.
Why 3 (dynamics part): 32 levels, ~42 hPa layers at the tropopause, top layer centred 22 hPa, stratosphere relaxed to its start + 1-day wind sponge above sigma 0.05 -> tropopause smeared. Evidence: 50 levels -> 100 hPa +7.1->+4.5, 250 -5.8->-4.9.
Why 4 (open): remaining ~-5 K: (a) top treatment (relaxation to start, sponge) - signature: bias grows from the top down, physics-independent; (b) radiation scheme accuracy in clear sky at 150-300 hPa - signature: clear-sky heating rate differs from a reference (RRTM) on the same profile; (c) missing large-scale subsidence warming (circulation too weak) - signature: omega/vertical advection term in a full budget.
Discriminating tests: tp75 (raised top, packed tropopause) - running; clear-sky radiation vs reference on 1 profile (CPU, no GPU); full budget incl. dynamics terms.

## P2 Tamil Nadu rain worse with 50 levels (ACC d3 0.29 -> 0.19)
Why 1: convection changed with thinner layers. Why 2 (code review): mass-flux cap = mf_cap x thinnest cloud-layer mass / dt -> ~35% lower at 50 levels; source parcel from a single (thinner) layer. Test: mf_capdp=2400 Pa at T170 L50 (one exam + Bay + genesis). Prediction if right: TN ACC back to ~0.29 with the 50-level upper-air gain kept.

28 Oct 10:35: CONFIRMED main cause of P1 = vertical resolution at the tropopause / low model top: tp75 (top ~4 hPa, ~8 hPa layers near 170 hPa) cuts 250 hPa bias -5.8 -> -3.6 K and 100 hPa +7.1 -> +2.1; adding ECMWF cloud-top + organised entrainment -> -1.7 K. Remaining: verify exam/TN rain/tracks/genesis with tp75.

## P3 Storms too weak (Arnab Cat 4 -> ours ~1001 hPa; Nivar severe -> ours 1004-1006 hPa) and unknown false-alarm rate
Sridhar's note (28 Oct, GFS over- vs ECMWF under-intensification) checked against our code:
- RH-dependent entrainment: already in (eps = entr x (1.3 - RH), ECMWF form).
- Closure timescale: CAPE removed over tau_deep = 40 min (ECMWF ~1 h or cloud depth / updraught speed; option mf_wup) - fine.
- Large-scale constraint: option mf_closure='hybrid' (moisture convergence) exists, off.
- Hyper-diffusion: del^4, e-folding 8.6 h at T85, ~3.6 h at T170 on the smallest wave -> candidate cause of weak, broad cores. Options diff_x (time multiplier), diff_order (3 = del^6).
Why chain: storms weak <- core not resolved/kept <- (a) 80 km grid (Stage 3), (b) inserted vortex fixed 180 km, (c) small scales damped by diffusion. Test: Nivar/Arnab-type cases with diff_x 4 vs 1 at T170 (intensity + track).
Gap: genesis test counts hits only - add a FALSE-ALARM measure (model storms with no real storm within 500 km) against GFS-style phantom storms.

28 Oct 20:00: P1 - mountain (sigma pressure-gradient) hypothesis ruled out (open Pacific same bias). 100 hPa: day-0 representation error +2.9 (32L) / +1.2 (tp75); sponge removes most of the remaining 100 hPa drift. Remaining: 250 hPa drift ~-1.6..-2.3 K -> next: full T-tendency budget incl. dynamics residual.
P3 - weak storms: diff_x 4 deepened Nivar to 1003 hPa (-9) and put it within 70-80 km on 24-25 Nov (single case) -> hyper-diffusion supported as a cause; broad test running.
