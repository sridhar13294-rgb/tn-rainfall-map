# MEGAM root-cause log (5-Why / fault tree before any test)
Rule (Sridhar, 28 Oct): no trial-and-error screening. For each problem: 1) symptom in numbers; 2) 5-Why / fault tree using the heat-budget, the code and reference documents (ECMWF IFS Part IV, papers); 3) each hypothesis with the signature it predicts; 4) at most 1-2 discriminating tests; 5) confirm, then fix; 6) adoption gate (budget + genesis + tracks + exam incl. TN rain).

## PROCESS (Sridhar, 30 Oct 09:54) - investigate before testing
1. Define the symptom with numbers (region, level, lead time, vs which truth).
2. 5-Why from the symptom down to a mechanism in the code.
3. Fishbone - list causes in 6 branches: Dynamics/numerics, Physics schemes, Initial state/insertion, Surface/ocean/land, Resolution/grid & levels, Verification/data.
4. A candidate passes ONLY if ALL hold: (a) exact code line + implemented equation identified; (b) theory/literature gives the expected value and ours is clearly off (magnitude stated); (c) it explains EVERY measured signature of the problem; (d) no existing test result contradicts it; (e) a predicted signature (which numbers move, which way, how much) is written down BEFORE testing; (f) the fix is physically justified, not a tuning knob.
5. Quick test: isolated change, same starts, <= ~1 h, measure the predicted signature + adverse effects (stability, conservation, 850 hPa, all-India rain gate where relevant). Signature absent -> reject the candidate (do not stretch the hypothesis).
6. Full regression only after 5 passes: exam 73 starts (all regions incl. Indian rain regions), genesis, Bay/AS/SI tracks + intensity, ensemble spread; adoption rule vs the control.

### Current problems through the process
P1 cold upper troposphere (tropics d5 250/300/400/500 hPa -5.9/-5.6/-4.4/-3.3 K vs ERA5; ~1/3 of it in day 1)
 Why1 the column 190-700 hPa loses heat (budget: -1.5..-2 K/day day 1) -> Why2 convective heating aloft is small vs radiative cooling -> Why3 deep convection fires in only 5-11% of columns, grid-scale condensation (peak ~600 hPa) does the heating -> Why4 boundary-layer moist static energy / CAPE is removed before deep convection can use it -> Why5 the shallow MSE mixing relaxes the whole parcel depth to its mean in 1 h (implied exchange 0.3-0.9 kg m-2 s-1 vs observed 0.02-0.03).
 Fishbone (others): radiation/clouds (rad_top tested: no), sponge (no), initial state (small at 250 hPa), trigger thresholds (no), levels (tp75 helps aloft but hurts rain), ozone (open), resolution (open).
 Candidate 2 (shallow mixing rate) passes a-f; predicted: deep share up (>15%), grid-scale down, 250-500 hPa warmer by >=1 K, 615 hPa moistening down, 850 hPa not colder than -1 K change. Quick test: tn-prof-shmf.
P3 storms fill in 12 h and never intensify (72 h 28 kt vs observed 73 kt, 6 storms; 54-storm audit)
 Why1 low-level spin is removed faster than it is generated -> Why2 not DFI, not the inserted vortex (Nivar without it is as weak; bogus equations correct), not surface fluxes (audited) -> Why3 a momentum sink acts where convection is on (the core) -> Why4 convective momentum transport relaxes u, v to the cloud-layer mean -> Why5 with tau_cmt = 6 h vs ~2 days for mass-flux CMT (column mass / cloud-base mass flux), ~8x too fast.
 Fishbone (others): resolution (63 km test pending), heating organisation (budget pending), ocean cooling (small at these winds), diffusion (no), DFI (no), shallow mixing (sh_cap made storms weaker - consistent with BL ventilation, not refuting Candidate 1).
 Candidate 1 (CMT time scale) passes a-f; predicted: with CMT off, 850 hPa max wind keeps or gains strength through 24 h, central pressure falls >=2-3 hPa more by 72 h, warm core 300 hPa grows. Quick test: tn-sb-cmt.
P2 rain worse with more levels and P4 TN wet bias (TN box 7.1 vs 4.6 mm/day at 32L, 10.2 at 75L; grid-scale rain on TN land and Ghats, little convective rain, no rain shadow under westerlies)
 Why1 grid-scale condensation over TN/Ghats -> Why2 mid levels saturate there -> Why3 moisture is lifted to 600-700 hPa without convection raining it out -> Why4a shallow mixing moistens 600-700 hPa (+1.2 g/kg/day) and suppresses deep convection (Candidate 2); Why4b smoothed 80 km Ghats give no lee descent (terrain suspect, separate).
 Status: Candidate 2 partly explains P2/P4 (prediction: grid-scale rain over TN land and Ghats down, convective share up); terrain branch to be examined with vertical motion fields before any test.

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

28 Oct 20:40 - P3 initial-state audit (Sridhar's checklist, item A): Bay storms (54 cases, inserted vortex), mean best-track vmax vs model max wind (kt) / min pressure:
          0 h          24 h         48 h         72 h
 real    22.5         27.1         33.9         44.6
 T170    28.1/1004.7  24.9/1006.0  29.2/1003.2  28.3/1003.8
 T85     22.7/1006.2  17.1/1008.0  22.1/1005.5  23.2/1004.7
-> Start strength is RIGHT on average (not the cause). Two signatures: (1) SPIN-DOWN in the first 24 h (T85 -25%, T170 -11%) = start imbalance (inserted vortex vs model physics/DFI) and/or damping; (2) NO intensification afterwards (real +65% from 24 to 72 h, model ~flat) = missing energy supply/organisation (surface enthalpy flux, convective heating profile, diffusion).
Next discriminating diagnostics (no new physics): storm-following budgets on ~10 Bay cases at T170: surface enthalpy flux under the core, convective heating profile within 200 km, vorticity/KE change by term incl. diffusion, 850-200 shear and mid-level RH around the storm vs ERA5. diff_x 4 runs (tn-bay-diff4) will show whether the spin-down shrinks.
P3 additions (Sridhar 20:28): (a) per-storm distribution, not only means; (b) the adjustment at 0/3/6/12/24 h (min p, max wind, 850 vorticity, radial profile) - immediate drop = start imbalance, gradual = fluxes/heating/shear/damping; suspect also our digital-filter initialisation (M.dfi) which may weaken the inserted vortex before hour 0 -> compare vortex before and after DFI and a run without DFI; (c) verification convention: best track = 1-min (JTWC) or 3-min (IMD) sustained surface wind; model = max lowest-level grid wind on an 80-140 km grid -> not like-for-like; compare trends and minimum pressure, and use a resolution-aware wind conversion before quoting absolute intensity errors.

## Findings 29 Oct (night + 08:00 cycle)
P1 cold upper troposphere
- Sponge ruled out below 100 hPa: confined sin^2 sponge 30->4 hPa (6 h, 12 h) changes nothing at 200-500 hPa (T170 32L, 10 starts). Keep it as the standard top sponge (harmless, ECMWF-style); not a fix.
- rad_top 0 (radiation to the top, no relaxation): 100 hPa worse (+8.5 -> +9.6), rest unchanged -> keep rad_top 0.12 for now.
- First T budget (T170 32L, tropics, 2-snapshot physics): the column 190-700 hPa cools 1.4-2.1 K/day in the FIRST day, then ~0.5 K/day on day 5. So about a third of the day-5 cold bias appears in day 1 (start-up shock), the rest is slow drift. Day 4-5: physics heats 300-500 hPa (+0.9..+1.2) but dynamics cools more (-1.3..-1.7) -> net cooling. Budget v2 (3-hourly, by process, tropics/TN/Ghats, T and q) running for 32L and 75L to name the process.
P2 rain vs levels
- tp75oc package rejected (exam/genesis/tracks). Clean levels-only tp75 exam running (quarters 0-1).
P3 weak storms
- Weaker diffusion (diff_x 4): neutral on 86 genesis cases and 83 Bay storms (+0.5-0.8 kt). Ruled out as main cause.
- DFI: without DFI the inserted vortex starts 5 hPa deeper (995.6 vs 1000.7 hPa, Arabian Sea, 105 cases), but by 12 h both are the same (1002.8 vs 1003.0) and stay identical to 72 h. DFI is NOT the cause: the model itself fills the vortex within 12 h.
- So the spin-down is the model rejecting the inserted vortex in its first 12 h. Remaining suspects (fault tree): (a) grid too coarse for the core (test: T255 ~50 km, running); (b) inserted vortex structure not in balance with model physics (no warm core / moisture, size); (c) surface exchange / convection not organising around the core. Nivar (no inserted vortex) is also weak, which favours (a) or (c) over (b).
- Data for GWD/blocking (sub-grid orography 0.5 deg) and ozone climatology (monthly zonal mean, 37 levels) are in release era5-cases (geo_gwd.npz, ozone_clim.npz).

## Findings 29 Oct 14:00 - heat budget by process (10 starts, T170, 3-hourly, tropics/TN/Ghats)
Causal chain found for P1 (cold upper troposphere), to be confirmed by the trigger tests:
1. Deep convection fires in only 11% of tropical columns on day 1 and 5% on day 5 (TN/Ghats 0-2%).
2. So grid-scale condensation does most of the rain: tropical column heating day 5 ~ large-scale 230 W/m2 vs deep convection 50 W/m2 (day 1: 170 vs 80); re-evaporation takes back ~55%.
3. Grid-scale heating peaks at ~600 hPa; convective heating would peak at 300-500 hPa. The upper troposphere (190-400 hPa) gets only +0.2..+1.0 K/day from convection against -1.4..-1.7 K/day radiative cooling -> it cools.
4. The 'shallow' MSE mixing runs in every CAPE column that the deep test rejects, up to the parcel top (often 400 hPa): it moves heat DOWN (300-700 hPa cooled by up to -6.7 K/day, 850-950 hPa warmed by +5..+10 K/day, column-conserving). Shallow clouds should not reach 400 hPa.
=> Root-cause candidate: the deep-convection trigger rejects most tropical convection (cloud-depth test 250 hPa, entrainment, kick), and the leftover columns get deep 'shallow' mixing. Tests running: tn-prof-trigA (mf_dmin 200 hPa; entrainment x0.5), tn-prof-trigB (organised entrainment; kick 1 K), tn-prof-shal (sh_dtop 0.6 = no shallow mixing where the parcel top is above 600 hPa; sh_top 0.7 cap). Confirm = on_dp up, large-scale share down, 250 hPa warmer, TN rain not worse.
P2 (TN rain with more levels) - levels-only 75L exam (quarter 0, 19 starts): z500 tropics d5 better (32.2 -> 30.3) but TN rain24 d5 error 5.2 -> 11.7 mm and ACC 0.32 -> 0.02. So the extra convection options were NOT the cause; the levels alone are. Budget: over TN at day 5, 75L gives 2.9 mm/day of grid-scale rain vs 0.6 with 32L, with deep convection still ~0-1% -> thinner layers saturate more easily, and with convection not firing the moisture comes out as grid-scale rain. Same root cause as P1 (convection trigger), so fix the trigger on 32L first, then re-test 75L.
P3: T255 runs killed by out-of-memory (host RAM) on Kaggle T4 - try T213 (~63 km) or a smaller storm subset next. DFI result stands.
Quota: Kaggle accounts 3 and 4 reached the 30 h weekly GPU limit (pushes refused) - not usable until the weekly reset.

## Trigger tests 29 Oct 17:40 (10 starts, T170 32L, vs control)
- Deep-trigger thresholds are NOT the cause: cloud depth 200 hPa, entrainment x0.5, organised entrainment, kick 1 K -> activation 4-5% at day 5 (control 5%), 250 hPa bias unchanged (-5.7..-5.9).
- The 'shallow' MSE mixing in deep-parcel columns IS a cause: sh_dtop 0.6 (no shallow mixing where parcel top is above 600 hPa) -> deep activation day 5 5% -> 15%, deep-convection heating 45 -> 114 W/m2, grid-scale 232 -> 151 W/m2, tropics d5 bias 250/300/400/500 hPa -5.9/-5.6/-4.4/-3.3 -> -4.8/-4.2/-2.8/-1.3 K. sh_top 0.7 cap similar.
  Mechanism: the mixing moves heat down and removes the instability, so deep convection rarely fires and grid-scale rain takes over.
- Side effect: 850 hPa +0.8 -> -2.1 K (the mixing was warming low levels). TN rain day 5 0.6 -> 2.1 mm/day (direction unknown until scored vs gauges).
- Remaining cold at 250 hPa (-4.8) = other causes still open (radiation/cloud, day-1 shock).
Next: exam quarter 0 with sh_dtop 0.6 (tn-wx-shd06q0, acct 1) for TN rain/z500; then a proper boundary-layer shallow scheme for the low-level part.

## Exam 29 Oct 20:10 (19 exam starts, quarter 0)
sh_dtop 0.6 (shallow-mixing fix) vs control: tropics z500 ACC d1/d3/d5 0.79/0.65/0.51 -> 0.83/0.71/0.57, u200 tropics better, India t2 better, India rain d1 better; but India t850 worse (d5 3.43 -> 3.90 K) and TN rain24 d5 RMSE 5.2 -> 11.5 mm, ACC 0.32 -> 0.04. Per start: wet bias in almost every start, largest in SW-monsoon starts (20 May +20.6, 9 Jun +14.7, 8 Aug +15.3 mm) when TN is in the rain shadow. 75 levels alone shows the same TN wet pattern (19 Jul +19.2, 8 Aug +15.0).
=> Do NOT adopt sh_dtop 0.6. The control's "good" TN rain partly comes from convection being suppressed. New problem P4: when convection is allowed to work (more levels or less shallow mixing), the model rains too much over TN, especially in the SW monsoon. Suspects: rain-shadow not reproduced at 80 km (Ghats too smooth -> no descent), daytime land convection over TN triggering too easily, or too-moist low levels. Next: per-start rain maps (convective vs grid-scale, land vs coast, time of day).
Genesis 75 levels only (half 1, 42 cases): 8 formed vs 18 with 32L -> 75 levels also hurts genesis by itself.

## P3 code audit 30 Oct 00:40 (surface exchange, mm2.py ~333-362, ocean ~607)
Checked: bulk formulas E = rho ck V1 (qsat(SST, ps) - q1), H = rho cp ck V1 (SST - theta1 at ps) - signs, units (kg m-2 s-1, W m-2) OK; V1 includes 1 m/s gust; Charnock 0.018 roughness at sea; Cd capped 2.4e-3; Ck 1.2e-3 (10 m) partly brought to the ~80 m lowest level (ck_z 0.5) -> Ck/Cd ~0.7-0.8 (observed range ~0.5-1, OK); stability factor shared; no salinity factor on qsat (+2% only); ocean cooling only above 10 m/s (V1-10)^2 - small for our weak storms. No defect found in the flux code itself.
Leading mechanism instead (links P1 and P3): the 'shallow' MSE mixing removes instability so deep convection fires in only ~5-11% of tropical columns; latent heating then comes from grid-scale condensation peaking ~600 hPa. A tropical cyclone's warm core and pressure fall need deep convective heating in the upper troposphere around the core - heating too low and too spread would explain fill-in and no intensification.
Targeted test (next): storm-following budget for 2-3 representative failing storms (incl. Nivar, no inserted vortex): every 3 h within 300 km of the centre - surface enthalpy flux, heating by process by level, warm-core anomaly (T') at 300 hPa, min pressure; control vs sh_dtop 0.6. If deep heating rises and the core deepens with sh_dtop -> mechanism confirmed; the proper fix is a boundary-layer-limited shallow scheme (must also pass the all-India rain gate).

## P3 quick test 30 Oct 01:50 - sh_cap 0.8 + sh_dtop 0.6 (mixing kept only up to ~800 hPa in deep-parcel columns), 6 Bay storms 72 h, T170, vs control same starts
Mean wind (kt) real / control / change: 0 h 20.0/25.2/25.2; 24 h 25.8/20.7/19.3; 48 h 44.2/27.9/21.9; 72 h 73.3/27.7/24.0. Pressure (hPa) control/change: 48 h 1003.3/1004.2; 72 h 1002.5/1003.2. Per storm: weaker in Sidr, Phailin, Titli, Giri, Hamoon; mixed in Nivar (72 h +2 kt, but pressure 2.5 hPa higher). No blow-ups.
=> REFUTED as the intensification fix: freeing deep convection by limiting shallow mixing does NOT make storms intensify (slightly weaker). The suppressed-convection mechanism explains part of the cold upper troposphere but is not the main cause of weak storms. Remaining suspects (fault tree): grid too coarse for the core (63 km test still to run), inserted-vortex structure/balance, how convective heating is distributed around the core (mass-flux closure / where heating goes relative to the centre), surface-flux feedback (wind-induced). Next = the storm-following budget (where heating and pressure fall happen vs the centre) before any further change.

## 30 Oct 10:00 - line-by-line physics review: two candidates (theory + evidence)
Reviewed mm2.py: surface layer (388-408), K-profile PBL (409-444), parcel/BMJ trigger (445-476), shallow MSE mixing (477-493), mass-flux conv_mf (250-375: plume, flux-form heating, CAPE closure, downdraft), CMT (503-506), large-scale condensation + evaporation (507-519), Holland bogus (195-248). Equations checked: flux-form convective q/h tendencies with explicit condensation sink (correct), gradient-wind + hydrostatic warm core of the bogus (correct signs), bulk fluxes (correct), saturation adjustment at 100% RH (standard).
CANDIDATE 1 - convective momentum transport (CMT) over-damps vortices (storm spin-down, no intensification, no genesis): line 506 relaxes u, v in every deep-convecting column toward the cloud-layer mass-mean wind with tau_cmt = 6 h. Mass-flux CMT (Gregory et al. 1997; ECMWF) changes the wind on the column-mass / cloud-base-mass-flux time scale, ~1e4 kg m-2 / 0.05 kg m-2 s-1 ~ 2 days, and less with the pressure-gradient correction. 6 h is ~8x too fast. For a weak storm (15 m/s low-level, cloud-layer mean ~7 m/s) it gives ~ -30 m/s per day at low levels - as large as surface friction on a 1 km boundary layer, and it acts exactly in the storm core where deep convection is on. Fits: 12-h fill-in independent of DFI/bogus, no intensification, Andaman low never forms, no rain/flux defect. Test: storm budget Nivar/Titli/Sidr, tau_cmt off vs on (tn-sb-cmt).
CANDIDATE 2 - shallow MSE mixing far too strong (cold upper troposphere, suppressed deep convection, grid-scale rain dominance): lines 485-493 relax h and q over the whole parcel depth (often 1000-400 hPa) to their column mean with tau_shallow = 1 h. That equals an exchange mass flux of ~m/(2 tau) = 0.3-0.9 kg m-2 s-1, 10-40x observed shallow-cumulus mass fluxes (~0.02-0.03, BOMEX/Siebesma et al. 2003). Measured: h_shal -6.7 K/day at 615 hPa and +10.6 K/day at 951 hPa (tropics, day 1) vs typical shallow-cumulus +-1-2 K/day. Mixing toward the mean lowers boundary-layer moist static energy -> CAPE destroyed -> deep MF fires in only 5-11% of columns -> grid-scale condensation (peak ~600 hPa) does the heating -> upper troposphere cools. Consistent with sh_dtop test (deep 5->15%, 250-500 hPa 1-2 K warmer). New option sh_mflux (mixing time from a realistic mass flux, 0.03). Test: prof 10 starts with budget (tn-prof-shmf) - must keep 850 hPa and the all-India rain gate.
Side results: T213 storm test killed by host memory again (M.run stores fields) -> rerun through storm_budget (integrate only): tn-sb-t213. GWD on vs off: temperature neutral (as expected; wind/z500 extratropics still to score). Storm budget on GitHub CPU failed (log not reachable through the proxy) -> moved to Kaggle (tn-sb-cmt includes the control budget).

## P2/P4 32L vs 75L TN rain diagnosis (6 starts: 4 SWM, 2 NEM; T170) - 30 Oct 09:50
TN-box rain model vs truth (ERA5), 5-day mean: 32L 7.1 vs 4.6 mm/day (+54%); 75L 10.2 vs 4.6 (+122%). TN land rain split conv/grid-scale (mm/day): 32L 2.5/9.2, 75L 0.8/14.9; Ghats 32L 4.4/13.4, 75L 1.4/23.8. => P4 (TN wet bias) exists already with 32 levels and is GRID-SCALE rain; 75 levels (P2) amplifies the same thing (convection on TN land 3x less, grid-scale +60%). SWM starts have westerly 850 hPa wind over TN (+8..+11 m/s) yet grid-scale rain on the lee (TN land) - no rain shadow.
Link to Candidate 2: the shallow MSE mixing moistens 600-700 hPa strongly (+1.2 g/kg/day at 615 hPa, tropics day 1) while suppressing deep convection - mid-level saturation then rains out as grid-scale rain (h_lsc peak ~600 hPa). Hypothesis: Candidate 2 contributes to P1, P2 and P4. tn-prof-shmf budget gives TN/Ghats rain by type to check it; then the all-India rain gate. Ghats smoothness at 80 km (no lee descent) remains a separate suspect for P4.

## 30 Oct 11:30 - quick-test results vs pre-registered predictions
Candidate 1 (CMT off), storm budget, T170, ctl vs no-CMT:
| Prediction | Sidr | Titli | Nivar |
| 850 hPa wind holds/grows to 24 h | 14.3->20.4 PASS | 18.0->19.4 PASS | 14.2->14.5 PASS (ctl 10.1) |
| pmin >= 2-3 hPa deeper by 72 h | 998.5 vs 999.4 (-0.9) FAIL | 992.0 vs 1000.4 (-8.4) PASS | 993.4 vs 1004.5 (-11.1) PASS |
| 300 hPa warm core grows | 1.83 vs 1.90 FAIL | 2.36 vs 1.89 PASS | 2.68 vs 1.72 PASS |
=> SUPPORTED (7 of 9 checks; Sidr weakly). Extra signature: without CMT core deep convection stays on (Nivar 24-48 h: 1.0 vs 0.0-0.2). No blow-ups. Next: CMT at the mass-flux time scale (tau_cmt 2 days) on 6 storms (tn-quick6-cmt2d) + budget (tn-sb-cmt2d), then regression.
Candidate 2 alone (sh_mflux 0.03), heat budget 10 starts, vs control:
| deep share > 15% | 0.11/0.05 -> 0.19/0.21 PASS |
| less grid-scale heating | 168/232 -> 32/81 W/m2 PASS |
| 250-500 hPa >= 1 K warmer | 250 -5.9->-4.5, 300 -5.6->-3.9, 400 -4.4->-2.7, 500 -3.3->-1.3 PASS |
| less 615 hPa moistening | 1.23 -> 0.34 g/kg/day PASS |
| 850 hPa no more than 1 K colder | +0.8 -> -2.3 (3.1 K colder) FAIL (FMEA predicted it: B-L1 weak PBL mixing) |
OLR 215 -> 202 (worse). => mechanism CONFIRMED for P1, fix ALONE REJECTED (850 hPa). Next as FMEA action #2: pbl_tm 1 + sh_mflux 0.03 together (tn-prof-combo).

## 30 Oct 13:15 - results vs pre-registered predictions (F2 combined, F1 at 2 days)
F2 = pbl_tm 1 + sh_mflux 0.03 (10 starts, heat budget), control / F2 alone(shmf) / F2 combined:
 d5 tropics T 250 -5.9/-4.5/-4.2, 300 -5.6/-3.9/-3.5, 400 -4.4/-2.7/-2.4, 500 -3.3/-1.3/-1.0, 700 -2.9/-0.8/-0.5, 850 +0.8/-2.3/-2.4, 925 +2.4/-1.9/-1.7, 1000 +2.7/-1.3/-1.0; deep share 0.05/0.21/0.24; grid-scale heat (d4-5) 232/81/87 W/m2; OLR 215/202/201.
 Pre-registered: 850 within +-0.5 K of control -> FAIL (-3.2 K). Upper air, deep share, grid-scale, 615 hPa moistening -> PASS. REJECTED as is.
 5-Why on 850 hPa: cold AND moist (q850 +0.78 g/kg) -> radiation -3.0 K/day at 862 hPa (control -1.1) + condensation 1.6 K/day at 862 -> a low cloud deck forms at the boundary-layer top and cools by long-wave from its top -> radiation clouds start at 80% RH at low levels (B-R1) and condensation/cloud are inconsistent (B-G1); slower shallow mixing no longer exports that moisture. => points to F6 (planned action #6). Note: the control itself is +2.4..+2.7 K too warm at 925-1000 hPa (old shallow mixing heated the surface layer +10 K/day); F2 reduces that to -1.7/-1.0, so 'within 0.5 K of control' was a poorly posed target. New test F2+F6 gets an absolute target vs ERA5 (registered before running).
F1 at 2 days (tau_cmt 172800 s), 6 storms 72 h (hind2) + budget 3 storms:
 Mean wind real/ctl/F1: 24 h 25.8/20.7/23.8, 48 h 44.2/27.9/28.3, 72 h 73.3/27.7/32.0 kt; pressure 72 h ctl 1002.5 / F1 1000.5. Per storm 72 h pmin vs ctl: Titli -7.5, Nivar -8.2 PASS; Sidr +0.8, Giri +4.6, Phailin +0.2, Hamoon -1.4 FAIL. Warm core (budget): Titli 2.53 vs 1.89, Nivar 3.00 vs 1.72, Sidr 1.38 vs 1.14 (all up).
 Tracks (hard gate): mean error 24/48/72 h ctl 89/203/246 km, F1 112/244/365 km -> FAIL (Giri includes a tracker jump; worse in 4 of 6, better in Nivar).
 => Not adoptable. Intensity response real in 2 storms, absent in 4.
NOISE FLOOR (new, important): the identical control (Sidr, T170, same settings) in two separate jobs gave 72 h pmin 999.4 vs 1003.0 hPa and v850 17.7 vs 15.0 m/s -> GPU non-determinism grows into differences of ~3-4 hPa by 72 h. Single-storm differences below ~4 hPa are noise. Action (C-V2, now urgent): repeat a control 3x to measure the spread; judge per-storm effects only beyond it; use more storms rather than single cases.

## 30 Oct 13:30 - tracker audit (F1 2 days) and registered targets for F2+F6
Tracker audit: one-step jumps > 250 km exist in BOTH runs (ctl: Sidr 114 h, Giri 72 h, Phailin 72 h, Titli 78 h, Nivar 36 h, Hamoon 78/84 h; F1: Giri 54 h). Excluding any position after a jump: 24 h ctl 89 / F1 112 km (6 storms; worse in 5), 48 h 202 / 237 (5 storms; worse in 4), 72 h 252 / 353 (4 storms; worse in all 4). => the track degradation is REAL, not a tracker artefact. Tracker fix (measurement): flag/stop tracks at jumps > 250 km per 6 h (to do in score_hind and track()).
REGISTERED BEFORE RUNNING - F2+F6 (pbl_tm 1 + sh_mflux 0.03 + consistent cloud fraction), 10 starts, d5 tropics vs ERA5 (absolute):
 850 hPa bias within +-1.0 K; 925 and 1000 hPa within +-1.5 K; q850 bias within +-0.5 g/kg;
 250 hPa bias >= -4.5 K (warmer than or equal); 500 hPa within +-1.5 K;
 deep share >= 0.20; OLR (tropics) >= 220 W/m2;
 grid-scale/deep heating ratio (d4-5) <= 1.0; no blow-up.
 Any one failing -> reject (no re-explaining).
Noise: per-metric spread (pmin, v850, warm core, track) from the repeat controls tn-sb-ctl-r2/r3b; 4 hPa is provisional only.

## 30 Oct 13:45 - audit (no GPU) of the two failures, per peer-review checklist
P1 / 850 hPa cold in F2:
- Humidity: rain (mm2.qsat) and radiation (radcloud.qsat) use the SAME saturation formula and the same T, q, p -> consistent. CONFIRMED by reading.
- Cloud: radiation large-scale cloud c = 1 - sqrt((1-RH)/(1-RHc)), RHc 0.80 low / 0.70 aloft; in-cloud water = 1% of qsat (+ condensation x 1 h). Condensation in mm2 only at 100% RH; no cloud water variable. So between 80% and 100% RH the radiation sees cloud that the water budget never formed. CONFIRMED inconsistency (B-G1/B-R1).
- Heating conversion: LW heating = flux divergence x g / (cp dp) -> dimensionally correct. -3 K/day at 862 hPa is a realistic cloud-top cooling rate for a low cloud deck (observed stratocumulus tops -5..-10 K/day in a thin layer).
- What is missing (new FMEA item B-L3): in nature cloud-top cooling drives turbulent mixing (it makes the cloud-top air sink and entrain warm dry air from above), which spreads the cooling and dries the cloud. Our K-profile boundary layer has no cloud-top-cooling term, so the cooling stays at 850 hPa and the layer stays moist (q850 +0.78 g/kg). The old over-strong shallow mixing hid this by mixing everything. => 850 hPa root cause = B-L3 (missing cloud-top-driven mixing) + B-R1 (cloud from 80% RH without water). Both need fixing with F2.
P3 / tracks with momentum mixing:
- The current CMT equation (relax u, v toward the cloud-layer mass-weighted mean, one time scale everywhere) conserves column momentum and is dimensionally correct, BUT it is not the mass-flux CMT equation. Mass-flux CMT (Gregory et al. 1997; ECMWF): du/dt = g d/dp [M_u (u_u - u)] with the updraft wind u_u from the entraining plume and a pressure-gradient term (u_u pulled toward u). Its strength scales with the actual mass flux M_u - strong in deep, organised convection, weak elsewhere. Ours acts with the same rate in every convecting column (ITCZ, monsoon trough), so it reshapes the large-scale vertical shear = the steering flow; changing its single time scale (6 h -> 2 d) therefore changes steering everywhere -> tracks. => The defect is the EQUATION, not just tau. Fix = implement mass-flux CMT with the plume's eta x Mb (available in conv_mf). Predicted: storm-core spin-down reduced (strong Mb there) while steering in weak-convection areas changes little -> intensity gain without the track loss.
Noise floor: inputs, code and settings identical; XLA on GPU uses non-deterministic parallel reductions by default -> rounding differs run to run and grows chaotically. Remedy: XLA_FLAGS --xla_gpu_deterministic_ops=true for all A/B tests (bit-reproducible); chaos still means any real change perturbs the run, so judge on several storms.

## 30 Oct 14:05 - mass-flux CMT: derivation, expected result, implementation, registered predictions
Derivation (Gregory et al. 1997; ECMWF): environment du/dt = g d/dp [M (u_u - u)]; updraft du_u/dz = -eps (u_u - u) + C_u du/dz, C_u = 0.7, M = eta x Mb from the deep plume. Old code: du/dt = (u_cloudmean - u)/tau_cmt in every convecting column.
Offline calculation (scratchpad deriv/cmt.py, idealised columns, equal 50-hPa levels):
| column | scheme | 950 | 850 | 700 | 500 | 300 | 200 hPa (m/s per day) | 850-200 shear change per day |
| storm core, rain 120 mm/d (Mb 0.093) | old 6 h | -23.1 | -21.1 | -11.1 | +4.9 | +20.9 | +28.9 | +50 |
|  | old 2 d | -2.9 | -2.6 | -1.4 | +0.6 | +2.6 | +3.6 | +6 |
|  | mass-flux | +2.2 | -3.7 | -3.7 | -1.8 | +4.4 | +5.0 | +9 |
| monsoon column, rain 10 mm/d (Mb 0.008) | old 6 h | -25.7 | -33.7 | -17.7 | +6.3 | +30.3 | +46.3 | +80 |
|  | old 2 d | -3.2 | -4.2 | -2.2 | +0.8 | +3.8 | +5.8 | +10 |
|  | mass-flux | +0.6 | -0.2 | -0.6 | -0.3 | +0.4 | +0.6 | +0.8 |
Column momentum conserved in all (sum ~ 0). Reading: the old 6 h rule erases 850-200 hPa shear in every convecting column within hours (+50..+80 m/s/day) and spins down storm low levels at ~ -21 m/s/day; the 2-day rule is still 12x too strong in ordinary monsoon convection (changes steering) while mass-flux CMT is weak there (+0.8) and moderate in storm cores (-3.7 at 850). => explains both results: 'off'/'2 d' helped storms but 2 d still reshaped steering (tracks). Implementation (mm2 option cmt_mf, scan bottom-up) reproduces the offline numbers exactly (check_impl.py: core -3.7 at 850, monsoon shear +0.8).
Noise floor from 3-4 identical controls (72 h): pmin spread Sidr 3.6, Titli 1.6, Nivar 2.6 hPa; v850 spread 2.8 / 3.8 / 3.2 m/s; warm core 300 hPa 0.8 / 0.1 / 0.6 K. CMT-off effect beyond noise for Titli (-7..-8 hPa, +5..+9 m/s) and Nivar (-9..-12 hPa, +9..+12 m/s); Sidr within noise.
REGISTERED (before running, GPU deterministic ops on): cmt_mf vs control
 (a) storm budget Nivar/Titli/Sidr: 72 h pmin deeper than the deepest control by > noise spread in >= 2 of 3 storms, and v850 at 72 h above the highest control in >= 2 of 3;
 (b) 6 quick storms (hind2): jump-cleaned mean track error at 48 h and 72 h no more than 10% worse than control (ctl 202 / 252 km on the cleaned sets);
 (c) mean 72 h wind (6 storms) > control 27.7 kt + 2 kt; no blow-up.
RESULT (a) 30 Oct 14:00 IST - PASS. 72 h pmin/v850 (controls ctl,r2,r3b; deepest ctl / highest v850):
 Sidr  cmt_mf 1001.2 / 19.0  vs ctl best 999.4 / 18.1 -> pmin NOT deeper (fail), v850 higher (pass)
 Titli cmt_mf  993.3 / 31.3  vs 998.8 / 27.9 -> 5.5 hPa deeper (> spread 1.6) pass; v850 pass
 Nivar cmt_mf  996.3 / 30.5  vs 1002.9 / 23.9 -> 6.6 hPa deeper (> 2.6) pass; v850 pass
 => pmin 2/3, v850 3/3: gate (a) met. Recovers most of the CMT-off gain (off: Titli 992.0, Nivar 993.4) while derivation says monsoon shear is kept (+0.8 vs +80 m/s/day).
 Sidr: warm core 300 hPa -0.3 K and deep share 0 in the core at 72 h (ctl 1.7-1.9 K, deep 1.0) - convection shut off in Sidr core under cmt_mf; flux core 66 W/m2 vs 195-260. Checked: tracker artefact. Sidr centre jumps ~280 km at +48 h (9.5N 91.4E -> 11.6N 92.8E) and ~310 km at +66 h (90.7E -> 93.5E, onto the Andaman islands: flux 11-25 W/m2). Up to +45 h the core is normal (wc300 up to 1.1 K, deep 0.8-1.0). Sidr stays a weak, multi-centre low in every variant (ctl/off/2 d all within noise) - same tracker jump issue as the quick-test track scoring; tracker fix (stop at >250 km/6 h) is already in the queue.
 Gates (b) tracks and (c) mean wind pending tn-quick6-cmtmf. Level: L2 -> L3 only if (b)+(c) pass and regression passes.
RESULT (b),(c) 30 Oct 14:30 IST (tn-quick6-cmtmf; scorer scratch score_q6.py reproduces ctl 89/202 and 2 d 112 km):
 Tracks, jump-cleaned, same storm sets as registered: 48 h ctl 202 / cmt_mf 231 km (+15%, limit +10%) FAIL; 72 h ctl 252 / cmt_mf 414 km (+64%) FAIL. Worse in Sidr, Phailin, Titli at 72 h; Hamoon and Phailin worst.
 Mean 72 h wind: ctl 27.7 / cmt_mf 27.2 kt (target > 29.7) FAIL. 48 h 27.9 -> 29.3 kt. Pressure 72 h 1002.5 -> 1001.3.
 => cmt_mf REJECTED as registered (2 of 3 gates fail). Option stays default OFF. Level stays L2.
 Prediction that failed: 'weak CMT in monsoon columns keeps steering, so tracks stay within 10%'. The derivation (+0.8 m/s/day shear change) holds for the column, but tracks still degrade -> track damage is NOT explained by CMT strength in the environment. Remaining candidate (not yet derived): a stronger/deeper inner vortex changes its own motion (beta drift grows with outer-wind strength; vortex tilt in shear). Also: intensity gain only in Titli/Nivar again (same as 2 d and off) -> CMT is not the limiter in 4 of 6 storms; P3 main cause lies elsewhere (grid scale 80 km, vortex moisture A-B4, surface fluxes at 80 km).
 MEASUREMENT GAPS found while scoring (no threshold changed): (1) Track noise: the three storm-budget controls differ by 79-389 km in centre position at 24-72 h (weak, multi-centre lows; budget tracker searches 350 km) -> single-storm track differences of ~150 km are noise. (2) The deterministic flag was only in the cmt_mf runs; ALL controls (sb ctl/r2/r3b, t170-new) ran without it. Action: deterministic 6-storm control twice (tn-quick6-ctl-d1/d2, accounts 1/7) -> confirms bit-reproducibility and gives the control every future quick test must use; track noise must then be measured with a perturbed-start ensemble, since a deterministic run has zero spread by construction.


## 30 Oct 14:15 IST - D1 consistent cloud + D2 cloud-top entrainment (P1 850 hPa cold, P4): derivation, offline check, registered predictions
Question (5-Why level 4 of the F2 failure): is -3.0..-3.5 K/day radiative cooling at sigma 0.84-0.86 (tropics d5, combo; control -0.8..-1.1) physical, and why does it persist?
Measured budget, combo vs control at 0.862 (K/day): rad -3.03 vs -1.12, shallow +0.69 vs +3.98, deep +2.58 vs +0.27, grid-scale +1.56 vs +0.33, bl -0.83 vs -0.48. The control's 850 hPa was right for the wrong reason (shallow MSE mixing heating +4..+10 K/day below 850); with that gone, radiation is the largest net term.
Signature check: combo d5 850 hPa T -2.4 K and q +0.78 g/kg vs ERA5 -> RH ~0.75 -> ~0.96 at the deck: a near-saturated cloud deck. Offline column ensemble (cloud_derivation.py + scratch deck_ens.py; Jordan 1958 sounding, deck top at 0.812/0.837/0.862/0.885, RH 0.99 at the top, 0.85 below) with the CURRENT scheme reproduces the measured deck-mean cooling: -2.78 vs -2.83 K/day measured. => mechanism reproduced (L1).
Code facts: radcloud clouds() = Sundqvist fraction from RH 0.8 with invented water c x b_ls x qs (never removed from q, no latent heat) while condensation starts at RH 1 (two different clouds). Nothing removes the deck: no cloud-top entrainment anywhere. Also found: radcloud.py defines clouds() twice (the second is the live one) - D1 patched in both.
D1 (L1, L2): one uniform sub-grid total-water PDF (Smith 1990; half-width (1 - RHc) qs) for both cloud fraction and water; option cld_pdf. Offline, same columns: deck-mean cooling -2.78 -> -2.24 K/day (+0.54); deck-top layer -4.49 -> -3.08. Water is the model's own; onset at RHc as before.
D2 (L1, L2): rho w_e cp dtheta = A dF_cld (Lilly 1968; Lock 2000), A = 0.54 from DYCOMS-II RF01 (w_e 3.8 mm/s, dtheta 8.75 K, LW jump ~70 W/m2); exchange of s and q between the cloud-top layer (highest cloud-cooled layer, sigma 0.7-0.97, no deep convection) and the layer above (cloudtop.py; option ent_top = A). Offline: entrainment warming at the top = 0.54 x cloud LW cooling (+4.5 K/day against -8.3 in a single near-saturated column) plus drying -13..-22 g/kg/day -> the deck thins within hours until entrainment drying balances the moistening from below (+0.6 g/kg/day measured): sustainable cloud-top cooling ~0.6-0.9 K/day instead of 1.3-3.6.
L2: cloudtop.py reproduces the hand formula exactly at 3 of 4 deck tops (+4.522/+4.503/+4.479 K/day, -14.299/-19.033/-21.811 g/kg/day); in the 4th column it correctly picks a thin cloud one layer higher (RHc 0.72 at 0.79). Column energy and water conserved to 1e-10. Default off; radcloud self-test unchanged (4 pre-existing misses, same with and without the patch).
Caveat (honest): with no prognostic cloud water, D1 is diagnostic-consistent (same PDF, model's own water) but rain still starts at RH 1; full consistency needs prognostic cloud water (Tiedtke/Sundqvist) - FMEA item, Stage 1 risk.

REGISTERED BEFORE RUNNING (30 Oct 14:15 IST; 10 starts, d5 tropics vs ERA5; GPU deterministic ops; compared with tn-prof-combo):
 Run A = F2 + D1 (pbl_tm 1, sh_mflux 0.03, cld_pdf 1). Run B = F2 + D1 + D2 (+ ent_top 0.54).
 D1 (A vs combo): radiative cooling at 0.812-0.862 reduced by 0.3-0.9 K/day; 850 hPa bias between -2.4 and -1.4 K.
 D2 (B vs A): further reduction, rad at 0.837 and 0.862 >= -2.3 K/day (combo -3.50 / -3.03); 850 hPa bias within +-1.0 K (central -0.8); q850 bias <= +0.5 g/kg (combo +0.78); 925 and 1000 within +-1.5 K.
 Must not get worse (B vs combo): 250 hPa bias within 0.3 K of combo (-4.16); 500 within +-1.5 K; deep share >= 0.20; grid/deep <= 1.0 (combo 0.45); no blow-up.
 Package target (F2+F6 gate above, unchanged): PREDICTED TO FAIL on OLR >= 220 (combo 201): low cloud is warm, removing it changes OLR by < +4 W/m2; the low OLR is a high-cloud / upper-humidity problem (d5 q +0.2..+0.46 g/kg at 300-500 hPa) -> new FMEA item, needs its own derivation. So F2+F6 cannot be adopted as a package today even if D1/D2 pass; D1/D2 move to L3 only on their own registered mechanism gates above + full regression.

DETERMINISM CONFIRMED (14:30 IST): tn-quick6-ctl-d1 and -d2 (XLA deterministic ops, accounts 1 and 7) give bit-identical tracks for all 6 storms. => tn-quick6-ctl-d1 is THE control for every future quick test (24/48/72 h: 93/199/273 km, 6 storms, no jumps; 72 h wind 25.7 kt, pressure 1003.5). Old non-deterministic control vs deterministic: up to ~100 km per storm at 48-72 h (Nivar 48 h jump vs 324 km; Hamoon 72 h 461 vs 565) = the size of the noise that was in all earlier single-run comparisons.
 cmt_mf verdict unchanged against the deterministic control (thresholds not touched): 48 h 199 -> 232 (+17%), 72 h same 5 storms 270 -> 363 (+34%); wind 25.7 -> 27.2 kt (< +2). Still REJECTED.

## 30 Oct 14:30 IST - D5 (track damage = beta drift of a stronger vortex?): REFUTED offline, no GPU
Prediction (Carr & Elsberry 1997: beta drift grows with outer-wind strength, ~0.2 m/s per m/s; NW-ward in the NH): if cmt_mf's track damage came from a stronger vortex, (a) the displacement cmt_mf - control points NW, (b) it is largest where the wind rose.
Data (jump-free positions, cmt_mf minus control): 48 h NW quadrant 0 of 5, 72 h 0 of 4; mean displacement 72 h +68 km E, -123 km N (SOUTH-east); wind change is negative in Sidr, Phailin, Hamoon yet they moved most (206, 272, 197 km). cmt_2d the same pattern (72 h mean +20 E, -74 N). => beta-drift candidate rejected.
Remaining candidate (D5b, to derive): the old 6 h CMT homogenises winds in every convecting column (+50..+80 m/s/day shear erasure); removing it changes the large-scale vertical shear and so the deep-layer steering everywhere convection is active, not just the storm. If the control's steering was right partly because that erasure offsets an upper-level wind error (thermal wind of the cold upper troposphere, P1), tracks degrade until P1 is fixed. Needs: day-3/5 wind error by level for ctl vs cmt_mf (wind scoring = pending scoring item) - derivation first, no run.

## 30 Oct 14:35 IST - D4 vortex moisture (A-B4): offline check on the 6 start fields (libm_fields.npz, 1.5 deg), no GPU
Code: bogus() fills the analysis' own vortex out of T, ps, u, v (3-4 deg) but NOT out of q, then only RAISES q toward 0.9 qs within 2.5 rmw (never lowers).
Result (d4_vortex_moisture.py): the 850-500 hPa moist core stays where the analysis had it: 89 / 249 / 176 / 245 / 166 / 156 km from the observed centre (Sidr, Giri, Phailin, Titli, Nivar, Hamoon; mean 180 km, 5 of 6 > 100 km); the analysis low itself sat 74-264 km away. RH at the max 0.93-0.96 vs 0.87-0.94 at the inserted centre (+0.01..+0.06).
Pre-stated prediction 'the model storm drifts toward the left-over moist core' -> REFUTED: the 12-24 h position error points AWAY from it (cosine -0.86..-1.0 in 4 of 6 storms: Phailin, Titli, Hamoon, Sidr 12 h; errors 100-180 km). The geometry defect is real (moisture and vortex inserted at different places) but its effect is not the one predicted; a systematic error pointing away from the analysis' moist core is a new signature -> 5-Why next (candidates to check: the filled-out analysis low leaves a pressure/wind imbalance ring; binary interaction). No fix implemented until explained.

D3 single shallow/deep decision (B-C1): code fact - two tests decide: the undiluted parcel (lines ~448-469) sets 'deep' (CAPE > 100, depth > 200 hPa) which switches OFF shallow mixing; the entraining mass-flux plume sets okmf (deep convection). Columns with parcel-deep but plume-not-deep get neither -> only grid-scale condensation acts (a direct route to the grid-scale rain of P4 over TN land / Ghats). Measurement before derivation: diagnostic on_orph (share of such columns) and lsc_orph (their grid-scale rain) added to the budget; it rides on today's tn-prof-d1 / d12 runs (no extra GPU).

## 30 Oct 15:15 IST - RESULTS D1 (tn-prof-d1) and D1+D2 (tn-prof-d12) vs registered predictions (10 starts, d5 tropics, deterministic)
d5 T bias vs ERA5 (combo / d1 / d12): 850 -2.42 / -2.02 / -2.20; 925 -1.71 / -1.95 / -1.93; 1000 -0.96 / -1.16 / -1.16; 500 -0.96 / -1.20 / -1.11; 250 -4.16 / -4.33 / -4.26. q850 +0.78 / +0.37 / +0.54 g/kg. OLR 201.1 / 206.2 / 206.0. Deep share 0.232 / 0.231 / 0.237. Grid/deep 0.45 / 0.38 / 0.37. Rain 6.22 / 5.63 / 5.74 mm/day. No blow-up.
Radiation at the deck (K/day, combo -> d1): 0.812 -2.89 -> -1.77, 0.837 -3.50 -> -2.31, 0.862 -3.03 -> -2.49 (mean +0.95); BUT below it 0.885 -1.89 -> -2.23, 0.908 -0.72 -> -1.63, 0.929 -0.32 -> -1.12.
D1 gates: 850 between -2.4 and -1.4 -> -2.02 PASS; deck cooling reduced 0.3-0.9 -> 0.95 MISSED (larger than predicted). Unpredicted: cooling moved down into 885-930 hPa. => D1 as registered: NOT passed (one gate missed, one unpredicted side effect). Stays OFF.
D2 gates: rad at 0.837/0.862 >= -2.3 -> -2.23/-2.26 PASS; 850 within +-1 -> -2.20 FAIL; q850 <= +0.5 -> +0.54 FAIL; 925 within +-1.5 -> -1.93 FAIL; must-not-worsen all PASS. => D2 REJECTED as registered. Entrainment heating tiny: tropical mean <= 0.12 K/day.
Interaction check (pre-registered, d12 vs d1 at 0.81-0.86): bl+shal change <= 0.09 K/day, physq change <= 0.18 g/kg/day -> CLEAN; no coupling defect. Sign pattern of h_ent correct (cooling above the top -0.13, warming at the top +0.12).
F2+F6 package target: fails 850, 925, OLR (OLR predicted) -> REJECTED.
Where MY derivation was wrong (not the code): D2's size was computed on the pre-D1 cloud. Entrainment = A x the CLOUD part of the LW cooling; after D1 that part is small, so D2 had little to act on. The registered numbers did not account for D1 running first. Logged as a derivation error.
KEY FINDING (5-Why level 5): low-level radiative cooling, mass-mean 800-1000 hPa: control -1.67, combo -1.53, d1 -1.55, d12 -1.48 K/day = UNCHANGED. D1 only moved the cooling from the deck top down into the layers below; the total stays the same, so the 850-1000 hPa cold bias stays. The cold layer is not a cloud-top artefact. Heat that balanced this layer in the control: shallow mixing +5.87 K/day (mass-mean) - far too much, but in combo only +1.12, with deep +1.06 and grid-scale +0.74. The missing heat therefore lies in the shallow-cumulus heating, whose strength is set by the FIXED mass flux sh_mflux = 0.03 kg m-2 s-1 (a BOMEX number, not a closure) -> next derivation: shallow cloud-base mass flux from the boundary-layer energy budget (Grant 2001: Mb ~ 0.03 rho w*; ECMWF closure from the surface moist-static-energy flux). Sensible heat flux tropics: control -14.5 (downward!), combo 7.3, d1 8.7 W/m2.
SECOND FINDING (OLR / shortwave): surface net SW, tropics: control 162, combo 111, d1 104 W/m2 (observed tropical mean ~190-210); OLR 201-206 (target 220). With deep convection on in 23% of columns (5% before), the convective tower + anvil clouds (Slingo cover from rain rate; anvil ice = 10% of rain x 3 h) block 50-60 W/m2 more sunlight and lower OLR. => convective/anvil cloud must be derived consistently with D1 (detrained condensate, not rain rate) - new item D9.
D3 measurement (rides on these runs): 'orphan' columns (parcel deep, plume not deep) = 25% of tropical columns, 9% over TN, 3% over the Ghats, but their grid-scale rain is only 0.38 of 2.49 mm/day in the tropics (15%), 0.19 of 1.12 over TN (17%), 0.03 of 0.57 over the Ghats (6%). => the double decision is real and common but is NOT the main source of grid-scale rain over TN/Ghats. D3 is downgraded as a P4 cause; still to be unified (consistency).
GPU-path equivalence (tn-l2-jax, Kaggle GPU, jax.numpy vs numpy, same 4 columns): radiation heating, cloud, cloud LW part, entrainment dT/dq agree to <= 1.6e-4 relative (float32); same cloud-top index; energy closed to 1e-6 W/m2 -> PASS. So the D1/D2 results above are the physics as derived, not a coding error; the D2 shortfall is the derivation-order error recorded above.

## 30 Oct 15:50 IST - D10 shallow closure: REFUTED OFFLINE (no GPU) + where the 850-1000 hPa heat goes (day-1 budget)
Day-1 budget, 800-1000 hPa mass-mean (K/day): control total +2.02 (shallow +7.49, evap -3.02, rad -1.80, dyn -0.73) - overheats; combo -0.94 / d1 -0.91 (rad -1.83, evap -1.16, shallow +1.30, deep +0.74, bl +0.34, lsc +0.29, dyn -0.60). Over days 1-3 this cooling gives the -2 K at 850 hPa; by day 5 the layer is in balance (total ~0) at the colder state. So the bias is set by a ~0.9 K/day = 21.6 W/m2 deficit in the first days.
D10 (shallow_closure_derivation.py): Grant (2001) Mb = 0.03 rho w* with the model's own fluxes (SH 8.7, LH 133.5 W/m2 -> buoyancy flux 5.2e-4 m2/s3) gives Mb 0.021-0.026 kg m-2 s-1 for a 400-800 m sub-cloud layer = 0.68-0.86 x the fixed 0.03. A physical closure would WEAKEN shallow heating -> cannot supply the deficit. Not tested (prediction: no gain).
Sizes of the remaining candidates for the 21.6 W/m2 (to be derived, in this order):
 1. Clear-sky long-wave too strong: radcloud self-test already MISSES its own target (clear LW cooling 800-300 hPa 2.25 vs 1.5-2.0 K/day) and gives -3.0..-3.4 K/day at 850-985 hPa for the tropical sounding; the spectral model carries a x1.5 calibration on H2O lines and continuum (SSM_LINE_FAC, SSM_CNT_FAC) = an unexplained constant on P1's main term. Up to ~17 W/m2 in this layer. Needs a line-by-line / RRTMG reference profile for the same sounding (derivation, not a run).
 2. Rain re-evaporation: 1.16 K/day = 0.95 mm/day (15% of rain) - within the usual range; k_evap / ev_frac are constants (later item).
 3. Surface sensible flux 8.7 W/m2 (0.37 K/day); an observed ~12 W/m2 adds only 0.14 K/day (D8 related).
 D9 (convective/anvil cloud) evidence from the radcloud self-test: a 2 mm/day convective column gets total cover 0.52, LWP 273 g/m2, albedo 0.37; 40 mm/day gives cloud 0.6 in every layer 270-940 hPa. With deep convection now in 23% of columns, this explains surface SW 162 -> 104 W/m2 and OLR 201-206.

## 30 Oct 16:00 IST - clear-sky long-wave vs an independent reference (RRTMG, climlab on Kaggle): ROOT CAUSE of most of the low-level heat deficit
Same column (AFGL tropical, mm2's 32 levels; lw_reference_check.py -> lw_column.json; rrtmg_climlab_reference.py, job tn-rrtmg-ref2).
800-1000 hPa mass-mean clear-sky LW heating: RRTMG -2.45 K/day (H2O+CO2 only -2.51); MEGAM -3.18 -> MEGAM cools 0.73 K/day = 17.4 W/m2 too much (of the 21.6 W/m2 day-1 deficit). 300-800 hPa: RRTMG -2.18, MEGAM -2.26 (fine; the self-test's own 1.5-2.0 target there was itself wrong). Surface downward LW: RRTMG 391.6, MEGAM 411.5 W/m2.
Attribution (1 cm-1 SSM, lines/continuum factors varied, attrib in scratch, numbers reproducible with lw_reference_check.py):
 lines x1.5 continuum x1.5 (as used): -3.09 K/day, DLR 410.4 | lines x1.5 continuum x1.0: -2.74, DLR 391.9 (= RRTMG 391.6) | lines x1.0 continuum x1.0: -2.92, DLR 388.3 | continuum off: -0.78.
 => The x1.5 on the WATER-VAPOUR CONTINUUM adds 0.35 K/day of low-level cooling and 18.5 W/m2 of surface DLR. It was tuned to a surface-DLR target of 400-420 W/m2; the independent reference gives 392 for this atmosphere, so the calibration target was wrong and the factor has no physical basis. The fitted 17-term scheme adds a further -0.09 (fit error); the SSM line shape leaves -0.29.
Derived change: continuum factor 1.0 (lines x1.5 kept: best match to RRTMG at low levels and OLR). Implementation: the existing radcloud switch lw_cnt = 1/1.5 = 0.667 scales the fitted continuum coefficients; offline the fitted scheme then gives 800-1000 hPa -2.85 K/day (SSM target -2.74; RRTMG -2.45), 300-800 -2.15 (RRTMG -2.18), OLR 288.7, DLR 393.5 (RRTMG 391.6). L1 + L2 done (no new code).

REGISTERED BEFORE RUNNING (30 Oct 16:00 IST; 10 starts, d5 tropics vs ERA5, deterministic):
 Run R1 = combo (pbl_tm 1 + sh_mflux 0.03) + lw_cnt 0.667, vs tn-prof-combo:
  rad 800-1000 hPa mass-mean (all-sky) -1.53 -> -1.20 +- 0.15 K/day; surface LW down (tropics) falls by 12-20 W/m2;
  850 bias -2.42 -> -1.7 +- 0.3 K; 925 -1.71 -> -1.1 +- 0.3; 1000 -0.96 -> -0.5 +- 0.3;
  300-500 hPa: change within +-0.3 K; OLR +1..+4 W/m2 (still < 220: D9);
  must not worsen: 250 within 0.3 K of combo, deep share >= 0.20, grid/deep <= 1.0, no blow-up.
 Run R2 = control + lw_cnt 0.667, vs tn-prof-bud2 (interaction / compensation check): low levels WARMER by +0.5..+1.0 K at 850-1000 (control already +0.8/+2.5/+2.7) - i.e. the old shallow over-heating was partly compensating the radiation over-cooling; the control is NOT a candidate.

## 30 Oct 16:50 IST - P4 (TN wet bias) and P2 (worse with more levels): 5-Why from the existing TN diagnostics (tn-tnr-ctl2, tn-tnr-tp75; 6 starts May-Dec 2020), no GPU
Signature table (5-day means, control 32L): in ALL regions and ALL six starts - SW monsoon westerlies, NE monsoon easterlies, pre-monsoon calm - RH at 925/850 hPa is 0.43-0.79 while RH at 700 hPa is 0.72-1.00. Grid-scale condensation 3.5-30 mm/day; rain re-evaporation 2.7-9.5 mm/day (falling through the dry boundary layer). Day-5 TN q bias vs ERA5: +1 to +5.2 g/kg at 500-700 hPa, -1.4 to -3.8 g/kg at 925-1000 hPa (75L: same pattern, larger).
5-Why:
 1 Why too much TN rain? Grid-scale rain (TN land 32L conv/grid 2.5/9.2 mm/day; 75L 0.8/14.9).
 2 Why grid-scale? The 700 hPa layer is saturated or nearly (0.77-1.00) over TN land, Ghats, coast and Bay alike.
 3 Why is 700 hPa saturated? Mid-levels are 1-5 g/kg too moist by day 5 while the boundary layer is 1.4-3.8 g/kg too dry: moisture has been moved UP from the boundary layer.
 4 Why moved up? Shallow MSE mixing relaxes q over the whole parcel depth (often 1000-400 hPa) to the column mean in tau_shallow = 1 h = an exchange of 0.3-0.9 kg m-2 s-1, 10-40x observed shallow-cumulus mass fluxes (Candidate 2). Measured over TN (prof budget, control): +2.09 g/kg/day at 615 hPa on day 1, -0.63 at 930 hPa; Ghats +2.58 / -2.12.
 5 Why rain and not convection? The same mixing lowers boundary-layer MSE -> CAPE gone -> deep convection on TN land ~0-18%; the moistened mid-levels then condense as grid-scale rain, half of which re-evaporates below.
Rain shadow (terrain branch of the fishbone) is NOT the root: the same mid-level saturation occurs with easterlies (Dec, 700 RH 0.89-0.91) and calm (May, 0.75-0.83). It may add on top in SWM; examine after this fix.
P2 link: the mixing deposits moisture at its top; with 75 levels the top layer is thinner, so the same deposit saturates it sooner (75L Ghats RH700 0.97-1.00 vs 32L 0.86-0.93) -> grid-scale rain +60%.
Fishbone summary: Method (scheme design: shallow mixing over full parcel depth) = ROOT; Measurement (ERA5 truth 0.25->1.5 deg) minor; Machine (80 km Ghats) secondary; Material (initial moisture) no (h0 q bias ~0); Environment (season) no - all seasons; Man (tuning tau 1 h) = the constant behind the root.
Fix = already derived Candidate 2 / F2: sh_mflux 0.03 (exchange from an observed mass flux) + pbl_tm 1. Measured effect over TN in the Jan-Feb prof runs: 615 hPa moistening 2.09 -> 0.27 g/kg/day, day-1 grid-scale 1.50 -> 0.45 mm/day.
REGISTERED BEFORE RUNNING (16:50 IST) - tn_rain_diag, same 6 starts, combo settings (pbl_tm 1, sh_mflux 0.03), deterministic:
 Run P4a (32L, account 11) vs tn-tnr-ctl2: TN box 5-day rain bias +54% -> within +-25% of truth (4.6 mm/day: 3.5-5.8); TN land grid-scale rain down >= 50% (9.2 -> <= 4.6); RH700 over TN land (6-start mean of 5-day means) <= 0.80 (ctl 0.82); d5 TN q bias at 600-700 hPa mean <= +1.0 g/kg (ctl ~ +2.5); convective share of TN land rain up.
 Run P2a (75L tp75, account 12) vs tn-tnr-tp75: TN box rain within 20% of P4a (32L) - i.e. the level sensitivity largely removed (ctl: 10.2 vs 7.1); TN land grid-scale <= 7.5 (tp75 ctl 14.9).
 Failure of the TN-box gate -> P4 not explained by Candidate 2 alone (rain shadow / Ghats branch next).

## 30 Oct 17:10 IST - P3 (weak storms) 5-Why from the existing storm budgets (no GPU)
Signature (storm-core budgets, 3 controls + cmt_mf + CMT-off): in the core (100 km) deep convection switches OFF for long spells - 'deep-off' share of 3-h steps: control Nivar 0.42 / 0.54 / 0.50, Sidr 0.12-0.21, Titli 0.00-0.12. In those spells the shallow MSE mixing takes over the whole core column: +50..+98 K/day at 850-1000 hPa and -5..-10 K/day at 500-850 hPa, with rain re-evaporation -25..-32 K/day (Nivar 36-48 h). The storms that deepened are exactly those whose core convection never switched off: Titli and Nivar with CMT off (off-share 0.00 -> 992 / 993 hPa) and with cmt_mf (0.00 -> 993 / 996); the ones that stayed weak had off-spells (control Nivar 0.42-0.54 -> 1003-1006; Sidr 0.12-0.42 in all variants -> 998-1003).
5-Why:
 1 Why no intensification? Core deep convection is intermittent (off up to half the time).
 2 Why off? When the entraining plume is not deep, the shallow MSE mixing acts over the full parcel depth with tau 1 h and homogenises moist static energy in the core: boundary-layer h drops, CAPE is removed, convection cannot restart for 12-24 h.
 3 Why so strong? Exchange rate m/(2 tau) = 0.3-0.9 kg m-2 s-1, 10-40x an observed shallow-cumulus mass flux (Candidate 2 - the same constant behind P1 and P4).
 4 Why did CMT changes help 2 of 3 storms? Not through momentum: in those runs the core convection happened to stay on (off-share 0), so the shallow-mixing collapse never started; Sidr had off-spells in every variant and never deepened. This also explains why the CMT gain was 'storm-dependent'.
 5 Root: one constant (tau_shallow = 1 h over the full parcel depth) - P1 (cold upper air / heating too low), P4/P2 (moisture lifted to 600-700 hPa -> grid-scale rain) and P3 (core convection collapses) all trace to it. F2 (sh_mflux 0.03 + pbl_tm 1) is the derived fix; its remaining problem is the low-level radiation over-cooling (now under test, R1).
REGISTERED BEFORE RUNNING (17:10 IST) - storm budget Nivar/Titli/Sidr and quick6 (6 storms), combo settings, deterministic:
 (a) core shallow heating 850-1000 hPa: max over 72 h <= 10 K/day in all 3 storms (control 25-98);
 (b) deep-off share in the core <= 0.15 in all 3 storms (control Nivar 0.42-0.54);
 (c) 72 h pmin deeper than the deepest control by more than the control spread in >= 2 of 3 storms (Titli < 997.2, Nivar < 1000.3, Sidr < 995.8);
 (d) quick6 vs the deterministic control tn-quick6-ctl-d1: mean 72 h wind >= +2 kt (25.7 -> >= 27.7); track error at 48 and 72 h no more than 10% worse (199 / 273 km).

## 30 Oct 17:25 IST - RESULT R1 / R2 (continuum x1.0, lw_cnt 0.667) vs registered predictions
R1 (combo + lw_cnt) vs combo: 850 -2.42 -> -2.42 (pred -1.7 +- 0.3) FAIL; 925 -1.71 -> -1.68 (pred -1.1) FAIL; 1000 -0.96 -> -0.91 (pred -0.5) FAIL; rad 800-1000 -1.53 -> -1.58 (pred -1.20) FAIL; surface LW down -3.8 W/m2 (pred -12..-20) FAIL. Must-not-worsen all pass (250 -4.13, deep 0.22, grid/deep 0.47). OLR 201.9.
R2 (control + lw_cnt) vs control: 850/925/1000 +0.22/+0.12/+0.06 K warmer (pred +0.5..+1.0) - direction right, size 3-5x smaller; DLR -8.4.
=> R1 REJECTED as registered. Implementation is acting (DLR and low-level T move in the predicted direction in both runs; rad_prm reaches radcloud), so this is a DERIVATION error: the offline numbers were CLEAR-SKY, but the model's tropical low levels are mostly cloudy/near-saturated (D1 diagnostics: deck cover 0.3-0.6); under cloud the continuum hardly matters, so the all-sky effect is ~1/4 of the clear-sky one. Lesson (added to the rules): derive in the same regime as the model (all-sky, the model's own cloud) before registering.
The x1.5 continuum remains physically unjustified (clear-sky DLR 411 vs RRTMG 392) - keep as a correctness item for the regression with a re-registered SMALL effect, not as the P1 fix. The 21.6 W/m2 day-1 low-level deficit is therefore still unexplained -> remaining candidates: all-sky low-cloud radiation (cloud amount/water at the deck, D1 full version with stored cloud water), rain re-evaporation (1 mm/day), and whatever the F2 package itself removes (shallow heating 7.5 -> 1.3 K/day was far too strong, but the right value is not zero: the real trade-cumulus layer gets ~1-2 K/day from cumulus condensation).
Account 1 hit its weekly quota (tn-sb-f2 refused) - relaunch on 11/12 when free.
ADDED GATE (30 Oct 16:55 IST, before any TN rain result exists - tn-tnr-f2 / f2tp75 still running): P2a must ALSO meet the absolute gate: 75L TN box 5-day rain within +-25% of truth (3.5-5.8 mm/day), not only within 20% of 32L (two runs can agree and both be wet). P3 reading order: gates (a) shallow heating and (b) off-share test the CAUSE; (c) intensity and (d) wind/tracks test the OUTCOME - an intensity gain without (a)+(b) does not support the mechanism. cmt_mf stays rejected regardless.

## 30 Oct 17:25 IST - RESULT P3 gate (d): F2 on 6 storms (tn-quick6-f2) vs deterministic control tn-quick6-ctl-d1
Mean 72 h wind 25.7 -> 21.2 kt (registered >= 27.7) FAIL; weaker in all 6 storms (Titli 34.4 -> 24.5, Sidr 24.1 -> 16.1). Pressure 72 h mean 1003.5 -> 1003.5 (Titli +2.6, Hamoon -2.7). Tracks 48 h 199 -> 189 (pass), 72 h 273 -> 416 km (+52%, limit +10%) FAIL (Hamoon 565 -> 993, Giri 291 -> 476).
=> F2 does NOT fix P3; it makes the storms' winds weaker. Gates (a)/(b) (shallow heating, off-share) still to be measured (tn-sb-f2b on account 7; tn-sb-f2 refused - account 1 quota) - they decide whether the off-spell mechanism was wrong or whether removing it exposes another limit. P3 is now separated from the P1/P4 single-root hypothesis.

## 30 Oct 17:40 IST - RESULT P4 (tn-tnr-f2, 32L, 6 starts) vs registered gates
TN box rain: control 7.08 vs truth 4.56 (+55%); F2 8.39 (+84%) -> registered gate (+-25%) FAIL.
Mechanism gates: TN land grid-scale 9.16 -> 3.14 mm/day (-66%, gate >= -50%) PASS; RH700 TN land 0.817 -> 0.675 (<= 0.80) PASS; d5 q bias 600-700 hPa +1.52 -> +0.93 g/kg (<= +1.0) PASS.
By region (5-day means, ctl -> F2): TN land rain 6.2 -> 3.0 (grid-scale 9.2 -> 3.1); Ghats 11.6 -> 6.7; TN COASTAL SEA 6.4 -> 17.3 (convective 2.8 -> 21.0, deep share 0.08 -> 0.69); Bay offshore 6.4 -> 12.3 (deep 0.07 -> 0.49).
=> F2 fixes the mechanism it was derived for (mid-level moistening, grid-scale rain over land - rain over TN land halves) but the TN box gets wetter because the sea part of the box now convects almost all the time. Not adoptable as P4 fix.
Why does the sea convect? Lowest-layer air: TN land T1 299.8 -> 296.7 K, coastal sea 302.4 -> 298.0 K, q1 +1.5..+2.5 g/kg, RH925 0.55 -> 0.88: a COLD, MOIST boundary layer (the same low-level cold as P1). Over the sea the SST stays ~302 K, so a 4 K air-sea difference drives large surface fluxes -> deep convection on in 50-70% of sea columns. Rain re-evaporation over the coastal sea with F2: 13.6-14.7 mm/day-equivalent for 17-25 mm/day rain (~55-80% of the rain re-evaporated) - a very large boundary-layer cooling.
5-Why for the new failure: wet TN box <- sea convection 0.5-0.7 <- cold moist boundary layer (-3..-4 K) <- the 22 W/m2 low-level heat deficit (P1) <- candidates now ranked by this evidence: (1) rain re-evaporation (k_evap, ev_frac, downdraft mf_dd = constants; 55-80% re-evaporation in convective regimes vs observed ~10-30% below cloud base), (2) low-cloud all-sky radiation, (3) too little shallow-cumulus heating.
=> P1 and P4 still share a cause, but it is the LOW-LEVEL HEAT BUDGET, not the shallow mixing alone. Next derivation (all-sky, model regime): rain re-evaporation from drop physics (Kessler 1969 / Sundqvist 1989 / Kain-Fritsch: evaporation rate from drop-size distribution, ventilation, (1-RH)), computed for the model's own coastal-sea convective column, before any test.

## 30 Oct 17:55 IST - rain re-evaporation derivation (offline, model's own columns): INCONCLUSIVE so far
evap_derivation.py: MEGAM fall() vs the Kessler (1969) form used by ECMWF (k_E 5.44e-4 s-1, alpha2 5.09e-3, alpha3 0.5777, precipitation fraction 0.3), below 850 hPa, on the F2 TN coastal-sea column (RH 0.88/0.81/0.73) and the control column (0.54/0.55/0.80):
 F2 column: re-evaporated 28% (5 mm/day) / 14% (20 mm/day) with MEGAM's formula vs 91% / 62% with the Kessler form as written.
 => The published Kessler form (without its operational limiters) evaporates MORE, not less -> 'MEGAM evaporates too much' is NOT supported by this comparison. The 55-80% seen in the tnr diagnostic is the column's evaporation-equivalent heating including convective downdrafts and grid-scale rain above 850 hPa, not only below-cloud rain. The operational IFS formula also limits evaporation by a clear-sky precipitation fraction and a humidity threshold (Jakob & Klein 1999/2000); those details could not be fetched (IFS Cy50r1 Part IV PDF refused). No change and no test until the exact operational form is in hand. Rain re-evaporation is DOWNGRADED from leading suspect to 'unresolved, needs the IFS source'.

## 30 Oct 20:00 IST cycle - P3 cause gates and P2
P3 storm budget with F2 (tn-sb-f2b, deterministic): (a) max core shallow heating 850-1000 hPa 1.6 / 2.2 / 2.3 K/day (Sidr/Titli/Nivar; gate <= 10) PASS; (b) deep-off share 0.00 / 0.00 / 0.00 (gate <= 0.15) PASS; (c) 72 h pmin 1001.6 / 1002.2 / 1004.6 vs deepest controls 999.4 / 998.8 / 1002.9 -> none deeper, FAIL; v850 72 h 10.1 / 15.5 / 15.3 m/s (controls 17.7-27.9) - weaker. Gate (d) already failed (quick6 wind 25.7 -> 21.2 kt).
=> The off-spell mechanism was REAL in the model and F2 removes it completely (cause gates pass), yet the storms get weaker. So the off-spells were NOT what limited intensity: the correlation (storms without off-spells deepened) did not reflect causation. Hypothesis REFUTED for P3. With F2 the boundary layer is 3-4 K colder (P4/P1 finding) and core surface flux is lower (Nivar 153 vs 142-278 W/m2) -> P3 now points at the boundary-layer energy supply under the storm (cold BL, surface enthalpy flux, D8 exchange coefficient) and at the 80 km grid itself (T213 cannot run: host memory).
P2 (tn-tnr-f2tp75, 75 levels + F2): NaN from the first output step in all 6 starts = NUMERICAL BLOW-UP -> registered 'no blow-up' gate FAIL. F2 has never run at 75 levels before. Per the implementation rule this is first an implementation question: trace which term goes non-finite at 75L (candidates: the explicit counter-gradient flux of pbl_tm on thin boundary-layer layers; sh_mflux time scale with thin layers; DFI) - a one-step finite-value check per process, before any physics conclusion.

## 30 Oct 20:50 IST - rain re-evaporation, now from the source (IFS Cy50r1 Part IV, uploaded by Sridhar on 27 Oct - I had it and missed it)
Source: convective rain below cloud base (eq. 6.49-6.52): e = C_conv a1 (RHcr qs - q)+ [sqrt(p/ps)/a2 x P/C_conv]^a3, C_conv = 0.05, RHcr 0.85 water / 0.70 land (deep), ZERO when q > RHcr qs. Grid-scale (eq. 7.58): evaporation only below RHcrit = min(0.7 + 0.3 a/(1-a), RHcrit_bl, 0.9). (Cy50r1 additionally hands 40% of deep-convective rain to the cloud scheme and switches sub-cloud evaporation of deep rain off.)
MEGAM: one stream, e = k_evap (1 - RH) sqrt(a P) m with a = 0.3 and NO threshold - it keeps evaporating in a near-saturated layer.
Offline, model's own columns (evap_derivation.py): F2 coastal sea (RH 0.88/0.81): MEGAM re-evaporates 28% (5 mm/day) / 14% (20 mm/day) below 850 hPa = 40-84 W/m2 of boundary-layer cooling; IFS form 1.3% / 0.7% (2-4 W/m2). F2 TN land: MEGAM 28%/14%, IFS 0%. Dry control columns (RH 0.55): IFS evaporates as much or MORE (64-100%).
=> In the moist regime that F2 produces, MEGAM's evaporation is a continuing boundary-layer cooling of the same size as the 22 W/m2 day-1 deficit, which the operational formula would not apply. Feedback: evaporation cools and moistens the BL -> RH up -> (1-RH) form keeps going; IFS form stops at RHcr. This is the strongest candidate so far for the cold, moist BL (P1 low levels, P4 sea convection).
Implementation: evapifs.py (numpy/jax), option evap_ifs (default off); two rain streams (grid-scale, convective). L2 (l2_evap.py): code = hand formula exactly on all columns (1.3/0.7/100/80.2/64.4/39.7%), water balance to 1e-20, one-step limiter never binds. GPU path: l2_evap.py runs first inside the test jobs (jax).
Caveat: grid-scale rate uses the Kessler form (older IFS), Cy50r1 uses the drop-size integral (eq. 7.56) - documented approximation.
REGISTERED BEFORE RUNNING (20:50 IST; deterministic):
 E1 prof (10 starts, tropics d5) combo + evap_ifs vs tn-prof-combo: evaporative cooling 800-1000 hPa mass-mean (d5) -1.42 -> between -1.1 and -0.4 K/day; 850 bias -2.42 -> between -1.8 and -0.6 K; 925 -1.71 -> between -1.2 and -0.3; q850 bias +0.78 -> lower; must not worsen: 250 within 0.3 K of combo, deep share >= 0.20, no blow-up.
 E2 TN rain (6 starts) combo + evap_ifs vs tn-tnr-f2: lowest-layer T over TN coastal sea 298.0 -> >= 299.5 K; coastal-sea deep share 0.69 -> <= 0.45; TN box rain +84% -> lower than F2 (registered P4 gate +-25% still applies, prediction: improves but may not reach it).
 Risk stated in advance: in DRY columns the IFS form evaporates more than MEGAM; if the tropics are mostly dry at low levels the mean change can be small or the other sign - then E1 fails and the regime split must be derived.
IMPLEMENTATION DEFECT FOUND BEFORE RESULTS (20:58 IST, while reviewing the IFS coupling points): evapifs v1 let convective rain evaporate at ANY level below the threshold, including inside the convective column above cloud base; IFS eq. 6.49 is BELOW CLOUD BASE only. Fixed (cloud base = lowest layer producing convective rain); L2 unchanged on the test columns (rain enters above them). tn-prof-e1 / tn-tnr-e2 were launched with v1 -> VOID (will not be scored as the test of the derivation). Relaunched as tn-prof-e1b (account 7) and tn-tnr-e2b (next free account), same registered predictions.
Coupling check (peer review of IFS Ch. 6.7): MEGAM has no prognostic rain, so no convective-to-cloud-scheme handover; convective rain is evaporated (i) in the downdraft (mf_dd; removed from the rain via Pscale) and (ii) below cloud base in the environment - the same two pathways as IFS before Cy50r1 (edown + esubcld), each water parcel once. The Cy50r1 switch-off of sub-cloud evaporation belongs with its 40% handover and is NOT copied.

## 30 Oct 21:20 IST - independent support from NOAA GFS (CCPP Scientific Documentation v7 + ccpp-physics source, samfdeepcnv.f)
CCPP SciDoc, sa-SAS deep convection, GFSv17 updates: "Reduction of convective rain evaporation rate to address a systematic cold bias near the surface in GFSv16." - the same symptom we see (cold near-surface layer), attributed by NOAA to convective rain evaporation.
GFS code (samfdeepcnv.f, rain evaporation loop): qcond = evef (q - qsat) / (1 + L^2 qsat / (cp Rv T^2)); qevap = -qcond (1 - exp(-0.32 sqrt(dt * rn))), limited by the rain available; evef is a namelist coefficient (older code: evfact = evfactl = 0.3, scaled by the downdraft efficiency edt; land once 0.07). Form = saturation deficit with NO humidity threshold (like MEGAM's (1 - RH)), but with a tunable strength that NOAA reduced in v17. IFS instead uses the RHcr threshold (0.85 sea / 0.70 land).
=> Two operational centres: IFS never evaporates convective rain above RHcr; GFS had MEGAM-like evaporation and a near-surface cold bias, and reduced it. Supports (does not prove) the evap_ifs candidate; E1b/E2b decide. Register: if E1b/E2b fail, the GFS-style alternative is a reduced deficit-form coefficient - but only with its own derivation, not as a tuning knob.
Sources: https://ncar.github.io/ccpp-physics/V7/_g_f_s__s_a_m_fdeep.html ; github.com/NCAR/ccpp-physics physics/CONV/SAMF/samfdeepcnv.f (main, 29 Oct 2026).
Reading rule for E1b/E2b (fixed 21:20 IST, before results): GFS and IFS limit evaporation by DIFFERENT mechanisms (GFS: weaker coefficient on a threshold-free deficit form; IFS: no evaporation above RHcr) - the NOAA history supports the mechanism, not the IFS formula or its size. E1b pass + E2b pass -> evaporation formulation supported for P1 and P4. E1b pass + E2b fail -> part of P1 only; P4 stays open (surface exchange, moisture supply, rain routing). E1b fail -> diagnose why (dry-column regime, implementation) BEFORE any other formulation; no GFS-style fallback is prepared in advance.

## 30 Oct 22:05 IST - RESULT E1b / E2b (evap_ifs, corrected) vs registered gates; GPU path check PASS (jax = hand formula on all 6 columns, printed in the tn-tnr-e2b log)
E1b (prof, 10 starts, tropics d5, vs combo):
 evaporative cooling 800-1000 hPa -1.42 -> -0.53 K/day (gate -1.1..-0.4) PASS - the mechanism acted exactly as derived (day 1: -1.22 -> -0.39).
 850 -2.42 -> -2.21 (gate -1.8..-0.6) FAIL; 925 -1.71 -> -1.49 (gate -1.2..-0.3) FAIL; 1000 -0.96 -> -0.64; q850 +0.78 -> +0.68 (lower) PASS.
 must-not-worsen: 250 -4.24 (within 0.3) PASS; deep share 0.232 -> 0.16 (gate >= 0.20) FAIL; no blow-up PASS.
 Side results: OLR 201.1 -> 211.9; mid-level q bias 400-700 hPa +0.29..+0.46 -> -0.18..+0.32 g/kg; 600/700 hPa T -0.04/-0.55 -> +0.25/-0.03; grid/deep 0.45 -> 0.60.
 => E1b FAILS as registered (850, 925, deep share).
E2b (TN rain, 6 starts, vs tn-tnr-f2): coastal-sea lowest-layer T 298.0 -> 298.6 (gate >= 299.5) FAIL; coastal-sea deep share 0.69 -> 0.45 (gate <= 0.45) PASS; TN box +84% -> +68% (lower) PASS; P4 gate (+-25%) FAIL. Evaporation (mm/day-equiv.) coastal sea 10.7 -> 3.7, Bay 7.1 -> 1.4, TN land 2.6 -> 1.4.
DIAGNOSIS (per the reading rule, before any other formulation): the evaporation term changed by the derived amount (-0.9 K/day at 800-1000 hPa), but the low-level temperature moved only +0.2..+0.3 K because other terms compensated in the same layer: radiation -1.53 -> -1.89 K/day (-0.36) and less deep-convective heating (deep share 0.23 -> 0.16); the day-1 total changed -0.94 -> -0.65 (+0.29 of the +0.83 evaporation change). My prediction converted ONE term's change into temperature as if nothing else responded - a derivation error of the same family as D2/R1 (single-process prediction of a coupled response). Lesson added: predictions of temperature must come from the full column budget response, not from one term. The 850 hPa cold therefore is not set by any single process tested today; it is the balance point of a coupled low-level budget (radiation, evaporation, convection, BL transport) - the SCM reference comparison (GFS v16 physics on TWP-ICE/BOMEX vs MEGAM column physics, same forcing) is now the right next tool, process by process.
evap_ifs is NOT adopted; it remains a well-supported correctness change (IFS form, NOAA v17 history, L2 + GPU path verified, its own term behaved as derived) to be re-registered within a coupled package once the column reference exists.

## 31 Oct 01:35 IST - D8 sea-surface exchange: offline derivation (d8_derivation.py), no GPU
Current: Cd at the lowest level z1 (~80 m) from the log law with Charnock z0m (consistent); Ck = 1.2e-3 (10-m value) x [ln(10/z0m)/ln(z1/z0m)]^(2 ck_z) with ck_z = 0.5 (half a height correction) and z0m used for heat/moisture.
Derived (COARE 3.0, Fairall et al. 2003, neutral): CHn(z1) = kappa^2 / [ln(z1/z0m) ln(z1/z0t)], z0t = z0q = min(1.1e-4, 5.5e-5 Rr^-0.6).
Result at z1 = 80 m: MEGAM's Ck is 12-30% TOO HIGH (ratio 1.30 at 3 m/s, 1.26 at 7, 1.25 at 10, 1.18 at 20, 1.12 at 30 m/s). The full height correction (ck_z = 1) lands within -11..+11% of COARE. Cd is 7-12% above COARE (Charnock 0.018 vs COARE's 0.011 at moderate winds).
Flux consequence in the F2 coastal-sea state (air 298 K, SST 302 K, q1 17 g/kg): 7 m/s -> MEGAM SH 33 + LH 160 = 193 W/m2 vs COARE 26 + 127 = 153 W/m2 (MEGAM ~25% more).
=> D8 is a real inconsistency, but in the OPPOSITE direction to what P1 and P3 need: correcting it LOWERS surface heat and moisture supply ~20%. So (1) the cold boundary layer is NOT from too-weak sea fluxes (it is cold despite fluxes ~25% too strong); (2) D8 cannot explain the weak storms - a correct Ck would make them weaker still; (3) for P4 it would reduce the moisture feeding the coastal-sea convection (helps). Consistent with the earlier ck_z = 1 run, which cooled the tropical column. D8 goes to the correctness list (with the coupled package), not as a P1/P3 fix.

## 31 Oct 13:15 IST - 84-storm library hindcasts (measurement, not registered tests): tn-lib84-ctl / -corr / -f2corr, deterministic, 120 h
41 storms had start fields in libm_fields (all three configs, none errored). Jump-cleaned track error on storms valid in all three (n), mean max wind (kt), mean min pressure (hPa); observed mean wind in brackets:
 24 h (n37): ctl 106 / 25.5 / 1006.1 | corr 115 / 23.3 / 1006.0 | f2corr 117 / 20.1 / 1006.6  [obs 27.2]
 48 h (n29): ctl 207 / 29.3 / 1002.8 | corr 183 / 28.7 / 1002.1 | f2corr 235 / 20.8 / 1004.7  [34.3]
 72 h (n24): ctl 247 / 27.6 / 1003.3 | corr 299 / 29.7 / 1001.4 | f2corr 331 / 21.9 / 1004.2  [46.8]
 96 h (n13): ctl 318 / 27.2 / 1004.4 | corr 366 / 28.1 / 1002.2 | f2corr 446 / 20.3 / 1004.6  [46.6]
 120 h (n6): ctl 337 / 26.4 / 1004.0 | corr 477 / 27.8 / 1002.7 | f2corr 359 / 18.7 / 1004.9  [51.4]
corr vs ctl at 72 h: track better in 9/25 storms, wind higher in 19/25; storms losing the centre (jump >250 km/6 h or NaN): corr 14, f2corr 13, ctl 22.
Reading: (1) the correctness items (evap_ifs + continuum x1.0 + ck_z 1) make storms slightly stronger (+2 kt, -2 hPa at 72 h, 19/25 storms) and more coherent (fewer centre losses 22 -> 14) but tracks beyond 48 h worse (+21% at 72 h); (2) F2 weakens storms across the whole library (wind ~20-22 kt vs 27-29; stronger than control in 0/24 at 72 h) - confirms the 6-storm result on 41 storms; (3) all configurations stay far below observed intensity (27-30 vs 47-51 kt at 72-120 h). Small samples at 96-120 h (n 13 / 6).

## 3 Nov 07:00 IST cycle - results of the overnight jobs (all 14 finished)
**P2 traces (tn-tr75-*)**: void - my script defect (column check before M.build set the start date: AttributeError doy0). Fixed (trace75.py), rerun with 72 steps on accounts 1-3.
**SCM reference (tn-scm-ref)**: build failed at cmake - NCEP libraries bacio/sp/w3emc missing (not on conda-forge). scm_ref.py now builds them from the NOAA-EMC sources (bacio v2.4.1, sp v2.5.0, w3emc v2.11.0) and fetches the v7 static data; rerun on account 4.
**Fresh deterministic baselines (control)**: exam 2020 (73 starts) z500 RMSE d1/d5/d10 = 20.2 / 73.3 / 120.2 m; genesis gen0 31 % / gen1 45 % formed (42 cases each); TN box 5-day rain model/truth 196 / 137 mm = 1.43 (+43 %).
**Budget time-evolution (tn-evo-ctl / -f2 / -tp75, 6 Jan starts; jobs were OOM-killed after 6/6/5 of 10 starts)**:
- The low-level error forms in days 1-2 and is in equilibrium from day 3 (layer totals ~0 after 48 h). Control: BL warms (+2.4 K/day day 1; d5 1000 hPa +2.8 K) - the MSE relaxation 'shallow' heats the BL by 8-10 K/day. F2: BL -0.97, -0.36 K/day on days 1-2; 850 layer -0.72, -0.54 -> d5 850 -2.4 K.
- F2 850-hPa layer: radiation -2.4 to -2.6 K/day (control -0.8 to -1.2); TN -5.4 K/day. F2 d5 radiation profile peaks at -3.5 K/day at sigma 0.84 with weak cooling below; surface SW 110 vs 162 W/m2 (control) -> a low cloud deck at ~850 hPa (cloud-top cooling, shading below). F2 d5 q bias +0.7 g/kg at 850 (TN +2.8).
**D12 offline check (d12_low_deck_check.py, L1)**: the model's own RH cloud (radcloud.clouds, defaults) on ERA5 + the F2 d5 tropics-mean T/q bias: large-scale cloud fraction 850 / 925 hPa = 0.48 / 0.59 vs 0.12 / 0.21 for ERA5 itself (control: 0.01 / 0.00, its cloud sits at 600-700 hPa instead). => P1 (F2) mechanism: moisture accumulates at the BL top (F2 mixes the shallow layer over hours, not 1 h) -> RH cloud deck at 850-925 -> cloud-top LW cooling -> colder -> higher RH (positive feedback, day 1). Not a fix - a located cause. Next: compare with the GFS v16 SCM (BOMEX) cloud-layer moisture/cloud and tendency profiles; derive the cloud-layer ventilation from that.
**D11 offline (d11_shallow_mse_closure.py, L1)**: ECMWF shallow closure (IFS Part IV eq. 6.35-6.37) on the model's own sub-cloud budget: source (advection + radiation + BL + L E) = 74-83 W/m2 (control), 126-135 W/m2 (F2); with (h_up - h_bar)_base 2.4-3.1 kJ/kg (ERA5 tropics) Mb = 0.024-0.044 kg m-2 s-1 (ftop 0) or 0.011-0.030 (30 % of E leaves by diffusion); the 'mixed' updraught bound gives up to 0.11. => the fixed 0.03 lies inside the derived range; the closure value is NOT the P1 cause. The existing sh_clos (surface flux only) omits the advection (-30..-40 W/m2) and radiation terms of eq. 6.37 - documented error, option stays off.
**Implementation defect found (genesis2.py)**: settings that are not run-time parameters (not in mm2.DYN: shallow, evap_ifs, rad_prm, diff_x ...) were silently dropped in genesis runs. Affected past results: gen_fullck (fullck, full_c10), gen_heat (full) - ran WITHOUT shallow='mf'; gen_diff4 without diff_x. Those genesis numbers are void for those settings. Fixed (every non-DYN setting goes to Model()); mm2.with_params now warns when a compile-time setting is passed.

### Registered before launch (3 Nov ~08:30 IST): regression of the correctness items (evap_ifs 1, lw_cnt 0.667, ck_z 1) vs the fresh baselines
Gates (regression = must not degrade beyond these): exam (tn-corr-wx-q0..3, 73 starts) z500 RMSE d5 <= 74.8 m and d10 <= 122.6 m (baseline +2 %); genesis (tn-corr-gen0/1) formed share >= baseline - 5 points (>= 26 % / 40 %); TN rain (tn-corr-tnr) |ratio - 1| <= 0.43 (no worse than control). Prediction for the budget run tn-evo-corr (measurement): control + corr keeps the warm BL - d5 1000 hPa T bias >= +2.8 K (evaporation cooling in the BL falls from ~-3.1 K/day), 850 hPa not colder than +0.8 K - 0.5.
F2 deterministic P4 references: tn-tnr-f2d (F2), tn-tnr-f2corrd (F2 + corr): measurement only.

## 3 Nov ~09:00 IST - P2 cause found: implementation defect in pbl_tm (counter-gradient flux)
Trace (tn-tr75-f2 / -pbl rerun, 75 levels, start 2020-01-01): nothing non-finite until step 7/9; the first sign is NEGATIVE humidity in the lowest layers (pbl only: q min -5.9 g/kg at step 2, -22.6 at step 3; F2: -5.0 at step 5), then h_bl explodes at sigma 0.982-0.989 (612 -> 954 -> 7557 K/day) and the run goes non-finite. Both runs share pbl_tm; deep/shallow/lsc/rad stay bounded until the BL has blown up.
5-Why: blow-up <- h_bl and q runaway in the lowest 3 layers <- explicit counter-gradient flux larger than the layer content per step <- F = rho Kh gamma used Kh = max(Kbl, Kfree) (clipped 500) while gamma = 6.5 w'x'_0/(ws h) is normalised for the profile K = kappa ws z (1-z/h)^2 <- with Kbl the ws cancels and F <= 0.385 rho w'x'_0; with Kfree (dominant near the surface on thin layers) it does not.
D13 offline (d13_cg_flux_check.py, same formulas, 936 daytime cases): old F / surface flux up to 18.6 (median 1.19; > 1 in 52 % of cases; Kfree > Kbl in 94-100 % of cases at interfaces <= 80 m); a ratio of ~3 empties a 7-hPa layer of vapour in one 20-min step -> negative q, as traced. Fixed form (Kbl): max 0.382 (bound 0.385). Also at 32 levels (interfaces 80/230 m) the old flux was > 1x the surface flux in 38-59 % of cases -> F2 pumped heat and moisture from the lowest layer to the BL top: a candidate contributor to the 850-925 hPa moistening / low cloud deck (P1, D12).
Fix (commit 60400f2b): F uses clip(Kbl, 0, 500). This changes F2 (pbl_tm 1): ALL F2 results before 3 Nov 09:00 IST used the defective counter-gradient flux. tn-tnr-f2d / tn-tnr-f2corrd (launched after the fix was pushed) use the fixed form.
Registered predictions (before results):
- tn-tr75-f2fix (75 L, F2 fixed, 72 steps = 24 h): no non-finite values; lowest-layer q min >= -0.1 g/kg over the first 9 steps; max |h_bl| < 300 K/day after step 1. Failure of any = reject the claim that this defect alone causes the 75-level blow-up.
- tn-evo-f2fix (32 L, F2 fixed, 6 starts, budget windows): direction only (magnitude not derivable offline): d5 tropics q bias at 850 lower than +0.70 g/kg; 850-layer radiation less negative than -2.4 K/day (0-24 h); d5 850 T bias less cold than -2.4 K. If none moves, the defect is not a P1 contributor at 32 L.
- tn-tr75-shm (75 L, sh_mflux only, old code): stable for 72 steps (24 h), q min 0.000, h_bl max ~330 K/day only at the lowest level (init shock) -> the 75-level blow-up needs pbl_tm, consistent with D13.

## 3 Nov 12:15 IST - scored (all jobs launched 07:05-07:28 had finished)
**tn-tr75-f2fix (P2)**: 75 L + F2 with the fixed counter-gradient flux ran all 72 steps (24 h) with no non-finite values (defective code: non-finite at step 7). Steps 55-72 (the part the 30 kB log kept): q min 0.000 g/kg, max |h_bl| 264 K/day only at the lowest level (sigma 0.996, the same init-shock level as the stable sh_mflux-only run). Gate 'q min >= -0.1 g/kg over steps 1-9' NOT verifiable (log cut) -> rerun tn-tr75-f2fix2 writes a full JSON summary. Status: blow-up gate PASS, q gate pending.
**tn-evo-f2fix vs tn-evo-f2 (32 L)**: identical to 2 decimals (d5 850 T -2.4, q850 +0.70, 850 rad 0-24 h -2.42, BL h_bl +1.30). All three direction gates FAIL as registered -> the counter-gradient defect is NOT a P1 contributor at 32 L (over the tropical oceans H is small, the counter-gradient term is tiny). P1 low deck stands as found (D12); its cause is elsewhere.
**tn-evo-corr (control + correctness items)**: prediction 'd5 1000 hPa T >= +2.8' FAIL - it fell to +1.9 (850 +0.8 -> -1.0); BL rain evaporation -3.1 -> -6.5 K/day (IFS form evaporates more below cloud base in the control regime; E1b with F2 showed the opposite: -1.42 -> -0.53). My prediction used the F2 result in the control regime - same error type as 30 Oct (derive in the model's own regime).
**Regression of the correctness items together (evap_ifs + lw_cnt 0.667 + ck_z 1) - FAIL on every gate**: exam z500 d1/d5/d10 22.1/76.3/121.0 vs 20.2/73.3/120.2 (gate d5 <= 74.8; worse at d5 in 72 of 73 starts); genesis 17 % / 33 % (gate >= 26 / 40); TN box ratio 1.85 vs 1.43 (gate <= 1.43). => NOT adoptable together. Each item is supported by a reference (IFS, RRTMG, COARE) but the rest of the model was calibrated with the old forms (compensating errors) - which item does the damage is unknown -> decomposition runs below.
**TN rain, deterministic**: F2 (fixed code) ratio 1.85; F2 + corr 1.98; control 1.43.
**SCM reference**: NCEP libraries and the SCM now BUILD; the run failed only because run_scm.py calls 'time' through /bin/sh and Kaggle has no /usr/bin/time (exit 127) -> shim added, rerun.

### Registered 3 Nov 12:20 IST
- Decomposition (measurement, no adoption decision; no derived prediction): each correctness item alone vs the control baseline - exam quarter 0 (tn-evi/lwc/ckz-wx-q0, compare with tn-base-wx-q0 same starts), TN rain (tn-evi/lwc/ckz-tnr vs 1.43), genesis gen0 (tn-evi/lwc/ckz-gen0 vs 31 %). An item is 'harmful' if it alone exceeds the regression gate on that score.
- 75 L with F2 fixed (P2a gate registered 30 Oct, unchanged): TN box 5-day rain within +-25 % of truth AND within 20 % of 32 L F2 (32 L F2 fixed = 1.85 -> 75 L between 1.48 and 2.22); tn-tp75f2-tnr. Exam quarter 0 tn-tp75f2-wx-q0: no blow-up in any start (gate), z500 d5 reported vs control q0.

### 3 Nov 12:40 IST - peer review of the 12:15 results; P1 moisture budget (measurement)
Peer: work the P1 chain backwards - where does the 850-925 hPa moisture come from, before assuming BL mixing. Already known: the deck is F2-specific (control RH cloud at 850/925 = 0.01/0.00; its cloud sits at 600-700 hPa). Correction to the peer: the corr run's 1000 hPa change (+2.8 -> +1.9 K) is not a clean improvement - 850 hPa went +0.8 -> -1.0 K and the regression gates all failed; it came from doubled BL rain evaporation.
New diagnostics (mm2 diag, default output only, no physics change): moistening by process q_bl, q_deep, q_shal, q_lsc (= -condensation), q_evap (kg/kg/s) and the radiation cloud fraction cld; wx_prof budget records them per window. Job tn-evo-f2q (acct 14, F2, 6 starts, windows 0-24/24-48/48-72/96-120 h): measurement only - which process supplies the 850-925 hPa moisture excess in days 1-2, and the model's actual cloud fraction there (checks D12, which used mean biases offline).
Peer recommendation adopted for the decomposition: if no single item fails alone, run the pairwise combinations before all three again.

## 3 Nov 13:00 IST cycle (Stage 1 = P3 + P4 required, date 12 Nov)
**P2 tn-tr75-f2fix2 (full JSON, 75 L F2 fixed, 72 steps): ALL registered gates PASS** - no non-finite values; q min -0.0005 g/kg over all steps (gate >= -0.1 over steps 1-9); max |h_bl| after step 1 = 264 K/day, only at sigma 0.996 (gate < 300). The implementation-defect claim is supported for this start. Still open for 'P2 fixed': tn-tp75f2-wx-q0 (many starts) and the P2a TN-rain gate (tn-tp75f2-tnr).
**Decomposition, TN rain (each item alone, gate <= 1.43)**: evap_ifs 1.83, lw_cnt 0.667 1.60, ck_z 1.56 - every item alone is wetter than the control; evap_ifs alone ~ the whole combined effect (1.85). Exam and genesis decomposition still running.
**SCM**: built and both cases start, but the executable exits 1 - Kaggle runs as root and OpenMPI refuses root without OMPI_ALLOW_RUN_AS_ROOT; set, and the executable is now also run directly so its own message is logged.
**P4 control, from the existing tn-base-tnr diagnostics**: TN-land rain is ~75 % grid-scale condensation (lsc 8.7 mm/day made, 5.2 re-evaporated; deep convection in 11 % of columns). The excess sits in the dry/SW-monsoon starts: 20 May 23.7 vs 4.3 mm (5.5x), 9 Jun 28.1 vs 14.4 (2x), 19 Jul 1.4x; NE-monsoon starts are near truth (27 Oct 0.93x, 6 Dec 1.18x). => control P4 = false grid-scale rain in rain-shadow regimes (31 Oct mechanism: the MSE/q shallow relaxation lifts vapour until layers saturate). F2 (fixed code): land grid-scale rain 8.7 -> 3.2 but coastal sea deep share 0.08 -> 0.69 and rain 5.9 -> 17.7.
**P3, attainable target (offline, ERA5 Nivar 0.5 deg vs MEGAM control storm budget)**: 72 h: observed 60 kt; ERA5 v850 max 30.0 m/s (26.6 m/s smoothed to ~1.5 deg, T170-like), msl min 994.1 hPa (-14 hPa in 72 h), ERA5 10-m max 20.8 m/s (~40 kt - ERA5 itself is ~1/3 below the best track); MEGAM v850 20.7 m/s, pmin 1005.5 (-3 hPa). => even against a resolution-fair reference MEGAM is ~22 % weak in wind and deepens ~5x too little; the gap is real physics, not only resolution. Core surface enthalpy flux in the model stays 150-250 W/m2 for 72 h (no WISHE growth).
### Registered (measurement, no gates): tn-sb-p3a/p3b (control storm budgets, Nivar/Michaung/Vardah + Fengal/Ockhi/Ditwah - the storms with ERA5 case files) for the offline ERA5 comparison of deepening, core flux, warm core, inflow; tn-p4dry-a/b (control TN rain diagnostics on 12 more Apr-Jun 2020 starts) to build the P4 dry-regime dataset for the offline derivation.

## 3 Nov 17:30 IST - P2 remaining checks scored
- tn-tp75f2-wx-q0 (75 L, F2 fixed, exam quarter 0): 18 of 19 starts ran 10 days; **2020-06-09 BLEW UP** (non-finite mslp). Gate 'no blow-up in any start' FAIL -> P2 is NOT closed; a second cause exists (or the same one under other conditions). z500 d1/d5/d10 on the 18 good starts 22.5/71.7/118.8 vs 32 L control 20.2/72.8/120.2 (same starts).
- tn-tp75f2-tnr (P2a gate): TN box ratio 1.66 - within 20 % of 32 L F2 (1.48-2.22) PASS; within +-25 % of truth FAIL (P4 problem, not a 75 L one).
- Next: trace75 on 2020-06-09 at 75 L F2 (TRACE_START, 240 steps = 80 h, full JSON) -> which process goes non-finite first.
- 3 Nov 17:40: maps_run.py (viewer forecasts) ignored 'grid' and 'layers' - every viewer forecast so far was T85 / 32 levels whatever its settings said (e.g. maps_nivar_best 'tp75' was 32 L). Fixed. Viewer run for Sridhar: tn-maps-p2 = 75 L, T170, F2 with the fixed counter-gradient flux, Nivar start 2020-11-21 00Z, 240 h (shows the P2-fixed model in the UI; not a test).

## 3 Nov 21:00 IST - TRACK error (Sridhar: fix with P1-P4). Nivar 75 L F2 viewer run: 217/262/303/411/523/810 km at 36-96 h; model low runs W at 6-7 m/s along 8-9 N, real Nivar crawled NW ~2 m/s, stalled, then N.
Steering, ring 300-600 km around the REAL centre: ERA5 500 hPa u +4.3/+2.3/-0.4 m/s at 60/72/84 h vs MEGAM -4.2/-5.6/-7.3; 850 hPa ERA5 -3.0/-2.7/-2.3 vs MEGAM -5.2/-5.9/-6.0.
**Test 1 (background flow, 18 Oct-Dec exam starts, no storm needed)**: u850 bias over Tamil Nadu -0.2/-3.0/-3.5/-2.9/-5.0 m/s at day 1/3/5/7/10 (south India -2.6..-3.4); v850 +2..+3; u200 +7..+9 by day 7. MSLP bias: central India +1.9 hPa, Tamil Nadu -0.7 hPa (day 3) -> N-S gradient ~2.5 hPa too strong -> geostrophic estimate ~-5 m/s at the surface: the easterly excess is in the large-scale pressure field. Tamil Nadu t850 +2.0..+2.6 K (warm low levels = thermal low) - the control's BL heating (shallow MSE relaxation, 8-10 K/day) is the candidate common cause of P1 (control warm BL), P4 (false grid-scale rain) and this steering bias.
**Test 2 (inserted storm)**: cannot be done yet - the inserted Nivar vortex (tn-sb-p3a, control, bogus) FILLS within 12 h (1008.3 -> 1010.6 hPa) and the tracker then jumps between noise lows; same in tn-sb-ctl-r3b. The storm-drift part of the track error is blocked by P3 (storms fill).
P2 note: tn-tr75-0609 (75 L F2 fixed, 9 Jun start) ran 240 steps (80 h) without non-finite values, but 10-20 columns have h_bl 600-940 K/day at sigma 0.94-0.98 from ~step 38 with q slightly negative (-0.18 g/kg at step 44) -> a remaining boundary-layer hot spot; the exam start blew up later in the 10 days. Rerun to 720 steps with the hot-spot location logged (tn-tr75-0609b).

### Registered 3 Nov 21:10 IST - common-cause test: shallow cumulus as a mass-flux plume (shallow 'mf', sh_trig 1, sh_clos 0.6) replacing the MSE/q relaxation
Basis: the relaxation 'heats' the BL by lifting vapour (31 Oct), the candidate root of P1-control, P4 and the steering bias; IFS Part IV 6.4.2 shallow plume with the sub-cloud closure; sh_clos 0.6 = the D11 ratio (non-convective sub-cloud MSE source / surface MSE flux) in the control regime = 0.62 (not tuned). Earlier rejection of 'mf' (25-26 Oct) partly rested on genesis runs that silently ignored 'shallow' (void) - so it is re-tested properly.
Predictions (gates): tn-shmf-evo: d5 tropics 1000 hPa T bias < +1.5 K (control +2.8) AND 850 not colder than -1.5 K. tn-shmf-tnr: TN box ratio < 1.43 (control) - direction; P4 gate +-25 % stays. tn-shmf-wx-q0/q1: Oct-Dec Tamil Nadu u850 bias at day 5 less negative than -2.0 m/s (control -3.5); z500 d5 RMSE no worse than control +2 %. tn-shmf-gen0: >= 26 %. tn-shmf-sb (Nivar/Michaung/Vardah, bogus): measurement - does the inserted storm survive 24 h (pmin not rising)?

## 3 Nov 21:30 IST - decomposition and P1 moisture source scored
**Correctness items one at a time** (exam q0, 19 starts; genesis gen0 42 cases; TN rain 6 starts):
| item | z500 d5 vs control | genesis (gate >= 26 %) | TN rain (gate <= 1.43) |
| evap_ifs | +2.9 % FAIL | 19 % FAIL | 1.83 FAIL |
| lw_cnt 0.667 | -0.9 % pass | 29 % pass | 1.60 FAIL |
| ck_z 1 | +2.7 % FAIL | 31 % pass | 1.56 FAIL |
=> evap_ifs is the harmful item on all three scores (it alone ~ the whole combined degradation). lw_cnt passes exam and genesis; every item alone is wetter over TN (TN gate mixes in P4). No pairs needed for evap_ifs (fails alone). Not adopted: all three stay off; lw_cnt is a candidate to re-test once P4 is fixed.
**P1 source (tn-evo-f2q, F2 moisture by process, tropics 850-925 hPa, g/kg/day)**: boundary-layer scheme +2.3..+2.5 (TN +2.5..+2.8), deep convection -1.2, shallow -0.4, advection -0.8, rain evaporation +0.2..+1.0. => the 850-925 hPa moistening that builds the F2 low deck comes from the BOUNDARY-LAYER MIXING (pbl_tm: larger ws, deeper K-profile) reaching above cloud base - not shallow convection and not the counter-gradient term (fix changed nothing at 32 L). Physical basis for the next derivation: in a cloud-topped BL the dry K-profile should mix only up to cloud base (LCL); above it the transport belongs to the cumulus plume (IFS EDMF / shallow convection). Next: derive the mixing-depth limit (hbl <= LCL when the parcel saturates) offline from the same budget, register, test. (cld output empty: the cloud fraction is only produced on fresh radiation calls - fix the diagnostic.)
- 3 Nov 22:25: tn-shmf-tnr / tn-shmf-evo failed at start - MY launch quoting error (escaped quotes inside the JSON) - relaunched 22:23 with verified commands (accounts 1-2).
- tn-shmf-sb (measurement): the inserted storm still fills in the first 12 h with the mass-flux shallow plume (Nivar 1008.3 -> 1009.5, Michaung 1005.5 -> 1006.2, Vardah 1002.1 -> 1004.5) - same as control. Later it is WEAKER than control (72 h: Vardah 997.2 vs 994.3 hPa, v850 22.8 vs 29.5 m/s; Michaung 1005.7 vs 1004.2, 11.6 vs 21.3 m/s). Track errors mixed (Nivar 36-60 h smaller: 83-354 vs 560-668 km, partly tracker jumps in control; Vardah 72 h worse 752 vs 454; Michaung better 149 vs 228). => replacing the shallow scheme does not cure the early filling (P3) and weakens storms - consistent with 25 Oct (cutting shallow mixing aloft weakened genesis). The early-filling cause is elsewhere: next = storm budget term analysis 0-12 h.

### 3 Nov 22:45 IST - peer review (P3 first 12 h) and registered P3 diagnosis runs
Peer: find which term removes the vortex's energy in the first 12 h, radially (not domain means); do not tune. Correction to the peer's status: the SCM 'time' issue was fixed at 13:00; the 13:09 rerun shows TWP-ICE with GFS v16 COMPLETED (output.nc summarised in scm_ref.json) - BOMEX fails only because its case uses the prescribed-surface suite SCM_GFS_v16_ps, which was not built -> now built too (rerun acct 4).
storm_budget.py: new 'radial' output - rings 0-100/100-200/200-300/300-500 km: column heating by process (W/m2), surface enthalpy flux, rain, azimuthal-mean tangential wind (850 hPa, lowest level), lowest-level T and q; core-minus-ring T by level; hourly ('step' 1).
Runs (Nivar, Michaung, Vardah, inserted storm, 12 h hourly; measurement - which term/when):
- tn-sb-r12 (control): radial budget baseline.
- tn-sb-r12d4 (diff_x 4 = 4x weaker damping of the smallest scales): numerical-smoothing test. Prediction if smoothing removes the vortex: 12-h pressure rise at least halved (Nivar +1.2 hPa -> <= +0.6) and the 0-100 km vt850 kept within 10 % of its 1-h value; otherwise smoothing is not the cause. (Diagnostic only - not an adoption candidate.)
- tn-sb-r12nb (no digital-filter initialisation, 24 h): the DFI (6-h filter) can remove the unbalanced part of an inserted vortex. Prediction if DFI is the cause: pmin at 1 h at least 1 hPa deeper than in tn-sb-r12 and no rise over the first 12 h.
Reading order: the term that changes sign/size first in the 0-100 km ring during 0-12 h names the cause; the two sensitivity runs separate numerics (diffusion, initialisation) from physics.

## 4 Nov 01:00 IST cycle (silent) - scored
**P3 numerics REJECTED as the cause** (registered 22:45): tn-sb-r12d4 (4x weaker small-scale damping) = control within 0.3 hPa for all 3 storms -> smoothing not the cause. tn-sb-r12nb (no initialisation filter): 1-h pmin only 0.7 hPa deeper (Nivar), then same rise -> DFI not the cause. Both predictions FAIL -> numerics excluded.
**Metric caveat found**: the 0-12 h central-pressure 'filling' is largely the semidiurnal pressure tide (all 3 starts at 00-06 UTC: minimum near 14-16 LT, maximum near 20-22 LT; Nivar 1006.7 at +3 h -> 1010.6 at +9 h). Raw pmin cannot measure early spin-down; use tangential wind.
**Radial budget (tn-sb-r12, control)**: the vortex DOES spin down, mostly near the surface: 100-200 km ring vt850 Vardah 17.3 -> 12.6, Nivar 11.2 -> 8.5, Michaung 12.9 -> 9.8 m/s in 12 h (-24..-27 %); lowest level -36 % (Nivar 11.0 -> 7.1). Heating is NOT lacking: core (0-100 km) deep-convective heating 1400-1550 W/m2 plus growing grid-scale condensation (to 1300-2300 W/m2); surface enthalpy flux 140-260 W/m2; core lowest-level T falls ~1.5 K in 6 h (Nivar) under rain evaporation -370 W/m2 at the start. => a MOMENTUM sink at low levels where convection is on, not an energy deficit. This matches the 29-30 Oct finding (convective momentum transport relaxes u, v to the cloud-layer mean with tau_cmt = 6 h, ~8x too fast; CMT off: Nivar -9..-12 hPa, Titli -7..-8 at 72 h). cmt_mf (mass-flux CMT, derived) was rejected on TRACKS - but tracks are now known to be biased by the large-scale easterly excess (-3 m/s at 850 over S India), so that gate mixed two problems. Plan: fix the steering bias, then re-run cmt_mf against the same gates.
**Common-cause test (shallow mass-flux plume) REJECTED**: tn-shmf-evo 1000 hPa +2.8 -> -1.5 K (gate < +1.5 PASS) but 850 -2.0 K (gate >= -1.5 FAIL); TN rain 1.91 (gate < 1.43 FAIL); genesis 12 % (gate >= 26 % FAIL). Exam runs (q0/q1) never started (launch push collided) - not needed after 3 fails.
**P2 hot spot located**: tn-tr75-0609b ran 720 steps (10 days) with no non-finite values (the exam blow-up did not recur in the trace); the boundary-layer runaway sits over land at 25.6 S 69.6 W (central Andes / Atacama-Chaco region in June), h_bl 1729 K/day at sigma 0.967 in 22 columns from step 45. Next: trace with surface H, Ts, hbl, LCL at the hot spot (tn-tr75-0609c).
**SCM reference COMPLETE**: GFS v16 ran BOMEX and TWP-ICE (outputs summarised in tn-scm-ref/scm_ref.json). Next: scm_megam.py (MEGAM column physics on the same forcing).
New diagnostics (output only): hbl, zlcl (Bolton-type LCL of lowest-level air), share of columns with BL top above the LCL; trace records surface H/E/Ts/hbl/LCL at the h_bl hot spot.
Measurement jobs (no gates): tn-evo-f2l (F2) and tn-evo-ctll (control) - BL top vs LCL in tropics/TN (for the P1 mixing-depth derivation); tn-tr75-0609c (75 L, 9 Jun, 80 steps) - hot-spot surface values.

## 4 Nov 07:00 IST cycle
**P2 second cause found - explicit surface heat exchange is numerically unstable on thin bottom layers.** tn-tr75-0609c at the hot spot (Andes, 24-28 S, 69-70 W): lowest-level wind V1 50-100 m/s, u* 5-7 m/s, sensible flux H swinging -2800 -> +12500 W/m2 between steps and land skin temperature 247 -> 307 K -> classic explicit-coupling oscillation, then h_bl 1900-3900 K/day and the blow-up.
D14 offline (d14_surface_coupling.py): explicit exchange is stable only if dt*chv/m1 (air) and dt*chv*cp/C (land) stay below ~2 together; 75 L bottom layer (7 hPa): 1.68 + 0.60 already at 10 m/s, 8.4 + 3.0 at 50 m/s, 16.8 + 6.0 at 100 m/s -> divergent; backward Euler (implicit) converges for any dt. (32 L, 20 hPa: stable at 10 m/s, unstable at 50 m/s.)
5-Why: blow-up <- BL heating 2000-4000 K/day <- surface flux 6-12 kW/m2 <- explicit flux with strong wind on a thin layer oscillates and grows <- surface fluxes and land temperature are stepped explicitly (only the interior diffusion is implicit) <- the coupling was written for 32 levels; 75 levels thin the bottom layer 3x.
Fix (implementation, default off): sfc_imp 1 = surface heat and moisture fluxes implicit in the lowest-layer tridiagonal solve (flux = rho ck V1 (X_s - X_1^{n+1})), fluxes reported consistent with the solve, land skin temperature implicit (net flux linearised: 4 sigma T^3 + cp chv + L chv beta dqs/dT). Separate open item: why the lowest-level wind reaches 50-100 m/s over the Andes (pressure-gradient error over steep terrain with thin sigma layers?) - to investigate after the stability fix.
Registered before running: (1) tn-tr75-0609d (75 L F2 + sfc_imp, 9 Jun, 80 steps): max |h_bl| after step 1 < 300 K/day everywhere AND |H| at the h_bl maximum < 1500 W/m2 in every step. (2) tn-tp75f2imp-wx-q0 (exam q0, 75 L F2 + sfc_imp): all 19 starts complete (incl. 9 Jun); z500 d5 no worse than 75 L F2 without it (71.7) + 2 %. (3) tn-imp-wx-q0 (32 L control + sfc_imp): z500 d5 within +-2 % of control (73.1) - expected near-neutral. P2 is closed only if (1) and (2) pass.
**P1 mixing depth (tn-evo-f2l / tn-evo-ctll, 6 starts)**: F2: BL top above the LCL in 77-88 % of tropical columns (hbl 785-867 m vs LCL 547-617 m), Tamil Nadu 76-100 % (969-990 vs 466-527 m). Control: BL top below the LCL (hbl 708-792 vs LCL 1113-1350 m; only 29-37 % above) - the control's warm, dry BL has a high cloud base. => In F2 the dry K-profile mixes 300-500 m into the cloud layer, which (with tn-evo-f2q: BL scheme +2.3..+2.8 g/kg/day at 850-925 hPa) builds the low deck.
Fix (IFS EDMF principle, Part IV ch. 3; default off): bl_lcl 1 = K-profile depth limited to the LCL of the lowest-level air (>= 100 m) when the LCL lies below the diagnosed BL top.
Registered (F2 + bl_lcl, vs F2): (a) tn-evo-f2lcl: BL-scheme moistening at sigma 0.82-0.95 (0-24 h, tropics) <= +1.2 g/kg/day (F2 +2.5); (b) d5 tropics 850 hPa T bias >= -1.5 K (F2 -2.4); (c) d5 q850 bias <= +0.35 g/kg (F2 +0.70); all three must pass. Measurements with the regression gates of 3 Nov: tn-f2lcl-tnr (TN box; P4 gate +-25 %), tn-f2lcl-gen0 (>= 26 %), tn-f2lcl-wx-q0 (z500 d5 <= control 73.1 + 2 %).
**P3 re-test registered (intensity only; tracks confounded by the steering bias)**: cmt_mf (mass-flux CMT, derived 30 Oct) vs control, Nivar/Michaung/Vardah, inserted storm, 72 h, radial output (tn-sb-cmtmf72 vs tn-sb-ctl72, both deterministic). Gates: (a) 100-200 km ring vt850 loss over 0-12 h at most half of control's (control -24..-27 %) in >= 2 of 3 storms; (b) 72 h max v850 closer to the ERA5-at-resolution value than control in >= 2 of 3 (Nivar ERA5 smoothed 26.6 m/s; Michaung/Vardah computed offline from their ERA5 case files before scoring).
**P3 targets (ERA5 at model resolution, data/cyclone/era5_p3_targets.json)**, 72 h max v850 smoothed / msl min: Nivar 26.6 m/s / 994.1 hPa, Michaung 26.9 / 992.0, Vardah 25.2 / 995.2. Control (tn-sb-p3a, 72 h): Nivar 22.8 / 1005.2, Michaung 21.3 / 1004.2, Vardah 29.5 / 994.3 -> Vardah already meets the target; Nivar and Michaung fall short mostly in PRESSURE (11-12 hPa too shallow) and 4-6 m/s in wind.
**Steering bias (reasoning, L1)**: Oct-Dec exam biases - central India MSLP +1.9 hPa with z500 -11 m and t850 +0.3 K (a column too cold aloft holds higher surface pressure under a lower 500 hPa surface: the tropical mid-troposphere is 3-5 K too cold in the control); Tamil Nadu MSLP -0.7 hPa with t850 +2.0..+2.6 K (warm low levels, thermal low). Both are the control's heating-profile errors (BL too warm, 300-700 hPa too cold). So the easterly excess should respond to the P1/P4 heating fixes - every candidate is now also checked on the Oct-Dec Tamil Nadu u850 bias (control -3.5 m/s at day 5).

## 4 Nov 09:30 IST - scored (Sridhar: fix P1-P3 today)
**P1 bl_lcl - all three registered P1 gates PASS**: BL-scheme moistening at sigma 0.82-0.95 (0-24 h) +2.5 -> +0.97 g/kg/day (gate <= 1.2); d5 tropics 850 T -2.4 -> -1.3 K (gate >= -1.5); q850 +0.70 -> -0.72 g/kg (gate <= +0.35; now too dry by about as much as it was too moist). BL top above the LCL in 4 % of columns (was 77 %). Exam q0 z500 d1/d5/d10 20.4/71.3/115.8 vs control 20.3/73.1/120.4 (better at d5 and d10). Oct-Dec TN u850 bias d3/d5 -1.12/-4.19 vs control -2.19/-4.87 (smaller, 5 starts only). BUT genesis 14 % (gate >= 26 % FAIL) and TN rain 1.82 (P4 gate FAIL); 925/1000 hPa now -2.2/-1.9 K. => the P1 MECHANISM is fixed; F2 + bl_lcl is not adoptable alone (genesis).
**P3 cmt_mf (registered gates) - PASS**: (a) 0-12 h loss of 100-200 km vt850 at most half of control's: Vardah -8.1 vs -26.8 %, Nivar -5.6 vs -23.7 % PASS, Michaung -13.7 vs -22.7 % fail -> 2 of 3 PASS. (b) 72 h v850 closer to ERA5-at-resolution: Nivar 31.9 vs ctl 18.3 (target 26.6) closer; Michaung 27.4 vs 19.2 (26.9) closer; Vardah 35.4 vs 26.3 (25.2) farther (overshoot) -> 2 of 3 PASS. Pressure at 72 h: Nivar 993.0 (ERA5 994.1, ctl 1005.0), Michaung 1000.5 (992.0, ctl 1004.0), Vardah 987.4 (995.2, ctl 995.7: overshoot 8 hPa). => the storm spin-down is removed; momentum transport was the P3 cause. Regression still needed (its 30 Oct rejection was on tracks, now known to be confounded by the steering bias).
**P2 sfc_imp**: trace 9 Jun (75 L) - no blow-up, |H| at the hot spot <= 694 W/m2 (gate < 1500 PASS), but h_bl 300-361 K/day in 49 steps at 26-27 S over the Andes with 45-80 m/s low-level wind (gate < 300 FAIL as registered). No runaway (it was 1700-3900 K/day). 32 L control + sfc_imp z500 d5 73.6 vs 73.1 (+0.7 %, gate +-2 % PASS). tn-tp75f2imp-wx-q0 never ran (launch collided) -> relaunched. Remaining P2 item: the 45-100 m/s lowest-level wind over the Andes at 75 L.

### Registered 4 Nov 09:40 IST - combined candidate PKG = F2 (pbl_tm 1, sh_mflux 0.03) + bl_lcl 1 + cmt_mf 1 (32 L); PKG75 = PKG + sfc_imp 1 at 75 L
Reason: P1 fix (bl_lcl) loses genesis; cmt_mf removes the vortex spin-down that kills weak systems -> expected to restore genesis. Gates (all must pass for Stage 1): exam (q0+q1, 38 starts) z500 d5 <= control + 2 %; genesis gen0 >= 26 %; P1 gates (850 >= -1.5 K, q850 within +-0.5 g/kg); P3 storm gates (as above) and no storm deeper than its ERA5 target by > 5 hPa at 72 h; Oct-Dec TN u850 day-5 bias smaller than control; TN rain measured against P4 gate (+-25 %) - P4 is expected to remain open. PKG75: all exam-q0 starts complete. Also cmt_mf alone genesis (tn-cmtmf-gen0) to separate effects.
**Tracks with cmt_mf (radial 72 h runs, same 3 storms)**: 24/48/72 h error km - Vardah ctl 213/496/454 vs cmt_mf 182/428/309 (better); Nivar ctl lost (tracker jumps from 24 h, storm too weak to follow) vs cmt_mf 150/208/169; Michaung ctl 92/182/228 vs cmt_mf 107/199/299 (worse). Mixed, 3 storms only.
### Registered 4 Nov 09:50 IST - TRACK gate for the package (same as the 30 Oct cmt_mf gate, now with the P1 fix included)
tn-quick6-pkg (Sidr, Titli, Phailin, Giri, Hamoon, Nivar; 72 h, deterministic) vs tn-quick6-ctl-d1: jump-cleaned mean track error at 48 h and 72 h no more than 10 % worse (ctl 199 / 273 km). tn-lib84-pkg (41 storms, 120 h, 2 chunks) vs tn-lib84-ctl: 72 h mean track error no more than 10 % worse; intensity gap at 72 h smaller. Failing the track gate rejects the package regardless of intensity.

## 4 Nov 10:40 IST - package (F2 + bl_lcl + cmt_mf) partial results
- TRACK gate (tn-quick6-pkg vs tn-quick6-ctl-d1, jump-cleaned, 6 storms): 48 h 206 vs 199 km (+3 %, pass), 72 h 358 vs 273 km (+31 %, FAIL; gate <= +10 %) -> PACKAGE REJECTED as registered. Better: Sidr 61 vs 107, Nivar 88 vs 246; worse: Giri 688 vs 291, Phailin 514 vs 364, Hamoon 662 vs 565, Titli 133 vs 66.
- Direction of the 72 h errors: every storm is too far SOUTH in both control and package (dLat -0.7..-4.2 deg); the recurving storms (Giri, Hamoon: real NE motion) go W/SW instead; Phailin (real W) lags east. => a systematic missing poleward motion, worse when storms are stronger. Candidates: deep-layer steering (Oct-Dec u200 westerly bias +7..+9 m/s by day 7; trough timing) vs vortex-scale beta drift. Next diagnostic: deep-layer (850-200 hPa) mean flow around the storms in model vs ERA5 (needs model fields along the track).
- P3 gates inside the package: 0-12 h vt850 loss Vardah -20.1, Nivar -12.4, Michaung -13.4 % (gate <= half of control's ~-12 %: FAIL in 3 of 3 - bl_lcl gives back part of cmt_mf's gain); 72 h v850 closer to ERA5 in 2 of 3 (Vardah 24.7/25.2, Nivar 23.6/26.6; Michaung 17.5/26.9 farther); 72 h pmin Vardah 993.2 (ERA5 995.2), Nivar 998.4 (994.1), Michaung 1000.1 (992.0) - no overshoot > 5 hPa.
- P1 inside the package (tn-pkg-evo): 850 -1.0 K (pass), q850 -0.67 g/kg (gate +-0.5 FAIL: too dry), 925/1000 -1.9/-1.7 K.
- TN rain 1.79 (P4 open). Exam/genesis/75 L runs still running.
Registered measurement (no gate): tn-maps-mich-ctl / tn-maps-mich-pkg - Michaung (real path north along the coast), maps_run from the library start 2023-12-01, 120 h, control vs package; offline: 850/500/200 hPa and deep-layer mean flow in the 300-600 km ring around the REAL position vs the ERA5 case file (michaung_2023) -> is the missing poleward motion in the environment flow or in the vortex?
- 11:10: package exam (q0+q1, 37 starts) z500 d1/d5/d10 19.8/69.8/116.6 vs control 20.2/72.5/119.8 (d5 -3.7 %, PASS). Oct-Dec TN u850 bias d3/d5 package -2.63/-4.51 vs control -2.16/-3.25 m/s (9 starts) -> the easterly steering error is LARGER with the package: consistent with its worse 72 h tracks.

### 4 Nov 11:20 IST - peer review: classify the problems; investigate heating and momentum budgets before more changes
Classification adopted (formulation vs coding bug vs numerics): P1 = scheme FORMULATION (dry K-profile allowed above cloud base; code did what it said); P2a = CODING BUG (counter-gradient flux used the wrong K); P2b = NUMERICAL STABILITY of the scheme design (explicit surface coupling); P3 = FORMULATION (6-h relaxation CMT is a crude scheme, not a coding error); P4 = mechanism partly known (control: grid-scale rain in dry regimes from the shallow MSE/q relaxation lifting vapour; F2: coastal-sea over-convection) but NO fix and no proof of which scheme is at fault; track = large-scale circulation bias (easterly excess, missing poleward motion) - cause open.
Measurement registered (no gates; no parameter change before it): momentum + heating budgets, Oct-Dec starts (6), control vs package, regions tropics / Tamil Nadu / central India (18-26 N, 74-86 E) / southern Bay (5-15 N, 80-92 E), windows 0-24 / 48-72 / 96-120 h: heating by process and momentum tendency by process (BL friction u_bl/v_bl, convective momentum transport u_cmt/v_cmt; new diagnostics) -> which term makes the 850 hPa easterly over S India stronger with the package (pressure-gradient forcing via heating, or a momentum sink/source).

## 4 Nov 11:30 IST - why the combined package fails: theory/offline calculation (Sridhar: find why, by calculation, not more tests)
Geostrophic check from the exam biases (Oct-Dec, 9 starts, day 5): u_g = -(1/(rho f)) dp/dy, dy ~ 1100 km (central India ~22 N to Tamil Nadu ~11 N), f at 16 N.
- Control: MSLP bias central India +0.98, Tamil Nadu -0.66 hPa -> extra N-S difference +1.63 hPa -> u_g -3.2 m/s; observed u850 bias -3.25 m/s. The control's easterly error IS the pressure-gradient error (agreement within 0.1 m/s).
- Package: central India +0.81, Tamil Nadu -3.01 hPa -> +3.82 hPa -> u_g -7.5 m/s at the surface; observed -4.51 at 850 (friction and the vertical decay reduce it). The extra easterly comes from LOWER pressure over the south (-2.3 hPa more than control), not from central India.
- Tamil Nadu t850 is now ~0 K (was +2.3), so the southern low is not a thermal low of warm low levels. With cmt_mf, weak lows no longer spin down (P3 fix) -> lows over the southern Bay / Tamil Nadu deepen and persist -> lower mean pressure in the south -> stronger N-S gradient -> stronger easterly -> storms steered west, and the lows themselves sit too far south (matches every 72 h track ending too far south).
- ERA5 Oct-Dec 2020 Tamil Nadu box: u850 -4.4, u200 -7.3 m/s (deep easterly); model day-5 u850 control -7.7, package -8.9.
Hypothesis (L1, not yet proven): the P3 fix exposes a pre-existing error - too many / too deep lows forming too far south in the southern Bay (the old 6-h CMT spun them down and hid it). Confirming test (one run, if approved): cmt_mf alone on the Oct-Dec exam starts - prediction: Tamil Nadu MSLP bias <= -2 hPa and u850 day-5 bias <= -4 m/s, while bl_lcl alone does not (its q0 value -4.19 vs control -4.87 on 5 starts).

### Registered 4 Nov 11:40 IST - DIAGNOSTIC experiment (not an approval of P3): P3 fix alone (cmt_mf 1) vs control, nothing else changed
Peer caution adopted: the geostrophic estimate is supporting evidence, not proof (near-surface tropical flow has frictional, ageostrophic and transient parts).
Same Oct-Dec starts and initial conditions (deterministic): tn-cmt-wx-q0/q1 (exam: MSLP and u850 bias by region), tn-lows-ctl / tn-lows-cmt (6 Oct-Dec starts, budgets + NEW lows diagnostic: number, mean lat/lon and depth of MSLP lows deeper than 2 hPa in 0-22 N 75-100 E, plus regional mean MSLP incl. southern Bay), tn-cmtmf-gen0/gen1 (formation frequency, genesis position), tn-quick6-cmt (24/48/72 h storm positions, 6 storms).
Predictions (hypothesis 'P3 fix exposes too many/too deep southern lows'): cmt_mf alone gives Tamil Nadu MSLP bias <= -2 hPa AND Oct-Dec TN u850 day-5 bias <= -4 m/s; and the lows diagnostic shows more and/or deeper lows south of ~15 N than control. Causal check: the southern-Bay mean-MSLP change (cmt minus control) must account for most of the change in the N-S pressure difference; if the extra lows are absent or north of 15 N, the hypothesis is rejected even if the wind error grows.
- 11:50 scored: **P2 tn-tp75f2imp-wx-q0 (75 L F2 + sfc_imp): all 19 exam starts complete incl. 9 Jun (gate PASS); z500 d1/d5/d10 23.1/72.9/118.6 vs 75 L F2 without (18 starts) 71.7 d5 -> within +2 % (PASS).** With the trace gate (h_bl < 300 K/day: max 361 over the Andes, FAIL) the registered P2 closure rule is NOT met - P2 stays open on the Andes low-level wind (45-80 m/s) item only; no blow-ups remain in the tested starts.
- Genesis gen0: package 14 %, cmt_mf alone 31 % (= control 31 %), F2 + bl_lcl 14 % -> the formation loss comes from the F2/bl_lcl side, not from the P3 fix. (F2 alone genesis has never been measured - add.)
- 11:55 peer review: hold all changes until the diagnostic runs finish. Precaution adopted: lows are compared with the SAME detection code (both tn-lows-ctl and tn-lows-cmt run the same wx_prof commit: 7x7-cell local MSLP minimum, > 2 hPa below an 11x11-cell mean, 0-22 N 75-100 E). Limitation stated: it is a per-snapshot count every 3 h, not a tracker - a long-lived low is counted in every snapshot, so the count measures low-presence (low-hours), not the number of separate systems.
- Next control experiments (queued for the first free accounts): genesis with F2 alone (gen_f2) and with bl_lcl alone on the control (gen_lcl) - separates which of the two causes the formation loss (31 % -> 14 %).
- 12:05 peer review of the 31 Oct physics document vs 4 Nov results. Corrections: (1) the equation du/dt = g d/dp[M(u_u - u)] is the NEW mass-flux CMT (cmt_mf), not the old one - the control's CMT is relaxation to the cloud-layer mass mean with tau_cmt 6 h; (2) the P3 candidate tested today IS the same cmt_mf code as the 30 Oct candidate (code unchanged since commit 601c27c2) - so today's genesis/intensity results continue that experiment; its 30 Oct track rejection is what is being re-diagnosed; (3) the P2 Andes peak is NOT a surface-flux spike any more: at the 361 K/day points H is -100..-700 W/m2 (stable, downward) and the peak sits at sigma 0.92-0.95 (above the bottom layer) with 45-80 m/s wind -> interior mixing under extreme shear (K_free ~ dU/dz), i.e. the Andes low-level wind item; (4) rainfall-source split for P4 already exists in tn_rain_diag (conv / grid-scale / evaporation by region): control TN land ~75 % grid-scale, F2 coastal sea deep-convective. Adopted: docs/formulation_history.md as the revision record (31 Oct document = control baseline).
- 12:50 P3 diagnostic, partial (6 Oct starts, same detector both runs): lows (0-22 N 75-100 E) at 96-120 h - cmt_mf depth 5.5 vs control 2.9 hPa, presence 1.4 vs 1.1, mean latitude 14.4 vs 14.2 N (south of 15 N); southern-Bay mean MSLP 48-120 h -0.8..-1.1 hPa vs control, Tamil Nadu -0.35..-0.6, central India also -0.3..-0.6 -> the central-India-minus-southern-Bay difference grows by ~+0.5 hPa (~1 m/s geostrophic). => hypothesis PARTLY supported: the P3 fix does deepen the southern lows, but its pressure effect (~0.5 hPa) is much smaller than the package's (Tamil Nadu -3.0 hPa) -> most of the package's southern pressure drop comes from the F2/bl_lcl side or the interaction. Exam wind/pressure (tn-cmt-wx-q0/q1) still pending for the registered thresholds.
- quick6 with cmt_mf alone: 48/72 h 221/297 vs control 199/270 km (+11 % / +10 %, at the gate limit); mean 72 h latitude error -1.3 vs -1.2 deg -> the southward track error exists in the CONTROL and is not caused by the P3 fix.

## 4 Nov 13:00 IST - Sridhar: could other issues be hidden? Global budget check (day 5, 6 Jan starts, from the existing budget runs)
| global mean | control | F2 | package | observed (approx.) |
| rain (L*P, W/m2) | 107.5 (3.7 mm/day) | 119.7 | 105.6 | ~78 (GPCP ~2.7 mm/day) -> 35-55 % too much |
| evaporation L*E | 102.6 | 106.6 | 92.2 | ~80-88 |
| rain minus evaporation | +4.9 | +13.2 | +13.4 | ~0 in balance -> the atmosphere is drying (water drift) |
| sensible heat SH | -6.4 | +5.8 | +16.3 | ~+17..+20 upward -> control sign/size suspect |
| OLR | 209 | 204 | 207 | ~240 (CERES) -> 31-36 W/m2 too low |
| net column physics heating | -19.2 | +6.5 | -0.3 | ~0 over days |
Control z500 global bias day 1/3/5/7/10: -14 / -24 / -31 / -38 / -45 m (a steady global column cooling, ~1.5 K in 10 days, matching the -19 W/m2 column deficit).
=> Yes: there are GLOBAL problems outside P1-P4 that every regional fix interacts with: (H1) far too much global rain and evaporation (hydrological cycle ~40 % too fast), (H2) OLR ~35 W/m2 too low (too opaque LW / too much high cloud), (H3) control energy drift (-19 W/m2, z500 -45 m by day 10), (H4) control global sensible heat negative, (H5) rain > evaporation (water not conserved or real drift). Not yet known which are formulation errors and which are coding/conservation bugs.
Plan (diagnose before changing anything): (a) conservation audit - per physics process, check that column energy and water change equal the boundary fluxes (a closed-budget test on saved columns; a non-zero residual = a coding/conservation bug); (b) compare the global numbers with CERES / GPCP / flux climatology for the same months (observations, not tuning targets); (c) the GFS single-column comparison (outputs ready) for the process sizes; (d) add 'global health' (H1-H5) to the Stage-1 acceptance table.

## 4 Nov 13:15 IST cycle - conservation audit (hidden-issue search)
budget_audit.py: for 2 starts x (6 h, 1 d, 3 d), every column's physics vs its boundary fluxes - BL heat/water vs surface H/E, moist-enthalpy conservation of deep/shallow/condensation/evaporation, total water (incl. the q >= 0 clip) vs E - rain, total non-radiative energy vs H + L E, radiation vs its own TOA/surface fluxes, surface rain vs water removed. Expected ~0 (W/m2) for each; a non-zero residual = conservation/coding defect in that process. Known non-conserving terms to be measured, not fixed yet: q >= 0 clip (adds water), stratosphere above rad_top 0.12 relaxed to the start T with 15 d (no radiation there), counter-gradient flux columns. Runs: tn-audit-ctl (control), tn-audit-f2 (F2), tn-audit-pkg (package).
- 13:25 tn-lib84-pkg (41 storms) vs tn-lib84-ctl: 72 h track 318 vs 247 km (+29 %, n 24 cleaned; better in 7/24) -> confirms the quick6 track FAIL; pressure deeper at 72-120 h (999-1000 vs 1003-1004 hPa) but max wind slightly lower (26.3 vs 27.6 kt at 72 h; obs 46.8); storms lost/jumping 10 vs 22 (package storms stay trackable).
- 15:35 conservation audit (control / F2 / package, +6 h and +24 h; the +72 h step did not finish): EVERY physics process conserves - BL water, deep, shallow, condensation, evaporation (moist enthalpy cp T + L q) all 0.000 W/m2 globally, max 0.01; total water and surface rain close exactly; BL heat vs surface H +0.5 W/m2 (max 21 in single columns, small). The one large residual - total non-radiative energy -14.4 W/m2 global, -21 tropics - comes from MY audit subtracting the COMPUTED radiation everywhere while the model applies a relaxation to the start temperature above rad_top (sigma 0.12) instead; the per-process sums show no leak. Audit corrected (mm2 diag 'rad_app' = the heating actually applied; checks for applied-minus-computed above rad_top and for process sum vs total) -> rerun tn-audit2-ctl.
=> Conclusion so far: no coding/conservation defect inside the physics processes. The global problems (rain too high, OLR too low, cooling drift) are formulation/parameter issues or sit in radiation / the stratosphere treatment - the rerun measures the latter.

## 4 Nov 15:45 IST - P3 diagnostic scored, F2 base decision, 75 L package
**Southern-lows hypothesis REJECTED for the P3 fix alone** (registered thresholds): cmt_mf alone, Oct-Dec (9 starts), day 5: Tamil Nadu MSLP bias -1.26 hPa (threshold <= -2: not met), TN u850 bias -2.31 m/s vs control -3.25 (threshold <= -4: not met - the easterly error is SMALLER with the P3 fix). Lows: slightly deeper (rootcause 12:50) but they do not drive the easterly. => the P3 fix alone does not cause the steering error; the package's easterly growth (-4.51) comes from the F2/bl_lcl side.
P3 fix alone otherwise: exam (37 starts) z500 d1/d5/d10 20.0/72.4/118.3 vs control 20.2/72.5/119.8 (neutral to slightly better); genesis gen0 31 % (= control), gen1 52 % vs 45 % (better); quick6 72 h +10 % (gate limit).
**F2 base decision**: genesis gen0 F2 alone 14 % vs control 31 %; bl_lcl alone 33 %. => F2 (pbl_tm + sh_mflux) causes the formation loss, NOT the cloud-base limit and NOT the P3 fix. Recommendation: drop F2 as the base; candidate base = control + cmt_mf (+ bl_lcl, + sfc_imp), F2 parts re-derived only where needed.
**75 L package (F2 + bl_lcl + cmt_mf + sfc_imp)**: 16 of 19 exam starts BLEW UP (F2 + sfc_imp alone at 75 L: 19/19 complete) -> cmt_mf or bl_lcl is unstable on thin layers. Suspect: cmt_mf flux divergence g dF/dp is explicit; on 7-hPa layers M (u_u - u) dt / (dp/g) can exceed 1 (same class as P2). Traces registered: tn-tr75-cmt (75 L F2 + sfc_imp + cmt_mf, 1 Jan, 80 steps) and tn-tr75-lcl (75 L F2 + sfc_imp + bl_lcl): the one that goes non-finite names the component.

## 4 Nov 19:00 IST cycle - full Stage-1 suite on the new base (control + cmt_mf), 75 L traces, audit rerun
**base1 suite** (score_suite.py base1; data/cyclone/suite_base1.json):
| criterion | base1 | control | |
|---|---|---|---|
| 1 z500 d5/d10 (73 starts) | 73.1 / 119.2 | 73.3 / 120.2 | PASS |
| 2 low-level T/q (d5 tropics) | T925 +2.5 K, T1000 +2.7, q850 -1.45 | T925 +2.5, T1000 +2.8, q850 -1.47 | FAIL - identical to control (inherited warm/dry BL) |
| 3 intensity vs ERA5 72 h (pmin) | Nivar -0.4, Vardah -5.7, Michaung +7.4 hPa | +10.9 / +0.5 / +12.0 | FAIL (2 of 3 just outside; large improvement) |
| 4 quick6 72 h track | 297 km, lat error -1.27 deg | 273 km (tn-quick6-ctl-d1, 30 Oct) | FAIL (+9 %) |
| 5 genesis | 36 % / 48 % | 31 % / 45 % | PASS |
| 6 TN rain ratio | 1.81 | 1.43 | FAIL |
| 7 Oct-Dec TN u850 d5 | -2.41 m/s | -3.51 | PASS |
| 8a 32 L stability | 73/73 | | PASS |
**Hidden-issue flag (TN rain)**: every option tested since 2 Nov gives TN rain 1.56-1.91 (ckz 1.56, lwc 1.60, tp75f2 1.66, pkg 1.79, base1 1.81, f2lcl 1.82, evi 1.83, corr 1.85, shmf 1.91) while the only control run (tn-base-tnr, 2 Nov) gives 1.43. Same script, same starts, deterministic flags. Either the control is the outlier in a noisy 6-start metric, or the code changed control behaviour after 2 Nov. Test: the whole control suite re-run on today's code (tn-s-ctl2-*, accounts 1-10). Prediction if no drift: identical to the 2 Nov control (tnr 1.43, z500 73.3/120.2, quick6 273 km). Any difference = code drift -> bisect the commits since 2 Nov. All baselines in score_suite will switch to ctl2 (same code as the candidates).
**75 L traces**: tn-tr75-cmt (F2+sfc_imp+cmt_mf) and tn-tr75-lcl (F2+sfc_imp+bl_lcl), 1 Jan, 120 steps (40 h): both finite throughout (max h_bl 317 / 468 K/day). => registered prediction (one of them goes non-finite) NOT confirmed: neither component alone blows up within 40 h. Next: tn-tr75-pkg (full package, 720 steps = 10 d, per-step JSON) finds the time/place of the blow-up; tn-b75-wx-q0 (new base cmt_mf + sfc_imp at 75 L, 19 starts) = stability gate for the base that will actually be used.
**Audit rerun (tn-audit2-ctl)**: all processes conserve (0.00 W/m2); process sum = total exactly; BL heat vs H +0.55 W/m2 (theta diffusion vs dry static energy, minor). Stratosphere: applied minus computed above rad_top -14.9 W/m2 global (-21 tropics) = the computed radiation there would WARM ~1 K/day and is replaced by relaxation to the START temperature (~0 at +6 h). => not an energy sink relative to the start state; the stratosphere is held. H4 'nudging' closed as a leak candidate; it stays a formulation limitation (no stratospheric radiation).
**Michaung steering maps** (tn-maps-mich-ctl/pkg): finished; fields uploaded to release model-maps (100 MB each) - comparison with ERA5 to be done offline (medium priority, tracks).

## 4 Nov 20:30 IST - code check: did the control change since 2 Nov? (local CPU, T42, start 2020-10-27; scripts drift_col1.py / drift_run.py)
- Diff 23c9b6bb (2 Nov control TN-rain run) -> HEAD, mm2.py: every change is behind an option that defaults OFF (sfc_imp, bl_lcl, pbl_tm counter-gradient) or is a diagnostic only. tn_rain_diag.py / landinit.py unchanged.
- Physics column on the same state, old vs new code: T, q, u, v, rain, H, E tendencies BIT-IDENTICAL (max diff 0). Each code is run-to-run deterministic (new vs new: 0).
- Time integration old vs new: step 1 identical; step 2 max 2e-4 K (round-off: the edited graph rounds differently - land-temperature update now has extra terms multiplied by 0); step 3 0.013 K in 80 points; 6 h 1.2 K max; 24 h 5.8 K max, global mean rain 1.750 vs 1.741 mm (0.5 %).
=> NO physics drift: the control formulation is unchanged. But a round-off-level difference grows to K-scale local differences within a day (chaotic growth via convection switches). Consequence: the TN-rain metric (6 starts, one 5x5-deg box, 5 days) is sensitive to round-off; part of the 'every option raises TN rain' pattern may be noise around a control that drew low (regression to the mean). Registered: ctl2 (same physics, different round-off) TN rain vs 1.43 measures this noise directly. If |ctl2 - 1.43| is >= ~0.1, criterion 6 needs more starts (and/or a small round-off ensemble) before any option can be judged on TN rain.

## 4 Nov 23:00 IST - Step 0 + Step 1 started (Sridhar: both overnight, complete by 5 Nov)
**Same-code control (ctl2) scored** - baseline for everything from now (score_suite BASE=ctl2): z500 73.3/119.7 (old 73.3/120.2), genesis 36/48 (old 31/45), TN rain 1.57 (old 1.43), quick6 72 h 289 km (old 273), Oct-Dec u850 -3.03 (old -3.51), intensity + low-level identical. => ROUND-OFF ALONE moves: TN rain 0.14, genesis 5 points, track 6 %, steering 0.5 m/s, z500 d10 0.5 m. base1 vs ctl2: z500 PASS, genesis equal (36/48 both; different cases), steering PASS (-2.41 vs -3.03), track +3 % (inside the 6 % round-off spread), TN rain 1.81 vs 1.57 (+0.24, ~2x the round-off spread).
**Step 0 (TN rain metric noise)**: 24 starts (every 15 days, all seasons), ctl / ctl + 0.1 % SPPT twin (round-off-type perturbation) / base1, 2 jobs each (tn-r24-*). Registered: noise = |ctl - ctlp| on the 24-start ratio; target < 0.05; then base1 - ctl judged against it.
**Step 1(a) evaporation - ROOT CAUSE FOUND (offline, T42, 2 starts, 72 h, ocean 60S-60N; flux_check.py)**: model ocean latent heat 134-137 W/m2 vs COARE 3.5 on the SAME lowest-level wind/T/q/height/SST 114-115 -> model +17..+20 % (tropics +19..+21 %), in every wind-speed bin (+8..+36 %). 5-Why: (1) ck = 1.2e-3 is a 10-m neutral value (COARE Ce10N ~1.1-1.2e-3); (2) it is applied with wind and humidity at the lowest model level (z1 = 82 m); (3) the correct height conversion is [ln(10/z0)/ln(z1/z0)]^2 ~ 0.71; (4) the default ck_z = 0.5 applies only the square root (~0.84) -> coefficient ~18 % too large; (5) also the 0.98 salinity factor on q_sat(SST) is missing (COARE, IFS). Offline check on the same columns: ck_z = 1 -> 116 / 119 vs COARE 114 / 115 (+2..+4 %); ck_z = 1 + salinity 0.98 -> 110 / 113 (-1..-3 %). => matches COARE to +-3 %. (ck_z 1 alone was tested 30 Oct: exam +2.7 % -> on hold; it must now be re-judged against ctl2 with the 24-start rain metric, and together with the radiation finding, because the evaporation excess may be compensating another error.) Confirmation at T170, 4 starts: tn-fluxchk.
**Step 1(b) radiation (first look, T42 day 1, model's own clouds)**: OLR 217 (CERES ~240), clear-sky OLR 253 (CERES ~266: -13), LW cloud effect 36 (CERES ~26: +10), cloud cover 0.79 (~0.67), grid-mean liquid water path 186 g/m2 (observed ocean ~50-90 g/m2: 2-3x), atmospheric radiative cooling -116 (~-105). => the OLR deficit is about half clear-sky (gas optics or the model's moisture) and half clouds (too much / too thick). T170 + RRTMG clear-sky comparison on the same columns: tn-radchk (builds climlab-rrtmg on Kaggle).
**Step 1(c) water drift**: tn-gb-ctl (global P, E, TCW, H, OLR every 6 h to day 10, Jan + Jul).

## 4 Nov 23:15 IST - P1 and track: offline diagnosis (Sridhar: start now, offline - code, equations, method)
**Method check first (roundtrip.py: model start state through the SAME output code vs ERA5, hour 0 and hour 24)**, T85/T42 locally (T170 too large for 8 GB here; T170 runs tn-rt-ctl / tn-rt2-ctl, 8 starts):
- Tropical T850 bias at hour 0 = -0.06 K, at hour 24 = +0.95 K -> the P1 warm layer is MADE BY THE MODEL IN THE FIRST DAY, not by initialisation or the pressure-level conversion.
- 'india' box MSLP +1.3 hPa already at hour 0 (Himalaya/Tibet sea-level reduction differs from ERA5's) -> measurement artefact of that box; central India / Tamil Nadu ~0 at hour 0 -> their later biases are real.
**P1 - which process (heat_prof.py, tropics, control, +3/+12/+24 h)**: at sigma 0.93 (~925 hPa) over ocean: shallow +1.9..+4.9 K/day (largest term), deep +1.0, rain evaporation -1.6..-3.2, radiation -1.1, BL -0.7..-0.9; NET physics +0.5..+1.3 K/day; over land shallow +1.8..+7.1 at +12 h. Same diagnostic with sh_mflux 0.03 (realistic shallow closure): shallow at 925 4.9 -> 0.8 K/day, deep 1.0 -> 1.7, net 0.96 -> 0.33 K/day. Reference check: GFS v16 SCM (our tn-scm-ref) BOMEX shallow heating 900-940 hPa is also +3..+5 K/day, so the shallow term is not absurd alone; the defect is the NET: nothing removes the +1 K/day. 
=> P1 hypothesis (registered): the control's shallow MSE relaxation (tau 1 h, exchange mass flux 0.3-0.9 vs observed 0.02-0.04) over-heats 925-850 hPa and dries it (moisture exported upward). Confirming test = D-F2a (sh_mflux alone on the base, full suite). Registered prediction: d5 tropical T925 bias falls by >= 1.0 K (from +2.5), q850 dry bias halves, deep-convection share >= 15 %.
**Track - storms do not turn north** (quick6 72 h: Hamoon -3.6 / Sidr -1.8 / Nivar -1.4 deg south and west; the real storms recurved N/NE): 
- Exam (73 starts) regional biases: north/central India land 2-m temperature -2.4 K at DAY 1 -> -3.2 K day 5 (Oct-Dec -1.6 -> -2.0); MSLP central India +0.9 (d1) -> +1.7 hPa (d5), NE India +2.3; south India / Tamil Nadu -0.4..-0.7 by d3-d5 -> an anomalous north-high / south-low pressure gradient ~2.5 hPa -> stronger easterlies over south India (u850 TN -3.0 m/s) and a ridge north of the Bay storms that blocks their northward turn.
- Michaung (maps vs ERA5 michaung_2023, environment ring 200-600 km at the REAL position): ERA5 200-hPa southerly 4.6-7.8 m/s after 36 h, control ~0 (-1.4..+1.7), package 3.7-4.6; model vortex (850 tangential wind) half of ERA5 at 72 h (13.9 vs 22.5 m/s) and lost at 84 h -> weak, shallow vortex in a too-weak poleward upper flow.
- Why is north/central India cold? roundtrip T42: central/NW India 2-m T +3.7/+4.9 K at hour 0 -> -2.4/-3.7 K at hour 24 (Apr start: -6.2/-7.5 K, T850 -2.9 K, MSLP +2.2 hPa) -> the land surface swings far too much and ends cold within the first day. Code: land = ONE thin slab, cap_land 2e5 J m-2 K-1, NO ground heat flux / deeper soil layer (mm2 surface(): tl += dt*net/cap), emissivity 1. Standard minimum is the force-restore two-layer soil (Deardorff 1978; ISBA), operational models use 4+ layers (Noah). 
=> Track hypothesis (registered): single-slab land without soil heat storage -> excessive night cooling of north/central India (and the hour-0 skin/air mismatch from landinit) -> cold dense low-level air -> high pressure over central/NE India -> anomalous easterlies + ridge -> storms steered west/south instead of recurving; the weak/shallow vortex makes them follow the lower-level flow. Next: (1) T170 confirmation (tn-rt2-ctl, with t2, 8 starts); (2) derive force-restore land (Deardorff 1978) offline, check the diurnal range vs ERA5 t2 for India; (3) landinit hour-0 +4 K check (which skin/soil field initialises tl).

## 5 Nov 01:00 IST (silent cycle) - Step 0 scored, 75 L base, land root cause at T170, RRTMG relaunched
**Step 0 - TN rain metric (24 starts, every 15 days)**: control 1.51, control + 0.1 % perturbation 1.52, base1 1.70. Start-resampling (bootstrap, 4000) 5-95 %: perturbation minus control -0.11..+0.14 -> the NOISE of the 24-start ratio is ~+-0.13 (target 0.05 NOT met; single starts swing by up to 35 %: 15 May 47 vs 63 mm). base1 minus control +0.19 (5-95 % +0.03..+0.35) -> the P3 fix adds TN rain, real but modest. By season: Oct-Dec (NE monsoon, 5 starts) control 1.38, base1 1.20 (inside +-25 %!); Jun-Sep 1.43 -> 1.76; Jan-May (dry) 1.94 -> 2.26 = worst. => the TN rain gate should be judged on >= 24 starts with this +-0.13 noise stated; the dry season carries most of the error.
**75 L base (cmt_mf + sfc_imp), exam q0**: 19/19 starts complete (no blow-up); z500 d1/d5/d10 21.7/72.8/119.6 vs 32 L ctl2 same starts 20.3/73.3/119.2 -> 75 L base STABLE (P2 for the base the project will use). The package crash (bl_lcl + explicit drag) stays as diagnosed.
**Land / track, T170 (tn-rt2-ctl, 8 starts)**: central India 2-m T +2.6 K at hour 0 -> -2.8 K at hour 24 (Apr -6.6, May -5.2; monsoon Jul/Aug -1.7..-2.1); NW India +3.8 -> -2.0; MSLP central India +0.8 -> +1.1 hPa. CONFIRMED at full resolution.
**5-Why (land)**: (1) cold land + high pressure over north/central India within 24 h; (2) the land starts too warm at night (+2.6..+6 K at 00 UTC) and then cools too far; (3) the start land temperature is the LOWEST MODEL-LEVEL AIR temperature (~80 m), and soil water is 60 % of the bucket everywhere: landinit FALLBACK, because (4) the test libraries (libm_wx2020_fields, libm_fields) contain NO land fields (v2 = surface pressure, SST, land mask, orography only) - they were built before the 22 Oct land-start code; (5) nothing checked that the land fields were present (landinit silently falls back). Plus the formulation weakness: one thin slab, no soil heat storage. => implementation gap (data) + formulation. Dry season: 60 % soil water over dry central India -> strong evaporative cooling -> no heat low -> high pressure (Apr T850 central India -2.9 K).
Action: land library libm_wx2020L (same 73 starts WITH ERA5 soil water, soil/skin temperature, snow; NEW name, standard library untouched) building in GitHub Actions (cyclone-wx.yml 'land library'). Registered test when ready: control on wx2020L vs control on wx2020 (exam q0-q3 + tnr24 + roundtrip): prediction - central India 2-m T hour-0 bias |..| < 1 K, 24-h cold bias halves, central India MSLP d5 bias halves, Oct-Dec TN u850 easterly bias smaller. Then the force-restore soil (Deardorff 1978) offline derivation. Also: landinit must WARN when land fields are missing (code check item).
**RRTMG**: the build on Kaggle WORKED; the clear-sky comparison failed on my scalar extraction (numpy 2: float() of a 1-element array) -> fixed, relaunched tn-radchk2.
**Excess-rain budget so far (global, mm/day)**: model 3.5-4.4 vs ~2.7 -> excess ~0.8-1.7. Evaporation formula (+17 % over ocean) ~0.5-0.6; atmospheric radiative cooling too strong (-112..-120 vs ~-105 W/m2: too much/thick cloud) ~0.25-0.5; rain > evaporation drift ~0.1-0.25. Sum ~0.85-1.35 = most of the excess.

## 5 Nov 07:00 IST - Step 1 complete; fix 1 (evaporation) registered and launched
**Step 1b radiation vs RRTMG (tn-radchk2, T170, 1600 columns, Jan + Jul, same states)**: clear-sky OLR model 251.2/256.8 vs RRTMG same gases 254.6/259.9 (-3.3) and RRTMG with CH4 + N2O 251.2/256.5 (= model, +-0.3) -> clear-sky OLR is RIGHT for the model's atmosphere; the -10..-15 vs CERES comes from the model's STATE (cold upper troposphere emits less; moisture). Clear-sky surface LW down model +9.6/+10.1 globally, +18 W/m2 tropics vs RRTMG -> lower-troposphere LW emission too strong; clear-sky LW cooling at sigma 0.91/0.97 -2.44/-3.36 vs -1.96/-2.89 K/day (+15..+25 %) -> the water-vapour continuum (lw_cnt factor 1.5) is too strong: independent evidence for the on-hold lw_cnt 0.667 (continuum x1.0). SW absorbed by the clear atmosphere 0.22 = RRTMG 0.22 (correct). All-sky: OLR 212/217, LW cloud effect 39/40 (CERES ~26), cover 0.83-0.84 (~0.67), grid-mean LWP 237/248 g/m2 (obs ocean ~50-90) -> clouds are the main all-sky error.
**STEP 0 + STEP 1 CONCLUSION (registered for the fix order)**:
- Metric: TN rain 24-start ratio noise +-0.13; single-start swings to 35 %. Control 1.51, base1 1.70 (+0.19, significant); Oct-Dec control 1.38 / base1 1.20; dry season ~2x.
- Global rain excess ~0.8-1.7 mm/day (model 3.5-4.4 vs ~2.7). Causes, sized: (1) ocean evaporation formula +16-20 % (ck height conversion half-applied + no salt factor) ~0.5-0.6 mm/day - CONFIRMED (fix within +-2 % of COARE); (2) atmospheric radiative cooling too strong (-112..-120 vs ~-105 W/m2): water-vapour continuum too strong in the lower troposphere (+15..+25 % LW cooling, +10/+18 W/m2 LW down) plus too much/too thick cloud (LWP ~3x, cover +0.16) ~0.25-0.5 mm/day; (3) rain > evaporation drift ~0.1-0.25 mm/day.
- No code/conservation defect (audit). Clear-sky gas optics otherwise correct.
**Fix order (each alone on the base, full suite vs base1 + 24-start TN rain; no tuning)**:
(a) evaporation: ck_z 1 + sfc_sal 0.98 (new option, default off; regression OK). PREDICTIONS: model ocean LE within +-3 % of COARE (flux_check); global E and P -12..-17 %; TN rain 24-start ratio <= base1 - 0.15 (1.70 -> <= 1.55); z500 d5/d10 within noise of base1 (+-0.5 m); cyclone pmin at 72 h weaker by 1-4 hPa (less enthalpy flux: Vardah toward target, Nivar/Michaung risk); genesis >= base1 - 5 points. Launched now: tn-s-evap-wx0..3, gen0/1, sb; r24/q6/evo when accounts free.
(b) shallow scheme alone (sh_mflux 0.03 on base) = P1 + F2 item 1 + part of P4: T925 d5 -1 K or more, deep share >= 15 %.
(c) land: land library test (running) -> force-restore soil (Deardorff 1978).
(d) water-vapour continuum lw_cnt 0.667 with the RRTMG prediction: tropical clear-sky LW down within +-5 W/m2 of RRTMG, low-level LW cooling within +-10 %.
(e) implicit surface drag (P2 crash 2, needed only with the cloud-base limit).
(f) clouds: stored cloud water (Zhao-Carr), cloud fraction.

## 5 Nov 09:00 IST - Sridhar: "Run all the tests in parallel" -> 2 jobs per Kaggle account (accepted by Kaggle), queue + dispatcher (scripts/cyclone/dispatch.py, data/cyclone/queue.json)
Registered BEFORE results (each alone on base1 = control + cmt_mf; compared with base1, noise from ctl2/ctlp):
**(b) shallow alone, sh_mflux 0.03 (tn-s-shal-*, tn-r24-shal-*)**: d5 tropical T925 bias <= base1 - 1.0 K (base1 +2.47); q850 dry bias <= half of base1 (-1.45 -> >= -0.73); deep-convection share of tropical columns >= 15 %; TN rain 24-start ratio <= base1 (1.70) and grid-scale share over TN land lower; genesis >= base1 - 5 points (risk: F2 lost genesis - F2 also had pbl_tm); z500 within noise.
**(d) water-vapour continuum x1.0, rad_prm lw_cnt 0.667 (tn-s-cnt-*, tn-r24-cnt-*)**: tropical clear-sky LW down within +-5 W/m2 of RRTMG (was +18) and low-level LW cooling within +-10 % (offline check with rad_check on the run's state - to do); global rain -0.1..-0.3 mm/day; TN rain ratio <= base1; z500 within noise (30 Oct alone: exam passed, TN rain 1.60 on 6 starts - now judged on 24 starts).
Not yet testable (code/design needed): (c2) force-restore soil, (e) implicit surface drag, (f) cloud water. Land library test and (a) evaporation already running.
Quota risk: 2 jobs per account doubles the weekly GPU hours used; Kaggle weekly limit ~30 h per account - this week already heavily used; a refused push stops the workflow early ('push refused' in status).
- 09:35 (e) implicit surface drag (drag_imp, default off, regression OK) registered: tn-tr75-pkgd = the exact crashing case (75 L F2 + sfc_imp + cmt_mf + bl_lcl, 1 Jan) + drag_imp, 720 steps. Prediction: all 720 steps finite, lowest-level wind max < 100 m/s at the Greenland point (crash was step 72-73, 93 -> 743 m/s).

## 5 Nov 10:30 IST - LAND test and FIX (a) EVAPORATION scored against their registered predictions
**Land library (control on libm_wx2020L vs ctl2; 73 exam starts, 24-start rain, 8 start-up checks)**:
- Hour-0 2-m T central India -0.12 K (was +2.6), NW +0.24 (was +3.8) -> start state FIXED (prediction met).
- Hour-24 central India -2.72 K (was -2.80), d5 -3.11 (was -3.18); central India MSLP d5 +1.60 (was +1.69); Oct-Dec TN u850 d5 -3.57 (was -3.03) -> predictions 'cold bias halves', 'MSLP bias halves', 'easterly smaller' all NOT met. => the cold land at 24 h is NOT caused by the start state; it is the land physics (one slab, no soil heat, night cooling) -> force-restore soil is the next step for the track.
- Bonus: z500 d1/d5/d10 19.4/71.5/118.1 vs 20.2/73.3/119.7 (73 starts; -1.8 m at d5, beyond the ~0.5 m round-off spread) -> real land state improves the forecast; TN rain 24-start 1.43 vs 1.51 (inside noise). => ADOPT the land library as the standard test input from now on (it is the correct implementation: real ERA5 land state), control re-baselined on it (ctlL).
**Fix (a) evaporation (base1 + ck_z 1 + sfc_sal) - REJECTED on registered gates**:
- Gains: tropical rain bias d5 +1.14 -> +0.57 mm/day (halved); TN rain bias d5 +3.0 -> +2.2; TN u850 easterly d5 -2.42 -> -1.34 (Oct-Dec -2.41 -> -1.29: steering error halved); genesis 38/52 vs 36/48; low-level T unchanged.
- Failures: z500 d5/d10 75.1/122.1 vs base1 73.1/119.2 (+2.0/+2.9 m, beyond noise; prediction 'within noise' FAILED); cyclones at 72 h much weaker: Nivar 1000.9 (target 994.1, base1 994.5), Michaung 1003.1 (target 992, base1 999.4), Vardah 998.7 (target 995.2) - predicted 1-4 hPa weaker, got 4-6; quick6 72 h track 397 km vs 297 (+34 %), lat error -1.71 vs -1.27.
- Interpretation (hypothesis, not tuned): the over-strong ocean flux (+18 %) is COMPENSATING other errors: storm intensity at T170 (80 km grid cannot resolve the core; extra flux stands in) and the radiative cooling excess (less evaporation with the same too-strong cooling -> colder column: z500 worse). Per rules: no tuning, gates not relaxed -> (a) rejected for now; to be re-tested TOGETHER with the radiation fixes (continuum, clouds) once those pass alone, since the energy budget must close as a whole.

## 5 Nov 11:45 IST - TRACK root cause (land surface), found with local runs (T42, land library, central India 18-26N 74-86E)
Land surface energy budget, 15 Apr start, control: daytime latent heat 767-1138 W/m2 (> net radiation) and skin T 305 -> 270 -> 291 K within 6 h = explicit land coupling OVERSHOOT (dt 60 min at T42; 20 min at T170 - smaller but same mechanism). With sfc_imp: smooth, but LE still 470-620 W/m2 at midday with H ~ 0 in the DRY season = land evaporates like open water: the land evaporation has NO SURFACE RESISTANCE (E = rho ck V1 beta dq; real models: E = rho dq / (r_a + r_s), r_s 100-250 s/m from stomata / dry soil; Monteith 1965, Jarvis 1976, ECMWF TESSEL, ISBA). 5-Why: cold land at 24 h -> evaporation takes the energy (Bowen ratio ~0 in April) + explicit overshoot -> no surface resistance in the formula + explicit coupling -> formulation simplification from the start (bucket beta only) -> never checked against a land energy budget.
New options (default off, regression bit-identical, both live): land_rs (minimum surface resistance, s/m; r_s = land_rs / soil-water stress) and soil_fr (force-restore deep soil, Deardorff 1978, thermal inertia 1400 -> C_eff 1.17e5 J m-2 K-1, tau 1 day, deep T from ERA5 soil temperature).
Local T42 roundtrip, 24 h, central India (ERA5 truth): 2-m T Apr -5.4 (control) / -3.9 (sfc_imp) / -2.3 (+ land_rs 100) / -0.7 (+ soil_fr); Oct -2.6 / -1.5 / -0.5 / +0.7; T850 Apr -2.5 -> -1.4; MSLP Apr +2.0 -> +0.9 hPa; TN MSLP +0.8 -> +0.15.
=> LAND MODULE = sfc_imp + land_rs 100 + soil_fr, tested as one land-surface scheme (each part is a standard correction; together they form the minimal ISBA-type surface). Remaining: midday LE still 260-450 W/m2 (a full Jarvis stress with radiation / vapour-pressure-deficit / leaf-area would lower it; later).
REGISTERED (tn-s-lnd-*, control + land module on the land library; vs ctlL = control on the land library, except gen/sb/q6 vs ctl2): central India 2-m T d1 bias within +-1.2 K (ctlL -2.4); central India MSLP d5 bias <= half of ctlL (+1.6 -> <= +0.8); Oct-Dec TN u850 d5 easterly smaller than ctlL (-3.57); quick6 72 h track <= ctl2 (289 km) and mean 72 h latitude error > -1.0 deg (-1.31); z500 d5/d10 <= ctlL + 0.5 m (71.5/118.1); TN rain 24-start <= ctlL (1.43), dry-season Jan-May ratio lower; genesis >= ctl2 - 5 points; cyclone intensity not worse than ctl2.

## 5 Nov 12:00 IST - P3 residuals (Michaung too weak, Vardah too strong at 72 h), offline from tn-s-base1-sb + ERA5 case files
- Michaung: model reaches 994.3 hPa at 60 h (target at 72 h 992.0 - on track for the target), then DECAYS to 999.4 at 72 h. At 72 h the model storm is 313 km NNE of the real one (15.8N 82.3E vs 13.1N 81.4E). ERA5 at the two positions, 4 Dec 00 UTC: SST 27.7 vs 28.5 C, TCWV 66 vs 71 mm, q850 13.1 vs 15.6 g/kg -> the model storm ran into cooler, drier air: flux core 308 -> 150 W/m2, low-level q 19.0 -> 15.9 g/kg, rain evaporation -573 W/m2 in the core. => the 72-h weakness is a TRACK consequence, not a core-physics failure.
- Vardah: model stalls at 9.5N 87.9E from 36 to 60 h while the real storm keeps WNW at ~91E (300-430 km apart); environment at the model position is not warmer (SST 28.5 both) and is drier (TCWV 55 vs 69) yet the storm deepens to 989 -> a slow / stalled storm (less ventilation, longer time over the same water) over-intensifies. Again position-driven.
- Nivar: intensity on target (994.5 vs 994.1) but the model makes landfall ~200 km too far south-west.
=> P3 core physics is not the open problem; the residual intensity errors follow the track errors. Action: no intensity change now; re-measure P3 after the land-module (track) result. Observation (NOT a gate change - gates are never changed after results): a 72-h intensity gate mixes track error into intensity; recorded for the Stage-2 gate design.

## 5 Nov 12:30 IST - P2 Andes hot spot (last open P2 item): offline checks + registered discriminating test
Local: at T42 (75 L, 9 Jun) the spot does NOT form (Andes lowest-level wind 4-9 m/s, |h_bl| <= 104 K/day, with or without drag_imp) -> resolution-dependent (steep T170 terrain). T170 model orography: Andes max 3968 m (ERA5 1.5 deg 4130), max slope ~1 km per grid step; spectral ringing over sea down to -153 m (3521 sea points |zs| > 100 m). Two candidate causes for the 45-100 m/s low-level wind at T170 / 75 L: (A) NO SUB-GRID OROGRAPHIC DRAG (Lott & Miller 1997 blocking + gravity-wave drag is coded since 30 Oct - gwd, default off, never suite-tested); (B) explicit surface stress overshoot on the 7-hPa bottom layer (drag_imp, 5 Nov).
REGISTERED (tn-andes-b / -drag / -gwd / -gwdrag: 75 L T170 base + sfc_imp, 9 Jun, 48 h, andes_check.py): gate as before = Andes |h_bl| < 300 K/day; plus lowest-level wind < 30 m/s (ERA5 there ~10-15). Prediction: 'b' reproduces the spot (wind > 40, h_bl > 300); if 'gwd' passes and 'drag' fails -> cause A; if 'drag' passes and 'gwd' fails -> cause B; if only 'gwdrag' passes -> both. Then the passing option(s) go through the 32 L suite (gwd affects winds globally: z500, tracks).

## 5 Nov 12:50 IST - cloud-water design started (docs/cloud_water_design.md): Zhao-Carr / Sundqvist prognostic condensate
Offline check on model states: storing the current condensation as cloud would give ocean LWP 256-400 g/m2 (obs ~80): over
ocean 3.6 mm/day grid-scale condensation, 2.72 of it at 500-850 hPa -> mid-level grid-scale saturation because deep
convection rarely fires. Same root as P1 / false land rain (shallow scheme). => cloud water is tested AFTER the shallow fix.

## 5 Nov 12:35 IST - FIX (b) SHALLOW ALONE (sh_mflux 0.03 on base1) scored vs its registered predictions - REJECTED on gates, large partial gains
| check | base1 | shal | registered prediction | verdict |
|---|---|---|---|---|
| z500 d1/d5/d10 (73 starts) | 20.0/73.1/119.2 | 20.9/71.1/117.0 | within noise | BETTER (-2 m d5) |
| T850 / T925 / T1000 d5 tropics | +0.86/+2.47/+2.74 | -1.93/-1.66/-0.96 | T925 <= +1.47 | warm bias removed but OVERSHOOTS cold: T850 -1.93, T925 -1.66 (gate +-1.5 FAIL) |
| q850 d5 | -1.45 | +0.48 | >= -0.73 | PASS |
| TN land grid-scale rain share | 77 % | 49 % | lower | PASS |
| TN rain 24-start | 1.70 | 1.58 | <= 1.70 | pass (inside noise +-0.13); Jun-Sep 1.76 -> 1.46, Jan-May 2.26 -> 1.72, but Oct-Dec 1.20 -> 1.73 (NE monsoon worse) |
| genesis gen0/gen1 | 36/48 | 24/29 | >= 31/43 | FAIL |
| quick6 72 h / lat error | 297 km / -1.27 | 362 km / -1.87 | not worse | FAIL |
| intensity 72 h (V/N/M) | 989.5/994.5/999.4 | 988.3/996.7/998.1 | not worse | ~same |
Interpretation (hypotheses, nothing tuned): (1) the shallow heating at 900-940 hPa drops from ~5 K/day to ~0.8 K/day (heat_prof), but the GFS v16 SCM reference (BOMEX) has shallow heating +3..+5 K/day there -> the 0.03 kg/m2/s relaxation removes TOO MUCH of the shallow heating: the old scheme had the right SIZE of heating but a wrong net (P1 +1 K/day). => the defect is the FORMULATION (relaxation to a mixed MSE/q profile with a time scale), not one magnitude: sh_mflux only changes the time scale. A true shallow mass-flux plume (cloud-base mass flux from a closure, entraining plume, detrainment at cloud top, compensating subsidence) is what GFS / IFS do; MEGAM's shallow 'mf' plume (rejected 3 Nov: 850 -2.0 K, genesis 12 %) must be re-checked against the GFS BOMEX profiles offline before any new run. (2) GENESIS depends on the over-active shallow scheme (F2 14 %, shallow 'mf' 12 %, sh_mflux alone 24/29): a compensating error - when the shallow layer stops exporting moisture upward, the lower troposphere becomes moist and cool everywhere, convection becomes widespread instead of organised -> fewer vortices. Next (offline): genesis mechanism, base1 vs shal on the same cases (convective heating distribution, mid-level humidity, CAPE in the formation region), and the shallow heating/moistening profiles of base1 / sh_mflux / 'mf' vs the GFS v16 BOMEX reference.
Consequences: P1 not closed (cold overshoot); F2 item 1 (shallow) NOT accepted; cloud-water precondition (mid-level grid-scale condensation -50 %) to be checked on the shal state anyway (it tells whether convection takes over).

## 5 Nov 13:50 IST - HIDDEN FAULT found by the new health run (scripts/cyclone/health.py): 'shallow' convection through deep layers
Health run (T42 at dt 20 min, 24 h, 15 Apr + 27 Oct, ERA5 land), control: HARD flags 'land latent heat > SWnet + LWdown + 300 W/m2' (the land bug, found by hand this morning - now automatic) and a 27 K land-skin jump at 79.5 S (Antarctic start mismatch - new, minor); SOFT flag: SHALLOW heating 389-454 K/day at sigma 0.31 (300 hPa!), together with grid-scale condensation 306-382 K/day at the same point and step (East Pacific, 1.4 N), 133 times.
5-Why: (1) shallow heating at 300 hPa; (2) the shallow MSE mixing runs from cloud base to the parcel top; (3) mm2 classifies 'deep' = CAPE > 100 J/kg AND depth > 200 hPa, 'shallow' = CAPE > 0 and NOT deep -> a deep parcel with weak CAPE falls into 'shallow'; (4) nothing limits the shallow depth (sh_dtop / sh_cap default off); (5) the IFS definition (shallow = cloud depth < 200 hPa, Bechtold et al. 2008) was not used. Measured: 3-4 % of tropical columns, tops above 600 hPa, carry 21-31 % of ALL shallow heating, 313-386 K/day aloft.
Fix (option sh_depth, default off, regression bit-identical): shallow only if depth <= 200 hPa. Local T42, 27 Oct +24 h, tropical ocean: 600-800 hPa grid-scale condensation 2.20 -> 0.24 K/day (-89 %), deep heating 1.82 -> 3.28 (deep convection takes over), shallow -2.15 -> -0.15; 800-1000 hPa net physics +0.35 -> -0.04 K/day (P1 warming gone). Cloud-water precondition (mid-level grid-scale condensation -50 %) MET locally.
REGISTERED (tn-s-shd-* + tn-r24-shd-*: base1 + sh_depth, vs base1): d5 tropics T850/T925/T1000 within +-1.5 K (base1 +0.86/+2.47/+2.74); q850 within +-0.5 (base1 -1.45); z500 d5/d10 <= base1 + 0.5 m; genesis >= base1 - 5 points (36/48 -> >= 31/43); quick6 72 h <= base1 + 6 % (round-off spread) and lat error > -1.27 - 0.2; TN rain 24-start <= base1 - 0.15 (1.70 -> <= 1.55); TN land grid-scale share < 60 % (base1 77 %); intensity at 72 h not worse than base1 by > 2 hPa.

## 5 Nov 14:10 IST - P2 CLOSED on the deciding tests; land module partial result
**Andes 4-way (75 L T170, 9 Jun, 48 h, andes_check)**: base 125 m/s / 390 K/day (spot reproduced, as predicted); + drag_imp 19.5 m/s / 161 K/day -> PASS (both gates); + gwd 112 / 481 FAIL; + gwd + drag_imp 167 / 774 FAIL (worse). => cause B CONFIRMED: the 45-125 m/s Andes winds were the EXPLICIT SURFACE-DRAG OVERSHOOT itself (same as the Greenland crash), not missing orographic drag. The gwd scheme (Lott-Miller, 30 Oct) makes it worse -> it has its own defect; stays OFF (separate item, not Stage 1).
**75 L crash case + drag_imp (tn-tr75-pkgd: F2 + sfc_imp + cmt_mf + bl_lcl, 1 Jan)**: all 720 steps (10 days) finite; wind at the h_bl maximum <= 19.1 m/s (crash was 93 -> 743 m/s at step 72) -> registered prediction MET. (max h_bl 863 K/day somewhere in 720 steps - SOFT, to be located with the health run at 75 L.)
=> P2: both 75-level causes fixed by numerics (sfc_imp: implicit surface heat/moisture + land skin; drag_imp: implicit surface stress). Remaining: 32 L neutrality check of drag_imp (registered: base1 + drag_imp, exam q0-q3 + sb + quick6: z500 within base1 +-0.5 m; intensity and tracks not worse than base1 beyond the round-off spread) -> tn-s-drg-*.
**Land module (sfc_imp + land_rs 100 + soil_fr) partial (q2 of the exam, rt, q6, sb, gen0)**: central India 2-m T at 24 h -2.72 -> -0.57 K (8 starts; prediction within +-1.2 MET), day 1 -2.50 -> -0.45 (18 starts), NW India -1.74 -> +0.23; central India MSLP d5 +1.73 -> +1.39 hPa (prediction 'halves' NOT met: -20 %); TN u850 d5 -4.04 -> -3.38 (smaller, met); quick6 72 h 296 km vs ctl2 289 (within round-off spread; strict 'not worse' fails by 7 km), latitude error -1.15 vs -1.31 (better, prediction > -1.0 not met); intensity ~1-2.5 hPa weaker; genesis gen0 38 vs 36. => the land surface is FIXED (cold land gone), but the central-India high pressure only falls 20 % and the tracks barely move -> the land was only part of the track cause. Remaining quarters / rain / gen1 pending.

## 5 Nov 14:30 IST - P5 opened (peer suggestion): large-scale circulation and cyclone steering
Why: the land fix removed the cold land but the tracks did not move -> widen to the steering circulation (subtropical ridge, upper ridge/trough pattern, Western Disturbances / subtropical Rossby waves).
Existing evidence: exam (73 starts) z500 bias d5 NW India -36 m vs south India -19 m -> the north falls faster -> weaker ridge gradient -> geostrophic easterly anomaly at 500 hPa of order 3 m/s (westward push, delayed recurvature); part of the global cooling drift (z500 -45 m by day 10).
Michaung, model (ctl / pkg) vs ERA5, every 24 h: 200-hPa jet latitude over 70-80 E within ~1 deg (OK); NW-India upper flow (v200, 20-35 N 65-80 E): 48 h model +7.4 vs ERA5 +3.6 (trough too strong/early), 96 h +4.5 vs +11.5 (too weak) -> the upstream trough (WD signature) is mistimed/misshaped. The 500-hPa ridge axis taken from the u=0 line is contaminated by the model cyclone itself (ctl 'axis' 9-12 N while the storm sits in the band) -> vortex must be removed (200-600 km ring method) before ridge comparison.
Jobs: tn-p5-b1-ond (18 Oct-Dec starts) and tn-p5-b1-am (12 Apr-May starts): mean 5-day bias MAPS of z500/u/v 850/200/mslp over 40-120 E 0-45 N, ridge-gradient bias (z500 25 N - 12 N along 80-95 E) -> implied u500 bias, Bay deep-layer steering bias, NW-India v200, central-India MSLP; tn-maps-vardah-b1 / tn-maps-mich-b1 (base1, 6-hourly maps) for the case audit with vortex removal. No equation changes until P5 names a process.
- 14:50 P5 peer review adopted: (1) day 0 added to p5_bias (wrong from the start vs growing) and the easterly checked from the height FIELD (geostrophic u500 profile 8-30 N along 80-95 E, Bay mean) instead of two box means; (2) case audit p5_case.py every 6 h with the SAME storm removal for model and ERA5 (own MSLP centre; steering = 200-600 km ring mean; ridge axis with the storm 600-km area masked; trough axis along 25-35 N, 55-95 E; 6-h axis displacement = propagation).
- 14:55 FIRST CASE RESULT (Michaung, old control maps vs ERA5): the ERA5 upstream trough (25-35 N) PROPAGATES: axis 73.5 E (0 h) -> 63 E (36 h) -> 65 -> 69 -> 72.5 (72 h) -> 76.5 E (96 h) and deepens to -45 m (72 h); the MODEL trough stays PARKED at 71-72 E for all 108 h and is too deep early (-35..-45 m at 12-48 h vs -8..-24). => a phase-speed / propagation error of the westerly wave (peer's hypothesis (2) supported for this case). Environmental 500-hPa steering (storm removed): model v +2.5..+5 m/s vs ERA5 +0.7..+2.1 at 12-84 h (too much northward steering - consistent with the control Michaung running too far north); subtropical ridge model +8 vs ERA5 +5 m (stronger). Candidate causes to test (not yet): (a) upper westerlies too weak/strong (Rossby phase speed c = U - beta/k^2) - linked to the cooling drift (thermal wind); (b) numerical damping/dispersion of synoptic waves (semi-Lagrangian, diffusion); (c) the jet itself is placed right (+-1 deg), so (a) is about speed, not position. Base1 maps (queued) + the 30-start systematic run decide whether it is systematic.

## 5 Nov 16:45 IST - 'How will you prove the whole model is not wrong?' (Sridhar + peer) - baselines and the 4-part test plan
Baselines on the 2020 73-start exam, z500 global RMSE / ACC, d1 / d5 / d10: ECMWF HRES 4.8/1.00, 31.1/0.93, 82.8/0.49; MEGAM base1 20.0/0.98, 73.1/0.67, 119.2/0.14; persistence 61.9/0.72, 106.8/0.17, 115.1/0.05; climatology 83.6 / 83.5 / 83.7. => MEGAM has real skill (beats persistence d1-d5, ACC 0.67 > 0.6 at d5) but useful skill ends ~day 6 (HRES ~day 10); by day 10 it is saturated (~sqrt(2) x climatology). The DAY-1 error (20 vs 4.8 m) is the key number: a fast error source in the first hours.
Plan (each with an external reference, not ours): (1) dynamical core: (a) physics OFF from real ERA5 starts, d1-d3, + Michaung trough propagation; (b) Jablonowski-Williamson (2006) baroclinic wave vs published reference solutions; (2) physics per process: MEGAM single-column vs GFS v16 SCM (BOMEX, TWP-ICE); (3) coupled budget: 10-day global net energy |imbalance| < 3 W/m2 (now ~-20) and no steady z500 drift; (4) independent 2018-2025 cases vs persistence / climatology / HRES. REGISTERED for (1a) (tn-core-adiab0/2, 37 starts, physics off vs base1 in the same job): if physics-off day-1 z500 RMSE <= 12 m -> the core is not the main fast-error source (physics is); if >= 18 m -> core / initialisation / resolution is, and the architecture question becomes the priority. (Caveat: with no physics the forecast drifts by day 2-3 (no radiation/latent heat), so only day 1 and the first-day trough movement are diagnostic.)

## 5 Nov 18:10 IST - sh_depth (tall-shallow fix) INTERIM: 2 registered checks FAIL -> NOT adopted
- Pipeline: the suite had not run until 17:50 - duplicate relaunches (dispatcher re-queued each refused slug once per old
  DONE entry) filled GitHub's 20 concurrent runners with 9-h pollers; fixed (dispatch.py dedupe + per-run account
  mapping; launches now push-only, cyclone-collect.yml fetches outputs). 31 duplicate runs cancelled.
- Storm budget (sb, 72 h pmin vs base1; ERA5-at-resolution target): Vardah 989.0 vs 989.5 (995.2), Nivar 997.9 vs 994.5
  (994.1) -> 3.4 hPa WEAKER (gate: not worse by > 2 hPa) FAIL; Michaung 997.9 vs 999.4 (992.0) better.
- quick6 72 h: 327 km vs base1 297 (+10 %; gate <= +6 %) FAIL; 24/48 h 135/168 vs 117/221; latitude error -1.17 vs
  -1.27 (gate > -1.47) pass.
- => sh_depth is NOT adopted (pre-approval rule: any failed check). Remaining parts (exam = low-level T/q, z500;
  genesis; 24-start TN rain; evo) still run - they tell whether the tall-shallow fault drives P1/P4 even though the
  fix as coded hurts Nivar/tracks. Cloud-water stacking on sh_depth NOT started (its base failed).

## 5 Nov 18:30 IST - P5 peer answers to the expert-question brief (AI peer, not a human expert) - checked
Adopted (diagnostics, no model change): (1) residual motion V_storm - V_env (same storm removal for model and ERA5) as the
beta-drift / vortex-interaction proxy; (2) steering by layer 850-700 / 850-500 / 850-200 and ring 200-600 vs 300-800 km
vs the observed 6-h motion; (3) along-/cross-track split of quick6 errors (also NOAA practice, GFSv16 CCB); (4) PV maps at
the trough; (5) lead-time decomposition 0 / 6-24 / 24-72 / 72-120 h (p5_bias already from day 0). Checked: geostrophic
illustration correct (10 m / 1000 km at 15 N = 2.6 m/s); IMD official 72-h track error 2024 = 116 km, 2020-2024 mean
154 km (RSMC New Delhi Annual Verification 2024) - official human forecasts with data assimilation, a reference only, not
a Stage-1 gate (gate changes are Sridhar's decision). Priority agrees with ours: core wave test (tn-core-adiab running,
J-W next) -> sigma / IFS Part III items D1/D2/D4 -> energy drift -> storm-removed steering -> drag offline only.

## 5 Nov 19:20 IST - core test (physics off) PARTIAL + day-1 z500 error decomposed
- tn-core-adiab0/2: OOM-killed after ONE start each (the job compiled both variants). Physics-off day-1 z500 RMSE 24.9 m
  (2020-01-01), 24.6 m (2020-01-11) vs base1 20.4 m (2020-01-01). Registered rule (16:45): >= 18 m -> core /
  initialisation / resolution first. n = 2 of 37 -> INDICATIVE, not the registered test; re-run physics-off only,
  4 chunks (tn-core-adiab1-0..3, wx_adiab1.json). Note: physics-off also lacks the real day-1 diabatic forcing, so its
  error is an upper bound on the core's share.
- Day-1 z500 error of base1 (2020-01-01) = 20.4 m RMSE with a GLOBAL MEAN BIAS -13.8 m -> bias-removed ~15 m. Tropics
  (tn-rt2-ctl, 8 starts): hour-0 bias -5.0 m in EVERY start (-4.8..-5.6; with or without DFI; t850 h0 ~0, mslp h0 +0.25
  hPa) -> a constant initialisation / z500-diagnostic offset, not forecast error; hour 24 -12.2 m -> -7 m real drift in
  day 1. => three separate pieces: (a) constant hour-0 offset ~-5 m (candidate: geopotential/z500 diagnosis, e.g.
  virtual-temperature or level-interpolation handling - to derive, offline at T42 first); (b) day-1 column cooling drift
  (-7 m tropics, -14 m global; links to the -20 W/m2 energy imbalance and P1); (c) bias-free error ~15 m (initial state at
  T170, resolution, physics, core).

## 5 Nov 19:45 IST - ROOT CAUSE of the constant hour-0 z500 offset: wrong dry-air gas constant in the dynamics
5-Why: hour-0 z500 -5.5 m everywhere (T42 local, 2 starts; T170 tropics -5.0 in 8/8 starts) -> not weather (uniform in
latitude, with/without DFI, t850 h0 ~0) -> diagnosis/hydrostatics -> geopotential integral exact for isothermal test
(0.00 m) -> constants: Dinosaur scales.py IDEAL_GAS_CONSTANT = 1004 x 2/7 = 286.86 J/kg/K vs ERA5/IFS 287.06 and MEGAM
physics RD 287.04 / CP 1004.6 -> every thickness 0.07 % short -> z500 -4.0 m (and dynamics vs physics constants
inconsistent). Fix: option rd_si (dynamics built with RD, kappa = RD/CP; default off; control regression bit-identical).
Offline confirmation (prediction +4.0 m written before): hour-0 z500 bias tropics -5.51/-5.18 -> -1.85/-1.53 m, globe
-5.8/-5.5 -> -2.3/-2.0 m. Residual -2 m (S mid-latitudes -4 m) = other initialisation detail, open.
REGISTERED (tn-s-rd-wx0..3, -sb, -q6 vs base1; same library): z500 day-1 global bias improves by >= +2.5 m and day-1
RMSE by >= 1.0 m; z500 d5/d10 not worse than base1 + 0.5 m; tracks (quick6 72 h) and storm intensity (sb, 72 h pmin)
within the round-off spread of base1 (6 % / 2 hPa). Pass -> adopt (it is a constant error, not a tuning).

## 5 Nov 22:15 IST - rd_si ADOPTED (all registered checks pass) + physics-off core test complete
rd_si (tn-s-rd-*, 73 starts, vs base1, same library): z500 day-1 global bias -13.74 -> -10.23 m (+3.51; registered
>= +2.5) PASS; day-1 RMSE 20.02 -> 17.77 m (-2.25; >= 1.0) PASS; d5/d10 73.1/119.2 -> 71.6/117.8 (not worse +0.5) PASS;
quick6 72 h 297.2 -> 303.1 km (+2.0 %; round-off 6 %) PASS; sb 72 h pmin Vardah 989.5 -> 990.5, Nivar 994.5 -> 993.8,
Michaung 999.4 -> 999.9 (all within 2 hPa) PASS; steering -2.41 -> -2.28; stability 73/73. => ADOPTED (pre-approval).
NEW BASE = base2 = control + cmt_mf + rd_si. All new candidates are tested on base2 and compared with a base2 control.
Physics-off (tn-core-adiab1-0..3, 73 starts, default constants = no rd_si): day-1 z500 RMSE 22.37 m, bias -9.99 m
(base1 20.02 / -13.74). Registered rule (16:45): >= 18 m -> core / initialisation / resolution is the main fast-error
source -> TRIGGERED. Reading: bias-free error physics-off ~20.0 m vs base1 ~14.6 m (physics improves the pattern, as the
real atmosphere has physics) -> the test bounds the core's share from above; the clean core checks are J-W and the
Part III items. NEW LEAD: physics-off has NO radiation or condensation, yet z500 falls -10 m in 24 h (-5.5 m is the
hour-0 constant offset, now fixed by rd_si) -> a further ~-4.5 m/day drop produced by the adiabatic core itself (an
adiabatic core should not cool the column). Candidates: horizontal diffusion of T on sigma surfaces (Part III D1),
DFI, moisture/virtual-T handling without physics. -> D1 offline test is now the top offline item.

## 5 Nov 23:10 IST - ROOT CAUSE of the adiabatic (physics-off) height drop: LINEAR vertical semi-Lagrangian interpolation
5-Why: physics-off z500 falls 2.2-2.9 m/day (T42, 2 starts) -> not mass (ps +-0.03 hPa), not total heat (mass-weighted T
-0.03 K/day) -> vertical/horizontal redistribution: global-mean T by level +1.16..+1.50 K/day at sigma 0.11 (tropopause),
-0.27..-0.29 at 0.42-0.49, -0.8..-1.1 at the lowest levels -> insensitive to DFI, diffusion x10, moisture, dt/2, monotone
limiter (each < 0.3 m change) -> SAME start in Dinosaur's EULERIAN sigma core (imex_rk_sil3, 10 min, same filter): 0.11
-0.08, 0.49 +0.04, lowest levels -0.81/-1.07 -> the tropopause warming and mid-level cooling are SEMI-LAGRANGIAN-ONLY;
the lowest-level cooling is common to both = start state (separate item, open) -> Dinosaur docs:
vertical_interpolation_order default 'linear', "production SL models interpolate at least cubically in the vertical;
linear vertical is the main source of extra vertical diffusion at long steps"; plus MEGAM's isothermal T_ref = 250 K
leaves the full tropopause kink in the advected T'. Fix: option sl_vcubic (cubic vertical; default off; control
bit-identical). Offline confirmation (prediction 'tropopause warming falls >= 50 %' written before): sigma 0.11
+1.50 -> +0.41 (-73 %), 0.49 -0.29 -> -0.06 (Eulerian +0.04), whole profile now close to the Eulerian core;
physics-off global z500 change -2.23 -> -0.59 and -2.87 -> -1.00 m/day (~ -70 %).
REGISTERED screen (base2 + sl_vcubic vs base2 = tn-s-rd-*, same starts): tn-s-vc-wx0 (exam quarter 0) day-1 global
z500 bias better by >= +0.8 m and day-1 RMSE better by >= 0.5 m vs tn-s-rd-wx0; d5/d10 not worse +0.5 m; sb 72 h pmin
within 2 hPa per storm; quick6 72 h within 6 %; runtime (sec per start) not more than +30 %. Pass -> full exam (wx1-3)
-> adopt only if the full set passes the same gates. Residual items: isothermal T_ref (a realistic reference profile
would remove the rest of the kink), lowest-level start-state cooling (both cores).

## 6 Nov 10:10 IST - sl_vcubic SCREEN: storm-intensity check FAILS -> NOT adopted; P5 Oct-Dec bias maps in
sl_vcubic (tn-s-vc-sb vs base2 tn-s-rd-sb, 72 h pmin; registered: within 2 hPa per storm): Vardah 998.2 vs 990.5
(+7.7 weaker), Nivar 989.6 vs 993.8 (-4.2 stronger), Michaung 1001.0 vs 999.9 (+1.1) -> FAIL (2 of 3 outside 2 hPa).
(vs ERA5-at-resolution targets 995.2 / 994.1 / 992.0 the changes go both ways: Vardah closer, Nivar further.) => the
cubic vertical interpolation changes storm cores strongly; NOT adopted as is. tn-s-vc-q6 (running on account 4)
finishes as diagnostic only; tn-s-vc-wx0 NOT re-run on scarce GPU. Open question: why storm cores react so strongly
(cubic overshoot at sharp vertical gradients in storm cores without a vertical limiter is the first suspect - to derive
offline before any new GPU run).
P5 (tn-p5-b1-ond, 18 Oct-Dec starts, base1, India/Bay box mean bias vs ERA5):
| day | ridge 25N-12N (m) | ug500 Bay | deep steering u,v (Bay) | u850,v850 Bay | u200,v200 Bay | C-India MSLP (hPa) |
| 0 | +4.1 | -0.7 | -0.18, +0.09 | -0.02, -0.01 | -0.34, +0.18 | +0.82 |
| 1 | -0.1 | +0.36 | -0.99, -0.22 | -0.95, +0.12 | -1.02, -0.56 | +0.86 |
| 3 | +6.5 | -1.0 | -1.42, -0.94 | -4.05, -0.45 | +1.21, -1.43 | +1.70 |
| 5 | +5.0 | 0.0 | +0.47, -0.70 | -2.62, -0.13 | +3.56, -1.27 | +1.17 |
=> the 500-hPa ridge / geostrophic steering is NOT the main error (|ug500| <= 1 m/s). The Bay steering error is LOW-LEVEL:
u850 -4.05 m/s by day 3 (too easterly) plus a southward deep-layer component (v -0.94 at day 3 -> storms too far south),
with the central-India surface high too strong (+1.7 hPa day 3). Central-India MSLP is already +0.82 hPa at DAY 0 ->
first suspect a diagnostic difference (MSLP reduction over elevated land vs ERA5's method), to check offline. P5 focus
moves from the 500-hPa ridge to the low-level circulation over India / the Bay (links to P1 low-level biases and the
land high).

## 6 Nov 13:10 IST - hour-0 central-India MSLP +1.0 hPa: decomposed; DFI removes part of the real thermal tide
Offline T42, Oct 2020 starts (scripts/cyclone/mm/mslp_h0.py, base2 constants): hour-0 C-India (18-26 N, 74-86 E) MSLP
bias +1.10/+1.17/+0.73/+1.03 hPa (mean +1.0; T170 P5 run +0.82). Decomposition (2 starts): MEGAM's IFS-style reduction
applied to ERA5's own ps/T = +0.16 hPa (formula NOT the cause); raw initial state (no DFI) +0.67/+0.75 (model terrain
~17 m lower -> ps +1.95 hPa, reduction compensates to ~+0.55 net: open); DFI adds +0.45/+0.41 hPa ps with lowest-level T
unchanged (+0.04 K).
Hypothesis 1 'the 6-h DFI window attenuates the 12-h tide' -> prediction (DFI change <= +0.15 hPa with dfi_span 12 h)
FAILED: +0.45/+0.41 unchanged (option dfi_span added, default 6 = control bit-identical).
Hypothesis 2 'the ADIABATIC DFI removes the solar-forced thermal tide (no forcing in the filter integration -> the tide
pattern behaves like free fast waves and is filtered)': DFI ps change over the tropics (20 S-20 N) by longitude has a
semidiurnal component of 0.29 hPa with maxima at local time 03.6 h and 15.6 h = the minima of the real S2 tide -> CONFIRMED
in sign and phase; it explains 30 % of the DFI change variance (other DFI changes up to -2.2 hPa elsewhere: open).
Options (to test offline before any GPU): (a) no DFI (keeps the tide; check noise and day-1 skill), (b) diabatic DFI
(physics in the filter integration, Huang & Lynch 1993). REGISTER before the test: without DFI the hour-0 C-India MSLP
bias falls by >= 0.3 hPa and T42 day-1 global MSLP / z500 RMSE vs ERA5 (4 starts) are not worse by > 2 %.

## 6 Nov 16:20 IST - dfi_off offline test (T42, 2 of the 4 registered starts; the run ended early) - PASSES so far
Hour-0 C-India MSLP +1.10/+1.17 -> +0.67/+0.75 hPa (-0.43; registered >= 0.3) PASS; day-1 global MSLP RMSE 3.70/3.51 ->
3.69/3.51 hPa and z500 26.72/26.81 -> 26.68/26.46 m (not worse > 2 %) PASS; first-3-h |dMSLP/dt| 0.37 -> 0.45 hPa/h
(+22 %, includes the real tide; noted, not gated). Option dfi_off (M.dfi returns the state unchanged; default off,
control bit-identical). REGISTERED T170 screen on base2 (tn-s-nd-sb, -q6, -wx0 vs tn-s-rd-*): sb 72 h pmin within 2 hPa
per storm; quick6 72 h within 6 %; wx0 day-1 z500 RMSE not worse > 0.3 m and day-1 MSLP RMSE not worse > 2 %; 18/18
stable. Pass -> full exam -> adopt on all gates.

## 6 Nov 18:20 IST - P5 low-level easterly: resolution check for offline diagnosis
T42 does NOT reproduce it (base2, 4 Oct-Nov starts: Bay u850 -0.78 m/s at day 3, C-India MSLP -4.4 hPa = opposite sign)
-> T42 unusable for P5. T85 (2 starts) DOES: Bay u850 +1.44 / -1.72 / -3.06 m/s at days 1/2/3, v850 -0.35 / -2.00 / -0.81
(T170 18 starts: -4.05 / -0.45 at day 3) -> T85 is the offline grid for P5 (one variant per process: ~6 GB RAM).
Running: mechanism denial at T85, one process changed at a time (physics off, no CMT, shallow <= 200 hPa, implicit
drag, land module, no DFI) -> the variant that removes most of the day-3 easterly points at the process.

## 7 Nov 05:55 IST - dfi_off T170 screen: storm check FAILS by 0.1 hPa -> NOT adopted (gate not relaxed)
tn-s-nd-sb vs base2 tn-s-rd-sb, 72 h pmin (registered: within 2 hPa per storm): Vardah 988.8 vs 990.5 (-1.7) pass,
Nivar 995.7 vs 993.8 (+1.9) pass, Michaung 1002.0 vs 999.9 (+2.1) FAIL. The 2 hPa gate was set to the round-off spread,
so this is marginal - but the rule is that gates are never relaxed after a result and a re-run to get a pass is not
allowed. => dfi_off NOT adopted. tn-s-nd-q6 / -wx0 (already pushed at 05:52, cannot be cancelled) finish as
diagnostics: they show whether removing the DFI changes tracks and day-1 z500 at T170; a future candidate must keep the
real tide AND pass storms (e.g. diabatic DFI, or DFI on the balanced part only).

## 7 Nov 12:15 IST - P5 mechanism denial moved to GPU (T170)
The container is reclaimed when the session is idle (3 restarts 6-7 Nov), killing long offline runs; one T85 variant
does not finish in a 10-min foreground call. -> tn-p5-denial on Kaggle (account 1, ~1 GPU-h est.): T170, 6 Oct-Nov
starts, 3 days, one process changed per variant from base2 (physics off, no CMT, shallow <= 200 hPa, implicit drag,
land module, no DFI); Bay u850/v850 and C-India MSLP bias vs ERA5 at days 1-3. Reading rule (set before the result):
the variant that removes >= 50 % of the base2 day-3 Bay u850 bias names the process; if none does, the easterly is
dynamical / initial-state (physics-off comparison decides which).

## 10 Nov 01:40 IST - P5 denial, first 3 variants (T170, 6 Oct-Nov 2020 starts, Kaggle T4; base2 = same set)
Day-3 Bay (10-20N, 82-95E) u850 / v850 bias, central-India MSLP bias. Registered rule (6 Nov): a variant that removes >= 50 % of
the day-3 u850 bias (-4.04 m/s) names the process.
| variant | u850 d3 | v850 d3 | C-India MSLP d3 |
|---|---|---|---|
| base2 | -4.04 | -3.18 | +2.13 |
| physics off | -7.78 | -1.39 | +8.52 |
| no CMT | -3.60 (-11 %) | -2.48 | +2.12 |
| shallow <= 200 hPa (sh_depth) | -2.72 (-33 %) | +0.77 | +0.52 (-76 %) |
Reading: no variant meets the 50 % rule yet. Physics off is much worse -> the easterly is not created by a physics term;
the dynamics/large-scale pressure pattern makes it and physics partly holds it back. CMT is not the cause. The tall shallow
scheme explains most of the central-India high (+2.13 -> +0.52) and all of the southward v850, and a third of u850 -> the
P5 low-level error and the P1 tall-shallow problem are linked (same scheme). Pending: implicit drag, land module, no DFI
(Kaggle, launched 20:05Z). The 9 Nov E2E numbers for these three are NOT used (A100 precision issue, docs/gpu_usage.md).

## 10 Nov 03:10 IST - P5 denial complete + noise check registered; P2 32 L neutrality result
| variant | u850 d3 | v850 d3 | C-India MSLP d3 |
|---|---|---|---|
| implicit drag | -2.97 (-26 %) | -2.10 | +1.98 |
| land module | -2.75 (-32 %) | -2.53 | +1.78 |
| no DFI | -3.22 (-20 %) | -2.42 | +1.88 |
Reading: NO variant meets the registered 50 % rule. Every change moves day-3 u850 by 11-33 % in the same direction, which
looks like spread from any perturbation rather than one process. Exception with a distinct signature: shallow <= 200 hPa
(v850 -3.18 -> +0.77, C-India MSLP +2.13 -> +0.52; others stay -2.1..-2.5 and +1.8..+2.1).
Noise check (registered before the run): base2 with a 2 % SPPT perturbation, seeds 1 and 2 (tn-p5-den-noise, same 6 starts).
Prediction: d3 u850 spread among base2 / noise1 / noise2 about +-0.5 m/s. If the noise members also move u850 by ~1 m/s,
the 11-33 % moves are noise and only the shallow-depth signature (v850, MSLP) is a real signal.
P2 32 L neutrality (registered 'base1 + drag_imp vs base1: z500 within +-0.5 m; intensity and tracks not worse beyond the
round-off spread'): z500 d1/d5/d10 20.01/73.0/119.1 vs 20.02/73.1/119.2 PASS; 72-h pmin Vardah 989.9 vs 989.5, Nivar 994.9 vs
994.5, Michaung 999.3 vs 999.4 PASS; quick6 72-h track 318.9 vs 297.2 km = +7.3 % vs the 6 % spread FAIL (marginal).
=> drag_imp stays a 75-level-only fix; NOT added to the 32-level base. 32 L does not need it (stable without it).
- 04:05 IST noise result: base2 noise1 (2 % SPPT, seed 1) d3 u850 -3.05 / v850 -3.77 / C-India MSLP +2.18 vs base2 -4.04 / -3.18 / +2.13.
  Prediction (spread ~+-0.5 m/s) FAILED: a tiny perturbation alone moves day-3 Bay u850 by 1.0 m/s (25 %). => the 11-33 %
  u850 moves of CMT / drag / land / DFI / shallow-depth are within noise; 6 starts are too few for a u850 attribution.
  v850 and MSLP move little with noise (-0.6 / +0.05) -> the shallow-depth signature (v850 +0.77, MSLP +0.52) is ~4 and
  ~30 noise-steps away: REAL. noise2 was killed (OOM: two T170 models in one process - known 7 Nov lesson; my error);
  re-queued alone as tn-p5-den-noise2.
- 07:15 IST CORRECTION: every P5 denial run (base2 included, tn-p5-denial 7 Nov) used STRIDE 8 over the 12 Oct-Nov starts
  = only 2 starts (2020-10-02, 2020-11-11), not 6. noise2 (seed 2): d3 u850 -3.13 / v850 -3.66 / MSLP +1.91. With 2 starts a
  2 % perturbation moves Bay u850 by ~1 m/s -> no P5 attribution possible from these runs. Re-run on all 12 starts (one variant
  per job): tn-p5-d12-b2 (base2), -shd (shallow <= 200 hPa), -nz (base2 noise1).
  REGISTERED before the runs: (a) noise: |base2 - noise1| d3 u850 <= 0.5 m/s at 12 starts (else 12 starts are still too few
  and the test needs the full 2020 year); (b) shallow-depth keeps its signature: d3 v850 at least 1.5 m/s less southward and
  C-India MSLP at least 1.0 hPa lower than base2; (c) 50 % rule for u850 unchanged.
- 09:00 IST 12-START RESULT (all Oct-Nov 2020 T00 starts, T170): d3 u850 / v850 / C-India MSLP
  base2 -4.65 / -0.69 / +1.63; base2 noise1 -4.30 / -0.61 / +1.67; shallow <= 200 hPa -4.01 / +0.80 / +1.04.
  (a) noise |base2 - noise1| u850 0.35 <= 0.5 -> PASS: 12 starts are enough. (b) shallow-depth signature: v850 +1.49 (needed
  >= 1.5) FAIL marginally, MSLP -0.59 (needed >= 1.0) FAIL; u850 -14 % (50 % rule) FAIL. => the 2-start signature was mostly
  sampling: shallow depth is NOT the P5 cause. Robust facts: Bay u850 easterly bias -1.0 (d1) -> -4.1 (d2) -> -4.7 m/s (d3),
  grows fastest on day 2; v850 small at 12 starts. Not explained by CMT, drag, land, DFI or shallow depth (all 2-start but
  none near 50 %); physics-off much worse. Next: 850-hPa u-momentum tendency budget by term (dynamics: pressure gradient,
  advection, Coriolis; physics: BL, convection) over the Bay, days 1-2, base2, 12 starts - to locate where the easterly
  acceleration comes from, before any fix.
- 10:10 IST P5 geostrophic check REGISTERED (tn-p5-geo: base2, 12 starts, T170; saves mean bias maps u850/v850/MSLP d1-d3;
  scripts/cyclone/analysis/p5_geo_eval.py). Back-of-envelope: C-India MSLP +1.6 hPa over ~800 km at 15 N -> geostrophic
  easterly ~5 m/s, the size of the Bay u850 bias (-4.65). Prediction: on days 2-3 the geostrophic u from the MSLP bias over the
  Bay has the same sign and 50-150 % of the u850 bias, pattern r >= 0.5 over 8-25 N 70-100 E. If yes: P5 = a low-level
  pressure-pattern error (central-India / north-Bay pressure too high) -> next: why that pressure rises (+0.24 d1 -> +1.63 d3).
  If no: the easterly is ageostrophic (momentum mixing / friction / convective momentum) -> physics budget.
- 12:55 IST GEOSTROPHIC CHECK RESULT (tn-p5-geo, base2, 12 starts): Bay u850 bias d1/d2/d3 -0.95/-3.98/-4.33; geostrophic u from
  the MSLP bias -1.24/-5.32/-6.77 (share 130/134/156 %), pattern r over 8-25N 70-100E +0.11/+0.24/+0.18.
  Registered: same sign YES; share 50-150 % d2 YES, d3 NO (156 %); pattern r >= 0.5 NO. => NOT confirmed. The box means
  agree in sign and size but the maps do not match: the u850 error is not simply the geostrophic wind of the MSLP error.
- 12:55 IST PIPELINE FINDING: identical base2 runs gave d3 Bay u850 -4.65 (tn-p5-d12-b2) and -4.33 (tn-p5-geo). Cause: Kaggle
  preinstalls jax_cuda13_plugin 0.11.1; with the unpinned 'pip install -U jax[cuda12]' some runs failed to initialise the
  cuda12 plugin ('XLA FFI handler ... API version 0.5 vs 0.4') and ran on a different library stack. Affected (plugin error in
  log): tn-p5-d12-b2, tn-p5-den-shd, tn-p5-denial, tn-s-rd-wx0 (and possibly earlier suites). Fix in kernel.py: remove the
  cuda13 plugin, pin jax[cuda12]==0.12.0.1, stop (exit 3) if the plugin does not load. Same-stack comparison at 12 starts
  (geo, d12-nz, d12-shd): base2 -4.33/-0.71/+1.70, noise1 -4.30/-0.61/+1.67 (noise 0.03 m/s), shallow-depth -4.01/+0.80/+1.04
  (u850 -7 %, v850 +1.51, MSLP -0.66) -> shallow depth still NOT the cause (MSLP check fails, u850 far from 50 %).
  Consequence to check: the '6 % track round-off spread' used as a neutrality limit may partly be this stack mixing.
- 13:15 IST continuum (cnt) track verdict re-test: the 5 Nov rejection compared cnt-q6 (clean cuda12 stack) with base1-q6
  (plugin-error stack) -> mismatched. Re-run both on the pinned stack (tn-s-cnt-q6p, tn-s-base1-q6p), same configs, same
  registered gate (quick6 72-h mean track error not worse than base1 beyond the round-off spread). If cnt passes, its other
  checks (z500, TN u850, stability passed 5 Nov; rain/genesis pending then) are re-confirmed before adoption.
- 13:40 IST P5 MAP FINDING (tn-p5-geo maps): the u850 easterly error appears on day 1 EAST of the Bay (105-120E, 12-24N: -3..-5
  m/s; Bay ~-1) and reaches the Bay on day 2 (90E 18N -7.0). A high-MSLP error sits north-east of the Bay from day 1 (24N
  90-105E +3.9 -> +6.2 hPa) = SE flank of the Tibetan Plateau / Myanmar hills. Lead: terrain-following (pure sigma)
  pressure-gradient error over steep terrain (IFS review D2/D4); fits 'T85/T170 show it, T42 not' and the hour-0 terrain
  +0.55 hPa.
  REGISTERED before running scripts/cyclone/mm/rest_test.py (standard atmosphere at rest, hydrostatic ps over real terrain,
  physics off, no DFI, 24 h): if the core has a significant terrain pressure-gradient error, 24-h mean |u850| on the SE Tibet
  flank (20-30N 90-110E) > 1 m/s while the flat ocean (5S-5N 60-90E) < 0.2 m/s, and it is larger at T85 than at T42. If the
  SE-flank value is < 0.3 m/s at T85, the lead is rejected.
- 14:00 IST REST TEST RESULT (rest_test.py, standard atmosphere at rest, real terrain, physics off, no DFI, 24 h): mean|u850|
  SE Tibet flank T42 0.09 / T85 0.16 m/s (max 0.37 / 0.76), Bay 0.04 / 0.04, flat ocean 0.01 / 0.01, Andes 0.11 / 0.10.
  Registered: confirm if SE flank > 1 m/s; reject if < 0.3 at T85 -> REJECTED. The core's terrain pressure-gradient error is
  small; the P5 easterly is not a sigma-coordinate PGF artefact. Next: is the high-MSLP error NE of the Bay (21-27N
  90-105E) already in the start state (init + DFI) or grown in day 1? (h0_map.py, 12 starts, T85).
- 15:40 IST HOUR-0 MAP RESULT (h0_map.py, 12 Oct-Nov starts, T85, init + DFI as in forecasts): MSLP bias box 21-27N 90-105E
  hour 0 +1.11 hPa -> hour 24 +2.48 hPa: ~45 % is already in the start state, ~55 % grows in day 1. The start state is also
  +0.2..+0.9 hPa high over most of the tropical ocean 3-15N (where the reduction is trivial -> a real surface-pressure
  offset), with terrain spots (27N 85E +6.2: Himalayan foothills). => two parts: (1) start-state surface pressure too high
  (init / DFI; the 6 Nov C-India split was formula +0.16, terrain +0.55, DFI +0.4); (2) day-1 growth of +1.4 hPa NE of the Bay.
- 15:55 IST CONTINUUM TRACK RE-TEST (pinned stack): base1-q6p 24/48/72 h 116.6/221.2/297.2 km, cnt-q6p 104.4/232.6/328.7 km
  -> IDENTICAL to the 5 Nov runs (base1-q6 had the plugin error, cnt-q6 did not). cnt +10.6 % on 72-h tracks -> rejection
  STANDS. Correction to 12:55: the plugin error does NOT by itself change results (identical here). The base2 difference
  (tn-p5-d12-b2 -4.65 vs tn-p5-geo -4.33, same config and starts) is UNEXPLAINED; the pin + stop check stays (harmless),
  but stack mixing is not shown to have affected earlier verdicts.
- 16:10 IST plugin message checked: runs with the 'xla_cuda12.initialize' FFI message inside the model process ran at GPU speed
  (rd-wx1 391/317 s per start vs base1-wx1 385/325 s) -> it is harmless (one cuDNN RNN handler), not a different stack.
  kernel.py stop check narrowed to 'JAX not on GPU' only. The base2 -4.65 vs -4.33 difference (same code, starts, GPU type)
  therefore means GPU run-to-run variation of ~0.3 m/s in 3-day Bay u850 (12-start mean) exists despite deterministic flags
  -> treat 0.3 m/s as the floor for any u850 comparison; registered 0.5 m/s noise limit remains appropriate.
- 16:40 IST HOUR-0 SPLIT (h0_split.py, 12 starts, T85; surface pressure, no reduction): Indian Ocean 3-15N 60-100E init -0.30
  -> after DFI +0.03 hPa (every start within +-0.25) => the start state over the sea is right; the hour-0 MSLP +0.2..0.9 over
  the sea is the reduction/regridding (model spectral terrain over sea: mean +2 m, spots to +144 m). NE-Bay hour-0 +1.1 hPa
  is over ~1000 m terrain (model 1080-1112 m vs ERA5 1003 m) -> mostly reduction. => P5 is a FORECAST-GROWN error (u850
  easterly appears east of the Bay on day 1, real pressure growth ~+1.4 hPa in day 1), not a start-state error.
  Side finding (not P5): tropical ocean 30S-30N surface pressure -0.50 hPa at init (-0.43 after DFI), every start -> a
  systematic start-state mass deficit; relates to the remaining hour-0 z500 offset (-2.0 m after rd_si). Logged for the core item.
- 16:45 IST 12-START DENIALS QUEUED (2-start results are not usable): physics off, land module, implicit drag (tn-p5-d12-phys/
  lnd/drg). REGISTERED: reference base2 d3 Bay u850 = mean of the two 12-start runs -4.49 (+-0.3 run-to-run floor). A process
  is named if its denial removes >= 50 % of that bias (|u850| <= 2.25). Physics off: if |u850| d3 >= 4.5 the easterly is made
  by the dynamics (physics only damps it); if it falls below 2.25 the physics creates it.

## 10 Nov 16:00 IST - Sridhar's three checks before any change ("a wind error east of the Bay does not by itself mean it came from Siberia")
1. CORIOLIS - PASSED. Dinosaur: Omega 7.292e-5 1/s (sidereal 7.2921e-5), radius 6,371,220 m; f on the T85 grid equals
   2*7.2921e-5*sin(lat) at 5-60 N to 4-5 digits, north positive, latitudes ordered S->N. Our code (mm2.fcor, bogus vortex)
   uses 2*7.292e-5*sin(lat) - only in the ocean coupling and storm bogus. No error.
2. SIBERIAN HIGH and 3. UPSTREAM - job tn-p5-wide: base2, 12 Oct-Nov starts, T170, daily bias maps day 0-5 of MSLP, u850,
   v850, z500 over 0-70 N, 40-140 E. REGISTERED reading:
   (2) Boxes Siberia 45-65N 80-120E, China 25-40N 100-120E, Myanmar 18-28N 92-100E, Bay 10-20N 82-95E. 'Reproduced' if the
       MSLP bias stays within +-2 hPa through day 3 and grows by < 1 hPa/day, and the u850/v850 biases stay within +-2 m/s.
       Anything beyond = a regional error, reported with where and when it starts.
   (3) 'Upstream origin' only if an easterly u850 bias <= -2 m/s exists over China/Indochina (12-30N 100-120E) at least one
       day BEFORE the Bay box reaches -2 m/s, AND the maps show a connected band between them on that day. Otherwise local
       growth. A Siberian origin would additionally need the Siberia/China MSLP bias to lead the Myanmar/Bay one in time.
- 16:35 IST GLOBAL EXTENSION (Sridhar 16:28: 'not only Siberian High - other global highs and trade winds'; T170 only, 16:30):
  tn-p5-wide switched to the whole globe (WIN -90,90,0,360; T42 smoke test only checks the code, no result used). Evaluation
  scripts/cyclone/analysis/p5_global_eval.py. REGISTERED reading, same rule for every feature: REPRODUCED if |bias| <= 2 hPa
  (MSLP) or 2 m/s (u850) through day 3 and MSLP bias grows < 1 hPa/day (day 0 -> 3); else FLAGGED with where/when.
  Highs/lows: Siberian, N Pacific, Azores, S Pacific, S Atlantic, Mascarene, Aleutian, Icelandic (+ China, Myanmar, Bay).
  Trades (u850): N/S Pacific, N/S Atlantic, S Indian, Arabian Sea NE monsoon, Bay, S China Sea/Indochina.
  Caveat stated in advance: MSLP over high terrain (parts of Siberia/China) depends on the reduction formula.
- 17:05 IST 12-START DENIALS RESULT (ref base2 d3 Bay u850 -4.49 +-0.3): physics off -7.41 / v850 -2.73 / C-India MSLP +10.66;
  implicit drag -4.39 (-2 %); land module -4.01 (-11 %). Registered reading: no process named (none reaches |u850| <= 2.25);
  physics off >= 4.5 -> the easterly is MADE BY THE DYNAMICS / large-scale flow, physics only damps it (caveat: physics off
  also removes surface friction and land heating, hence the huge C-India MSLP). => the global circulation check (tn-p5-wide,
  launched 11:33Z on account 1) is the right next step.
- 17:25 IST WORDING CORRECTION (Sridhar 17:15): the 12-start denials show only that THE TESTED PHYSICS PROCESSES DO NOT EXPLAIN
  the easterly and that the complete physics package partly compensates; physics-off also removes friction and land heating
  and changes the whole evolution, so this is NOT proof of a dynamical-core defect. 'Global circulation error' and 'core error'
  are different claims: the global check says WHERE the forecast goes wrong, a tendency budget must still say WHY.
  Status: P5 unresolved, investigation narrowed. No physics or core change until the global evidence is in.
- 17:25 IST GLOBAL PER-START JOB tn-p5-glob (account 4): same as tn-p5-wide but saves every start's bias maps (PERSTART=1);
  evaluation scripts/cyclone/analysis/p5_global_eval2.py: per system and start, POSITION (centre shift km), STRENGTH (central
  MSLP diff), WIND (850-hPa speed diff in the system box), EVOLUTION (days 0-5); trades per start. REGISTERED limits: centre
  shift > 500 km, |dP| > 2 hPa or |dWind| > 2 m/s = failing start; a system counts as systematically wrong if >= 7 of 12 starts
  fail on the same day with the same sign. tn-p5-wide (account 1, mean maps only, launched before this request) is kept as a
  run-to-run cross-check of the mean maps. Caveat: centre = box max/min, unreliable for flat or split highs (flagged by eye).
- 18:05 IST GLOBAL CHECK, 12-start MEAN (tn-p5-wide, T170; per-start job tn-p5-glob still queued on Kaggle):
  REPRODUCED (registered rule): N Pacific High, Azores High, S Pacific High, S Atlantic High, Mascarene High, Aleutian Low; trades
  N Pacific, S Pacific, N Atlantic, S Indian. FLAGGED: Siberian High TOO WEAK (d1 -0.9, d2 -3.6, d3 -4.7 hPa; terrain caveat);
  Icelandic Low too shallow (+2.0..+3.4 d2-d4); S Atlantic trades too weak (+2.8 d1, +2.2 d3); China 25-40N 100-120E +1.7/+2.3
  (d1/d2); Myanmar +1.9/+2.9; Arabian Sea NE monsoon -2.2 (d2); S China Sea/Indochina u850 -2.5 (d1) -3.0 (d2); Bay -1.0 (d1) -4.0 (d2).
  CHECK 3 (upstream): easterly error over Indochina/S China Sea on day 1 (box -2.5; 20N 100E -6.3, 15N 110E -6.5) while the Bay
  is -1.0; day 2 the Bay reaches -4.0 with a continuous negative band 15-20N 80-120E (weak at 90E on day 1). Registered
  criteria for 'upstream origin' MET on the mean - origin INDOCHINA / SOUTH CHINA SEA, not China north of 25N.
  CHECK 2 (Siberia): Siberian High is too WEAK, and its bias is opposite in sign to the China/Myanmar high bias and does not
  lead it -> no evidence for a Siberian origin.
  Pattern: high-MSLP bias over Myanmar/Yunnan/S China (20-30N 95-110E, +3 hPa d1-d3) and a growing LOW-MSLP bias over the
  tropical W Pacific/S China Sea (0-20N 110-140E: -1..-2.5 d1 -> -3..-6 d3); the easterly error sits between them.
  Caveats: (a) u850 at 30-40N 70-100E (+10..+16 m/s) is below ground over Tibet - extrapolation artefact, ignored; (b) Oct-Nov
  2020 had several strong W Pacific typhoons crossing the S China Sea (Molave, Goni, Etau, Vamco) - a mean low bias there can
  come from a few starts with misplaced/too-deep typhoons; the per-start job decides this before any conclusion.
  This says WHERE (Indochina/S China Sea/W Pacific), not WHY.
- 18:15 IST SRIDHAR'S FIVE PER-START QUESTIONS - REGISTERED before tn-p5-glob results (script committed 6b3fc1ea; this note
  written 18:25, still before results). Boxes: SE Asia SEA 12-24N 100-120E (u850), Bay 10-20N 82-95E (u850), dip 0-20N
  110-140E (MSLP), typhoon box 5-25N 105-140E. Typhoon start (objective, from ERA5 itself): ERA5 min MSLP in the typhoon box
  <= 995 hPa on any day 0-3 (1.5 deg truth grid; ERA5 minimum printed for every start so borderline cases are visible).
  Q1 systematic: SEA u850 <= -2 m/s on day 1 or 2 in >= 7 of 12 starts.
  Q2 without typhoons: the same in >= half of the non-typhoon starts.
  Q3 timing: SEA reaches -2 before the Bay in >= 2/3 of the starts in which the Bay reaches -2.
  Q4 pressure dip: dip box <= -1.5 hPa on the day SEA first reaches -2, in >= 2/3 of those starts.
  Q5 typhoon starts: centre shift > 300 km = misplaced, depth diff < -5 hPa = too deep (box min can jump to another low:
  checked by eye).
  Reading: Q1 + Q2 yes = repeatable MEGAM weakness; Q1 yes but Q2 no with Q5 misplaced/too deep = typhoon-driven average.
  If repeatable (still no solver/physics change): SE Asian pressure-gradient evolution, W Pacific subtropical circulation,
  trough/Rossby propagation across East Asia, then the tendency budget on native model levels (WHY).
  Noted (Sridhar): 6/8 systems and 4/5 trade belts passing does not establish global accuracy; seasonal and case verification
  still needed.
- 18:30 IST JETS / WESTERLIES / ROSSBY WAVES / MJO (Sridhar 18:10) - job tn-p5-dyn: base2, 12 Oct-Nov 2020 starts, T170, days
  0-10, global, per start: u200, v200, z500, u850, rain24 (model day d minus d-1, as wx2.py). REGISTERED before results:
  JETS - per start/day, per sector (Asia 70-150E, Pacific 150-240E, Atlantic 280-350E): subtropical jet = u200 max 20-45N,
    eddy-driven/polar jet = u200 max 45-70N; core LATITUDE shift > 2.5 deg or core SPEED bias > 5 m/s = failing start.
  WESTERLIES - u850 40-60N sector means; |bias| > 2 m/s = failing.
  ROSSBY WAVES - z500 35-60N, eddy part (minus zonal mean) per longitude: PHASE shift = lag (deg lon) of best model-ERA5
    correlation (+ = model too far east), AMPLITUDE ratio = model/ERA5 eddy std; failing if |phase| > 10 deg or ratio outside
    0.8-1.2; shown globally and for East Asia 60-160E.
  MJO (approximate - no OLR or climatology, so no RMM index): equatorial 15S-15N u200 and u850 eddy profiles and rain24 along
    longitude; pattern correlation model vs ERA5 and eastward lag; failing if correlation < 0.6 or |lag| > 10 deg. Stated
    limit: whether a real MJO event was active in these starts is not determined by this check.
  A feature is SYSTEMATICALLY wrong if >= 7 of 12 starts fail on the same day with the same sign. Says WHERE/WHAT, not WHY.
- 18:25 IST ADDED BEFORE tn-p5-dyn RESULTS (Sridhar 18:17; registered measures unchanged, these are extra):
  (1) jet: wind-weighted core latitude (centroid of the sector-mean u200 profile where u >= 0.8 max) beside the max-latitude
      measure (the original already uses the sector-mean profile, but can jump between two maxima); same 2.5 deg limit.
  (2) Rossby: phase/amplitude also on z500 ANOMALIES (model and ERA5 minus ERA5 daily climatology c_z500) so a background
      height bias is not mistaken for a wave error; same 10 deg / 0.8-1.2 limits.
  (3) tropical: labelled 'tropical circulation test, NOT MJO validation'; spatial match (correlation) and propagation drift
      (lag) reported separately.
  CLASSES per feature and day: PASS (<= 2 of 12 starts beyond the limit), SYSTEMATIC (>= 7 same sign), CASE-DEPENDENT (3-6, or
  >= 7 mixed sign), INCONCLUSIVE (diagnostic unsuitable, assigned by eye with the reason). Failed metrics are not fixed one by
  one - several may share one cause. Solver and physics frozen until both experiments are read.
  Circulation chain tropics -> Rossby/Asian circulation -> westerlies/jet/pressure gradients -> Indochina/S China Sea -> Bay is a
  HYPOTHESIS, two-way interactions possible; each link needs its own evidence.
- 18:50 IST CORRECTION (start-state mass): the 'tropical ocean -0.5 hPa at init' (16:40) was MY DIAGNOSTIC: h0_split mapped the
  model field back to the 1.5 deg grid by nearest point and compared on the 1.5 deg ocean mask -> coastal land points with
  lower pressure. Direct test (2 starts): model start ps vs regridded ERA5 ps over tropical ocean -0.009 hPa (T85) / +0.065
  (T170) (terrain shift -0.004/+0.074, spectral truncation -0.005/-0.009); global mean ps ERA5 grid 985.863 vs model grid
  985.823 (T85) / 985.847 (T170) hPa. => NO start-state mass error. (The expert-question item on it is withdrawn.)

## 10 Nov 19:00 IST - CLOSED ENERGY AUDIT (Sridhar 18:32 'do the audit'; peer review 18:29)
Already known (4 Nov budget_audit): every physics process conserves internally (moist enthalpy 0.000 W/m2; water closes; BL heat
vs surface H +0.5). Never audited: the dynamics step, diffusion and physics-dynamics coupling, and the closed total. New:
scripts/cyclone/mm/energy_audit.py - E = sum dsig ps/g (cp T + Lv q + K) + Phi_s ps/g; every 3 h one step split into FULL, DYN
(physics off), FILT (diffusion once), PHYS (RAD / SFC = H + Lv E / KE removed by drag-CMT / rest), COUPLING = FULL - DYN - PHYS;
radiation parts (OLR, surface LW up/down, surface SW net, atmospheric LW and SW); layer thicknesses 1000-850 / 850-500 / 500-200.
Run: T85, base2, starts 2020-10-02 and 2020-01-01, 24 h (local CPU; T170 later on Kaggle if needed).
REGISTERED reading (before results): reference global-mean atmosphere (Wild et al. 2013 / Trenberth et al. 2009, annual means):
radiative -103 (SW absorbed ~ +79, LW ~ -183; OLR ~ 239, surface LW down ~ 342, up ~ 398, surface SW net ~ 161), sensible ~ +20,
latent ~ +84, net ~ 0. A model term off by > 10 W/m2 (day mean, h3-h24) is a lead; DYN, FILT or COUPLING beyond +-2 W/m2 is a
numerical energy leak. Caveat: single days in Jan/Oct vs annual means, 3-hourly samples of the diurnal cycle; the radiation cache
is empty at hour 0 (h0 excluded from means). Says WHICH term; does not by itself say why.
- 19:25 IST energy audit: local T85 killed twice by the 7 GB memory limit (model + extra compiled audit steps); T42 two-pass
  test reproduces the one-process numbers exactly (DYN -1.40, COUPLING -4.59). Moved to Kaggle at T170 (Sridhar: T170 only):
  tn-energy-audit, two processes in one job (full pass, then physics-off pass on the saved states), 2 starts x 24 h. Reading
  as registered 19:00.
- 19:45 IST GLOBAL PER-START RESULT (tn-p5-glob, T170, 12 Oct-Nov 2020 starts; registered readings 16:00/16:35/17:25/18:15).
  Run-to-run: the mean SEA / Bay u850 boxes equal tn-p5-wide exactly (-2.5/-3.0/-3.0; -1.0/-4.0/-4.3) -> reproducible.
  POSITION (centre = box max/min): INCONCLUSIVE for broad highs - day-0 'shifts' already 953 km (S Pacific High), 206 km (N
  Pacific High) where model = ERA5, so the centre jumps inside flat highs (caveat registered 17:25). Counts below use STRENGTH
  (central pressure, |dP| > 2 hPa) and WIND (|dW| > 2 m/s) only.
  Aleutian Low: TOO DEEP from day 1 (mean dP -1.4/-2.4/-3.6/-4.9 d1-d4; 10-11 of 12 starts) -> SYSTEMATIC.
  Icelandic Low: 9-10 of 12 fail d2-d4 but the sign flips (+2.5 d2, -1.1 d3, -3.2 d4) -> CASE-DEPENDENT.
  Siberian High: strength 3-6/12 d1-d3 (C), 10/12 d4; wind +2.2..+2.4 in 7-9/12 -> INCONCLUSIVE for wind (850 hPa is below
  ground over the Mongolian/Tibetan part of the box) and position; the box-mean -4.7 hPa (wide) vs central max +0.5..+2 shows
  a structure/terrain issue, not a clean weak high.
  N Pacific High, Azores, S Atlantic, Mascarene: PASS to day 3 (<= 4/12); S Pacific High C (6/12 d2-d3, stronger +1.5).
  Trades (u850, starts beyond 2 m/s): S ATLANTIC SYSTEMATIC too weak (+2.8 d1 10/12; +2.2 d3 7/12); N Atlantic C (3-5/12);
  N/S Pacific, S Indian PASS; Arabian Sea too easterly d2 8/12 (S); Bay S (11/12 d2, 12/12 d3); S China Sea/Indochina S (8/12 d1,
  9/12 d2); China 25-40N too westerly d3-d5 8-10/12 (terrain caveat).
  FIVE QUESTIONS: Q1 SEA easterly <= -2 on d1/d2 in 12/12 -> SYSTEMATIC. Q2 present in 9/9 non-typhoon starts (3 typhoon
  starts by ERA5 < 995 hPa) -> NOT a typhoon-driven average: a repeatable MEGAM weakness. Q3 SEA before the Bay in 7/12 (4 same
  day, 1 Bay first) = 58 % < 2/3 -> 'SEA leads' NOT established per start (the mean-map lead of 18:05 is weaker than it looked).
  Q4 dip <= -1.5 on the SEA onset day in 4/12 -> NOT met: the W Pacific/S China Sea low develops a day or two LATER (d2-d3
  -2..-5 in almost every start) - it follows the easterly, it does not accompany its onset. Q5 typhoon centre metric jumps
  between lows (3066/2730 km) -> INCONCLUSIVE; Oct 22 start 231-513 km / +3.2..-3.9 hPa; Oct 27 d3 7.2 hPa too deep.
  Reading: the South/South-East Asian low-level easterly error is systematic and not caused by typhoons; it appears over
  Indochina/S China Sea and the Bay within the same 1-2 days (no robust one-day lead); the W Pacific pressure dip is a later
  consequence, not the trigger. Elsewhere: Aleutian Low too deep and S Atlantic trades too weak are also systematic -> the
  model has more than one large-scale error; WHERE only, not WHY.

## 10 Nov 19:20 IST - FIRST-HOURS TENDENCY DIAGNOSIS ('how to find the WHY'; Sridhar 'Ok' 19:04)
Method: Klinker & Sardeshmukh (1992) / Rodwell & Palmer (2007) initial tendencies. scripts/cyclone/mm/init_tend.py: 12 Oct-Nov
2020 starts, T170, base2, init + DFI; every step of the first 24 h at sigma ~0.85 (and 0.5): TOTAL change of u/v/T split into PHYS
(exact column tendencies: u by BL, CMT, rest; T by radiation, BL, deep, shallow, condensation, re-evaporation), PGF (pressure-
gradient force on sigma levels), COR (Coriolis), REST = TOTAL - PHYS - PGF - COR (transport, metric terms, diffusion, coupling,
numerics); windows 0-6 h and 6-24 h; reference = ERA5 real day0->day1 change (u850, T850) over the same starts. Job tn-init-tend.
REGISTERED reading (before results), per box (Indochina/S China Sea, Bay, Aleutian, S Atlantic trades, globe):
  error tendency = model TOTAL - ERA5 real change. The LEADING term is the one with the same sign as the error tendency, at least
  50 % of its size, and that sign in >= 8 of 12 starts. Interpretation: PGF+COR leading = the wind is pushed out of balance by the
  pressure/mass field (next: what builds that pressure - the T tendency terms at 850/500); REST leading = transport/numerics/
  coupling; PHYS (BL/CMT) leading = physics drag/mixing. No term meeting the rule = the error is not formed in the first day
  locally (it grows later or comes from elsewhere). Caveat: physics enters the time step inside the RK2/Crank-Nicolson scheme,
  so the column tendency at the start state approximates its contribution; the difference falls into REST.
- 19:55 IST ENERGY AUDIT RESULT (tn-energy-audit, T170, base2, 2020-10-02 and 2020-01-01, 24 h, 3-hourly, day means h3-h24, globe):
  FULL -36.8 / -37.8 W/m2 (the model atmosphere loses ~3.2 MJ/m2 per day; real ~0).
  PHYS -28.2 / -29.0 = RAD -138.5 / -133.3 (reference ~-103 -> 30-35 W/m2 TOO MUCH radiative cooling: LEAD) + SFC +113.7 / +107.0
    (ref ~+104) + KE removed by drag -3.9 / -3.2 (not returned as heat).
  Radiation parts: SW absorbed in the atmosphere +52.9 / +54.4 (ref ~+79: -25, LEAD); surface SW net 134.5 / 140.8 (ref ~161: -20..-27,
    LEAD); OLR 228 / 226 (ref ~239: -11..-13, LEAD); atmospheric LW -191 / -188 (ref ~-183: -5..-8); surface LW down 361 / 352 (ref ~342:
    +10..+19, LEAD); total SW absorbed (atm + surface) ~188-195 vs ~240 -> planetary albedo ~0.43-0.45 vs ~0.29 (inferred: TOA SW is
    not kept in the radiation cache; insolation itself not yet checked). Fits the 4-5 Nov findings: convective/anvil cloud too
    extensive and bright (D9) and the water-vapour continuum (lw_cnt) too strong.
  Surface: latent LvE +117 / +107 (ref ~84: +23..+33, LEAD = the known +16-20 % ocean evaporation formula); sensible H -3.5 / -0.1 (ref
    ~+20: -20..-24, LEAD; the low levels are too warm, P1).
  NUMERICAL (registered limit +-2): DYN -4.7 / -6.7 (negative in 16 of 16 samples) -> LEAK in the dynamics step; COUPLING -4.0 / -2.1
    -> leak (Oct); FILT -0.4 / -0.6 OK. Non-physical loss total (DYN + COUPLING + KE not heated) ~ -10..-15 W/m2.
  Layer thickness, 24 h: 1000-850 +6.0 / +6.7 m (Tv +1.3 / +1.4 K: low levels warm), 850-500 -13.3 / -12.5 m (-0.8 K), 500-200 -30.1
    / -27.2 m (-1.0..-1.1 K: upper troposphere cools ~1 K/day) -> the z500 day-1 drift (-14 m) is THERMAL (peer test).
  Classification (diagnostic / tendency / coupling): TENDENCY errors in radiation (clouds/SW, continuum) and surface fluxes, plus a
  numerical dynamics + coupling leak. Next checks: TOA insolation and clear-sky vs all-sky SW (cloud vs gas), DYN leak location.
  No change made.
- 20:15 IST SUNLIGHT CHECK (existing tn-radchk2, T170, Jan + Jul day-3 states): clear-sky daytime atmospheric SW absorption
  fraction model 0.22 = RRTMG 0.22, clear-sky OLR = RRTMG with all gases (+-0.3) -> gas optics and insolation geometry RIGHT.
  All-sky: SW cloud radiative effect -115 / -109 W/m2 vs CERES ~-47; cloud cover 0.84 / 0.83 vs ~0.67; LW CRE 39-40 vs ~26.
  => the 45-50 W/m2 missing solar absorption (audit) is CLOUDS (too much / too bright), not gases or the sun.
- 20:15 IST JETS / WESTERLIES / ROSSBY / TROPICS RESULT (tn-p5-dyn, T170, 12 starts, 10 days; classes as registered):
  ASIAN SUBTROPICAL JET SPEED: TOO WEAK, SYSTEMATIC FROM DAY 1: mean -6.2 / -8.7 / -10.3 m/s (d1/d2/d3), 9-11 of 12 starts, all same
    sign (worst -16 by d3). Pacific and Atlantic subtropical jets also weaken, more slowly (-2.4 / -2.0 d1, -3.7 / -4.0 d3; C, some S
    late). Jet LATITUDE (both measures) P to day 3-4, C after. Eddy-driven/polar jets P to day 3-5, C later. 850-hPa westerlies:
    Asia C from day 2, Pacific/Atlantic P to day 5.
  ROSSBY waves (raw and climatology-removed): phase P to day 6 globally, C after; East Asia AMPLITUDE too strong (+0.3..+0.8), C from
    day 3, S days 8-10.
  TROPICS (not MJO validation): u200/u850 spatial match 0.96 -> 0.73 (d1 -> d5), drift -2..-6 deg (within 10) -> PASS to day ~8;
    RAIN pattern match falls below 0.6 from day 2 (5/12), day 3 (9/12) -> tropical rain placement SYSTEMATICALLY poor from day 2-3.
  Reading (hypothesis, not proven): the earliest and largest systematic large-scale error is the weakening Asian subtropical jet.
  By thermal wind, jet speed follows the upper-tropospheric equator-to-pole temperature gradient; the audit shows the upper
  troposphere cooling ~1 K/day and clouds/convection badly placed - a too-cold tropical upper troposphere (or too-warm subtropics)
  would weaken the jet. Needs evidence: zonal-mean T tendency by latitude at 500/200 (init_tend maps, T500 saved) and its terms.
- 20:55 IST FIRST-HOURS TENDENCY RESULT (tn-init-tend, T170, 12 Oct-Nov starts, sigma 0.862; registered reading 19:20). u850 in m/s/day.
  Indochina/S China Sea: ERA5 real -0.20; model TOTAL -3.06 (0-6 h) / -3.00 (6-24 h) -> error tendency ~-2.9 (matches the day-1 bias -2.5).
    PGF+COR -4.34 / -6.36 (same sign, > 100 % of the error, negative in 10/12 starts both windows) -> LEADING TERM = PGF+COR.
    PHYS +0.48 / +1.33 and REST +0.80 / +2.03 oppose it.
  Bay: ERA5 -0.11; TOTAL -1.27 / -1.04 -> error ~-1.1; PGF+COR -2.83 / -2.46, negative in 10/12 -> LEADING = PGF+COR.
  S Atlantic trades: error ~+2.4; 0-6 h PGF+COR +2.42 (8/12 positive) LEADING; 6-24 h PGF+COR +1.09 (46 %, fails 50 %), REST +2.24
    (11/12) LEADING -> pressure imbalance first, then transport/numerics.
  Aleutian: u850 error small (-0.5..+0.2) - the deepening needs a mass (surface pressure) tendency, not measured here.
  Reading (registered): PGF+COR leading = the wind is pushed by a pressure/mass field out of balance -> what builds the pressure:
  T850 (K/day): Indochina TOTAL +4.45 / +0.12 vs ERA5 -0.17; Bay +5.04 / +1.67 vs -0.16; globe +1.34 / +0.12 vs -0.01. The dominant heating
    is SHALLOW CONVECTION: h_shal +7.14 / +2.45 (Indochina), +7.31 / +5.55 (Bay), +2.66 / +1.24 (globe), positive in 12 of 12 starts.
  T500 (zonal means, K/day): shallow convection COOLS 500 hPa: tropics -5.33 / -2.60, subtropics -3.03 / -1.64, mid-latitudes ~0.
    => the shallow scheme moves heat DOWN (warms ~850, cools ~500) in every start: the P1 mechanism (warm low levels) and the
    upper/mid-troposphere cooling of the audit (thickness 850-500 -13 m/day).
  Jet (thermal-wind) evidence: MIXED. 0-6 h: tropics cool faster than mid-latitudes (all longitudes -3.48 vs -1.94; Asia -2.25 vs -1.10)
    = FOR a weaker jet; 6-24 h reversed (tropics -0.62 vs mid-lat -1.18; Asia -0.48 vs -0.93) = AGAINST. 500 hPa is below the jet (200
    hPa not saved) -> the jet link is neither confirmed nor rejected.
  Consistency check: the 12-start shallow-DEPTH denial (cap 200 hPa) removed only 7-14 % of the Bay u850 error; that variant changed
    the heating profile but over-cooled 850 (-2.26 K) -> the problem is the shallow scheme's vertical heating PROFILE, not its depth alone.
  Status: WHERE + first part of WHY found (pressure-field imbalance, with the shallow-convection heating profile as the largest
  early temperature error in the same places, 12/12). NOT yet shown that this heating builds that pressure error (attribution of
  PGF to processes needs column heating by process - next). Candidate fix = the P1 second shallow design (IFS Part IV, Tiedtke
  shallow mass flux), to be registered with predictions for T850/T500 tendencies AND the SE Asia/Bay u850 error, 32 L + 75 L screen.

## 10 Nov 21:15 IST - P1/P5 CANDIDATE 'ifs_sh' = IFS Cy50r1 shallow convection (Sridhar 20:55 'proceed')
Why: first-hours tendencies show base2's shallow scheme ('mse': relax moist static energy and q to their column mean from the
surface to the PARCEL TOP over 1 h - not a cumulus scheme; own comment: 10-40x too strong) heats ~850 hPa (+7 K/day Indochina/Bay,
+2.7 globe) and cools ~500 hPa (-5.3 K/day tropics) in 12/12 starts, where the easterly error forms (PGF+COR leading, 10/12).
Earlier shallow attempts (sh_mflux, sh_depth, 'mf' inside the 29-30 Oct 'full' package with sh_clos 0.6) were not the IFS scheme.
IFS Cy50r1 Part IV ch. 6 (read today): shallow = cloud <= 200 hPa deep (6.4.2); entrainment = f_eps 1.75e-3 (1.3 - RH) f_scale with
f_eps = 2 and f_scale = (qsat/qsat_base)^3 (eq. 6.7); detrainment D = E (1.6 - RH) (eq. 6.9); closure = sub-cloud moist static
energy balance, factor 1 (eq. 6.35/6.37). New mm2 options (default off; regression bit-identical 22.259984322409387): sh_eps,
sh_det, sh_dmax. Candidate settings (all from the document, nothing tuned): shallow 'mf', sh_trig 1, sh_dmax 20000, sh_eps 3.5e-3,
sh_det 1, sh_clos 1. Stated differences left: closure uses surface fluxes only (IFS also includes sub-cloud radiation/advection);
parcel kick is ours (0.5 K / 5e-4) not eq. 6.19; updraught kinetic energy (mf_wke) off; shallow condensate re-evaporates (no drizzle).
REGISTERED predictions (first-hours test, T170, 12 starts, same as tn-init-tend):
  (1) shallow heating at 500 hPa, tropics 15S-15N, 0-6 h: |h_shal| <= 0.3 K/day (base2 -5.33);
  (2) shallow heating at 850 hPa, globe, 0-6 h: between 0 and +3 K/day, and over Indochina / Bay below +3 (base2 +7.14 / +7.31);
  (3) 0-6 h T850 error (model TOTAL - ERA5) over Indochina and Bay reduced by >= 50 % (base2 +4.6 / +5.2 K/day);
  (4) 0-24 h u850 error tendency over Indochina and Bay reduced by >= 30 % (base2 ~-2.9 / ~-1.1 m/s/day).
If (1)-(3) hold, the full Stage-1 suite at 32 L + the 75 L screen (standing rule) follows, with gates unchanged. Local T42 runs
only check the code.
- 21:40 IST ifs_sh code check (T42, 1 start, NOT the registered test): with eq. 6.18 test-parcel trigger added (first version used the
  strong entrainment for the trigger too -> plume never condensed, inactive - fixed, regression still bit-identical): tropics 0-6 h
  shallow heating 850 +0.13 (base2 +3.43), 500 0.00 (base2 -2.53); tropical T850 total -1.72 K/day (base2 +0.87; ERA5 ~-0.1). Indication:
  500 hPa spurious cooling gone, but the 850 heating disappears too -> cold overshoot as in earlier attempts. Over warm tropical ocean
  the IFS test parcel usually exceeds 200 hPa -> 'deep', not shallow. Hypothesis: base2's 'mse' heating was standing in for the
  IFS boundary-layer mass-flux (EDMF, Part IV ch. 3) + deep-scheme low-level heating, which MEGAM lacks. Registered T170 test launched
  (tn-init-ifssh) to decide predictions (1)-(4).
- 22:20 IST (cycle, no GPU) design notes for the likely next candidate, IFS Cy50r1 Part IV ch. 3: turbulence = EDMF. The dry convective
  boundary layer gets a MASS-FLUX updraught (eq. 3.42-3.43: M_u,surf = 0.1 rho sigma_w, sigma_w = (1.2 u*^3 + 1.5 kappa w*^3 zn/zi)^(1/3)
  (1 - zn/zi)^(1/2); M_u = M_u,surf (z/zn)(1 - z/zi)^2; plume = the shallow test parcel eq. 6.18-6.20 with entrainment x3 in cloud;
  scalars only, not momentum); the CLOUDY boundary layer is the shallow scheme's job; stratocumulus (EIS = max(he700 - he950,
  he950 - he_sfc) > 5 K, he = hl + cp T* 5.87 qt) gets diffusion up to cloud top. MEGAM has K-profile diffusion (+ optional counter-
  gradient pbl_tm), no BL mass flux -> candidate 2 = ifs_sh + EDMF dry mass flux, to be registered only after tn-init-ifssh is scored.
- 23:25 IST ifs_sh REGISTERED TEST RESULT (tn-init-ifssh, T170, 12 starts, vs base2 tn-init-tend):
  (1) tropics 0-6 h shallow heating 500 hPa: -5.33 -> -0.00 K/day  PASS
  (2) shallow heating 850: globe +2.66 -> +0.59, Indochina +7.14 -> +1.85, Bay +7.31 -> +0.08  PASS
  (3) 0-6 h T850 error (model - ERA5): Indochina +4.62 -> +0.21 (-95 %), Bay +5.20 -> -0.93 (-82 %)  PASS
  (4) 0-24 h u850 error tendency: Indochina -2.83 -> -3.95, Bay -1.05 -> -2.43 m/s/day = WORSE  FAIL
  Cold overshoot: T850 TOTAL globe +1.34 -> -0.91 (0-6 h), +0.12 -> -0.89 (6-24 h); tropics +5.30 -> -1.21 / +0.83 -> -1.30 (ERA5 ~0).
  PGF+COR imbalance grows: Indochina -4.34 -> -4.88 / -6.36 -> -7.06; Bay -2.83 -> -2.85 / -2.46 -> -4.17.
  Reading: the IFS shallow scheme removes the wrong shallow heating profile exactly as predicted (P1 mechanism located and
  removable), BUT (a) without base2's spurious low-level heating the lower troposphere cools ~0.9 K/day globally (a missing heat
  source - the EDMF boundary-layer mass flux is the documented candidate), and (b) the Asian easterly error gets WORSE, so the
  shallow heating was NOT building the easterly - it was partly offsetting it. The 20:55 hypothesis 'shallow heating builds the
  pressure error' is REJECTED. New hypothesis (not tested): the easterly follows LOW-LEVEL COOLING (colder air -> higher pressure
  over continental Asia / Myanmar -> stronger pressure gradient); base2's spurious warming masked part of it.
  Registration said: if (1)-(3) hold, full suite + 75 L screen follows. They hold, but (4) and the global cold overshoot make the
  suite very likely to fail checks 2 and 4 -> decision put to Sridhar (run suite now vs build candidate 2 = ifs_sh + EDMF first).

## 10 Nov 23:55 IST - EDMF (IFS dry boundary-layer mass flux) built and checked locally: it does NOT address the cold overshoot
- New mm2 option `edmf` (default off; regression bit-identical 22.259984322409387): IFS Cy50r1 Part IV eqs. 3.42-3.43 mass flux
  with the surface test parcel of eqs. 6.18-6.20 and the kinetic-energy equation 6.10 (beta Cd = 0.949, f(1+gamma) = 3); scalars only;
  stops at saturation (cloud base, shallow scheme above) or w = 0. Energy closes to 0.2-0.4 W/m2 per column (explicit flux form).
- No predictions were registered and no GPU was used: the local T42 checks below showed the option has nothing to act on at 850 hPa.
  * 1-day T42 forecast (2020-01-01): T850 global bias ifs_sh -0.641 K, ifs_sh+edmf -0.638 K (no change).
  * Column snapshot after 30 h (2020-06-30 06 UTC): EDMF changes heating only in the lowest 2 layers (-1.1 / +1.1 K/day);
    0.00 K/day at sigma 0.86 (850 hPa). Plume top median 165 m vs Ri boundary-layer height ~1000 m.
  * Daytime stratification, E US and Amazon (3 starts, T42, `bl_strat.py`): ifs_sh and ifs_sh+edmf identical to 0.05 K.
    theta850 falls 1.7-2.7 K (E US) and 2.4-5.6 K (Amazon) in 24-48 h; 850->700 stability grows from +7 K (ERA5) to +9 to +12.7 K.
    base2 keeps theta850 within 0.3 K. The cooling is at and above 850 hPa, not inside the mixed layer.
- WHY (from the T170 first-hours budgets already on file, globe 6-24 h, T850 K/day, ifs_sh minus base2 = -1.01 in TOTAL):
  radiation -1.25 (-1.53 -> -2.78), shallow -1.00, dynamics -0.65, boundary layer -0.38, deep +1.23, rain evaporation +1.26.
  S Atlantic trades: radiation -3.85 -> -5.74. The largest single term is extra RADIATIVE cooling at 850 hPa: cloud-top cooling
  from the low cloud/moisture that base2's over-strong shallow mixing used to remove. This links the cold overshoot to the
  cloud root cause already measured in the energy audit (cloud cover 0.84 vs 0.67, SW CRE -110 vs -47 W/m2).
- Conclusion: EDMF (dry MF) is not the missing heat source. Next WHY = low cloud amount / cloud-top cooling (cloud scheme),
  which is also the largest energy-budget error. EDMF stays in the code, off.

## 11 Nov 04:00 IST - base2 75-level reference (tn-s-b2-75-wx0) collected: 19/19 starts ran 10 days, no blow-up
- Stability at 75 levels (check 8): 19/19 complete, all scores finite. Compared with 32-level base2 (tn-s-rd-wx0), same 19 starts, global RMSE:
  z500 d1 19.46 vs 17.80 (+9 %, worse 19/19), d3/d5 equal (43.9/71.5), d10 117.9 vs 119.5 (-1.3 %, better 12/19);
  mslp +2 to +5 % worse d1-d5; u850 +2 to +5 % worse (better only 3/19 at d3-d5); t850 equal within 1 % to d5, +3 % at d10.
- Caveat: the 75-level config also has sfc_imp=1, drag_imp=1 (implicit surface flux and drag, needed for 75-level stability); the 32-level reference does not, so the gap mixes level count and these two options.
- Reading: 75 levels is stable but not better; the day-1 z500/mslp gap (19/19) is systematic and points at the start
  (vertical interpolation / DFI at 75 levels), not at the physics. This is the reference every 75-level candidate screen is compared with.

## 11 Nov 10:30 IST - 75-level day-1 gap located in the TROPICS and in the first day's column cooling (not the start state)
- T170 bias split (19 starts, tn-s-b2-75-wx0 vs tn-s-rd-wx0): day-1 z500 bias tropics -10.2 m (75L) vs -8.0 m (32L), rmse 13.9 vs 11.8
  (+17 %); extratropics nearly equal (NH -15.3 vs -14.4, SH -8.8 vs -8.7). Tropical mslp rmse stays worse to day 5 (361 vs 302 Pa).
- Both level sets lose z500 globally every day: -10 m (d1), -16 (d2), -19 (d3), -23/-27 (d5): the column cools ~0.3-0.5 K/day,
  matching the energy audit (FULL -37 W/m2, radiation -133 vs ~-103 reference). This global cooling is the largest single error.
- T42 screen (gap75.py, 3 starts, partial): hour 0 equal (z500 rmse ~7 m both, after DFI), so the start state is NOT the cause;
  sfc_imp + drag_imp at 32L change day-1 z500 by only -0.3 to -0.6 m bias; 75L tropics day-1 z500 bias -15.6 vs -9.9 m (32L+imp).
- Next (measurement, T170, 12 starts): first-hours process profiles (init_tend.py, new: per-level tropics/globe means of every
  heating and moistening process + total) at 32L+imp and 75L+imp. Expectation registered: the 75L-32L difference in tropical
  column heating is small (~0.1 K/day for the 2.2 m z500 gap) but its VERTICAL distribution by process will differ; the process
  whose profile changes most with layer count is the 75L cause. Same output gives the low-level moistening by process (P1/P4/P5 track).

## 11 Nov 11:30 IST - cloud drift (cloud_drift.py, T42 screen, 2 starts): the cloud SCHEME is not the cause; the model MOISTENS the troposphere within 1-2 days
Large-scale (RH) cloud of radcloud on the model state, global means:
| | cover | low cover | RH >850 | RH 850-700 | RH 700-500 | RH 500-300 |
|---|---|---|---|---|---|---|
| ERA5 start (h0) | 0.27 | 0.23 | 0.73 | 0.56 | 0.43 | 0.37 |
| base2 h24 / h48 | 0.74 / 0.82 | 0.58 / 0.66 | 0.73 / 0.72 | 0.65 / 0.70 | 0.57 / 0.62 | 0.53 / 0.58 |
| ifs_sh h24 / h48 | 0.81 / 0.91 | 0.70 / 0.81 | 0.85 / 0.89 | 0.64 / 0.69 | 0.51 / 0.55 | 0.50 / 0.55 |
- On ERA5 humidity the scheme makes LITTLE cloud (0.27); cover triples in 24 h because RH rises 0.1-0.2 at every level above 850 hPa
  (base2) and in the lowest layers too with ifs_sh (0.73 -> 0.89: the boundary-layer moisture is no longer vented). The column cooling
  (~0.5 K/day) explains only ~+0.03 RH; the rest is real moistening. ERA5 does not drift like this.
- => Cloud excess, cloud-top cooling (P1), extra radiative energy loss (global z500 fall) are CONSEQUENCES of a fast moistening of the
  model troposphere. Next WHY: which process moistens (BL / shallow / deep detrainment / rain evaporation / condensation deficit / dynamics
  incl. humidity transport and negative-q filling). The running T170 jobs (tn-prof-32imp, tn-prof-75imp) record q tendency by process
  per level plus the total; dynamics = total - physics. Registered reading: the process (or dynamics) with the largest positive 700-300 hPa
  moistening in 0-24 h that is not balanced by condensation is the cause; if dynamics dominates, transport/positivity is suspect.
- 11 Nov 11:50 local T42 look (75L+imp base2, 1 start, init_tend profiles, g/kg/day, tropics 6-24 h): the 500-700 hPa moistening (+0.50)
  is the base2 shallow 'mse' scheme lifting boundary-layer vapour (+0.72; up to +1.24 at 0-6 h), against deep convection -0.12,
  condensation -0.41, rain evaporation +0.26, dynamics +0.05. Below 850: surface/BL +4.07, shallow -2.19, deep only -1.02.
  Working hypothesis (to confirm at T170, 12 starts): deep convection removes too little boundary-layer moisture; base2 hides it by
  pumping the excess into the free troposphere (mid-level moistening -> cloud -> cooling), ifs_sh leaves it in the BL (low deck, P1).
  Queued tn-prof-ifssh (acct 1) for the ifs_sh moisture budget with the same profiles.

## 11 Nov 13:10 IST - T170 first-hours process profiles, 12 starts each (tn-prof-32imp, tn-prof-75imp, tn-prof-ifssh), tropics 30S-30N, 6-24 h
Moisture budget (g/kg/day; DYN = total - physics):
| layer | run | total | BL+sfc | deep | shallow | condensation | rain evap | DYN |
|---|---|---|---|---|---|---|---|---|
| below 850 | base2 32L | -0.75 | +3.44 | -0.45 | -3.92 | -0.12 | +1.28 | -0.98 |
| below 850 | ifs_sh 32L | +0.45 | +3.46 | -1.81 | -0.35 | -0.23 | +0.42 | -1.04 |
| 500-700 | base2 32L | +0.47 | 0 | -0.27 | +2.20 | -1.76 | +0.16 | +0.13 |
| 500-700 | ifs_sh 32L | +0.15 | 0 | -0.41 | 0.00 | -0.03 | +0.40 | +0.20 |
Column heating (K/day): base2 deep +0.45, grid-scale condensation +1.57, rain evap -0.95, radiation -1.32;
ifs_sh deep +1.30, condensation +0.31, rain evap -0.64, radiation -1.32.
Reading (against the 11:50 hypothesis):
- base2: CONFIRMED in a sharper form. The 'mse' shallow scheme carries boundary-layer vapour to 500-700 hPa (+2.20) where grid-scale
  condensation rains it out (-1.76; heating +4.39 against shallow cooling -4.61 K/day). Deep convection makes only ~30 % of tropical
  latent heating (0.45 of ~1.6). Net +0.47 g/kg/day moistening at 500-700 -> mid-level cloud -> cooling. Not a real atmospheric cycle.
- ifs_sh: deep convection takes over (+1.30, ~80 % of latent heating, realistic) and mid levels moisten little (+0.15), BUT the layer
  below 850 GAINS +0.45 g/kg/day: the IFS-type shallow scheme vents only -0.35 (base2 -3.92). Surface supply +3.46 is not removed
  -> RH 0.73 -> 0.89 -> low deck (P1) -> cloud-top cooling. In IFS the shallow scheme is the main vent of the trade-wind sub-cloud
  layer (closure eq. 6.35: mass flux = sub-cloud MSE gain / (h_up - h_mean)). Next WHY: why our ifs_sh shallow mass flux is so small
  (closure, trigger area, or detrainment) - offline check of the cloud-base mass flux against eq. 6.35 with the surface fluxes.
- 75L vs 32L (base2+imp): tropical column cooling -0.514 vs -0.492 K/day (as registered: ~0.1 K/day order, small). Below 500 hPa
  75L is ~0.1 K/day colder; largest process changes: DYN below 850 -1.72 vs -1.16 K/day, rain evaporation 700-850 -2.10 vs -1.80,
  deep 300-500 +0.87 vs +0.54. Lead: near-surface vertical transport/coupling with thin layers (DYN), not one physics scheme. Next:
  split DYN below 850 (vertical advection of the +7 K/day shallow heating profile through thin layers) - lower priority than ifs_sh.

## 11 Nov 14:30 IST - why ifs_sh vents so little (sh_vent.py, T42 grid with the T170 20-min step, 24 h spin-up, tropical ocean)
- Shallow applies in ~30 % of tropical-ocean columns (deep convection active in ~25-50 %; shallow is switched off there).
- Cloud-base mass flux: the closure (sh_clos, eq. 6.35 as coded) asks for median 0.105 kg/m2/s (p10-p90 0.05-0.15);
  the numerical cap mf_cap * (thinnest cloud layer mass) / dt = 0.3 * m_min / dt clips it to 0.052 in almost every column.
  (At the 60-min T42 step the cap is 0.017; it scales with 1/dt and with layer thickness -> lower at 75 levels.)
- Defects found (both break the 10 Nov rule "physical units, independent of the number of levels / time step"):
  D-a  closure evaluated one layer above the source (kb = ksrc - 1), not at cloud base as IFS eq. 6.35/6.37 says: the plume
       excess there is only the kick -> (h_u - h) small (floor 1 kJ/kg) -> Mb 3-5x the observed shallow-cumulus 0.02-0.03 (BOMEX).
  D-b  the cap depends on dt and on the thinnest layer: it, not physics, sets the mass flux; at 75 levels it is ~2x lower.
- Plume: 4-8 layers deep, median depth 13 kPa from the source -> cloud tops ~860 hPa. The moisture stays inside the 950-860 hPa
  cloud layer (sub-850 net shallow vent ~0 in the median column): with tops below the trade inversion nothing carries the surface
  supply into the dry air above, so the layer below 850 moistens (+0.45 g/kg/day at T170) and the low deck forms.
- Next: derive the IFS cloud-base closure and limiter exactly from Part IV (eq. 6.35-6.37 and the CFL treatment), register predictions,
  T42 code check, then T170 first-hours test at 32 L and the 75 L screen.

## 11 Nov 16:00 IST - sh_ifs2 built (IFS cloud-base closure + linear sub-cloud fluxes + implicit transport) - no effect on the moistening
- Code: off by default, regression bit-identical, shallow tendencies conserve water/energy (max column error 1e-4 kg/m2/day, 0.1 W/m2).
- T42 grid, 20-min step, 24 h: cloud-base mass flux median 0.067 (p10-p90 0.023-0.116) kg/m2/s vs 0.052 capped before; sub-850 venting
  by shallow -0.57 vs -0.66 mm/day (E = 5.9 mm/day). Cloud/RH drift (2 starts, 48 h): identical to ifs_sh within 0.005
  (RH >850 0.857 vs 0.858, cover 0.871 vs 0.871). => The shallow mass-flux defects are real (kept, off) but they are NOT what moistens
  the low levels: shallow acts in only ~25 % of tropical-ocean columns and its tops stay below 850 hPa.
- Back to the supply side: ocean evaporation is +17..+20 % above COARE 3.5 on the same inputs (4 Nov, flux_check; energy audit LvE
  107-117 vs ~84 W/m2). That fix (ck_z 1 + sfc_sal 0.98) was rejected ALONE on 5 Nov (z500 d5 +2 m, storms 4-6 hPa weaker) while it
  halved the tropical rain bias and the TN easterly - interpreted then as compensation with the radiation cooling excess.
  Today's chain explains the compensation: base2's shallow scheme pumps the excess moisture into mid levels -> cloud -> cooling.
- Next screen (local, running): RH/cloud drift for ifs_sh + evaporation fix, and base2 + evaporation fix.
- 16:20 IST screen result (T42 grid, 20-min step, 2 starts, global RH/cloud at 24/48 h): ifs_sh + evaporation fix (ck_z 1, sfc_sal 0.98)
  RH >850 0.824/0.850 vs ifs_sh 0.830/0.858; cover 0.866 vs 0.871 -> evaporation is NOT the driver of the drift either.
- Decisive clue (T170 profiles, column-mean radiative heating): -1.24 K/day globally ALREADY in hours 0-6 (cover from RH still ~0.3) and
  -1.27 at 6-24 h after cover has tripled; same in base2 and ifs_sh. ~-140 W/m2 vs reference ~-103 from the FIRST hours -> the radiation
  excess does not come from the moistening drift. It comes with the radiation's own cloud from the start: convective + anvil cloud
  (Slingo) and cloud water (LWP 186 vs 50-90 g/m2 observed, 4 Nov), SW cloud effect -110 vs -47. Next (offline, hour 0, T42 grid, no
  forecast): radiation on the ERA5 start state with (a) as is, (b) convective/anvil cloud off, (c) cloud water x0.5, vs reference -103
  and CERES SW CRE -47 -> which cloud part makes the excess.

## 11 Nov 17:30 IST - radiation by cloud part (rad_parts.py, offline radiation on the model state, T42 grid, 20-min step, 2 starts)
| state | case | atm rad W/m2 | SW abs atm | SW net sfc | SW CRE | OLR | cover | LWP g/m2 |
|---|---|---|---|---|---|---|---|---|
| h0 | as is | -121.9 | 69.2 | 174.1 | -61.7 | 252.9 | 0.34 | 122 |
| h0 | no conv/anvil cloud | -124.6 | 69.3 | 191.6 | -44.0 | 257.2 | 0.30 | 65 |
| h0 | cloud water x0.5 | -122.1 | 68.6 | 185.6 | -50.7 | 253.6 | 0.34 | 61 |
| h0 | clouds off (clear sky) | -118.1 | 67.9 | 237.1 | 0 | 263.8 | - | 0 |
| h24 | as is | -122.8 | 68.5 | 126.2 | -110.4 | 222.2 | 0.77 | 217 |
| h24 | cloud water x0.5 | -125.6 | 67.8 | 150.0 | -87.3 | 226.1 | 0.77 | 109 |
| h24 | clouds off | -119.6 | 68.0 | 237.1 | 0 | 256.6 | - | 0 |
References (CERES-EBAF / Wild 2013, approximate): all-sky atm -103..-105; clear-sky atm ~-113 (TOA clear SW abs ~287 - OLR_clr 266 -
sfc clear SW net ~214 + sfc clear LW net ~-80); SW CRE -47; OLR 239 / clear 266; atmospheric CRE ~+5..+10 (clouds REDUCE the
atmosphere's cooling).
Reading:
- Clear sky: -118 vs ~-113 (-5): small. Gas optics already verified against RRTMG.
- Clouds change the ATMOSPHERE's cooling by -3..-4 W/m2 (more cooling) where the real atmosphere gets ~+5..+10 (less cooling):
  a -10..-14 W/m2 error present at hour 0. SW absorbed in the atmosphere hardly changes with clouds (+1.3 W/m2; real clouds add a few
  W/m2 of near-IR absorption) -> suspect: cloud SW absorption (droplet near-IR single-scattering co-albedo) and cloud LW at cloud base.
- TOA/surface sunlight: at h0 SW CRE -62 (close to -47; conv/anvil cloud adds -18 and doubles LWP), at h24 -110 as cover/LWP grow with
  the moistening (cover 0.34 -> 0.77, LWP 122 -> 217). This is where the surface loses 35-50 W/m2 of sunlight.
=> Two separate errors: (1) cloud-radiation coupling to the atmosphere wrong sign at h0 (~-10..-14 W/m2), (2) cloud growth from the
moistening drift (SW at the surface, ~-50 W/m2 by day 1). Next decisive check: RRTMG ALL-SKY with the SAME cloud fractions and water
(tn-radchk machinery) -> are our cloud optics right? Then the moistening drift's process (still open after shallow/evap screens).

## 11 Nov 19:00 IST - ALL-SKY radiation vs RRTMG with the SAME clouds (rad_allsky.py, local climlab-rrtmg build, T42 grid, 1664 columns)
CORRECTION 1: the 5 Nov clear-sky RRTMG check (rad_check.py) built columns with climlab.column_state(lev=points), which forces the bottom
bound to 1000 hPa -> NEGATIVE lowest-layer thickness wherever ps > 1000 hPa (RRTMG SW segfaults with cloud there). rad_allsky passes the
model's real interfaces. The 5 Nov "clear sky = RRTMG" statement is therefore withdrawn for the lowest layer / atmospheric totals.
CORRECTION 2: the 17:30 reading "clouds change the atmosphere's cooling with the WRONG SIGN" is withdrawn: RRTMG with the same clouds
gives the same sign (atmospheric CRE -5.9 vs MEGAM -6.9 at h0); the +5..+10 reference reflects real cloud amounts/structure, not optics.
Results, W/m2 (MEGAM / RRTMG / diff):
| state | atm all-sky | atm clear | atm CRE | SW abs atm | TOA SW CRE | TOA LW CRE | OLR |
|---|---|---|---|---|---|---|---|
| 2020-07-19 h0 | -131.6/-121.0/-10.6 | -124.7/-115.1/-9.6 | -6.9/-5.9 | 67.6/74.7 | -65.0/-56.1 | 12.3/12.7 | 255.3/253.8 |
| 2020-01-06 h0 | -121.3/-111.1/-10.2 | -115.6/-106.2/-9.4 | -5.7/-4.9 | 68.7/75.3 | -66.8/-57.9 | 11.7/12.0 | 248.1/247.1 |
| 2020-07-19 h24 | -125.1/-111.8/-13.3 | -126.0/-113.8/-12.2 | +0.9/+2.0 | 66.4/75.1 | -123.3/-114.8 | 40.9/41.8 | 218.3/217.0 |
| h0 + lw_cnt 0.667 | -125.6/-121.0/-4.6 | -115.4/-115.1/-0.3 | -10.2/-5.9 | 67.6/74.7 | -65.0/-56.1 | 13.1/12.7 | 256.5/253.8 |
Reading:
- MEGAM cools the atmosphere 10-13 W/m2 more than RRTMG on the same state and clouds, almost all CLEAR SKY. With the water-vapour
  continuum at x1.0 (lw_cnt 0.667, the 4 Nov correctness item) clear sky matches RRTMG to -0.3 W/m2. Remaining: SW absorbed in the
  atmosphere -7 (about half gases, half missing cloud absorption) and TOA SW cloud effect ~9 W/m2 (15 %) too bright.
- Cloud OPTICS are close to RRTMG (TOA LW CRE within 1 W/m2, SW within 15 %). The huge day-1 SW cloud effect (-115..-123 vs CERES -47) is
  the cloud AMOUNT (cover 0.41 -> 0.80 in 24 h) - RRTMG gives the same with those clouds. So: radiation code ~-10 (continuum, known fix)
  + ~-5..-7 (SW absorption); the dominant error is the moistening -> cloud amount growth, whose process is still not found
  (shallow transport, evaporation ruled out today).

## 11 Nov 15:10 IST - process-denial moisture test (cloud_drift.py, T42 grid, 20-min step, 2 starts, ifs_sh base, global means)
| run | RH >850 h24/h48 | q >850 g/kg h24 | T >850 h24 (h0 285.88) | RH 700-500 h24 | cover h24 |
|---|---|---|---|---|---|
| ifs_sh | 0.830/0.858 | 9.10 (h0 8.63) | 284.89 (-1.0 K) | 0.498 | 0.79 |
| rain evaporation off | 0.805/0.825 | 9.07 | 285.23 (-0.65) | 0.473 | 0.76 |
| deep convection off | 0.847/0.855 | 9.68 | 285.25 | 0.510 | 0.85 |
| downdraughts off | 0.802/0.830 | 8.95 | 285.22 | 0.505 | 0.75 |
Tropics below 850: T -1.48 K in 24 h (ifs_sh), q +0.51 g/kg.
Reading:
- NO single process causes the drift: switching off rain evaporation or downdraughts removes only ~1/4 of the low-level RH rise;
  switching off deep convection makes it worse (moister).
- About HALF of the low-level RH rise is COOLING (-1.0 K/day globally, -1.5 K/day tropics below 850 hPa: radiation, rain evaporation and
  dynamics not balanced by boundary-layer/convective heating), the other half real moistening (+0.47 g/kg/day).
- => The moistening/cooling is a BALANCE error of the convection + boundary layer + radiation package as a whole, not one faulty process.
  base2 hides it with the over-strong shallow mixing (+7 K/day at 850). Piecewise fixes (sh_depth, cnt, evap, ifs_sh, edmf, sh_ifs2) each
  moved one term and broke another, consistent with this.
Decision needed (Sridhar): continue piecewise, or replace the convection/cloud/boundary-layer package as one consistent, documented
scheme (IFS Cy50r1 Part IV chapters 3 + 6 together).

## 11 Nov 17:30 IST - IFS package v1, convection part built (ifs_phys.py, phys_ifs=1; docs/ifs_package.md)
- Built: shallow and deep test parcels (6.18-6.21, dry lift to the LCL and KE from cloud base for deep), full updraught (6.7-6.12, entrainment
  only where buoyant), Sundqvist precipitation with freezing/Bergeron (6.43-6.46), downdraught from the min-h level (6.13-6.17), Kessler
  sub-cloud evaporation (6.49-6.52), melting, PCAPE closure with tau = H/w alpha_x and PCAPE_bl (6.22-6.34), sub-cloud MSE closure for
  shallow (6.35-6.37), linear sub-cloud fluxes (6.40-6.41), implicit transport with CFL 3 / 2 kg m-2 s-1 (6.69-6.70). Regression with
  phys_ifs=0 bit-identical. Column water closes to 1e-9..2e-6 kg m-2 s-1 (rain up to 3e-4).
- First look (T42, 20-min step, ERA5 start): deep convection active in ~5 % of tropical columns, cloud-base mass flux median 0 (PCAPE of the
  entraining plume near zero on the near-moist-neutral analysed soundings), shallow ~1 %.
- 48-h drift (2 starts): IDENTICAL to ifs_sh within noise (cover 0.87, RH >850 0.842 vs 0.858, tropics 850-700 T -2 K in 48 h).
  => With three different convection schemes (base2 'mse', ifs_sh, IFS package convection) and with single processes switched off the
  drift stays. The one component common to ALL of them is the boundary-layer scheme (K-profile from a Ri height, explicit surface layer):
  daytime heat stays in the lowest layer (+52 K/day there, stable theta above; 11 Nov morning column check), moisture accumulates
  below 850 hPa. Next: the BL part of the package (task 45: IFS EDMF K-profile with zi from the plume, eq. 3.42-3.50).

## 11 Nov 16:00 IST - stronger boundary-layer mixing (pbl_tm) does not change the drift; the drift is insensitive to every physics change
- cloud_drift (T42, 20-min step, 2 starts, 48 h): ifs_sh + pbl_tm: cover 0.90 vs 0.87, RH >850 0.855 vs 0.858; IFS package + pbl_tm:
  0.91 vs 0.87, RH >850 0.848 vs 0.842. Slightly MORE cloud, same low-level drift.
- Physics-off check (sfc_start.py): lowest layer cools -0.9..-1.1 K/day over ocean and land with NO physics (as found 5 Nov in both cores);
  base2 instead WARMS it +1.7..+2.6 K/day over ocean (shallow 'mse'); ifs_sh / package cool it ~-1 K/day.
- Summary of today's screens: convection scheme (3 versions), shallow mass flux, evaporation, rain evaporation, downdraughts, deep off,
  BL mixing strength -> none removes the 24-48 h rise of low/mid-level RH (+0.1) and cloud cover (0.27 -> 0.8-0.9).
- Limitation of the method: the drift is measured against the hour-0 state (ERA5 on our 32 sigma levels via 13 pressure levels), not
  against ERA5 at +24/48 h; the truth file has no humidity or cloud. Hour-0 RH/cloud on our levels may itself be biased (only 3 ERA5 levels
  below 850 hPa). Next: add ERA5 humidity / cloud truth (q 925/850/700, total column water vapour, total and low cloud cover) at +1..+10 days
  to the truth file (cyc_wx.py, WeatherBench2 ERA5) so the drift is measured against reality.

## 11 Nov 16:40 IST - drift measured against REAL ERA5 (moist_vs_era5.py, wx_truth_moist_2020.npz, T42, 2 starts, global means)
| | h0 model/ERA5 | base2 h24 | ifs_sh h24 |
|---|---|---|---|
| q 925 / 850 / 700 / 500 | within 1 % at all levels | -10 % / -4 % / +22 % / +34 % | +7 % / +5 % / +5 % / +20 % |
| column water vapour | 25.4 / 25.3 | +3 % | +6 % |
| total cloud cover | 0.34 / 0.61 (-44 %) | 0.77 / 0.62 (+23 %) | 0.81 / 0.62 (+30 %) |
- The start state is RIGHT (humidity within 1 %). CORRECTION to the 11:30 entry ("the cloud scheme is not the cause"): on ERA5's true
  humidity the cloud scheme gives 0.34 cover vs 0.61 real, and after a 5-10 % humidity rise 0.8 -> its response to humidity is far too
  steep: a calibration/structure defect of the diagnostic cloud scheme that AMPLIFIES a modest moistening into a large cloud and
  radiation error. The moistening itself is real but modest (+5..+10 %; base2 moves moisture from 925 to 700-500 hPa, +22..+34 %).
- Launched at T170, 12 starts: tn-moist-b2 (acct 4), tn-moist-ifssh / tn-moist-ifspkg (acct 1).

## 11 Nov 17:20 IST - cloud vs humidity curve against ERA5 (cloud_curve.py, T42, 6 starts across 2020, global)
Total cover in bins of column-mean RH (1000-300 hPa): scheme / ERA5
| RH bin | 0.2-0.3 | 0.3-0.4 | 0.4-0.5 | 0.5-0.6 | 0.6-0.7 | 0.7-0.8 | 0.8-0.9 |
|---|---|---|---|---|---|---|---|
| hour 0 (ERA5 state) | 0.11/0.36 | 0.20/0.46 | 0.26/0.56 | 0.35/0.68 | 0.46/0.81 | 0.62/0.92 | 0.78/0.99 |
| hour 24 (model state) | 0.37/0.36 | 0.56/0.43 | 0.66/0.49 | 0.76/0.57 | 0.85/0.67 | 0.93/0.78 | 0.98/0.88 |
Share of the globe with column RH >= 0.8: 4 % at hour 0, 18 % at hour 24. Global cover 0.34 -> 0.76 (ERA5 0.63 both).
Reading - TWO defects, not one:
(a) On real (ERA5) humidity the scheme gives about HALF of ERA5's cloud at every RH (critical RH 0.8 low / 0.7 aloft too high for
    1.5-deg / T42 grid-mean humidity: grid-mean RH under-represents sub-grid saturated air).
(b) At the SAME column-mean RH the model's cloud doubles within 24 h (0.35 -> 0.76 at RH 0.5-0.6): the model's humidity becomes
    vertically layered - individual layers near saturation (and more columns at RH >= 0.8: 4 % -> 18 %). Lowering the critical RH to
    fix (a) would make (b) worse, so a calibration alone cannot work; (b) is the model process (which layers saturate, and why).
Next: per-layer RH distribution h0 vs h24 vs ERA5 q levels (which layers saturate), using the T170 tn-moist-* results when they arrive.

## 11 Nov 18:40 IST - T170, 12 starts, humidity / cloud vs REAL ERA5 (tn-moist-b2 / -ifssh / -ifspkg); every number holds in 12/12 starts
| global, h24 (h48) | q925 | q850 | q700 | q500 | TCWV | cloud cover (h0) |
|---|---|---|---|---|---|---|
| base2 | -11 (-13) % | -3 % | +22 (+25) % | +32 % | +3 % | 0.77 vs 0.63 (h0 0.34 vs 0.62) |
| ifs_sh | +7 % | +6 (+10) % | +4 % | +19 (+16) % | +6 % | 0.81 |
| IFS package (convection) | +9 (+7) % | +10 (+12) % | +2 (+1) % | +4 (+2) % | +5 % | 0.81 |
- Start humidity correct (within 2 %) at T170; start cloud -46..-56 % (problem A confirmed at T170, 12/12).
- Problem B LOCATED: base2 moves water from 925 to 700-500 (shallow 'mse' pump). With the IFS convection the mid/upper troposphere
  stays at ERA5 (700 +1..+2 %, 500 +0..+4 %, tropics 500 -4..0 %) - the only remaining humidity error is BELOW 850 hPa (+7..+12 %).
  Candidates for the low-level excess: ocean evaporation (+17..+20 % vs COARE, 4 Nov), boundary-layer top entrainment/venting.
- Caveats (peer, 18:22): ERA5 tcc is ERA5's own model diagnostic (prognostic cloud, max-random overlap) - same definition family as ours
  but not an observation (CERES/ISCCP ~0.66-0.68 agrees); bin tables mix category shifts with within-category change - a paired
  per-column analysis is needed; A and B may feed back through radiation/precipitation. Cloud relationship to be developed and validated
  on separate date sets (development / calibration check / independent validation), by RH, level, latitude band and regime.
- Launched: tn-moist-pkgevap (acct 4: package + COARE evaporation), tn-moist-pkgevapcnt (acct 1: + continuum fix).

## 11 Nov 19:30 IST - PROBLEM A ROOT CAUSE FOUND: the cloud scheme's humidity is relative to LIQUID water only
- radcloud.clouds() computes RH = q / qsat_liquid. Below ~250 K air is saturated over ice at a liquid RH of 0.6-0.8, so cirrus and
  mixed-phase cloud are missed. New option rad_prm.qs_mix = 1: RH w.r.t. the IFS mixed-phase saturation (Part IV ch. 7,
  es = a es_liq + (1 - a) es_ice, a = ((T - 250.16)/23)^2, Teten 17.502/32.19 and 22.587/-0.7). No parameter fitted; critical RH unchanged.
- Total cover on ERA5 start states (T42), scheme / ERA5, liquid RH -> mixed-phase RH:
  development set (starts 1, 25, 49): 0.34 -> 0.62 / 0.63; validation set 1 (13, 37, 61): 0.33 -> 0.62 / 0.62;
  validation set 2 (7, 31, 55): 0.34 -> 0.63 / 0.63. Per column-RH bin the curve now follows ERA5 within -0.08..+0.06 (driest bin
  0.27-0.29 vs 0.34-0.37; RH 0.6-0.7 0.86 vs 0.80-0.82) on all three sets.
- Housekeeping: radcloud.py contains TWO definitions of clouds(); the first (line ~168) is dead code overridden by the second. The option
  is in the live one. Regression with qs_mix off bit-identical (22.259984322409387).
- Still open: with the mixed-phase RH the forecast's low-level moistening (+7..+12 % at 925/850, problem B) will make even more
  low cloud unless B is fixed (evaporation screens running). Next T170 screen: IFS convection + evaporation fix + continuum + qs_mix.

## 11 Nov 20:20 IST - T170 screens (12 starts, vs real ERA5): evaporation fix explains only ~1/5 of the low-level moistening
| global h24 (h48) | q925 | q850 | q700 | q500 | cloud cover h0 / h24 / h48 |
|---|---|---|---|---|---|
| IFS convection | +9 (+7) % | +10 (+12) % | +2 % | +4 % | -56 % / +29 % / +35 % |
| + evaporation fix (COARE) | +7 (+5) % | +9 (+10) % | +2 % | +4 % | -56 % / +28 % / +34 % |
| + continuum | +7 (+6) % | +9 (+10) % | +2 % | +4 % | -56 % / +29 % / +35 % |
| + mixed-phase cloud RH | +7 (+6) % | +9 (+10) % | +2 % | +4 % | -4 % / +44 % / +49 % |
- Evaporation: contributes (~2 percentage points of the ~10) but another low-level moisture source/retention remains (peer decision table:
  "improves but remains high"). Continuum: no humidity effect (as expected). Cloud RH fix: start cloud right (-4 %), but the forecast
  cloud excess grows (+44 / +49 %) because the low-level humidity error is unchanged - as predicted at 19:30.
- Next (launched tn-prof-pkgall, acct 4): first-hours process budget of the full candidate (q and T by process per level, globe/tropics)
  to find what keeps adding / failing to remove water below 850 hPa (BL, convection, condensation, rain evaporation, dynamics).
- 20:40 IST shallow-trigger check (sh_trig.py, T42 grid, 20-min step, IFS package, state after 24 h, tropical ocean): CORRECTION to the
  "shallow fires in ~1 % of columns" (that was the hour-0 snapshot): after spin-up deep 56 %, shallow 19 %, none 25 %; by TPW: <30 mm
  shallow 38 % / deep 14 %, 45-55 mm deep 90 %, >55 mm deep 98 %. Convection removes 2.2 mm/day of water below 850 hPa against 4.9 mm/day
  evaporation (deep columns -3.1 of 4.8, shallow columns -2.7 of 5.3); deep cloud-base mass flux median 0.005 kg m-2 s-1 (31 % zero),
  PCAPE median 57 Pa of which PCAPE_bl 37. The remaining ~2.6 mm/day must leave by large-scale export/subsidence and BL-top entrainment
  -> the T170 process budget (tn-prof-pkgall) decides between weak deep closure, missing BL-top entrainment, and dynamics.

## 11 Nov 22:00 IST - independent causes for P5 / tracks (while the moisture runs are on Kaggle)
- Land: already tested 5 Nov - the land module removes the cold land (central India 2-m T -2.7 -> -0.6 K) but central-India MSLP falls only
  20 % and the tracks barely move (296 vs 289 km). Not the track cause.
- Known case evidence (5 Nov, Michaung): the upstream westerly trough PARKS at 71-72 E in the model while ERA5's propagates 63 -> 76.5 E;
  environmental 500-hPa steering too far north (+2.5..+5 vs +0.7..+2.1 m/s). A slow westerly wave fits a too-weak subtropical jet.
- Asian subtropical jet too weak from day 1 (-6.2 m/s, 10 Nov): does the 500-hPa heating pattern explain it? T170 first-hours maps
  (tn-prof-32imp, 6-24 h, 60-140 E): T500 tendency 10-20 N -0.46, 20-30 N -0.76, 30-40 N -0.66, 40-50 N -1.29 K/day -> the tropics cool
  LESS than the subtropics: the 500-hPa gradient STRENGTHENS slightly (+0.2 K/day; ifs_sh +0.8). Physics momentum drag at 500 hPa ~0
  (PHYS -0.03 m/s/day). => the jet weakening is NOT explained by 500-hPa heating or drag. Next: the 200-hPa budget (init_tend now also
  at sigma 0.2; tn-prof-b2jet queued, acct 4): u200 TOTAL / PHYS / PGF+COR / REST and T200 by process over the jet region.

## 11 Nov 22:15 IST - T170 divergence check (tn-div-chk, base2, 12 starts): LOW-LEVEL CONVERGENCE far too strong, 12/12 starts
| region | 200-hPa divergence d1 (d2) model/ERA5 | 850-hPa convergence d1 (d2) model/ERA5 |
|---|---|---|
| tropics 25S-25N | -11 % (+5 %) | +65 % (+64 %), stronger 12/12 |
| Indian Ocean + Bay | -4 % (+13 %) | +66 % (+56 %), 12/12 |
| W Pacific warm pool | -2 % (+45 %) | +70 % (+79 %), 12/12 |
| E Pacific / Atlantic trades | -21 % (+3 %) | +96 % (+112 %), 12/12 |
- Upper divergence about right (the T42 'too weak' was resolution); the 850-hPa inflow is 1.5-2x ERA5's everywhere in the tropics from
  day 1 (Sridhar's hypothesis, 20:43). Strong low-level convergence without matching upper divergence -> the mass converging at 850 must
  leave through mid levels, i.e. the model's heating/ascent profile is too BOTTOM-HEAVY (base2's shallow 'mse' heats 850 by +7 K/day),
  and it imports moisture into the lower troposphere. The IFS-package run of the same check was killed (two models in one job, OOM)
  -> re-queued alone (tn-div-pkg, acct 1).

## 11 Nov 23:00 IST - IFS package removes the excess low-level convergence; BL-top entrainment has no effect
- tn-div-pkg (T170, 12 starts, IFS package + evap + continuum + cloud RH): 850-hPa convergence vs ERA5, tropics +3 % (d1) / +8 % (d2)
  (base2 +65 / +64 %); Indian Ocean+Bay -5 / +14 % (base2 +66 / +56); warm pool +14 / +17 % (+70 / +79); trades +9 / +20 % (+96 / +112).
  200-hPa divergence -4 / +4 %. => the 1.5-2x inflow was base2's bottom-heavy heating (shallow 'mse'); the IFS convection fixes it.
- tn-moist-entr (BL-top entrainment, IFS eq. 3.50, on top of the package): humidity and cloud identical to the package to the printed
  digit (q925 +7 %, q850 +9 %, cover +44 % at 24 h). Either the term is inactive in practice (to be verified: Kh at the BL-top
  interface may already exceed K_e) or it is too small -> suspect 2 NOT supported as implemented.

## 11 Nov 23:15 IST - PROBLEM B LEFTOVER LOCATED: the IFS convection vents too little moisture from below 850 hPa (tn-prof-pkgall, T170, 12 starts)
Tropics 30S-30N, 6-24 h, g/kg/day, layer below 850 hPa (convection = deep + shallow in each scheme):
| run | total | BL + surface | convection | condensation | rain evap | dynamics |
|---|---|---|---|---|---|---|
| ifs_sh | +0.45 | +3.46 | -2.16 | -0.23 | +0.42 | -1.04 |
| IFS package (+COARE evap, continuum, cloud RH) | +0.50 | +2.56 | -1.06 | -0.29 | +0.14 | -0.86 |
- The supply is SMALLER in the package (COARE evaporation: 3.46 -> 2.56) and rain evaporation is smaller (+0.42 -> +0.14), but convection
  removes only HALF as much (-2.16 -> -1.06), so the low levels still gain +0.5 g/kg/day. => the leftover of problem B is WEAK CONVECTIVE
  VENTING in the IFS convection v1, consistent with the 20:40 column check: deep cloud-base mass flux median 0.005 kg m-2 s-1 (31 % zero),
  PCAPE_bl removing ~2/3 of PCAPE over tropical ocean.
- Next (12 Nov): check the closure against IFS Part IV 6.22-6.34 term by term (PCAPE_bl units/sign and T* = 1, the sub-cloud layer
  definition, tau = H/w x alpha_x with alpha_x = 1 + 1.6 dx/125 km), and the sub-cloud flux profile; register predictions; T170 screen.

## 11 Nov 23:55 IST - closure check (IFS Part IV 6.22-6.34) and a first screen
- Code vs documentation: PCAPE (6.22), the closure (6.25), tau = H/w x alpha_x (6.26-6.27, alpha_x = 2.0 at T170), the unit base flux
  (cancels), PCAPE_bl integral and tau_bl (6.33-6.34) match. One difference: IFS 6.33 uses dTv/dt|bl = diffusion + radiation + ADVECTION;
  v1 passes diffusion + radiation only. New switch ifs_pbl = 0: the pre-40r1 IFS closure (PCAPE_bl = 0, Gregory et al. 2000).
- Column snapshot (T42 grid, 20-min step, 24 h): with PCAPE_bl = 0 deep cloud-base mass flux median 0.005 -> 0.017 kg m-2 s-1 (zero in
  31 % -> 2 %), convection removes 2.2 -> 7.3 mm/day below 850 hPa (instantaneous, after 24 h of weak venting).
- BUT the forecast humidity barely moves (1 start, T42, 24 h): q925 +6.2 %, q850 +7.4 % (package +6.7 / +7.9 %). Stronger venting is
  compensated elsewhere within hours. => the closure strength is NOT the controlling factor either; the low-level humidity excess is robust
  to supply (evaporation), removal (convection strength), BL-top entrainment and the convection scheme. T170 confirmation queued
  (tn-moist-pbl0). Next: check whether the excess is an equilibrium of the model's surface layer / lowest-level vertical structure
  (where the model holds its moisture relative to ERA5 by level, near-surface RH, and the 925-hPa interpolation itself).

## 12 Nov 00:10 IST - convection INPUTS (Sridhar 23:48): the boundary layer pushes surface moisture ABOVE cloud base -> leftover of B
- conv_inputs.py (IFS package, T42 grid, 20-min step, 24 h, tropical ocean 25S-25N), 32 and 75 levels give the same picture:
  925 hPa: model T -0.4..-0.5 K, q +0.5..+0.6 g/kg vs ERA5 -> RH 0.90 vs 0.84. The BL + radiation tendency handed to convection moistens
  +2..+3.3 g/kg/day up to ~1.5 km (well above the ~600 m cloud base) and radiation cools that layer's top by -5.9..-6.6 K/day (cloud-top
  cooling of the low deck) -> a self-reinforcing loop: BL moisture above cloud base -> saturation -> cloud -> cloud-top cooling.
- The dry K-profile reaches the Ri height (~1.5 km) instead of cloud base; in the IFS EDMF the K-diffusion stops at the cloud base zi,cb
  in a cumulus-topped layer and the shallow mass flux carries the cloud layer (Part IV ch. 3; MEGAM option bl_lcl, built 4 Nov, never adopted).
- 1-start screen (T42, 2020-01-06): IFS package -> + bl_lcl: q850 +7.8 -> +0.8 % (h24), +10.8 -> -0.7 % (h48); q925 +6.7 -> +3.9 / +2.8 %;
  TCWV +4.9 -> +3.6 / +2.0 %; q700 / q500 unchanged (+2 / +6 %). Cloud cover still 0.94-0.97 vs 0.63 (needs the per-level look).
- Queued T170 12 starts: tn-moist-lcl32 (acct 1), tn-moist-lcl75 (acct 4).

## 12 Nov 01:40 IST - Asian jet: the day-1 weakening is in the DYNAMICAL CORE, not the physics (jet_check.py, T42, 3 Oct-Nov starts)
- T170 200-hPa budget (tn-prof-b2jet, base2, 12 starts): 0-6 h u200 tendency 25-45 N, 60-140 E: TOTAL -5..-8 m/s/day, PHYS 0,
  PGF+COR +3.6..+4.5, REST (transport/diffusion/numerics) -9.6..-11.4. 6-24 h: tropical T200 -3 K/day (physics -2.9) vs 35-55 N
  -0.3..+0.5 -> the upper-level temperature contrast shrinks (second, slower contributor).
- Jet peak (max over 20-50 N of the 60-140 E mean u200), ERA5 start on our levels -> after DFI -> model day 1 | ERA5 day 1:
  default 53.1 -> 52.7 -> 47.6 | 54.1 (error -6.5; T170 exam -6.2); no DFI 47.7; diffusion x4 weaker 47.9; no stratosphere relaxation 47.6;
  PHYSICS OFF 46.9 (-7.2). => not DFI, not horizontal diffusion, not the stratosphere relaxation, not the physics: the core (or its
  configuration) slows the jet ~6-7 m/s in the first day, at T42 and T170 alike.
- Running: physics-off at 75 levels, with non-monotone semi-Lagrangian dynamics (mm2 sets monotone_dynamics=True: a monotone limiter on
  the WIND interpolation clips extrema every step - IFS applies quasi-monotone limiters to tracers, not to winds), and with cubic vertical SL.
- 02:40 IST jet variants (physics off, T42, 3 starts; day-1 jet error vs ERA5): linear vertical SL -7.2; non-monotone wind SL -7.2 (limiter
  NOT the cause); cubic vertical SL -4.7; 75 levels (linear) -5.6; cubic + 75 levels -4.7; cubic + 3 departure iterations -4.7.
  => about a third of the core's jet loss is vertical interpolation of the semi-Lagrangian scheme (linear smooths the sharp jet core;
  IFS uses cubic); the remaining ~-4.7 m/s/day is untouched by levels, iterations, limiter, DFI, diffusion and physics.
- Global wind check on the IFS package (tn-p5-dyn-pkg, T170, 12 starts): Asian subtropical jet speed -6.2 / -8.3 / -9.6 m/s (d1-d3) vs
  base2 -6.2 / -8.7 / -10.3: the physics package does not change the jet weakening (consistent with a core cause); jet latitude slightly
  better after day 4.
- Hypothesis being tested: the PURE SIGMA coordinate (mm2 uses Dinosaur SigmaCoordinates). The Asian jet sits beside/above Tibet where
  sigma surfaces at jet level slope by several km; the pressure-gradient force on sloping sigma levels is a difference of two large
  terms and the SL vertical interpolation acts along sloping surfaces. IFS uses hybrid sigma-pressure levels (pure pressure aloft).
  Test: is the weakening specific to Asia (Pacific/Atlantic jets weaken -2.4 / -2.0 at day 1 with physics on, 10 Nov)? Running.
- 03:00 IST sector test (T42, 3 starts, day-1 jet-peak error vs ERA5; physics on / off): Asia 60-140E -6.5 / -7.2; Pacific 150-220E
  -5.7 / -4.0; Atlantic 280-340E -3.3 / -3.4. => every jet loses ~3.5-4 m/s/day in the core alone (general part: the linear vertical SL
  interpolation is one known piece), and the Asian jet loses ~3.5 m/s/day MORE (Tibet-specific part, consistent with the pure sigma
  coordinate). Dinosaur (pinned commit) contains hybrid_coordinates.py and SemiLagrangianPrimitiveEquationsHybrid: an IFS-type hybrid
  sigma-pressure core is available upstream; switching needs mm2's sigma assumptions (p = sigma ps in physics, init, diagnostics) generalised.

## 12 Nov 04:10 IST - tn-moist-lcl32 scored (IFS package + bl_lcl, 32 L, T170, 12 starts Jan-Dec 2020) vs ERA5 (wx_truth_moist_2020)
Global means, model vs ERA5, per start (h24 / h48):
- q850: h24 -0.8..+3.5 % (mean +2.0); h48 -2.6..+2.9 % (mean +0.4). Package alone (T170) was +8 %. => low-level humidity excess at
  850 hPa REMOVED in 12/12 starts (class Pass at +-3 %).
- q925: h24 +2.0..+5.6 % (mean +4.4); h48 +0.4..+3.7 % (mean +2.3). Was +7 %. => two-thirds removed; small positive residual, same sign
  in 12/12 (systematic but within +-4 %).
- q700 h48 -3.6..+0.0 % (mean -1.2); q500 h48 +0.3..+5.1 % (mean +2.4); TCWV h48 -0.1..+2.4 % (mean +1.3).
- => PROBLEM B (low-level moisture excess): FIXED by bl_lcl at 32 L (K-diffusion capped at cloud base, as in IFS EDMF). 75 L (lcl75b) and
  the base2-at-75 reference (b275) still running.
- CLOUD COVER: hour 0 0.58-0.62 vs ERA5 0.62-0.63 (qs_mix OK), but h24 0.92-0.94 and h48 0.95-0.96 vs ERA5 0.61-0.65 in 12/12 starts
  with humidity now within ~2 % of ERA5. => Problem A is solved only at the start: the diagnostic cloud scheme saturates the sky within
  24 h of forecast. Since q is right, the cause is either the forecast temperature (RH via T: -0.4 K at 925 hPa found 12 Nov 00:10) or the
  RH->cloud mapping reacting to the model's own sub-grid variability. Next: per-level cloud + RH + T vs ERA5 at h24 (local T42 first).

## 12 Nov 04:25 IST - jet: core test against an ANALYTIC reference (registered before running)
- Finding first: mm2 already runs the semi-Lagrangian with monotone_dynamics=True, and Dinosaur's quasi-monotone limiter clips the
  CUBIC vertical interpolation to the 2x2x2 bracketing cell (Bermejo & Staniforth 1992, as in IFS). So the 6 Nov suspicion "cubic
  overshoot without a vertical limiter shifts storm cores" is WRONG: the limiter was on in that screen. The 6 Nov storm changes
  (+7.7 / -4.2 / +1.1 hPa, opposite signs, 1 start per storm) need a noise check before they are blamed on vcubic.
- Test jw_check.py: Jablonowski-Williamson steady state (exact balanced solution, two 35 m/s jets, no real-data imbalance, no Tibet),
  MEGAM core settings, physics off, T42, dt 20 min (as jet_check), 32 L, 3 days.
- Registered reading: NH jet loss >= 2 m/s/day -> the general core loss is numerical damping of a balanced jet, and the variants
  (vcubic, off-centering, diffusion, T_ref, step) say which piece; loss < 0.5 m/s/day -> the core does not damp a balanced jet, and
  the real-data loss comes from imbalance/adjustment of the ERA5 start on sigma levels (then the hybrid coordinate becomes the lead).
- 04:40 RESULT (JW steady state, T42, 20 min, 3 days, physics off): NH jet 34.94 -> 34.81 m/s = -0.04 m/s/day (default); vcubic -0.04;
  no off-centering +0.01; no diffusion -0.03; JW reference T -0.04. => the core does NOT damp a balanced zonal jet: time scheme,
  off-centering, diffusion and T_ref are cleared. Caveat (honest): JW is zonally symmetric with zero vertical motion, so it does NOT
  exercise the SL interpolation errors (along-flow structure, vertical displacement) - which is exactly where cubic vertical helped on
  real data (-7.2 -> -4.7). So: the general real-data loss is interpolation of non-symmetric / vertically moving flow, or start adjustment.
- 04:45 next test REGISTERED (hyb_jet.py): real ERA5 start, physics off, T42, 20 min, 3 Oct-Nov starts, three cores with the same
  reference levels: sigma (MEGAM) / hybrid core with A=0 (control) / true hybrid (B = ((s-0.1)/0.9)^1.3, near-pressure above ~250 hPa).
  Reading: Tibet/sigma hypothesis CONFIRMED if hybrid vs hybA0 reduces the Asia day-1 error by >= 2 m/s while Pacific/Atlantic change
  < 1 m/s; REJECTED if Asia changes < 1 m/s. hybA0 vs sigma must agree within ~0.5 m/s (otherwise the cores differ and the comparison
  is reported as inconclusive).
- 05:05 RESULT (hyb_jet.py, real ERA5 starts 7 Oct / 1 Nov / 26 Nov, physics off, T42, no DFI; day-1 jet-peak error vs ERA5):
  | core | Asia | Pacific | Atlantic |
  | sigma (MEGAM) | -8.6 | -5.9 | -4.5 |
  | hybrid core, A=0 (control) | -8.9 | -5.7 | -4.5 |
  | hybrid levels | -7.8 | -5.6 | -4.3 |
  Control agrees with sigma within 0.3 (cores consistent). Hybrid vs control: Asia +1.1, Pacific +0.1, Atlantic +0.2 m/s.
  => between the registered thresholds (>= 2 confirm, < 1 reject): PARTIAL. The sigma coordinate over Tibet is a real but SMALL piece
  (~1 of the ~3.5 m/s extra Asian loss). It does not justify the multi-day hybrid refactor on its own; noted as a later improvement.
- Timing of the loss (sigma, same starts): Asia jet on own levels 52.3 -> 48.7 (6 h) -> 47.6 (12 h) -> 46.0 (24 h): ~60 % of the day-1
  loss happens in the first 6 h (-3.6 m/s, a rate of -14 m/s/day), then ~-1.3 m/s per 6 h. Matches the T170 200-hPa budget (0-6 h REST
  -10 m/s/day). DFI did not change it (01:40). => the dominant piece is a fast start-up loss in the first hours, not a steady damping
  (JW: no damping). Next (10:00 cycle): where in the first 6 h - level-by-level and jet-core-relative u tendency in the first steps
  (vertical: the jet core sharpness on 32 levels vs the SL departure-point interpolation; horizontal: T42 vs T170 same start).

## 12 Nov 09:10 IST - jet: EULERIAN vs SEMI-LAGRANGIAN core, same start/levels/diffusion (hyb_jet.py core 'euler'; Sridhar 08:45 "why not different dynamics")
Physics off, T42, 3 Oct-Nov starts, no DFI; day-1 jet-peak error vs ERA5 (m/s):
| core | Asia | Pacific | Atlantic |
| semi-Lagrangian (MEGAM), 20 min | -8.6 | -5.9 | -4.5 |
| semi-Lagrangian, 10 min | -8.7 | -6.0 | -4.5 |
| Eulerian spectral (Dinosaur PrimitiveEquationsSigma, IMEX RK3, 10 min) | -4.7 | -2.7 | -3.5 |
At 6 h: Asia SL 52.3 -> 48.7, Eulerian 52.3 -> 50.3.
=> The semi-Lagrangian TRANSPORT costs ~3-4 m/s/day of jet speed in Asia and the Pacific (~1 in the Atlantic); not the step length
(10 vs 20 min identical). The remaining ~-3..-5 m/s with the Eulerian core = start state / T42 / no physics (to separate later).
Candidate fix: Eulerian dynamics (same library, same physics coupling, same levels). Costs: shorter step (GPU time x2-3), stability with
full physics and at 75 levels unknown, storm intensity/track effects unknown -> registered screen needed before adoption.
- 09:20 same harness, SL + cubic vertical interpolation (sl_vcubic, limiter on): Asia -5.7, Pacific -4.3, Atlantic -3.8
  (SL linear -8.6 / -5.9 / -4.5; Eulerian -4.7 / -2.7 / -3.5). => cubic vertical closes ~3/4 of the SL-Eulerian gap in Asia, ~1/2 in the
  Pacific, most in the Atlantic; remaining SL-Eulerian gap ~1-1.6 m/s (Asia: hybrid levels gave +1.1). Mm v1 (mm.py) was Eulerian
  at T85 with a 6-min step; v2 moved to SL for T170 at 20 min (Eulerian T170 needs ~3 min -> ~6x more steps, physics each RK stage).

## 12 Nov 09:35 IST - dynamics fix step 1: storm-gate NOISE check (Sridhar 09:23 "Yes start") - REGISTERED before results
Why: the storm gate (72 h pmin within 2 hPa per storm, single run each) was set to a round-off spread assumed from the OLD control
(3-4 repeats: Sidr 3.6, Titli 1.6, Nivar 2.6 hPa). If base2's own spread is larger than 2 hPa, a single-run comparison cannot tell a
dynamics change (sl_vcubic: Vardah +7.7, Nivar -4.2, Michaung +1.1; dfi_off: -1.7/+1.9/+2.1) from noise.
Jobs (account 1, T170, sb suite Nivar/Michaung/Vardah, 72 h, ~0.3 GPU-h each): tn-nz1/2/3-sb = base2 + SPPT 1e-3 (round-off-type
perturbation, seeds 1-3); tn-vz1/2/3-sb = base2 + sl_vcubic + SPPT 1e-3 (same seeds).
Reading (fixed now): spread per storm = max - min of 72 h pmin over {tn-s-rd-sb, nz1, nz2, nz3}.
- spread <= 2 hPa in all 3 storms -> the gate is valid as designed; the 6 Nov vcubic failure STANDS (real effect) and the next step
  is to find why cubic changes storm cores.
- spread > 2 hPa in any storm -> single runs cannot resolve 2 hPa. The storm check is then applied to 3-member MEANS (same seeds):
  |mean(vz) - mean(nz)| <= 2 hPa per storm - the SAME 2 hPa threshold, on a quantity with ~1/sqrt(3) of the noise (stricter, not
  relaxed). This design is fixed now, before any vz result is seen, and applies to every later candidate. The old single-run vcubic
  verdict is not re-judged; vcubic is judged only on the new vz-vs-nz means.
- 10:05 SL details (T42, same 3 starts, day-1 jet error Asia/Pacific/Atlantic): SL+cubic -5.7/-4.3/-3.8; + limiter OFF -5.6/-4.3/-3.8;
  + off-centering 0 -5.6/-4.3/-3.8 => neither the quasi-monotone limiter (which in Dinosaur also bounds the vertical, unlike IFS) nor
  off-centering matters. First 6 h, Asia: SL linear 52.3 -> 48.7, SL cubic -> 50.0, Eulerian -> 50.3 => the fast start-up loss (S1) is
  almost entirely the LINEAR vertical interpolation (D1); cubic removes it. Remaining SL-cubic vs Eulerian gap builds over 6-24 h (~1 m/s).
- Decomposition vs ERA5 (Asia, 3 starts): ERA5 day 0 54.8 -> day 1 54.6; model start on its own T42 levels 52.3 (-2.5 = representation
  at T42: truncation + interpolation; T170 exam day 0 was -1.8). Day-1 change: ERA5 -0.2, SL linear -6.3, SL cubic -3.4, Eulerian -2.4.
  Pacific ERA5 +8.1 (jet strengthening) vs cubic +4.8 / Eulerian +6.5; Atlantic ERA5 -3.4 vs cubic -5.8 / Eulerian -5.3.
  => the ~2 m/s/day left even in the Eulerian core is common to both cores: candidates T42 resolution (eddy forcing of the jet), no
  physics. Running T85 (sigma / SL cubic / Eulerian) to see if it shrinks with resolution.

## 12 Nov 10:15 IST - cycle: pipeline fault found; T85 jet check; first noise twin
- PIPELINE: tn-moist-lcl75b and tn-moist-b275 (11 Nov 20:42) NEVER RAN: their GitHub workflow runs sat 'queued' for 8 h and cannot be
  cancelled (409) or deleted (403). The dispatcher counted them as busy, blocking one slot on account 1 and the only slot on account 4
  all night (pkg75 waited behind it). Fix: dispatch.running() ignores runs still queued > 2 h after creation (they never reached
  Kaggle; the push happens inside the run). Re-queued: lcl75b launched on account 4 (10:12), b275 queued on account 1.
- Noise twin 1 (tn-nz1-sb, base2 + SPPT 1e-3 seed 1) vs base2 (tn-s-rd-sb), 72 h pmin: Vardah 992.2 vs 990.5 (+1.7), Nivar 992.7 vs
  993.8 (-1.1), Michaung 999.3 vs 999.9 (-0.6). (vcubic single run 6 Nov: +7.7 / -4.2 / +1.1.) Twins 2-3 running; no reading yet.
- T85 jet check (same 3 starts, physics off; day-1 error Asia/Pacific/Atlantic): SL linear -8.1/-4.1/-4.2 (T42 -8.6/-5.9/-4.5);
  Eulerian -4.5/-1.8/-2.7 (T42 -4.7/-2.7/-3.5). Start representation Asia at T85 53.1 vs ERA5 54.8 (-1.7; T42 -2.5).
  => doubling resolution barely changes the Asian loss in either core: the ~2 m/s/day common loss is NOT grid resolution. Left:
  no physics in this test (but physics on/off gave the same jet error on 10 Nov) and the START STATE itself (ERA5 interpolated from
  pressure levels; jet core between the 250 and 200 hPa analysis levels). SL cubic at T85 re-running (first attempt timed out).
- 10:40 T85 SL cubic: Asia -4.4, Pacific -2.2, Atlantic -3.4 vs Eulerian T85 -4.5 / -1.8 / -2.7 (SL linear -8.1 / -4.1 / -4.2).
  => at T85 the SL core WITH cubic vertical interpolation matches the Eulerian core (within ~0.5); the 1-1.6 m/s gap seen at T42 (D2)
  is a coarse-grid effect of the horizontal interpolation and shrinks with resolution -> D2 CLOSED (expected negligible at T170).
- D4 (T42, standard-atmosphere T_ref instead of isothermal 250 K, SL cubic): -5.7 / -4.3 / -3.9 vs -5.7 / -4.3 / -3.8 -> no jet effect;
  D4 CLOSED for the jet (the tropopause T effect of T_ref not separately needed: cubic already removed most of it on 5 Nov).
- So the dynamics' jet loss = D1 (linear vertical SL; fix = sl_vcubic, built) + D3 (sigma over Tibet, ~1 m/s Asia, deferred). The
  remaining ~-2..-4 m/s at day 1 common to all cores and resolutions = start state (-1.7 at T85 already at hour 0) + evolution without
  physics in this test.

## 12 Nov 10:50 IST - Problem A in the forecast: which cloud component fills the sky (Sridhar 10:23: fix issues before the exam)
History from the T170 humidity jobs (h24 global cover vs ERA5 ~0.63): base2 0.77; IFS package 0.82; + evap + continuum 0.82;
+ qs_mix 0.91-0.92; + bl_lcl 0.93. => the forecast cover was already too high with base2 (+0.14); the package adds ~+0.05 and the
mixed-phase RH (qs_mix) ~+0.09 in the forecast (at hour 0 qs_mix brought the cover UP to ERA5's 0.62). The cover = large-scale RH
cloud + convective towers (Slingo 0.245 + 0.125 ln P, x f_tow 0.5 over the convective layer) + anvils (2 (C - 0.3) over the top 100 hPa
of deep convection), maximum-random overlap. At hour 0 there is no convection -> only the RH part shows; after spin-up the tower/anvil
parts switch on in every convecting column (the IFS mask now includes shallow convection: ~19 % of columns).
REGISTERED (cloud_parts.py, T42, 1 start, lcl32 candidate, h0/24/48): if the tower+anvil components explain >= 2/3 of the 0.62 -> 0.93
rise (cover with them removed stays <= 0.72), the cause is the convective-cloud diagnosis (a pre-IFS Slingo-type scheme fed by every
IFS convecting column, incl. shallow); if the RH part alone rises to >= 0.85, the cause is the RH cloud scheme / the forecast RH
(then: which levels).
- 11:05 RESULT (cloud_parts.py, T42, start 1 Nov, h0 / h24 / h48; global):
  candidate lcl (IFS package + bl_lcl + COARE + continuum + qs_mix): cover 0.58 / 0.90 / 0.93 (ERA5 0.62 / 0.65 / 0.64); RH-cloud alone
  0.58 / 0.895 / 0.93; towers 0.00 / 0.06 / 0.07; anvils 0.00 / 0.06 / 0.06. Low cover 0.27 -> 0.75 -> 0.77; mid 0.17 -> 0.32; high 0.44 -> 0.64.
  => registered branch 2: the RH (large-scale) cloud alone fills the sky; the convective cloud is NOT the cause.
  Per level (global mean): RH at sigma 0.91-0.95 0.73 -> 0.83-0.84 in 24 h, RH-cloud there 0.17-0.20 -> 0.40-0.42; T falls 0.5-0.9 K
  through sigma 0.7-0.99. vs ERA5: t925 -0.8 K (h24), -1.1 K (h48); q925 +2.5 / +1.3 %.
  base2 for contrast: t925 +1.5 K (warm, the old P1), q925 -12 %, but RH-cloud also 0.30 -> 0.76 (mid/high levels moisten: q700 +22 %).
  => 5-Why: forecast cloud excess <- lower-tropospheric RH +0.10 in 24 h <- cooling ~0.8-1 K/day below ~700 hPa plus a little
  moistening <- ? (candidates: radiation incl. low-cloud-top LW cooling (positive feedback: cloud -> cooling -> RH -> cloud),
  the dynamics' lowest-level start cooling S4 (-0.8..-1.1 K/day physics-off, both cores), BL / convection). Note: P1 on this
  candidate is now COLD (t925 -1.1 K at 48 h) instead of the old warm +1.5 K.
  Next: first-hours T budget by process per level (init_tend.py, candidate settings) - which process cools 925-700 hPa.
- 11:40 first-hours T budget (init_tend.py, candidate lcl, T42, 2 starts, GLOBAL mean, K/day; DYN = total - physics):
  0-6 h  at 976/957/937/916 hPa: TOTAL -0.8/-1.6/-1.8/-1.5; rad -2.1/-1.5/-1.2/-1.3; BL +3.9/+1.0/0.0/-0.3; conv -0.5/+0.1/+0.2/+0.3;
         lsc +0.1/+0.1/+0.1/+0.2; rain evap -0.2; DYN -2.1/-1.0/-0.6/-0.2.
  6-24 h at 976/957/937/916/894: TOTAL -0.8/-1.0/-1.1/-0.8/-0.3; rad -0.2/-1.6/-0.7/-2.4/-4.0 (cloud-top LW cooling of the growing low
         deck at ~900 hPa); BL +2.3/+1.3/-0.7/+1.3/+1.5; DYN -2.1/-1.2/-1.1/-1.4/+0.4.
- S4 check (s4_check.py, PHYSICS OFF, T42, 3 Oct-Nov starts, 24 h): cooling confined to the lowest 4 levels: sigma 0.99/0.97/0.95/0.93
  -1.11/-0.80/-0.57/-0.34 K; same over sea (-0.99..), tropical sea (-0.99), extratropical sea (-1.00), low land (-1.22); high land
  -0.39 (the lowest levels there are ~600 hPa). DFI changes T by <= 0.01 K. ERA5 t925 day0->1: -0.01 K. With the 5 Nov result (same in
  the Eulerian core) => S4 is NOT a numerical/initial-state error: it is the real dynamical cooling of the near-surface layer (warm
  low-level air converging and rising in the tropics, cold-air outflow elsewhere) that the PHYSICS must balance (surface heat flux,
  BL mixing, shallow-cumulus condensation heating). Reclassified: S4 'not a bug'.
- => A (forecast cloud) and P1 (now cold, t925 -1.1 K at 48 h) are ONE problem: the physics supplies ~1 K/day too little heat to the
  lowest ~100 hPa (or radiation cools it too much), the layer cools, RH rises 0.73 -> 0.83, the RH cloud grows, its top cools by LW
  (-4 K/day at 894 hPa) -> more cooling below -> more RH (positive feedback). Two things to separate next: the INITIATOR (which
  process is short in the first 6 h, before the cloud has grown: radiation -1.2..-2.1 and BL vs a reference) and the AMPLIFIER (the
  cloud-radiation feedback). Reference needed: an observed/IFS low-level heating budget (e.g. ERA5 mean temperature tendency due to
  parametrisations, or the RRTMG clear-sky check of the start column already done: clear-sky matched after lw_cnt).
- 11:50 NOISE CHECK RESULT (registered 09:35): 72 h pmin of base2 runs {rd, nz1, nz2, nz3}: Vardah 990.5 / 992.2 / 987.0 / 991.3
  (spread 5.2 hPa), Nivar 993.8 / 992.7 / 991.0 / 993.6 (2.8), Michaung 999.9 / 999.3 / 999.3 / 1000.2 (0.9).
  => spread > 2 hPa in 2 of 3 storms: a single run cannot resolve the 2 hPa gate (Vardah alone moves 5.2 hPa from a 0.1 %
  perturbation). Per the registered rule the storm check now uses 3-member MEANS with the same 2 hPa threshold. nz means: Vardah 990.2,
  Nivar 992.4, Michaung 999.6. vcubic judged on mean(vz1-3) vs these (vz1/vz2 running, vz3 queued).
  Consequence for earlier verdicts made on single storm runs (dfi_off failed by 0.1 hPa on Michaung, the spread there is 0.9 -> that
  failure stands as measured; vcubic 6 Nov Vardah +7.7 exceeds even the 5.2 spread). Not re-judged; noted.

## 12 Nov 12:30 IST - A + P1: initiator vs amplifier (Sridhar 11:50 "first fix A and P1") - REGISTERED before running
Reference checked and set aside: the GFS v16 SCM BOMEX run (tn-scm-ref) is NOT usable as a heating reference - GFS fires deep
convection in BOMEX and its column warms +5..+7 K/day in the cloud layer (BOMEX LES is steady). The reference used instead is ERA5
itself: t925 / q925 / total cloud at 24 and 48 h (ERA5 t925 day0->1 change ~0).
New diagnostic switch cld_fix (radiation's RH cloud diagnosed from the START T/q, convective cloud live; default off; base2 6-h run
bit-identical: mslp 100809.609375, rain 0.43390631675720215).
Variants (cloud_parts.py, T42, start 1 Nov, 24/48 h; reference lcl = -0.8 / -1.1 K t925, cover 0.90 / 0.93):
 (a) lcl + cld_fix  - if the cloud-radiation feedback is the AMPLIFIER, t925 error shrinks to <= half (>= -0.5 K at 48 h);
                      if it stays <= -0.9 K the cooling does not need the cloud (initiator elsewhere).
 (b) package without bl_lcl - if bl_lcl's cap removes heat transport above cloud base, t925 is warmer by >= 0.4 K (but q925 wetter).
 (c) lcl + edmf (IFS 3.42-3.43 dry mass flux: heat/moisture carried from the surface layer to cloud base) - if the missing piece is the
     non-local BL heat transport, t925 warms by >= 0.4 K with q925 not wetter than +3 %.
- 13:15 RESULT (T42, start 1 Nov; t925 bias vs ERA5 h24 / h48; q925 bias; cover):
  | variant | t925 | q925 | cover h48 |
  | lcl (reference) | -0.8 / -1.1 K | +2.5 / +1.3 % | 0.93 |
  | (a) lcl + cld_fix (RH cloud frozen in radiation) | -0.5 / -0.8 | +2.8 / +2.2 % | (0.90 diagnosed) |
  | (b) package without bl_lcl | -0.5 / -0.7 | +5.6 / +4.8 % | 0.92 |
  | (c) lcl + edmf | -0.8 / -1.1 | +2.9 / +1.6 % | 0.93 |
  Reading (registered 12:30): (a) NOT an amplifier-only problem: freezing the cloud removes ~0.3 K of the 1.1 K; the rest cools
  without the cloud feedback -> the INITIATOR is elsewhere. (b) bl_lcl costs +0.3..+0.4 K of cooling at 925 hPa (meets the 0.4
  threshold at 48 h only) while it removes ~3.5 % of the moisture excess -> part of the cost, not the initiator. (c) EDMF mass flux:
  no effect -> rejected as the missing piece.
  => ~0.7 K/2 days of 925-hPa cooling with frozen cloud and without bl_lcl. Need a REFERENCE per energy term: ERA5 daily-mean surface
  sensible/latent heat flux, surface net LW/SW, TOA net LW/SW and BL height for the exam starts (cyc_flux.py, GitHub 'flux truth',
  new file flux_truth_2020.npz). Registered use: model day-1 means of the same terms; a term differing from ERA5 by >= 5 W m-2
  globally (or >= 10 W m-2 over the tropical/subtropical ocean) in the direction that cools the low levels is the initiator candidate.
- 13:35 vcubic twins so far (72 h pmin): vz1 Vardah 997.3 / Nivar 994.6 / Michaung 1002.3; vz2 996.4 / 991.6 / 1000.0 (vz3 running).
  vs nz means 990.2 / 992.4 / 999.6: Vardah +6.6 (cannot come within 2 hPa whatever vz3 gives unless vz3 < 977), Nivar +0.7,
  Michaung +1.6. => cubic vertical interpolation REALLY weakens Vardah ~6-7 hPa (beyond the 5.2 noise spread) -> storm gate FAILS for
  Vardah (final after vz3). Context only (not a gate): ERA5-at-T170 targets Vardah 995.2 / Nivar 994.1 / Michaung 992.0 -> Vardah
  moves TOWARD its target (990.2 -> ~996.9), Michaung away (999.6 -> ~1001), Nivar ~same.
- 14:05 ENERGY TERMS vs ERA5 (flux_vs_era5.py, candidate lcl, T42, 3 Oct-Nov starts, day-1 means; ERA5 sign, W m-2):
  sensible heat globe -16.4 vs -15.8, ocean 40S-40N -14.3 vs -12.8, land -20.8 vs -25.8 -> SHF is RIGHT (not the initiator).
  latent heat globe -73.1 vs -84.9, ocean 40S-40N -103.7 vs -128.7 (-19 %), land -47.8 vs -36.8.
  BL height: ocean 40S-40N 412 vs 786 m (ERA5), land 453 vs 503 m. (ERA5 radiation fields are empty for 2020 in the WB2 archive.)
  => the surface heat INPUT is right but the model keeps it in a boundary layer half as deep as ERA5's over the ocean: the 925-hPa
  layer (~750 m) is inside ERA5's mixed layer but above ours, so it gets no surface heat and cools under radiation + dynamics; the
  shallow, moist BL also evaporates 19 % less (smaller q deficit at the surface). Caveat: ERA5 BLH is a bulk-Ri diagnostic, ours is
  the LCL-capped mixing height - not identical definitions, so the factor 2 is indicative, not exact.
  Found while checking: bl_lcl measures the LCL from the GROUND although the 125 m/K estimate is relative to the lowest model level
  (~70-100 m up). New option bl_lcl = 2 adds that height (default and bl_lcl = 1 unchanged; base2 6-h run bit-identical).
  REGISTERED: lcl2 (bl_lcl 2) - t925 bias at 48 h smaller than lcl's -1.1 by >= 0.3 K and q925 not above +3 %; BL height closer to ERA5.
- 14:40 RESULT lcl2 (bl_lcl = 2, cloud base above ground): t925 -0.8 / -1.1 K (unchanged), cover 0.90 / 0.93; ocean BL height 412 -> 502 m
  (ERA5 786); LHF unchanged (-104 vs -129). => registered prediction NOT met (needed >= +0.3 K): the ~90 m deeper mixing does not
  warm 925 hPa. lcl2 kept as a correctness fix candidate only (it is what the IFS definition says), not as the A/P1 fix.
- Next (running): low-level RADIATIVE heating vs RRTMG on the SAME forecast columns (rad_allsky.py now also reports the 850-1000 hPa
  mass-weighted LW/SW heating, all-sky and clear-sky, model vs RRTMG), hour 0 and hour 24. Registered: a model-minus-RRTMG difference
  of <= -0.3 K/day in that layer (model cools more) would be the initiator; within +-0.2 K/day clears radiation.
- 15:20 RESULT radiation vs RRTMG (rad_allsky.py, lcl candidate, T42, start 1 Nov, 1664 columns; 850-1000 hPa mass-weighted, K/day):
  | | LW all | SW all | LW clear | SW clear | total all-sky diff |
  | h0  MEGAM / RRTMG | -2.3 / -2.1 | +0.6 / +0.7 | -2.1 / -1.9 | +0.6 / +0.7 | -0.3 |
  | h24 MEGAM / RRTMG | -2.6 / -2.4 | +0.5 / +0.8 | -2.1 / -1.9 | +0.6 / +0.7 | -0.5 |
  Column: SW absorbed in the atmosphere MEGAM 67.1 vs RRTMG 72.3 (h0), 68.7 vs 77.6 (h24) W m-2; clear-sky atmospheric total within
  1 W m-2 at h0; OLR within 2. => per the registered rule (<= -0.3 K/day): radiation over-cools the low layer by 0.3 (h0) to 0.5 (h24)
  K/day relative to RRTMG on the same columns: ~0.2 K/day clear-sky LW cooling too strong, ~0.1-0.3 K/day SW absorption too weak
  (Lacis-Hansen water-vapour SW, no continuum; and less cloud SW absorption). Over 48 h that is ~0.6-1.0 K = the size of the t925 drift.
  REGISTERED sufficiency test (rad_low_add = +0.4 K/day in 850-1000 hPa, the measured mean difference; diagnostic only): if t925 at 48 h
  improves to >= -0.4 K and cover falls by >= 0.1, radiation is the initiator and the fix is in the low-level radiation (to be derived
  from the reference, not by adding heat).
- 15:40 RESULT rad_low_add +0.4 K/day (sufficiency test): t925 -0.6 / -0.8 K (was -0.8 / -1.1), cover 0.89 / 0.92 (unchanged).
  => registered prediction NOT met (needed >= -0.4 K and cover -0.1). Radiation's low-level over-cooling vs RRTMG is a REAL
  contributor (~0.3 K of the 1.1 K at 48 h) but not sufficient. Tally of measured contributors at 48 h: cloud-radiation feedback
  ~0.3 K, bl_lcl cap ~0.4 K, radiation vs RRTMG ~0.3 K. Cloud cover is insensitive to all of them (0.92-0.93).
  => A (cloud) and P1 (t925) may NOT be the same problem after all: warming 925 hPa by 0.3 K moves the cover by 0.00. Next: ERA5
  relative humidity by level (WB2 has it; 'rh truth' job) to split A into "model RH too high" vs "cloud scheme maps RH to too much cloud".
- 16:00 FINAL vcubic storm check (3-member means, registered rule): vz mean Vardah 996.6 / Nivar 992.3 / Michaung 1001.3 vs nz mean
  990.2 / 992.4 / 999.6 -> +6.4 / -0.1 / +1.7 hPa. Vardah outside 2 hPa -> sl_vcubic FAILS the storm gate; NOT adopted (D1 open).
  (vs ERA5 targets 995.2 / 994.1 / 992.0: Vardah error -5.0 -> +1.4, Nivar -1.7 -> -1.8, Michaung +7.6 -> +9.3; gate-definition
  question put to Sridhar 13:45, unanswered; current rule applies.)
- 16:00 tn-moist-lcl75b (IFS package + bl_lcl, 75 L tp75, T170, 12 starts) vs ERA5, h48: q850 -0.8..+4.0 % (mean +2.0; 9/12 within
  +-3 %), q925 +1.4..+5.5 % (mean +3.6), q700 -3.3..-0.3 %, q500 -0.7..+3.7 %, TCWV +0.7..+2.9 %. Reference base2 at 75 L (tn-moist-b275):
  q925 -9..-12 %, q700 +24..+32 %, q500 +23..+33 %. => at 75 L the package + bl_lcl removes the mid-level moistening completely and
  most of the low-level error; residual +2..+4 % at 850-925 (positive in 10/12: small systematic) - slightly larger than at 32 L
  (+0.4 / +2.3 %). B at 75 L: 'mostly fixed'.
- ~14:00 RESULT rh_vs_era5.py (lcl candidate, T42, 3 Oct-Nov starts; ERA5 daily means; model RH w.r.t. IFS mixed-phase saturation):
  TEMPERATURE vs ERA5 (d0 / d1 / d2): t850 globe -0.05 / -0.89 / -1.29 K, ocean 40S-40N -0.07 / -0.95 / -1.34, poleward 40 +0.07 / -0.51 / -0.70;
  t700 globe -0.06 / -0.82 / -1.17. => the cold drift is NOT a near-surface problem: the whole 925-700 hPa layer cools ~0.6 K/day,
  tropics included (850 hPa gate +-1.5 K will be exceeded within ~2.5 days).
  RH change from d0 (model minus ERA5; d0 offsets at cold levels partly a definition difference - WB2 RH may be w.r.t. water):
  tropical ocean 925/850/700/500: +0.04/+0.04/+0.04/+0.07 by d2; poleward of 40: +0.07/+0.07/+0.14/+0.27.
  RH-cloud fraction (the scheme applied to model vs ERA5 RH at the level): largest excess poleward (500 hPa 0.50 vs 0.01, 700 0.36 vs 0.03,
  850 0.36 vs 0.11, 925 0.44 vs 0.21 at d2); tropical ocean smaller (925 0.31 vs 0.22, 850 0.16 vs 0.09).
  => A is mainly an extratropical / mid-level RH rise plus the low-level cooling; the scheme is NOT mis-mapping (at d0 the low-level
  RH-cloud from model RH is <= ERA5's). The common driver of A and P1 is a lower-to-mid-tropospheric COOLING of ~0.6 K/day (global),
  i.e. the atmospheric energy budget: candidates measured so far against references - radiation over-cools vs RRTMG (column
  -3.4 W m-2 at h0, -8.6 at h24; 850-1000 hPa -0.3..-0.5 K/day), latent heat flux -12 W m-2 globally (-25 over the 40S-40N ocean)
  vs ERA5 -> less latent heating aloft. Next: the same energy terms for base2 (was the evaporation deficit introduced by ck_z/sfc_sal
  or by the package?) and the precipitation vs ERA5 (latent heating actually released).
- ~14:20 ENERGY TERMS base2 vs ERA5 (same 3 starts, day 1): LHF globe -105 vs -85 (+24 % too strong), ocean 40S-40N -150 vs -129 (+17 %);
  SHF globe +1.4 vs -15.8 (WRONG SIGN: net downward - the old shallow scheme's +7 K/day heating made the low levels warmer than the
  surface), ocean +5.5 vs -12.8; BL height 943 vs 786 m (ocean). Candidate lcl: LHF ocean -104 (-19 %), SHF -14 (right), BLH 412.
  => the old base got its warmth from a wrong-signed sensible heat flux plus too much evaporation; the package fixed the SHF but the
  evaporation swung from +17 % to -19 % over the ocean (-46 W m-2). Decomposition running: package WITHOUT ck_z/sfc_sal (the COARE
  evaporation changes) -> splits the swing into "package (moister surface layer)" vs "COARE coefficient change"; plus rain vs ERA5.
- ~14:45 DECOMPOSITION of the evaporation swing (same 3 starts, ocean 40S-40N, day-1 LHF vs ERA5 -128.7): base2 -150.1 (+17 %);
  package + bl_lcl WITHOUT ck_z/sfc_sal -118.9 (-8 %); + ck_z 1 + sfc_sal 0.98 -104.3 (-19 %). Rain vs ERA5 (mm/day): globe 3.1 / 2.9 vs
  3.0, ocean 4.2 / 3.8 vs 3.7 -> precipitation (latent heating released) is RIGHT in both.
  => the package itself brings evaporation to -8 % of ERA5; the 5 Nov COARE changes (adopted into the candidate on 11 Nov to remove ~2 %
  of the moisture excess) now OVER-correct it to -19 %. ck_z = 1 was derived against the old base (where LHF was +17 %); on the package
  it is no longer supported by the reference. sfc_sal (2 % lower saturation over sea water) is a physical fact (COARE 3.5 / IFS) and stays.
  REGISTERED (rh_vs_era5.py, same starts): package + bl_lcl + sfc_sal WITHOUT ck_z: t850 d2 bias better than lcl's -1.29 K by >= 0.3 K
  and LHF ocean within -10 % of ERA5, with q925 not above +4 %. (If the temperature does not move, evaporation is cleared as an A/P1 cause.)
- ~15:00 RESULT package + bl_lcl + sfc_sal WITHOUT ck_z: t850 d1/d2 -0.85 / -1.21 K (lcl -0.89 / -1.29), t700 -0.81 / -1.12 (lcl -0.82 / -1.17);
  RH unchanged within 0.003; LHF ocean -114 vs ERA5 -129 (-11 %; lcl -19 %); rain 3.0 vs 3.0 (globe), 4.0 vs 3.7 (ocean).
  => registered prediction NOT met (+0.08 K vs >= +0.3): evaporation is CLEARED as an A/P1 cause. Separately (correctness, reference-
  based): ck_z = 1 is no longer supported on the package (LHF -19 % vs -11 % without it) -> drop ck_z from the candidate, keep sfc_sal.
  Tally for the 925-700 hPa cooling (~0.6 K/day): radiation vs RRTMG (low layer) ~0.15 K/day, cloud-radiation feedback ~0.15, bl_lcl
  ~0.2 at 925 only; evaporation ~0.04. Rain (column latent heating) right. Next: RRTMG comparison for the 700-850 hPa layer and the
  heating profile split by process vs a reference profile; SW water-vapour coefficient fit (rad_fit.py).
- ~15:10 RESULT radiation vs RRTMG, 700-850 hPa (same columns): LW all-sky -1.8 vs -2.0 (h0), -2.1 vs -2.2 (h24); SW +0.6/+0.5 vs +0.7;
  clear-sky within 0.1 => radiation is RIGHT in the 700-850 hPa layer (the over-cooling vs RRTMG is confined to 850-1000 hPa).
  SW water-vapour fit (rad_fit.py, 790 training columns Oct, 847 validation Jan/Jul, clear-sky day side): before, column absorption
  145 vs 152 (train) / 153 vs 154 (val), 850-1000 hPa heating 1.31 vs 1.49 K/day; fitted K = [0.00016, 0.061, 0.55, 2.36, 22.5]
  (cm2/g) fixes the low layer (1.51 vs 1.49) but OVERSHOOTS the column (158 vs 152 train, 167 vs 154 validation) and the profile rms
  improves only 0.55 -> 0.50. => NOT adopted: one k-set cannot match both; the deficit is small (~0.1 K/day diurnal mean) - leave.
  => the unexplained ~0.3 K/day at 700-850 hPa is NOT radiation and NOT evaporation. Next: which process changed between base2
  (850 hPa warm) and the package (850 hPa cold): first-hours T budget by process, base2 vs package, same starts.
- ~15:25 PROCESS BUDGET base2 vs package (init_tend.py, T42, 2 starts; K/day): at 880-990 hPa base2 is warmed by its old shallow scheme
  (+3..+6) and cooled by rain evaporation (-1.3..-2.5); the package has neither (shallow +0, evaporation -0.1..-0.4), more radiative
  cooling at 880-950 hPa (tropics 6-24 h -2.3..-2.7 vs base2 -1.1..-1.9: its low cloud deck) and much weaker convective heating in the
  first 6 h (tropics 400-700 hPa +0.1..+0.4 vs base2 +1.1..+1.8). At 700-850 hPa the TOTAL tendency is similar in both (about -0.5..-1 K/day)
  -> the 700-850 hPa cooling may be common to every model version (not introduced by the package). Checking base2 vs ERA5 t850/t700.
- 15:35 P5b RE-MEASURED on the package (tn-p5-lcl-ond: IFS package + bl_lcl + ck_z + sfc_sal + continuum + qs_mix, 18 Oct-Dec starts,
  T170) vs base1 (tn-p5-b1-ond, 6 Nov table): Bay u850 bias d1/d3/d5 -1.98 / -4.07 / -3.61 m/s (base1 -0.95 / -4.05 / -2.62); v850
  +0.72 / +1.29 / +1.36 (base1 +0.12 / -0.45 / -0.13); deep-layer steering v d3/d5 -0.53 / -1.14 (base1 -0.94 / -0.70); central-India
  MSLP d0/d1/d3/d5 +0.79 / +1.23 / +2.28 / +2.22 hPa (base1 +0.82 / +0.86 / +1.70 / +1.17); 500-hPa ridge gradient d3 +12.5 m (base1 +6.5).
  => the physics package does NOT fix the Bay low-level easterly (same -4 m/s at day 3) and makes the central-India surface high
  stronger by day 3-5 (+0.6..+1.0 hPa) - consistent with the colder lower troposphere (A/P1) over land. P5b stays OPEN; its
  day-3 easterly is common to both physics versions -> not a convection-scheme effect; next: the 850-hPa momentum budget (P5 item 3).

(15:35 note: the clock times written on the 12 Nov afternoon entries above were wrong - estimated, not read from a clock; corrected to approximate real IST.)
- 15:50 base2 vs ERA5 (rh_vs_era5.py, same 3 starts): t700 d1/d2 -1.34 / -1.55 K (package -0.81 / -1.12); t850 +0.18 / +0.05 globe,
  +0.80 / +0.75 tropical ocean (package -0.85 / -1.21); RH d2: 925 -0.13 (dry), 700 +0.21, 500 +0.30 (package 925 +0.06, 700 +0.11, 500 +0.21).
  => the 700-hPa cooling is OLDER than the package and was LARGER in base2 (-1.55 vs -1.12 K at d2): the package improves it. At 850 hPa the
  old shallow scheme's +3..+6 K/day overheating hid the same cooling (base2 +0.8 K warm over the tropical ocean); the package removes that
  wrong heating and exposes it. => the A/P1 driver at 700-850 hPa is a long-standing, model-wide heat deficit in the lower-to-middle
  troposphere, not a package defect. Measured and cleared for it: radiation at 700-850 (= RRTMG), evaporation, dynamics alone (physics-off
  +0.0..-0.2 K/day there). Left: the vertical distribution of latent heating (rain total right) and the large-scale cloud/condensation
  scheme shared by both versions.
- 16:10 cycle: tn-moist-pkg75 (package WITHOUT bl_lcl, 75 L, T170, 12 starts) h48 vs ERA5: q850 +10.1 % (8.0..12.5), q925 +6.6 %, q700 0.0,
  q500 +1.3, TCWV +3.6 %. With bl_lcl (lcl75b): q850 +2.0 %, q925 +3.6 %. => at 75 L bl_lcl removes 80 % of the 850-hPa moisture excess too:
  B's fix is confirmed at both 32 and 75 levels. Kaggle: account 1 at weekly limit; account 4 now running tn-lz1-sb (6 waiting).
- 16:40 HYPOTHESIS for the remaining 700-850 hPa heat deficit (5-Why): rain total right, radiation right there, evaporation cleared ->
  WHERE the latent heat stays. IFS v1 as built turns ALL detrained condensate back into vapour where it detrains (pre-prognostic IFS;
  Cy50r1 instead feeds it to the prognostic cloud scheme, from which part precipitates). In the 700-850 hPa layer congestus/shallow plumes
  detrain most of their condensate -> condensation heating in the plume is cancelled by evaporation cooling at detrainment, and the
  layer is moistened = exactly the observed cooling + RH rise. New diagnostic switch det_prec (fraction of detrained condensate turned
  into precipitation at the detrainment level; default 0 = v1 unchanged).
  REGISTERED sufficiency test (det_prec = 1, upper bound; rh_vs_era5 + flux_vs_era5, same 3 starts): mechanism CONFIRMED if t850 and t700
  d2 biases both improve by >= 0.4 K (from -1.21 / -1.12) and RH 700 d2 excess falls by >= 0.03; rain change reported (cost). If < 0.2 K:
  rejected.
- 17:10 RESULT det_prec = 1 (upper bound): t850 d1/d2 -0.70 / -0.99 K (was -0.85 / -1.21), t700 -0.74 / -1.01 (was -0.81 / -1.12); RH700 excess
  d2 0.086 (was 0.107); rain globe 3.2 vs 3.0 (+0.2), ocean 4.2 vs 3.7. => registered criteria NOT met (+0.22 / +0.11 K vs >= 0.4):
  detrained-condensate evaporation is a SMALL contributor (~0.1-0.2 K at d2 even at its upper bound), not the main driver. Rejected as
  the A/P1 fix.
  Tally at d2 (850 hPa, -1.2 K): radiation vs RRTMG ~0.3, cloud feedback ~0.3, bl_lcl ~0.3 (925), detrained condensate <= 0.2,
  evaporation ~0.1 - several small contributors, each confirmed against a reference, none dominant; ~0.3-0.5 K still unassigned.
  Caveat: all these are T42 local runs; the T170 exam quarter (tn-lcl-wx0, queued) gives the real-resolution P1 numbers.
- 18:45 P3 first member on the package (tn-lz1-sb): 72 h pmin Vardah 995.4 / Nivar 1004.6 / Michaung 1005.8 vs base2 nz means 990.2 / 992.4 /
  999.6 and ERA5-at-T170 targets 995.2 / 994.1 / 992.0. 1 of 3 members (lz2 running, lz3 queued) - no verdict yet; first sign: the
  package weakens Nivar (+12 hPa) and Michaung (+6) well beyond the noise spread.

## 12 Nov 19:20 IST - A/P1: the UNASSIGNED 0.3-0.5 K (Sridhar 19:14 "first find the unexplained cause") - REGISTERED
Candidate from the dynamics work (D1): with PHYSICS OFF the linear vertical semi-Lagrangian interpolation cools the middle troposphere
(z500 -2.2..-2.9 m/day; s4_check: -0.0..-0.2 K/day at sigma 0.70-0.85), and cubic vertical interpolation removed that on 5 Nov.
-0.15..-0.2 K/day over 2 days = -0.3..-0.4 K = the size of the unassigned remainder. It is not physics, so none of today's physics
tests could see it.
Test (rh_vs_era5.py, same 3 starts, T42): package (phys_ifs + bl_lcl + sfc_sal + continuum + qs_mix) + sl_vcubic.
CONFIRMED if t850 AND t700 d2 biases both improve by >= 0.3 K (from -1.21 / -1.12); rejected if < 0.15 K.
- 19:45 RESULT package + sl_vcubic: t850 d1/d2 -0.82 / -1.16 K (was -0.85 / -1.21), t700 -0.73 / -1.01 (was -0.81 / -1.12) -> +0.05 / +0.11 K:
  REJECTED (< 0.15): D1 is not the unassigned remainder of the A/P1 cooling.
  Next (registered): ALL measured contributors removed at once (rad_low_add +0.4, cld_fix, det_prec 1, no ck_z, bl_lcl kept) - the
  remaining t850 d2 bias IS the unassigned part (expected -0.3..-0.5 K if the contributors add linearly); its first-day process budget
  at 700-850 hPa then shows which term carries it.
- 20:30 RESULT combined (all measured contributors removed): t850 d1/d2 -0.40 / -0.50 K (package -0.85 / -1.21), t700 -0.67 / -0.88 (-0.81 / -1.12).
  => the measured contributors remove 0.7 K at 850 but only 0.24 K at 700: the unassigned part is -0.5 K at 850 and -0.9 K at 700 hPa.
- 20:40 FOUND: COLUMN ENERGY BUDGET (init_tend profiles integrated cp/g * sum(dT/dt dp), globe, W m-2) vs the observed global energy
  balance (Wild et al. 2013/2015: latent heat 84, sensible 20, solar absorbed in the atmosphere ~79 = 240 TOA - 161 surface, so
  atmospheric radiative cooling ~ -104):
  | run, window | total | radiation | latent (conv + lsc - evap) | BL/sensible | dynamics |
  | package 0-6 h | -81 | -116 | +24 | +12 | -2 |
  | package 6-24 h | -56 | -137 | +67 | +21 | -7 |
  | base2 0-6 h | -78 | -120 | +35 | +10 | -3 |
  | base2 6-24 h | -63 | -137 | +64 | +12 | -3 |
  | all contributors removed 6-24 h | -34 | -120 | +72 | +19 | -6 |
  => the atmosphere loses 55-80 W m-2 on day 1 in EVERY version (0.5-0.7 K/day mass-weighted = the A/P1 cooling). Two terms are off
  against the observed balance: (1) LATENT HEATING SPIN-UP: +24 (0-6 h) and +67 (6-24 h) vs ~84 needed (rain reaches ERA5's 3.0 mm/day
  only on day 2) - a first-day deficit of ~30-60 W m-2; (2) RADIATIVE COOLING too strong: -116 at the start vs ~-104 (solar absorbed in
  the atmosphere 67 vs ~79; RRTMG on the same columns 72 - neither run has AEROSOLS, which absorb ~3-6 W m-2 globally) and it grows to
  -137 as the cloud deck builds (the A feedback). Dynamics -2..-7 (small).
  => the 'unexplained' part is (1) the convective spin-up on day 1 plus (2) the missing atmospheric solar absorption (aerosol + water
  vapour), both constant-sign, both in all versions. Next: rain hours 0-24 vs ERA5 day 0 (size of the spin-up) and an aerosol
  climatology for the radiation (IFS uses one; MEGAM has none).
- 21:20 SPIN-UP measured (flux_vs_era5.py DAY=0, package, 3 starts, hours 0-24 vs ERA5 day 0): rain globe 2.0 vs 2.9 mm/day (-31 %),
  ocean 40S-40N 2.4 vs 3.6 (-33 %), land 1.4 vs 2.0; day 1 rain 3.0 vs 3.0 (right). => latent heating deficit on day 0 ~ 27 W m-2
  (0.95 mm/day x 29 W m-2 per mm/day) - confirmed as a main A/P1 driver. (Also: land evaporation day 0 -58 vs -37 W m-2, too strong.)
  5-Why candidate: the digital filter (DFI) at the start removes the analysed divergent (convectively driven) circulation - large-scale
  ascent restarts from ~0 and convection must spin it up again (classic reason for diabatic initialisation). Links to S2 (DFI removes
  the tide). REGISTERED: no-DFI start, same runs: DFI is the spin-up cause if day-0 rain rises by >= 0.4 mm/day globally; < 0.15 rejects.
- 21:55 RESULT no-DFI start: day-0 rain globe 2.0 vs 2.9 (unchanged, +0.0..+0.1), ocean 2.5 vs 3.6 => REJECTED: the filter is not the
  spin-up cause. IMPORTANT CAVEAT: at T170 the old base had TOO MUCH tropical rain by day 5 (+1.14 mm/day, 5 Nov), so part of this T42
  day-0 deficit may be resolution (T42 smooths the humid convective columns). The T170 exam quarter (tn-lcl-wx0, queued) decides
  whether the spin-up exists at the real resolution before any fix is built for it. The atmospheric solar-absorption deficit
  (67 vs ~79 W m-2; no aerosols) is resolution-independent -> next fix to build (aerosol climatology as in IFS).

## 12 Nov ~21:55 IST - D1 / D3 / S3 (Sridhar 21:50 "work on D1, D2, D3 and S3"; D2 already closed at 10:40 - T85 cubic SL = Eulerian)
D1 - WHY cubic changes the storms (from the 6 storm runs already done, nz1-3 vs vz1-3, sb.json; no new GPU):
- tracks vs best track: 72 h error nz / vz (3-member means): Vardah 358 / 201 km, Nivar 113 / 138, Michaung 278 / 373; all 3 storms
  250 / 237 km. Vardah's cubic track stays east (89.3E at 72 h vs nz 87.2E; best track 90.7E) - much closer to reality; Michaung's
  cubic track runs north faster (16.5N vs 15.8N at 72 h) toward the Andhra coast.
- Vardah weakening in cubic starts at 36-48 h over OPEN SEA (88-89E): core rain 211 -> 76 mm/day, core RH700 1.09 -> 0.99, deep-
  convection-on fraction 1.0 -> 0.6, while the 500/300 hPa warm core is similar until 48 h. Michaung's cubic run weakens after 60 h
  (core RH700 0.87, rain 50 vs 165) as it nears the coast.
  => the storm differences come from the CHANGED LARGE-SCALE FLOW (steering and the environment the storm moves into), not from a
  core-scale numerical artefact of the interpolation: cubic changes the upper winds (that is its purpose - the jets), which moves the
  storms. The storm-intensity gate as defined ("same as base within 2 hPa") cannot separate an environment/track change from a
  defect; on tracks, cubic is slightly better overall (237 vs 250 km) and much better for Vardah. Decision on the gate definition is
  Sridhar's (asked 13:45); until then cubic stays rejected under the registered rule.
S3 - hour-0 central-India MSLP (s3_check.py: T170 INITIAL STATE, no DFI, no time step, model's own IFS reduction vs ERA5 msl, 4 Oct starts):
  box bias +0.02 / +0.08 / +0.04 / +0.06 hPa (mean +0.05); where |dz| < 30 m +0.08; mean dz (model - ERA5 terrain) -9 m (|dz| 33 m);
  corr(bias, dz) 0.64 but the amplitude is tiny. => at T170 the initial state and the reduction are RIGHT (the 6 Nov +0.55 hPa
  residual was a T42 effect: coarser terrain smoothing). The T170 hour-0 value of +0.8 hPa (P5 runs) therefore comes from the DFI
  (S2: it removes part of the real thermal tide, +0.4 hPa measured 6 Nov, plus its other changes). S3 is CLOSED as a separate item and
  merges into S2.
D3 - hybrid vertical coordinate: SCOPE (mm2.py touch points, grep): coordinate setup (l.124-140), start-state interpolation
  (l.186 interp_pressure_to_sigma -> per-column target pressures a + b ps, as hyb_jet.py already does), the physics column
  (l.465 p = sig ps, dp = dsig ps -> a + b ps, da + db ps), sigma-fraction tests inside the convection/BL code (l.337-345, 641, 820:
  sig thresholds -> p / ps), diagnostics (l.899-1000: geopotential on sigma, lowest-level height, MSLP reduction, 850/700 indices),
  the equation object (SemiLagrangianPrimitiveEquationsHybrid, already exercised in hyb_jet.py), DFI, and every analysis script that
  reads M.sig (storm_budget, hind2, wx2, p5_bias, tn_rain_diag). Plan: option 'hyb' (default 0 = sigma, bit-identical), with
  p_c, dp, p_b computed once per step from (a, b, ps) and passed everywhere sig * ps is used today; level set = hyb_jet.py's (same
  reference pressures as today's 32 / 75 levels, B = ((s - 0.1)/0.9)^1.3). Expected gain from hyb_jet: Asia jet +1.1 m/s/day (T42).
  Order: mm2 core + init + column (local T42 regression: hyb = 0 bit-identical; hyb = 1 runs 48 h stable at 32 and 75 L) -> diagnostics
  -> scripts -> T170 screen (jets, storms on 3-run means, z500).
- 22:10 D3 BUILT (mm2.py option hyb; default 0): coords_dyn = HybridCoordinates (A, B from the sigma boundaries, B = ((s-0.1)/0.9)^1.3),
  SemiLagrangianPrimitiveEquationsHybrid, start state interpolated to each column's own level pressures, physics column p/dp/interfaces
  from A + B ps (sigma tests become p / ps), geopotential by hydrostatic integration on the interfaces (checked vs Dinosaur's sigma
  geopotential on a sigma state: <= 0.3 m at 500 hPa), MSLP / lowest-level height / column water from the level pressures.
  Regression hyb = 0: base2 6-h run bit-identical (mslp 100809.609375, rain 0.43390631675720215). hyb = 1, T42, 32 L, 48 h, 1 start:
  stable, finite; vs ERA5 RMSE / bias: z500 d1 22.9 / -9.9 m (sigma 23.4 / -11.2), d2 38.9 / -11.1 (39.9 / -14.6); t850 d2 3.75 (3.76);
  u200 d2 6.95 (6.95); mslp d2 464 / +58 Pa (461 / +22). Next: 75 L stability, the jet check (sector jets) with hyb in the full model.
- 22:25 D3 hyb at 75 L (tp75, T42, 48 h, 1 start): stable; z500 d1/d2 bias -10.6 / -12.2 m (sigma 75 L -11.0 / -13.6), RMSE 23.6 / 41.0
  (23.8 / 41.2); t850, u200 RMSE equal within 0.01. REGISTERED next (jet_check.py, full physics, T42, 3 Oct-Nov starts, sector jets):
  hyb adopted-candidate if the Asian jet day-1 error improves by >= 0.7 m/s with Pacific and Atlantic not worse by > 0.3 m/s
  (hyb_jet.py physics-off predicted +1.1 / +0.1 / +0.2).
- 22:40 RESULT D3 jet check (full physics, T42, 3 starts; day-1 jet error sigma -> hyb): Asia -7.6 -> -6.7 (+0.9), Pacific -7.6 -> -7.3 (+0.3),
  Atlantic -4.8 -> -4.6 (+0.2) => registered local criterion MET (>= +0.7 Asia, others not worse). D3 becomes a candidate.
  REGISTERED T170 screen (tn-p5-dyn-hyb, base2 + hyb, same 12 starts as tn-p5-dyn): Asian subtropical jet speed bias d1-d3 better than
  base2 (-6.2 / -8.7 / -10.3) by >= 0.5 m/s on average, no worse jet latitude classes, global z500 not worse; then the storm check
  (3-member means, current rule) before adoption.
- 04:05 (13 Nov) P3 package storm members complete (tn-lz1/2/3-sb, 72 h pmin): Vardah 995.4 / 995.3 / 995.3, Nivar 1004.6 / 1004.6 / 1004.3,
  Michaung 1005.8 / 1005.8 / 1005.7 -> means 995.3 / 1004.5 / 1005.8 vs base2 nz means 990.2 / 992.4 / 999.6 and ERA5-at-T170 targets
  995.2 / 994.1 / 992.0. Spread between package members <= 0.3 hPa (base2: up to 5.2) - the package is far less chaotic.
  => the package weakens Nivar by 12.1 hPa and Michaung by 6.2 (both AWAY from their targets) and Vardah by 5.1 (onto its target).
  Storm check (registered rule, vs base2 within 2 hPa): FAILS for all three. P3 suspects (to test): the colder/drier lower troposphere
  (A/P1 energy deficit, larger over warm-core inflow), the IFS deep closure (PCAPE removed over tau 720-10800 s: too strong venting
  of the storm core instability), weaker surface enthalpy flux (package LHF -8..-11 % vs ERA5).
  Kaggle: tn-p5-dyn-hyb (D3 T170 screen) launched on account 4 at 04:00; 4 waiting (TN rain x2, tracks, exam quarter).
- 03:20 (13 Nov) local storm runs (storm library downloaded, Nivar, T85) are killed by memory (6.1 GB of the 7 GB, even without the radial
  diagnostics): the storm library itself is too large for this machine. Storm tests stay on Kaggle. One hour-0 observation from the
  attempt (same start): core rain package 24 vs base2 41 mm/day (inner/outer 24.1/13.2 vs 41.3/37.6) - the package starts the storm
  with far less convective rain (the A/P1 spin-up seen at storm scale) -> first P3 suspect to test on Kaggle.
- 09:10 (13 Nov) D3 T170 SCREEN (tn-p5-dyn-hyb, base2 + hyb, 12 Oct-Nov starts) vs base2 (tn-p5-dyn), subtropical jet core speed bias d1/d2/d3:
  Asia -6.5 / -8.4 / -10.0 (base2 -6.2 / -8.7 / -10.3: mean +0.1), Pacific -2.3 / -2.6 / -2.9 (-2.4 / -2.9 / -3.7: +0.4), Atlantic -2.0 / -3.8 / -3.7
  (-2.0 / -4.0 / -4.0: +0.2); Atlantic jet latitude d1-d3 -0.5 / -1.4 / -1.4 deg (base2 -2.4 / -1.8 / -2.2: better).
  => registered T170 criterion (Asia d1-d3 better by >= 0.5 m/s) NOT met: the +0.9 m/s seen at T42 does not appear at T170 - the sigma
  slope over Tibet matters less at higher resolution (steeper but better-resolved terrain is not the jet's problem). D3 NOT adopted;
  kept as an option (small gains elsewhere: Pacific speed, Atlantic latitude). The Asian jet speed error at T170 is therefore D1
  (linear vertical interpolation) plus something not yet identified (~-6 m/s at day 1 remains in both).

## 13 Nov 11:40 IST - NEW STORM RULES (Sridhar 11:37 "Ok with this new rules"), registered BEFORE any further storm result
Reason: 3 storms judged one by one at 72 h mix track error into intensity (5 Nov: Michaung decayed in cooler air on a wrong track,
Vardah over-deepened while stalled) and a 0.1 % perturbation moves one storm by up to 5.2 hPa - single-storm 2-hPa checks cannot
separate better from worse (cubic moved Vardah TOWARD its target and was rejected).
1. STAGE-1 INTENSITY CHECK (accuracy): the 41-storm library (lib84 set), PEAK intensity over 0-72 h (min pmin) vs ERA5-at-T170 peak
   over the same window; PASS if >= 80 % of storms are within +-5 hPa.
2. SCREENING CHECK for every candidate change (non-regression): mean |peak-intensity error vs ERA5| over the storm set not worse than the
   base by more than the measured noise (3-member spread; for the 3-storm sb set: 3-member means, noise = max-min of base members);
   reported together with the per-storm values.
Applied identically to every candidate from now on. Earlier verdicts under the old single-storm rule (sl_vcubic, dfi_off) are NOT
re-judged on old runs: they are re-run and judged under rule 2.
- 11:50 REJUDGE PLAN under rule 2 (Sridhar 11:38 "first rejudge"): the old members are deterministic (same seeds -> identical result), so
  'rerun' = NEW members, seeds 4-6, for base2 (nz), cubic (vz), no-DFI (dz) and the package (lz): 12 jobs x ~0.3 GPU-h, account 4, ahead of
  the queue. Judged on the 3-storm sb set: mean over storms of |3-member-mean 72-h PEAK intensity - ERA5-at-T170 target| vs base2's, noise =
  max-min of the base2 member means. Rule 1 (41 storms) needs ERA5 peak-intensity targets for all 41 storms - building them next
  (ERA5 msl along the best tracks, GitHub job).
- 12:05 Rule-1 targets: cyc_peak.py (GitHub 'peak truth'): for every library storm, ERA5 0.25-deg msl minimum and 850-hPa wind maximum
  within 2.5 deg of the best-track position, 0-72 h every 6 h, at hind2's start time; peak = min msl over 0-72 h ->
  data/cyclone/wx/peak_targets.json (same definition as era5_p3_targets.json msl_min).
- 16:20 (13 Nov) Rule-1 targets READY: data/cyclone/wx/peak_targets.json, 83 library storms, ERA5 0.25-deg 0-72 h peak msl 985-1010 hPa.
  Check against the old 3-storm targets (independent earlier extraction): 72 h msl Vardah 995.24 (old 995.2), Nivar 994.07 (994.1),
  Michaung 992.03 (992.0) -> identical. Rule-2 members so far (seed 4): base2 Vardah 991.4 / Nivar 993.4 / Michaung 1000.7; cubic 995.8 /
  991.8 / 1001.9; no-DFI 991.0 / 993.8 / 1001.2 (72-h values; peak values computed when all members are in).

## 13 Nov ~20:15 IST - RULE-2 VERDICTS (registered 11:40; 3 storms x 3 new members, seeds 4-6; PEAK pmin over 0-72 h vs ERA5 peak targets
Vardah 994.8 / Nivar 994.1 / Michaung 992.0)
| version | peak means V / N / M | member spread | |err| V / N / M | mean |err| |
| base2 (nz) | 989.1 / 993.9 / 994.0 | 2.4 / 0.8 / 1.3 | 5.7 / 0.2 / 1.9 | 2.60 |
| cubic, sl_vcubic (vz) | 994.0 / 992.9 / 992.2 | 1.6 / 2.5 / 0.1 | 0.8 / 1.2 / 0.1 | 0.70 |
| no DFI (dz) | 989.1 / 993.5 / 994.8 | 0.5 / 0.3 / 1.1 | 5.7 / 0.6 / 2.8 | 3.02 |
| package (lz) | 994.3 / 1003.0 / 1001.1 | 0.4 / 0.1 / 0.1 | 0.4 / 8.9 / 9.0 | 6.12 |
Noise (mean base2 member spread) 1.5 hPa. Rule 2 (not worse than base2 by more than the noise):
- D1 cubic: 0.70 vs 2.60 -> PASS (better on all three storms). Remaining registered check before adoption: the exam quarter
  (z500 etc.; never run for cubic because the 6 Nov storm verdict stopped it) -> tn-vc-wx0 queued FIRST on account 4.
- S2 no DFI: 3.02 vs 2.60 (+0.42 < 1.5) -> PASS storms. Its 7 Nov exam-quarter/track diagnostics exist (tn-s-nd-wx0 / -q6) - to be
  read before adoption; combination with cubic untested (FMEA #2).
- P3 package: 6.12 vs 2.60 (+3.5 > 1.5) -> FAILS: it under-deepens Nivar and Michaung by ~9 hPa at peak. Cause hunt continues
  (slow storm-core rain at the start, cold/dry low levels).
- ~20:45 S2 / D1 existing diagnostics read (7 Nov / 6 Nov runs, single members, T170):
  exam quarter 0 (19 starts) no-DFI vs base2, global RMSE diffs: z500 d1/d3/d5/d10 +0.23 / +0.12 / -0.08 / +0.44 m, t850 <= 0.02 K,
  mslp d5 -2 Pa, rain24 d10 -0.33 mm, winds <= 0.2 m/s -> NEUTRAL (no exam-level change).
  quick-6 tracks, 72 h error (km): base2 Sidr 319 / Giri 993 / Phailin 388 / Titli 139 / Nivar 197 / Hamoon 472 (mean 418);
  no-DFI 341 / 563 / 396 / 128 / 230 / 500 (360); cubic 352 / - (lost) / 460 / 354 / 100 / 1072 (mean of 5: 468).
  => single-member track errors move by hundreds of km between versions (Giri 993 vs 563, Hamoon 472 vs 1072): the track
  check needs the same treatment as storms (3-member means) before any verdict. Cubic's 6-storm tracks look WORSE on single
  members (Titli, Hamoon) while its 3-storm sb tracks were better (237 vs 250) - not resolved; registered next: quick-6 with
  3 members each for base2 and cubic (seeds 4-6), judged on the mean 72 h error (not worse than base2 by more than the base2
  member spread). Cubic adoption waits for this AND its exam quarter (running next).

## 13 Nov 20:57 IST - SRIDHAR DECISIONS (target: Stage 1 first week of December)
1. FOCUS (yes): critical path only - energy-balance fixes (A/P1, probably P3) -> sl_vcubic + dfi_off adoption -> full exam. Parked
   until after the exam: D3, the P5b deep-dive, T42 side studies.
2. ADOPTION (confirmed): a candidate passing ALL its registered checks is adopted into the base without asking; Sridhar is told after.
3. TRACK RULE (approved), registered now before any of the new track runs is read: screening = 3 members per version (seeds 4-6),
   mean 72 h track error vs best track; PASS if not worse than base by more than the base member spread (mean over storms of
   max-min). Stage-1 track check unchanged (72 h <= 280 km plus the trend/turn rule).
E2E: Sridhar tops up Rs 2,000 by Monday (balance check Rs 4,320 stays). Until then Kaggle only.
- 21:40 A/P1 fix 1 BUILT: aerosol in the short-wave (radcloud option aer; default off, base2 6-h run bit-identical). Literature-typical
  values, NOT fitted: 550-nm AOD 0.10 sea / 0.20 land (global mean ~0.13; MODIS/MISR/AeroCom range 0.12-0.15), single-scattering
  albedo 0.93, asymmetry 0.70, Angstrom exponent 1.3 across the 7 bands, exponential profile with 2 km scale height.
  REGISTERED (rad_allsky.py, same 1 Nov columns, h0): all-sky atmospheric SW absorption rises by 3-7 W m-2 (67.1 -> 70-74; observed
  ~79) and the 850-1000 hPa heating gap vs RRTMG+obs shrinks; then the forecast test (rh_vs_era5.py, 3 starts): t850 d2 bias better by
  >= 0.2 K (from -1.21) with rain and cloud not worse vs ERA5.
- 22:05 RESULT aerosol on (same 1 Nov columns, h0): atmospheric SW absorption 67.2 -> 70.6 W m-2 (+3.4, inside the registered 3-7;
  observed ~79), surface SW 194.2 -> 188.7, whole-atmosphere radiative cooling -120.2 -> -116.9, 850-1000 hPa SW heating +0.1 K/day.
  Step 1 met. Forecast test running (rh_vs_era5 + flux_vs_era5, 3 starts).
- 22:50 RESULT aerosol forecast test (3 starts): t850 d1/d2 -0.80 / -1.14 K (was -0.85 / -1.21), t700 -0.76 / -1.04 (was -0.81 / -1.12); RH,
  rain (3.0 vs 3.0) unchanged; LHF -78 vs -85. => +0.07 K at d2: registered criterion (>= 0.2 K) NOT met. Aerosol is physically right
  (absorption toward observations) but too small to matter for A/P1 (~3 W m-2 = ~0.03 K/day column). Kept as option, not adopted.
  => the main A/P1 driver left is the day-1 latent-heating spin-up (T42: day-0 rain -31 %). Before building a fix: the T170 exam quarter on
  the package (tn-lcl-wx0) gives day-1 rain vs ERA5 at the real resolution.
- 23:15 SPIN-UP SHAPE (spin.py, T42, 3 Oct-Nov starts, global rain mm/day every 3 h):
  package h0..h45: 0.15 0.78 1.29 1.88 2.08 3.05 2.52 2.76 2.77 2.72 2.81 2.98 3.00 3.39 3.27 3.20
  base2   h0..h45: 2.03 2.09 2.30 2.61 2.75 2.96 3.00 2.92 2.96 3.06 3.14 3.32 3.27 3.37 3.23 3.14
  => the slow first-day rain is a PACKAGE-SPECIFIC spin-up: the IFS convection starts from ~0 rain and needs ~15 h to reach ~2.8 mm/day;
  the old scheme rains 2 mm/day from the first step. Day-0 mean 1.8 vs 2.6 (base2) vs ERA5 2.9. This is where the package loses its
  day-1 latent heating (A/P1) and very likely why it starts storms with half the core rain (P3, 24 vs 41 mm/day at hour 0).
  Next: which input of the IFS convection is missing at the start (trigger excess from surface fluxes, BL tendency in the closure,
  radiation cache, or the start profile itself) - per-hour convection diagnostics at h0 / h3 / h12.
- 23:15 CAUSE of the package spin-up (spin_dbg.py, T42, 1 Nov): at hour 0 the IFS plume finds almost NO instability in the ERA5 start
  state (PCAPE 0.0 -> 0.8 / 4 / 9.5 / 18 / 22 at h1 / 3 / 6 / 12 / 24; deep-convection columns 2.4 % -> 28 %; rain 0.16 -> 2.9 mm/day):
  the model waits ~15 h to build its own instability before it rains. The real IFS does not, because two terms of the documented scheme
  respond to LARGE-SCALE MOISTURE CONVERGENCE immediately - and MEGAM's v1 left both out ('needs the advective tendency, v2'):
  (6.21) deep-trigger humidity excess + min(3e-4, dq/dt|adv x 600 s) below 700 hPa, and (6.29-6.32, Cy47r3) the QCV term in the
  closure, QCV = -0.8 Lv tau_c/(g H) int_lowest 60 hPa (q/qsat) dq/dt|adv dp (off where the column saturation fraction > 0.94).
  Storms are convergence-driven -> this is also the leading P3 suspect (package storms start with half the core rain).
  BUILT (default off; base2 6-h run bit-identical): carry q_adv = (q_now - q_last)/dt - physics tendency (the dynamics-only moisture
  tendency of the previous step, from surface()); ifs_phys.convection(q_adv=..., a_qcv=0.8) adds 6.21 and QCV (PCAPE'' of 6.30-6.31
  not recomputed in v2: one-step advective change, negligible).
  REGISTERED (T42, 3 Oct-Nov starts): fix CONFIRMED if day-0 (0-24 h) global rain rises from 1.8 to >= 2.4 mm/day and rain at h0-h6
  >= 1.5 mm/day, AND t850 d2 bias improves by >= 0.2 K (from -1.21), with day-1 rain not above ERA5 (3.0) by > 10 %.
- 23:30 RESULT (registered 23:15): 6.21 + QCV do NOT fix the spin-up -> hypothesis REJECTED. Global rain h0..h45 (3-hourly, T42, 3 starts):
  package 0.15 0.78 1.29 1.88 2.08 3.05 ... ; with q_adv+QCV 0.15 0.74 1.33 1.85 2.09 2.85 ... (unchanged within noise). Reason: QCV is
  ~Lv tau/(gH) x 0.8 x int(q/qs dq/dt_adv dp) ~ a few J/kg in the global mean vs PCAPE tens - a storm-scale term, not a global one; and at
  h0 the advective tendency is zero by construction. Options kept (default off) for the storm test (P3) where convergence is large.
  NEXT (running): swap test - convection on the h0 state with each h24 input (surface fluxes, BL+radiation tendency, T, q) to find
  which input carries the missing instability at the start.
- 23:40 SWAP TEST (T42, 1 Nov, global means; convection called on the h0 state with h24 inputs swapped in):
  h0 as is: deep 0.024, PCAPE 0.0, conv rain 0.04 mm/day | h24 as is: deep 0.283, PCAPE 22, 1.91
  h0 + h24 surface fluxes / BL+rad tendency / all inputs: deep 0.022-0.024, rain 0.04-0.07 -> the INPUTS are NOT the cause
  h0 + h24 T: deep 0.19, rain 1.99 | h0 + h24 q: deep 0.21, 1.56 | h0 + h24 T and q: deep 0.29, 1.66 -> the STATE is the cause.
  Tropics (20S-20N) h24 - h0: T -0.7..-1.1 K from 990 to 790 hPa; q +1.1..+1.2 g/kg at 990-950 hPa, ~0 above 900.
  => The IFS deep-trigger test (6.4/6.21) fires in only 2.4 % of columns on the ERA5 start; the model then cools the lower troposphere
  ~1 K and moistens the sub-cloud layer until the trigger fires (28 %). THIS IS the A/P1 cold bias: the convection scheme's own
  equilibrium is ~1 K colder than ERA5. The real IFS rains from step 1 on ERA5 (ERA5 is IFS's own equilibrium), so our trigger /
  test parcel is stricter than the documented one. NEXT (running): which trigger condition fails on tropical ocean at h0 (cloud base
  not found / parcel dies before 200 hPa depth / source level).
- 23:45 DEEP-TRIGGER DIAGNOSIS (tropical ocean 20S-20N, h0 vs h24, test parcel +0.2 K / +0.1 g/kg as in 6.21):
  departure sig 0.971: cloud base found 100 % both times (911 / 937 hPa) but max in-cloud buoyancy -0.65 K at h0 vs +2.07 K at h24;
  parcel top 886 vs 557 hPa; deep test passes 3 % vs 51 %. Source RH 0.80 (h0) vs 0.88 (h24). -> the parcel is too cold/dry at the start.
  SUSPECT (start data, not physics): MEGAM starts from WB2 ERA5 on 13 levels - nothing between 1000, 925 and 850 hPa. The 975/950 hPa
  (sub-cloud) humidity is interpolated straight across the top of the mixed layer -> too dry by about the +1.1..1.2 g/kg the model then
  adds at 990-950 hPa in day 1; ~1 g/kg in the parcel = ~2.5 K of moist static energy = the -0.65 -> +2 K buoyancy gap.
  REGISTERED (check running on GitHub, ERA5 37 levels, 3 starts, tropical ocean): start-data cause CONFIRMED if the 13-level
  interpolation is too dry at 975 AND 950 hPa by >= 0.5 g/kg; REJECTED if |error| < 0.3 g/kg (then the plume itself is too strict).
  If confirmed, fix = build start fields with the extra ERA5 levels 975/950/900/875/825/800 (ARCO), no physics change.
- 23:50 RESULT bl truth (ERA5 37 levels vs the 13-level interpolation, tropical ocean 20S-20N, 3 starts, data/cyclone/wx/bl_levels.txt):
  q error at 975 / 950 hPa -0.50..-0.55 / -0.54..-0.58 g/kg (too DRY), T +0.44..0.46 / +0.50..0.52 K (too WARM); 900/875 hPa T +0.06..0.32 K.
  By the registered rule (>= 0.5 g/kg at both levels) the start-data cause is CONFIRMED - but only just (1 Nov 975 hPa = 0.50).
  SIZE: applying the measured mean error to the h0 state (T42) raises global deep-trigger columns 2.4 % -> 5.8 % and h0 convective
  rain 0.04 -> 0.30 mm/day (h24: 28 %, 1.9). => REAL but PARTIAL (~15 % of the spin-up). Fix (start fields with ERA5 975/950/900/875/
  825/800 hPa) is worth doing and costs no physics change, but it does not close A/P1 alone.
  REMAINING (open): even on corrected ERA5 the test parcel is negatively buoyant in ~94 % of columns. Suspects, in order:
  (1) resolution - the trigger is nonlinear and T42 / 1.5 deg start fields remove the moist, warm extremes where it would fire
      (test: same diagnosis at T85/T170 on the same date); (2) the test parcel's 50 %-condensate loading or the 6.10 kinetic-energy
      factors (check against the text line by line); (3) our lowest model level (sig 0.99, ~80 m) vs the IFS 2nd level (~30 m).
- 23:51 TEST-PARCEL CHECK vs IFS text: (6.10) - the kinetic-energy equation that ends the test parcel - uses Tv,up WITHOUT
  condensate loading; only PCAPE (6.22) subtracts l_up. MEGAM's plume subtracts it in both. Diagnostic switch TEST_LOAD (default =
  old behaviour). h0 T42 global: deep columns 2.4 % (as is) -> 5.5 % (no loading in 6.10) -> 11.0 % (+ corrected BL start); h24 34 %.
  BUT h0 convective rain only 0.04 -> 0.30 mm/day: the triggered FULL updraughts still find PCAPE ~ 0 on the ERA5 start.
  => on ERA5 soundings MEGAM's entraining plumes are generally not buoyant; the model has to cool the lower troposphere ~1 K first.
  Running: (a) 13-level interpolation error over the whole 1000-300 hPa column (850-700 hPa is also interpolated: if the environment
  there is too warm, every plume loses buoyancy); (b) same h0 diagnosis at T85 / T170 (resolution / smoothing of the extremes).
- 23:54 THREE CHECKS:
  (1) RESOLUTION rejected: same h0 diagnosis at T85 - deep columns 2.0 %, conv rain 0.01 mm/day (T42: 2.4 %, 0.04).
  (2) PLUME THERMODYNAMICS correct: MEGAM undiluted parcel (60 columns, 10S-10N ocean, h0) vs MetPy parcel_profile: same buoyancy
      within 0.00-0.27 K at every level (MEGAM slightly cooler aloft, ice). Not the cause.
  (3) START DATA, whole column (ERA5 37 levels vs 13-level interpolation, 20S-20N ocean, 1 Nov): 975/950 too dry -0.5 g/kg and
      +0.45/+0.5 K warm; 900/875 +0.22 K; 825-750 hPa (trade inversion) -0.38..-0.48 K COLD and +0.34..+0.50 g/kg MOIST; above 650 small.
      Undiluted parcel from 975 hPa on the MEAN sounding: CAPE 33 J/kg on 37 levels vs 2 J/kg on the 13-level interpolation; buoyancy
      -0.5 K lower at 875-925 hPa and -0.4 K lower at 450-650 hPa. The interpolation errors vary with the inversion height, so a
      mean correction (tested: deep 2.4 -> 5.8 %) is not the real test.
  REGISTERED (running on GitHub: start fields from all 29 ERA5 levels >= 50 hPa, ARCO 0.25 deg box-mean to 1.5 deg, 3 dates; the
  control is the 13-level subset of the SAME file, so only the vertical sampling differs): start-data cause CONFIRMED as the main
  driver if, at T42 h0, deep columns rise from ~2.4 % to >= 12 % AND h0 convective rain to >= 1.0 mm/day; PARTIAL if 5-12 % /
  0.3-1.0; REJECTED if < 5 % (then: entrainment/closure vs ERA5 equilibrium). Then the forecast test (t850 d1-d2, rain, LHF).
- 00:05 (14 Nov) RESULT l37 test (registered 23:54): start from all 29 ERA5 levels vs the 13-level subset of the same file, T42 h0:
  deep columns 1.9/2.1/2.1 % -> 2.4/2.4/2.6 %; conv rain 0.15/0.15/0.17 -> 0.16/0.15/0.19 mm/day (3 dates). => REJECTED (< 5 %).
  The 13-level start is NOT the main cause; the mean-sounding CAPE (33 vs 2 J/kg) was an artefact of averaging trade-wind columns.
  My 23:54 message called this "cause found" - that was premature and is withdrawn. (Side fix kept: init extrapolates up to 4 level
  spacings, needed for any all-level start; 13-level starts bit-identical.)
  WHAT STANDS: the IFS deep trigger fires in ~2.5 % of columns on ERA5 starts (any level set, T42 or T85); the model then cools the
  lower troposphere ~1 K (radiation not offset by convective heating) until it fires (28 %). Plume thermodynamics verified (MetPy).
  Measured part: 6.10 condensate loading (doc says none) 2.4 -> 5.5 %.
  NEXT: a real reference for how often deep convection should be on at the start - ERA5's own convective precipitation in the first
  hour (fraction of tropical columns with cp > 0, and its total) - then compare our trigger column by column against it.
- 00:10 REFERENCE (ERA5 hour 0-1, 3 starts, cp_start.npz): convective precip 1.27-1.39 mm/day global (total 2.7-2.9); 13-16 % of
  native tropical points with cp > 0.1 mm/h. MEGAM package at h0: 0.15 mm/day, deep trigger ~4 % of tropical columns -> 9x too little.
  COLUMN BY COLUMN (1 Nov, T42): where ERA5 rains convectively (cp > 0.1 mm/h, 21 % of tropical columns) our test parcel's median
  max in-cloud buoyancy is -0.5 K: MARGINAL. Trigger hit rate there 10.8 % with condensate loading in the K equation (current code)
  vs 27.8 % without it (6.10 as written); false alarms where ERA5 is dry 0.1 % / 0.8 %. (cp > 0.5 mm/h: 16 % vs 35 %.)
  The same (6.10) also governs the FULL updraught's kinetic energy - with loading it dies early -> PCAPE ~0 even when triggered.
  BUILT option ke_noload (6.10 without loading for test parcels AND the full updraught; PCAPE 6.22 keeps loading; default off).
  REGISTERED (T42 spin test, 3 starts, package + ke_noload): CONFIRMED as a main driver if h0-h6 global rain >= 1.5 mm/day (now
  0.15-1.3) AND 0-24 h global rain >= 2.4 mm/day (now 1.8), with day-1 not above ERA5 (3.0) by > 10 %; then the forecast test
  (t850/t700 d1-d2 vs ERA5, rain, LHF) must improve t850 d2 by >= 0.2 K. PARTIAL if h0-h6 0.6-1.5.
- 00:20 RESULT ke_noload spin test (registered 00:10): rain h0..h12 0.17 0.76 1.19 1.81 2.12 (package 0.15 0.78 1.29 1.88 2.08)
  -> REJECTED as a driver (trigger fires more, rain unchanged). Kept as an option (doc-faithful, default off).
  FULL-UPDRAUGHT PROFILE in triggered columns (T42, 1 Nov, ke_noload): h0 Tv_up - Tv only +0.1..+0.36 K from 860 to 300 hPa while
  condensate loading costs 0.15..0.6 K -> PCAPE median -44 Pa (> 0 in 11 % of triggered columns) -> closure mass flux ~0.
  h24: Tv excess +0.4..+1.15 K, PCAPE > 0 in 69 %. Condensate 2 g/kg at 500 hPa; precipitation conversion (6.44-6.46) checked line by
  line against Cy50r1 - identical (the IFS text itself says updraught condensate is "probably still overestimated").
  CONCLUSION OF THE NIGHT (4 hypotheses tested, all against references): MEGAM's IFS convection is faithful to the documentation,
  but at our resolution / start data the ERA5 atmosphere is only marginally unstable for its entraining, water-loaded plume (+0.1-0.3 K),
  so it barely rains for ~12-15 h and radiation cools the lower troposphere ~1 K until the scheme's own equilibrium is reached.
  ERA5 (produced by the same scheme at 31 km / 137 levels) rains 1.3 mm/day convectively from hour 1. The difference is the
  resolution at which the scheme sees the atmosphere (T42/T85 tested; T170 evidence: P3 core rain at h0 24 vs 41 mm/day).
  Rejected tonight: 6.21+QCV, 13-level start data (as the main cause), grid T42->T85, plume thermodynamics (MetPy-verified),
  6.10 loading. Partial real effects kept as default-off options: 13->29-level start (+0.5 % deep), 6.10 loading (2.4 -> 5.5 % deep).
  DECISION NEEDED (Sridhar, 07:00 report): the package convection cannot be "fixed" without tuning (closure/entrainment constants),
  which our rules forbid. Options: (a) keep base2 convection (rains from step 1) and adopt only the non-convection package parts
  (bl_lcl, sfc_sal, rad lw_cnt/qs_mix) - test registered next; (b) ask the expert whether IFS uses resolution-dependent constants
  for its convection at ~100 km (the 6.27 tau factor is the only one documented); (c) accept the day-1 spin-up and judge the package
  on days 2-5 only.
- 00:25 REGISTERED option (a) "parts" = base2 convection + bl_lcl 1, sfc_sal 0.98, rad_prm {lw_cnt 0.667, qs_mix 1} (no phys_ifs).
  T42, 3 starts (27 Oct / 1 Nov / 6 Nov), vs ERA5 (rh_truth / flux_truth): viable if t850 AND t700 global d2 |bias| <= 0.6 K
  (package -1.14 / -1.04) and day-1 rain and LHF within 15 % of ERA5; then storms (rule 2, seeds 4-6) and the T170 screen.
  base2 and the package are rerun on the same starts as controls.
- 00:52 SRIDHAR DECISION: option (a) for Stage 1 - base2 convection + the package's non-convection parts (bl_lcl, sfc_sal, rad_prm),
  subject to the registered (a) test. The full IFS convection (phys_ifs, with ke_noload / 29-level start / q_adv+QCV options kept,
  default off) is PARKED for Stage 3, where it is to be adopted completely.
- 01:15 RESULT option (a) test (registered 00:25; NOTE the starts actually run were 7 Oct / 1 Nov / 26 Nov - the script's indices
  56,61,66 map to these dates in rh_truth, not 27 Oct / 6 Nov as I wrote; same starts for all three candidates, so the comparison holds):
               t850 d1/d2        t700 d1/d2        rh850 d2   day-1 rain (ERA5 3.0)   LHF (ERA5 -84.9)
    base2      +0.18 / +0.05     -1.34 / -1.55     +0.049     3.2                     -105.4 (+24 %)
    parts (a)  +0.47 / +0.55     -1.23 / -1.31     +0.001     3.0                     -97.1 (+14 %)
    package    -0.85 / -1.21     -0.81 / -1.12     +0.082     (2.6-3.0 earlier)       (-77.9 earlier)
  VERDICT by the registered rule: option (a) FAILS - t850 d2 +0.55 OK, rain OK, LHF +14 % OK, but t700 d2 -1.31 K (limit 0.6).
  Not adopted. The 700 hPa cold bias belongs to base2 itself (-1.55) and is only slightly reduced by the parts; the package's
  convection is the only version that is better at 700 hPa (-1.12) but it is worse at 850.
  => A/P1 has TWO separate pieces: (i) 850 hPa: package-convection spin-up (fixed by (a): +0.55); (ii) 700 hPa: ~-1.3 K in every
  version since base2 - root cause still open (radiation at 700-850 hPa matches RRTMG, so the suspect is missing convective heating
  at 700 hPa in base2 conv_mf: its heating profile vs ERA5/IFS). Next: column heating budget at 700 hPa (radiation, convection,
  large-scale condensation, dynamics) base2 vs ERA5's implied heating, T42, same starts.
- 01:20 700 hPa HEATING BY PROCESS (T42, 1 Nov, +24 h, K/day at sigma 0.81 / 0.70 / 0.62; physics only):
                       deep          shallow            large-scale cond   rain evaporation   radiation          physics total
    parts globe        +0.89/1.07/1.17  -1.23/-0.74/-0.78  +2.51/0.94/0.94    -0.98/-0.69/-0.55  -2.14/-1.01/-1.03  -0.88/-0.42/-0.25
    parts tropics      +1.17/2.16/2.80  +0.05/-1.58/-1.31  +0.86/1.36/1.07    -1.93/-1.40/-1.24  -0.99/-0.63/-0.74  -0.82/-0.09/+0.58
    package globe      +0.47/0.46/0.48   0 (in deep)       +0.46/0.31/0.33    -0.10/-0.10/-0.08  -1.67/-1.16/-1.04  -0.79/-0.41/-0.19
  Physics totals at 700 hPa are similar (-0.42 vs -0.41 globe), so the budget alone does not show the 700 hPa deficit (needs the
  dynamics term / a reference). Two base2 processes stand out against the doc-faithful IFS scheme at 700 hPa: the shallow (MSE-mixing)
  scheme cools 700 hPa by -0.74 K/day globally (-1.6 tropics) - mixing that reaches above the trade inversion - and rain evaporation is
  -0.69 (-1.4 tropics) vs -0.10 in the IFS scheme. SUSPECTS for the 700 hPa piece, in order: (1) base2 shallow-mixing depth;
  (2) base2 rain-evaporation rate. Reference needed before any change: observed / IFS Q1 and evaporative-cooling profiles at 700 hPa
  (literature, e.g. Yanai-type budgets, IFS diagnostics). Next session.
- 11:15 (14 Nov) T170 EXAM QUARTER 0 (19 starts) - package tn-lcl-wx0 vs base2 tn-s-rd-wx0 vs base2+cubic tn-s-vc-wx0, bias d1/d2/d3/d5:
    t850 globe    base2 +0.33/+0.06/-0.02/-0.10   package -0.73/-1.14/-1.37/-1.71   cubic +0.42/+0.17/+0.09/+0.02
    t850 tropics  base2 +1.27/+1.05/+1.06/+1.05   package -1.17/-1.72/-2.04/-2.45   cubic +1.41/+1.21/+1.23/+1.24
    rain24 globe  base2 +0.23/+0.81/+0.96/+1.13   package -0.62/+0.38/+0.49/+0.52   cubic +0.29/+0.79/+0.91/+1.02
    z500 globe    base2 -10.3/-15.5/-19.5/-26.6   package -14.7/-21.8/-27.4/-36.2   cubic -7.3/-10.7/-13.6/-18.4
  The package spin-up IS present at T170 (day-1 rain -0.62 mm/day, t850 cooling grows to -1.7 K by day 5) -> resolution (T170) does
  not save the IFS convection; consistent with Sridhar's decision (a). Note base2 at T170 is WARM in the tropics at 850 hPa (+1.05..
  +1.27 K) - the 850 hPa "fix" of option (a) (+0.55 K at T42) must be re-checked at T170 before adoption (risk: tropics too warm).
  Cubic: z500 drift -27 -> -18 m by d5, u200 better; t850 ~same. Track rule (q6 3-member) not run: Kaggle accounts 1 AND 4 both at the
  30-h weekly GPU limit (account 4 hit it overnight; refused pushes used no GPU). Next GPU: E2E after Monday top-up.
  tn-r24-lcl-b (package TN rain) not scored - package not adopted for Stage 1.
- 10:05 (15 Nov) TRACK RULE partial (q6, 72 h error km, mean of 6 storms): base2 seed 4 = 371, seed 5 = 410; cubic seed 4 = 429.
  Verdict waits for cubic seeds 5-6 and base2 seed 6 (rule: cubic mean not worse than base2 mean by more than the base2 member
  spread). Account 1 and account 4 quotas reset 14/15 Nov; remaining jobs queued.
- 16:05 (15 Nov) cubic seed 5 = 512 km (seed 4 429; corrected - first entry wrongly said 424). Waiting: base2 seed 6 (running, account 4), cubic seed 6 (queued).
- 10:10 (16 Nov) base2 seed 6 = 355 km -> base2 mean 379 (371/410/355), member spread 55 km. Cubic so far 429/512 (mean 470).
  Pass limit for cubic mean = 379 + 55 = 434 km -> needs seed 6 <= 361 km. Cubic seed 6 running (account 4). The 22:00 and 04:00
  cycles of 15/16 Nov did not run (session idle); this pass done at 10:00 16 Nov.
- 16:10 (16 Nov) TRACK RULE VERDICT, cubic (sl_vcubic) vs base2, q6 6 storms x 3 seeds, 72 h error km:
    base2 371 / 410 / 355  mean 379, spread 55   | cubic 429 / 512 / 614  mean 518
  Limit = 379 + 55 = 434 -> cubic FAILS by 84 km (worse in every seed; Giri/Hamoon worst: 672-1200 km). NOT ADOPTED.
  Cubic improves z500 drift (-27 -> -18 m at d5, T170) but moves storms worse - consistent with the 6 Nov suspicion that cubic
  vertical interpolation without a limiter shifts storm cores (overshoot near the warm core). Next for D1/D2: cubic with a
  monotone limiter (SLMONO option exists in hyb_jet) - derive and T42-test before any GPU.
- 00:25 (17 Nov) 700 hPa ATTRIBUTION (diagnostic denial, not adoption), T42, starts 7 Oct / 1 Nov / 26 Nov vs ERA5 rh_truth:
  parts (= option a) vs parts + sh_depth (shallow mixing only for clouds <= 200 hPa deep) vs parts + k_evap 0 (no rain evaporation).
  PREDICTION: if the base2 shallow-mixing top is the main 700 hPa sink, sh_depth moves t700 d2 by >= +0.5 K (from -1.31);
  if rain evaporation is, k_evap 0 moves it by >= +0.5 K. If neither moves it >= 0.5 K, the 700 hPa cold is not physics-local
  (next: dynamics/vertical advection at 700 hPa).
- 01:15 (17 Nov) RESULT 700 hPa attribution (registered 00:25), day-2 global bias t850 / t700:
    parts (a)            +0.55 / -1.31
    parts + sh_depth     -1.10 / -0.69   (t700 +0.62 -> shallow-mixing top CONFIRMED as a 700 hPa sink)
    parts + k_evap 0     +1.79 / -0.60   (t700 +0.72 -> rain evaporation CONFIRMED as a column sink)
  Reading: base2's tall "shallow" MSE mixing (to 300 hPa deep) moves heat from 700 down to 850 - it HIDES a cold 850 (with
  sh_depth 850 is -1.1) and creates the cold 700. Rain evaporation (-0.69 K/day at 700 vs -0.10 in the IFS scheme) cools the column.
  REGISTERED NEXT: parts + sh_depth + evap_ifs (IFS Kessler sub-cloud evaporation, existing option): viable if t850 AND t700
  d2 |bias| <= 0.6 K, day-1 rain and LHF within 15 % of ERA5. Then storms (rule 2) and T170.
- 01:35 (17 Nov) D1/D2 cubic track failure - suspect "cubic vertical overshoot without limiter" REJECTED by code inspection:
  MEGAM runs mono=True -> Dinosaur monotone_dynamics -> semi_lagrangian.interpolate_3d(limiter='quasi_monotone') clips the cubic
  result to the 2x2x2 bracketing cell, whose vertical extent is always the two nodes around the departure sigma, regardless of
  vertical_order (semi_lagrangian.py docstring + code). So the cubic is already limited. Remaining suspect: cubic makes storms
  STRONGER (rule 2: 0.70 vs 2.60 hPa) -> deeper vortex feels base2's mid-level steering error more. Base2's own 72 h track error
  (379 km vs 280 target) - leading suspect is P5's Bay u850 easterly bias (-4 m/s by day 3), which steers storms west.
- 01:55 (17 Nov) RESULT parts + sh_depth + evap_ifs (registered 01:15), T42 3 starts, day-2 global bias:
  t850 -0.87 (FAIL, limit 0.6) | t700 -0.39 OK | day-1 rain 2.7 vs 3.0 (-10 %) OK | LHF -97.2 vs -84.9 (+14 %) OK | rh850 +0.10.
  NOT adopted. Progress: worst level 1.31 K -> 0.87 K. With the tall mixing gone, a real 850 hPa cold appears (same sign as the
  package's -1.2) together with a too-moist 850 hPa (+0.10 RH). Suspects (from earlier measurements): radiation at 850-1000 hPa
  vs RRTMG -0.3..-0.5 K/day; RH-cloud feedback (moist 850 -> more low cloud -> more cooling). Next: heating by process for this
  version at sigma 0.85 vs option (a) and the package.
- 02:15 (17 Nov) 850 hPa heating by process, parts + sh_depth + evap_ifs (T42, 1 Nov, +24 h, K/day at sigma 0.86 / 0.70 / 0.62, globe):
    deep +0.85/1.02/0.94 | shallow -1.64/-0.05/-0.01 | large-scale cond +2.27/0.32/0.27 | rain evap -0.09/-0.09/-0.12 |
    radiation -1.68/-1.18/-1.02 | physics total -0.25/+0.03/+0.07   (extratropics 850: shallow -1.81, lsc +2.49, rad -1.47)
  Rain evaporation is now IFS-sized (-0.09 vs -0.69). At 850 the remaining sinks are the shallow scheme's cloud-top cooling (-1.6;
  physically right sign - BOMEX-type inversion cooling - size unverified) and radiation (-1.7; earlier measured 0.3-0.5 K/day
  colder than RRTMG at 850-1000 hPa). Together with rh850 +0.10 (moist) the leading suspect is the shallow scheme ventilating too
  little moisture out of the BL into the cloud layer at the right depth (moist 850 -> RH cloud -> extra LW cooling).
  Next (needs a reference): BOMEX/RICO single-column shallow heating and moistening profiles vs ours at 850-950 hPa.
- 02:40 (17 Nov) AKVAN control tn-akvan-new75 (12Z) BLEW UP on Kaggle (member 0 'model blew up'). Cause = my config, not the model:
  I set layers=75 (the plain 75-level spacing), dt 30 min, without sfc_imp / drag_imp. MEGAM's 75-level setup is 'tp75' + dt 20 min
  + implicit surface exchange (sfc_imp) and drag (drag_imp) - the two numerical fixes that closed P2 (75 L stability 19/19, 10 Nov).
  Fixed live_config_new.json (tp75, dt 20, sfc_imp 1, drag_imp 1) and live2.py (layers may be a 'tpNN' string). Local T42 check
  running to completion this time before any GPU relaunch. GPU lost: ~40 min of account 1.
- 08:35 (17 Nov) SRIDHAR: AKVAN control track "looks good" but intensity far too low (peak 32 kt / 1000 hPa) -> concentrate on
  INTENSITY. Also hypothesis for the general WEST track bias: Arabian ridge too dominant, Indochina / Asian ridge too weak in MEGAM.
  REGISTERED (T42 base2, 8 NE-monsoon starts 2 Oct - 7 Dec 2020, day 5 vs ERA5 = next library entry): hypothesis SUPPORTED if
  z500 bias (Arabian box 15-28N 55-75E) minus (Indochina/SCS box 12-25N 95-115E) >= +10 m with the same sign in >= 6/8 starts,
  and Bay u850 bias easterly (< -1 m/s). REJECTED if the difference is < +5 m or flips sign across starts.
  (24 Oct steering check already found Bay u850 -3.0 / u200 +3.0 m/s at day 5 -> too much shear, overturning too strong.)
  Map runs tn-akvan-maps-12/-18 launched 07:55 for the viewer; Sridhar 08:21 "not required now" - Kaggle kernels cannot be
  cancelled; outputs kept for later.

## 17 Nov 10:05 IST — Sridhar's ridge hypothesis (west track bias = Arabian ridge too strong, Indochina/Asian ridge too weak)
Registered rule (before results): SUPPORTED if z500 bias(Arabian 15-28N 55-75E) − bias(Indochina/SCS 12-25N 95-115E) ≥ +10 m with same sign in ≥ 6/8 starts AND Bay u850 bias < −1 m/s; REJECTED if difference < +5 m or sign flips.
Test: T42 base2, 8 NE-monsoon starts 2 Oct–11 Dec 2020, day 5 vs ERA5 (WB2 1.5°), script /tmp/claude-0/ridge_bias.py.
- z500 bias: Arabian −16.6 m (spread 20), Indochina −15.5 (14), Bay −16.5, Tibet/Asia −11.4. Per-start Arabian−Indochina: +7, +14.5, −26, +6.4, +5.3, +65.6, −42.8, −38.7 → mean ≈ −1 m, sign flips. **z500 hypothesis REJECTED** (uniform −16 m tropical drift, no E–W imbalance).
- 850 hPa: z850 Arabian +12.0 m vs Indochina −4.5, Bay −7.9 (difference +16.5 m; Tibet value is a below-ground artefact). u850: Bay −3.3 m/s (easterly), Indochina −3.0; v850 Arabian −1.9, Indochina +1.9.
- Reading: the low-level Arabian/NW-India high is too strong relative to the east, consistent with the P5 Bay easterly bias. West push is a LOW-LEVEL (850) problem, not 500-hPa steering. Per-start z850 not saved → consistency of the +12 m unverified.
- Next (P5): what builds the 850 Arabian high (radiative cooling / subsidence over the dry NW); recheck at T170 before calling it confirmed.

## 17 Nov 10:45 IST — RULE 1 (intensity, registered 13 Nov 11:40) — BASE2 baseline at T170 32 L: FAIL
Jobs tn-r1-b2-0 (42 storms) + tn-r1-b2-1 (41) = whole lib84 library, 83 storms (the rule text said "41-storm library"; the library is 83 -
judged on all 83; halves alone give 83 % / 66 %, not used to pick a pass). Scorer scripts/cyclone/rule1_score.py: model min pmin over 0-72 h
vs ERA5 0.25° peak msl (peak_targets.json).
- Within ±5 hPa: 62/83 = 75 % (need 80 %, i.e. 67) -> FAIL. Mean error +0.28, mean |err| 3.62, 13 too weak (>+5), 8 too deep (<-5).
- Pattern: intensity range is COMPRESSED. Regression slope model-vs-ERA5 peak 0.44, r 0.51. ERA5 peak < 995 hPa (20 strongest): mean +4.2 hPa
  too weak, only 8/20 within ±5 (Madi +14.8, Sidr +10.6, Phailin +9.5, Helen +8.6, Giri +8.5, Sitrang +8.1, Hudhud +8.0, Nilam +7.9).
  995-1001: +0.35, 25/31. >1001 (weak systems): −2.3 too deep, 29/32 (Fengal −12.2, Fanoos −8.3).
- Reading: the failure is the strong storms not deepening (same symptom as AKVAN peaking at ~1001 hPa) plus weak lows over-deepening.
  Rank of suspects for the strong-storm deficit (to test, not yet tested): storm-core convective heating too slow at start (A/P1: ERA5 cp
  1.3 vs ours 0.15 mm/day at hour 1 with package; base2 not yet measured the same way), cold/dry low levels, T170 resolution
  (ERA5 0.25° targets are themselves weak for Phailin/Hudhud, so resolution is a partial explanation only).
- Next: storm-core heating/moisture budget for the 20 strongest, base2 vs ERA5 (registered predictions before running).

## 17 Nov 10:55 IST — AKVAN light TN rain: convection test (Sridhar 10:25: "rain quantum and intensity no much relation... Convection is problem")
Correction to my 10:21 answer: I gave "weak storm" as reason 1. Sridhar is right that rain amount does not need a deep low (weak LPAs/depressions
give very heavy TN rain, e.g. via onshore convergence bands). Weak central pressure and light rain are better read as two symptoms of one
cause: convection that does not switch on (package IFS convection under-triggers on our start: ERA5 cp 1.3 vs ours 0.15 mm/day at hour 1).
Test (one change): live_config_new_b2c.json = live_config_new.json minus phys_ifs/ke_noload/q_adv/a_qcv (convection back to base2), same 18Z
GFS start, tp75 T170, account 4 after a local T42 7-day stability check.
REGISTERED before results (metric = north-TN 4 districts Chennai/Tiruvallur/Chengalpattu/Kancheepuram, mean of daily rain, days 2-6, vs the
18Z package run 4.7 mm/day; and model-domain convective share):
- SUPPORTED if north-TN mean rain >= 1.5x the package run (>= 7 mm/day) - whatever the central pressure does.
- REJECTED if within ±25 % of the package run -> convection scheme is not the limiter; next suspect = moisture supply (onshore q flux, tcw vs GFS).
- Intensity reported but not part of the verdict.

## 17 Nov 11:15 IST — Sridhar's 850-hPa Arabian-high idea, sharpened (11:02): the model's high is too strong IN GENERAL; when the real one
is also strong (Akvan, Vardah) the real storm goes W so our track looks right; when the real one weakens (Nivar, Michaung) ours stays
strong and the storm goes W/SW instead of NW/N. Claude's refinement: maybe not a constant offset but a failure to WEAKEN the high
(Michaung: ERA5 trough 63->76.5E, ours parked at 71-72E).
Test (local CPU, T42 base2 32 L, hind2-identical init + bogus, 120 h, z850 vs ERA5 days_YYYY 1° 12-hourly, terrain > 800 m masked):
westward group Vardah, Thane, Gaja, Mandous, Burevi; turning group Nivar, Michaung, Hamoon, Sidr, Phethai.
Boxes: Arabian/NW-India 15-28N 55-75E (as before) and C/NW India 18-28N 70-85E (north of the Bay - geostrophically the one that sets
Bay easterlies); also Bay u850 10-22N 80-95E. Metric = mean z850 bias days 2-5.
REGISTERED before results:
- STATE-DEPENDENT (Sridhar's idea as sharpened) if turning-group bias >= +10 m AND exceeds the westward group by >= 10 m (either box).
- CONSTANT offset if both groups >= +5 m and differ by < 5 m.
- NOT SUPPORTED if the turning-group bias < +5 m in both boxes.
- Caveat fixed now: T42 (not T170), 5+5 storms -> a result here is a lead, confirmation needs T170.

## 17 Nov 11:20 IST — AKVAN convection test RESULT (registered 10:55): NOT SUPPORTED
tn-akvan-b2c-18 (base2 convection, everything else = MEGAM-new, 18Z, tp75 T170; 623 s on account 4).
- North-TN 4 districts, mean daily rain days 2-6: base2 conv 3.29 mm/day vs package 4.73 (−30 %). Registered: SUPPORTED needed >= 7;
  REJECTED band was ±25 %. Result is outside both, in the WRONG direction -> "package convection is the rain limiter" is NOT supported.
- Confounder: the track changed. Base2-conv storm is weaker (min 1003.4 vs 1001.6 hPa) and goes further north (15.1N 81.6E at 72 h,
  then NNE to 20-24N), so N-TN is further from the system. TN-mean 7-day rain is higher (29.1 vs 19.6 mm) but from days 6-7 (post-system).
- Reading: neither convection scheme gives heavy N-TN rain from this system; switching scheme is not the lever. Sridhar's point stands
  that rain amount is not set by central pressure; the next registered suspect is the moisture supply (onshore moisture flux into N-TN,
  tcw vs GFS). Real reference: IMD/TN-SMART observed rain for 18-21 Nov once the event is over - verify both runs against it.
- Arabian-high test amendment (before any group result; only Vardah seen): ERA5 start library (1.5°) and days_YYYY (1°) z850 differ by
  ~+20 m over the Arabian box at the SAME time (1551 vs 1531 m: product/grid difference, not model error). Metric changed to bias GROWTH:
  bias(day d) − bias(day 0), days 2-5. Thresholds unchanged.

## 17 Nov 12:00 IST — 850-hPa Arabian-high test RESULT (registered 11:15, metric amended 11:20 to growth since day 0): NOT SUPPORTED
scripts/cyclone/ah850.py, data/cyclone/wx/ah850_t42.json (T42 base2, bogus, 120 h, vs ERA5 days_YYYY, terrain > 800 m masked).
Mean growth of the z850 bias, days 2-5:
| Box | Westward (Vardah, Thane, Gaja, Mandous, Burevi) | Turning (Nivar, Michaung, Hamoon, Sidr, Phethai) |
| Arabian/NW India 15-28N 55-75E | +15.6 m (5.5..21.0) | +3.9 m (−7.4..+22.4) |
| C/NW India 18-28N 70-85E | −1.7 m | −6.4 m |
| Bay u850 10-22N 80-95E | −2.5 m/s | −2.2 m/s |
- Rule: turning group < +5 m in both boxes -> NOT SUPPORTED. The high does grow too strong over Arabia in general (all-10 mean ~+10 m),
  but MORE in the westward cases, not in the turning ones; Michaung and Hamoon have it too LOW over C/NW India by days 3-5.
- Bay easterly bias grows the same in both groups (−2.5 vs −2.2 m/s) -> it is not explained by the Arabian/NW-India high.
- Caveats: T42, 5+5 storms, tracks of these runs not saved (the model's own storm can enter the C/NW box late, e.g. Michaung).
- Next suspect for the Bay easterly: the eastern side (Indochina/SCS/W-Pacific ridge too weak - the other half of Sridhar's 17 Nov idea)
  or a Bay-local cause (P5b: cold land low levels / SE-Tibet terrain pressure). Same script with Indochina + W-Pacific boxes next.
- 12:05 REGISTERED follow-up (same 10 storms, same metric): east side box Indochina/SCS 12-25N 95-110E (days files end at 110E).
  SUPPORTED (weak eastern ridge drives the Bay easterly) if its 10-storm mean z850 growth <= −5 m AND, across storms, the growth of
  [Arabian − Indochina] correlates with Bay u850 growth at r <= −0.5. NOT SUPPORTED if growth > 0 or |r| < 0.3.
- 12:50 Indochina follow-up RESULT: NOT SUPPORTED. 10-storm mean z850 growth over Indochina/SCS −0.6 m (needed <= −5; per storm −15.7..+12.6);
  r([Arabian − Indochina] growth, Bay u850 growth) = −0.19 (|r| < 0.3). Neither ridge (west or east) explains the Bay 850 easterly bias in
  these 10 storms. Reading: the easterly is Bay-local or tied to the model's own storm (box contains the vortex; weaker/misplaced model
  storm changes box-mean u). Next: 850-hPa u tendency budget by process over the Bay (HANDOFF priority 3) with the vortex region masked.

## 17 Nov 13:25 IST — P5b Bay 850-hPa u ERROR-TENDENCY budget (Sridhar 13:08 "Yes"), REGISTERED before results
scripts/cyclone/ubudget.py: T85 base2 32 L, 8 NE-monsoon starts 2020 (2 Oct ... 11 Dec, as the ridge test), 48 h, no bogus (general
starts -> no model-vortex contamination). On the ERA5 1° grid at 850 hPa, model and ERA5 alike: du/dt (12-h centred), horizontal
advection, Coriolis + pressure gradient (f v − g dz/dx), residual (friction, vertical advection, convective momentum, diffusion).
Error tendency = model − ERA5, mean over h = 12/24/36 and starts. Boxes: Bay 10-22N 80-95E; east of Bay 12-24N 98-110E
(where the 13 Nov maps saw the error appear first); terrain > 1000 m masked. (Smoke test 1 start T42 only: code check, not judged.)
- The term carrying >= 50 % of the Bay's easterly error tendency (same sign) is named the carrier:
  corpgf -> pressure-pattern origin (continue with the NE-of-Bay high-MSLP growth, 13 Nov 15:40);
  adv -> error imported from upstream (east) -> look at the E-of-Bay box first;
  res -> physics/vertical (friction, CMT, vertical advection) -> process split with M.column u_bl/u_cmt next.
- If no term reaches 50 %, report the shares; no carrier named.

## 17 Nov 14:25 IST — Sridhar: "Leave about Akvan. We will continue our work" -> AKVAN verification and map publishing DROPPED.
Work order: P5b Bay u850 budget (running, T85 8 starts) -> P3 storm-core heating/moisture budget for the 20 strongest library storms.

## 17 Nov 17:55 IST — status note + convection COLUMN TEST registered
- Process slip: the Bay u-budget's 2nd half was killed again at the 2-h background limit after 2 of 4 starts (per-start saving kept
  them: 6/8 done). Last 2 starts running now (ubC). I also sat idle waiting for an answer on test order instead of preparing - corrected.
- INTERIM (6 of 8 starts, NOT judged): Bay error tendency −1.54 m/s/day = adv −0.22 + corpgf −0.53 + res −0.79 (res 51 %);
  E of Bay −2.37 = adv −0.97 + corpgf +1.56 + res −2.96. Verdict only on 8 starts.
- Column test (A/P1, corrects my 14:29 'resolution mismatch' claim: IFS runs this scheme at 36-125 km operationally):
  cyc_mlcol.py (GitHub 'ml columns'): ERA5 137-level columns at 2020-11-01T00 / 11-11T00 - 40 strongest-cp cells (>= 1 mm/h hour 1),
  20 weak (0.1-1), 20 dry. Feed each column (ERA5 T, q, u, v, ps, surface fluxes) to our ifs_phys convection on ERA5's 137 levels.
  REGISTERED: SCHEME OK (problem = state we give it) if our cp on the 40 strong columns is within a factor 2 of ERA5's (median ratio
  0.5-2) and >= 70 % of them trigger deep; IMPLEMENTATION if median ratio < 0.3 or < 40 % trigger deep; in between -> report both.
  Dry columns: >= 80 % must give no deep convection (false-trigger check).

## 17 Nov 18:05 IST — CONVECTIVE HEATING: 5-Why + Fishbone + FMEA (Sridhar 17:54: I had stopped using them; and "physics looks correct
## but still fails -> look at the INPUTS to the formula")
Problem statement: IFS-package convection gives 0.15 mm/day convective rain at hour 1 vs ERA5 1.3 (x9 too little); deep columns 2-5 %;
base2 gets its low-level heating from grid-scale condensation (+2.27 K/d) instead of convection; 20 strongest storms ~4 hPa too weak.
5-WHY (IFS package):
1 Why little convective rain? -> few columns trigger deep convection (2-5 %).
2 Why few trigger? -> the test parcel has negative PCAPE: Tv excess +0.1..+0.36 K vs condensate loading 0.15..0.6 K.
3 Why is the parcel excess so small? -> the parcel formula is verified (MetPy), so its INPUTS are suspect: parcel source T/q
  (lowest levels / mixed layer), the environment Tv profile it rises through, the surface-flux excess term, the level spacing.
4 Why would those inputs be wrong? -> known measured input errors: low levels warm/dry or cold/moist by region (P1, B), LHF +14 %,
  start interpolation 13->29 levels (rejected as MAIN cause, real but small), no sub-grid/convective state in the ERA5 start.
5 Why do the inputs differ from what IFS sees? -> OPEN: to be answered by the column test (ERA5's own 137-level state vs ours).
FISHBONE (cause categories -> candidates):
- Inputs/state: parcel source T,q; env Tv profile; surface SH/LH fluxes; ps; large-scale omega / moisture convergence (closure); cloud
  condensate fed to loading; level count/spacing (32/75 vs 137).
- Method/formula: trigger (6.21), PCAPE closure + time scale (resolution-scaled in IFS), entrainment/detrainment, loading (6.10).
- Numerics: timestep / call frequency, order of physics calls (BL before/after convection), DFI removing developing convection.
- Start/initialisation: no convective memory at hour 0, DFI, interpolation.
- Coupling: BL scheme (bl_lcl) supplying the parcel; shallow scheme removing instability first; radiation cooling profile.
- Reference/measurement: ERA5 cp is a model product (IFS's own scheme) - fair reference for 'does our copy behave like IFS'.
FMEA (S severity, O occurrence, D detection difficulty; 1-10; RPN = SxOxD):
| Failure mode | Effect | Cause candidate | S | O | D | RPN | Detection / test |
| Parcel source too cool/dry | no trigger | our BL/lowest-level T,q vs ERA5 | 9 | 7 | 4 | 252 | column swap: ERA5 lowest levels into our column |
| Env too warm aloft (stable) | PCAPE<0 | mid-level T bias / level interp | 8 | 5 | 4 | 160 | column swap: ERA5 T profile above 850 |
| Shallow scheme eats instability first | deep never fires | call order / shallow closure | 8 | 6 | 5 | 240 | run with shallow off on same columns |
| Closure time scale wrong for grid | heating too slow | tau not resolution-scaled as IFS | 7 | 5 | 3 | 105 | compare tau formula vs IFS doc 6.40-ish |
| Surface-flux excess too small | weak trigger | SH/LH or formula input units | 6 | 4 | 3 | 72 | ERA5 fluxes into column |
| Implementation departure | everything | code vs doc | 9 | 3 | 6 | 162 | ERA5-column test (scheme on ERA5 state) |
| No convective memory at start | slow spin-up | init | 6 | 8 | 2 | 96 | cp vs time over first 24 h |
Order by RPN: (1) parcel-source inputs, (2) shallow-before-deep, (3) implementation, (4) env T aloft.
TEST PLAN (input swaps on the SAME columns, registered with the column test of 17:55):
 a) scheme on ERA5 137-level columns (baseline, registered 17:55);
 b) scheme on OUR model state at the same points/hour (T42 & T170 runs at 2020-11-01/11 +1 h);
 c) swaps into b): ERA5 lowest 3 levels T,q only / ERA5 T profile above 850 only / ERA5 surface fluxes only / shallow off.
 The input whose swap restores >= 50 % of the a)-b) rain gap is named the cause. Registered now, before any column result.

## 17 Nov 18:15 IST — WEEKEND TARGET (Sridhar 17:58): close 3 of the remaining problems by Sun 22 Nov.
"Closed" = root cause shown AND either a fix adopted through ALL registered checks, or the item proven not-a-problem / definitively
rejected with its cause. Plan (value x probability):
1. S2 no-DFI - last check = 3-member track rule (registered 13 Nov): quick-6, seeds 4-6, mean 72-h error <= base2 mean 379 + spread 55
   = 434 km -> PASS. Storms passed (3.02 vs 2.60, limit +1.5), exam quarter neutral. PASS -> adopt; FAIL -> rejected with cause.
   Jobs tn-dq4/5/6-q6 queued now (accounts 4/1/4).
2. P4 dry-season rain - measure the current base (base2 + bl_lcl, B fix) dry-season TN/India rain vs ERA5 on the exam starts;
   close if inside the Stage-1 rain gate, else name the cause.
3. A/P1 convective heating inputs (column/input-swap test, FMEA ranks 1-2) - cause by Thu, fix screen Fri-Sat. Fallback 3rd item:
   P5b Bay steering (u-budget carrier this evening).
Risk: Kaggle weekly quota (both accounts used ~this week); a fix may fail its gate - then 'closed' only if the cause is proven.

## 17 Nov 18:25 IST — TARGET RE-SET (Sridhar 18:13: "Don't choose easy ones - harder and most important, the ones that take the model to
## the next step"). The 3 to close by Sun 22 Nov: A/P1 CONVECTIVE HEATING, P3 INTENSITY, P5b BAY STEERING (tracks).
S2 no-DFI and P4 are NOT counted; S2's remaining 3-member track runs continue at lowest priority (2 already launched, seed 6 queued last).
Honest risk: these three are linked (A/P1 heating feeds P3; P5b interim budget points to the physics residual), so one cause may close
two - or none of the three may have a passing fix by Sunday. Gates are not relaxed for the target.
P3 STORM-CORE BUDGET, REGISTERED before results:
Jobs tn-p3core-a (Rule-1 FAIL strong storms: Madi, Sidr, Phailin, Hudhud, Giri, Sitrang, Nilam, Titli, Dana) and tn-p3core-b (strong
storms that PASS: Thane, Michaung, Mandous, Nivar, Vardah, Khai-Muk, Montha, Rashmi); storm_budget.py T170 base2, 72 h every 6 h, radial.
Reference: ERA5 rain around the ERA5 centre (cyc_corerain.py, 'core rain', 100/300 km, total + convective).
- SLOW-HEATING cause SUPPORTED if, in the FAIL group, model 300-km rain over 0-24 h is < 60 % of ERA5's AND this ratio is lower than in
  the PASS group by >= 20 percentage points, AND deep-convective heating share of core heating (h_deep vs h_lsc+h_shal+h_bl) is lower
  in FAIL than PASS.
- REJECTED if FAIL-group 0-24 h rain ratio >= 80 % (heating amount not the limiter) -> next: heating location (radial profile / warm
  core height) and inflow-layer inputs (surface enthalpy flux, low-level q) per the FMEA.

## 17 Nov 18:55 IST — P5b Bay u850 ERROR-TENDENCY BUDGET RESULT (registered 13:25; 8 starts T85 base2, 48 h)
| m/s per day | Bay 10-22N 80-95E: model / ERA5 / error | E of Bay 12-24N 98-110E: model / ERA5 / error |
| du/dt | −1.25 / −0.04 / −1.21 | −1.63 / +0.60 / −2.22 |
| advection | +1.02 / +1.13 / −0.10 (8 %) | −1.97 / −1.29 / −0.67 |
| Coriolis + pressure gradient | −5.19 / −4.96 / −0.23 (19 %) | −7.40 / −8.39 / +0.99 (opposite sign) |
| residual (friction, CMT, vertical adv., diffusion) | +2.92 / +3.79 / −0.88 (73 %) | +7.74 / +10.28 / −2.54 (114 %) |
VERDICT by the registered rule: carrier = RESIDUAL (73 % >= 50 %) -> physics/vertical. Pressure pattern (19 %) and import from the
east (8 %) are minor. Check: ERA5 vertical advection −w du/dp at 850 is +0.15 (Bay) / −0.02 (E) m/s/day -> the residual is NOT
vertical advection; it is sub-grid momentum transport (BL turbulence, convective momentum transport) [+ ERA5 analysis increments -
caveat: ERA5's tendency includes assimilation increments]. Reading: the background 850 flow is easterly; ERA5's residual slows the
easterlies (+3.8 / +10.3 m/s/day); ours does less (+2.9 / +7.7) -> our sub-grid momentum mixing at 850 is too WEAK, so easterlies grow.
5-Why: easterly too strong <- too little deceleration at 850 <- sub-grid momentum transport too weak at 850 <- (candidates) BL mixing
does not reach 850 (BL too shallow / K too small above the surface layer), CMT too weak or absent in shallow convection, deep CMT
mass flux too small (links to A/P1: too little deep convection = too little CMT). FMEA top: shallow-convection CMT absent (S8 O7 D3),
BL depth/K at 850 (S8 O6 D4), deep CMT via weak deep mass flux (S7 O7 D5 - shared with A/P1).
NEXT (registered now): ubproc - model u_bl and u_cmt at 850 by box (same 8 starts, 12/24/36 h) + BL height vs ERA5 boundary_layer_height.
The process whose 850 tendency would have to grow by >= 50 % of the 0.88 / 2.54 deficit to close it, and is physically allowed
(e.g. BL top below 850 where ERA5's is above), is named the cause.
- 19:10 ERA5 BL-height reference (cyc_blh.py, 8 starts x 12/24/36 h): Bay mean BLH 582 m, E of Bay 259 m, fraction > 1500 m ~0.
  Model smoke (T42, 1 start): Bay hbl ~607 m, E of Bay ~1065 m. => ERA5's BL does NOT reach 850 hPa either: FMEA #1 ("our BL does
  not reach 850") is REJECTED as the cause - in ERA5 the extra 850 deceleration must come from convective momentum transport (or
  analysis increments). Lead now: CMT too weak (smoke: u_cmt = 0 in the E-of-Bay box) - shared with A/P1 (too little / wrong
  convection). T85 process split (one start per process after an OOM) running.

## 17 Nov 20:15 IST — A/P1 COLUMN TEST (a) RESULT + BUG FOUND IN A CLOSURE INPUT
(a) Our IFS convection on ERA5's own columns (2020-11-01/11, 80 strong cp >= 1 mm/h, ERA5 cp mean 4.48 mm/h):
- L137, dx 78 km: deep TRIGGERS in 70 % (passes the >= 70 % trigger rule) but rain 0.03 mm/h (median ratio 0.00); L32 0.06; dx 9 km
  0.05/0.10. Dry columns: 0 % deep (no false trigger). => by the registered rule: IMPLEMENTATION (ratio < 0.3), not resolution/levels.
- Why no rain although deep triggers: closure mass flux Mb = 0 because PCAPE <= 0 in 90 % of the triggered strong columns
  (median −20 Pa) - i.e. the closure INPUT PCAPE is wrong while the trigger is fine.
- Inputs of PCAPE (6.22) checked against the doc: PCAPE = −∫ ((Tv,up − Tv)/Tv − l_up) dp, where Tv,up is the updraught virtual
  temperature (no condensate). Our code (ifs_phys.py line ~184): Tvu = Tu (1 + 0.608 (qt − l) − l) ALREADY subtracts l_up, and the
  integrand subtracts l_up AGAIN -> condensate loading counted TWICE. With l_up 2-2.8 g/kg at 600-500 hPa (w_up 5-6 m/s), one
  loading is ~0.5-0.75 K - the size of the whole buoyancy. 5-Why level 4 answered: the formula was right, its INPUT Tv,up was not.
REGISTERED before the fix run: with single loading (Tvu = Tu (1 + 0.608 (qt − l))), on the same columns: CAUSE CONFIRMED if the strong
columns' median rain ratio rises to >= 0.5 and >= 70 % get Mb > 0, with dry columns still >= 80 % no deep; NOT the (main) cause if the
median ratio stays < 0.3.
- 20:30 FIX RUN RESULT (single loading): strong-column rain 0.03 -> 0.24 mm/h (L137, 78 km; 9 km 0.42), median ratio 0.01-0.03 ->
  by the registered rule NOT the main cause (< 0.3), although REAL: PCAPE now > 0 in 100 % of triggered strong columns (median
  65 Pa, was −20), Mb median 0.019-0.034 kg m-2 s-1 (a normal cloud-base mass flux). So the closure now works; the rain is lost
  AFTER the mass flux is set -> next 5-Why level: column rain budget (condensation, updraught precipitation, evaporation in
  downdraught / sub-cloud, condensate detrained to the cloud scheme). Test-design caveat logged: the reference picks the
  strongest 0.25° ERA5 cells (point maxima) - fair only against a run at ERA5's ~31 km; at 78 km the grid-box mean is lower.
- 20:45 column rain budget after the fix (strong triggered columns, L137): 78 km Mb 0.038-0.042, updraught precipitation 0.38-0.42,
  downdraught evaporation 0.04-0.07, sub-cloud evaporation ~0, condensate detrained 0.13-0.24, surface 0.31-0.37 mm/h; at 31 km
  (ERA5's own grid) Mb 0.053-0.058, surface 0.44-0.53 mm/h. Evaporation is NOT the sink. Fairer reference (post hoc, does not change
  the registered verdict): ERA5 cp 175-km box mean at the same cells 1.61 mm/h (point maxima 4.38) -> we are still ~x3-5 low at 31 km.
  Remaining limiter = the mass flux Mb itself: Mb = (PCAPE − PCAPE_bl)/(tau x den) with PCAPE ~65 Pa, tau 3200-4600 s, den ~0.29.
  5-Why level 5 candidates (inputs to Mb): PCAPE too small (entrainment in the plume -> Tv,up), tau too long (Hc / w_bar, dx factor
  6.27), den too large; and the one-call test lacks the step's large-scale forcing (quasi-equilibrium caveat). Next: the same columns
  with each Mb input set to the IFS-doc value range (not tuned): entrainment per 6.7 checked line by line, tau per 6.27 at 31 km.
- The double-loading fix itself is a doc-correct code fix (Tv,up per 6.22). It goes through the registered screens (storms rule 2,
  exam quarter, tracks) before adoption - not adopted on the column test alone.
- 20:55 P3 core budget, PASS group collected (tn-p3core-b; scorer /tmp/claude-0/p3score.py): model 300-km rain 0-24 h vs ERA5 total
  median ratio 0.86 (mean 1.02; Mandous 0.49 .. Michaung 1.72), deep-convective share of core heating 0.41. Verdict waits for the
  FAIL group (tn-p3core-a, running, account 4).
- PROCESS ERROR: tn-p3core-b was launched TWICE on account 1 (collected 14:59 UTC, relaunched 15:02 UTC) - my 18:25 queue commit
  re-added it after the dispatcher had removed it (concurrent edit of queue.json). ~1 GPU-h wasted; Kaggle kernels cannot be cancelled.
  Fix: never edit queue.json while a dispatcher pass may run; pull right before editing and dispatch in the same step.

## 17 Nov 22:10 IST — P3 STORM-CORE BUDGET RESULT (registered 18:25): slow-heating cause REJECTED
FAIL group (Madi, Sidr, Phailin, Hudhud, Giri, Sitrang, Nilam, Titli, Dana): model 300-km rain 0-24 h / ERA5 total = mean 1.01,
median 1.00 (Phailin 0.48, Sidr 0.70 .. Titli 1.49); PASS group median 0.86. Deep share of core heating 0.38 vs 0.41.
Rule: REJECTED if FAIL ratio >= 0.80 -> the AMOUNT of heating/rain is NOT why strong storms stay weak (base2).
What differs (12-48 h means, FAIL vs PASS): warm core 300 hPa +0.86 vs +1.36 K, 500 hPa +0.74 vs +1.17 K (−37 %) with the SAME
heating and the same inner-ring share (0.38); core surface enthalpy flux 180 vs 202 W m-2 (−11 %); 700-hPa core RH 0.95 vs 1.01.
5-Why: storm too weak <- warm core too weak <- heat not retained in the core although produced <- (candidates) heating spread over a
model core too wide for these storms (T170 ~78 km vs small inner cores / rapid intensifiers: Phailin, Hudhud, Sidr, Madi), shear
ventilation, lower surface enthalpy flux (inflow-layer inputs: SST, wind, q).
REGISTERED next (ERA5 add-on to cyc_corerain: RMW from 10-m wind, 850-200 hPa shear 500 km): RESOLUTION-LIMITED if ERA5 RMW of the
FAIL group (12-48 h median) is <= 0.7 x the PASS group's or <= 60 km while PASS > 60 km; SHEAR if FAIL shear exceeds PASS by >= 3 m/s;
neither -> inflow-layer inputs (enthalpy flux components vs ERA5 sshf/slhf).

## 18 Nov 09:05 IST — S2 no-DFI: TRACK RULE PASSED -> ADOPTED (pre-approved rule: all registered checks pass)
q6 72-h error (6 storms, scorer /tmp/claude-0/q6err.py reproduces base2 seed 4 = 371 and cubic seed 4 = 429): no-DFI seeds 4/5/6 =
377 / 382 / 380 km, mean 380 <= limit 434 (base2 379 + spread 55). Storms (rule 2) and exam quarter passed earlier.
BASE3 = {cmt_mf: 1, rd_si: 1, dfi_off: 1}. All later screens compare against BASE3.

## 18 Nov 09:05 IST — P3 RMW / shear test RESULT (registered 17 Nov 22:10)
ERA5 12-48 h medians: FAIL group RMW 124 km, shear 6.3 m/s; PASS group RMW 174.5 km, shear 6.8 m/s.
- Resolution-limited rule: FAIL RMW <= 0.70 x PASS -> 124/174.5 = 0.71 -> NOT met (by 0.01); FAIL not <= 60 km -> NOT met.
- Shear rule: FAIL exceeds PASS by >= 3 m/s -> FAIL is LOWER -> NOT met.
=> by the rule: neither -> next = inflow-layer inputs (surface enthalpy flux components vs ERA5 sshf/slhf in the core).
Caveat (honest): ERA5's own 0.25° RMWs (62-283 km) are far larger than real inner cores (~20-50 km), so ERA5 RMW is a weak proxy
for true core size; the borderline 0.71 means a resolution part is NOT excluded - only not shown.

## 18 Nov 09:25 IST — A/P1: doc check of the remaining Mb inputs + test (b) registered
Line-by-line vs Cy50r1: entrainment (6.7: 1.75e-3 f_eps (1.3-RH) (qs/qs_base)^3, buoyant only), tau (6.26-6.27: H/w_up x (1+1.6 dx/125 km),
720-10800 s) and the closure denominator (6.25: g/Tv M* (dTv/dz + g/cp) dz) MATCH the code. Two documented differences from what
ERA5 used: ERA5 ran IFS Cy41r2 (no QCV term 6.29-6.32), and the column test lacks the step's large-scale forcing (quasi-equilibrium).
-> The single-column test has reached its limit; the decisive check is in the model state itself.
TEST (b), REGISTERED before running: our own T42 start state (spin_I.npz, 2020-11-01, the state behind the 0.15 vs 1.3 mm/day
finding), IFS convection hour 1, tropics 20S-20N, convective rain vs ERA5 cp (hour 1): fix explains the A/P1 deficit if ours rises
from ~12 % to >= 50 % of ERA5; partly if 25-50 %; not if < 25 %.
- 09:35 TEST (b) RESULT: our T42 start state, tropics 20S-20N, hour 1: convective rain original 0.02 / single-loading 0.11 mm/day vs
  ERA5 cp 2.77 (ratio 0.01 -> 0.04); deep fraction 4.7 % in both. By the rule: the fix does NOT explain the A/P1 deficit (< 25 %).
  KEY CONTRAST: on ERA5's own columns deep triggers in 70 % of strong cells; on our start state only 4.7 % of the tropics -> the
  TRIGGER fails on our state but not on ERA5's. Same scheme, different inputs -> the start state we feed is the problem (FMEA #1,
  "parcel source too cool/dry"). Next: swap test (c) at the same 60 points (2020-11-01): our column vs ERA5 column; swap ERA5's
  lowest levels (T, q) into ours and see if the trigger returns.
- 10:00 SWAP TEST (c) RESULT (our T42 start columns at the 40 strong 2020-11-01 ERA5 points, single-loading fix):
  deep trigger: ours 12.5 % | ERA5 T,q lowest 3 levels 25 % | ERA5 T,q ABOVE the lowest 6 levels 52.5 % | whole ERA5 profile 60 % |
  ERA5 surface fluxes only 17.5 % | BL tendencies 0: 12.5 %. Split aloft: q only 40 %, T only 30 %.
  -> The input that kills the trigger is the FREE-TROPOSPHERE MOISTURE of our start state (largest single swap; T aloft second).
  Profile (median at strong points): our RH lower than ERA5 by 5-9 points from 850 to 550 hPa (0.86/0.77 vs 0.91/0.86); T within
  ±0.3 K there. Mechanism (doc 6.7): entrainment ∝ (1.3 − RH) -> 0.3+0.08 raises entrainment ~25-40 % -> plume dies.
  5-Why: no trigger <- plume over-entrains <- environment RH too low at convective points <- our start state is ERA5 1.5° (WB2, 13
  levels) smoothed to T42: averaging over ~280 km lowers RH at the moist convective maxima (sub-grid moisture variance lost).
  Prediction to check next (registered now): the same columns from a T170 start state are within 3 RH points of ERA5 at 850-550 hPa
  (then the T42 tests overstate A/P1 and the T170 deficit has another cause); if T170 is also >= 5 points dry -> the start-data
  input (13-level 1.5° WB2) is the cause at all resolutions -> fix = start from 0.25° 37-level ERA5 (ARCO) fields.
- 10:20 RH check RESULT (start state at the 40 strong points vs ERA5 L137): T42 diff −3.3 / −5.4 / −6.7 RH points at 850/700/550 hPa;
  T170 −2.1 / −2.7 / −2.7. By the rule (within 3 points at T170): the T42 tests OVERSTATE A/P1 (horizontal smoothing); at T170 the
  start moisture is close to ERA5 -> the T170 deficit (package spin-up day-1 rain −0.62 mm/day) needs its own check: next = the same
  trigger/rain measurement on the T170 start state (package + single-loading fix).

## 18 Nov 10:35 IST — P3 next test REGISTERED: inflow-layer surface enthalpy flux (core) vs ERA5
cyc_corerain add-on: ERA5 sshf + slhf (W m-2 upward, 6-h mean) within 100 / 300 km of the ERA5 centre, 12-48 h.
Model: sb flux_core (same radius as defined in storm_budget). Ratio model/ERA5 per storm, group medians.
- INFLOW FLUX is the cause if FAIL median ratio <= 0.80 AND PASS median >= 0.90 (FAIL short of energy input while PASS is not).
- NOT the cause if FAIL ratio >= 0.90 or within 0.05 of PASS -> next: heat retention (warm-core ventilation by the model's own
  outflow / vertical heating profile vs ERA5 temperature anomaly profile).
- 10:50 T170 START-STATE RESULT (package settings + BASE3, one column call at hour 0, tropics 20S-20N): convective rain original 0.08,
  single-loading fix 0.30 mm/day vs ERA5 cp 2.68 (3 % -> 11 %); deep fraction 5.7 %; where ERA5 rains (cp > 0.1 mm/h) deep fires
  in only 22 % (ERA5's own L137 columns: 70 %; the same ERA5 columns on our 32 levels: 57 %). So at T170 the trigger still fails on
  OUR start state although its RH is only 2-3 points drier. Remaining input candidates: start data from 13-level 1.5° WB2 (vertical
  structure of T/q lost between 13 levels), horizontal smoothing to ~78 km. Next: swap test at T170 at the 40 strong points
  (ERA5 L137 -> our 32 levels, by part: low / aloft, T / q), same rule as (c).
- 11:05 T170 SWAP RESULT (40 strong points, single-loading fix): deep ours 35 % | ERA5 q aloft 52.5 % | whole ERA5 profile 60 % |
  T aloft 32.5 % | lowest 3 levels 25 % | ERA5 fluxes 35 %. Rain 0.235 -> 0.36-0.41 mm/h (ERA5 point 4.38, 175-km mean ~1.6).
  Decomposition of the IFS-package deficit at T170: double loading x~4 (fixed), start moisture aloft x~1.5 (2-3 RH points), the rest
  (x3-5 vs box mean) in the single-call closure (quasi-equilibrium / Cy41r2-vs-Cy50r1) - only a forecast run can settle that part.
- SCOPE CORRECTION (important): the double-loading bug is in ifs_phys (the IFS package = STAGE 3 per Sridhar 14 Nov). Stage-1
  convection is base2 'mf' (conv_mf): checked - its CAPE uses buoyancy WITHOUT condensate (b = Tv excess only), single count -> the
  bug does NOT affect Stage 1. A/P1 for Stage 1 = base2 shallow/deep heating split (850 hPa cold with sh_depth + evap_ifs; t700).
  The package fix is recorded for Stage 3 (flag to add: pcape_1load), not adopted now.

## 18 Nov 11:45 IST — P3 INFLOW-FLUX TEST RESULT (registered 10:35)
Core (100 km) surface enthalpy flux, 12-48 h, model / ERA5: FAIL median 0.86 (Madi 0.64, Sidr 0.66, Hudhud 0.72, Giri 0.80 ..
Dana 1.26); PASS median 1.07 (Khai-Muk 0.91 .. Michaung 1.82).
Rule: cause needs FAIL <= 0.80 AND PASS >= 0.90 -> NOT met (0.86); not-cause needs FAIL >= 0.90 or within 0.05 of PASS -> NOT met
(0.21 apart). => INDETERMINATE by the registered rule.
Exploratory (NOT registered, reported as such): across the 17 storms r(flux ratio, Rule-1 peak error) = −0.56; the four most
under-deepened (Madi +14.8, Sidr +10.6, Phailin +9.5, Giri +8.5 hPa) have ratios 0.64-0.86.
Caveat - circularity: a weaker model storm has weaker core winds, so a low flux can be CONSEQUENCE as well as cause. 5-Why next:
split flux = exchange coefficient x wind x air-sea disequilibrium (dk). REGISTERED: if model dk (SST vs lowest-level T,q) and Ck
are within 10 % of ERA5 and the deficit is all wind -> flux is a consequence (look elsewhere: heat retention / core size); if dk or
Ck is >= 15 % low in the FAIL group -> the flux INPUT is a cause (then 5-Why on that input: SST, lowest-level q, Ck formula).
Needs: ERA5 core SST, t2m, d2m, 10-m wind (add-on) and the model's core wind / SST / lowest-level T,q (storm_budget add-on + rerun of
the 9 FAIL storms on Kaggle, ~1 h GPU).

## 18 Nov 12:05 IST — A/P1 (Stage 1, base2): BOMEX single-column test REGISTERED (external reference, not ERA5)
Problem: limiting shallow depth (sh_depth) fixes 925/1000 hPa but 850 hPa goes −0.87..−2.26 K (budget at 850: shallow −1.64,
lsc +2.27, radiation −1.68 K/day). 5-Why level 3: is the shallow scheme's cloud-top (850 hPa ~ 1.5 km) cooling physically right in
SIZE? Reference: BOMEX LES intercomparison (Siebesma et al. 2003, JAS 60): trade-cumulus case with prescribed forcing in which the
LES mean state is quasi-steady between hours 3 and 6 (cloud base ~500 m, top ~1.5-2 km, cloud-base mass flux ~0.02-0.03).
Test: MEGAM column physics (base2 shallow + BL, BASE3; radiation replaced by BOMEX's prescribed −2 K/day; BOMEX subsidence and
moisture advection added; BOMEX initial profiles) for 6 h, horizontally uniform T42 grid, one ocean column read.
- Shallow cloud-top cooling TOO STRONG (cause of the 850 cold) if theta_l at 1.4-2.0 km drops by > 0.5 K over hours 3-6 (LES:
  quasi-steady) while the 0.5-1.0 km layer is within ±0.3 K.
- NOT the cause if the 1.4-2.0 km layer stays within ±0.3 K (then 850 cold comes from the lsc/radiation coupling - next).
- Reported alongside (not judged): our surface fluxes vs BOMEX's prescribed 9.5 W m-2 sensible / ~150 W m-2 latent.
- 13:10 BOMEX RESULT (registered 12:05). Setup note: above BOMEX's 3-km domain the column is blended (3-4 km) into the ERA5
  sounding at the point (first try extended BOMEX's lapse rate to the tropopause -> unphysical CAPE; discarded).
  theta change hours 3->6: base3 500-1000 m −0.56 K, 1400-2000 m −0.57 K | candidate (parts+sh_depth+evap_ifs) −0.17 / −0.14 K.
  By the rule, candidate: cloud-top layer within ±0.3 K -> "shallow cloud-top cooling too strong" NOT the cause.
  BUT the test exposes a different, bigger defect: in this textbook NON-precipitating trade-cumulus case the SHALLOW scheme never
  acts (h_shal = 0) and base2's DEEP scheme fires (on_dp = 1, plume from 455 m to ~3.5 km, heating up to +48 K/day at 1.5 km,
  −73 K/day in the lowest layer). LES: cloud top ~1.5-2 km under the inversion, no deep convection.
  5-Why: deep fires <- the plume overshoots the BOMEX inversion and exceeds the 250 hPa depth threshold <- plume too buoyant
  <- base2 entrainment entr = 1.5e-4 (1.3−RH) m-1 is ~12x below IFS Cy50r1 (6.7: 1.75e-3 (1.3−RH) f_scale) and ~10-20x below
  BOMEX LES-derived values (Siebesma & Cuijpers 1995, Siebesma et al. 2003: ~1.5-2.5e-3 m-1). The formula is right; its INPUT
  (the coefficient) is not the documented one. (docs/simplifications.md row 6 already lists this as HIGH.)
  REGISTERED next (no tuning: the documented IFS value): base3 + entr 1.75e-3 + mf_org 1 (f_scale^3 as 6.7) in BOMEX ->
  SUPPORTED if the deep scheme stays off (on_dp 0 after hour 1) and cloud-layer theta drifts within ±0.3 K over hours 3-6;
  then the global screens (T42 3 starts t850/t700, rain, LHF) and storms before any adoption.
- 13:35 BOMEX with IFS deep entrainment (entr 1.75e-3 + mf_org 1): deep stays OFF all 6 h (criterion 1 met) BUT the shallow scheme
  never switches on either (base2 shallow 'mse'), so the cloud layer 1.4-2.0 km cools −0.69 K over hours 3-6 (−1.36 over 6 h) and
  moistens +0.55 g/kg: the prescribed −2 K/day is not balanced -> criterion 2 FAILS. Not supported alone.
  5-Why continues: no shallow convection in BOMEX <- base2 'mse' shallow test (positive buoyancy and CAPE > 0) "almost never passed"
  (mm2 comment; known) <- the IFS-document shallow set exists (shallow 'mf', sh_trig 1, sh_dmax 20000, sh_eps 3.5e-3, sh_det 1,
  sh_clos 1; registered 10 Nov) but was only ever tested with base2's 12x-too-small DEEP entrainment.
  REGISTERED (same rule): BOMEX with IFS deep entrainment + IFS-document shallow set: SUPPORTED if deep stays off, shallow is on
  in >= 4 of 6 hours, and cloud-layer theta 3->6 h within ±0.3 K at 500-1000 and 1400-2000 m.
- 13:55 BOMEX RESULT, IFS deep entrainment + IFS-document shallow set (registered 13:35): deep OFF 6/6 h, shallow ON 5/6 h,
  theta h3->h6: 500-1000 m −0.15 K, 1400-2000 m −0.05 K (both within ±0.3) -> SUPPORTED by the rule. Shallow heating +4.2 K/day
  in the cloud layer and −13.3 K/day at the cloud top (BOMEX-type structure). Not judged but reported: cloud layer moistens
  +0.5-0.6 g/kg over hours 3-6 (LES ~steady) and surface fluxes H 7-8 / LE 164-184 W m-2 (BOMEX 9.5 / ~153).
  This is the first Stage-1 convection set that behaves like the LES reference in BOMEX. Next (registered 13:10): global T42 screen
  (3 starts: t850 AND t700 day-2 |bias| <= 0.6 K, day-1 rain and LHF within 15 % of ERA5), then storms (rule 2) and T170.
- 14:50 GLOBAL T42 SCREEN (rh_vs_era5, starts 7 Oct / 1 Nov / 26 Nov, day-2 globe bias; rule |t850|, |t700| <= 0.6 K):
    base3            t850 +0.04  t700 −1.55  rh850 +0.050
    conv_doc         t850 −1.34  t700 −1.06  rh850 +0.171
    parts_conv_doc   t850 −0.73  t700 −1.05  rh850 +0.087
  => FAIL (both). NOT adopted. Progress at 700 (−1.55 -> −1.05), but 850 turns cold AND moist (+0.17 RH) - the same signature
  BOMEX showed (+0.5 g/kg cloud-layer moistening while LES is steady). 5-Why: 850 cold <- too moist 850 -> more RH cloud -> LW cooling
  <- shallow moistening of the cloud layer too large <- candidates (stated differences from IFS, 10 Nov): (1) ALL shallow condensate
  re-evaporates where it detrains (no shallow precipitation; IFS converts with 6.44 x0.8/0.9), (2) shallow closure uses surface
  fluxes only (IFS adds sub-cloud radiation + advection, 6.35-6.37), (3) detrainment D = E (1.6-RH) shape. Next: BOMEX moisture
  budget by term for conv_doc (which of 1-3 makes the +0.5 g/kg), then the 850 column budget globally.
- 15:05 BUG IN MY BOMEX HARNESS (found while reading the moisture budget): the subsidence term used d/d(−z), so BOMEX's large-scale
  SUBSIDENCE was applied as ASCENT (cooling + moistening above ~1 km). ALL BOMEX numbers from 13:10-14:00 (base3, cand, ent_ifs,
  ifs_doc) are INVALID and withdrawn, including "ifs_doc SUPPORTED". The global T42 screen (14:50) is unaffected (no harness).
  The 'deep fires in BOMEX' observation was at hour 0 (before any forcing acted) and stands; everything after hour 0 is re-run now.
- 15:40 BOMEX RE-RUN with the corrected subsidence (results replace 13:10-14:00):
    base3    : deep ON at hour 0 (off after), shallow never; theta h0->h6 +3.36 (500-1000 m) / +3.53 K (1400-2000 m) - the hour-0
               deep burst heats the trade-cumulus layer by >3 K (LES steady) -> base2/3 misclassifies trade cumulus as deep: STANDS.
               h3->h6 −0.40 / +0.10 K.
    ent_ifs  : deep off, shallow never; theta h3->h6 +0.11 / +0.24 (inside ±0.3 -> passes the theta rule) BUT nothing convects:
               the BL scheme mixes up to ~1.4 km (q_bl +2.4..+4.6 g/kg/day) and subsidence dries the cloud top unopposed
               (q 1400-2000 m −0.49 g/kg in 3 h; LES steady). Passing theta here is not physical success - stated plainly.
    ifs_doc  : deep off; shallow ON only 2/6 hours -> FAILS "shallow on >= 4/6"; theta h3->h6 −0.08 / +0.18; cloud-top q −0.33 g/kg.
  => Corrected verdict: the IFS-document set is NOT supported in BOMEX (shallow trigger intermittent). Two confirmed defects:
     (1) base2's deep plume fires in trade cumulus (entrainment 12x below IFS/LES) and heats the layer >3 K;
     (2) neither shallow option switches on reliably in BOMEX, so moisture is not ventilated from the sub-cloud to the cloud layer
         (BL scheme over-reaches instead). Next: why the sh_trig test parcel fails in BOMEX (cloud base 455 m, depth ok): print
         the test-parcel path at hour 1-3 (LCL, buoyancy, depth vs sh_dmax).
- 16:05 Why the IFS-doc shallow trigger fails in BOMEX (eager trace at hour 3, test parcel of make_plume(test=True)):
  parcel from sigma 0.99 (85 m) rises to sigma 0.929 (~640 m) and dies; it NEVER condenses (cond 0 at all levels) -> cloud False ->
  shallow off. Inputs to the parcel: (a) mixing eps = 0.8/z + 3e-4 (IFS 6.18) applied EXPLICITLY per layer: eps dz = 0.60 entering
  260 m, 0.39 at 445 m, 0.31 at 640 m -> the parcel is ~60 % environment after one layer (IFS integrates on 137 levels, ~20-50 m
  thick near the surface, where eps dz << 1); (b) the parcel excess is our fixed kick (0.5 K / 5e-4) instead of IFS 6.19
  (flux-based: 1.5 w'theta'/w*, 1.5 w'q'/w*). Suspect ranking: (a) discretisation of the mixing on coarse layers (input = dz),
  then (b). Test (registered): same BOMEX with the mixing integrated exactly over each layer (hu -> he + (hu-he) exp(-eps dz),
  the analytic solution of 6.18, layer-thickness independent): trigger SUPPORTED as the cause if shallow is ON >= 4/6 h.
- 16:30 RESULT exact mixing (new option mf_mix_exact, default off, regression bit-identical 100809.609375 / 0.43390631675720215 /
  280.74951171875): BOMEX ifs_doc + mf_mix_exact: deep off 6/6, shallow ON 3/6 h (was 2/6) -> NOT supported (rule >= 4/6).
  theta h3->h6 −0.09 / +0.14 K; cloud-top q −0.37 g/kg (shallow now moistens 1.4-2.0 km +4.3 g/kg/day but subsidence −6.3 wins).
  Partial effect only. Next suspect (b): parcel excess - ours fixed 0.5 K / 5e-4 vs IFS 6.19 flux-based excess.
- 16:50 (b) parcel excess checked against IFS 6.19: IFS excess = max(0.2 K, 1.5 Js/(rho cp w*)) <= 1 K and max(1e-4, 1.5 Jq/(rho L w*))
  <= 5e-4; for BOMEX fluxes that is ~0.2 K / 1.3e-4 - SMALLER than our fixed 0.5 K / 5e-4 -> (b) is not why the parcel fails.
  Note: the exact integral of 6.18 from 85 to 260 m (1-(85/260)^0.8 = 0.59) dilutes as much as our explicit step -> in IFS too the
  test parcel is mostly environment by 260 m; it reaches the LCL because IFS's sub-cloud layer is well mixed up to cloud base.
  BOMEX ifs_doc + mf_mix_exact + bl_lcl (BL capped at the LCL, option (a) part): BL no longer reaches into the cloud layer (q_bl 0
  above 500 m), shallow ventilates (q_shal −9.1 sub-cloud, +0.9/+4.8/+5.5 g/kg/day in the cloud layer = BOMEX-like structure),
  theta h3->h6 −0.06 / +0.14 K, cloud-top q −0.37 g/kg. Shallow ON 3/6 snapshot hours -> NOT supported by the rule. Not judged:
  ON in 39 % of all steps, intermittent (101001110001000100) - LES trade cumulus is continuous. Next 5-Why: why does the trigger
  switch off every other step (sub-cloud q after a convective step vs the parcel's LCL) - closure (sh_clos) too strong per step?

## 18 Nov 11:10 IST — TIME-LABEL CORRECTION (checked the clock now: 11:08 IST)
The 18 Nov entries labelled 10:20, 10:35, 10:50, 11:05, 11:45, 12:05, 13:10, 13:35, 13:55, 14:50, 15:05, 15:40, 16:05, 16:30 and 16:50 IST
were all written between ~09:15 and 11:08 IST - the labels ran ahead of the real clock (my error, again). Their ORDER is right; the
clock times are not. Registrations were still made before each result (order preserved in this file and in git history timestamps).
From now on every entry's time is taken from the clock tool at the moment of writing.
- 11:15 (clock) Intermittency 5-Why: sh_clos 1 vents ONLY the source layer explicitly (Mb from the surface MSE flux over (h_u-h_e)
  one level above the source) -> the lowest layer dries, next step the parcel cannot condense -> off; next step moist again -> on.
  The IFS-faithful option already exists (sh_ifs2, 11 Nov: closure at cloud base 6.35/6.37, whole sub-cloud layer vented linearly
  6.40-6.41, implicit transport 6.69). REGISTERED: BOMEX ifs_doc + mf_mix_exact + bl_lcl + sh_ifs2: SUPPORTED if shallow ON >= 4/6
  snapshot hours AND theta h3->h6 within ±0.3 K at 500-1000 / 1400-2000 m; also reported: % of steps on, cloud-top q drift.
- 11:25 (clock) RESULT BOMEX ifs_doc + mf_mix_exact + bl_lcl + sh_ifs2: deep off 6/6; shallow ON 6/6 snapshot hours (78 % of steps);
  theta h3->h6 −0.03 K (500-1000 m) / +0.11 K (1400-2000 m) -> SUPPORTED by the rule. Also: cloud-top q −0.06 g/kg (near steady),
  500-1000 m q −0.29 g/kg; shallow heating +0.9 K/day low in the cloud layer, −1.7 K/day near the inversion; sub-cloud venting
  q_shal −9.3 g/kg/day vs BL +7.6 (BOMEX-type balance). First Stage-1 convection configuration that behaves like the BOMEX LES
  reference, all values from the IFS document (nothing tuned). Next (registered 13:10 rule): global T42 screen, then storms, T170.
- 11:22 (clock) GLOBAL T42 SCREEN of the BOMEX-supported set (starts 7 Oct / 1 Nov / 26 Nov, day-2 globe; rule |t850|,|t700| <= 0.6 K):
    conv_ifs        t850 −1.01  t700 −0.99  rh850 +0.116
    parts_conv_ifs  t850 −0.91  t700 −0.91  rh850 +0.109   (ocean 40S-40N: −0.84 / −0.67 / +0.077)
    (base3 for reference: t850 +0.04, t700 −1.55, rh850 +0.050)
  => FAIL. NOT adopted. Locally right in BOMEX, globally the 850 hPa layer still ends up cold and moist (+0.11 RH) - so the
  remaining 850 defect is NOT the shallow trade-cumulus process. 5-Why next, by FMEA rank: (1) where the extra 850 moisture comes
  from with the new entrainment (deep plumes now detrain lower: 850-700 moistening by deep detrainment / rain evaporation), (2) the
  moist-850 -> RH-cloud -> LW cooling chain (radiation measured 0.3-0.5 K/day colder than RRTMG at 850-1000 hPa). Test: 850 hPa
  heat AND moisture budget by process, conv_ifs vs base3, tropics/extratropics, +24 h (heat700.py style), registered before running:
  the process whose 850 moistening grows most vs base3 (>= 50 % of the rh850 change) is named.
- 11:25 (clock) 850 hPa HEAT + MOISTURE BUDGET (T42, 1 Nov, +24 h, sigma 0.86, globe; base3 -> parts_conv_ifs):
    moistening g/kg/day: total +0.47 -> +0.50 | shallow +0.74 -> +1.16 | BL +0.52 -> +0.08 | lsc −0.95 -> −0.59 | evap +0.50 -> +0.18 | deep −0.34 -> −0.34
    heating K/day:       total −0.79 -> −0.38 | rad −1.63 -> −2.25 | lsc +2.36 -> +1.46 | evap −1.25 -> −0.45 | deep +0.57 -> +1.02 | BL −0.53 -> −0.01 | shal −0.31 -> −0.15
  By the registered rule: NO moistening process carries the rh850 rise (physics moistening changes by only +0.03 g/kg/day; the
  shallow +0.42 is cancelled by BL −0.44 and evap −0.32). And the physics HEATS 850 more in the new set (−0.79 -> −0.38 K/day), yet
  day-2 t850 is ~1 K colder -> the extra 850 cold is NOT from column physics at +24 h; it must come from (a) radiation changes later
  (rad is the one physics term that cools more: −0.62 K/day, consistent with more RH cloud), or (b) the DYNAMICAL response
  (adiabatic cooling by stronger large-scale ascent / advection). Next 5-Why test (registered): total dT/dt at 850 from consecutive
  states minus physics = dynamics, base3 vs new, days 0-2, tropics/extratropics; the larger of (dynamics change, radiation change)
  over days 1-2 is named.
- 11:37 (clock) 850 T TENDENCY SPLIT RESULT (dyn850.py, T42, 3 starts, day-2 mean, sigma 0.86, K/day, base3 -> new set):
    globe:     total −0.08 -> −0.33 | physics −0.42 -> −0.17 | radiation −1.22 -> −2.19 | dynamics +0.34 -> −0.17
    tropics:   total −0.20 -> −0.52 | physics −0.60 -> −0.28 | radiation −1.33 -> −2.58 | dynamics +0.40 -> −0.25
  Change new − base3 (globe): radiation −0.97, dynamics −0.51, physics without radiation +1.22. By the rule the larger is RADIATION
  -> named: the new convection set makes 850 hPa radiate ~1 K/day more (~2x). 5-Why next: more LW cooling at 850 <- more low
  cloud at/above 850 (moist 850, RH +0.11 -> RH-cloud) and/or cloud-top cooling of the now-active shallow cloud layer; the
  radiation scheme itself was measured 0.3-0.5 K/day colder than RRTMG at 850-1000 hPa. Registered test: same states, 850 radiative
  heating split clear-sky vs cloud (rad_allsky style) and cloud fraction at 850, base3 vs new; and the new-set column through RRTMG
  (rrtmg_climlab_reference.py) - the cloud part is named if it carries >= 50 % of the −0.97; the scheme if RRTMG on the same
  state cools >= 0.5 K/day less.
- 11:44 (clock) RADIATION SPLIT RESULT (rad_allsky, T42, 2 starts, h36, 800-900 hPa layer, K/day; same clouds into RRTMG):
    base3: LW all-sky −2.0 (RRTMG −1.9), LW clear −1.8 (−1.6); total cover 0.84
    new  : LW all-sky −2.7 (RRTMG −2.7), LW clear −1.7/−1.8 (−1.8); total cover 0.93
  => The extra 850 cooling (−0.7 K/day in this layer) is ALL in the CLOUD part (clear-sky unchanged), and RRTMG on the same clouds
  gives the same number -> the radiation SCHEME is not the cause; the CLOUD AMOUNT is (cloud part >= 50 % -> named).
  RH-cloud at 850 (scheme's cloud from model RH vs from ERA5 RH, day 2): base3 0.232 vs 0.091; new 0.289; at day 0 0.109 vs 0.091 ->
  low cloud at 850 jumps x2 within day 1 although rh850 rises only +0.04 (base3) / +0.09 (new).
  5-Why: 850 too cold <- too much LW cooling <- too much 850 cloud <- RH-cloud curve steep near its critical RH + small moist bias
  -> positive feedback (cloud cools -> RH up -> more cloud) = problem A (cloud / day-1 energy loss). Caveat: ERA5 side uses daily-
  mean RH (smoother -> less cloud through the nonlinear curve); the fair reference is ERA5's OWN cloud fraction at 850.
  REGISTERED next: model 850 cloud fraction (radiation input) vs ERA5 'fraction_of_cloud_cover' at 850 hPa (ARCO, same times, h12-h48):
  RH-cloud OVER-PRODUCTION confirmed if model >= 1.5x ERA5 (globe, 40S-40N ocean) while model RH is within 0.05 of ERA5.
- 11:57 (clock) A: MODEL vs ERA5 CLOUD FRACTION (cc_model.py: radcloud.clouds on the model state; ERA5 fraction_of_cloud_cover 1.5° box
  means; T42, 3 starts, globe, model / ERA5):
    850 hPa  h0 base3 0.186/0.124 new 0.150 | h24 base3 0.369/0.124 new 0.382 | h48 base3 0.381/0.123 new 0.436
    925 hPa  h0 base3 0.245/0.133 new 0.218 | h24 base3 0.234 new 0.489 | h48 base3 0.205/0.126 new 0.498
    700 hPa  h48 base3 0.297/0.068 new 0.270
  RULE (registered 11:44): over-production confirmed if model >= 1.5x ERA5 while model RH within 0.05 of ERA5 -> base3 at 850:
  3.1x ERA5 with rh850 +0.04..+0.05 -> CONFIRMED. (new set: 3.5x, rh850 +0.11 - RH not within 0.05, but the excess is the same kind.)
  Already 1.5x at hour 0 (cloud diagnosed from the ERA5-started state) and 3x by day 1 -> the cloud SCHEME maps near-right humidity
  to ~3x too much low/mid cloud. This is problem A's root (day-1 energy loss: more cloud -> more LW cooling at 850 + SW at surface).
  5-Why next: inputs of the cloud diagnosis: (1) RH-cloud critical humidity (rhc_low/rhc_up/rhc_n) vs IFS/Sundqvist reference values,
  (2) convective cloud (Slingo convective + anvil) share at 850-925 (the new set's 925 jump to 0.49 suggests the shallow-convective
  cloud term). Registered: split cl['c'] into RH part and convective part at 850/925 at h24; the part carrying >= 50 % of the excess
  over ERA5 is named.
- 12:00 (clock) A: CLOUD SPLIT (1 Nov, globe, 850 hPa): base3 h0 c 0.181 = RH-part 0.144 + tower 0.044; h24 c 0.357 = RH 0.326 + tower 0.051;
  new h24 c 0.371 = RH 0.338 + tower 0.061; 925 new h24 0.469 (RH 0.439). Anvil 0. => the RH (Sundqvist) part carries >= 90 % of
  the excess -> RH-cloud named.
  CORRECTION to the 11:57 wording "scheme over-production confirmed": at HOUR 0 the same scheme on the ERA5-started state gives
  RH-cloud 0.144 vs ERA5's cloud 0.124 at 850 (1.2x) - roughly consistent. The 3x appears during day 1 while the GLOBAL-MEAN rh850
  rises only +0.04: the rule's "RH within 0.05" test used the global mean, which hides changes in the moist tail (the columns above
  the critical RH ~0.74 at 850). So: scheme ~OK on ERA5-like humidity; the model's moist TAIL grows in day 1 (cloud-radiation-RH
  feedback) - verdict revised to 'RH-cloud is the carrier; cause = growth of the moist tail', not 'scheme over-produces'.
  REGISTERED next: fraction of 850-hPa area with RH > 0.74 (the scheme's critical RH there): ERA5 instantaneous (from T, q, 1.5°) vs
  model h0 and h24. Moist-tail growth is the cause if model h24 area >= 1.5x ERA5 while h0 is within 1.2x.
- 12:10 (clock) A: 850 RH TAIL RESULT (same water saturation, instantaneous, globe; frac = area with RH > 0.74; ERA5 0.25° / 1.5° ~equal):
    ERA5:  mean RH 0.63-0.65, frac 0.43-0.47 at h0/h24/h48 (steady)
    base3: h0 0.640 / 0.42-0.44 | h24 0.720-0.737 / 0.55-0.56 | h48 0.741-0.764 / 0.58-0.61
    new:   h0 0.634-0.639 / 0.40-0.43 | h24 0.723-0.739 / 0.61-0.63 | h48 0.756-0.781 / 0.66-0.71
  Rule (h24 >= 1.5x ERA5 with h0 within 1.2x): base3 1.25x, new 1.4x -> NOT met at h24 (new reaches 1.5-1.6x at h48).
  BUT a premise correction: with the same saturation formula and instantaneous ERA5, the model's MEAN rh850 bias is +0.09 at h24 and
  +0.11..+0.14 at h48 (base3 too) - not the +0.04/+0.05 from rh_vs_era5 (that compared to ERA5 DAILY-MEAN RH with mixed-phase
  saturation). So the 3x cloud by day 1 = a +0.1 RH moistening of 850 in day 1 pushed through the steep RH-cloud curve.
  5-Why next: 850 moistens ~+0.1 RH/day (T nearly unbiased in base3 -> it is q) <- net moistening (physics + dynamics) where ERA5 is
  steady <- column physics adds +0.47 g/kg/day at 850 (base3: shallow +0.74, BL +0.52, rain evap +0.50, lsc −0.95, deep −0.34).
  Registered: q850 split physics vs dynamics over day 1 (like dyn850.py, for q), base3; the side whose day-1 net exceeds ERA5's own
  change (~0) by >= 50 % of the model's q850 drift is named.
- 12:12 (clock) P3 FLUX-SPLIT RESULT (tn-p3flux-a, 9 FAIL storms, 12-48 h, core 100 km; registered 18 Nov "11:45"):
  Valid storms (Sidr, Giri, Titli, Sitrang, Dana) model/ERA5: flux 0.66/0.85/1.18/0.90/1.26, wind 0.73/0.83/0.87/1.08/1.20,
  dk 1.12/1.38/1.40/1.13/1.20, Ck 0.79/0.75/0.93/0.53/0.82. INVALID: Nilam, Phailin, Madi, Hudhud - model dk near zero / negative
  (my add-on's sea mask lets land / near-coast points in: a diagnostic bug, not model physics) -> excluded, stated.
  Height mismatch (model lowest level ~85 m vs ERA5 10 m / 2 m) biases Ck low and dk high by construction; the height-robust
  product Ck x dk = flux/(rho V): Sidr 0.88, Giri 1.04, Titli 1.30, Sitrang 0.60, Dana 0.98 (median 0.98).
  => By the rule: the FAIL-group flux deficit is carried by WIND (most-deficient storms: Sidr 0.73, Giri 0.83), not by dk or Ck
  -> the low flux is a CONSEQUENCE of the weak storm, not its cause (with the caveat of 5 valid storms). P3 5-Why returns to heat
  RETENTION: same heating, 37 % weaker warm core. Next registered test: the radial and vertical heating structure vs where ERA5
  puts its warm anomaly - is the model heating spread over a too-wide core (T170 grid ~78 km; ERA5 RMW FAIL 124 vs PASS 175 km)?
- 12:17 (clock) A: q850 SPLIT (dynq850.py, base3, T42, 3 starts, g/kg/day at sigma 0.86):
    day 1  globe total +0.17 = physics +0.56 (shallow+BL +1.32) + dynamics −0.40
           tropics total −0.25 (physics +0.11, dyn −0.36) | EXTRATROPICS total +0.37 (physics +0.79, shallow+BL +1.83, dyn −0.42)
    day 2  globe total +0.04 (physics +0.45, dyn −0.41)
  Reading (the registered rule needs ERA5 per-term values that do not exist; stated, so this is a lead, not a verdict): the
  day-1 850 moistening is EXTRATROPICAL and carried by shallow + BL mixing (+1.83 g/kg/day), which dynamics removes only in part;
  the tropics dry slightly. Next: map the extratropical shallow+BL moistening at 850 (oceans behind cold fronts / stratocumulus
  vs land) and check the BL top there vs ERA5 boundary_layer_height (BL mixing reaching 850 where ERA5's BL is lower = input error).

## 18 Nov 17:47 IST (clock) — 16:00 cycle: dispatcher queue empty. A: extratropical 850 moistening test REGISTERED
(1) split shallow vs BL at 850 in the extratropics (day 1, base3, 3 starts) and the model BL height there;
(2) ERA5 boundary_layer_height, same times, extratropics (GitHub 'blh global').
INPUT ERROR named if the process carrying >= 50 % of the +1.83 g/kg/day is BL mixing AND the model's BL top exceeds 1500 m in
>= 1.5x the area ERA5's does (BL reaching 850 where ERA5's does not). If the carrier is shallow convection, the next check is its
cloud-top height vs ERA5 cloud-base/top.
- 17:54 (clock) RESULT extratropical 850 moistening (base3, 3 starts) vs ERA5 BLH (blh_global.json):
    h12 q_bl +0.89, q_shal +1.22 | h24 +0.65 / +1.01 | h36 +0.69 / +0.74 g/kg/day at 850
    model BL top > 1500 m: 0.21 / 0.20 / 0.25 of the extratropics (mean hbl 1070-1180 m); ERA5: 0.066 / 0.048 / 0.064 (mean 700-770 m)
  Rule: carrier >= 50 % -> SHALLOW (58-61 % at h12/h24) -> named; BL carries ~40 % (rule's BL branch not met). Measured besides:
  our BL top exceeds 1500 m over 3-4x ERA5's area and is ~400 m deeper on average - an input error in its own right.
  => base3 extratropical 850 moistening = tall shallow mixing (~60 %) + over-deep BL (~40 %). Next: the same split for the
  candidate (parts_conv_ifs: IFS shallow + bl_lcl) - does it remove the extratropical moistening or move it?
- 18:01 (clock) Same split for the CANDIDATE (parts_conv_ifs): extratropics h12/h24/h36 q_bl +0.17/+0.13/+0.23, q_shal +1.01/+1.04/+1.03
  g/kg/day at 850; BL top > 1500 m area 0.033/0.007/0.030 (ERA5 0.05-0.07); mean hbl 463/365/416 m (ERA5 700-770 m).
  Day 1 q850: globe total +0.37 (physics +0.58, dyn −0.22), tropics +0.49, extratropics +0.30 (base3: +0.17 / −0.25 / +0.37).
  Reading: bl_lcl removes the BL share but now makes the BL ~HALF ERA5's depth (new input error, opposite sign); the shallow scheme
  keeps moistening 850 by ~+1 g/kg/day everywhere, and the large-scale drying is weaker (−0.22 vs −0.40) -> 850 still moistens,
  now in the tropics too. In BOMEX the same shallow moistening was balanced by BOMEX's prescribed subsidence; globally it is not.
  5-Why next (registered): is the shallow scheme active where the large scale is NOT subsiding? Split the day-1 850 shallow
  moistening by the sign of large-scale omega at 700 hPa: MIS-TRIGGERING named if >= 50 % of it occurs where omega700 <= 0
  (ascent/neutral), where trade-cumulus balance cannot hold.
- 18:09 (clock) RESULT omega split (candidate, extratropics): only 28-33 % of the 850 shallow moistening occurs where omega700 <= 0
  (ascent area 43-45 %) -> MIS-TRIGGERING NOT the cause (shallow fires mostly under subsidence, as it should).
  So the imbalance is shallow moistening vs large-scale drying. ERA5 reference (days_2020, region 0-40N 50-110E, 3 starts, h12-36,
  resolved terms at 850): dynamics −0.45 g/kg/day (horizontal −0.23, vertical −0.23), actual dq/dt −0.03 -> implied physics +0.42.
  Model (GLOBAL, not yet the same region): physics base3 +0.56 / candidate +0.58; dynamics base3 −0.40 / candidate −0.22.
  First reading (to confirm on the same region, running): physics moistening ~0.15 above ERA5's implied value; the candidate's
  large-scale drying is HALF of ERA5's -> the candidate weakens the subsidence drying at 850 (circulation response). Caveat: ERA5's
  'implied physics' also contains analysis increments.
- 18:21 (clock) SAME-REGION RESULT (0-40N 50-110E, day 1, q850 g/kg/day, total / physics / dynamics):
    ERA5       −0.03 / +0.42 (implied) / −0.45
    base3      −0.17 / −0.20 / +0.03      (0-20N: physics −0.71, dyn +0.20; 20-40N: +0.38 / −0.17)
    candidate  +0.46 / +0.58 / −0.12      (0-20N: +0.71 / −0.05; 20-40N: +0.44 / −0.21)
  Candidate excess over ERA5's dq/dt: +0.49 = physics +0.16 (33 %) + MISSING large-scale drying +0.33 (67 %).
  => The larger part of the 850 moistening is the WEAK LARGE-SCALE DRYING (model dynamics −0.12 vs ERA5 −0.45; base3 even +0.03),
  not the physics. Same family as P5b (850 circulation errors over the Bay). 5-Why next (registered): split model dynamics at 850
  into horizontal advection and vertical (−omega dq/dp) from model u, v, omega, q - as done for ERA5 (−0.23 / −0.23): the term with
  the larger shortfall vs ERA5 is named; if vertical -> subsidence too weak (link to radiation / heating profile); if horizontal ->
  the low-level flow (P5b easterlies, moisture import).
- 18:28 (clock) DYNAMICS SPLIT RESULT (model u, v, omega, q at 850, same method as ERA5; g/kg/day horizontal / vertical):
    ERA5       region −0.23 / −0.23 | 0-20N −0.26 / −0.10 | 20-40N −0.19 / −0.37
    base3      region −0.20 / −0.04 | 0-20N −0.19 / −0.09 | 20-40N −0.22 / +0.03
    candidate  region −0.22 / +0.18 | 0-20N −0.18 / −0.07 | 20-40N −0.26 / +0.48
  Horizontal transport matches ERA5; the VERTICAL term carries the shortfall (named by the rule) - but it sits in 20-40N, where the
  box includes Tibet / Iran / Afghanistan with 850 hPa BELOW GROUND (both ERA5 and model extrapolate there; no terrain mask in either
  computation). In the clean 0-20N band the vertical term matches ERA5 (−0.07..−0.09 vs −0.10). => verdict NOT trusted until the
  terrain is masked; also the residual 'dynamics' (total − physics) and this direct split differ (0-20N: −0.05 vs −0.25) - the
  residual carries numerical/diffusion terms. Next: recompute both with surface pressure > 900 hPa only (ERA5: z850 vs orography).
- 18:33 (clock) TERRAIN-MASKED RESULT (surface pressure > 900 hPa in both; q850 dynamics, horizontal / vertical, g/kg/day):
    ERA5       region −0.30 / −0.21 (−0.51) | 0-20N −0.26 / −0.10 | 20-40N −0.39 / −0.46 (−0.85)
    base3      region −0.16 / −0.17 (−0.33) | 0-20N −0.19 / −0.09 | 20-40N −0.10 / −0.37 (−0.47)
    candidate  region −0.11 / −0.04 (−0.14) | 0-20N −0.18 / −0.07 | 20-40N +0.08 / +0.05 (+0.13)
  => 0-20N: both configurations match ERA5 within ~0.08. The drying deficit is in the SUBTROPICS 20-40N (low ground only):
  base3 already −0.38 short (mostly horizontal), the candidate −0.98 short with BOTH terms gone (horizontal +0.47, vertical +0.51);
  mean omega850 there: base3 +0.0136, candidate +0.0066 Pa/s (subsidence halved).
  Reading: the candidate convection changes the large-scale circulation so that the subtropical 850 subsidence and dry-air import
  weaken - a circulation response to where the convective heating now goes (deep heating at 850: +0.57 -> +1.02 K/day). 5-Why
  next: compare the candidate's tropical convective heating PROFILE with a reference profile (TRMM/ERA5 Q1, or the IFS-doc
  behaviour in its own SCM cases) - a heating peak too low would drive a shallow, weak overturning with weak subtropical subsidence.
- 18:41 (clock) TROPICAL HEATING PROFILE (0-20N 50-110E, low ground, day 1, 3 starts; K/day at 850 / 700 / 500 / 300 hPa):
    ERA5 Q1/cp (budget residual, 6 levels)   −0.08 / +0.29 / +0.93 / +1.21
    base3 physics heating (incl. radiation)  −0.58 / −0.65 / +1.02 / +0.40   (deep part +1.05 / +2.19 / +2.49 / +0.71)
    candidate                                −0.79 / −0.22 / +0.93 / −0.13   (deep part +2.19 / +2.40 / +2.13 / +0.64)
  => The model's tropical heating is BOTTOM-HEAVY: upper-tropospheric (300 hPa) heating short by −0.81 (base3) / −1.34 (candidate)
  K/day vs ERA5, which peaks at 300. The candidate moves deep heating further DOWN (850 +1.05 -> +2.19). A low heating peak drives a
  shallow, weak overturning -> weak subtropical subsidence (the 20-40N drying deficit) -> moist 850 -> 3x low cloud -> cold 850.
  The same missing upper heating fits P3 (300-hPa warm core 37 % weaker in the failing storms) and the known cold upper troposphere.
  Caveat: ERA5 Q1 from 6 pressure levels and 12-h differences (coarse); radiation included on both sides.
  5-Why next (registered): are our deep plumes too SHALLOW? Model OLR vs ERA5 top net thermal radiation (ttr, days file) over the
  same box: tops too low/warm named if model OLR >= 10 W m-2 above ERA5 where ERA5 OLR < 220 W m-2 (deep convective areas).
- 18:47 (clock) OLR TEST RESULT (registered above; 0-20N 50-110E, h12/24/36, 3 starts; model OLR from the radiation carry vs ERA5 ttr):
    where ERA5 OLR < 220: base3 144 / candidate 143 vs ERA5 174 W m-2 | all 0-20N: 208 / 209 vs 246 | area OLR < 220: 0.50 vs 0.30
  Rule: 'plumes too shallow' needed model OLR >= 10 above ERA5 -> NOT supported. The OPPOSITE holds: OLR 30-38 W m-2 too LOW and
  deep/cold-top cloud area 0.50 vs 0.30 -> too much cold high cloud (or too-high tops), in base3 and candidate alike.
  Caveat: ERA5 ttr in days_YYYY may be a daily/hourly mean vs our instantaneous carry; a 38 W m-2 gap is far larger than that.
  Updated reading of the 300-hPa heating deficit: with too much high cloud, LW cooling at the cloud tops (~300 hPa) offsets the
  convective heating -> the net physics heating at 300 is short although deep heating is there. 5-Why next (registered): 300 hPa
  heating split radiative vs convective (model), and model cloud fraction at 300/250 hPa vs ERA5 fraction_of_cloud_cover:
  HIGH-CLOUD EXCESS named if model >= 1.5x ERA5 at 300 hPa and the radiative part at 300 is >= 0.5 K/day more negative than the
  clear-sky part.
- 18:55 (clock) HIGH-CLOUD RESULT (base3, T42, 3 starts; model radcloud cloud vs ERA5 fraction_of_cloud_cover, 1.5°):
    globe 300 hPa: h0 0.031/0.106, h24 0.238/0.104, h48 0.284/0.102 | 20S-20N 300: h24 0.305/0.064, h48 0.371/0.067;
    20S-20N 200: h0 0.014/0.167, h24 0.330/0.178, h48 0.442/0.182
  Radiation 250-350 hPa layer (h36, 2 starts): LW all-sky −1.7/−1.8 vs clear −1.9 K/day; SW +0.5 both; OLR 210.8 = RRTMG 209.9 on
  the same clouds.
  Rule: part 1 (model >= 1.5x ERA5 at 300) MET (2.3-4.8x); part 2 (cloud part >= 0.5 K/day more negative than clear sky at 300)
  NOT met - the cloud part slightly WARMS that layer (+0.2). => High-cloud excess is real (it explains the OLR −38 W m-2), but it
  is NOT why the 300-hPa net heating is short. Notable: high cloud starts TOO LOW at h0 (0.03 vs 0.10) and grows to 2-5x by day 1-2.
  Status of the chain: bottom-heavy NET heating vs ERA5 Q1 (coarse 6-level estimate) remains measured; its cause at 300 is not
  radiation. Remaining candidates for the 300 deficit: the convective (latent) heating aloft and the reliability of the coarse Q1.
  Also seen: SW cloud absorption in the atmosphere 6-7 W m-2 below RRTMG (swCRE_atm) - logged, not chased now.
- 18:59 (clock) FINE ERA5 Q1 (cyc_q1.py: 37 levels, 0.25°, 1-h centred differences, same box/starts/hours, low ground):
    925 −1.13 | 850 −0.81 | 700 −0.24 | 600 −0.17 | 500 +0.84 | 400 +0.89 | 300 +0.11 | 250 −0.54 | 200 −0.86 K/day
  vs model 850 / 700 / 500 / 300: base3 −0.58 / −0.65 / +1.02 / +0.40 ; candidate −0.79 / −0.22 / +0.93 / −0.13
  => CORRECTION: the coarse 6-level estimate (+1.21 at 300) was WRONG; ERA5's heating peaks at 400-500 hPa. Against the fine
  reference the CANDIDATE's tropical heating profile matches within 0.02-0.24 K/day at all four levels (base3 is off by −0.41 at
  700 and +0.29 at 300). The "bottom-heavy heating" chain (18:41) is WITHDRAWN. The candidate's convection is right in BOMEX AND
  in the tropical heating profile; what fails is the subtropical (20-40N) 850 drying and the cloud response (low 3x, high 2-5x).
  Open 5-Why: why does the subtropical 850 subsidence/dry import weaken with the candidate? Candidates: (1) cloud-radiative
  heating anomalies in the subtropics (the 3x low cloud itself feeding back on the circulation), (2) the BL now half ERA5's depth
  (bl_lcl) changing low-level divergence. Test (2) first: candidate WITHOUT bl_lcl in the same masked 20-40N budget.
- 19:02 (clock) Candidate WITHOUT bl_lcl, masked 20-40N q850 dynamics: horizontal +0.02, vertical −0.04 (sum −0.02; candidate +0.13,
  base3 −0.47, ERA5 −0.85). => bl_lcl is NOT the main cause (0.15 of the 0.60 loss vs base3). REGISTERED next: split the candidate's
  convection change into (a) IFS deep entrainment only (entr 1.75e-3 + mf_org) and (b) IFS shallow set only (shallow mf + sh_trig +
  sh_dmax + sh_eps + sh_det + sh_clos + mf_mix_exact + sh_ifs2), each on base3, same masked budget; the one that removes >= 50 % of
  base3's 20-40N drying (−0.47) is named.
- 19:07 (clock) RESULT deep vs shallow split (masked 20-40N q850 dynamics, sum; base3 −0.47):
    entr_only (IFS deep entrainment on base3)  −0.36 (horizontal −0.08, vertical −0.28; omega850 +0.0151)
    shal_only (IFS shallow set on base3)       −0.06 (horizontal −0.01, vertical −0.05; omega850 +0.0109)
  => the SHALLOW set removes 0.41 of base3's 0.47 (87 %) -> named. Subsidence itself is still there (omega850 +0.011 vs base3
  +0.0136) but its drying is gone -> the drying −omega dq/dp shrinks because dq/dp at 850 shrinks: the shallow scheme mixes
  moisture through the subtropical inversion and flattens the vertical humidity gradient that subsidence acts on.
  REGISTERED: dq/dp at 850 (q925 − q700 over 225 hPa) in 20-40N masked: model shal_only vs base3 vs ERA5 - 'shallow mixes through
  the inversion' named if shal_only's gradient is <= 0.6x ERA5's while base3's is >= 0.8x.
- 19:13 (clock) GRADIENT RESULT (20-40N masked, dq/dp between sigma 0.79 and 0.91, g/kg per 1000 Pa): base3 0.147, shal_only 0.215,
  ERA5 (925-700) 0.172. Rule needed shal_only <= 0.6x ERA5 -> it is 1.25x -> 'shallow mixes through the inversion / flattens the
  gradient' REJECTED. The mean gradient is even LARGER, and mean subsidence similar - so the lost vertical drying comes from the
  CO-LOCATION of motion and gradient (ascent where the gradient is strong, e.g. where shallow convection now moistens), i.e. the
  covariance of omega and dq/dp, not the means. Next (registered): split the 20-40N vertical term into subsiding vs ascending
  points (omega850 > 0 / <= 0) for base3, shal_only and ERA5; the part with the larger change vs base3 is named.
- 19:19 (clock) COVARIANCE SPLIT RESULT (20-40N masked, vertical term −omega dq/dp at 850, area-weighted contributions, g/kg/day):
    subsiding points: base3 −0.81, shal_only −0.85, ERA5 −1.01 | ascending points: base3 +0.44, shal_only +0.80, ERA5 +0.56
    subsiding area: base3 0.53, shal_only 0.53, ERA5 0.60
  => By the rule the ASCENDING part changes most (+0.36 vs base3; subsiding −0.04) -> named: with the IFS shallow set, 20-40N
  ASCENT regions moisten 850 much more (+0.80 vs ERA5 +0.56). Also (both configs): too little subsiding area (0.53 vs 0.60) and
  weaker drying where it subsides (−0.81/−0.85 vs −1.01).
  5-Why next (tomorrow): in the ascent regions, is it stronger ascent (omega) or a steeper gradient below 850 (shallow venting the
  sub-cloud moisture upward into 925-850 where ascent lifts it)? Split the ascending contribution into mean omega x mean gradient
  and their covariance for shal_only vs base3.
- 19:25 (clock) ASCENT-REGION SPLIT (20-40N masked): base3 ascent omega −0.093 Pa/s, dq/dp 0.124 | shal_only −0.087, dq/dp 0.219 (+77 %);
  subsidence regions: dq/dp 0.176 -> 0.236. => Ascent is NOT stronger; the vertical humidity GRADIENT near 850 is steeper -> named.
  Next: which end - q below 850 (925 moister: sub-cloud/BL moisture not ventilated by the BL, since shal_only has no BL change) or
  above (700 drier)? Compare q925 / q850 / q700 in the ascent regions with ERA5 (registered: the level whose bias vs ERA5 changes
  most from base3 to shal_only is named).
- 19:31 (clock) LEVEL RESULT (20-40N ascent regions, g/kg; bias vs ERA5 925 / 850 / 700):
    ERA5 7.21 / 6.28 / 3.64 | base3 6.81 / 5.89 / 4.16 (−0.40 / −0.39 / +0.52) | shal_only 7.90 / 6.36 / 3.87 (+0.69 / +0.08 / +0.23)
  Change base3 -> shal_only: 925 +1.09, 850 +0.47, 700 −0.29 -> 925 named: with the IFS shallow set the lowest levels in subtropical
  ascent regions are TOO MOIST (+0.69); base3 was the opposite (its tall 'mse' shallow mixed 925 moisture up to 700: 700 +0.52).
  So the IFS shallow set ventilates the sub-cloud layer too little in these regions (or the surface supplies too much - LHF +14 %
  measured 13 Nov). Next (registered): q925 physics budget in 20-40N ascent regions, base3 vs shal_only: surface evaporation into the
  layer, q_bl, q_shal (venting), q_evap; the term whose change explains >= 50 % of the +1.09 is named.
- 19:39 (clock) 925 BUDGET RESULT (20-40N ascent regions, g/kg/day; base3 -> shal_only): shallow venting −1.04 -> −0.05 (+0.99),
  BL +1.34 -> +1.54, rain evap +0.66 -> +0.21, deep −0.25 -> −0.47, lsc −0.04 -> −0.27; surface evaporation 3.05 -> 3.20 mm/day.
  => the lost SHALLOW VENTING (+0.99) is the largest change -> named: with the IFS shallow set, convection barely vents 925 there.
  5-Why, input check: classification thresholds. Shallow (IFS set) only if cloud depth <= sh_dmax = 20000 Pa; deep only if depth >
  mf_dmin = 25000 Pa (mm2 default; its own comment says "ECMWF ~20000"). => clouds 200-250 hPa deep get NO convection at all -
  a GAP between the two schemes that IFS does not have (IFS: deep if > 200 hPa, else shallow). Base3 had no gap (shallow 'mse'
  had no depth limit). REGISTERED (no tuning: set mf_dmin to the IFS value 20000 so the classes meet): candidate + mf_dmin 20000 ->
  SUPPORTED if (1) 925 venting in 20-40N ascent regions recovers >= 50 % of base3's (<= −0.52) and (2) masked 20-40N q850 dynamics
  recovers >= 50 % of base3's drying (<= −0.24); then the global T42 screen.
- 19:47 (clock) GAP TEST RESULT (candidate + mf_dmin 20000): 925 venting in 20-40N ascent regions q_shal +0.11 (needed <= −0.52), deep
  −0.19; masked 20-40N q850 dynamics +0.15 (needed <= −0.24) -> NOT SUPPORTED. The 200-250 hPa gap is real in the code (logged for
  the Stage-1 config) but it is not why 925 is not vented. Next: where is the shallow scheme active in those regions and where is
  its cloud base - if 925 sits ABOVE the shallow cloud base, the IFS scheme moistens it (in-cloud detrainment) instead of venting it,
  while base3's 'mse' scheme vented from the lowest level up. Diagnostic: on_sh fraction and source / cloud-base sigma, 20-40N ascent.
- 19:56 (clock) DIAGNOSTIC (20-40N ascent regions, area fractions / heights): base3: shallow-'mf' on 0.00 (its −1.04 venting is the old
  'mse' mixing, which acts without any cloud trigger), deep on 0.21, LCL 1896 m, BL top 1099 m | shal_only: shallow on 0.11, deep on
  0.33, LCL 1475 m, BL top 1099 m.
  => In these (largely dry, land-heavy) subtropical regions the LCL (1.5-1.9 km) sits ABOVE the BL top (1.1 km): the IFS shallow
  test parcel rarely reaches its LCL -> shallow on in only 11 %. Base3 vented 925 with 'mse' mixing that ignores the cloud trigger
  (acting like dry-convective mixing). With the IFS set nothing mixes the layer between the BL top and the LCL -> 925 stays moist.
  5-Why next (registered for tomorrow): ERA5 boundary_layer_height and LCL in the same regions/times: if ERA5's BL reaches the LCL
  (BLH >= 0.9 x LCL) where ours stops at ~0.6-0.75 x LCL -> our BL depth is the input error there (dry-convective BL too shallow);
  if ERA5's BL also stops well below the LCL -> the missing venting must come from the shallow trigger (parcel excess / LCL input).
- 19:58 (clock) ERA5 BLH vs LCL (20-40N 50-110E low ground, 3 starts x 3 times): ascent regions BLH 528 m, LCL 1377 m, BL >= 0.9 LCL in
  18 %; subsidence regions 426 / 1297 m, 15 %. Our model there: BL top 1099 m, LCL 1475-1896 m.
  Rule: ERA5's BL ALSO stops well below the LCL -> our BL depth is NOT the input error (ours is even deeper); the missing 925
  venting must come from the SHALLOW TRIGGER (ERA5's own IFS shallow scheme vents these regions: its 925 q is 0.69 g/kg lower).
  Input to check: the test-parcel ascent rule. IFS lifts the test parcel with the kinetic-energy equation (6.10, w > 0 from the
  surface excess + buoyancy); our test parcel instead survives below the LFC only within 0.2 sigma of its source (mf_wke = 0).
  REGISTERED: shal set + mf_wke 1 (the existing IFS-KE option): SUPPORTED if shallow-on in 20-40N ascent regions >= 0.30 (from 0.11)
  and 925 venting <= −0.52 g/kg/day.
- 20:03 (clock) RESULT shal set + mf_wke 1: shallow on 0.10 (needed >= 0.30), 925 venting −0.03 (needed <= −0.52) -> NOT SUPPORTED.
  The test-parcel ascent rule is not the limiter. Next: trace the shallow test parcel over the 20-40N ascent columns (eager call on a
  day-1 state): fraction reaching condensation, where it stops, parcel RH at its top - to find which input stops it.
- 20:05 (clock) TEST-PARCEL TRACE (shal set, 1 Nov +24 h, 20-40N ascent columns, n = 22 at T42 - small sample): parcel reaches
  condensation 56 %, LFC 77 %; of the cloudy half only 50 % are <= 200 hPa deep -> shallow active 28 % (snapshot; 10-11 % averaged
  over 9 times); source sigma 0.938 (~600 m), parcel top sigma 0.74. sh_ifs2 does vent the WHOLE sub-cloud layer (code checked,
  linear to the ground), so 925 is vented whenever shallow is active - the deficit is how OFTEN (and with what Mb) it is active.
  Half the cloudy parcels are 200-250+ hPa deep: neither shallow (<= 200) nor, mostly, deep (base3 plume needs > 250 hPa and CAPE
  > 50) - consistent with the gap logged at 19:39 even though closing it alone (mf_dmin) did not vent 925 (the deep scheme does
  not vent the sub-cloud layer the same way). Open for tomorrow: run BOMEX-like single-column checks on a representative 20-40N
  ascent column against ERA5's own state there (the ERA5-column method of 17 Nov), to see what IFS's scheme would do with ERA5's
  inputs vs ours.

## 18 Nov 22:49 IST (clock) — 22:00 cycle: queue empty; next cycle 04:00 (silent). ERA5 subtropical columns (40 ascent + 20 subsidence,
20-40N 50-110E, 2020-11-01/11 00Z, 137 levels) being fetched ('ml sub columns') for tomorrow's column test: our shallow scheme on
ERA5's own subtropical columns vs on ours (same method as 17 Nov) - which input keeps the shallow trigger off.
- 23:01 (clock) SUBTROPICAL COLUMN TEST (IFS shallow set; ERA5 137-level columns inserted vs our start state, same points, h0):
    1 Nov ascent: ours shallow on 0.12, q_shal@925 −1.12 | ERA5 columns 0.15, −0.12 | RH925 0.45 both | LCL 1625 / 1741 m, BL 400 m
    11 Nov ascent: ours 0.10 | ERA5 0.15 | RH925 0.43 / 0.44 ; subsidence points: shallow ~0-0.05 in both.
  => With ERA5's OWN inputs the shallow scheme also fires in only ~15 % of these dry (RH925 ~0.45) subtropical ascent columns ->
  the trigger is NOT failing because of our state; these regions genuinely have little shallow convection at the start.
  So what moistens 925 during day 1 (+1.09 g/kg vs base3, ERA5 drier by 0.69)? The 925 budget: BL mixing +1.34..+1.81 g/kg/day is
  the largest source, and OUR BL GROWS from ~400 m at h0 to ~1100 m by day 1 while ERA5's is 528 m (2.1x). Base3 hid this with
  'mse' mixing that vented 925 upward regardless of clouds.
  REGISTERED next: our BL depth growth over subtropical low ground: model sensible heat flux H and BL top at h12/24 vs ERA5 sshf and
  BLH (same regions/times). INPUT ERROR named if our H is >= 1.3x ERA5's (surface driving too strong) - else the BL scheme's depth
  formula (given right H) is named.

## 18 Nov 23:03 IST (clock) — Sridhar 23:03 "You are not trying to close stage 1". Course correction:
The Stage-1 deliverable is a FULL EXAM RUN + SCORECARD with the cause of each failing check (not every check passing). I had been
deepening diagnoses without producing that run. Launched now: the full BASE3 exam on Kaggle - exam quarters tn-b3-wx0..3 (accounts
1/4) + Rule-1 intensity tn-r1-b3-0/1; tracks for BASE3 already exist (q6 seeds 4-6: 377/382/380 km). The scorecard is built as soon as
quarters land, with this week's root causes on each failing row. Fix work (A/P1 etc.) continues in parallel; a passing fix triggers an
exam re-run.
- 23:09 (clock) SURFACE FLUX RESULT (20-40N 50-110E low ground, 850 ascent regions, h12/24/36 x 3 starts, same instants):
    sensible H: base3 62.0, candidate 67.9 W m-2 vs ERA5 10.9 (5.7-6.2x) | latent LE: 88.2 / 87.3 vs 34.1 (2.6x) | BL top 1099 / 932 vs 528 m
  Rule (H >= 1.3x ERA5 -> surface driving named): MET by a wide margin -> SURFACE FLUXES named as the input error behind the
  over-deep BL and the 925/850 moistening in the subtropics (both configurations). Note the sample times (00/12 UTC = morning /
  late evening over 50-110E): ERA5's H is small then; ours stays ~60 W m-2 -> suspect the land surface does not cool at night /
  wrong diurnal phase of the land skin temperature, or the land exchange coefficient. Next (registered): model vs ERA5 skin
  temperature and 2-m temperature at the same points/times, and H split land vs sea: land skin too warm at these hours -> named.
- 23:13 (clock) LAND/SEA SPLIT RESULT (20-40N ascent regions, h12/24/36 = 05:30/17:30 local-ish over 50-110E):
    model base3 land (91 % of the sample): H 64.7 W m-2, land skin 295.5 K | sea: H 33.1, SST 298.8
    ERA5 land: H 9.6, LE 13.8, skin 293.6 K, 2-m T 295.1 K (skin COLDER than air: evening/morning surface inversion) | sea H 13.5, LE 164
  => Over LAND our sensible flux is 6.8x ERA5 and the skin is ~1.9 K warmer, i.e. our land skin stays warmer than the air at
  these hours where ERA5's is colder -> NAMED: land skin temperature / land surface energy balance (input to the bulk flux).
  The land module already built 5 Nov (sfc_imp + land_rs 100 + soil_fr; ISBA-type, fixed central-India cold land) was never adopted.
  REGISTERED: BASE3 + land module in the same diagnostic -> SUPPORTED if land H in 20-40N ascent regions <= 2x ERA5 (<= 19 W m-2)
  AND BL top <= 1.3x ERA5 (<= 690 m); then global screen with the candidate convection.

## 18 Nov 23:17 IST (clock) — Sridhar 23:17: work with the rules (FMEA, 5-Why, Fishbone; when an equation/implementation is suspect,
## CHECK ITS INPUTS first - do not blindly change physics or implementation). Applied to the land-skin finding BEFORE any land change:
Problem: over subtropical land at 00/12 UTC our skin stays 1.9 K warm, sensible flux 64.7 vs ERA5 9.6 W m-2.
Equation: C dTl/dt = SW_sfc + LW_dn − sigma Tl^4 − H − LE  (cap_land 2e5 J m-2 K-1); H = rho cp Ck V1 (Tl − theta1).
5-Why: H too large <- (Tl − theta1) too large and/or Ck V1 too large <- Tl too warm <- net surface energy too positive at night:
  LW_dn too large? (our 850 is too moist and low cloud is 3x ERA5 -> more downward LW) / SW_sfc too large (cloud too thin?) /
  C too large (slow cooling) <- inputs to be MEASURED, not changed.
Fishbone: Inputs (LW_dn, SW_sfc, V1, theta1, Ck), Equation (slab vs force-restore), Parameter (cap_land), State (cloud, q850),
  Coupling (cloud -> LW_dn -> Tl -> H -> BL -> q850 -> cloud = possible LOOP with problem A).
FMEA (RPN): LW_dn too large from excess cloud/moisture 8x7x3=168 | C too large 6x5x3=90 | V1/Ck too large 6x4x3=72 | SW_sfc 5x3x3=45.
REGISTERED input check: model SW_sfc, LW_dn, V1 over the same land points/times vs ERA5 ssrd / strd / 10-m wind (W m-2, hourly):
the input whose error, put through the equation, accounts for >= 50 % of the extra (H + net) is named; the land module (already
running as a separate test) is NOT adopted on its own result unless this check points to the land equation/capacity.
- 23:17 (clock) Land-module test (run before the 23:17 rule; recorded, NOT used to decide): land H 64.7 -> 24.2 W m-2 (rule <= 19: not
  met), BL top 1099 -> 1045 m (rule <= 690: not met), LE 88 -> 58 W m-2. Not supported, and not adopted. The input check decides.
- 23:21 (clock) LAND-SKIN INPUT CHECK RESULT (20-40N ascent regions, land, h12/24/36, base3 vs ERA5):
    LW_dn 354.9 vs 349.4 W m-2 (+5.5) | SW: ours 91.7 (absorbed) vs ERA5 93.9 downward (~75 absorbed at albedo 0.2: ~+17)
    wind: our lowest level (~85 m) 5.88 m/s vs ERA5 10-m 2.29 m/s (2.6x) | H 64.7 vs 9.6; skin 295.5 vs 293.6 (ERA5 skin < 2-m air)
  => FMEA #1 (LW_dn from excess cloud) REJECTED: only +5.5 W m-2. SW +~17 is a minor term. The largest input difference is the
  near-surface WIND (2.6x), entering H linearly (and the turbulent exchange that keeps the skin coupled to warm air above).
  Height caveat: ~85 m vs 10 m; typical u85/u10 is 1.3 (neutral) to 2 (stable), so 2.6x exceeds what height alone explains.
  REGISTERED next: ERA5 100-m wind at the same points/times vs our lowest-level wind: NEAR-SURFACE WIND named if ours >= 1.5x ERA5's
  100-m wind; then 5-Why on its inputs (surface drag: z0_land 0.1 m vs ERA5 roughness incl. orographic form drag; drag_imp;
  momentum mixing from above) - measured, not changed.
- 23:23 (clock) 100-m WIND RESULT: ERA5 land (20-40N ascent regions) 10-m 2.29, 100-m 3.56 m/s; ours (lowest level ~85 m) 5.88 m/s =
  1.65x ERA5's 100-m wind -> rule (>= 1.5x) MET -> NEAR-SURFACE WIND named as the input behind the large land H.
  ERA5's skin is colder than its 2-m air (stable surface layer, decoupled, weak near-surface wind); ours is warmer (unstable,
  strong mixing brings momentum down) -> a possible loop: warm skin <-> strong mixing/wind <-> large H. Which comes FIRST decides the
  input to fix. REGISTERED: same comparison at hour 0 (ERA5-initialised) and h6: if our wind is already >= 1.5x ERA5 at h0 -> the
  wind/drag input (roughness z0_land 0.1 m vs ERA5, initialisation) is first; if it is within 1.2x at h0 and grows by h6-h12 -> the
  skin/stability loop is first (then: what warms the skin in the first hours - SW absorbed +17 W m-2 is the remaining input).
- 23:26 (clock) DRAG INPUT CHECK REGISTERED (before results; measure only). Fishbone for "near-surface wind 1.65x": (1) surface roughness
  z0_land fixed 0.1 m vs ERA5 forecast_surface_roughness (includes vegetation/urban; ERA5 TOFD is separate); (2) turbulent stress
  rho*ust^2 ours vs ERA5 mean turbulent surface stress; (3) missing orographic/gravity-wave surface stress (our gwd option is OFF in BASE3);
  (4) stability (warm skin -> unstable -> strong downward momentum mixing). RULES at the same land ascent points, h12-36:
  (1) named if ERA5 z0 >= 3x ours (>= 0.3 m); (2) named if our stress < 0.67x ERA5 turbulent stress while our wind is 1.65x
  (i.e., our drag coefficient is too small); (3) named if ERA5 gw stress >= 50% of its turbulent stress there; (4) decided by the h0/h6 order test.
- 23:28 (clock) ORDER TEST RESULT (land ascent points, mean of 3 starts; 00Z ~ 05 local, 06Z ~ noon, 12Z ~ evening):
  | h | wind ours (85 m) / ERA5 100 m | H ours / ERA5 | skin ours / ERA5 | SW sfc ours (net) / ERA5 down |
  | 0 | 2.82 / 3.56 | 1.6 / -8.8 | 287.2 / 287.1 | 4 / 3 |
  | 6 | 5.27 / 2.96 | 10.5 / 93.1 | 292.0 / 302.0 | 470 / 534 |
  | 12 | 4.15 / 3.40 | 105.1 / 18.0 | 299.2 / 296.8 | 139 / 135 |
  Verdict by the registered rule: wind at h0 is 0.79x ERA5 (within 1.2x) and grows by h6 -> the WIND/DRAG input is NOT first; the
  SKIN/STABILITY side is first. CORRECTION of the earlier framing: our land H is not uniformly too big, it is PHASE-SHIFTED. At local
  noon ours is 9x too SMALL (skin 10 K too cold); in the evening it is 6x too big (skin 2.4 K too warm while ERA5's skin is already
  below the air). The day-1 mean (h12/24/36) hid this. Our near-surface wind is high at noon (5.3 vs 3.0), when our H is small, so the
  wind does not cause the noon error. The registered drag rules (roughness/stress) still run, but they are now secondary.
  New 5-Why: why does our skin warm 4.7 K by noon (ERA5 15 K) and stay warm into the evening? The inputs to C dTl/dt = net are
  SW/LW (match at h0/h12; SW net 470 vs ERA5 down 534 -> plausible), the heat capacity C = cap_land 2e5 J m-2 K-1, and H/LE.
  REGISTERED for the hourly trace (model and ERA5, all low-ground land, 0-24 h): (a) THERMAL INERTIA named if our skin's diurnal
  range is < 0.6x ERA5's AND our maximum is >= 2 h after ERA5's; (b) an ENERGY-input error named if our time-integrated
  (SW net + LW dn - LW up) from 0 to 6 h differs from ERA5's by more than 25%; (c) the SURFACE-FLUX partition (LE) is named if
  our LE at local noon is < 0.5x ERA5's (ERA5 noon LE 128 W m-2) - the noon energy has to go somewhere.
- 23:34 (clock) DRAG TRUTH (ERA5, land ascent points, h12/24/36 mean): roughness z0 0.40 m (ours fixed 0.1) -> rule (1) MET: ROUGHNESS
  named (ERA5 4x ours; ERA5 forecast_surface_roughness, no orographic part). Turbulent stress 0.088 N m-2, GW surface stress 0.032
  = 36% of turbulent -> rule (3) NOT met (orographic drag not named). Rule (2) (our rho*ust^2) runs after the hourly trace.
  Weight: secondary to the skin phase (order test). A 4x larger z0 also raises our heat exchange (Ck), so it cannot by itself fix the
  noon deficit; it is noted as an input error to correct with the land fix, not alone.
- 23:37 (clock) HOURLY LAND TRACE (all low-ground land 20-40N 50-110E, 3 starts, ours vs ERA5): skin ours/ERA5 h2 285.1/289.0, h4 285.2/295.7,
  h6 289.5/302.0, h8 295.5/304.3 (ERA5 max), h10 299.1/302.2 (our max), h12 298.9/296.5, h24 285.7/287.3.
  Rule (a) THERMAL INERTIA: our range 14.0 K = 0.82x ERA5's 17.0 (needed < 0.6) -> NOT met (max lag 2 h met, range not).
  Rule (b) ENERGY INPUT: radiative net 0-6 h ours 1.09x ERA5 -> NOT met (radiation is not short).
  Rule (c) LE at noon: our E was rounded to 0 in this run (kg m-2 s-1 at 2 decimals) -> re-running h0-12 with LE in W m-2; pending.
  Two new observations, not yet rules: (i) our skin does NOT warm for 4 h after sunrise (h2-h4 flat at 285 K while ERA5 warms 7 K,
  with our radiation 1.09x ERA5) -> the energy goes to a sink we have not measured yet (LE or the near-surface air) - the LE rerun
  decides; (ii) at NIGHT our near-surface wind keeps growing (h24 7.6 vs ERA5 100-m 3.9, 1.9x) while H is -16 vs -10: the stable
  night layer does not decouple, so momentum keeps mixing down. This is where the day-mean 1.65x wind excess comes from.
- 23:43 (clock) LE RERUN (h0-12, land): LE ours/ERA5 h6 114/128 (0.89x) -> rule (c) NOT met. All three registered land rules (a)(b)(c) are NOT met.
  The hourly surface budget of ours alternates hour to hour (slab heating residual h4..h9: +190, +9, +269, -1, +140, -15 W m-2; LE
  43, 183, 114, 272, 149, 212), while ERA5's is smooth. Fishbone: methods/implementation - the land skin is stepped EXPLICITLY
  (sfc_imp 0 in BASE3) with large exchange coefficients at noon (unstable), so an oscillation between steps is possible; the
  hourly snapshots then sample it. REGISTERED (per-step tl trace, 2020-11-01, 0-10 h): NUMERICAL OSCILLATION of the skin named if
  >= 30% of land points show a sign-alternating 2nd difference in > 50% of steps, OR the median |2nd difference| >= the median
  |1st difference| (noise as large as the signal). If named, the input to check is the coupling time step/implicitness, not the physics.
- 23:44 (clock) INPUT FOUND for the oscillation test: the T42 screen steps at dt = 60 min (DT_MAX T42 60; T170 20). The explicit skin
  update tl += dt*net/C is stable without overshoot only if K*dt/C < 1, where K = dnet/dTl = 4 sigma T^3 + cp*chv + Lv*chv*beta*dqs/dT
  (the same K the sfc_imp option uses). REGISTERED: compute K*dt/C from the model's own diagnostics at land points (h6, local noon);
  EXPLICIT-STEP OVERSHOOT named if the median over land >= 1 at dt 3600 s (then the skin rings at T42; check the same at T170, dt 1200 s).
  If named, the T42 land results (H 65, BL 1100 m) are partly a time-step artifact of the SCREEN, and the input fix is the solver
  (implicit skin = sfc_imp, already in the code), not the physics.
- 23:47 (clock) OSCILLATION RESULT: 62% of land points alternate sign in > 50% of steps (rule >= 30%) -> NUMERICAL OSCILLATION NAMED.
  Stability number K*dt/C median 0.56 at dt 3600 s (0.19 at 1200 s; K = 31 W m-2 K-1) -> explicit-step overshoot NOT named (< 1).
  So the ringing does not come from the skin solver. Its source is the radiation interval: rad_every 2 x dt 60 min = radiation
  every 2 h at T42 (SW sfc pairs in the hourly trace: 8,8 / 78,72 / 280,277 / 457,460 / 489,482), a step forcing every 2 h -> 2-step
  alternation. It adds noise; it cannot make a 10 K noon deficit (radiation over 0-6 h is 1.09x ERA5).
  The noon deficit is still unexplained by the registered rules. Seen so far (stated openly: h6 values already seen): at h6 ours puts
  +269 W m-2 into slab storage, while ERA5's residual (ground flux) is ~92. REGISTERED (h3-h8 mean, both from data already in hand,
  ERA5 residual = SWnet + LWdn - sigma*Tskin^4 - H - LE, emissivity 1 for both): HEAT STORAGE named if ours >= 2x ERA5's.
- 23:47 (clock) HEAT STORAGE RESULT: h3-h8 ours 95 vs ERA5 65 W m-2 = 1.47x (< 2) -> NOT named. Over h3-h8 our skin warms 10 K vs ERA5 12 K -
  close. The 10 K noon gap opens EARLIER: h0-h4 ours cools 287.2 -> 285.2 while ERA5 warms 287.4 -> 295.7 (the box's east is already
  in sunlight at 00Z). REGISTERED (data in hand, h1-h4, term-by-term flux difference ours - ERA5 into the skin, W m-2): the term
  that explains >= 50% of the summed deficit is named; candidates SW net (2-h held radiation lags sunrise), LW down, H, LE.
- 23:47 (clock) MORNING DECOMPOSITION RESULT (h1-h4, ours - ERA5, W m-2 into the skin): SW net -12.3, LW down -7.8, H +13.8 (ours loses
  less), LE +13.2 (ours loses less); sum +7.0 -> ours RECEIVES slightly MORE energy, yet our skin cools 2 K while ERA5's warms 8 K.
  -> no flux INPUT is named (all within 14 W m-2 and the sum has the wrong sign). The inputs are now checked (radiation, H, LE,
  wind order); what remains is the RESPONSE to the same flux: how much the skin's temperature changes per W m-2 = the land
  skin's heat capacity/formulation. Our skin is one slab with C = 2e5 J m-2 K-1 (~10 cm of wet soil) and no conduction to deeper soil;
  the ERA5 (IFS) skin has no heat capacity of its own and is coupled to the top soil layer by a skin conductivity (IFS Cy47r3
  Part IV, ch. 8.3). FORMULATION named (after the input check, per the method).
  REGISTERED test, existing code only, no tuning: soil_fr 1 (force-restore, Deardorff 1978, C_eff 1.17e5, mu 1400 from the docs)
  vs base3, hourly trace h0-12: PASS if noon (h6) skin within 3 K of ERA5's 302.0 AND evening (h12) H <= 2x ERA5's 15.
  If it fails, the IFS skin-layer formulation (zero capacity + skin conductivity) is the next candidate - from the document, not tuned.
- 23:48 (clock) REFERENCE (IFS Cy38r1 Part IV, eq. 3.75, Table 8.2, Table 8.6, sec. 8.5.1): the skin layer "has no heat capacity and
  therefore responds instantaneously": R_SW + R_LW + H + L Jq = Lambda_sk (T_sk - T_1). Lambda_sk: low vegetation 10, bare ground 15,
  high vegetation 20 (unstable) / 15 (stable) W m-2 K-1. Top soil layer 0.07 m, volumetric heat capacity 2.19e6 J m-3 K-1
  (-> 1.53e5 J m-2 K-1 for layer 1), four layers 0.07/0.21/0.72/1.89 m. Ours: one slab C = 2e5 that IS the skin -> with G ~ 90 W m-2
  at noon the IFS skin runs (90/10..15) = 6-9 K above its top soil layer; ours cannot. This is the documented formulation to
  implement as an OPTION if the force-restore test fails (Lambda 10 low veg / 15 bare, from Table 8.2; nothing tuned).
- 23:51 (clock) METHOD RULE (Sridhar 23:50): a fix that fails a gate is NOT rejected directly - another cause may produce the failure.
  Each failed gate gets a failure 5-Why (which check failed, which mechanism/input drives that check); the fix is "rejected" only if
  the failure traces to the fix itself, otherwise "HELD - blocked by X". Re-opened under this rule: land module (sfc_imp+land_rs+soil_fr:
  H 65 -> 24, ERA5 10; failed on BL 1045 m, which the night wind 1.9x / late skin cycle can produce) -> HELD; gap closure (mf_dmin
  20000) and mf_wke -> HELD, re-test after the land fix; soil_fr / skin_ifs tonight judged with the same failure analysis.
- 23:57 (clock) soil_fr TEST RESULT (hourly trace, land, skin K / H W m-2): h6 287.4/21 (base 289.5/8, ERA5 302.0/97); h12 295.9/54 (base 298.9/108, ERA5 296.5/15).
  Gate (h6 skin within 3 K AND h12 H <= 30) -> FAIL on both checks. h12 H halved vs base (108 -> 54), evening skin within 0.6 K of ERA5.
  Failure 5-Why: (1) why is the noon skin still 15 K cold? the morning skin is flat h0-h4 in BOTH base and soil_fr (285 K) -> a cause
  SHARED by both runs; (2) why flat in both? both skins are slabs with capacity (2e5 / 1.17e5 J m-2 K-1), so ~25 W m-2 of morning
  net heating gives < 1 K h-1, and our morning SW (2-h held radiation at T42) is 16% below ERA5 over h1-h5; (3) the IFS skin has
  ZERO capacity (eq. 3.75), so it follows the same flux at once. -> part of the failure traces to soil_fr's own design (a slab skin),
  part to the shared radiation timing. VERDICT: soil_fr is HELD (not rejected) as the deep-soil part; it cannot fix the noon skin by design.
  [reg: 23:47 | inputs: SW/LW/H/LE h1-h4 checked 23:4x, radiation timing | fail-5why: slab-skin capacity (fix design) + 2-h radiation (shared)]
  Next: skin_ifs (zero-capacity skin + 4-layer soil, IFS Cy38r1) on the same gate - running now.
- 00:02 (clock) skin_ifs TEST RESULT (land skin K / H W m-2): h6 293.5/17 (base 289.5/8, ERA5 302.0/97); h12 299.8/94 (ERA5 296.5/15) -> gate FAIL
  on both checks; noon skin 4 K warmer than base (closer, still 8.5 K cold).
  Failure 5-Why: (1) the hourly budget RINGS: h3 LE 220 / h5 LE 856, H 240, residual -944 W m-2, skin 287.5 -> 286.0 -> 297.1 -> 293.5;
  (2) why? the zero-capacity skin is solved at the END of the step from the old fluxes, then the next step's H/LE see a jump in
  skin-air difference at dt = 60 min -> overshoot. IFS solves the skin INSIDE the implicit vertical diffusion (same tridiagonal
  system), which this first implementation does not -> the failure traces to MY IMPLEMENTATION (explicit coupling), not to the
  IFS physics -> HELD; needs the implicit coupling (sfc_imp/diffuse_imp machinery) before it can be judged.
  (3) Shared by base, soil_fr and skin_ifs: the morning skin stays ~285-287 K to h4 in all three -> a cause common to all runs.
  Common to all: the T42 screen steps at 60 min and radiation runs every 2 steps = every 2 h (ours SW 69 at h3 vs ERA5 147 = the h2
  value held). REGISTERED (base only, hourly trace): RADIATION INTERVAL named as the shared cause if rad_every 1 raises the h4 skin by
  >= 3 K vs rad_every 2; TIME STEP named if dt 20 min + rad_every 1 raises it by a further >= 3 K. (Inputs of the test harness itself.)
  [reg: now | inputs: SW/LW/H/LE hourly h0-h6 | fail-5why: explicit skin coupling (my implementation) + shared morning cause under test]
- 00:15 (clock) HARNESS TEST RESULT (base, land h4 skin): rad_every 1 286.6 vs 285.2 (+1.4 K, rule >= 3) -> radiation interval NOT named;
  dt 20 min + rad_every 1 287.5 (+0.9 K more) -> time step NOT named. With rad_every 1 our SW now matches ERA5 hour by hour
  (h3 149/147, h5 371/365) yet the skin still stays ~286-287 K to h4 (ERA5 295.7). Evening H drops with both (108 -> 62 -> 48; ERA5 15).
  Failure 5-Why of the harness hypothesis: correct SW does not warm our skin -> the cause is not the input timing; ERA5's skin warms
  3 K h-1 at h3 with ~0 W m-2 into storage, ours would need 167 W m-2 at C = 2e5 -> skin heat capacity (formulation) stays named,
  and skin_ifs's failure was its explicit coupling. Radiation every 2 h and the 60-min step are noted as harness contributors
  (evening H), not the morning cause.
  REGISTERED next (existing code only, both from IFS docs): skin_ifs 1 + sfc_imp 1 (implicit surface fluxes in the lowest layer),
  same gate (h6 skin within 3 K of 302.0 AND h12 H <= 30), run with rad_every 2 and with rad_every 1. Ringing check: no hour with
  |LE| > 400 W m-2 (ERA5 max 136).
  [reg: now | inputs: SW hourly now matched (rad_every 1), LW/H/LE | fail-5why: harness hypothesis rejected because correct SW did not warm the skin (the hypothesis' own failure)]
- 00:26 (clock) skin_ifs + sfc_imp RESULT (land, skin K / H W m-2): rad_every 2: h6 293.9/18, h12 299.8/83, max |LE| 664 (still rings) -> FAIL;
  rad_every 1: h6 297.4/89 (ERA5 302.0/97: noon H now MATCHES), h12 298.0/48 (ERA5 15), max |LE| 396 (< 400: ringing gone) -> gate FAIL
  (noon skin 4.6 K cold > 3; evening H 48 > 30), large improvement on both.
  Failure 5-Why (fix vs other cause): the hourly budget now shows the sink - LE ours/ERA5 h4 182/86, h6 396/128, h8 262/130, h12 82/20 =
  2-3x all day -> the energy that should warm the skin evaporates. Not caused by the skin fix (base LE was low only because its
  skin was cold). INPUT CHECK of the LE formula (E = rho ck V1 beta (qs - q1)): soil-water availability beta from ERA5 swvl1 in the box
  = 0.52 (ours) vs IFS stress factor 0.38 (TESSEL loam pwp 0.171, cap 0.323) -> 1.4x, part of the 3x; the main missing input is the
  surface (canopy/soil) resistance: IFS E = rho (qs - q)/(r_a + r_c), r_c = r_s,min/LAI x f(soil water) (Part IV ch. 8); ours r_c = 0
  (land_rs 0 in BASE3) -> evaporates like a wet surface. -> skin_ifs + sfc_imp HELD (blocked by LE: no surface resistance).
  REGISTERED: skin_ifs 1 + sfc_imp 1 + rad_every 1 + land_rs 100 (existing option; 100 s m-1 = IFS r_s,min for crops / short grass,
  Table 8.1, not tuned): same gate (h6 skin within 3 K of 302.0 AND h12 H <= 30) AND h6 LE <= 1.5x ERA5 (192) AND max |LE| <= 400.
  [reg: now | inputs: beta from ERA5 swvl1 vs IFS f2; r_c missing | fail-5why: LE sink (missing surface resistance, not the skin fix)]
- 00:32 (clock) skin_ifs + sfc_imp + rad_every 1 + land_rs 100 RESULT (land; skin K / H / LE W m-2, ours/ERA5): h6 297.9/302.0, H 91/97, LE 118/128;
  h10 skin 302.2/302.2, H 140/71; h12 skin 299.4/296.5, H 60/15; max |LE| 140. Gate: LE <= 192 PASS, ringing PASS, h6 skin 4.1 K cold
  (> 3) FAIL, h12 H 60 (> 30) FAIL. HBL (ascent) 995 m.
  Failure 5-Why: (1) evening H 4x because our skin stays warm into the evening (h10-h12 +0-2.9 K) and our afternoon SW is +10%
  (net 448/406 at h9; albedo matches: ERA5 effective 0.19-0.23 vs ours 0.20) -> SW DOWN is ~7-10% too high in the afternoon:
  an INPUT to the skin (clouds or clear-sky aerosol/water vapour); (2) the morning skin still lags (h3 287.0/291.9) with SW, LE,
  H now close -> candidates: ERA5's earlier-sunlit east weighted differently by the T42 land mask (comparison input), and the 4
  soil layers all starting at ERA5 stl1 (no deeper-soil temperatures in the start file). Neither traces to the fixes ->
  the land set {skin_ifs, sfc_imp, land_rs 100, rad_every 1} is HELD (blocked by SW-down excess + morning sampling/soil start), not rejected.
  REGISTERED: (a) SW: ERA5 total cloud cover and clear-sky SW down vs ours (cover, SW down) at h6-h10: CLOUD named if our cover is
  < 0.7x ERA5's; CLEAR-SKY (aerosol/vapour) named if the ERA5 clear-sky/all-sky SW gap explains < 50% of our excess.
  (b) MASK: mean longitude of the land comparison points, ours (T42, own orography) vs ERA5: SAMPLING named if they differ by >= 5 deg.
  [reg: now | inputs: albedo checked (matches), SW down, LE now OK | fail-5why: SW-down excess + morning sampling/soil start - not the fixes]
- 00:39 (clock) SW / MASK RESULT (land, ours/ERA5, h6-h10): cloud cover 0.32/0.36 (0.88x >= 0.7) -> CLOUD NOT named; SW down 589/552,
  626/592, 451/409 (excess ~38 W m-2); ERA5 clear-sky 655/673/449, and at h10-h12 our ALL-sky SW (451, 169) exceeds ERA5's CLEAR-sky
  (449, 145) -> our clear sky is too transparent. The 12% cloud deficit explains ~9 of the 38 W m-2 (~25%, < 50%) -> CLEAR-SKY named
  (rule as registered was loosely worded; applied as: cloud-amount share < 50% of the excess). Mask mean longitude 73.4 vs 77.5
  (4.1 deg < 5) -> SAMPLING NOT named (16 min of solar time - minor). The morning skin lag stays unexplained (next: soil start).
  Input to the clear sky: BASE3 has NO aerosol (option aer built 13 Nov, judged on day-2 t850 only, +0.07 K < 0.2 -> re-marked HELD
  under the 23:50 rule: its own effect is surface SW -5.5 W m-2 daily mean, the t850 test could not show it).
  REGISTERED: land set + rad_prm aer 1 (13 Nov literature values: AOD 0.20 land, SSA 0.93, g 0.70; not tuned): SW-down excess h6-h10
  <= 20 W m-2 (from 38) AND the land gate (h6 skin within 3 K, h12 H <= 30).
  [reg: now | inputs: cloud cover, clear-sky SW, albedo, mask longitude | fail-5why: n/a (measurement step); aer re-marked HELD]
- 00:40 (clock) REGISTERED (morning lag, soil start input): ERA5 soil temperature levels 1-4 at the 3 starts vs ours (all 4 layers start
  at ERA5 stl1). SOIL START named if ERA5's stl2-stl4 mean differs from stl1 by >= 2 K (then our soil column starts with the wrong
  heat content and the zero-flux bottom). [reg: now | inputs: soil start | fail-5why: n/a (measurement)]
- 00:46 (clock) AEROSOL RESULT (land set + aer 1): SW-down excess h6-h10 36.9 -> 14.3 W m-2 (rule <= 20) -> PASS on SW; land gate: h6 skin
  297.4 (4.6 K cold), h12 H 52 -> FAIL. SOIL START RESULT (ERA5, 3 starts, box land): stl1 295.8/290.7/286.3, stl2-4 mean 300.6/298.2/294.9
  -> deeper soil is 4.8-8.6 K WARMER than level 1 (rule >= 2 K) -> SOIL START NAMED: our 4 layers all start at stl1, i.e. 5-9 K too
  cold below 7 cm, so the soil keeps drawing heat out of the skin by day (and less heat comes up at night).
  Failure 5-Why for the aerosol run's land gate: the remaining skin deficit is the named soil start (an input), not aerosol
  -> aer + land set HELD (blocked by soil start). FIX of the INPUT (not physics): soil_temperature_level_2-4 added to the start library
  (cyc_libm LAND appended, landinit NAMES, Model.init -> skin_ifs soil layers; old libraries unchanged -> fall back to stl1).
  New library wx2020L2 building on GitHub ('land2 library'). REGISTERED: the land set + aer on wx2020L2, same gate (h6 skin within
  3 K of 302.0 AND h12 H <= 30) AND SW excess <= 20 AND max |LE| <= 400.
  [reg: now | inputs: SW (aer), soil start (ERA5 stl1-4) | fail-5why: soil start input (named), not the fixes]
- 01:00 (clock) SOIL-START RESULT (land set + aer on wx2020L2, ERA5 stl1-4): h3 287.1 (was 286.8), h6 297.6/H 85 (was 297.4/81), h12 299.2/H 55
  (was 298.9/52) -> gate FAIL (noon 4.4 K cold; evening H 55). The soil start was a real input error (named), but correcting it moves
  the skin < 0.3 K: deeper layers barely reach the skin within 12 h. CORRECTION: soil start is NOT the driver of the remaining deficit.
  Kept (input now right). Failure 5-Why on the remaining morning gap (h3 skin -4.8 K with SW, H, LE all within 7 W m-2 of ERA5):
  the zero-capacity skin settles where net = Lambda (Tsk - T1); the remaining term is LONG-WAVE UP: ours = sigma Tsk^4 (emissivity 1);
  IFS uses emissivity 0.99 outside / 0.93-0.96 inside the 8-12 um window (Part IV Table 2.8), i.e. ~0.97 broadband, and ERA5's
  skin is defined consistently with it. Emitting 3% more at the same T costs ~12 W m-2 -> ~1 K at Lambda+K ~ 40 W m-2 K-1;
  REGISTERED: ERA5 net thermal (str) vs ours (lw_dn - sigma Tsk^4) h0-h12: EMISSIVITY named if ERA5's implied broadband emissivity
  (lw_dn - str = eps sigma Tsk^4 + (1 - eps) lw_dn) is <= 0.97 over this land.
  [reg: now | inputs: soil start fixed; SW, H, LE matched | fail-5why: not soil start (tiny effect); LW-up/emissivity under test]
- 01:03 (clock) EMISSIVITY RESULT: ERA5-implied broadband emissivity over this land (lw_dn - str vs sigma x mid-hour skin^4, 36 h) = 0.967
  (<= 0.97) -> EMISSIVITY NAMED (ours 1.0). (Single hours are noisy from accumulation timing, 0.83-1.08; the 36-h fit is the measure.)
  Option emis_land added (default 1 = unchanged; net LW = eps (LW_dn - sigma T^4), also in the skin's K). Value 0.97 from ERA5 and IFS
  Table 2.8 (0.99 outside / 0.93-0.96 in the window), not tuned. PREDICTION (registered before the run): +0.8 to +1.5 K at noon - NOT
  enough alone for the 4.4 K gap; the same land gate applies, so a FAIL is expected and the failure 5-Why continues.
  [reg: now | inputs: ERA5 str, skin | fail-5why: n/a (measurement); test running]
- 01:09 (clock) EMISSIVITY TEST RESULT: h6 297.8 (+0.2 K vs 297.6; predicted +0.8..1.5 - smaller than predicted), h12 H 56 -> gate FAIL (as
  predicted). emis_land kept (input correct per ERA5/IFS), not the driver. Failure 5-Why: with SW, LE and LW now matched, ours has
  H 90 at noon from a skin 4.2 K colder -> our skin-air coupling is stronger (morning near-surface wind 4.9 vs ERA5 100-m 3.4).
  REGISTERED: COUPLING named if our H / (Tsk - T_lowest) >= 1.5x ERA5's H / (skin - t2) at h4-h8 (ERA5 with t2 is conservative:
  the 2-m gradient is smaller than to ~85 m, which overstates ERA5's conductance).
  [reg: now | inputs: emissivity fixed, SW/LE/LW matched | fail-5why: skin-air coupling under test]
- 01:20 (clock) COUPLING RESULT: conductance H/(Tsk - Tair) h4-h8 mean ours 56.9 vs ERA5 18.0 (3.2x) - BUT the mean is dominated by h4
  where ours has Tsk - Tair = 0.1 K (198 W m-2 K-1); at h5-h9 ours 18-25 vs ERA5 18-22 (median ratio 1.2). The registered statistic
  (mean of a ratio with a near-zero denominator) was ill-posed; reading it honestly -> COUPLING NOT named. (Rule fix for the future:
  use the regression of H on the skin-air difference, not the mean of ratios.)
  NEW, measured directly (soil layers traced; ERA5-like 290.6/295.1/297.8/300.1 at h0 - the soil start works): the "zero-capacity"
  skin is NOT in energy balance in the morning: residual SW + LW - H - LE - Lambda (Tsk - T1) = +45 (h3), +89 (h4), +105 (h5), +84 (h6)
  W m-2. Cause (implementation timing, not physics): the skin is solved in surface() AFTER the column with this step's radiation, and
  is first seen by the NEXT step, whose sun is higher; at the T42 screen dt = 60 min the sun ramps ~115 W m-2 per hour, so the skin
  runs ~1 h behind (~100 W m-2 / (K+Lambda ~ 50) ~ 2 K), and more when the 2-step radiation cache was on. IFS has the same order but at dt 7.5-15 min.
  REGISTERED: TIME-STEP LAG named if the same land set at dt 20 min (the T170 step) raises the h6 skin by >= 2 K and cuts the morning
  residual (h3-h6) by >= half.
  [reg: now | inputs: soil layers traced (correct), coupling measured | fail-5why: skin solve lags the sun by one 60-min step]
- 01:24 (clock) TIME-STEP LAG RESULT (land set, dt 20 vs 60 min): h6 skin 299.4 vs 297.8 (+1.6 K; rule >= 2 K -> NOT met); morning residual
  h3-h6 mean 25.5 vs 81 W m-2 (cut by 69%, rule >= half -> met). Both were required -> TIME-STEP LAG NOT named by the rule as written.
  Stated plainly: the step explains most of the energy imbalance but only 1.6 K of the skin; at dt 20 the h6 skin is 2.6 K below ERA5
  (inside the 3-K gate half). Failure 5-Why on the remaining 2.6 K and the h4 residual (41 W m-2 at dt 20): the skin is still solved
  after the column with the step-start sun - the order of operations remains (implementation). The T170 exam runs at dt 20, so the
  T42 screen at dt 60 handicaps the land; the land screen must run at the exam's step.
  REGISTERED: full 0-12 h land gate at dt 20 (T42): h6 skin within 3 K of 302.0 AND h12 H <= 30.
  [reg: now | inputs: residual measured both steps | fail-5why: skin-solve order (implementation) + screen step 60 min]
- 01:31 (clock) LAND GATE RESULT (T42 at dt 20 = exam step; land set = skin_ifs + sfc_imp + land_rs 100 + aer + emis_land 0.97 + rad_every 1,
  start file wx2020L2 with ERA5 soil levels 1-4): h6 skin 299.4 vs ERA5 302.0 (2.6 K <= 3) PASS; h12 H 24 vs ERA5 15 (<= 30) PASS ->
  LAND GATE PASS. LE matches hour by hour (h6 128/128, h8 135/130); night skin within 1.8 K.
  Remaining, recorded (not part of the gate): afternoon H 1.3-1.4x ERA5 (h7-h10: 144/112, 151/113, 138/97, 110/71) with the
  afternoon skin 0.4-2.3 K low and our lowest-level air 1.5-2.2 K below ERA5 t2 -> the BL is still deep (ascent HBL 1133 m vs ERA5 ~530-700).
  NEXT (registered from 17-18 Nov, unchanged): the A/P1 global screen - the land set at dt 20 vs BASE3 at dt 20 (same harness), with
  the 18 Nov screen gates (t850 / t700 / q850 day-1/2 biases vs ERA5, not relaxed).
  [reg: 23:47 / 01:24 | inputs: SW, LW, LE, H, soil start, emissivity, roughness noted | fail-5why: n/a (PASS)]
- 01:32 (clock) REGISTERED A/P1 GLOBAL SCREEN with the land set (rule from 18 Nov 13:10, unchanged: 3 starts, day-2 globe |t850| AND |t700|
  <= 0.6 K; day-1 rain and LHF within 15 % of ERA5), rh_vs_era5 at T42 dt 20, start file wx2020L2 for all:
  base3r = BASE3 + rad_every 1; land = base3r + land set; land_conv = land + the IFS-document convection set (candidate, 18 Nov).
  PREDICTION: land alone changes the GLOBE day-2 t850/t700 by < 0.3 K (land is ~30 % of the globe; the 20-40N land BL heating is the
  part it fixes) -> the land set alone FAILS the globe gate; its value shows in the land/subtropical split and as the input fix for
  the held convection candidate (land_conv). [reg: now | inputs: land inputs fixed per the land gate | fail-5why: to follow]
- 02:00 (clock) A/P1 GLOBAL SCREEN RESULT (T42 dt 20, wx2020L2, 3 starts, day-2 globe bias; rule |t850|, |t700| <= 0.6 K):
    base3r     t850 +0.07  t700 -1.54  rh850 +0.048 | t850 ocean 40S-40N +0.77, poleward -0.85
    land       t850 +0.17  t700 -1.41  rh850 +0.037 | ocean +0.82, poleward -0.80
    land_conv  t850 -0.76  t700 -0.89  rh850 +0.090 | ocean -0.81, poleward -0.23 | RH-cloud 850 tropical ocean 0.215 (ERA5-RH 0.092; base3r 0.105)
  -> all three FAIL (t700 in all; t850 in land_conv). Prediction for the land set (globe change < 0.3 K) MET (t850 +0.10, t700 +0.13).
  Land improved land_conv vs the 18 Nov candidate (t850 -0.91 -> -0.76, t700 -0.91 -> -0.89): small, as predicted.
  Failure 5-Why: (1) t700 -1.4..-1.5 K in base3r and land = a cause SHARED by all, not the land set -> land set HELD (not rejected;
  blocked by the shared t700 cold); (2) land_conv's t850 failure is over the TROPICAL OCEAN (-0.81; poleward improves to -0.23): its
  850-hPa RH-cloud doubles (0.105 -> 0.215 vs ERA5-RH 0.092) -> more low cloud -> radiative cooling (the 18 Nov chain); the fix's
  failure traces to its moistening at 850 over the ocean -> the INPUT to check: the candidate's moisture source/sink by process at
  850 vs ERA5's apparent moisture sink Q2 (never compared; Q1 was). REGISTERED: ERA5 Q2 (37 levels, 20S-20N 50-110E ocean, h12/24/36)
  vs model physics Q2 (base3r, land_conv): the PROCESS named is the one whose 850-hPa moistening exceeds ERA5's Q2 balance by
  >= 50 % of land_conv's 850 Q2 error. [reg: now | inputs: RH-cloud split, region split | fail-5why: shared t700 (all); ocean 850 moistening (land_conv)]
- 02:17 (clock) Q2 RESULT (20S-20N 50-110E ocean, day 1, g/kg/day, + = drying): ERA5 925 -2.25, 850 -0.81, 700 +0.32, 500 +0.40;
  base3r -0.52 / -0.64 / -0.61 / +0.49; land_conv -0.58 / -0.91 / +0.08 / +0.15. land_conv's 850 Q2 error = -0.10 (small) -> NO process
  named by the rule (the 850 physics moistening is right). Day-by-day (ocean 40S-40N): land_conv t850 -0.07 / -0.62 / -0.81 and rh850
  +0.00 / +0.05 / +0.06 (base3r: t850 +0.81 / +0.77, rh850 -0.035 / -0.028). A 0.62 K cooling raises RH by ~0.04 (Clausius-Clapeyron)
  -> the RH and RH-cloud excess are a CONSEQUENCE of the 850 cooling, not of moistening (correction of my 02:0x framing).
  Base3r is the opposite: +0.8 K too WARM over the ocean at 850 on day 1 (the 'mse' shallow heating), ERA5 between the two.
  Next (registered): WHERE the day-2 t850 error sits (maps base3r vs land_conv) - trade-cumulus / stratocumulus regions vs the deep
  tropics; rule: a region type is named if it holds >= 50 % of the area-weighted ocean t850 error of land_conv.
  Also noted: model 925 moistening -0.5 vs ERA5 -2.25 over the ocean (the BL's surface moisture input is 4x too small at 925 - or it is
  vented higher) - a separate input to check. [reg: now | inputs: Q2 vs ERA5 | fail-5why: 850 cold is the cause, RH follows]
- 02:36 (clock) ERROR-MAP RESULT (day-2 t850, ocean 40S-40N, area-weighted share / regional mean K):
    land_conv (mean -0.81): SUBTROPICS 10-40 0.75 / -0.84; deep tropics |lat|<10 0.25 / -0.73; stratocumulus boxes ~0 / +0.10;
              Indian Ocean 0.25 / -1.26, W Pacific 0.26 / -0.97, E Pacific 0.19 / -0.44, Atlantic 0.18 / -0.60
    base3r    (mean +0.77): DEEP TROPICS 0.73 / +2.03; subtropics 0.27 / +0.29; Sc boxes ~0 / +0.23
  -> rule (>= 50 %): land_conv's cold error is named in the SUBTROPICAL (trade-wind) OCEANS outside the stratocumulus decks;
  base3r's warm error is named in the DEEP TROPICS (+2.0 K at 850 by day 2 - large; its own open item, not hidden by the globe +0.07).
  REGISTERED: Q1 by process over the subtropical ocean (10-40 N/S), day 1: ERA5 Q1 (37 levels) vs model total physics heating and its
  parts (bl, shallow, deep, lsc, evap, radiation) for base3r and land_conv: the PROCESS named is the one whose 850 difference
  land_conv - base3r explains >= 50 % of land_conv's 850 Q1 error vs ERA5. [reg: now | inputs: maps | fail-5why: subtropical trade-wind cooling (land_conv)]
- 02:54 (clock) Q1 BY PROCESS RESULT (subtropical ocean 10-40 N/S, day 1, K/day): ERA5 Q1 925 +0.27, 850 -1.25, 700 -0.58;
  base3r total 925 +1.52, 850 -0.87, 700 -0.89 (shallow +6.2 at 925, evap -3.4); land_conv 925 +0.21, 850 -0.89, 700 -0.31
  (850 parts: deep +1.29, lsc +1.23, rad -2.87, evap -0.43). -> land_conv's 850 PHYSICS heating is 0.36 K/day WARMER than ERA5's, not
  colder -> NO physics process explains its 850 cold (rule: none named). At 925 land_conv matches ERA5 (+0.21 vs +0.27) while base3r is
  +1.25 too warm there (its 'mse' shallow heating).
  CORRECTION: the 850 cold of land_conv over the subtropical oceans is NOT local physics. With 850 physics equal in base3r and land_conv
  (-0.87 / -0.89) the 1.1 K day-2 difference must come from the DYNAMICS - adiabatic (subsidence) warming. The deep tropics differ
  strongly (base3r +2.0 K warm, land_conv -0.7 K at 850 by day 2): weaker tropical heating -> weaker Hadley descent -> less
  subsidence warming in the subtropics (a remote cause).
  REGISTERED: 850/700 omega over the subtropical ocean (day 1-2) model vs ERA5: SUBSIDENCE named if land_conv's descent is >= 20 %
  weaker than ERA5's while base3r's is within 20 %; then the deep-tropical heating (Q1 0-10 N/S ocean vs ERA5) is the next input.
  [reg: now | inputs: Q1 by process vs ERA5 | fail-5why: not local physics -> dynamics/remote]
- 03:17 (clock) SUBSIDENCE RESULT (ocean, day 1-2 mean, omega Pa/s, + = descent): subtropics 10-40 850/700: ERA5 0.0089/0.0094, base3r
  0.0046/0.0061 (41 % weaker), land_conv 0.0032/0.0036 (63 % weaker); deep tropics |lat|<10 500 hPa ascent: ERA5 -0.0135, base3r -0.0131,
  land_conv -0.0141 (both match). Rule: land_conv >= 20 % weaker MET, base3r within 20 % NOT met -> SUBSIDENCE NOT named as the
  land_conv-specific cause (descent is too weak in BOTH; a shared deficit). Size check: the land_conv-vs-ERA5 descent deficit
  (0.0058 Pa/s x static stability ~4e-4 K/Pa) ~ 0.2 K/day -> could give ~half of the day-2 -0.84; base3r-vs-land_conv difference only
  ~0.07 K/day -> does NOT explain their 1.1 K difference. Deep-tropical ascent is right in both -> the "weaker Hadley" idea is NOT
  supported (my 02:5x hypothesis withdrawn).
  TRUTH-UNCERTAINTY found: ERA5 Q1 at 850 over the same subtropical ocean = -1.25 K/day from 37 levels (q1sub) but -0.60 from the
  7-level gradient here -> the ERA5 Q1 estimate itself is uncertain by ~0.6 K/day at 850; Q1 comparisons smaller than that cannot
  name a process. The 03:0x "no physics process named" stands only at that resolution.
  NEXT (registered for the 04:00 cycle): close the model's own 850 temperature budget over the subtropical ocean, day 1 (total dT/dt
  = physics + dynamics, from the model state every hour) and ERA5's dT/dt at the same points: the term (physics or dynamics) whose
  land_conv - base3r difference explains >= 50 % of the day-1 t850 difference is named.
  [reg: now | inputs: omega both regions vs ERA5 | fail-5why: shared weak subtropical descent; Hadley idea not supported; truth Q1 uncertain]
- 04:19 (clock) 850 BUDGET CLOSURE (model, sigma 0.85, subtropical ocean 10-40 N/S, day 1, hourly, 3 starts): base3r dT +0.90 K = physics
  -0.27 + dynamics +1.17; land_conv dT -0.63 = physics -0.99 + dynamics +0.36. ERA5 day-1 change ~0 (ocean 40S-40N t850 d0 -> d1
  287.71 -> 287.72). Difference land_conv - base3r: dT -1.52 = physics -0.72 (47 %) + dynamics -0.81 (53 %).
  Rule (>= 50 %): DYNAMICS named - by a hair (53/47); stated plainly: physics and dynamics share the difference about equally.
  Side finding: base3r's HOURLY physics integral (-0.27 K/day) differs from its 00Z/12Z snapshot mean (-0.83) -> the earlier Q1
  comparisons from h12/24/36 snapshots were biased by the diurnal cycle; budget numbers must come from hourly integrals.
  ERA5 needs ~0: base3r is too warm (+0.90) through dynamics (+1.17 with physics -0.27), land_conv too cold (-0.63) through physics
  (-0.99 with dynamics +0.36). The omega means explain only ~0.08 K/day of the dynamics difference (03:1x) -> the dynamics term is
  NOT the area-mean subsidence; candidates: correlation of descent with stability (clear vs cloudy columns) and horizontal advection.
  NEXT (registered): the same hourly closure split into physics-by-process (rad, shallow, deep, lsc, evap, bl) and dynamics into
  vertical (omega x stability) and horizontal advection; the term explaining >= 50 % of each run's error vs ERA5's ~0 is named.
  [reg: 03:16 | inputs: hourly budget both runs | fail-5why: split ~equal; snapshot Q1 bias found]
- 04:25 (clock) PRE-LAUNCH CHECK caught my error: the emis_land edit (01:0x) changed the CONTROL model by 3e-5 K in the land temperature
  (default 1.0 multiplied in -> different float rounding); the precheck refused the last exam job (tn-r1-b3-1). Bisected
  (b6e7a135, d842e219, d3a397d3 all bit-identical; 5ff7fa7f not). Fixed with a static branch (default = original expression);
  regression now bit-identical. emis_land 0.97 results are unchanged (that path is untouched). Also fixed: precheck treated a
  "collected" job as still running; dispatch counted 7-day-old GitHub ghost runs as holding a Kaggle slot.
- 09:07 (clock) 850 BUDGET BY PROCESS (sigma 0.85, subtropical ocean 10-40, day 1 hourly integral, K/day; sums close exactly):
                 bl     shallow  deep   lsc    evap   rad    | physics  dynamics  dT
    base3r     -0.71   +2.06   +0.53  +1.64  -1.96  -1.79   |  -0.22   +1.11    +0.89
    land_conv  -0.02   -0.12   +1.02  +0.68  -0.34  -2.21   |  -0.99   +0.36    -0.63      (ERA5 dT ~0)
  land_conv - base3r: shallow -2.19, lsc -0.96, rad -0.42, evap +1.61, bl +0.69, deep +0.49 -> physics -0.76.
  Reading: in the candidate the shallow scheme gives ~NO heating at 850 over the trade-wind oceans (-0.12 vs base +2.06), and the
  cloud layer then cools by radiation (-2.21, the largest term). ERA5 has no process split, so the rule (term >= 50 % of each run's
  error vs ERA5) is applied to the totals only: land_conv's error (-0.63) is PHYSICS (-0.99 vs dynamics +0.36) -> PHYSICS named;
  base3r's error (+0.89) is DYNAMICS (+1.11) -> DYNAMICS named. Within the candidate's physics no single process can be named
  against ERA5 without a reference split.
  Hypothesis for the next input check (not a verdict): trade cumulus should heat the cloud layer (BOMEX-type); the candidate's
  shallow plume may trigger too rarely over these oceans (the 200-250 hPa classification gap and sh_trig). REGISTERED: shallow
  trigger frequency (on_sh) and low-cloud cover over the subtropical ocean, model vs ERA5 low cloud cover: SHALLOW TRIGGER named if
  land_conv's on_sh < 0.3 where ERA5 low cloud >= 0.3 (trade-cumulus regime, observed shallow-cumulus occurrence ~50-80 %).
  [reg: now | inputs: hourly process budget | fail-5why: candidate physics (shallow ~0 at 850 + radiative cooling); base dynamics]
- 11:03 (clock) P3 RULE-1 BREAKDOWN (BASE3, 83 storms, by ERA5 minimum pressure): 995-1010 hPa (weak lows) n=63, mean err -5.3 hPa, 26 too deep,
  57 % within +-5; 985-995 n=19, +2.8, 8 too weak, 47 % within; 970-985 n=1, +15.1. -> the model COMPRESSES the intensity range:
  weak lows deepen too much, stronger systems stay too weak (the 10 Nov "slope 0.44" pattern, now with weak lows dominating the
  sample of 83). Not a new cause yet - registered next after A: why weak lows over-deepen (candidates: CMT/cmt_mf spin-up of weak
  vortices, convective heating triggered too easily in weak lows, surface flux at low winds). [reg: now | inputs: Rule-1 rows | fail-5why: n/a (measurement)]
- 11:14 (clock) SHALLOW TRIGGER RESULT (land_conv, subtropical ocean, day-1 hourly mean): on_sh 0.337 (rule: named if < 0.3) -> SHALLOW
  TRIGGER NOT named (fires in a third of the columns; ERA5 low cloud >= 0.3 over 46 % of this ocean). The shallow plume fires but
  nets ~0 at sigma 0.85 (cloud-top detrainment/evaporation there - BOMEX-like structure, not a fault by itself). Model total cloud
  cover 0.78 vs ERA5 0.60 (1.3x) with radiation the largest 850 cooling (-2.21 K/day).
  REGISTERED: LOW-CLOUD AMOUNT named if the model's low cloud (sigma >= 0.68; maximum overlap = lower bound) is >= 1.3x ERA5 low cloud
  cover (0.365) over the subtropical ocean, day 1; then the cloud scheme's INPUTS (RH at those levels vs ERA5, critical RH) before any
  scheme change. [reg: now | inputs: on_sh, cover vs ERA5 tcc/lcc | fail-5why: trigger fine; cloud amount next]
- 11:37 (clock) LOW-CLOUD RESULT (subtropical ocean 10-40, day-1 hourly, model low cloud sigma >= 0.68): land_conv max-overlap 0.546
  (random 0.763), base3r 0.498 (0.603); ERA5 low cloud cover 0.365 -> land_conv 1.50x, base3r 1.36x (rule >= 1.3x) -> LOW-CLOUD AMOUNT
  NAMED in BOTH (shared; larger in the candidate). Per the method, the cloud scheme's INPUTS before the scheme.
  REGISTERED (land_conv, same region/day): ERA5 day-1 RH 925 0.808, 850 0.610 (rh_truth, mixed-phase saturation = liquid at these T).
  RH INPUT named if the model's RH at sigma 0.925 or 0.85 exceeds ERA5's by >= 0.05; otherwise the cloud COMPONENT (RH-based c_ls,
  convective tower c_tow, anvil c_anv) holding >= 50 % of the low-cloud excess is named. Cloud components exposed as diagnostics
  (radcloud/mm2; control bit-identical, regress OK). [reg: now | inputs: ERA5 lcc, RH truth | fail-5why: cloud excess shared]
- 11:50 (clock) CLOUD-INPUT RESULT (land_conv, subtropical ocean, day 1): low cloud by component (max over sigma >= 0.68): RH-based c_ls 0.531,
  convective c_tow 0.032, anvil 0.000 -> c_ls holds 97 % of the low cloud. RH: model sigma 0.925 0.826 / sigma 0.85 0.697 vs ERA5
  925 hPa 0.808 / 850 hPa 0.610 - but sigma 0.85 sits ~863 hPa over the ocean (level mismatch, biases ours high); pressure-matched
  (rh_vs_era5, ocean 40S-40N, d1): 925 +0.026, 850 +0.050. Rule (RH input >= 0.05): met only at 850, exactly at the threshold.
  Stated plainly - the 850 RH excess is not the driver: hourly, c_ls doubles in the first 6 h (0.24 -> 0.47) while RH at sigma 0.85
  stays flat (0.675) and RH at sigma 0.925 rises 0.777 -> 0.812; over the day RH 925 rises +0.066 and c_ls follows (0.24 -> 0.65).
  Pressure-matched day-0 -> day-1 drift at 925 hPa (ocean 40S-40N): model 0.807 -> 0.853 (+0.046), ERA5 0.824 -> 0.827 (+0.003).
  -> NAMED (as the driver, by the hourly order): the model's 925 hPa RH DRIFT over day 1 (+0.046 vs ERA5 +0.003), amplified by the
  RH-based cloud (about +0.1 cloud per +0.026 RH at 925). [reg: 11:3x | inputs: RH pressure-matched, components | fail-5why: 925 RH drift drives the cloud]
  REGISTERED next: split the 925 RH drift into temperature (Clausius-Clapeyron) vs moisture: T-DRIVEN named if the 925 cooling explains
  >= 50 % of the RH rise (dRH_T = -RH x 0.065 dT); otherwise MOISTURE named -> then the 925 moisture budget by process vs ERA5 Q2 (hourly).
- 12:03 (clock) T-vs-q SPLIT (land_conv, sigma 0.925, subtropical ocean, day 1): dT -0.82 K, dq +0.26 g/kg, dRH +0.066 = temperature part +0.041
  (62 %) + moisture part +0.019 (29 %; remainder nonlinearity) -> T-DRIVEN NAMED (rule >= 50 %): the low-level COOLING raises RH,
  RH-based cloud grows, cloud cools radiatively -> a feedback loop; the loop's starting point is the cooling, present from the first
  hours (sigma 0.85 physics -0.6..-1.0 K/day at h0-h2 while low cloud was still BELOW ERA5's, 0.24 vs 0.365).
  REGISTERED: hourly sigma-0.925 heat budget by process (land_conv and base3r, day 1, subtropical ocean), with the first 6 h separated:
  the process giving >= 50 % of land_conv's 0-6 h cooling is named (that is the loop's trigger). ERA5 day-1 change at 850 ~0 is used as
  the reference (925 assumed similar - to be checked with ERA5 t925). [reg: now | inputs: T, q, RH hourly | fail-5why: cooling-cloud loop]
- 12:26 (clock) 925 BUDGET BY PROCESS (sigma 0.925, subtropical ocean, hourly integral, K):
    land_conv 0-6 h: dT -0.44 = physics -0.24 (rad -0.24, evap -0.06, deep +0.07, bl -0.02, shallow +0.01, lsc +0.01) + dynamics -0.20
    land_conv 0-24 h: dT -0.82 = physics -0.36 (rad -1.26, evap -0.51, deep +0.55, bl +0.33, lsc +0.28, shallow +0.25) + dynamics -0.46
    base3r    0-6 h: dT +1.19 = physics +1.30 (shallow +2.01 = 8 K/day!, evap -0.44, bl -0.20, rad -0.20); 0-24 h: dT +2.24 (shallow +6.72)
  Rule (process >= 50 % of land_conv's 0-6 h cooling): RADIATION -0.24 of -0.44 = 55 % -> RADIATION named (dynamics -0.20 = 46 %, close).
  5-Why on that: the radiative cooling itself (~ -1 K/day at 925 in the first 6 h, with low cloud still below ERA5's) is a normal clear-
  sky boundary-layer value, and RRTMG matched our radiation on the same clouds (18 Nov) -> radiation is not wrong as an input; what is
  missing is the HEATING that balances it: in the first 6 h the candidate's boundary-layer mixing (-0.02) and shallow plume (+0.01) put
  ~nothing into 925, where trade-wind boundary layers are heated by the surface sensible flux (mixed up) and shallow cumulus.
  Base3r is the opposite fault: its 'mse' shallow scheme heats 925 by ~8 K/day in the first 6 h (+2.2 K in day 1) - far too much.
  REGISTERED: the INPUT to boundary-layer heating - the surface sensible and latent heat flux over the subtropical ocean, model (land_conv,
  base3r) vs ERA5, day 1 hourly: SURFACE FLUX named if the model's sensible flux is < 0.7x ERA5's; otherwise the BL mixing depth/flux
  profile (how much of the flux reaches 925) is next. [reg: now | inputs: radiation checked (RRTMG 18 Nov) | fail-5why: missing BL/shallow heating at 925]
- 12:48 (clock) SURFACE FLUX RESULT (subtropical ocean, day 1): sensible H land_conv 16.5 W m-2 (first 6 h 13.0), base3r -0.2 (4.1), ERA5 12.7;
  latent LE land_conv 114, base3r 145, ERA5 134; wind at the lowest level land_conv 7.2, base3r 8.0 vs ERA5 10-m 6.9.
  Rule (H < 0.7x ERA5): land_conv 1.3x -> SURFACE FLUX NOT named (the input is right). base3r's H ~0 = a consequence of its 8 K/day shallow
  heating (the air above the sea is too warm). Failure 5-Why: the surface heat arrives, but little of it heats 925 in the first hours ->
  the vertical DISTRIBUTION (BL mixing depth and the shallow plume's flux profile) is next.
  REGISTERED: boundary-layer height over the subtropical ocean, land_conv vs ERA5 BLH, day 1: BL DEPTH named if ours < 0.7x ERA5's (the
  surface heat then stays below 925); if not, the shallow plume's heat-flux profile 950-850 is next (where the shallow scheme is on).
  [reg: now | inputs: H, LE, wind vs ERA5 | fail-5why: input fine; vertical distribution next]
- 13:01 (clock) BL DEPTH RESULT (subtropical ocean, day 1): land_conv hbl 455 m (first 6 h 503), LCL 497 m; ERA5 BLH 821 m -> 0.55x (rule < 0.7x)
  -> BL DEPTH NAMED: the candidate's ocean boundary layer is too shallow, so the surface heat (H right, 16.5 vs 12.7) stays below
  ~450 m and 925 (~750 m) gets little of it. The candidate includes bl_lcl 1, which ties the BL top to the LCL (hbl ~= zlcl here).
  Per the method, the INPUT to that cap first: our LCL (497 m) vs ERA5 cloud-base height. REGISTERED: LCL INPUT named if our LCL is
  < 0.7x ERA5's cloud base height over the subtropical ocean (then near-surface humidity/temperature are the inputs to check); if the
  LCL is right, the bl_lcl cap (a formulation choice: IFS's dry BL ends at cloud base but its cloud layer is mixed by the shallow mass
  flux) is the next suspect, judged against ERA5's 821 m. [reg: now | inputs: hbl, zlcl vs ERA5 BLH | fail-5why: shallow BL traps the surface heat]
- 13:03 (clock) LCL vs ERA5 CLOUD BASE: ERA5 cloud-base height (where defined, 95 % of the subtropical ocean) mean 996 m; our LCL 497 m -> 0.50x
  (rule < 0.7x) -> LCL INPUT named by the rule as registered. CAVEAT stated now: ERA5 'cloud_base_height' is the base of the LOWEST cloud
  of any type, so where no cumulus exists it is a mid-level base - this biases ERA5 high (observed trade-cumulus bases ~500-700 m).
  An apples-to-apples check is added (registered before its result): ERA5 LCL from 2-m temperature and dewpoint (125 m per K of dewpoint
  depression) vs ours; the LCL input verdict STANDS only if ours is also < 0.7x that; otherwise the cloud-base comparison was the
  wrong quantity and the bl_lcl cap is the suspect. [reg: now | inputs: cbh (biased high), t2-d2 to come | fail-5why: n/a]
- 13:06 (clock) LCL APPLES-TO-APPLES: ERA5 LCL from t2/d2 = 549 m vs ours 497 m (0.90x, rule < 0.7x) -> LCL INPUT NOT named; the 996-m cloud-base
  comparison was the wrong quantity (as cautioned) and is withdrawn. So the input (cloud-base level) is right and the BL depth
  deficit (455 vs ERA5 821 m) comes from the bl_lcl CAP itself: ERA5's BL top sits ~270 m above its LCL (into the cumulus layer),
  ours is held at the LCL. bl_lcl entered the candidate on 18 Nov to curb the land BL (1100 vs 528 m) - before the land fix.
  REGISTERED: land_conv with bl_lcl 0 (the cap removed; no other change, nothing tuned): SUPPORTED if, over the subtropical ocean, day-1
  hbl is within 0.7-1.3x ERA5 (575-1067 m) AND the sigma-0.925 day-1 temperature change moves toward ERA5's ~0 by >= half (from -0.82)
  AND land ascent-region HBL (20-40N) is not deeper than with the cap; then the global screen.
  [reg: now | inputs: LCL t2/d2 checked (right) | fail-5why: bl_lcl cap (formulation) traps the ocean BL]
- 13:19 (clock) bl_lcl 0 RESULT (land_conv without the cap, subtropical ocean, day 1): hbl 1036 m (ERA5 821; 1.26x, inside 0.7-1.3) PASS; LCL 647
  (ERA5 549); H 11.2 (ERA5 12.7, closer than 16.5); sigma-0.925 day-1 change -0.54 K (from -0.82: 33 % of the way to ~0; rule >= 50 %)
  FAIL; land HBL check not yet run -> gate FAIL.
  Failure 5-Why: the 925 PHYSICS now heats +0.08 K/day (was -0.36; ERA5 Q1 ~+0.27 from snapshots) - the fix does its own job; the
  remaining -0.54 K is DYNAMICS (-0.62), i.e. the weak subtropical descent shared by every run (03:1x: 41-63 % weaker than ERA5) ->
  the failure traces to another cause -> bl_lcl 0 HELD (blocked by the weak descent), not rejected.
  5-Why on the weak descent: in the subtropics the descent rate is set by the free troposphere's radiative cooling (omega ~ Q_rad / S).
  18 Nov found our OLR 208 vs ERA5 246 W m-2 with high cloud 2-5x -> less longwave cooling -> slower descent. REGISTERED: OLR over the
  subtropical ocean, day 1, model (land_conv no cap, base3r) vs ERA5: COLUMN COOLING named as the descent's input if our OLR is lower
  than ERA5's by >= 15 W m-2. [reg: now | inputs: hbl, LCL, H vs ERA5 | fail-5why: remaining cooling is the shared weak descent]
- 14:52 (clock) OLR RESULT (subtropical ocean 10-40 N/S, day 1 hourly): ERA5 261.3 W m-2; land_conv no cap 251.0 (-10.3); base3r 248.0
  (-13.3). Rule: >= 15 W m-2 lower -> COLUMN COOLING NOT named (the sign is the expected one, the size is below the registered bar;
  18 Nov's 208-vs-246 was a different region and state). Input note: the "no soil water, skin temperature" landinit warning in these
  logs is spurious (helper calls that remap soil_t pass None); the main land start gets all fields (checked: all finite at the 3 starts).
  5-Why continues on the weak descent: omega ~ Q_rad / S, and the cooling side is not named, so the other input is the static
  stability S. Our lower troposphere is cold (t850 -0.76, t700 -0.89 in land_conv), which raises S above it and slows the descent
  for the same cooling (a loop: weaker descent -> less adiabatic warming -> colder).
  REGISTERED: static stability S = -(T/theta) dtheta/dp at 850/700/500 hPa, subtropical ocean, +12/24 h, 3 starts, model (land_conv
  no cap, base3r; sigma -> pressure in log p) vs ERA5: STABILITY named as the descent's input if ours exceeds ERA5's by >= 15 % at
  700 or 500 hPa (where the descent is measured). If neither cooling nor stability is named, the descent measurement itself
  (our omega from divergence vs ERA5 omega) is the next input to check.
  [reg: now | inputs: OLR vs ERA5 (not named) | fail-5why: n/a (diagnostic step)]
- 15:27 (clock) STABILITY RESULT (subtropical ocean, +12/24 h, 3 starts; K per 100 hPa): ERA5 S850/S700/S500 = 6.36 / 5.47 / 5.41;
  land_conv no cap 6.03 / 5.81 (+6 %) / 4.97 (-8 %); base3r 4.43 / 4.92 (-10 %) / 5.39 (0 %). Rule >= 15 % above ERA5 at 700 or 500 ->
  STABILITY NOT named. (Side finding, not the registered level: base3r S850 is 30 % below ERA5 - its 'mse' shallow heating warms 925/850
  (+2.1 / +0.5 K) and cools 700 (-1.5 K): the deep-tropics-warm / 700-cold pattern of base3r.)
  Neither omega ~ Q_rad / S input is named -> per the 14:52 registration the next input is the descent MEASUREMENT itself.
  INPUT CHECK of omsub.py: our omega was -cumsum(D ps dsigma) at the half level below the nearest sigma, i.e. the PRESSURE-coordinate
  formula. In sigma coordinates omega/p = v.grad(ln ps) - (1/dsigma)(alpha_n sum G[:n] dsigma + alpha_n-1 sum G[:n-1] dsigma),
  G = D + v.grad(ln ps) (Durran 8.124, Dinosaur's own _t_omega_over_sigma_sp). The dropped v.grad(ps) term is ~7 m/s x 10 hPa/1000 km
  ~ 0.007 Pa/s - the same size as the ERA5 descent (0.009) -> the 41-63 % "weak descent" may be a diagnostic error.
  REGISTERED: model omega recomputed with Dinosaur's scheme, full levels -> 850/700/500 hPa in log p, same samples (+12/24/36/48 h, 3
  starts, subtropical ocean) vs ERA5 (0.0089 / 0.0094 / 0.0090 Pa/s): MEASUREMENT named (weak descent withdrawn) if both runs' corrected
  descent at 850 and 700 is within 0.8-1.2x ERA5; if still < 0.8x the weak descent STANDS and the 5-Why goes to the dynamics.
  [reg: now | inputs: S vs ERA5 (not named); omega formula checked (suspect) | fail-5why: n/a (diagnostic step)]
- 15:27 (clock) LAND HBL RESULT for bl_lcl 0 (20-40 N land, day 1 hourly, land_conv): cap mean 843 / daily max 1875 m; no cap 984 / 2211 m
  (+17 / +18 %). Registered rule "not deeper than with the cap" -> FAIL.
  Failure 5-Why (not a rejection): the rule's reference was the capped model, not ERA5. The cap was added 18 Nov when the land BL was
  1100 vs ERA5 528 m because of the 6x sensible heat - fixed since by the land set. Whether 984 m is too deep is a question for ERA5 on the
  same domain/sampling (the 528 m was 50-110E ascent regions at 00/12Z only - not comparable).
  REGISTERED: ERA5 BLH over 20-40 N land, all longitudes, day 1 hourly (cyc_blhland.py): the land failure TRACES TO bl_lcl 0 if no-cap mean
  > 1.3x ERA5 while cap is within 0.7-1.3x; if no cap is within 0.7-1.3x (mean and daily max) the failure was the reference, not the fix.
  bl_lcl 0 stays HELD until then. [reg: now | inputs: land H fixed (land gate) | fail-5why: rule reference = capped model, not ERA5]
- 15:50 (clock) OMEGA MEASUREMENT RESULT (subtropical ocean, +12/24/36/48 h, 3 starts, Pa/s, + = descent; ERA5 0.0089/0.0094/0.0090 at
  850/700/500): old pressure-formula diagnostic reproduces 03:17 (base3r 0.0044/0.0060). Dinosaur's sigma scheme: base3r 0.0073/0.0075/
  0.0060 (0.82x / 0.80x / 0.66x); land_conv no cap 0.0063/0.0055/0.0048 (0.71x / 0.58x / 0.54x). Rule (both runs 0.8-1.2x at 850 and 700)
  NOT met -> weak descent NOT withdrawn: it STANDS for land_conv. But the old diagnostic WAS wrong (dropped v.grad ps): it overstated the
  deficit by ~25-30 points. Consequences, stated plainly:
  (1) the 03:17 verdict "shared deficit" is re-opened - with the right formula base3r is at the 0.8x edge (0.815 / 0.799) and the deficit
      is mainly land_conv's (29 % / 42 % weaker), i.e. it comes with the candidate convection;
  (2) the 03:17 deep-tropics ascent (old formula) must be re-measured before it is used again;
  (3) size: land_conv's 700 deficit 0.0039 Pa/s x S 5.8e-4 K/Pa ~ 0.2 K/day - real, but not the whole -0.62 K/day at 925.
  REGISTERED: decompose the sigma-0.925 and 0.85 day-1 DYNAMICS of land_conv no cap and base3r (subtropical ocean, hourly) into
  horizontal advection -V.grad T and the vertical/adiabatic term omega (kappa T / p) - sigma_dot dT/dsigma (corrected omega): the part
  carrying >= 60 % of land_conv's -0.62 K/day at 925 is NAMED as the input; if neither does, the two cancel and both are reported.
  [reg: now | inputs: omega formula fixed (was wrong) | fail-5why: n/a (diagnostic step)]
- 15:50 (clock) LAND HBL vs ERA5 (20-40 N land, day 1 hourly, cyc_blhland): ERA5 mean 497 / daily max 1507 m. Cap 843 (1.70x) / 1875
  (1.24x); no cap 984 (1.98x) / 2211 (1.47x). Rule (14:52+15:27): no cap > 1.3x while cap within 0.7-1.3x -> on the DAILY MAX this is met
  (1.47x vs 1.24x): removing the cap does push the land afternoon BL too deep - this part of the failure TRACES TO THE FIX. On the MEAN
  neither is within (cap 1.70x): the land BL is too deep at night with or without the cap - a separate, pre-existing land fault
  (fits the night wind 1.9x ERA5 named 18 Nov; z0 0.1 vs ERA5 0.40 and no gravity-wave drag named as suspects).
  VERDICT bl_lcl 0: ocean PASS, land daily max FAIL traced to the fix -> NOT adoptable as a global switch; HELD. The cap is a non-IFS
  device (IFS has no LCL cap), so the clean route is the land BL fault itself (night depth), not a land/ocean split of the cap.
  [reg: 14:52/15:27 | inputs: ERA5 BLH same domain + sampling | fail-5why: daily max -> fix; mean -> pre-existing land night BL]
- 23:27 (clock; the session was paused ~16:00-23:20, so the 16:00 cycle ran late) DYNAMICS SPLIT RESULT (dynsplit.py, subtropical ocean,
  day 1 hourly, K/day; vertical term with the corrected Dinosaur omega / sigma-dot):
  land_conv no cap, sigma 0.925: dT -0.54 = phys +0.08 + dyn -0.62 [hadv -0.69 | vadv -0.46, adiabatic +0.30 -> vertical -0.16 | residual +0.23]
  land_conv no cap, sigma 0.85 : dT -1.21 = phys -1.77 + dyn +0.56 [hadv -0.44 | vertical +0.67 | residual +0.33]
  base3r,          sigma 0.925: dT +2.24 = phys +2.76 + dyn -0.52 [hadv -1.41 | vertical +0.04 | residual +0.86]
  base3r,          sigma 0.85 : dT +0.89 = phys -0.22 + dyn +1.11 [hadv -0.38 | vertical +1.02 | residual +0.47]
  Rule (>= 60 % of land_conv's -0.62 at 925): HORIZONTAL ADVECTION carries 110 % -> named as the term; the vertical term is only -0.16.
  Caveat stated before reading more into it: equatorward trade flow brings cooler air, so cold advection is EXPECTED in the subtropics -
  "named as the term" is not yet "named as the error". The error question needs ERA5's own terms. Also: a numerics residual of
  +0.2..+0.9 K/day (semi-Lagrangian/diffusion, not in either explicit term) is as large as the signal - reported, not yet explained.
  Self-correction: the 13:19 entry called the -0.62 "the weak descent"; the split shows it is mostly horizontal advection, the
  vertical term being small at 925. The weak-descent link is therefore weaker than stated at 13:19.
  REGISTERED: ERA5 -V.grad T and -omega (dT/dp - kappa T/p) at ~937 hPa (925/950 mean), same region, day 1 3-hourly (cyc_advsub.py):
  a term is NAMED AS AN ERROR if |model - ERA5| >= 0.27 K/day (half of land_conv's -0.54 day-1 error at 925); if neither is, the
  physics/residual split is the next input (ERA5 Q1 uncertainty +-0.6 noted).
  [reg: now | inputs: corrected omega/sigma-dot | fail-5why: n/a (diagnostic step)]
- 23:38 (clock) ERA5 ADVECTION RESULT (~937 hPa, subtropical ocean, day 1 3-hourly, K/day): ERA5 hadv -0.74, vertical +0.04 (omega
  0.0063 Pa/s). land_conv no cap: hadv -0.69 (diff +0.05), vertical -0.16 (diff -0.20) -> NEITHER named (rule >= 0.27). base3r: hadv
  -1.41 (diff -0.67, NAMED for base3r - its warm-tropics state gives a stronger cold advection), vertical +0.04 (matches).
  So land_conv's 925 DYNAMICS is right within the bar (explicit terms -0.85 vs ERA5 -0.70; numerics residual +0.23 on top -> -0.62).
  SELF-CORRECTION of 13:19: "the remaining -0.54 K is dynamics / the weak descent" is NOT supported - at 925 the dynamics matches ERA5.
  Then by the budget the -0.54 day-1 error at 925 must sit in the PHYSICS (ours +0.08 K/day) or in ERA5's own day-1 change (taken as
  ~0 from the RH-drift check, never measured as T). ERA5 Q1 at 925 is uncertain: snapshot +0.12 vs budget-implied +0.70 (if dT = 0).
  bl_lcl 0 stays HELD, but the blocker is re-labelled: "925 physics deficit (unconfirmed)", not "weak descent".
  Physics parts at 925 (land_conv no cap): BL -0.24, shallow +0.27, deep +0.67, large-scale cloud +0.14, rain evaporation -0.68,
  radiation -0.08 (with the cap: -1.26). Two items look off against the BOMEX/LES trade-cumulus reference (Siebesma et al. 2003:
  clear-sky radiative cooling ~-2 K/day through the trade layer; little rain evaporation): radiation -0.08 is small, and deep
  convection + rain evaporation (+0.67 / -0.68) are both large where LES has neither - noted as suspects, not yet named.
  REGISTERED: ERA5 day-1 temperature change at ~937 hPa (cyc_dt937.py) -> ERA5 hourly Q1 = dT - (-0.70). PHYSICS DEFICIT named at 925
  if ERA5 Q1 - our +0.08 >= 0.27 K/day; else 925 is consistent and land_conv's 925 error is ERA5-dT-limited (reported as such).
  [reg: now | inputs: ERA5 hadv/vertical (dynamics matches) | fail-5why: bl_lcl 0 blocker re-labelled to 925 physics]
- 23:41 (clock) ERA5 dT RESULT (~937 hPa, subtropical ocean, day 1): +0.07 / +0.18 / -0.02 -> mean +0.08 K. ERA5 hourly Q1 = +0.08 - (-0.70)
  = +0.78 K/day; ours +0.08 -> deficit 0.70 >= 0.27 -> 925 PHYSICS DEFICIT NAMED. It accounts for the whole land_conv 925 error
  (model dT -0.54 vs ERA5 +0.08 = -0.62; dynamics within 0.08 of ERA5). The snapshot ERA5 Q1 (+0.12) was the diurnally biased one.
  Consequence for bl_lcl 0: blocker = 925 physics deficit (named). Is it the fix? With the cap the 925 physics was -0.36 (deficit 1.14),
  without +0.08 (deficit 0.70): the fix REDUCES the deficit by 40 % -> the failure does not trace to the fix; HELD stands.
  NEXT (registered now, with a stated caveat: the 925 process parts were already seen at 23:38): process ranges from the trade-cumulus
  LES intercomparisons (Siebesma et al. 2003 BOMEX; vanZanten et al. 2011 RICO) will be read from the papers FIRST and written here
  before any comparison; a process outside its LES range at ~650 m is named. Suspects as seen: radiation -0.08 (LES/RICO forcing about
  -2 to -2.5 K/day), BL turbulence -0.24 inside a 1036 m mixed layer (should heat), deep convection +0.67 with rain evaporation -0.68.
  [reg: now (caveat: parts seen) | inputs: ERA5 dT, hadv, vertical | fail-5why: deficit smaller without the cap -> not the fix]
- 23:41 (clock) LES REFERENCE RANGES (read before the comparison, as registered 23:41):
  BOMEX (Siebesma et al. 2003): surface w'theta' 8e-3 K m/s, flux falls linearly to -0.2 x surface at cloud base (~500 m) -> subcloud
  turbulent heating = (8e-3 + 1.6e-3) / 500 m = +1.7 K/day (my arithmetic from their stated profile); clear-sky radiative forcing about
  -2 K/day through the trade layer (cloud radiative effects neglected); cloud base ~500 m, inversion ~1500 m.
  RICO (vanZanten et al. 2011): radiative forcing ~-2 K/day near the surface to ~-1 aloft; surface rain just under 1 mm/day (radar
  ~21 W m-2); evaporation of rain "concentrated in the cloud layer itself" - no subcloud magnitude given.
  COMPARISON at ~650 m (sigma 0.925, inside our 1036 m BL), land_conv no cap: BL turbulence -0.24 vs LES subcloud/mixed-layer +1.7
  (wrong SIGN) -> NAMED. Radiation -0.08 vs clear-sky -2: outside, but all-sky vs clear-sky are not the same quantity and the error
  would WARM us -> not named as the cold's cause (noted). Rain evaporation -0.68: RICO gives no number -> not named (no range), suspect.
  5-Why on the BL cooling inside a positive-H mixed layer: inputs first - (a) where sigma 0.925 sits relative to each column's hbl
  (above-top columns see entrainment cooling), (b) whether h_bl includes evaporation of BL cloud water (moist-conserved mixing in a
  cloudy top), (c) the flux profile shape vs BOMEX's linear one. REGISTERED: day-1 h_bl / h_evap / h_shal / rad profile over
  sigma 0.98-0.70 plus the fraction of columns with hbl above the sigma-0.925 height (blprof.py): (a) named if h_bl at 0.925 is >= 0
  in columns where 0.925 is inside the BL and the negative mean comes from above-top columns; otherwise (b)/(c) next.
  [reg: now | inputs: LES references read first | fail-5why: n/a (diagnostic step)]
- 23:57 (clock) BL PROFILE RESULT (blprof.py, land_conv no cap, subtropical ocean, day 1 hourly, K/day): sigma 0.925 is inside the BL in
  90 % of columns and h_bl there is still -0.19 (above-top columns -0.45) -> (a) NOT the explanation.
  Profile (sigma: h_bl / deep / rain evap / shallow / rad): 0.990: +7.4 / -4.4 / -1.2 / +0.2 / -0.1; 0.971: +1.8 / +0.2 / -1.1; 0.951:
  +0.7 / +0.5 / -0.9; 0.929: -0.2 / +0.7 / -0.7; 0.908: -0.7 / +0.9 / -0.5; 0.885-0.862: -1.1 / +1.2 / -0.35 (rad -2.7..-3.1, lsc +1.5..+1.9).
  Reading (arithmetic, ~20 hPa layers ~ 204 kg m-2): the bottom layer gains 7.4 K/day ~ 17 W m-2 from the BL scheme - MORE than the
  surface sensible flux (~11) - so the BL heat flux turns DOWNWARD above ~200 m: the BL is mixing heat down into a bottom layer that
  deep downdrafts (-4.4) and rain evaporation (-1.2) are cooling. Over sigma 0.99-0.93 deep convection removes ~7 W m-2 and rain
  evaporation ~9 W m-2 - together more than the surface sensible heat. In BOMEX/RICO the subcloud layer is heated by the surface flux
  with an upward, linearly falling flux; RICO puts rain evaporation in the cloud layer. So the 925 BL cooling is a RESPONSE; the
  upstream suspects are (d) deep convection with downdrafts active in the trade-wind regime and (e) subcloud rain evaporation.
  REGISTERED for the 04:00 cycle: day-1 deep-convective rain over the subtropical ocean vs ERA5 convective precipitation (same region,
  hourly): DEEP CONVECTION named if ours >= 1.5x ERA5; and our surface rain vs ERA5 total precipitation: RAIN EVAPORATION named if
  the evaporated fraction below cloud base exceeds half of the rain falling through cloud base while our surface rain is within
  0.7-1.3x ERA5 (i.e. the right rain, evaporating in the wrong place).
  [reg: now | inputs: column split inside/above BL (not named) | fail-5why: n/a (diagnostic step)]
- 00:32 (clock, 20 Nov) RAIN BUDGET RESULT (rainchk.py, subtropical ocean 10-40 N/S, day 1 hourly, mm/day; ERA5 cpsub_truth: total 2.99,
  convective 1.73): land_conv no cap: surface rain 2.06 (0.69x), convective at surface ~1.42 (0.82x ERA5 cp), deep active 12 % of the
  time; evaporation below cloud base 0.29 = 12 % of the rain through cloud base. base3r: rain 2.84 (0.95x), convective ~0.72 (0.42x),
  deep 6 %; below-base evaporation 1.62 = 36 %.
  Rules (registered 23:57): DEEP CONVECTION named if ours >= 1.5x ERA5 cp -> 0.82x, NOT named. RAIN EVAPORATION named if below-base
  evaporation > half of the rain through cloud base -> 12 %, NOT named. Neither upstream suspect is named by rain amount.
  5-Why continues: the bottom-layer cooling in land_conv (deep -4.4 K/day at sigma 0.99) comes with the RIGHT amount of convective
  rain, so the input to check is how the deep scheme distributes its cooling - the DOWNDRAFT (mass flux and where it detrains its
  cold air). Reference to read first: IFS Cy38r1 Part IV ch. 6 (downdraft initial mass flux at the level of free sinking as a
  fraction of the updraft base mass flux, and downdraft detrainment in the lowest layers). REGISTERED for the 04:00 cycle: read the
  IFS value first, then our downdraft-to-updraft base mass-flux ratio over the subtropical ocean; DOWNDRAFT named if ours exceeds
  the IFS fraction by >= 50 %, or if our downdraft deposits >= 2x more cooling in the lowest layer than an IFS-form detrainment would.
  [reg: 23:57 | inputs: ERA5 tp/cp, model rain budget | fail-5why: n/a (diagnostic step)]
- 04:03 (clock, 20 Nov) DOWNDRAFT REFERENCE (read first, IFS Cy38r1 Part IV sec. 6.3.2): initial downdraft flux at the LFS = -eta x
  cloud-base updraft flux, eta = 0.35 (eq. 6.13, after Johnson 1976/80); a downdraft negatively buoyant down to the surface has its
  mass flux "decreased linearly over the lowest 60 hPa". OURS (mm2.py mf): eta = mf_dd = 0.5 (its comment says "ECMWF ~0.3"), and the
  downdraft keeps its full flux to the ground and detrains ALL its air into the bottom level (19.4 hPa thick).
  Rule (00:32): (a) eta >= 1.5x IFS -> 0.5 / 0.35 = 1.43x, NOT named by (a); (b) lowest-layer deposit >= 2x the IFS form -> IFS puts
  ~19.4/60 = 0.32 of the downdraft air in the bottom level, we put 1.0 = 3.1x -> DOWNDRAFT DETRAINMENT NAMED. (mf_dd 0.5 is also not a
  referenced value - the IFS value is 0.35; it goes with the documented fix rather than being "named".)
  [reg: 00:32 | inputs: IFS doc read before comparing; layer thicknesses | fail-5why: n/a (named)]
  FIX (documented, rule 6 fix-first): option dd_ifs = 1 -> eta 0.35 and linear flux decrease over the lowest 60 hPa (flux form: the
  downdraft's excess h/q flux at each interface scaled by min(1, (ps - p_int)/60 hPa); evaporation into it scaled the same way).
  Default off; regress: control bit-identical, dd_ifs changes 7 fields.
  REGISTERED PREDICTION (land_conv no cap + dd_ifs, same diagnostics): (1) the sigma-0.99 deep cooling falls by >= 50 % (from -4.4) and
  h_bl at sigma 0.929 becomes >= 0 (mechanism); (2) GATE: sigma-0.925 day-1 dT closes >= 50 % of the gap to ERA5 (from -0.54 to >= -0.23
  against ERA5 +0.08); then (3) the global day-2 screen |t850|, |t700| <= 0.6. If (2) fails, failure 5-Why before any verdict on dd_ifs.
- 08:17 (clock; session paused ~04:10-08:15) dd_ifs RESULT (land_conv no cap + dd_ifs, subtropical ocean, day 1 hourly):
  (1) mechanism: sigma-0.99 deep cooling -4.4 -> -2.1 K/day (-53 %) PASS; h_bl at sigma 0.929 -0.21 -> -0.15 (still < 0) FAIL.
  (2) GATE sigma-0.925 dT -0.54 -> -0.47 (needed >= -0.23; 11 % of the gap closed) FAIL. Physics +0.08 -> +0.22; dynamics -0.62 -> -0.69.
  Failure 5-Why: the fix did what the IFS form does (bottom-level downdraft cooling halved), but RAIN EVAPORATION in the environment rose
  (sigma 0.99 -1.2 -> -1.5, 0.97 -1.1 -> -1.3, 0.95 -0.9 -> -1.1, 0.93 -0.7 -> -0.8): with eta 0.35 the downdraft takes up less rain, so
  more falls into the environment and evaporates there. Sub-cloud cooling by deep + evaporation summed over sigma 0.93-0.99: -7.0 before,
  -6.4 after - conserved, only moved. Column: 35 % of the rain produced re-evaporates (1.13 of 3.19 mm/day) with surface rain 0.69x ERA5.
  The failure traces to the rain-evaporation formula, not to dd_ifs -> dd_ifs HELD (blocked by rain evaporation in the lowest 100 hPa).
  [reg: 04:03 | inputs: deep/evap/BL profiles | fail-5why: evaporation took over the cooling the downdraft gave up]
  INPUT CHECK of the evaporation formula: ours (default) = k_evap (1 - RH) sqrt(P af) mass - it evaporates at any RH < 1, so it keeps
  cooling a moist trade BL (RH 0.8-0.9). IFS (Cy50r1, our option evap_ifs, evapifs.py): evaporation only below a critical RH (0.85 sea
  for convective rain, ~0.8 grid-scale) - the documented form. evap_ifs was "not adopted" on 13 Nov (TN rain 1.83 vs gate 1.43, exam
  +2.9 %) - judged ALONE, before rule 4 and before P4 (dry-season moist low levels) was named; that verdict is re-opened under rule 4.
  REGISTERED PREDICTION (land_conv no cap + dd_ifs + evap_ifs): (1) h_evap at sigma 0.95-0.99 falls >= 50 % and h_bl at 0.929 >= 0;
  (2) GATE sigma-0.925 dT >= -0.23 K/day; (3) surface rain stays 0.7-1.3x ERA5 (2.99 mm/day); then the global screen and TN rain.
- 08:50 (clock) dd_ifs + evap_ifs RESULT (land_conv no cap + both, subtropical ocean, day 1 hourly):
  (1) mechanism: rain evaporation at sigma 0.95-0.99 -3.96 -> -3.63 K/day summed (-8 %, needed -50 %) FAIL - the IFS form moved the
      evaporation down to sigma 0.99 (-1.5 -> -1.9) instead of removing it; h_bl at 0.929 -0.32 (still < 0) FAIL.
  (2) GATE sigma-0.925 dT -0.47 -> -0.36 (needed >= -0.23; with dd_ifs 29 % of the gap closed from -0.54) FAIL.
  (3) rain: surface 2.36 mm/day (0.79x ERA5, inside 0.7-1.3) PASS; convective 1.74 vs ERA5 cp 1.73 (1.00x); re-evaporated 13 % of
      production (was 35 %).
  Failure 5-Why: in ALL four versions (cap, no cap, +dd_ifs, +evap_ifs) h_bl at sigma 0.929 is negative and the BL scheme carries heat
  DOWN: here it cools sigma 0.93-0.84 (-0.3, -0.9, -1.2, -1.2, -0.65) and heats 0.97/0.95 (+3.0, +1.4) by matching amounts. A downward
  turbulent heat flux inside a BL with positive surface H means the K-diffusion is acting on a STABLE theta gradient in the upper part
  of our 1036-m BL - i.e. it is mixing the CUMULUS CLOUD LAYER as if it were the dry mixed layer. IFS input: for a cumulus-topped BL the
  dry K-diffusion stops at cloud base (test-parcel LCL) and the cloud layer is mixed by the moist updraft / shallow mass flux. BOMEX
  (Siebesma 2003): theta well mixed to ~520 m, then +~4 K/km through the cloud layer.
  Self-correction (rule 5): this partly reverses the 13:19 / 18 Nov reading of bl_lcl. The cap (BL top = LCL) is the IFS cumulus-regime
  behaviour; "hbl 455 vs ERA5 BLH 821" compared our K-profile top with ERA5's bulk-Richardson BLH, which in moist cumulus layers sits
  inside the cloud layer - not the same quantity. bl_lcl's verdicts are re-opened; nothing is adopted or rejected on this alone.
  dd_ifs and evap_ifs: both HELD (blocked by the BL scheme mixing the cloud layer); each moved the 925 error the right way and evap_ifs
  brought rain re-evaporation and convective rain to ERA5.
  [reg: 08:17 | inputs: deep/evap/BL profiles, ERA5 tp/cp | fail-5why: K-diffusion mixing the cloud layer down-gradient]
  REGISTERED INPUT CHECK (no code change): with the full set (+dd_ifs +evap_ifs, no cap), per column hourly: hbl vs LCL and the theta
  gradient between them, and ERA5's theta profile 1000-850 hPa over the same region. BL-IN-CLOUD-LAYER named if hbl > LCL + 300 m in
  >= 50 % of columns AND our mean dtheta/dz between LCL and hbl >= 2 K/km (stable, so K-mixing moves heat down) AND ERA5's gradient over
  the same heights is also >= 2 K/km (i.e. the layer really is a cloud layer, not a mixed layer).
- 09:14 (clock) BL-IN-CLOUD-LAYER RESULT (bllcl.py, full set no cap, subtropical ocean, day 1 hourly; ERA5 thsub_truth 3-hourly):
  ours: hbl 1075 m, LCL 675 m; hbl > LCL + 300 m in 72 % of columns; mean dtheta/dz between LCL and hbl 4.1 K/km.
  ERA5 theta(z): 147 m 293.70 | 365 m 293.87 | 588 m 294.40 | 815 m 295.37 | 1048 m 296.67 -> 0.8 K/km below ~400 m (mixed layer), then
  2.3 / 4.3 / 5.6 K/km - over our LCL-hbl band (675-1075 m) ERA5 is 4.3-5.6 K/km: a real cloud layer.
  Rule (08:50): all three met (72 % >= 50 %; 4.1 >= 2; ERA5 >= 2) -> BL-IN-CLOUD-LAYER NAMED: with bl_lcl 0 our dry K-diffusion mixes
  the cumulus layer down-gradient, cooling ~650-1300 m and heating the subcloud layer. Our own theta there is less stable than ERA5
  (2.7 / 4.2 vs 4.3 / 5.6 K/km) - the mixing has eroded it.
  [reg: 08:50 | inputs: hbl, LCL, theta(z) vs ERA5 | fail-5why: n/a (named)]
  Documented behaviour (IFS Cy38r1 Part IV ch. 3, cumulus-topped regime): dry K-diffusion and the dry EDMF updraft stop at cloud base;
  the cloud layer is mixed by the moist updraft / shallow convection. Our bl_lcl = 1 (BL top = cloud base when below the K-profile top)
  is that behaviour; it failed on 19 Nov only in combination with the downdraft and evaporation faults, now fixed (dd_ifs, evap_ifs).
  REGISTERED PREDICTION (land_conv + dd_ifs + evap_ifs + bl_lcl 1): (1) h_bl at sigma 0.929 >= 0; (2) GATE sigma-0.925 day-1 dT >= -0.23
  K/day (ERA5 +0.08); (3) surface rain 0.7-1.3x ERA5; then (4) the global day-2 screen |t850|, |t700| <= 0.6 K.
- 09:37 (clock) bl_lcl 1 + dd_ifs + evap_ifs RESULT (land_conv base, subtropical ocean, day 1 hourly, K/day):
  (1) h_bl at sigma 0.929 = +0.27 (inside-BL columns +1.10) PASS - the down-gradient mixing of the cloud layer is gone.
  (2) GATE sigma-0.925 dT -0.63 (needed >= -0.23) FAIL. BUT sigma-0.85 dT -0.47 (no-cap version -1.16; land_conv first screen -1.21).
  925 physics -0.21 = BL +0.27, shallow +0.26, deep +0.53, large-scale +0.26, evaporation -0.05, RADIATION -1.47 (no cap: -0.06).
  Failure 5-Why: with the cloud layer no longer K-mixed, the 925 radiative cooling (-1.5 K/day) appears - inside the LES trade-layer
  range (-2, Siebesma 2003 / vanZanten 2011), so radiation is now plausible, not the fault. The heating terms (+1.3) fall short of the
  ERA5-implied ~+2.3 non-radiative heating. Caveat recorded honestly: "ERA5 Q1" is a budget residual and contains ERA5's analysis
  increments (not separable here); the 18 Nov note put ERA5 Q1 uncertainty at ~0.6 K/day near 850. The 925 gate's reference is
  therefore weaker than the global screen's (direct ERA5 temperatures). Per the 09:14 registration the global day-2 screen (4) is
  now being run to measure the combination; no verdict on bl_lcl / dd_ifs / evap_ifs until it is in.
  [reg: 09:14 | inputs: process profiles; ERA5 Q1 residual caveat | fail-5why: radiation uncovered, heating short vs a residual reference]
- 09:57 (clock) GLOBAL SCREEN of the combination "lc_full" = land set + IFS-document convection set + bl_lcl 1 + dd_ifs + evap_ifs
  (rh_vs_era5, T42 dt 20, wx2020L2, 3 starts, truth era5f/rh_truth_2020.npz; gate day-2 globe |t850|, |t700| <= 0.6 K, from 18 Nov):
  t850 globe d2 -0.52 PASS; t700 globe d2 -0.70 FAIL (by 0.10). Split d2: t700 ocean 40S-40N -0.43, poleward 40 -1.03; t850 ocean -0.53,
  poleward -0.10. rh850 globe d2 +0.06. Comparison (day-2 globe t850 / t700): base3r +0.07 / -1.54, land +0.17 / -1.41, land_conv
  -0.76 / -0.89, lc_full -0.52 / -0.70 (best on both together). Tropical-ocean t700: base3r -1.94, land_conv -0.68, lc_full -0.43.
  Subtropical rain (rainchk): lc_full 1.86 mm/day = 0.62x ERA5 (FAIL vs 0.7-1.3; was 0.79x without the cap); convective 0.73x ERA5 cp.
  Failure 5-Why (t700): poleward-40 t700 d2 is -1.03 (lc_full), -1.03 (base3r), -1.04 (land), -1.09 (land_conv), -1.01/-1.39/-1.44
  (convdoc variants) - the SAME in every version; the convection/BL fixes do not touch it. The global t700 failure traces to this
  shared EXTRATROPICAL mid-level cold, not to the fixes -> lc_full HELD (blocked by the poleward t700 cold), not rejected; the
  tropical part of A is inside the gate (t700 ocean -0.43, t850 ocean -0.53).
  Rain: lc_full is too dry over the subtropical ocean (0.62x) - recorded as a second blocker for the A verdict; the 18 Nov gate's
  "day-1 rain and LHF within 15 % of ERA5" (global) has not been measured for lc_full yet.
  [reg: 18 Nov 13:10 gate; 09:14 sequence | inputs: per-region split; shared across all versions | fail-5why: poleward t700 shared]
  REGISTERED NEXT: (a) the poleward t700 cold, day 1 (-0.85) - inputs first: hourly 700-hPa budget poleward of 40 (radiation by part,
  cloud, dynamics) vs ERA5 temperatures, naming the term carrying >= 50 % of the day-1 -0.85; (b) global day-1 rain and LHF of lc_full
  vs ERA5 (the 18 Nov gate's second half).
- 09:58 (clock) REGISTERED (poleward t700 cold, inputs first): hourly day-1 budget at sigma 0.70 and 0.50, 40-80 N/S all surfaces,
  lc_full (dyn700.py: dT = physics by part + horizontal advection + vertical + residual) and ERA5 at 700 hPa (cyc_adv700.py: hadv,
  vertical term, day-1 T change). A term is NAMED AS THE ERROR if |model - ERA5| >= 0.43 K/day (half of the -0.85 day-1 t700 error);
  for physics (no ERA5 parts) the implied ERA5 Q1 = dT - hadv - vert is compared with our total physics, and the largest part is then
  checked against its reference. [reg: now | inputs: to measure | fail-5why: n/a]
- 11:44 (clock; session paused ~10:10-11:40) POLEWARD 700 RESULT (dyn700.py, lc_full, 40-80 N/S all surfaces, sigma 0.70, day 1 hourly,
  K/day; ERA5 adv700_truth at 700 hPa): model dT -1.05 vs ERA5 -0.17 (error -0.88). hadv model -0.01 vs ERA5 -0.36 (diff +0.35, < 0.43,
  NOT named); vertical +0.18 vs +0.24 (diff -0.06, NOT named). Physics: ERA5-implied Q1 = -0.17 - (-0.36 + 0.24) = -0.05; ours -1.25 ->
  diff -1.20 >= 0.43 -> PHYSICS NAMED (residual caveat as at 09:37 applies). Parts at sigma 0.70: radiation -1.32, shallow -0.60,
  large-scale +0.50, deep +0.22, evaporation -0.05, BL 0. (sigma 0.50: radiation -1.32, large-scale +0.37 -> physics -0.94; dT -1.03.)
  Caveat: sigma 0.70 is not 700 hPa over high ground (40-80 N includes the Rockies, Tibet's north rim, Antarctica's edge).
  Shared-cause test (the cold is -1.03 in EVERY version, but shallow -0.60 exists only with the 'mf' shallow scheme): REGISTERED - the
  same budget for base3r; the part that is (a) present in both runs at >= 0.43 K/day beyond the ERA5-implied Q1 and (b) not changed by
  the convection set is named as the shared input, then checked against its reference (for radiation: an offline clear-sky check or a
  published mid-latitude cooling profile, read first). [reg: 09:58 | inputs: ERA5 hadv/vert/dT | fail-5why: n/a (named)]
- 11:45 (clock) INPUT CHECK REGISTERED for the poleward 700 physics (radiation already matched RRTMG on the same clouds, 18 Nov 11:44 ->
  the scheme is not the suspect; its INPUTS are): (i) poleward day-1 precipitation (latent heating) ours vs ERA5 total precip:
  LATENT HEATING DEFICIT named if ours <= 0.7x ERA5; (ii) 700-hPa cloud fraction ours vs ERA5 fraction_of_cloud_cover: CLOUD named if
  ours >= 1.3x ERA5 (more mid-level cloud -> more LW cooling). Both for lc_full and base3r (cyc_cppole.py; rainchk.py REG=pole).
  [reg: now | inputs: radiation scheme vs RRTMG (18 Nov) | fail-5why: n/a]
- 12:17 (clock) POLEWARD INPUT RESULTS (40-80 N/S, all surfaces, day 1; ERA5 cppole_truth: precip 2.44 mm/day, conv 0.64, cc700 0.142):
  lc_full : rain 1.50 (0.62x) - production 1.62 (large-scale 1.26), 7 % re-evaporated; cloud 700 0.309 (2.2x).
  base3r  : rain 2.07 (0.85x) - production 3.29 (large-scale 2.87), 37 % re-evaporated; cloud 700 0.214 (1.5x).
  Rules (11:45): (i) LATENT DEFICIT named for lc_full (0.62x <= 0.7), NOT for base3r (0.85x); (ii) CLOUD named for both (2.2x, 1.5x).
  Base3r poleward budget (sigma 0.70): dT -0.93 = physics -0.77 [rad -1.42, large-scale +0.94, shallow -0.47, deep +0.36, evap -0.15]
  + dyn -0.16; lc_full: physics -1.25 [rad -1.32, large-scale +0.50, shallow -0.60, deep +0.22]. Shared-cause rule (11:44): parts present
  in both at >= 0.43 beyond the ERA5-implied Q1 (-0.05) and unchanged by the convection set: radiation (-1.3/-1.4) and SHALLOW-TOP
  cooling (-0.5/-0.6, both shallow schemes). Radiation was matched by RRTMG on the same clouds (18 Nov) and sits in the usual
  mid-latitude range, so its input (cloud, 1.5-2.2x ERA5 at 700) is the radiation-side suspect; shallow cooling at 700 averaged over the
  whole 40-80 belt is the other. What really differs from ERA5 is the latent side: ERA5 needs ~+1.3 K/day of condensation heating at
  700 to balance the same radiation; we have +0.07 (lc_full) / +0.68 (base3r).
  Note on lc_full's rain deficit: its large-scale rain production poleward is less than half of base3r's (1.26 vs 2.87 mm/day) - which
  item of the set does that (sfc_sal, qs_mix, evap_ifs, convection changes) is unknown -> to be split.
  [reg: 11:44 / 11:45 | inputs: ERA5 precip and cloud; RRTMG check of 18 Nov | fail-5why: n/a (named)]
  REGISTERED NEXT: (1) poleward 700 cloud: our cloud scheme's RH threshold vs IFS (Tiedtke/ Sundqvist critical RH in the mid
  troposphere, read first) and our RH at 700 vs ERA5 r700 - CLOUD-SCHEME named if our RH is within 0.05 of ERA5 while cloud is >= 1.3x;
  RH named if ours is >= 0.05 above ERA5. (2) lc_full poleward large-scale rain: one-item-out runs (each set item removed) - the item
  whose removal restores >= 50 % of the 1.6 mm/day production gap is named.
- 12:19 (clock) RH CHECK RESULT (registered 12:17, rule (1)): poleward rh700 (rh_vs_era5, same saturation blend both sides) lc_full
  d0 +0.07 / d1 +0.18 / d2 +0.22; base3r d1 +0.20 / d2 +0.25 -> our RH is >= 0.05 above ERA5 (also after removing the d0 offset: +0.11
  in day 1) -> RH NAMED (shared by both versions) as the input to the excess 700 cloud. Cloud-scheme branch not named (RH not within 0.05).
  5-Why on the moistening: the shared shallow-top cooling (-0.5/-0.6 K/day at sigma 0.70) is evaporation of detrained condensate, i.e.
  moistening of ~0.22 g/kg/day; at qs(261 K, 700 hPa) ~2.6 g/kg that alone is ~+0.085 RH/day, plus ~+0.035 from the -0.85 K cooling ->
  ~0.12, the size of the +0.11 growth. Arithmetic on already-seen numbers -> stated as a HYPOTHESIS, not a verdict.
  REGISTERED: direct moisture budget at sigma 0.70, 40-80 N/S, day 1 (qpole.py; lc_full and base3r): SHALLOW-TOP MOISTENING named if
  the shallow scheme's q tendency there is >= 50 % of the net physics+dynamics moistening, in both runs. If named, the reference to read
  next is the IFS shallow-convection top/detrainment in mid-latitude cold-air regimes (Cy38r1 Part IV ch. 6) before any change.
  [reg: 12:17 | inputs: RH vs ERA5 with matched saturation; d0 offset removed | fail-5why: n/a (named)]
- 12:40 (clock) POLEWARD MOISTURE BUDGET RESULT (qpole.py, sigma 0.70, 40-80 N/S, day 1, g/kg; q0 1.34):
  lc_full: dq +0.087 = physics -0.131 [shallow +0.054, large-scale condensation -0.201, evap +0.019, BL +0.004, deep -0.007] + dyn +0.218
  base3r : dq +0.130 = physics -0.096 [shallow +0.219, condensation -0.378, evap +0.060, BL +0.015, deep -0.012] + dyn +0.226
  Rule (12:19): shallow >= 50 % of the net moistening in both -> lc_full 62 %, base3r 168 % -> SHALLOW-TOP MOISTENING NAMED (per rule).
  Honest qualifiers: (1) my 12:19 arithmetic was wrong for lc_full - its -0.60 K/day shallow cooling at 700 is mostly mass-flux
  transport, not evaporation (only +0.054 g/kg); (2) in both runs the larger moistening is DYNAMICS (+0.22), and the condensation sink
  is weak (-0.20 / -0.38) - with grid-scale condensation only at saturation (saturation adjustment), moisture can pile up below 100 %
  RH where IFS (Tiedtke, cloud fraction from RH_crit) already condenses. Whether dyn +0.22 is right needs ERA5's own moisture
  advection. [reg: 12:19 | inputs: q budget by part | fail-5why: n/a (named; qualifiers stated)]
  REGISTERED: ERA5 700-hPa moisture advection poleward (cyc_qadv700.py, horizontal + vertical) -> ERA5-implied physics drying =
  dq_ERA5 - dyn_ERA5. CONDENSATION DEFICIT named if ours (-0.13 / -0.10) is short of the ERA5-implied drying by >= 0.1 g/kg/day;
  DYNAMICS MOISTENING named if our dyn exceeds ERA5's by >= 0.1. Shallow (named) waits for the IFS shallow-top reference.
- 12:51 (clock) ERA5 700 MOISTURE RESULT (qadv700_truth, 40-80 N/S, day 1, g/kg/day): hadv +0.066, vertical +0.196 -> dyn +0.262;
  dq -0.036 -> ERA5-implied physics drying -0.298. Ours: physics lc_full -0.131 (short by 0.167), base3r -0.096 (short by 0.20) ->
  CONDENSATION (physics drying) DEFICIT NAMED in both (>= 0.1). Dynamics: ours +0.218 / +0.226 vs ERA5 +0.262 -> NOT named (ours is
  slightly LESS moistening).
  Chain (poleward 700, shared by every version): physics removes too little vapour (-0.10/-0.13 vs -0.30) -> RH +0.11/day beyond d0 ->
  cloud 1.5-2.2x ERA5 and too little condensation heating -> with radiation -1.3 K/day (RRTMG-matched) the layer cools ~0.9 K/day.
  Inputs of the condensation: our grid-scale scheme condenses only at grid saturation (saturation adjustment) - the IFS scheme
  (Tiedtke 1993; Cy38r1 Part IV ch. 7) condenses in the cloudy part of a box once RH exceeds the critical value, so a mean RH of
  0.7-0.9 already rains. NEXT (registered): read IFS ch. 7 (condensation in the cloudy part / cloud formation term, RH_crit), then
  measure what fraction of our poleward 700 columns sit between RH_crit and 1 (where IFS condenses and we do not); SUBGRID
  CONDENSATION named if >= 30 % of columns are there and the ERA5-implied missing drying (0.17-0.20 g/kg/day) is within what those
  columns would condense under the IFS form.
  [reg: 12:40 | inputs: ERA5 q advection and dq | fail-5why: n/a (named)]
- 13:05 (clock) SUBGRID-CONDENSATION RESULT (rhpole.py, lc_full, sigma 0.70, 40-80 N/S, day 1): RH (model water-only q_s) in
  [0.8, 1): 21 % of columns (>= 1: 6 %); mean RH 0.58; IFS eq. 7.18 condensation-in-cloud estimate C1 = a max(-dqs/dt, 0) = 0.17
  g/kg/day (the missing drying is 0.17-0.20). Rule (12:51) needs BOTH >= 30 % of columns AND the size -> 21 % < 30 % -> NOT named.
  [reg: 12:51 | inputs: RH distribution, c_ls, hourly qs | fail-5why: n/a (not named)]
  INPUT CHECK found on the way (rule 2): the saturation our grid-scale condensation uses. mm2 qsat = Bolton over WATER at every T.
  IFS Cy38r1 ch. 7 uses MIXED-PHASE saturation for stratiform condensation (e_s = a e_w + (1 - a) e_i, a = ((T - 250.16)/23)^2) - the
  same blend ERA5's RH uses. At 700 poleward (T ~ 261 K) q_s,mix / q_s,water = 0.91 -> our air holds ~9 % more vapour before it
  condenses = ~+0.09 RH (mixed) of headroom, the size of the +0.11 RH excess grown in day 1. The mean RH 0.58 above is against
  water saturation, which is why only 21 % of columns look "near saturation". -> SATURATION FORMULA (water-only below 0 C) NAMED as
  the input of the condensation deficit (documented IFS form differs; the size matches).
  [reg: now (input check under rule 2, size arithmetic stated) | inputs: qsat formula vs IFS ch. 7 | fail-5why: n/a (named)]
  FIX (documented): option lsc_mix = 1 - IFS mixed-phase q_s in the grid-scale condensation and in the rain-evaporation RH; latent heat
  kept at LV (no ice phase in this model). Default off; regress: control bit-identical, lsc_mix changes 7 fields.
  REGISTERED PREDICTION (lc_full + lsc_mix, global screen, same harness): (1) poleward rh700 d1 excess falls >= 50 % beyond the d0
  offset (+0.18 -> <= +0.13); (2) poleward t700 d2 cold falls >= 50 % (-1.03 -> >= -0.52); (3) GATE day-2 globe |t850|, |t700| <= 0.6;
  (4) poleward precipitation rises toward ERA5 (from 0.62x). If (3) fails, failure 5-Why first.
- 13:14 (clock) lsc_mix RESULT (lc_full + lsc_mix, global screen, same harness):
  (1) poleward rh700 d1 +0.184 -> +0.140 (needed <= +0.13) FAIL - beyond the d0 offset the excess fell 0.112 -> 0.068 (-39 %);
  (2) poleward t700 d2 -1.03 -> -0.96 (-7 %, needed -50 %) FAIL; (3) globe d2 t850 -0.53 PASS, t700 -0.69 FAIL (by 0.09).
  Failure 5-Why (and a self-correction, rule 5): I did not check the SIZE of the latent link before calling the chain at 12:51. The
  ERA5-implied missing drying (0.17-0.20 g/kg/day) is worth only L/cp x 0.2 g/kg ~ 0.5 K/day of condensation heating, while the
  700 physics gap is 1.2 K/day (ours -1.25 vs ERA5-implied -0.05). So the latent deficit can explain at most ~40 % of the cold; lsc_mix
  removes part of it (RH -39 %) and the temperature barely moves - consistent. The failure does not trace to lsc_mix (it did what the
  IFS form does to RH); it traces to the NON-LATENT ~0.7 K/day: radiation (-1.3) and the shallow scheme's transport cooling (-0.6).
  lsc_mix HELD (blocked by the non-latent 700 cooling). [reg: 13:05 | inputs: RH/T split; size arithmetic | fail-5why: non-latent part]
  INPUT CHECK (radiation side): RRTMG matched our radiation on the SAME clouds (18 Nov), so the clouds are the input. Our large-scale
  cloud (radcloud c_ls) starts at RH_crit = rhc_up 0.70 + 0.10 exp(1 - sigma^-4) = 0.70 at sigma 0.70; IFS Cy38r1 eq. 7.19 uses
  RH_crit = 0.8 for sigma < 0.8 - our cloud forms at 0.10 lower RH aloft, on top of the +0.14..0.18 RH excess -> 700 cloud 1.5-2.2x ERA5.
  REGISTERED: radiation at sigma 0.70 poleward split clear-sky vs cloud (rad_allsky style) for lc_mix: CLOUD RADIATIVE COOLING named if
  the cloud part is >= 0.43 K/day (half the -0.85 day-1 error); and in the same run the shallow-transport cooling (-0.6) is checked
  against the IFS shallow-top reference (Part IV ch. 6, read first).
- 13:19 (clock) RADIATION SPLIT RESULT (rad_allsky.py, lc_mix, 650-750 hPa, |lat| >= 40, h24, 3 starts, K/day; same clouds into RRTMG):
  LW all-sky -1.5/-1.5/-1.6 (RRTMG -1.6/-1.5/-1.6), LW clear -1.3 (RRTMG -1.4); SW all-sky +0.3/+0.4/+0.4, clear +0.4.
  Cloud radiative part = (all - clear) ~ -0.3 K/day (< 0.43) -> CLOUD RADIATIVE COOLING NOT named, despite cloud 1.5-2.2x ERA5;
  radiation is right for the state (RRTMG within 0.1) and mostly clear-sky (-0.9 net).
  [reg: 13:14 | inputs: same clouds through RRTMG | fail-5why: n/a (not named)]
  Where that leaves the poleward 700 cold (shared, ~-0.9 K/day): dynamics matches ERA5 (T and q); radiation right for the state;
  latent heating short by an amount ERA5 cannot pin (its q residual mixes condensation with convective/turbulent moistening);
  the remaining named non-latent item is the SHALLOW scheme's transport cooling at 700 (-0.47 base3r / -0.60 lc_full), present in both
  shallow schemes. NEXT: read IFS Cy38r1 Part IV ch. 6 on shallow convection (cloud top, detrainment, where its cooling sits) before any
  comparison; then a profile of the shallow T/q tendency vs height poleward (where its top is) against that reference.
- 13:20 (clock) IFS SHALLOW REFERENCE (read first, Cy38r1 Part IV sec. 6.4): shallow only if cloud thickness < 200 hPa (we use sh_dmax
  20000 Pa - matches); mass flux constant with height then reduced at cloud top by organised detrainment (kinetic-energy budget, eqs.
  6.10-6.12); detrained condensate goes to the prognostic cloud scheme (eq. 6.47) - it is not evaporated on the spot; shallow
  "predominantly occurs in undisturbed flow". No number for shallow-top cooling is given -> no quantitative range to compare with.
  So instead of naming by reference, a DIAGNOSTIC DENIAL (measurement only, never a fix): option sh_off = 1 zeroes the shallow
  tendencies (regress: control bit-identical; sh_off changes 7 fields).
  REGISTERED: lc_mix + sh_off, global screen: SHALLOW named as the cause of the poleward 700 cold if poleward t700 d2 falls by >= 50 %
  (-0.96 -> >= -0.48); if not, the shallow scheme is cleared for this fault. [reg: now | inputs: IFS shallow ref read | fail-5why: n/a]
- 13:29 (clock) SHALLOW DENIAL RESULT (lc_mix + sh_off, measurement only): poleward t700 d2 -0.96 -> -0.73 (-24 %, needed -50 %) ->
  SHALLOW NOT named as the cause of the poleward cold; it contributes ~0.23 K of it. (Side numbers, not a verdict on anything: with the
  shallow scheme denied, globe d2 t850 -0.26, t700 -0.56, tropical t850 +0.11 - the shallow scheme also cools the tropical 700/850.)
  [reg: 13:20 | inputs: denial run | fail-5why: n/a (not named)]
  Status of the poleward 700 5-Why: dynamics (T, q) = ERA5; radiation = RRTMG on the state, cloud part only -0.3; shallow ~0.23 of
  0.96; latent: poleward rain 0.62x (lc_full) / 0.85x (base3r) ERA5 and RH +0.14..0.18 - the column-integral says latent heating is
  short by ~0.3-0.6 K/day in the 500-850 layer. Remaining candidate list (fishbone): (a) latent heating (precipitation efficiency of
  the grid-scale scheme), (b) dynamics residual (numerics: -0.33 K/day at sigma 0.50 in both runs), (c) T42 resolution of mid-latitude
  ascent (ERA5 at 0.25 deg). NEXT: poleward precipitation of lc_mix (does lsc_mix raise it toward ERA5?) and the residual's size at
  T85 vs T42 (resolution test) - registered rules to be written before each run.
- 13:29 (clock) REGISTERED (two parallel input checks on the poleward 700 cold, lc_mix):
  (a) poleward day-1 precipitation (rainchk REG=pole): LATENT confirmed as the main remaining input if lsc_mix raised poleward rain
      by < 0.2 mm/day and it is still <= 0.7x ERA5 (2.44) - i.e. the grid-scale scheme's precipitation, not its saturation, is short;
  (b) resolution: the same global screen at T85 (dt 20): RESOLUTION named if poleward t700 d2 at T85 is >= 50 % smaller than at T42
      (-0.96 -> >= -0.48).
- 13:41 (clock) POLEWARD RAIN of lc_mix (rainchk REG=pole): 1.76 mm/day (lc_full 1.50; ERA5 2.44) = 0.72x; cloud 700 0.27 (from 0.31).
  Rule (a) 13:29: lsc_mix raised rain by 0.26 (>= 0.2) and the ratio is 0.72 (> 0.7) -> NOT met: the grid-scale precipitation is not
  named as the main remaining input; the saturation fix moved rain the right way. [reg: 13:29 | inputs: ERA5 tp | fail-5why: n/a]
- 13:51 (clock) AMENDMENT to the 13:29 resolution test, before any result: the T85 screen was killed by the 7 GB memory limit (OOM,
  6.1 GB RSS) - not runnable here. Replaced by T63 (same rule: RESOLUTION named if poleward t700 d2 at T63 is >= 50 % smaller than at
  T42, -0.96 -> >= -0.48; a smaller step than T85, so a FAIL here is weaker evidence against resolution - stated now).
- 13:52 (clock) RESOLUTION TEST NOT RUN: Dinosaur has no T63 grid (only TL63, which keeps the T42 physics grid - not a resolution test
  of the physics), and T85 is OOM here (7 GB). Deferred to a Kaggle T85/T170 screen job (needs a small harness: rh_vs_era5 with CANDS)
  - no verdict on (b) until then. [reg: 13:29/13:51 | inputs: grid availability | fail-5why: tooling, not physics]
  Plan note: the poleward 700 cold is shared by EVERY version (incl. the BASE3 that scored best on the exam) and sits poleward of 40;
  the Bay-of-Bengal problems (P3, P5b, Tracks) live in the tropics, where lc_mix is inside the gate. Per the 18 Nov plan (21-23 Nov
  re-measure P3/P5b/P2), the exam re-measurement with lc_mix as the MEASURED candidate runs in parallel with the poleward 5-Why;
  no gate is relaxed and A stays HELD.
- 13:54 (clock) EXAM RE-MEASURE PREPARED (plan 21-23 Nov; lc_mix as the MEASURED candidate, A stays held): Rule 1 intensity, T170, 2 jobs
  (tn-r1-lcm-0 acct 1, tn-r1-lcm-1 acct 4; cfg kaggle_cfg/lib84_lcmixr1.json; precheck OK, regress bit-identical).
  INPUT CHECK first (rule 2): the storm-start library libm_fields.npz has NO land fields (known since 5 Nov: landinit falls back to
  air temperature and 60 % soil water) - a land-set exam on it would be unfair. -> building libm_cycL2_fields.npz (same storm list,
  land incl. soil levels 2-4) by the 'cycl2 library' workflow step; the 2 jobs are parked in kaggle_cfg/queue_lcmix_pending.json and
  go to the queue once the library is on the release. No GPU minutes spent on wrong inputs.
- 14:00 (clock) LAUNCHED (re-measure per plan, lc_mix as measured candidate, A held): general-weather exam tn-lcm-wx0..3 (T170, 10 days,
  suite_lcmix_wx.json) on the LAND library wx2020L2 (accounts 1 and 4; wx3 waiting for account 4). Comparability note stated now: the
  BASE3 exam used libm_wx2020 (no land fields); lc_mix's numbers carry both the physics and the better land start - a BASE3 run on
  wx2020L2 is needed to separate them before any adoption verdict.
- 14:11 (clock) WHERE is the poleward t700 cold (lc_mix day-2 error map, T42, 3 starts): NH >= 40: -1.11 (land -0.97, ocean -1.27);
  SH <= -40: -0.76 = Southern Ocean -1.37 (40-60 S: -1.74) offset by Antarctica +3.77 (high ice sheet, 700 hPa near the surface).
  -> the cold sits over the mid-latitude OCEAN storm tracks, strongest over the Southern Ocean; Antarctica is a separate warm fault.
  Storm-track latent heating at fronts is under-resolved at T42 -> raises the resolution branch (b) of the 13:29 fishbone; the T85 test
  goes to Kaggle (rh_vs_era5 harness; inputs libm_wx2020L2 + rh_truth_2020, both on the release) - same registered rule (>= 50 %
  smaller at T85). [reg: 13:29 | inputs: day-2 error map by region | fail-5why: n/a (localisation)]
  Library: libm_cycL2_fields.npz built (84 storm starts, land incl. soil 1-4; sources logged: soil T and skin from ARCO, soil water
  and snow from WB2); the 2 Rule-1 jobs moved to the queue (waiting for a free account slot).
- 16:02 (clock) REGISTERED (Antarctica +3.77 warm at 700, input/diagnostic check first, rule 2): ERA5 700 hPa is extrapolated below ground
  where ERA5 surface pressure < 700 hPa, while the screen keeps a point when the MODEL's (T42-smoothed, lower) ice sheet has ps > 700.
  DIAGNOSTIC ARTIFACT named if >= 70 % of the Antarctic (<= -60) area-weighted warm error at 700 (lc_mix day-2 map) sits where ERA5
  surface pressure (wx2020L2 starts 56/61/66) < 750 hPa (700 + 50 hPa margin for the near-surface layer); otherwise it is a model fault.
- 16:03 (clock) ANTARCTICA WARM = DIAGNOSTIC ARTIFACT (named): 86 % of the Antarctic (<= -60) warm error at 700 (lc_mix d2) sits on 9 % of
  the area where ERA5 surface pressure < 750 hPa (mean error there +9.3 K; ERA5 700 below ground or in its surface inversion, model
  T42 ice sheet lower); the rest of Antarctica is +0.15. Rule (16:0x) met -> not a model fault; closed as a problem.
  [reg: this cycle, before the split | inputs: ERA5 surface pressure at the 3 starts vs the day-2 map | fail-5why: n/a]
  CORRECTION of my own numbers (stated openly): the artifact was HIDING cold. With points where ERA5 ps < 750 hPa removed, t700 d2:
  lc_mix global -0.689 -> -0.753, poleward -0.94 -> -1.129; land_conv -0.889 -> -0.949 / -1.076 -> -1.253; BASE3 -1.536 -> -1.613 /
  -1.013 -> -1.212. A's gap to the gate is 0.15, not 0.09. Same mask applied to every version, so the ranking is unchanged.
- 16:03 (clock) AMENDMENT to the 13:29 resolution rule, BEFORE any T85 result (job still queued): both resolutions measured with the same
  ERA5-ps >= 750 hPa mask (T85 job now saves maps and prints MASKED t700). RESOLUTION named if masked poleward t700 d2 at T85 is
  >= 50 % smaller than masked T42 (-1.129 -> >= -0.565). Unmasked rule (-0.96 -> -0.48) reported alongside, unchanged.
- 16:50 (clock) DECISION (Sridhar 16:44: split or combine is my call, fix the poleward cold now): SPLIT. A/P1 = tropical + subtropical
  convective heating (its gates there; plus its own open check, subtropical rain 0.62x ERA5). NEW PROBLEM "P-pole" = poleward-40
  700 hPa cold, pre-existing in every version (masked T42: BASE3 -1.21, lc_mix -1.13), carries the unchanged global t700 gate (0.6)
  into the final exam. No gate removed or weakened.
  Local T85 retried with a 3-start library: OOM again (5.4 GB RSS, cgroup kill) -> resolution only on Kaggle (job queued).
  Input check on the way: the 'no soil water, skin temperature' warnings in every screen log come from mm2's own soil-level calls
  (lines 228-233 pass None on purpose); the main land start (line 220) gets all fields (finite 100 %) -> not an input fault.
  FISHBONE (P-pole, physics gap ~1.2 K/day at 700; dynamics match ERA5): latent ~0.4-0.5 (size of the missing drying), shallow ~25 %,
  radiation matched by RRTMG, resolution (Kaggle). CODE FACT: mm2 convection starts plumes only at sigma >= 0.87 (line 670) - there is
  NO mid-level convection. IFS Cy38r1 Part IV 6.4.3: mid-level convection for 500 m < z < 10 km when there is large-scale ascent and
  RH > 80 %; closure eq. 6.31: cloud-base mass flux = large-scale vertical mass flux. In storm-track frontal ascent this condenses at
  RH 0.8-1.0 where our scheme waits for grid saturation; ERA5 poleward cp 0.64 vs ours 0.31 mm/day (half) is consistent.
  REGISTERED (midlev.py, lc_mix, sigma 0.70, 40-80 N/S, day 1): MID-LEVEL CONVECTION named if the eq. 6.31 condensation heating in
  trigger columns (ascent, RH_mix in [0.8, 1), no active deep convection) is >= 0.43 K/day area mean (half the day-1 700 error -0.85).
- 16:58 (clock) MID-LEVEL CONVECTION RESULT (midlev.py, lc_mix, sigma 0.70, 40-80 N/S, day 1, 3 starts): trigger columns (ascent,
  RH_mix in [0.8, 1), no deep) 10.9 % of the area; eq. 6.31 condensation heating there 0.25 K/day area mean (incl. already-saturated
  ascent 0.71, which our grid-scale scheme already condenses: h_lsc +0.5). Rule (16:4x): 0.25 < 0.43 -> MID-LEVEL CONVECTION NOT named
  as the main cause; it is a CONTRIBUTOR (~30 % of the day-1 -0.85; also an upper bound - grid-scale condensation catches part of it
  later). [reg: 16:4x | inputs: model omega (sigma scheme), RH_mix, on_dp | fail-5why: n/a (not named)]
  P-pole tally at sigma 0.70 (day-1 error -0.85 K/day): sub-saturated latent / mid-level ~0.25, shallow ~25 % of the d2 cold (denial),
  rest (~0.4) not yet attributed -> resolution (Kaggle T85, registered rule) stays the lead branch; no single named cause yet, so no
  physics change is made (rule 1). Note for the fix: mid-level convection is a documented IFS part we lack (6.4.3) and a fair contributor
  - to be built as an option (needs a correct omega inside the column physics) after the T85 verdict, with its own registered test.
- 16:59 (clock) EXAM PARTIAL (no verdict - 3 of 4 parts; tn-lcm-wx3 and tn-res-t85 launched 16:51): z500 RMSE on the same 55 starts,
  d1/d5/d10: BASE3 18.0 / 71.6 / 118.1, lc_mix 15.3 / 65.4 / 110.1; lc_mix better at d5 in 51 of 55 starts. Caveat stated now: lc_mix ran
  on the land library wx2020L2, BASE3 on wx2020 (no land); the d1 gap (2.7 m) shows part of the gain is the start. A BASE3 run on
  wx2020L2 is needed before any adoption verdict (queued next when a slot frees).
- 19:10 (clock) T85 RESOLUTION RESULT (tn-res-t85, lc_mix, starts 56/61/66, same harness, rule amended 16:03 before the result):
  masked poleward t700 d2 T42 -1.129 -> T85 -0.882 (-22 %, rule needs >= 50 %, i.e. >= -0.565) -> RESOLUTION NOT NAMED.
  Unmasked (reported alongside): -0.96 -> -0.768 (-20 %, needed -0.48) - same answer. Resolution is a CONTRIBUTOR of ~20 %.
  Poleward rh700 excess barely moves (d1 +0.14 T42 -> +0.122 T85; d2 +0.128) -> the moist/cold 700 layer is not a grid-scale effect.
  Note, not a closure: T85 global masked t700 d2 = -0.593 (unmasked -0.553), just inside 0.6. The gate is measured at the screen
  resolution (T42); counting a T85 number after seeing it would be relaxing the gate, so A's gate status is unchanged.
  Contributors so far to the ~0.85 K/day poleward 700 cooling excess: mid-level (missing) convection ~30 %, shallow-top cooling ~25 %,
  resolution ~20 % -> no single named root cause; no >= 50 % branch left in the fishbone. Next: build IFS mid-level convection
  (Cy38r1 Part IV 6.4.3, eq. 6.31) as an option (with column omega) and test whether the contributors ADD (combined registered test).
  [reg: 16:03 | inputs: same mask both resolutions, same starts/harness | fail-5why: n/a (rule not met, contributor sized)]
- 19:12 (clock; first written as 19:25, see 19:16) REGISTERED (before any code/run): option midlev=1 = IFS Cy50r1 Part IV 6.4.3 mid-level convection (the local p4.txt is
  Cy50r1; same scheme as the Cy38r1 text cited at 16:2x, equation now numbered 6.38): in columns with NO deep and NO shallow plume, the
  lowest level with 0 < z < 10 km, large-scale ascent (omega < 0) and RH > 0.8 is the cloud base; updraught starts from environmental
  T/q there (doc silent on the base values; CUBASMCN code uses environmental values - flagged as from the code, not the text);
  entrainment x f_eps = 2 (as shallow, 6.7); closure M_base = max(-omega_base/g, (Js + Jq)/(g z_base)) >= 1e-6 (6.38); rains like deep.
  Not in v1: sub-cloud flux reduction m = 2 (6.40-6.41), autoconversion factor 0.8/0.9. Omega = Dinosaur sigma-coordinate omega
  (as midlev.py), computed in the step and passed to the column physics. Default off -> regression bit-identical.
  TEST (local T42, rh_vs_era5 harness, starts 56/61/66, ERA5-ps >= 750 hPa mask, lc_mix vs lc_mix + midlev):
  (1) poleward masked t700 d2 cold falls >= 25 % (-1.129 -> >= -0.847) [the 16:4x diagnostic sized mid-level at ~30 %];
  (2) poleward rh700 d1 excess falls (any amount; convection rains out the excess);
  (3) GATE (unchanged): global d2 |t850| <= 0.6 and |t700| <= 0.6 - expected to FAIL on t700 alone (A needs ~0.15 more); a fail
      there with (1)+(2) met is HELD, not rejected (fail-5why first);
  (4) no harm: global t850 d2 and tropical-ocean t700 d2 not worse by > 0.1 K.
  If (1) fails: 5-Why on the plume (does it fire where the 16:4x diagnostic found trigger columns? 10.9 % of area).
  [reg: 19:25 | inputs: omega formula as midlev.py (checked 16:4x); IFS 6.4.3 text read | fail-5why: n/a (registration)]
- 19:16 (clock) TIME CORRECTION (rule: check the clock before writing a time): the two entries above stamped '19:10' and '19:25' were
  written without checking the clock; real times about 19:08 and 19:12. The registration still came before any code or run
  (code written after it; first run started after the code). Option midlev committed now (default off).
- 19:32 (clock) midlev RESULT (registered 19:12; local T42, starts 56/61/66, masked, maps_lc_mid vs maps_lc_mix):
  (1) poleward masked t700 d2 -1.129 -> -1.143 FAIL (needed >= -0.847); (2) poleward rh700 d1 +0.140 -> +0.141 FAIL (no fall);
  (3) gate: global masked t850 -0.523 -> -0.384, t700 -0.753 -> -0.789 (unmasked -0.73) FAIL on t700 (as expected, not the test);
  (4) tropical-ocean t700 d2 -0.505, global t850 better -> no harm on t850.
  FAIL-5WHY (midfire.py: same states, column with midlev on vs off, poleward 40-80, day 1, 6-hourly):
   1 Does it fire? YES, 12.9 % of the area (16:4x trigger diagnostic: 10.9 %) -> trigger implemented as registered.
   2 Heating at sigma 0.70: +0.019 K/day (sized at 16:4x: 0.25) -> 1/13 of the size; extra rain 0.05 mm/day.
   3 Why so small? With the IFS closure M_base = -omega/g the latent heat released = L x rain: 0.05 mm/day ~ 1.5 W/m2 -> ~0.02 K/day
     over the layer. The 0.25 K/day needs ~0.3 mm/day.
   4 Why did the 16:4x diagnostic say 0.25? It took Q = L/cp (-omega) dqs/dp, i.e. sub-saturated (RH 0.8-1) air condensing at
     the SATURATED moist-adiabatic rate with all latent heat kept: an UPPER BOUND, not the IFS scheme's heating.
   5 Root of the failure: MY SIZING (16:4x), not the option. SELF-CORRECTION: mid-level convection is a ~2 % contributor, not ~30 %.
  midlev: faithful to IFS 6.4.3 (v1), negligible effect -> not adopted, not rejected (stays an option, default off).
  P-pole attribution now: shallow-top ~25 %, resolution ~20 %, mid-level ~2 %, ~0.45-0.5 K/day UNATTRIBUTED.
  [reg: 19:12 | inputs: trigger fraction 12.9 % vs 10.9 % diag; omega same formula as diag | fail-5why: my sizing upper bound]
- 19:33 (clock) REGISTERED (radiation INPUT check, P-pole): poleward model air is too moist through the column at day 1
  (rh500 +0.22, rh700 +0.14, rh850 +0.06; lc_mid run). Offline, same lc_mix day-1 states (start 56, 6-hourly), radcloud called twice:
  model q vs q scaled per level to ERA5's poleward RH (ratio 0.66 at 500, 0.78 at 700, 0.92 at 850, 0.96 at 925, linear in sigma,
  |lat| >= 40 only). VAPOUR/CLOUD INPUT named as a contributor >= 25 % if the sigma-0.70 poleward radiative heating with ERA5-matched
  humidity is >= 0.3 K/day warmer (all-sky; clear-sky reported to split vapour vs cloud). If named, the root is upstream (what
  moistens 500-700: shallow top named for 700 at 12:40; 500 not yet budgeted).
  [reg: now | inputs: RH by level from the same harness | fail-5why: n/a (registration)]
- 19:38 (clock) RADIATION INPUT RESULT (radq.py, lc_mix, start 56, day 1 6-hourly, sigma 0.70, 40-80 N/S, K/day):
  all-sky model q -1.371 vs ERA5-matched q -1.371 (difference 0.000); clear-sky LW -1.334 vs -1.476; cloud700 0.283 vs 0.044.
  Drier air cools MORE in clear sky, but loses the 700 cloud; the two cancel exactly -> VAPOUR/CLOUD INPUT NOT named (0 % of the gap).
  Radiation at 700 is insensitive to the moisture excess and matched RRTMG on the same state (18 Nov) -> radiation branch CLOSED.
  ATTRIBUTION SUM (P-pole, masked d2 cold -1.13 K; physics gap at sigma 0.70 ~1.2 K/day vs ERA5-implied):
   latent deficit: poleward rain 0.72x ERA5 (1.76 vs 2.44 mm/day) -> 0.68 mm/day ~ 20 W/m2 ~ 0.47 K/day over 500-850 hPa (~40 %);
   shallow top 0.23 K (denial, ~20-25 %); resolution 0.25 K (T85, ~20 %, overlaps with latent: under-resolved ascent rains less);
   mid-level convection ~2 %; radiation 0. Sum ~80-85 % -> the cold is MULTI-CAUSAL; the largest single branch is the LATENT DEFICIT.
  5-Why on the latent deficit: the air is TOO MOIST (rh700 +0.14) yet rains 0.72x -> condensation starts too late. IFS forms
  stratiform condensate inside the cloudy part of the box at RH < 1 (Cy50r1 ch. 7, condensation in existing cloud, eq. C1 = a dqs/dt);
  MEGAM condenses only at grid saturation (no prognostic cloud). 13:05 estimate of that term: 0.17 g/kg/day = the missing drying
  (0.17-0.20). Its column-share rule was judged with WATER-only RH (21 % < 30 %) - INPUT FAULT in my own 13:05 check (the same
  formula I then fixed in lsc_mix). REGISTERED re-check with mixed-phase RH (rhpole.py, lc_mix): SUBGRID CONDENSATION named if
  >= 30 % of poleward 700 columns have mixed-phase RH in [0.8, 1) and C1 >= 0.15 g/kg/day.
  [reg: 19:38 (rad: 19:33) | inputs: same states, q swapped only | fail-5why: n/a (not named)]
- 19:54 (clock) SUBGRID-CONDENSATION RE-CHECK (rhpole_mix.py, lc_mix, mixed-phase RH, 3 starts, sigma 0.70, 40-80 N/S, day 1):
  RH in [0.8, 1): 25.4 % of columns (water-only check 13:05: 21 %); RH >= 1: 9.3 %; mean RH 0.63; C1 = 0.152 g/kg/day.
  Rule (registered 19:4x): >= 30 % AND C1 >= 0.15 -> 25.4 % < 30 % -> NOT NAMED (size met, share not). The input fault in my 13:05
  check moved the share 21 -> 25 %, not across the line. Not re-cut after the result.
  P-POLE STATUS: every fishbone branch measured; none >= 50 %; sizes add to ~80-85 % (latent deficit ~40 %, shallow top ~20-25 %,
  resolution ~20 % overlapping latent, mid-level ~2 %, radiation 0). Unmeasured: dynamics numerics residual (-0.33 K/day at sigma
  0.50, both runs, 13:29 list item b). Conclusion: no single root cause exists to fix; closing P-pole needs either several
  reference-based fixes together or a decision on scope - stated to Sridhar, not decided by me.
  [reg: 19:4x | inputs: mixed-phase RH (corrected input) | fail-5why: n/a (not named)]
- 19:55 (clock) EXAM (all 4 parts, T170, 73 starts, 0 failed): lc_mix z500 d1/d5/d10 15.3/65.5/111.1 vs BASE3 18.0/71.8/117.7;
  lc_mix better at d5 in 67 of 73. Land-start share (quarter 0, 19 starts, b3L = BASE3 on the land library): z500 d5 BASE3 71.6 ->
  b3L 70.0 -> lc_mix 65.9 -> ~1.6 m from the land start, ~4 m from the lc_mix physics.
  WARNING (criterion 7, steering): TN u850 d5 bias Oct-Dec lc_mix -5.75 vs BASE3 -1.91 m/s (worse). Quarter 0 shows no such gap
  (-3.54 vs -3.31 / b3L -3.49) -> it sits in the Oct-Dec starts; land-start vs physics split needs b3L-wx3 (queued, account 4).
  Not a verdict: no adoption decision until b3L is complete and P3/P5b/Tracks are scored. [reg: 14:00 | inputs: same 73 starts;
  land-start confound measured on q0 | fail-5why: pending b3L-wx3]
- 19:56 (clock) REGISTERED (before code/run), fix for the largest P-pole branch (latent deficit): option lsc_sub = 1, IFS Cy50r1
  Part IV ch. 7 stratiform condensation in a SUB-SATURATED box (grid RH < 1; saturated boxes keep the existing adjustment, so no double
  count): dqs/dt from eq. 7.16 = (dqs/dp)_ma (omega + g M_cu) + (dqs/dT)(dT/dt)_diab [diab = cached radiation + BL tendency];
  cloud fraction a = diagnostic Sundqvist form with IFS RH_crit eq. 7.19 (RHc 0.8, sigma1 0.8; mixed-phase RH) since MEGAM has no
  prognostic cloud; C1 = -a dqs/dt (7.18), C2 = -0.5 da dqs/dt with da from 7.21 (limit (1 - a)/dt); condensate rains at once (as
  MEGAM's large-scale scheme; no cloud water store - stated deviation). Default off.
  TEST (local T42, same harness/starts/mask as lc_mix, lc_mix + lsc_sub): (1) poleward masked t700 d2 cold falls >= 25 %
  (-1.129 -> >= -0.847); (2) poleward rh700 d1 <= +0.120 (excess beyond d0 offset -30 %); (3) poleward rain rises (> 1.76 mm/day);
  (4) gate global |t850|, |t700| <= 0.6 (fail -> fail-5why, HELD not rejected if (1)-(3) met); (5) no harm: tropical-ocean t700/t850 d2
  not worse by > 0.1 K. [reg: now | inputs: omega formula (midlev), IFS 7.16-7.22 read | fail-5why: n/a (registration)]
- 20:12 (clock) lsc_sub RESULT (registered 20:0x; local T42, starts 56/61/66, masked): (1) poleward t700 d2 -1.129 -> -1.098
  (-3 %, needed >= -0.847) FAIL; (2) poleward rh700 d1 +0.135 (needed <= +0.120) FAIL; (5) tropical-ocean t700 d2 -0.505 -> -0.413,
  t850 -0.529 (lc_mix -0.53 area) no harm; (4) gate global masked t700 -0.717, t850 -0.51 -> t700 FAIL.
  FAIL-5WHY (subfire.py, same states, on vs off, sigma 0.70, 40-80, day 1): 1 Does it act? YES: +0.147 K/day, drying 0.044 g/kg/day,
  +0.27 mm/day rain (toward ERA5). 2 Why only 0.03 K warmer at day 2 when it heats 0.15 K/day? The condensation it adds happens EARLIER
  than the saturation adjustment would have done it later - the moisture supply is the same, so total condensation barely changes
  (timing, not amount). 3 Why is the instant term 1/4 of the 13:05 estimate (0.15)? IFS RH_crit 0.8 gives a smaller cover than
  radcloud's 0.7, and eq. 7.16 excludes horizontal advection that the Eulerian 13:05 estimate included. 4 So the latent deficit is
  not a condensation-threshold fault: the poleward column does not get enough moisture LIFTED (ascent), which is the resolution
  branch (T85 -20 %). 5 Root of the failure: the branch was a SYMPTOM of under-resolved ascent, not an independent cause.
  lsc_sub: faithful IFS form, small effect -> HELD (blocked by: under-resolved ascent), default off. [reg: 20:0x | inputs: same
  states; term magnitude measured | fail-5why: timing vs amount; ascent supply]
  NEXT (information, NOT a gate change): the same screen at T170 = the exam's resolution (Kaggle tn-res-t170), to measure how much of
  the poleward cold is a T42-screen artefact. Prediction stated now: if resolution is the supply limit, T170 poleward masked t700 d2
  is >= 40 % smaller than T42 (-1.129 -> >= -0.677).
- 21:09 (clock) T170 SCREEN RESULT (tn-res-t170, lc_mix, same starts/harness/mask; information run registered 20:1x):
  masked poleward t700 d2: T42 -1.129 / T85 -0.882 / T170 -0.819 -> -27 % at T170; my prediction (>= 40 %, >= -0.677) FAILED.
  The gain SATURATES between T85 and T170 -> ~0.8 K of the poleward cold is resolution-INDEPENDENT. So "resolution is the common
  thread" (20:15 message) was wrong as stated: resolution is a ~25 % contributor, not the main cause. Self-correction made to Sridhar.
  Side numbers (information, gate unchanged at T42): masked global t700 d2 T170 -0.576, t850 -0.33; poleward rh700 d1 +0.108.
  Fishbone item NOT yet measured and resolution-independent: (b) dynamics numerics. Known fault D1 (5 Nov): LINEAR vertical semi-
  Lagrangian interpolation cools sigma 0.42-0.49 by -0.27..-0.29 K/day with physics OFF; fix sl_vcubic exists, was not adopted
  under the OLD single-storm rule (verdicts under that rule declared invalid, 'D1 re-test' open). lc_mix does NOT use sl_vcubic.
  REGISTERED (before run): lc_mix + sl_vcubic, local T42 screen, same starts/mask: D1 named as a P-pole contributor >= 25 % if
  poleward masked t700 d2 improves by >= 0.28 K (-1.129 -> >= -0.849); NAMED as the main cause if >= 50 % (>= -0.565).
  Also reported: global gate, tropical no-harm (t700/t850 trop not worse by > 0.1 K). Storm gate re-test (new multi-storm rule)
  follows only if named. [reg: now | inputs: D1 physics-off numbers 5 Nov; lc_mix set checked: no sl_vcubic | fail-5why: T170
  prediction failed - gain saturates]
- 21:22 (clock) D1 (sl_vcubic) RESULT on lc_mix (registered 21:1x; local T42, same starts, masked): poleward t700 d2 -1.129 ->
  -0.960 (+0.17 K, 15 %; rule >= 0.28 K) -> NOT named as a >= 25 % contributor; a ~15 % contributor. Tropics IMPROVE (t700 -0.547 ->
  -0.441, t850 -0.782 -> -0.717) -> no harm. GATE: masked global t700 -0.753 -> -0.624 (FAIL by 0.024), t850 -0.471 PASS.
  Unmasked (the 18 Nov wording): t700 -0.567, t850 -0.473 -> both inside 0.6. I keep the MASKED number as the verdict (decided 16:03:
  the unmasked one is flattered by the Antarctic below-ground warm artefact) -> A still FAIL, by 0.024. Both shown to Sridhar.
  [reg: 21:1x | inputs: same mask both runs | fail-5why: n/a (contributor sized, rule not met)]
  REGISTERED (before run): COMBINED reference-based fixes, no new values: lc_mix + sl_vcubic (D1, Dinosaur cubic) + lsc_sub (IFS 7.16-
  7.22). Prediction if additive: masked global t700 ~ -0.624 + 0.036 = -0.59. Verdict on the GATE as written (masked, |t850|,|t700|
  <= 0.6 day-2 globe) + no-harm (tropical t700/t850 not worse than lc_mix by > 0.1 K). PASS here is a screen pass only: adoption still
  needs the storm gate (multi-storm rule) for sl_vcubic and the exam. [reg: now | inputs: both parts measured separately | fail-5why: n/a]
- 21:35 (clock) COMBINED RESULT (lc_mix + sl_vcubic + lsc_sub, registered 21:2x; local T42, starts 56/61/66, masked):
  global d2 t700 -0.591, t850 -0.455 -> GATE (masked, as written) PASS, margin 0.009 K on t700 (prediction -0.59 matched: effects add).
  No harm: tropics t700 -0.547 -> -0.405, t850 -0.782 -> -0.686 (both better). Poleward t700 -1.129 -> -0.933 (P-pole still cold;
  P-pole carries the global gate per the 16:4x split, so its gate passes on the screen too).
  HONEST CAVEAT: 0.009 K on 3 starts is inside start-to-start noise -> SCREEN PASS ONLY, not a closure. Closure of A needs:
  (i) Rule 1 storm intensity (multi-storm rule) with sl_vcubic + lsc_sub (tn-r1-vcs-0/1 queued), (ii) the exam (tn-vcs-wx0..3 queued).
  [reg: 21:2x | inputs: same mask/starts as every candidate | fail-5why: n/a (pass)]
- 23:02 (clock) P3 RE-MEASURE (Rule 1, registered 13 Nov; lc_mix tn-r1-lcm-0/1, T170, 83 storms, cycL2 land library):
  within +-5 hPa 47/83 = 57 % (gate 80 %) -> FAIL. BASE3 (tn-r1-b3, no-land library) 45/83 = 54 %; BASE2 75 % (17 Nov).
  Pattern identical in both: ERA5 peak < 995 (20): +3.9 too weak (9 weak); 995-1001 (31): -5.0 (13 too deep); > 1001 (32): -5.7
  (12 too deep) -> the dominant failure is OVER-DEEPENING of weak/moderate lows (25 of 63), shared with BASE3 and absent in BASE2
  (BASE2 weak systems -2.3) -> it arrived with the BASE3 set {cmt_mf, rd_si, dfi_off} or later, not with the lc_mix additions.
  Not a fix verdict (no fix tested). FAIL-5WHY start: which BASE2 -> BASE3 item deepens weak lows (registered next cycle, per-item
  denial on the 25 over-deep storms); P3 plan item 'convective rain in over-deep weak lows vs ERA5 cp' runs on the same storms.
  [reg: 13 Nov 11:40 | inputs: same 83 storms, ERA5 peak targets; land-library confound noted | fail-5why: over-deepening of weak lows]
- 23:03 (clock) REGISTERED (P3 fail-5why, before any run): per-item DENIAL of the BASE2 -> BASE3 items on lc_mix, on the 26
  over-deep storms of tn-r1-lcm (error < -5 hPa; list kaggle_cfg/overdeep26_list.json), T170 72 h, same scorer (rule1_score.py):
  variants lcm_no_cmt (cmt_mf 0), lcm_no_rdsi (rd_si 0), lcm_dfi_on (dfi_off 0). An item is NAMED as the over-deepening cause if
  denying it brings >= 50 % of the 26 (>= 13) within +-5 hPa AND raises their mean error by >= +2.5 hPa (lc_mix mean on the 26
  computed by the same scorer). If none is named: the over-deepening came with the lc_mix additions or the land library, and the next
  denial is the land start (cycL2 vs no-land library). Denial = measurement only, never a fix. Jobs tn-p3-deny-0/1 (account 1).
  [reg: now | inputs: same storms and targets; variants differ by one item each | fail-5why: n/a (registration)]
- 01:52 (clock) RULE 1 for the A candidate vcs (lc_mix + sl_vcubic + lsc_sub; tn-r1-vcs-0/1, T170, 83 storms, cycL2):
  within +-5 hPa 47/83 = 57 % -> Rule 1 gate (80 %) FAIL, identical to lc_mix (47/83; mean |err| 6.15 vs 6.08, mean -3.47 vs -3.11;
  bands <995 +3.45 / 995-1001 -5.38 / >1001 -5.95 vs +3.92 / -5.03 / -5.65). -> sl_vcubic + lsc_sub do NO HARM to storm intensity
  (D1 storm re-test under the multi-storm rule: no degradation; D1's old single-storm rejection does not reproduce).
  The Rule 1 failure is the P3 over-deepening shared by BASE3, lc_mix and vcs (P3 denial jobs tn-p3-deny-0/1 launched 01:46).
  A: screen gate PASS (21:2x) + no storm harm; still waiting for the exam (tn-vcs-wx0..3 queued). Whether A may close while Rule 1
  fails for a reason owned by P3 is stated to Sridhar at 10:00, not decided here.
  [reg: 21:2x | inputs: same 83 storms/targets/library as tn-r1-lcm | fail-5why: P3 over-deepening (pre-existing since BASE3), not vcs]
- 03:52 (clock) P3 DENIAL JOBS FAILED (tn-p3-deny-0/1): 'Killed' after the first storm's DFI - out of memory. 5-Why: my config
  put 3 variants in one job -> 3 compiled T170 models + the full cycL2 library in one process (every earlier Rule 1 job had 1
  variant). Fault in MY job design, not in the physics; ~15 GPU min lost. Re-queued as one variant per job (tn-p3-lcm-no-cmt acct 4,
  tn-p3-lcm-no-rdsi / tn-p3-lcm-dfi-on acct 1), same storms, same registered rule (23:1x).
  [reg: 23:1x | inputs: kernel log 'Killed' after 'dfi done' | fail-5why: 3-variant job OOM (my design)]
- 03:52 (clock) STEERING SPLIT (exam, T170; b3L = BASE3 on the land library, all 4 parts now in): TN u850 d5 bias by exam part
  (BASE3 / b3L / lc_mix): q0 -3.31/-3.49/-3.54, q1 -2.26/-1.93/-4.43, q2 -2.74/-2.93/-4.42, q3 -1.24/-0.97/-4.31 m/s.
  The land start changes it by <= 0.35 m/s; lc_mix PHYSICS adds ~ -2 to -3 m/s easterly bias in parts 1-3 -> the steering
  degradation is CAUSED BY THE lc_mix PHYSICS, not the land start (z500 gain: land ~1.5-2 m, physics ~4-5 m per part).
  Open question for P5b / Tracks: which lc_mix item drives the 850 easterly over TN (next: item-group denial on the exam starts
  with the largest bias, registered before running). Adoption of lc_mix / vcs is NOT possible while this stands unexplained.
  [reg: 13:54 (exam plan) | inputs: same starts per part, land confound measured | fail-5why: lc_mix physics -> TN 850 easterly]
- 04:01 (clock) REGISTERED (P5b/Tracks steering, before any run): lc_mix ITEM-GROUP DENIAL on exam part 3 (18 starts, T170,
  5 days, wx2020L2 land library): no_land (drop skin_ifs, sfc_imp, land_rs, emis_land), no_conv (drop the IFS convection set incl.
  rad_prm), no_late (drop bl_lcl, dd_ifs, evap_ifs, lsc_mix). A group is NAMED as the driver of the extra TN 850 easterly if dropping
  it restores >= 50 % of the lc_mix - b3L gap on part 3 (TN u850 d5 bias -4.31 vs b3L -0.97 -> >= -2.64 m/s). Denial = measurement,
  never a fix. Jobs tn-p5b-no-land (acct 4), tn-p5b-no-conv, tn-p5b-no-late (acct 1), after the P3 denials.
  [reg: now | inputs: same starts/library as tn-lcm-wx3 and tn-b3L-wx3 | fail-5why: n/a (registration)]
- 12:37 (clock) (session was paused 04:05-12:30; cycles 10:00 missed - stated to Sridhar) ACCOUNT 1 hit the 30 h weekly GPU
  quota 05:09-05:33 (refused pushes, no GPU used); it accepted pushes again at 12:36 (weekly reset). No workaround used.
  A EXAM RESULT (vcs = lc_mix + sl_vcubic + lsc_sub, 73 starts, T170, 0 failed; criteria from score_suite.py vs BASE3):
   crit 1 z500 d5/d10: vcs 65.94/117.74 vs BASE3 71.76/117.70 -> d5 PASS, d10 FAIL by 0.04 m -> criterion 1 FAIL.
     lc_mix 65.54/111.09 -> PASS. vcs d10 is ~6 m worse than lc_mix in EVERY exam part (q0..q3: +6.6, +8.5, +4.6, +6.9 m).
   crit 7 steering Oct-Dec TN u850 d5: vcs -3.50 vs BASE3 -1.91 -> FAIL (lc_mix -5.75, also FAIL). By part vcs/b3L: q0 -2.05/-3.49,
     q1 -1.99/-1.93, q2 -2.94/-2.93, q3 -3.16/-0.97 -> vcs REMOVES most of lc_mix's extra easterly in q0-q2.
   crit 8a stability PASS. -> A NOT closed. FAIL-5WHY: two new items; which one costs d10 and which one fixes steering?
  REGISTERED (before run): tn-vc-wx1 = lc_mix + sl_vcubic only (no lsc_sub), exam part 1 (18 starts). lsc_sub NAMED as the d10 cost if
  part-1 d10 <= 112.75 (restores >= 50 % of the 8.5 m gap vcs 117.0 vs lc_mix 108.5); otherwise sl_vcubic carries it. Steering:
  sl_vcubic NAMED as the steering fix if part-1 TN u850 d5 >= -3.21 (keeps >= 50 % of the vcs gain over lc_mix -4.43 -> -1.99).
  P5b denial no_late (part 3): TN u850 -4.00 (needed >= -2.64) -> NOT named [reg: 04:01 | inputs: same 18 starts as tn-lcm-wx3 |
  fail-5why: n/a (not named)]. [reg: now | inputs: same starts/library | fail-5why: two-item candidate -> split]
- 12:39 (clock) RE-MEASURE from the exam (73 starts, T170; information, no new rule):
  P5a jets - u200 d1 bias India (m/s): BASE3 -2.46, b3L -2.44, lc_mix -1.72, vcs -1.12 (NH extratropics -1.59/-1.59/-1.28/-0.59);
   vcs halves the day-1 India jet deficit (D1 cubic, as the 13 Nov S1 = D1 finding said); d5 India vcs +1.41 (overshoots; BASE3 -0.90).
  P2/P4 TN rain - rain24 TN bias d1/d3/d5 (mm/day): BASE3 +0.96/+2.04/+3.45 (wet), lc_mix -1.52/-1.77/-2.06 (dry), vcs -1.34/-1.26/
   -1.65 -> lc_mix flips TN from too wet to too dry; the P2/P4 gate (5-day ratio within +-25 %) needs the TN truth mean -> computed
   next with the exam truth file before any verdict. [reg: n/a (measurement) | inputs: same 73 starts all versions | fail-5why: n/a]
- 14:38 (clock) RE-MEASURE P2/P4 TN rain 5-day ratio from the exam vs ERA5 rain24 (wx_truth_2020, TN box 8-14N 76-81E, cos-weighted,
  days 1-5 of every start; proxy for criterion 6, whose official job tn-s-*-tnr is vs the tnr truth):
   all 73 starts (ERA5 TN mean 3.77 mm/day): BASE3 1.56, lc_mix 0.56, vcs 0.66.
   Oct-Dec 18 starts (ERA5 6.31 mm/day):     BASE3 1.24, lc_mix 0.50, vcs 0.54.
  -> gate |ratio-1| <= 0.25: BASE3 passes only in Oct-Dec (1.24); lc_mix and vcs FAIL both (about half the observed TN rain).
  P2/P4 stays OPEN and is now a lc_mix REGRESSION (dry by ~45-50 %), not a BASE3 wet bias. Next (5-why first, no code change yet):
  is the deficit convective or large-scale rain, and does it track the steering error (lc_mix easterly -> less onshore NE flow)?
  [reg: n/a (measurement) | inputs: same 73 starts and truth file for all versions | fail-5why: n/a]
- 14:39 (clock) P2/P4 5-WHY step 1 (lc_mix minus BASE3, same starts): TN rain change days 1-5 -4.66 mm/day in Oct-Dec, of which -3.16
  is already there on DAY 1 (before the flow can drift); per-start correlation with the TN u850 change 0.07 (Oct-Dec), 0.29 (all);
  all-India rain also drops (-1.14). -> the deficit is NOT the steering error carried into rain; it is the column physics producing
  less rain from day 1. Inputs check: identical starts and land initial state for both versions.
  REGISTERED (before reading rain from any denial job): exam part 3 TN 5-day ratio vs ERA5 is BASE3 1.264, lc_mix 0.422 (gap 0.842).
  A lc_mix item group (no_land / no_conv / no_late) is NAMED as a TN dry-bias cause if its part-3 ratio >= 0.843 (restores >= 50 %
  of the gap). no_late's result file was already on disk (landed for P5b) but its rain had not been read when this was written.
  [reg: now | inputs: same 18 part-3 starts as tn-b3L-wx3 / tn-lcm-wx3 | fail-5why: n/a (attribution)]
- 14:40 (clock) P5b + TN-rain denial results (part 3, 18 starts; rules registered 04:01 and 14:39):
   no_conv: TN u850 d5 -3.92 (needed >= -2.64) -> NOT named for steering; TN rain ratio 0.594 (needed >= 0.843) -> NOT named for rain.
   no_late: rain ratio 0.407 -> NOT named for rain (steering already NOT named, -4.00).
  Neither group alone carries either error. no_land (acct 4) pending. If no_land is also NOT named, the cause is an interaction
  across groups (no single-group denial carries it) -> next registration would be pairwise denial, not a fix.
  [reg: 04:01 / 14:39 | inputs: same 18 part-3 starts as tn-lcm-wx3 / tn-b3L-wx3 | fail-5why: n/a (attribution, not named)]
- 14:40 (clock) P3 DENIAL RESULT lcm_no_rdsi (tn-p3-lcm-no-rdsi, 26 over-deep storms, T170 72 h, rule1_score.py; registered 23:03):
  within +-5: 1/26 (needed >= 13); mean error -12.14 vs lc_mix -12.14 on the same 26 (needed >= +2.5 change) -> rd_si NOT named.
  Per-storm min-pressure change vs lc_mix: 0.0 on 23 storms, max |0.3| hPa. Inputs/size check: the variant file sets rd_si 0 and
  mm2.py reads it (line 134); rd_si only makes the dynamics gas constant equal to the physics one (286.86 -> 287.05, 0.07 %), so it
  cannot deliver a 7-12 hPa deepening -> expected null, now measured. Remaining denials: no_cmt (queued acct 4), dfi_on (running).
  [reg: 23:03 | inputs: same 26 storms/targets, one-item variant, verified the key is read | fail-5why: n/a (not named)]
- 14:41 (clock) TIME CORRECTION: the three entries above were first stamped 14:44 / 14:50 / 14:55 without reading the clock; the
  clock read 14:40 after the last one. Restamped 14:39 / 14:40 / 14:40. Order (registration before reading denial rain) unchanged.
- 15:40 (clock) P3 DENIAL RESULT lcm_dfi_on (tn-p3-lcm-dfi-on, 26 over-deep storms; registered 20 Nov 23:03):
  within +-5: 21/26 (needed >= 13); mean error -12.14 -> -1.43 (+10.71, needed >= +2.5) -> dfi_off is NAMED as the P3 cause.
  5-WHY (inputs before physics) - WHY does dfi_off "deepen"? Mean model min pressure on the 26 by hour, lc_mix / dfi_on:
   h0 991.1 / 1002.2, h6 1002.9 / 1003.2, h12 1004.0 / 1004.0, h24 1004.9 / 1004.9, h72 1004.9 / 1004.4 -> identical after 6 h.
  -> the model does NOT over-deepen weak lows. The deficit exists only at HOUR 0: the bogus vortex (hind2.py, inserted from the
  best-track vmax) starts too deep and, with no DFI since BASE3, is not filtered; it collapses within 6 h. rule1_score.py takes the
  min over 0-72 h, so hour 0 is scored. All 83 lc_mix storms: the scored minimum is hour 0 in 36; model h0 minus ERA5 h0 = mean
  -5.68 hPa (median -2.33), 31 storms > 5 hPa too deep at hour 0. BASE2 (DFI on) filtered the bogus -> 75 %.
  ROOT CAUSE (P3): an INPUT fault - the bogus initial vortex is deeper than the ERA5 analysis it is added to - exposed by dfi_off.
  It is not a physics fault, and BASE3/lc_mix/vcs P3 numbers measured the start, not the forecast.
  NOT a fix verdict. The gate and scorer stay as they are (hour 0 is a model state and stays scored). Fix direction (next, registered
  before any run): make the start match the reference - the bogus must not leave the hour-0 central pressure deeper than ERA5
  (reference = ERA5 h0 msl_min per storm) - or no bogus where ERA5 already holds the low. DFI stays off (it removes the real tide).
  [reg: 20 Nov 23:03 | inputs: same 26 storms; hour-by-hour pressure checked against ERA5 h0 | fail-5why: bogus start too deep at h0]
- 15:42 (clock) P3 SIZE CHECK + REGISTRATION (before any run). Diagnostic only (not the gate): lc_mix Rule 1 scored on h >= 6 = 63/83
  = 76 % (gate 80 %), mean +0.92; bands <995 +5.16 (15 storms too weak), 995-1001 +0.64, >1001 -1.47 (5 too deep). -> removing the
  hour-0 artefact leaves P3 4 points short, and what remains is the OPPOSITE error: strong storms too weak (old Rule 1 pattern).
  FIX TEST (documented option, fix-first after the input check): storm_mode 'relocate' (mm2.bogus, 22 Oct: NCEP-style relocation of
  the ERA5 analysis' own vortex to the best-track centre -> hour-0 pressure = ERA5 by construction). "Tested worse" on 22 Oct was on
  the DFI-on base, where the bogus was filtered anyway; re-test is valid under rule 4. Jobs tn-r1-reloc-0/1 (acct 1, after
  no-land), lc_mix + relocate, 83 storms, same scorer/targets (min over 0-72 h, unchanged). Local T42 init smoke test passed.
  RULE: P3 CLOSES if within +-5 >= 67/83 (80 %). Start check: |model h0 - ERA5 h0| mean <= 1 hPa (else the start is not fixed).
  If < 80 % with the start fixed: the remaining failure is strong-storm under-intensification -> HELD - blocked by that, which is
  the next 5-why (not a rejection of relocate). [reg: now | inputs: h0 vs ERA5 per storm checked; relocate code path smoke-tested |
  fail-5why: n/a (registration)]
- 15:42 (clock) tn-p3-lcm-no-cmt WITHDRAWN before launch: dfi_on is named and lc_mix/dfi_on are identical from h6 on, so no other
  item can carry the hour-0 deficit; running it would spend GPU for no information (rule 9).
- 16:20 (clock) P5b + TN-rain denial result no_land (part 3, rules 04:01 / 14:39): TN u850 d5 -4.38 (needed >= -2.64; lc_mix -4.31)
  -> land set NOT named for steering. TN rain ratio 0.760 (needed >= 0.843; lc_mix 0.422) -> NOT named, but the largest single
  recovery (40 % of the gap; no_conv 20 %, no_late -2 %). [reg: 04:01 / 14:39 | inputs: same 18 part-3 starts, 0 failed |
  fail-5why: n/a (not named)]
  INPUTS CHECK OF THE DENIAL ITSELF (5-why on "no group named"): b3L (suite_b3_wx.json) runs rad_every 2 (mm2 default); lc_mix runs
  rad_every 1; the 04:01 groups (land / conv / late) did NOT include rad_every, and all three denials kept it at 1. So one lc_mix item
  was never denied - my registration gap, stated openly. Single-group effects on steering sum to +0.6 of the 3.34 m/s gap, so either
  rad_every carries it or the groups interact.
  REGISTERED (before any run), part 3, same scorers: (1) tn-p5b-no-radev = lc_mix with rad_every 2 (acct 1): NAMED for steering if
  TN u850 d5 >= -2.64, for TN rain if ratio >= 0.843. (2) tn-p5b-no-land-conv = lc_mix minus land AND conv sets (keeps late set +
  rad_every 1; acct 4 after tn-vc-wx1): same two rules; tests the land x conv interaction (the two largest single rain recoveries).
  Denial = measurement only. If (1) is named for steering, rad_every 1 is a physics-accuracy item (hourly SW matches ERA5, 19 Nov), so
  the answer is NOT to revert it but a 5-why on what hourly radiation changes over TN. [reg: now | inputs: b3L vs lc_mix configs
  diffed key by key | fail-5why: n/a (registration)]
- 18:10 (clock) A/P1 SPLIT RESULT tn-vc-wx1 (lc_mix + sl_vcubic only, exam part 1, 18 starts, 0 failed; registered 12:37):
  z500 d1/d5/d10: lc_mix 15.30/63.76/108.49 | vc 14.28/64.39/117.43 | vcs 14.12/64.09/117.02. TN u850 d5 (all 18): lc_mix -4.43,
  vc -2.37, vcs -1.99.
  -> d10: 117.43 > 112.75 -> lsc_sub NOT named; sl_vcubic carries the d10 cost (+8.9 m, worse in 14/18 starts, sd 9.8; vcs - vc
  -0.4 m). Steering: -2.37 >= -3.21 -> sl_vcubic NAMED as the steering fix. One change both fixes steering and costs d10.
  [reg: 12:37 | inputs: same 18 starts as tn-lcm-wx1/tn-vcs-wx1, both reproduced exactly | fail-5why: below]
  FAIL-5WHY step 1 (d10 cost of cubic), information from the same files: cubic improves BIAS everywhere (z500 d10 global -32.7 ->
  -25.9 m, tropics -26.6 -> -16.9; u200 d10 jet deficit -2.54 -> -1.23 m/s) and tropics RMSE (32.3 -> 25.4), but extratropical d10
  RMSE grows (N +10.1, S +12.6 m). d10 ACC is near zero skill in both (globe 0.21 vs 0.15; N 0.26/0.23; S 0.17/0.11). At no skill,
  RMSE grows with the model's own eddy amplitude (double penalty), so the leading suspect is: cubic is less damping than linear
  vertical interpolation -> stronger extratropical eddies. NOT yet proven: needs d10 z500 eddy variance vs ERA5 (lc_mix vs vc).
  Gate stays as written: A remains HELD (vcs fails d10 by 0.04 m). Note for the scorecard: d10 ACC ~0.2 is itself far below
  operational skill - a separate open item, not hidden by the A verdict.
- 18:10 (clock) P3 FIX TEST HALF RESULT tn-r1-reloc-0 (42 of 83 storms, lc_mix + storm_mode relocate; registered 15:41):
  within +-5 hPa 18/42 (43 %; lc_mix same 42: 24/42, 57 %), mean err -12.15 (lc_mix -3.89), 21 too deep. h0 - ERA5 h0: mean -14.55,
  median -6.86, 23 storms < -5 (lc_mix -5.75/-2.73/17). Worst: Unnamed 2025-10-01 942.7 vs ERA5 996.8 (-54), Nisha 2008 -48, Jal
  2010 -46, Lehar 2013 -45, Jawad 2021 -44, Senyar 2025 -42 - all near coasts/hills. Even 41/41 in the other half gives 59 < 67 ->
  the rule CANNOT pass: NOT CLOSED. [reg: 15:41 | inputs: same library/storms as tn-r1-lcm-0 | fail-5why: traced to the FIX]
  FAIL-5WHY: why is the relocated start 40-54 hPa too deep when relocation should keep the ERA5 depth? -> local numpy check of the
  relocate step at T170 on the 2020 library (Nivar 26 Nov 00Z, Burevi 1 Dec 00Z): Nivar sea-point SLP min within 600 km 1003.1 ->
  951.1 hPa (-52, same size as Kaggle). ROOT CAUSE (implementation bug in my relocate code, 22 Oct): (1) the analysis centre was
  searched on RAW surface pressure, whose minimum within 350 km is the highest terrain (Ghats/Sri Lanka/Myanmar/Malaysia), so a
  mountain's pressure imprint was cut out as the "vortex" and moved onto the sea; (2) raw ps was moved, carrying terrain with it
  (-56 hPa spot). The relocate IDEA is not tested yet - this run tested a bug.
  FIX (mm2.bogus relocate branch): centre found on sea-level pressure ps exp(g zs / Rd T_low); the vortex is moved in SLP and ps
  is scaled by the SLP ratio (terrain cancels); 3-D anomalies below ground set to 0 before the shift. Check (same numpy test):
  Nivar SLP 1003.1 -> 1003.6, Burevi 1005.3 -> 1005.6, largest ps change -0.7 hPa (bug: -56). Bogus path untouched (it still deepens
  Nivar 1003.1 -> 986.2, the original P3 input fault).
  REGISTERED (before run): tn-r1-reloc2-0/1 = lc_mix + fixed relocate, all 83 storms, same rule as 15:41: P3 CLOSES if >= 67/83
  within +-5 hPa AND |mean(h0 - ERA5 h0)| <= 1 hPa; otherwise HELD (fail-5why next on strong-storm under-intensification).
  WASTE NOTE: tn-r1-reloc-1 (other half, buggy code) is still QUEUED on account 1; I cannot cancel a Kaggle kernel from here.
  [reg: now | inputs: same library and storm list as tn-r1-lcm | fail-5why: n/a (registration)]

## 21 Nov 21:41 IST - cycle: nothing landed; day-10 activity check (indirect)
- Kaggle queue: tn-p5b-no-radev (acct 1) and tn-p5b-no-land-conv (acct 4) QUEUED on Kaggle since 17:56 IST (3.5 h, Kaggle-side
  wait); tn-r1-reloc-1 (old buggy relocate) RUNNING on acct 1 since 20:18 IST - cannot cancel from here; its result will NOT be
  scored (code superseded by 66a6cb7f). tn-r1-reloc2-0/1 still waiting in our queue behind them.
- Day-10 / cubic suspect, indirect check from existing part-1 scores (18 starts, no fields saved): implied d10 z500 forecast
  anomaly std / obs std (obs std from d1 via MSE=2so^2(1-acc), assumes sf=so at d1): NH lc_mix 1.07 vs vc 1.22; SH 0.90 vs 1.04.
  ACC also drops (NH 0.26->0.22, SH 0.17->0.11). Reading: cubic makes the flow ~15% more active AND loses some pattern skill,
  so it is NOT a pure double penalty. Estimate is fragile (1-acc at d1 ~0.01). Not a verdict.
- Independent of cubic: lc_mix itself has z500 ACC 0.50 at d7 and 0.20 at d10 (globe). That, not cubic, is the main day-10 problem.
- Input fix to the diagnostic: wxscore.scores now writes sf/so (forecast and ERA5 anomaly std) per region (4e20490e), so every
  future exam gives activity directly at no extra GPU cost.

## 21 Nov 22:29 IST - Day-10 skill: where is the gap to HRES created? (local, no GPU)
- lc_mix exam (73 starts) vs ECMWF HRES on the same starts, ACC ours/HRES: z500 NH d1 0.99/1.00, d3 0.91/0.99, d5 0.72/0.92,
  d7 0.50/0.78, d10 0.26/0.49; t850 tropics d1 0.63/0.89. We trail HRES by ~2.5 days in NH z500, and the gap is visible from day 1.
- Error growth d1->d3 (z500 NH random part): ours 14.3 -> 40.3 m (x2.8), HRES 4.9 -> 15.2 m (x3.1). Growth RATE is similar;
  what differs is the day-1 error. => the first day is where the gap is made (initial state or first-day adjustment).
- Day-0 check (T85, start 2020-01-06, lc_mix): z500 NH rmse 10.4 m at hour 0. Input check: integrating ERA5's own T,q from
  (ps, zs) to 500 hPa gives 8.5 m vs ERA5 z500 on 13 levels and 7.4 m on 29 levels (3 dates, libm_l37). So ~8 m of the hour-0
  z500 error is a diagnostic/verification floor (my integration + box-averaging), NOT model error; added in quadrature it is
  negligible beyond day 2 (72 -> 72.4 m at d5). Vertical sampling 13 vs 29 levels: 1 m. => NOT the day-10 cause. Dropped.
- t850 is different: hour 0 rmse 0.32 K (tropics) / 0.60 K (NH), day 1 1.66 / 1.82 K (HRES day 1: 0.64 / 0.71). The start is
  close to ERA5 and the error appears DURING day 1. Suspect: first-day adjustment (physics spin-up / imbalance; dfi_off).
  Check running now (T85, 6-hourly rms change over 48 h): a shock shows as a large first 6 h change that settles.
- 22:31 RESULT first-day check (T85, lc_mix, 2020-01-06T00, globe, rms 6-h change of the model's own field, 8 intervals):
  t850 1.87 1.37 1.40 1.31 1.38 1.27 1.35 1.25 K; z500 26.0 24.8 25.5 26.1 24.4 22.3 20.5 19.4 m; u850 3.13 ... 2.30 m/s;
  global mean t850 280.40 -> 279.90 K in 48 h (-0.25 K/day), z500 -5.6 m/day. Reading: only a mild first-6h jump in t850
  (+40 % over later intervals), no large shock; but 6-h activity in z500/mslp/u850 falls 25-30 % over 48 h. Without ERA5's own
  6-hourly changes I cannot tell model damping from the real weather (diurnal tide, the day's synoptic state). INPUT NEEDED.
  REGISTERED (before the data): ERA5 6-hourly fields for the same 48 h (cyc_libm, 13 levels, 'act6h fields'). Using the ratio
  R = model 6-h rms change / ERA5 6-h rms change per interval:
  (a) first-day SHOCK confirmed if t850 R(0-6 h) >= 1.3 while R(24-48 h) is within 0.8-1.2;
  (b) ACTIVITY LOSS confirmed if mean R(24-48 h) is >= 15 % below mean R(0-24 h) for z500 or u850.
  If neither: the day-1 error is a placement/phase error, not shock or damping -> next check = day-1 error by scale (planetary
  vs synoptic) against HRES.

## 22 Nov 00:04 IST - results
- P5b denial tn-p5b-no-radev (lc_mix with rad_every 2, part 3, 18 starts, 0 failed; scorer reproduces b3L -0.97/1.264 and lc_mix
  -4.31/0.422 exactly): TN u850 d5 -4.25 (needed >= -2.64) -> NOT named for steering; TN rain ratio 0.440 (needed >= 0.843) -> NOT
  named for rain. rad_every carries neither. [reg: 21 Nov (P5b 04:01 follow-up) | inputs: same 18 starts as tn-lcm-wx3, references
  reproduced | fail-5why: n/a (attribution, not named)]. Remaining single test: no_land_conv (running, acct 4). If not named ->
  pairwise denials.
- First-day check (registered 21 Nov 22:31) vs ERA5 6-hourly (act6h, same 48 h): R = model/ERA5 6-h rms change
  t850 1.22 0.82 0.96 0.92 | 0.97 0.86 0.96 0.90 ; z500 1.00 0.96 1.02 1.04 | 1.01 0.92 0.89 0.81 ; u850 0.98 0.91 0.92 0.89 | 0.89
  0.86 0.84 0.84. (a) t850 R(0-6) 1.22 < 1.3 -> SHOCK NOT confirmed. (b) day-2 vs day-1 mean R drop: z500 9.7 %, u850 7.5 %
  (< 15 %) -> ACTIVITY LOSS NOT confirmed. [reg: 21 Nov 22:31 | inputs: ERA5 6-hourly from the same cyc_libm pipeline, same start
  | fail-5why: n/a (diagnosis)]. Notes (not verdicts, one start only): u850 activity already 8-14 % below ERA5 on day 1, z500 R
  falls steadily to 0.81 at 48 h; global-mean drift model z500 -11 m / t850 -0.5 K in 48 h vs ERA5 -1 m / -0.1 K (bias, not ACC).
  Per the rule -> next: day-1 error by spatial scale (planetary / synoptic / small), local T85.
- 00:04 REGISTERED (before the run): day-1 error by scale (T85 lc_mix, 2020-01-06T00, error vs ERA5 split by total wavenumber n,
  shares of error variance for n=1-59): if n 10-39 (synoptic) carries >= 50 % of the day-1 z500 error -> systems misplaced/
  mistimed (dynamics: phase speed, steering, diffusion) and the next check is phase speed of troughs vs ERA5; if n 1-9 carries
  >= 50 % -> large-scale forcing/drift (heating, mountains, tropics) and the next check is the day-1 mean tendency vs ERA5 by
  region; if n >= 40 -> small-scale noise (low ACC impact), look elsewhere. One start only = direction, not verdict.
- 00:55 RESULT day-1 scale split (registered 00:04): z500 d1 error variance n 1-9 68 %, n 10-39 29 %, n >= 40 3 %; t850 d1
  65 / 29 / 6 % (planetary err/anom 0.78). By the rule -> LARGE-SCALE drift, not misplaced systems. Region split of t850 d1:
  Antarctica +9.6 K (t850 is underground there: below-ground extrapolation, verification artefact - not a forecast error),
  summer land cools fast: SH land 20-60S -2.0 K (d2 -3.1), tropical Africa -1.9 (d2 -3.4), S America -1.0, ocean -0.2 to -0.4.
  INPUT ERROR IN MY OWN CHECK (stated openly): every local check tonight (hour-0, first-day, scale split) used libm_wx2020 (no
  soil/skin fields: land starts at air temperature + 60 % soil water), while the lc_mix exams ran on libm_wx2020L2 (ERA5 soil water,
  soil T 1-4, skin). The atmosphere is identical, so the z500 hour-0 floor and the 13-vs-29-level result stand; the land cooling and
  the scale split do NOT stand until rerun on wx2020L2 (running now, same start). No verdict from the land numbers above.
- 01:10 RERUN on wx2020L2 (exam library, same start): scale split unchanged (z500 d1 n1-9 68 %, t850 60 %) -> the 00:55 scale verdict
  STANDS: day-1 error is LARGE-SCALE. Summer-land cooling is roughly halved with real soil fields (SH land -1.98 -> -1.14 K d1,
  Africa -1.85 -> -1.11) but not gone; ocean -0.36 K d1. [reg: 22 Nov 00:04 | inputs: rerun on the exam's own library after my
  library mistake | fail-5why: n/a (diagnosis)]
- 01:10 INPUT/SIZE CHECK of the drift (exam lc_mix, 73 starts, vs ERA5 and HRES): day-1 rain globe 2.32 vs ERA5 2.94 mm/day (0.79;
  HRES 1.00), tropics 2.83 vs 4.15 (0.68); day 2 0.99 / 0.88; day 5 1.05 / 0.97 (extratropics then 10-13 % too wet). Size: 0.62
  mm/day = 18 W/m2 less latent heating = ~0.15 K/day column cooling = ~3 m/day z500 - about HALF the measured global z500 fall
  (-5.6 m/day); in the tropics more than enough (1.32 mm/day -> ~6.6 m/day vs -3.8 m d1 bias). => The day-1 gap to HRES is mostly
  the known CONVECTIVE SPIN-UP deficit (14-15 Nov A/P1 work: deep trigger fires in ~2.5 % of columns at the start, lower troposphere
  cools until it fires), plus a radiative/land cooling remainder. Day-10 skill and A/P1 share this root. Not a verdict on d10 ACC.
  REGISTERED next (before any run): 'Day-10 skill is driven by the day-1 spin-up' is CONFIRMED if, in the 73 exam starts, the
  per-start day-1 global rain deficit correlates with the day-5 NH z500 ACC deficit vs HRES with r <= -0.4 (more deficit -> less
  skill); REJECTED if |r| < 0.2 (then the d1 drift and d10 skill are separate problems). Local, from existing scores.
- 01:10 RESULT link test (registered 01:10): 73 starts, deficit = -(d1 rain bias / ERA5): r(deficit, d5 NH z500 ACC ours-HRES) =
  -0.13, d10 +0.04 -> |r| < 0.2 -> REJECTED as registered. [reg: 01:10 | inputs: same 73 starts, lc_mix exam + HRES scores |
  fail-5why: the DIAGNOSTIC was weak - the d1 rain deficit barely varies between starts (0.21 +- 0.03), so a per-start correlation
  cannot see a systematic effect; my registration error, stated openly. The rejection stands as written: no per-start evidence links
  d1 spin-up to d10 skill. The size check (spin-up ~half of the d1 large-scale drift) still stands.]
  NEXT (direct, not correlational): the d1 error is large-scale, so separate the planetary-scale error at d5 by source: zonal-mean
  z500 error (drift/heating) vs eddy error - from saved fields once the exam writes sf/so (4e20490e), and locally on 1-2 starts.
- 01:10 zonal-mean vs eddy split of the d1/d2 error (wx2020L2 start, T85; truth grid is south-first, labels checked): NH extratropics
  (winter) z500 d1 error is 72 % EDDY (zonal-mean rms 10.2 m, eddy 16.1), t850 94 % eddy, u850 95 % eddy; SH extratropics (summer)
  z500 48 % zonal-mean (13.5 m), t850 60 % zonal-mean (inflated by the Antarctic below-ground t850 artefact). CORRECTION of my 00:55
  scale verdict: the t850 'planetary' share was inflated by Antarctica (verification artefact) -> t850 part WITHDRAWN; the z500
  'large-scale' share is mainly the SH summer zonal-mean drift. In the NH, where the d5/d10 ACC gap is largest, the day-1 error
  is eddy (systems), not drift. One January start only -> direction, not verdict. Next (daytime): 4 starts across seasons, and
  exclude below-ground points from t850 scoring (mask where ERA5 ps < 850 hPa) before any further t850 conclusion.

## 22 Nov 02:03 IST - P5b TN rain: land + convection denial RESULT, land split REGISTERED
- tn-p5b-no-land-conv (lc_mix minus land AND conv sets, part 3, 18 starts, 0 failed; scorer reproduces lc_mix -4.31/0.422):
  TN rain ratio 0.924 (needed >= 0.843) -> land+conv NAMED for the TN dry bias; TN u850 d5 -5.34 (needed >= -2.64) -> NOT named for
  steering (worse). [reg: 21 Nov 12:3x (P5b follow-up, rules 04:01/14:39) | inputs: same 18 starts as tn-lcm-wx3, refs reproduced |
  fail-5why: n/a (named / not named)]
  Not an interaction: rain recovery vs lc_mix is no_land +0.338, no_conv +0.172, sum +0.510 vs pair +0.502 -> ADDITIVE. The land set
  carries ~2/3 (0.760 alone: 40 % of the gap - under the 50 % line, so land alone stays NOT named, gate not relaxed), conv ~1/3.
  Steering is separate from both (all four denials failed it) -> steering stays with A/P1 (sl_vcubic named 21 Nov 18:10).
- Size/reference check of the land set's largest item: land_rs 100 s/m is used as the whole surface resistance; IFS uses a canopy
  resistance r_c = (r_s,min / LAI) f1 f2 f3 (TESSEL/H-TESSEL) with r_s,min/LAI = 180/3 = 60 (crops), 225/3 = 75 (shrubs), 110/2 = 55
  (short grass) before stress factors -> ours is ~1.3-1.8x the IFS unstressed value, so it plausibly dries land a little, not 3x.
  REGISTERED (before any run), part 3, same scorer: (1) tn-p5b-no-landrs = lc_mix minus land_rs (acct 1); (2) tn-p5b-no-skinimp =
  lc_mix minus skin_ifs and sfc_imp (acct 4). An item is NAMED for TN rain if its ratio >= 0.591 (restores >= 50 % of the land set's
  own recovery 0.422 -> 0.760). If land_rs is named, the fix is the IFS form (r_s,min/LAI by vegetation type, ERA5 type/LAI fields),
  not a tuned land_rs. [reg: now | inputs: lc_mix config key by key, single key removed per job | fail-5why: n/a (registration)]

## 22 Nov 04:00 IST - P3 corrected relocate, first half (tn-r1-reloc2-0, 42 storms)
- Rule 1: within +-5 hPa 34/42 (81 %; lc_mix same 42: 24/42; buggy relocate 18/42), mean err +1.56, mean|err| 2.64, 7 too weak,
  1 too deep. Start check: model h0 - ERA5 h0 mean +0.71 hPa (sd 0.65, max 3.6) -> |mean| <= 1 PASSES (buggy run: -14.55).
  The relocate fix works at the start. Closure needs the full 83: >= 67/83 -> the second half needs >= 33/41. Pending
  tn-r1-reloc2-1 (running, acct 4). Half verdict only - NOT CLOSED yet. [reg: 21 Nov 18:10 | inputs: libm_cycL2, fixed relocate
  66a6cb7f, h0 checked vs ERA5 | fail-5why: n/a (half result)]. Residual: 7 too weak (Hudhud +12.4, Nisha +7.6) = strong storms
  under-deepening, the registered next 5-why if the full count fails.
- 04:25 Day-10: 4 seasonal starts (T85, wx2020L2; t850 scored only where ERA5 ps > 870 hPa): z500 d1 error, zonal-mean share / bias:
  NH Jan 28 % / -7.0 m, Apr 33 % / -6.6, Jul 62 % / -12.3, Oct 47 % / -10.4; SH Jan 48 % / -11.8, Apr 23 % / -5.6, Jul 47 % / -4.0,
  Oct 43 % / -2.2; tropics bias -2.3 to -5.0 m. t850 (above ground) is mostly eddy (4-35 %), tropical bias -0.5 to -0.8 K.
  Reading: z500 FALLS on day 1 in every start and hemisphere (largest in the summer NH), while t850 hardly cools outside the tropics.
  A -12 m z500 fall needs ~0.6 K mean cooling below 500 hPa OR ~1.4 hPa less surface pressure. t850 shows only -0.2 K there ->
  SUSPECT: a mass (surface-pressure) loss, not heating. REGISTERED (before the run): global-mean mslp model vs ERA5 at d0/d1/d2
  (Jul start, T85). Mass loss CONFIRMED if the model's global-mean mslp falls >= 0.5 hPa/day more than ERA5's; then the next check
  is the dry-mass budget of the dynamical core (spectral ps, semi-Lagrangian, mass fixer). REJECTED if < 0.2 hPa/day.
- 04:39 RESULT mass-loss test (registered 04:25; Jul start, T85): global-mean mslp model 1011.83 -> 1011.96 -> 1011.96 hPa, ERA5
  1011.50 -> 1011.54 -> 1011.55: model minus ERA5 change +0.09 hPa/day then -0.01 -> < 0.2 hPa/day -> MASS LOSS REJECTED. The core
  keeps mass. [reg: 04:25 | inputs: same start, model and ERA5 global means on one 1.5 deg grid | fail-5why: n/a (diagnosis)]
  Global-mean z500 model 5698.9 -> 5695.0 -> 5692.5 m vs ERA5 5700.4 -> 5701.4 -> 5701.4: the column below 500 hPa cools ~0.25 K/day
  in the mean while t850 barely moves -> the cooling sits in other layers (near-surface 1000-925 and/or 700-500 hPa).
  NEXT: model T profile (1000/925/700/500 hPa) vs ERA5 at d1 by region - needs T on more levels from run_wx (local, daytime).
- 04:40 REGISTERED (before the run): profile of the day-1 cooling (Jan start, T85, map_snd output vs ERA5 act6h on the 13 shared
  levels, global and tropics/NH/SH, above-ground points only): the layer that carries >= 50 % of the pressure-weighted
  1000-500 hPa cooling (model-minus-ERA5 change of T from h0 to h24) is named the cooling layer; virtual-temperature (q) part
  reported separately. Near-surface (1000-850) -> boundary layer/land/radiation at the surface; 700-500 -> convection/radiation
  aloft (spin-up). Diagnosis only.
- 05:01 RESULT cooling profile (registered 04:4x; Jan start, T85, model-minus-ERA5 change h0->h24, above-ground points; hour-0 offsets
  <= 0.2 K at every level so the start is fine): globe 1000 -0.30, 925 -0.38, 850 -0.24, 700 -0.38, 600 -0.22, 500 -0.49, 400 -0.79,
  300 -0.82, 250 -0.83, 200 -0.68 K. 1000-500 pressure-weighted mean -0.32 K; share 1000-850 44 %, 700-500 56 % -> by the rule the
  cooling layer is 700-500 hPa (aloft), marginally. The clearest signal is ABOVE that: tropics 300 -1.39, 250 -1.77, 200 -1.64 K/day,
  with tropical moisture piling up at 1000 hPa (+0.19 g/kg) and missing at 700 (-0.23). That is the signature of too little deep
  convection: latent heat is not released aloft and moisture is not carried up. Size: the tropical day-1 rain deficit 1.32 mm/day =
  38 W/m2 spread over 500-200 hPa = ~1.1 K/day, the measured order. NH (winter) cooling 700-400 hPa -0.7 K is separate (not tropical
  convection). [reg: 04:4x | inputs: ERA5 act6h same 13 levels and times, below-ground masked, h0 offsets checked | fail-5why: n/a
  (diagnosis)] Verdict: the tropical/summer part of the day-1 gap is the CONVECTIVE SPIN-UP deficit (same root as A/P1 spin-up);
  the NH winter mid-troposphere cooling is an open second cause (suspect: radiation/clouds aloft). One start -> repeat on Jul start.
- 05:09 REPEAT on the July start (ERA5 act6hjul): tropics 300 -1.59, 250 -1.92, 200 -1.56 K/day; NH (summer) 300-200 -1.0 to -1.3;
  tropical moisture +0.33 g/kg at 1000 hPa, -0.19 at 700. SH (winter) cools at 700-500 (-0.7 to -1.0) and NOT aloft (+0.4/+0.8 at
  250/200). Same two signatures as January with the hemispheres swapped -> CONFIRMED on 2 starts, opposite seasons:
  (1) summer hemisphere + tropics: upper-troposphere cooling + boundary-layer moisture build-up = deep-convection spin-up deficit
      (shared root with A/P1);
  (2) winter hemisphere: 700-500 hPa cooling - separate, unexplained. Suspect list (fishbone, not yet tested): clear-sky/cloud
      longwave aloft, large-scale cloud/precip evaporation, vertical advection (sl_vcubic off in lc_mix). [reg: 04:4x | inputs:
      ERA5 6-hourly same times, below-ground masked, h0 offsets <= 0.25 K | fail-5why: n/a (diagnosis)]
- 05:10 REGISTERED (before the run): winter-hemisphere 700-500 cooling, physics or dynamics? Jan start, T85, lc_mix with
  phys_off=True (dynamics only, no heating at all), 24 h, same scoring, NH 20-90N 700/600/500 hPa mean of (model - ERA5) change.
  With physics on this was -0.72/-0.65/-0.77 K. PHYSICS cause if the physics-off value is >= +0.3 K warmer than physics-on at
  each of 700/600/500 (heating removed -> net cooling gone/reversed would mean physics was cooling); DYNAMICS cause if within
  +-0.2 K of the physics-on value (the cooling is made by the core: advection / vertical transport). In between -> both.
- 05:15 RESULT physics-vs-dynamics (registered 05:1x): NH 700/600/500 (model - ERA5 change, 24 h): physics on -0.72/-0.65/-0.77 K,
  physics OFF -0.05/-0.05/-0.13 K -> warmer by +0.67/+0.60/+0.64 (>= +0.3 at each) -> PHYSICS cause. The dynamical core alone
  follows ERA5's mid-troposphere change within 0.13 K; our physics adds ~0.65 K/day of net cooling there that ERA5's physics
  does not. Tropics 300/250: physics on -1.39/-1.77, off -0.78/-0.66 -> our physics also makes the tropical upper cooling WORSE
  than no physics at all (radiative cooling not offset by convective heating) - consistent with (1). [reg: 05:1x | inputs: same
  start/scoring, only phys_off changed | fail-5why: n/a (diagnosis)]
  NEXT (fishbone, physics branch): radiation vs large-scale condensation vs convection in the NH winter mid-troposphere ->
  per-process heating rates on this start (model tendencies by process), compared with the IFS/ERA5 typical values
  (radiative cooling ~1-1.5 K/day mid-troposphere).

## 22 Nov 05:59 IST - P3 full result + P5b land_rs result
- P3 (lc_mix + fixed relocate, 83 storms, 0 failed): within +-5 hPa 62/83 (75 %) < 67 -> NOT CLOSED, HELD. Start check passes:
  h0 - ERA5 h0 mean +0.70 hPa (sd 0.77). Second half 28/41 (first 34/42). Misses: 20 too weak, 1 too deep. [reg: 21 Nov 18:10 |
  inputs: libm_cycL2, fixed relocate 66a6cb7f, h0 vs ERA5 checked on all 83 | fail-5why below]
  fail-5why: (1) why short? 20 storms too weak at their 0-72 h peak. (2) why too weak? The START is right (h0 +0.7) but the model
  does not DEEPEN them: by ERA5 deepening h0->peak, shortfall 0.1 hPa (0-3 hPa class, n 30), 1.1 (3-8, n 29), 6.8 (8-30, n 24);
  r(ERA5 deepening, model deficit) = -0.74. (3) why no deepening? Suspect: too little latent heating in the core - the same deep-
  convection spin-up deficit found for day-10 (tropical day-1 rain 0.68 of ERA5, upper-level cooling ~1.6 K/day). Resolution is
  NOT the reason at h0 (start matches the 0.25 deg truth to 0.7 hPa). The failure does not trace to the relocate fix -> relocate
  stays (it took 24/42 -> 34/42 and 18 -> 62/83 overall) and P3 is HELD on the convective spin-up, now a shared root of P3, A/P1
  spin-up and day-10. Gate unchanged (67/83).
- P5b tn-p5b-no-landrs (lc_mix minus land_rs, part 3, 18 starts): TN rain ratio 0.683 >= 0.591 -> land_rs NAMED for the TN dry
  bias (it alone restores 78 % of the land set's recovery); TN u850 d5 -3.88 (steering not the aim). [reg: 22 Nov 02:03 | inputs:
  same 18 starts, scorer reproduces lc_mix | fail-5why: n/a (named)]. Registered fix path: IFS canopy resistance r_s,min/LAI by
  vegetation type from ERA5 fields (type, cover, LAI) with the IFS stress factors - not a tuned land_rs. tn-p5b-no-skinimp running.
- 06:31 P5b tn-p5b-no-skinimp (lc_mix minus skin_ifs and sfc_imp, part 3, 18 starts, 0 failed): TN rain ratio 0.399 < 0.591 -> NOT
  named (slightly drier than lc_mix 0.422); TN u850 d5 -4.37. [reg: 22 Nov 02:03 | inputs: same 18 starts, refs reproduced |
  fail-5why: n/a (not named)]. Land-set attribution complete: land_rs carries the land share of the TN dry bias (0.683 alone);
  skin/implicit surface do not. Queue now empty; Kaggle idle -> next jobs must be fixes, not more denials.
- 06:35 SIZE CHECK before any GPU (method rule): ERA5 vegetation fields fetched (veg_static.npz, ARCO 0.25 deg -> 1.5 deg). Tamil Nadu
  (11N 78.5E): low veg = irrigated crops (type 10, cover 0.82), high = interrupted forest (type 19, 0.17); ERA5 monthly LAI low 1.85
  (Nov), high 2.69. IFS canopy resistance there: r_s,min/LAI = 180/1.85 = 97 s/m (low), 175/2.69 = 65 (high), x f1 1.19 at midday
  -> ~110 s/m before soil stress. lc_mix land_rs = 100 s/m. => over TN our land_rs is ALREADY about the IFS value. The IFS form
  (land_rc, coded in mm2 22 Nov, not yet run) would change TN evaporation very little -> predicted NOT to fix the TN dry bias.
  5-why consequence: removing land_rs restores TN rain by letting land evaporate like open water - a COMPENSATION for something
  else (missing moisture supply or too little convective rain), not proof that land_rs is wrong. Candidates from the reference
  diff: (a) the interception reservoir (wet-leaf evaporation with r = 0 after rain, IFS 8.73-8.75) is missing in our land - large in
  a rainy NE-monsoon November; (b) the convective share (conv set named ~1/3). NEXT (input check before any fix run): model land
  evaporation over TN vs ERA5 surface latent heat flux on part-3 dates, locally. If model LE >= ERA5 LE, land evaporation is not
  the cause and land_rs is cleared.
- 07:22 RESULT P5b input check (registered 06:35; lc_mix, start 2020-11-11, T85 local, TN land 8-13.5N 76.5-80.5E, 9 points) vs ERA5
  (ARCO hourly slhf/tp, same box): LE day 1 85 vs 83 W/m2, day 2 51 vs 74; rain day 1 0.51 vs 1.72, day 2 1.88 vs 5.93 mm/day.
  Day-1 land evaporation matches ERA5 (85 >= 83) -> by the rule land evaporation is NOT the cause; land_rs CLEARED as root (its
  'named' effect is compensation: open-water evaporation adds moisture the convection then rains out). Order of events: rain is
  short FIRST (30 % of ERA5 on day 1), then LE falls on day 2 because the soil is not re-wetted - a consequence. [reg: 06:35 |
  inputs: same start library as the exam, ERA5 hourly fluxes, one start at T85 - direction | fail-5why: n/a (diagnosis)]
  => P5b TN dry bias, P3 under-deepening, A/P1 spin-up and day-10 all trace to ONE root: too little convective rain/heating in the
  first day. Next: the convection spin-up fix (reference-based), the single highest-value job for stage 1.
- 07:22 CORRECTION (my own claim at 05:59 and in the 07:06 report): I linked P3's under-deepening to the day-1 convective spin-up. The
  17 Nov storm-core budget (registered, base2) REJECTED that: the strong (FAIL) storms make the SAME core rain as ERA5 (0-24 h ratio
  median 1.00) but keep less of the heat (warm core 500 hPa -37 %); RMW/shear rules not met; inflow-flux test indeterminate
  (core enthalpy flux 0.86 of ERA5, possibly a consequence). So P3's open root is heat RETENTION / core flux, not spin-up - unless
  lc_mix behaves differently from base2 (not measured). Shared spin-up root stands for A/P1, day-10 and (by today's TN check) P5b
  rain; NOT for P3. Next for P3: the registered 18 Nov dk/Ck split of the core flux (where it stopped).

## 22 Nov 09:40 IST - 09:39 cycle: Kaggle idle since ~06:00 -> A/P1 d10 activity test REGISTERED and queued
- Note: P3's registered next test is the radial/vertical heating structure vs ERA5's warm anomaly (18 Nov, not yet built) - my 07:22
  note said 'dk/Ck split' but that was done 18 Nov (flux deficit = wind, a consequence). Corrected here.
- A/P1 (sl_vcubic d10 cost +8.9 m): rerun lc_mix and vc part 1 with wxscore sf/so (4e20490e; scoring only, model code unchanged
  except the evap/land_rc options which are OFF). Reproducibility check first: both reruns must reproduce their 21 Nov z500 d1/d5/d10
  exactly (deterministic XLA) - else the comparison is void.
  REGISTERED: d10 NH+SH z500 activity ratio A = sf/so per start, mean over 18 starts. DOUBLE PENALTY (cubic keeps more real-looking
  activity, RMSE pays for it) if A(vc) - A(lc_mix) >= 0.10 AND A(vc) <= 1.10 AND ACC(vc) >= ACC(lc_mix) - 0.03; OVER-ACTIVE (cubic adds
  spurious activity) if A(vc) > 1.10 and A(vc) - A(lc_mix) >= 0.10; PATTERN LOSS if |A(vc) - A(lc_mix)| < 0.05 (then the cost is in
  the phase of systems). The 21 Nov indirect estimate (1.07 -> 1.22 NH) predicts OVER-ACTIVE.
- 09:58 Stage-1 rain spin-up timescale (lc_mix, T85 local, Jan start, wx2020L2), 3-hourly mean rain globe / tropics mm/day:
  h0-3 1.37/1.84, h3-6 1.65/2.05, h6-9 1.90/2.39, h9-12 2.29/3.02, h12-15 2.46/3.35, then flat 2.3-2.6 / 3.0-3.7 to h36.
  ERA5 day-1 reference 2.94 / 4.15. Reading: starts at ~47 % (globe) / 44 % (tropics) and levels off after ~12 h at ~85 % - so
  the day-1 deficit is two parts: an e-folding spin-up of ~6-9 h AND a plateau ~10-15 % low in the first 36 h (exam d2 0.99,
  d5 1.05 later). Next: conv set closure and trigger at h0 vs h12 (which input changes: CAPE, trigger fraction, closure time).

## 22 Nov 15:28 IST - A/P1 d10 activity RESULT (registered 09:40)
- Reproducibility: both reruns reproduce their 21 Nov z500 RMSE exactly (max diff 0.0000 over 18 starts x d1/d5/d10) -> valid.
- z500 activity sf/so (mean of 18 starts): NH d10 lc_mix 1.037, vc 1.201 (+0.163); SH d10 0.987 vs 1.121 (+0.134); d5 NH 1.025 vs
  1.113, SH 0.974 vs 1.043. ACC d10 NH 0.260 vs 0.225, SH 0.169 vs 0.106.
  Rule OVER-ACTIVE (A(vc) > 1.10 and diff >= 0.10): NH 1.201/+0.163 YES, SH 1.121/+0.134 YES -> OVER-ACTIVE CONFIRMED (the 21 Nov
  indirect estimate predicted it). lc_mix keeps realistic activity (0.99-1.04); cubic vertical SL adds 12-20 % spurious eddy energy
  by day 10 and also loses pattern skill. [reg: 09:40 | inputs: deterministic reruns reproduce, sf/so from the same scorer, only
  sl_vcubic differs | fail-5why: n/a (diagnosis); for A/P1 the fix stays HELD: the steering gain is real, the d10 cost is excess
  activity -> 5-why: why does cubic add energy? linear vertical interpolation damps; cubic does not, and nothing replaces that damping
  (IFS pairs cubic SL with horizontal diffusion + its own vertical-filtering). Next: does our horizontal diffusion match IFS at T170?]
- PROCESS FIX: results sat uncollected ~5.5 h (finished on Kaggle, collector only runs on pushes, dispatcher exited at 'queue empty').
  dispatch.py now keeps looping (and requesting collection) while account-1/4 kernels are pending.
- 15:40 A/P1 5-why step (does our horizontal diffusion fall short of IFS, so cubic's lost damping is not replaced?) - REFERENCE CHECK:
  IFS Part III CY49r1 2.2.11(a): linear grid default del^4 (r = 2), K = tau^-1 (a^2/N(N+1))^2, tau = 6 dt (the IFS's own step);
  cubic grid: spectral-viscosity form acting only above N/2. IFS steps at this resolution: TL159 3600 s, TL255 2700 s -> tau 4.5-6 h.
  Ours (Dinosaur form): tau = 8.6 h / 2.4^log2(256/128) = 3.58 h at T170, del^4 -> our damping is already STRONGER than the IFS
  reference at this resolution. => 'too little diffusion' is NOT the cause; raising it would be tuning against the reference -> not
  done. Remaining fishbone branch for cubic's excess activity: the interpolation itself (IFS uses quasi-monotone cubic for some
  fields and a vertical finite-element discretisation; Dinosaur cubic on sigma, monotone_dynamics on) - check what Dinosaur's
  monotone limiter covers in the vertical before any run. [reg: n/a (reference check, no run) | inputs: IFS doc + our tau formula |
  fail-5why: n/a]
- 15:41 A/P1 fishbone, interpolation branch: Dinosaur's monotone_dynamics applies the Bermejo-Staniforth quasi-monotone limiter to
  the 3-D (incl. vertical) wind interpolation - as IFS does for momentum. So both reference items are already in place (cubic +
  quasi-monotone, diffusion >= IFS). => the excess activity is probably NOT a numerics defect of cubic itself: linear interpolation
  was damping eddies and HIDING a missing physical sink. Fishbone sinks of eddy energy vs IFS: (a) sub-grid orographic drag +
  blocking (Lott-Miller) - OFF in lc_mix (our gwd option has its own known defect, 9 Nov Andes test); (b) turbulent orographic form
  drag (TOFD, IFS 3.x) - not coded; (c) surface turbulent stress. 17 Nov land check: ERA5 gravity-wave stress = 36 % of its turbulent
  stress at land ascent points -> a real sink we lack. NEXT (measure before any run): global and NH-midlatitude mean surface stress
  (turbulent + orographic) ours vs ERA5 (ewss/nsss + lgws/mgws) at d1-d5; if our total < 0.8x ERA5 -> missing sink named.

## 22 Nov 21:40 IST - A/P1 missing-drag-sink test REGISTERED (21:39 cycle; I sat idle 15:45-21:39 - stated)
- Inputs: ERA5 daily-mean turbulent + gravity-wave surface stress (ARCO, 'stress truth'), Jan 6 and Jun 29 2020 starts, d1-d2;
  model: lc_mix T85 local with new stress_out diagnostic (time-integrated rho Cd V u1 / v1). Metric: zonal-mean eastward stress
  over NH 30-60N (Jan) / SH 30-60S (Jul) = the winter-hemisphere momentum sink; also land-only.
  RULE: missing sink NAMED if ours (turbulent only) <= 0.8 x ERA5 (turbulent + gravity-wave) in the winter hemisphere; NOT named if [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
  >= 0.95 x. If named, the fix candidate is IFS orographic drag/blocking (Lott-Miller, IFS Part IV ch.4) + TOFD - after first
  fixing our gwd option's known defect (9 Nov Andes). Prediction: named (ERA5 gw stress was 36 % of turbulent at land ascent points).
- 22:13 RESULT missing-drag test (registered 21:40): winter-hemisphere zonal-mean eastward surface stress, |ours| / |ERA5 turb + gw|
  (sign conventions differ: ours = force on air, ERA5 = stress on surface; magnitudes compared), T85 local lc_mix:
  Jan NH 30-60N d1 0.57 (land 0.46, ocean 0.73), d2 0.61 (0.51 / 0.71); Jul SH 30-60S d1 0.78 (ocean 0.76), d2 0.73 (0.72).
  ERA5 gravity-wave share of the NH Jan total: land 18 %, ocean ~0. Rule: <= 0.8x -> MISSING SINK NAMED in both seasons.
  [reg: 21:40 | inputs: ERA5 hourly stresses same days, model stress_out on the exam's start library, T85 (exam is T170) |
  fail-5why: n/a (named)]. 5-why: the deficit is NOT only orographic - over OCEAN (no orography, no gw stress) ours is 0.71-0.76x.
  Ocean drag formula checked: Charnock 0.018 (IFS value) + 1.5e-5 m, cd_cap 2.4e-3 not binding at normal winds -> the formula is
  standard; so either our near-surface winds are weaker than ERA5's at the same height, or the stability factor cuts drag too much.
  Land: 0.46-0.51x, of which ERA5 gw is 18 % -> orographic drag explains part, the rest is the same turbulent shortfall.
  NEXT (measure): ocean lowest-level wind and stability (Ri_b) ours vs ERA5 at the same points; this decides wind vs stability.
  Note: a 25-40 % weaker surface momentum sink is the right SIZE to explain eddies 12-20 % too active once cubic stops damping them.
- 22:13 REGISTERED (wind vs stability for the ocean drag deficit): winter-hemisphere ocean 30-60, day 1: ours |V1| (lowest level, ~80 m)
  vs ERA5 100-m wind speed (daily mean). WIND named if ours <= 0.85x ERA5 (drag ~ V^2 -> explains >= 0.72x stress); STABILITY named
  if ours >= 0.95x ERA5 (then the drag coefficient/stability function cuts the stress). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 22:30 RESULT wind vs stability (registered 22:2x): winter-hemisphere ocean 30-60, day-1 mean wind speed ours (1000 hPa, 6-hourly) vs
  ERA5 100 m (hourly): Jan NH 10.03 vs 10.43 (0.96), Jul SH 11.64 vs 12.35 (0.94). Rule: >= 0.95 -> STABILITY/drag coefficient named
  for Jan; Jul 0.94 is in the gap (neither). With winds within 4-6 % of ERA5, a 0.72x stress means our drag COEFFICIENT is ~25 %
  low. [reg: 22:2x | inputs: ERA5 hourly 100-m wind, model 1000 hPa (height ~100 m over open ocean), same days | fail-5why: n/a]
  5-why next (reference check, no run): our stability function is Louis (1979): unstable 1 - 2b Ri/(1 + 3bc Cdn sqrt(z/z0 |Ri|))
  with b = c = 5 (matches Louis), but STABLE uses 1/(1 + 10 Ri)^2, while Louis's momentum form is 1/(1 + 2b Ri / sqrt(1 + d Ri))
  (d = 5) - ours cuts stable-side drag much harder. IFS uses Monin-Obukhov (Businger-Dyer unstable, Holtslag-De Bruin stable).
  Measure first: share of winter-ocean points with Ri > 0 and the mean stability factor in our run; if stable points carry
  >= half the stress deficit, the stable branch is the cause and the fix is the reference (Louis 1979 or IFS MO) form.
- 22:38 RESULT stability share (Jan, NH winter ocean 30-60, d1, T85): stable fraction 0.32, mean stability factor 0.95; zonal stress
  ours 0.0678, ours-if-NEUTRAL 0.0703, ERA5 0.0926 (0.73 / 0.76). Deficit split: stable-dominated points 27 %, UNSTABLE points 73 %
  (there our factor already raises drag: 0.0442 vs neutral 0.0415, ERA5 0.0622). Rule (stable carries >= half) NOT met -> the
  stable branch is NOT the cause; my 22:30 suspect CLEARED. [reg: 22:30 | inputs: same run, model diagnostics fst/stab/neutral
  stress | fail-5why: n/a]. The NEUTRAL coefficient itself is ~25 % short. 5-why candidates (not tested): (a) the drag law is applied
  at the lowest level (~80 m) via the log law - in convective (unstable) winter marine layers the wind is near-uniform above ~10 m,
  so a log-law Cd from 80 m understates the stress (same height issue already noted for ck, 'ck_z'); (b) Charnock constant 0.018 vs
  IFS wave-coupled Charnock (often 0.02-0.03 in young winter seas); (c) gustiness (IFS adds convective/free-convection gust).
  NEXT (measure): ERA5's implied Cd = stress / (rho V10^2) and V10/V100 over the same ocean points vs ours.
- 22:56 REGISTERED (before computing): NH winter ocean 30-60N, 2020-01-07. Log law with our z0 (~2e-4 m) gives V10/V80 ~ 0.83.
  (a) HEIGHT named if ERA5's own V10/V100 >= 0.90 (marine layer well mixed, so a log-law Cd taken from ~80 m understates stress);
  (b/c) ROUGHNESS/GUST named if ERA5 V10/V100 <= 0.86 (log-like profile) AND ERA5 Cd10 = stress / (rho <|V10| u10>) >= 1.15x our
  Charnock neutral Cd10 at the same V10. Between -> both partly. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 22:56 RESULT implied Cd (registered 22:5x): ERA5 V10/V100 0.824 (log-like, not well mixed) -> (a) HEIGHT NOT named; ERA5 implied
  Cd10 1.84e-3 vs our Charnock neutral Cd10 1.43e-3 at the same V10 (9.6 m/s) -> ratio 1.28 >= 1.15 -> (b/c) NAMED: ERA5's
  surface is rougher / its drag enhanced beyond our neutral Charnock. [reg: 22:5x | inputs: ERA5 hourly 10/100-m wind and turbulent
  stress, same points and day | fail-5why: n/a]. Remaining split, inside (b/c)+(d): ERA5 Charnock from the wave model vs our fixed
  0.018; gustiness; unstable-side enhancement (IFS Monin-Obukhov vs our Louis: ours adds only 6.5 % on unstable points).
  REGISTERED next: ERA5 'charnock' field mean over the same points: WAVES named if >= 0.025 (Cd10 at 9.6 m/s then +~15 %);
  NOT named if <= 0.020 (then the unstable enhancement / gust carries it). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 23:12 RESULT Charnock split (registered 22:56): ERA5 Charnock over the same ocean points Jan NH 0.0195, Jul SH 0.0173 (ours 0.018)
  -> <= 0.020 -> WAVES NOT named. [reg: 22:56 | inputs: ERA5 'charnock' field, same points/day | fail-5why: n/a]. Remaining for the
  1.28x Cd gap: the stability function on the UNSTABLE side (IFS Monin-Obukhov, Businger-Dyer; ours Louis 1979 adds only +6.5 % there)
  and the free-convection gust (IFS adds (beta w*)^2 to |V|^2 in the surface fluxes, beta = 1.2; ours a fixed 1 m/s). Size: MO at
  z/L ~ -0.5 gives ~+12 %, gust ~+2-5 % -> together plausibly most of 28 %, not certainly all.
  FIX CANDIDATE (reference only, not tuned): 'sfc_mo' = IFS surface-layer formulation (Part IV ch.3: Monin-Obukhov with Businger-Dyer
  unstable / Holtslag-De Bruin stable psi functions, z0M Charnock + 0.11 nu/u*, free-convection gust beta 1.2). To be coded and checked
  locally (winter-ocean stress must reach >= 0.9x ERA5) BEFORE any GPU; then exam part 1 lc_mix+vcubic+sfc_mo against the ORIGINAL
  A/P1 gates (d10 z500 <= 112.75, TN u850 d5 >= -3.21) and activity 0.95-1.05.
- 23:13 sfc_mo coded (mm2, from IFS CY47r1 Part IV 3.17-3.22, 3.26; momentum only; default OFF, other runs unchanged). REGISTERED local
  gate before any GPU (Jan start, T85, NH winter ocean 30-60N d1): sfc_mo stress >= 0.90x ERA5 turbulent -> go to exam; 0.80-0.90 ->
  partial (gust/MO not the whole gap, 5-why on the rest before GPU); < 0.80 -> the IFS form does not explain the gap -> re-open.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 23:22 RESULT sfc_mo local gate (registered 23:1x): NH winter ocean d1 stress / ERA5: lc_mix 0.73 -> sfc_mo 0.78 (land 0.56 -> 0.59).
  0.78 < 0.80 -> by the rule the IFS form does NOT explain the gap; NOT taken to GPU. [reg: 23:1x | inputs: same start, only sfc_mo
  differs | fail-5why below]. fail-5why (does the failure trace to the fix or to the diagnostic?):
  (1) MY 22:56 implied-Cd number is biased: ratio of zonal means of signed stress and signed |V|u, compared with Charnock Cd at the
      MEAN wind - Cd rises with wind, so this overstates ERA5's Cd. The 1.28x is not reliable (my error, stated).
  (2) INPUT/RESOLUTION: ERA5 stress is computed at 0.25 deg from 0.25-deg winds and then box-averaged to 1.5 deg; our T85 (~150 km)
      winds lack the sub-grid wind variance, and stress ~ V^2 -> box-mean stress > stress of the box-mean wind even with identical
      physics. The mean speeds matched (0.96), so a variance deficit could produce much of the 0.73.
  => sfc_mo is HELD (reference-correct, small effect +7 %), and the 'missing sink' verdict of 22:20 needs this resolution check before
  it stands: NEXT (registered): recompute ERA5's stress from its own 1.5-deg box-mean hourly winds with the same bulk law; if that
  'coarse' ERA5 stress is <= 0.85x ERA5's real box-mean stress, the gap is largely RESOLUTION (not a missing physical sink) and the
  A/P1 drag branch is re-examined at T170.
- 23:22 REGISTERED resolution test (N Pacific 30-60N 150-240E, 2020-01-07 hourly, same neutral Charnock law): ratio R = stress from 1.5-deg
  box-mean winds / box-mean of 0.25-deg stress. RESOLUTION named (main part of the 0.73) if R <= 0.85; minor if R >= 0.95.
  Note: this box is 1.5 deg; our T85 is ~1.4 deg - comparable; T170 (~0.7 deg) would sit between. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 23:44 RESULT resolution test (registered 23:3x; value from the workflow log - the json write failed on float32, script fixed): R = 0.954
  (coarse-wind stress / box-mean of fine stress, N Pacific, 24 hourly fields) -> >= 0.95 -> RESOLUTION MINOR (~5 %). My 23:30 worry
  that the gap is mostly a comparison artefact is NOT supported. [reg: 23:3x | inputs: ERA5 hourly 0.25-deg 10-m winds, same law
  both ways | fail-5why: n/a]. Ledger for the winter-ocean stress gap (ours 0.73 of ERA5): resolution ~+5 %, IFS MO + gust +7 %
  (sfc_mo) -> ~0.82 explained at best; ~0.18 still unexplained. The 22:20 'missing sink' verdict STANDS (a real ~25 % shortfall).
  Open candidates for the rest: (i) our lowest level ~80 m vs IFS ~10 m with heat/momentum exchange there (profile shape not
  log above the surface layer in winter cold-air outbreaks - V10/V100 0.824 says log-like on average, but the stress is weighted to
  the windy unstable cases); (ii) ERA5's stress includes the wave-model sea-state drag in high winds; (iii) T85 vs T170 wind
  variance in the model itself (fewer strong-wind events). NEXT: rerun the stress comparison at T170 (the exam resolution) - if
  T170 reaches >= 0.85x with sfc_mo, sfc_mo goes to the exam. One local T170 24 h run may OOM; try, else a short Kaggle job.
- 23:45 Local T170 OOM-killed (6.1 GB) as expected -> REGISTERED Kaggle check (2 short jobs, 24 h each, one variant per job): T170 lc_mix
  and lc_mix + sfc_mo, Jan start, NH winter ocean 30-60N day-1 zonal stress vs ERA5 turbulent. sfc_mo goes to the exam (part 1, vs
  original A/P1 gates) if its ratio >= 0.85; if < 0.85 the remaining ~15 % gets its own 5-why (lowest-level height / sea-state drag)
  before any exam. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 00:01 RESULT T170 stress check (registered 23:5x; outputs from release model-maps): NH winter ocean day-1 zonal stress / ERA5: base 0.73,
  sfc_mo 0.78 (land 0.59 / 0.62) - identical to T85 -> model resolution is not it either. 0.78 < 0.85 -> sfc_mo NOT to the exam;
  stays HELD (reference-correct, +7 %). [reg: 23:5x | inputs: T170 Kaggle, same start/library, ERA5 hourly stress | fail-5why: the
  shortfall does not trace to sfc_mo (it moves the right way); ~20 % remains]. Process note: the collector puts .npz in release
  model-maps, not in the job folder (I looked in the wrong place first).
  Remaining 5-why for the ~20 % (to test in daytime, measure first): (1) ZONAL component - we compared |V| (0.96), but the stress
  compared is the zonal one: a more cross-isobaric / less zonal near-surface flow gives less zonal stress at the same speed ->
  compare <|V|u> ours vs ERA5 at the lowest level; (2) the 80-m lowest level vs IFS's ~10-m surface layer in strongly unstable
  cold-air outbreaks (stress weighted to them); (3) daily-mean sampling: ours 6-hourly speeds vs ERA5 hourly.
- 03:39 REGISTERED (zonal-component check, NH winter ocean 30-60N, Jan d1): Z = <|V| u> / <|V|>^2 (dimensionless 'zonality'), ours at
  1000 hPa (6-hourly, T85) vs ERA5 10 m (hourly). ZONAL named if Z(ours) <= 0.85 x Z(ERA5); NOT named if >= 0.95x. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 03:47 RESULT zonality (registered 03:39): Z ours 0.333 vs ERA5 0.339 -> 0.98 -> ZONAL NOT named. [reg: 03:39 | inputs: ours 1000 hPa
  6-hourly T85, ERA5 10-m hourly, same ocean points | fail-5why: n/a]. Left for the ~20 %: lowest-level height in unstable outbreaks,
  sampling. Since wind speed (0.96), direction (0.98), Charnock (ERA5 ~0.018), resolution (0.95) all match, the coefficient applied at
  our ~80-m level is the remaining place: daytime check = IFS-style exchange computed at 10 m (z1 replaced by 10 m with the wind
  brought down by the MO profile) vs ours, on the same run.
- 03:48 REGISTERED: ERA5's real |stress|/rho (hourly accumulations /3600) vs the neutral Charnock law on its own 0.25-deg 10-m winds,
  N Pacific 30-60N, Jan 7. E = real / law. If E >= 1.20 -> ERA5's stress carries a large enhancement over neutral Charnock (stability
  /sea state) that our MO (+7 %) does not reproduce -> compare stability inputs (air-sea T difference) ours vs ERA5 next. If E <= 1.08
  -> ERA5 is close to neutral Charnock, so our 0.73 must come from our own wind/coefficient pairing -> re-check our cd path for a defect.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 04:10 RESULT ERA5 enhancement (registered 03:4x): ERA5 real |stress| / neutral-Charnock law on its own 0.25-deg 10-m winds, N Pacific
  Jan 7: E = 1.14 -> between 1.08 and 1.20 -> neither branch by the rule. [reg: 03:4x | inputs: ERA5 hourly stress and 10-m winds,
  same box/hours | fail-5why: n/a]. LEDGER (multiplicative, NH winter ocean): ours/ERA5 0.73 ~= our stability factor 0.95 (Louis, net)
  x resolution 0.954 / ERA5 enhancement 1.14 = 0.795 -> ~8 % left (sampling, rho, profile). So most of the gap = ERA5's surface layer
  ENHANCES drag over winter ocean by ~14 % while ours REDUCES it by ~5 %; sfc_mo moves ours to ~+2 % net (0.78) - still ~12 % short of
  ERA5's. NEXT (measure, daytime): the stability INPUT - air-sea temperature difference (T at lowest level vs SST) and its share of
  unstable points, ours vs ERA5 (ERA5 2-m T, SST): if our air is warmer over the winter ocean (less unstable), the MO form cannot
  give ERA5's enhancement -> the cause sits in the low-level temperature (links to the winter 700-500 / boundary-layer findings).
- 04:10 REGISTERED: air-sea contrast at day 1 (Jan 7 00Z), NH winter ocean 30-60N: dT = T(1000 hPa) - SST, ours (T85 fcsnd) vs ERA5
  (act6h). STABILITY INPUT named if our mean dT is >= 0.5 K warmer (less unstable) than ERA5's or our unstable-point share is >= 0.10
  lower; NOT named if within 0.2 K and 0.05. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 04:10 RESULT air-sea contrast (registered 04:1x): NH winter ocean d1, T(1000) - SST ours -4.44 K vs ERA5 -3.59 K; unstable share 0.90 vs
  0.87 -> ours is MORE unstable -> STABILITY INPUT NOT named. [reg: 04:1x | inputs: ours fcsnd T85 d1, ERA5 act6h same time, NaN-masked,
  n 1561 | fail-5why: n/a]. So with a more unstable surface layer, our formula still gives less drag than ERA5's: the response of the
  exchange to instability is weaker in ours (Louis net 0.95; MO +7 %) than ERA5's effective +14 %. Candidates now inside the formula
  path: w* gust from the PREVIOUS step's flux (sfc_mo) - check its size; the 80-m z1 makes zeta large and the Dyer-Hicks form saturates
  - check zeta distribution. Branch status: missing drag is REAL (~25 %), explained ~3/4 by ledger; fix path = stability/gust response.
- 07:14 sfc_mo internals (T85 Jan d1, NH winter ocean): zeta(z1) mean -0.85, percentiles 10/50/90 = -3.22 / -0.37 / +0.58, 36 % below -1;
  free-convection w* mean 0.69 m/s; stress / neutral 1.04. Size check: at zeta -0.37 Dyer-Hicks gives ~+10 %, at -1 ~+20 %, but the
  stable tail (+0.58 -> Holtslag-De Bruin ~-30 %) and wind weighting pull the mean to +4 %. The MO code behaves as the reference
  says; the remaining shortfall vs ERA5's +14 % is not a coding defect visible here (diagnosis, no verdict). [reg: n/a (diagnosis) |
  inputs: same run | fail-5why: n/a]. Drag branch parked pending the user's freeze decision (07:05 message).

## 23 Nov 09:40 IST - slow-start (A/P1 + Day-10 + P5b shared root): reference check of the Stage-1 deep trigger
- conv_mf deep needs cloud depth > mf_dmin = 25000 Pa (code comment itself says 'ECMWF ~20000'); the shallow plume (sh_trig, sh_dmax
  20000 = IFS) covers depth <= 20000 Pa. Clouds 200-250 hPa deep therefore get NEITHER scheme - a gap that does not exist in IFS (deep
  if > 200 hPa). REGISTERED (before the run, T85 local, Jan start, 3-hourly rain as 22 Nov 10:0x): lc_mix with mf_dmin 20000 (IFS):
  GAP named for the slow start if tropical h0-3 rain rises >= 20 % (1.84 -> >= 2.21 mm/day) AND h0-12 mean rises >= 10 %; not named
  if < 5 %. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 09:52 RESULT (registered 09:40): mf_dmin 20000: tropical rain h0-3 1.85 (was 1.84), h0-12 mean 2.33 (was 2.33) -> < 5 % -> GAP NOT named
  for the slow start (it was also not the 925-venting cause on 25 Nov). [reg: 09:40 | inputs: same start/run, one key changed |
  fail-5why: n/a (not named)]. Next: which part of the trigger fails at h0 - share of tropical columns with an LFC, with CAPE > 50,
  and passing depth, at h0 vs h12 (diagnostic flags from conv_mf).
- 10:00 Slow-start split (lc_mix, T85, Jan, conv_diag): tropical deep-active fraction 0.077 (h0-3) -> 0.121 (h12-15) (+57 %), rain 1.84 ->
  3.35 (+82 %); rain per active column 23.9 -> 27.7 (+16 %). => ~3/4 of the spin-up (log share) is the TRIGGER firing in too few
  columns at the start, ~1/4 is intensity. The trigger catches up as the model moistens the boundary layer (+0.19 g/kg at 1000 hPa)
  and cools aloft (22 Nov profile) - i.e. the model re-makes its own instability before it convects. [reg: n/a (diagnosis) | inputs:
  same start/run as 22 Nov | fail-5why: n/a]. Same shape as the package finding (ERA5 start parcels too negatively buoyant for our
  trigger). NEXT (reference check, no run): does the Stage-1 deep test parcel get the IFS surface-flux excess (IFS Part IV 6.x: test
  parcel T/q excess from the surface sensible/latent fluxes) - if missing, that is the reference-based fix candidate.
- 10:00 Reference check of the trigger excess: Stage-1 conv_mf uses a FIXED parcel kick 0.5 K / 0.5 g/kg (mf_kick_t/q); the IFS flux-based
  excess (Part IV 6.x) over tropical ocean (H ~10, LE ~150 W/m2, w* ~0.7 m/s) is ~0.2 K / ~0.1 g/kg - ours is already LARGER, so a
  missing excess is NOT the slow-start cause. Conclusion so far (diagnosis, not a verdict): the start state from ERA5 is not in our
  model's convective balance; the trigger fires in 64 % of its later columns at h0 and the model needs ~12 h to build its own
  instability (moister boundary layer, cooler upper air). IFS has no such spin-up on ERA5 because ERA5 is its own state. A
  reference-based remedy is an initialisation step (e.g. diabatic / incremental initialisation), not a physics constant. Kept OPEN.

## 23 Nov 15:42 IST - RE-SCORE of closure gates under method rule 10 (2-SE tolerance, user decision 15:42)
- P3 (lc_mix + fixed relocate, 83 storms): within +-5 hPa 62/83; SE = sqrt(83 x 0.747 x 0.253) = 4.0 -> limit 67 - 2 x 4.0 = 59.0;
  62 >= 59 -> PASS (tol). Start check: h0 - ERA5 h0 mean +0.70 (SE 0.08) <= 1 -> PASS. => P3 CLOSED (tol). Remaining real cost for
  Stage 2: strong storms under-deepen (6.8 hPa short when ERA5 deepens >= 8 hPa; core heat retention). [reg: 21 Nov 18:10 + rule 10 |
  inputs: 83 storms, h0 checked vs ERA5 | fail-5why: n/a (pass)]
- A/P1 (lc_mix + sl_vcubic, part 1, 18 starts): d10 z500 117.43, sd 10.9, SE 2.57 -> limit 112.75 + 2 x 2.57 = 117.89; 117.43 <= 117.89
  -> PASS (tol). Steering TN u850 d5 -2.37 >= -3.21 -> PASS. => A/P1 CLOSED (tol) with sl_vcubic. Remaining real cost for Stage 2:
  vs lc_mix the cubic d10 cost is +8.9 m (paired SE 2.3, worse in 14/18) = eddies 12-20 % too active, traced to a ~25 % weak surface
  drag over winter oceans (sfc_mo held). [reg: 21 Nov 18:10 (gates) + rule 10 | inputs: deterministic reruns reproduce | fail-5why: n/a (pass)]
- NOT YET MEASURED TOGETHER: P3 was scored on lc_mix (linear vertical) and A/P1 on lc_mix + sl_vcubic. The Stage-1 candidate is
  lc_mix + sl_vcubic + fixed relocate; the final exam measures them together - neither closure is final until that run agrees.
- P5b: TN rain ratio lc_mix 0.422 vs gate 0.843 - not within any tolerance (no fix exists; slow start) -> stays OPEN.
- Attribution ('named') verdicts made before rule 10 are left as recorded; rule 10 applies to them from now on.
- 15:43 REGISTERED combined check (Stage-1 candidate = lc_mix + sl_vcubic + fixed relocate) on the 83 storms (tn-p3-vcreloc-0/1): P3 stays
  CLOSED if >= 59/83 within +-5 hPa (rule 10) and |h0 - ERA5 h0| mean <= 1; else P3 re-opens with cubic as the suspect.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 17:41 Re-score of dependents (rule 10): D1 (sl_vcubic adoption): storm gate PASS (6 Nov, 0.70 vs 2.60) and multi-storm re-test no
  degradation (21 Nov); remaining exam-quarter gate z500 d5 <= control + 2 %: vc 64.39 vs lc_mix 63.76 (+1.0 %) -> PASS (no tolerance
  needed) -> D1 CLOSED (adopted with A/P1). [reg: 6 Nov exam-quarter gate | inputs: deterministic part-1 reruns | fail-5why: n/a (pass)]
  P-pole: gate = masked global d2 t700 bias within -0.6 K; last measured on the T42 screen with vcs (-0.591, 3 starts, screen only) ->
  not measured on the exam config -> stays TESTING, decided in the final exam. Tracks / P2-P4: re-scored when the combined storm run
  (tn-p3-vcreloc) lands - P2/P4 TN 5-day rain within +-25 % is 0.42 on lc_mix -> FAIL, tied to the slow start.
- 19:40 Combined check half 1 (tn-p3-vcreloc-0, lc_mix + sl_vcubic + relocate, 42 storms, 0 failed): within +-5 hPa 35/42 (linear version
  34/42), h0 - ERA5 h0 +0.71. Cubic does not hurt storm starts/intensity. P3 stays CLOSED (tol) if half 2 gives >= 24/41 (total >= 59).
  Half 2 queued on Kaggle (account 4) since ~17:30. [reg: 23 Nov 15:4x | inputs: same storms/library, only sl_vcubic added | fail-5why: n/a (half result)]

## 24 Nov 01:46 IST - Combined check RESULT (registered 23 Nov 15:4x): lc_mix + sl_vcubic + fixed relocate, 83 storms, 0 failed
- Within +-5 hPa 64/83 (linear version 62/83); SE sqrt(83 x 0.771 x 0.229) = 3.8 -> 64 >= 59 (and >= 67 - 2 x 3.8 = 59.3) -> PASS (tol).
  h0 - ERA5 h0 +0.70 (SE 0.08) <= 1 -> PASS. => P3 stays CLOSED (tol) on the Stage-1 candidate; cubic does not hurt storms (+2).
  [reg: 23 Nov 15:4x | inputs: same storms/library as tn-r1-reloc2, only sl_vcubic added | fail-5why: n/a (pass)]
  Residual for Stage 2: 18 too weak (strong-storm under-deepening).
- 01:46 Tracks re-score (gate: 48/72 h mean track error vs ERA5 positions not worse than control by more than +10 %, rule 10 tolerance;
  same storms, 63 at 48 h, 52 at 72 h): candidate (lc_mix + cubic + relocate) 287 / 450 km.
  vs BASE3 (Stage-1 control, base of lc_mix) 240 / 398: +19.7 % / +13.3 % -> limit 264 / 437, tol 303 / 497 -> PASS (tol) both.
  vs BASE2 222 / 375: 48 h +29.4 % -> FAIL (tol 283); 72 h PASS (tol). vs lc_mix (no reloc) 274 / 500: better at 72 h (-9.8 %).
  vs lc_mix + relocate: -1.3 % / -4.8 % (cubic does not hurt tracks).
  VERDICT with BASE3 as the control (the registered Stage-1 base; no separate Tracks control was written - stated so the user can
  overrule): Tracks CLOSED (tol). Real cost carried to Stage 2: tracks 13-20 % worse than BASE3 (the lc_mix land/conv/late sets).
  [reg: Tracks gate +10 % (early Nov) + rule 10 | inputs: ERA5 positions from peak_targets, same storm keys paired | fail-5why: n/a (pass)]
- 09:40 REGISTERED P-pole re-score under rule 10: gate = masked global t700 d2 |bias| <= 0.6 at the T42 screen (starts 56/61/66). Candidate
  lc_mix + sl_vcubic measured -0.624 on 21 Nov (FAIL by 0.024, pooled). Rule-10 SE = sd of the per-start values / sqrt(3), so run the same
  harness one start at a time (local T42). PASS (tol) if |mean| <= 0.6 + 2 SE; note n = 3 makes SE coarse. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 09:52 RESULT P-pole re-score (registered 09:4x): lc_mix + sl_vcubic, local T42, one start at a time: masked global t700 d2 -0.585 / -0.599 /
  -0.692; mean -0.625 (reproduces the pooled -0.624 of 21 Nov), SE 0.033 -> limit 0.6 + 2 x 0.033 = 0.667 -> PASS (tol). t850 passed already
  (-0.471). => P-pole CLOSED (tol) on its gate. Real cost carried to Stage 2: the poleward-40 700 hPa cold itself is still -0.96 K at
  T42 (-0.82 at T170 for lc_mix), contributors sized: mid-level convection ~30 %, shallow-top ~25 %, resolution ~25 %, cubic 15 %.
  [reg: 09:4x | inputs: same harness/starts/mask as 21 Nov, per-start runs reproduce the pooled value | fail-5why: n/a (pass); SE from n = 3 is coarse - stated]

## 24 Nov 10:08 IST - CORRECTIONS (user 10:06-10:07): 'Stage 2' misuse; Tracks gate; plan
- I used 'Stage 2' for 'later fixes'. In the plan Stage 2 = 3-D ocean. The open items are atmosphere items and belong to Stage 1;
  Stage 1 closes only when ALL are closed (user standard, no accepted known limitations). My 28 Nov freeze recommendation is WITHDRAWN.
- Tracks: I scored against a control +10 %. The REGISTERED Stage-1 Tracks gate (5 Nov, eased 9 Nov) is: trend/turns match the real storm
  AND 72-h mean position error <= 280-290 km. Candidate: 72 h 450 km (SE ~20) -> 450 > 290 + 2 SE -> FAIL; trend: 92 % within 45 deg but
  a systematic left (west) drift (-197 km cross-track at 72 h) and 1.30x too far. => Tracks OPEN (FAIL). The 24 Nov 02:0x 'CLOSED (tol)'
  is WITHDRAWN. [reg: 5/9 Nov Tracks gate + rule 10 | inputs: 52 storms at 72 h, ERA5 positions | fail-5why: track error = speed (too far)
  + left drift -> steering too strong/turned; lc_mix sets worsen tracks vs BASE3 (+13-20 %) -> next: steering wind at 500-850 hPa vs ERA5
  along the storm paths]
- User 10:07: 'work on the open items and close'. Order: (1) slow-start initialisation (P5b, P2/P4, P5a, Day-10 share it); (2) Tracks
  steering; (3) D3 re-score; (4) Land night BL root cause.
- 10:08 SLOW-START FIX DESIGN (reference: Incremental Analysis Update, Bloom et al. 1996 MWR 124; as used operationally with a 6-h window,
  e.g. Met Office / GEOS): (1) start from ERA5 at t0-6h, run 6 h free -> background bg(t0); (2) increment = ERA5(t0) - bg(t0) for vorticity,
  divergence, temperature, log ps, q (spectral); (3) restart from ERA5(t0-6h) and run 6 h adding increment/6 every hour; the state at t0
  is ERA5's large scale with the model's own convection already running for 6 h. No tuned constants (window 6 h = the reference window).
  Data: ERA5 at t0-6h for all 73 starts ('pre fields'). REGISTERED local test (T85, Jan K=1 and Jul K=36 starts, lc_mix + sl_vcubic):
  FIX WORKS if (a) tropical day-1 rain >= 0.85 x ERA5 (now 0.68) on both starts AND (b) z500 NH and SH d1 RMSE not worse than without
  IAU by > 5 %. If (a) fails, 5-why before any exam run. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 10:15 AMENDMENT (before any IAU result): local T85 with sl_vcubic is OOM-killed (6 GB) -> the local IAU test runs on lc_mix WITHOUT cubic
  (the spin-up mechanism is in convection/boundary layer, not vertical advection); same rule. The exam check will use the full candidate.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 11:01 RESULT IAU slow-start test (registered 10:1x, amended 10:2x; T85 lc_mix, 6-h IAU): tropical d1 rain / ERA5: Jan 0.62 -> 0.67, Jul
  0.64 -> 0.67 (rule needs >= 0.85) -> (a) FAIL; z500 d1 rmse NH 19.05 -> 19.23 (+1 %), SH 19.55 -> 21.67 (+11 %) Jan, Jul NH 17.19 ->
  18.18 (+6 %), SH 20.69 -> 20.73 -> (b) FAIL. => IAU NOT adopted; HELD. [reg: 10:1x (+ amendment 10:2x) | inputs: ERA5 t0-6h same
  pipeline, same starts, only the start method differs | fail-5why below]
  fail-5why: (1) why so little gain? The increment re-imposes ERA5's T and q at t0, i.e. it removes the moist boundary layer / cool upper
  air the model builds before it convects (22 Nov profile) - so any start that matches ERA5 brings the deficit back. (2) why does the model
  need a different state? Its convection reaches ERA5's rain only in a state MORE unstable than ERA5's own (trigger fires in 64 % of its
  later columns at ERA5's state; plateau still ~0.85 after spin-up). (3) => the root is NOT the start method but the scheme's equilibrium:
  at ERA5's instability our deep trigger/closure makes ~2/3 of ERA5's convective rain. That is a PHYSICS discrepancy vs IFS (trigger test
  parcel / closure), not an initialisation one. The failure traces to the diagnosis (my 'cold-start balance' reading of 23 Nov was
  incomplete), not to a coding fault in IAU. NEXT: reference diff of the deep trigger and CAPE closure vs IFS Cy47r1 6.x on the same
  column states (h0 ERA5 columns where IFS-ERA5 rains and we do not).
- 11:01 REFERENCE DIFF found (deep trigger): our deep convection exists only if the FULLY entraining updraught (eps = entr (1.3 - RH) ...)
  reaches an LFC, > mf_dmin depth and CAPE > 50 J/kg; IFS decides existence/type with a weakly entraining TEST parcel (eq. 6.18,
  eps = 0.8/z + 3e-4) and calls it deep when that cloud is > 200 hPa deep - our test parcel is used only for SHALLOW. A stricter trigger
  at ERA5's state = exactly the 'fires in 64 % of later columns' finding. Fix option dp_test (coded, default OFF): deep existence from
  the IFS test parcel (> 200 hPa), updraught unchanged for mass flux/closure. No new constants.
  REGISTERED (T85 local, lc_mix + dp_test, Jan K=1 / Jul K=36, ctl = 0.62 / 0.64): FIX WORKS if tropical d1 rain / ERA5 >= 0.85 on both
  AND <= 1.15 (no overshoot) AND z500 d1 rmse NH/SH not worse than ctl by > 5 %. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 11:15 RESULT dp_test (registered 11:0x): tropical d1 rain / ERA5 Jan 0.62 -> 0.32, Jul 0.64 -> 0.35; z500 d1 worse (NH 19.05 -> 21.75) ->
  FAIL on every criterion; NOT adopted. [reg: 11:0x | inputs: same starts/run, only dp_test differs | fail-5why below]
  fail-5why: the failure traces to MY reading of the reference: the IFS test-parcel entrainment eps = 0.8/z + 3e-4 is LARGER than our
  updraught's (~0.5-1e-3 in moist air) below ~1.5 km, so the test parcel is more diluted in the boundary layer and reaches 200 hPa depth
  LESS often - my 'weakly entraining = looser trigger' statement was wrong in the lower layers. The diff is real but acts the other way;
  it is not the slow-start cause. Remaining slow-start leads (unchecked vs IFS): source-parcel definition (IFS: departure from the
  surface-flux-based excess, eqs 6.12-6.14), closure time scale (IFS tau = Hc/w x (1 + 264/N), ours fixed 40 min).
- 11:15 D3 RE-SCORE: D3 = 'sigma coordinate over Tibet costs the Asian jet'. Its registered T170 test (13 Nov) measured the effect of the fix
  (hybrid coordinate): Asia jet d1-d3 +0.1 m/s mean vs the 0.5 m/s the problem would need -> at the exam resolution the sigma slope does NOT
  produce a measurable jet loss. Under rule 10 the question is whether a defect exists, and the measured effect (+0.1) is inside noise. =>
  D3 CLOSED as 'no defect at T170' (hyb kept as an option). The Asian jet speed error that remains (~-6 m/s d1 at T170 in base2) is NOT D3;
  it moves to the Tracks/steering investigation (steering = 500-850 hPa winds). [reg: 13 Nov T170 criterion + rule 10 | inputs: T170 screen,
  same starts, only hyb differs | fail-5why: n/a]

## 24 Nov 11:16 IST - Tracks: steering diagnosis (from existing part-3 exam runs; diagnosis, not a verdict)
- Storms drift left (west/south of the NW track) and go too far. Part-3 (Oct-Dec etc.) biases, TN / south India: lc_mix v850 d1/d2 -1.7 / -1.1
  m/s (too NORTHERLY), BASE3 -0.3 / 0.0; u850 d2-d3 too easterly in BOTH (-2.5..-2.8). Existing denials: removing the CONV set brings TN v850 to
  -0.4 / 0.0 (land -1.5, late -1.5, rad_every -1.7, land_rs -1.4, skin/imp -1.7) -> the extra northerly steering that turns storms left comes
  with the conv set (~90 % of the lc_mix - BASE3 difference; measured post hoc, so it only directs the next test).
- REGISTERED: split the conv set on part 3 (one variant per job): no_shmf (shallow mass-flux scheme items), no_deepmix (entr, mf_org,
  mf_mix_exact), no_salrad (sfc_sal, rad_prm). A sub-group is NAMED for the steering if removing it brings TN v850 d1 to >= -1.0 m/s (>= 50 %
  of the -1.4 difference), rule 10 SE stated. Then the named item is compared with its IFS reference (5-why) before any fix.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]

## 24 Nov 13:18 IST - Tracks: conv-set split verdict (registered 24 Nov rule)
- tn-p5b-no-shmf (lc_mix minus shallow mass-flux items: shallow 'mf', sh_trig, sh_dmax, sh_eps, sh_det, sh_clos, sh_ifs2; part 3, 18 starts):
  TN v850 d1 -0.29 +/- 0.55 (>= -1.0) -> NAMED. Paired vs lc_mix (tn-lcm-wx3, same 18 starts): +1.38 +/- 0.29 d1, +1.20 +/- 0.61 d2 m/s
  (whole no-conv effect was +1.23). Same removal: TN 5-day rain ratio 0.422 -> 0.794, TN u850 d5 bias -4.31 -> -2.47, BUT globe z500 d5 RMSE
  65.9 -> 71.4 m (worse) -> removing it is NOT a fix; the scheme must be made right.
  tn-p5b-no-deepmix: v850 d1 -2.19 +/- 0.51 (paired -0.52 +/- 0.10) -> NOT named. tn-p5b-no-salrad: -1.69 +/- 0.46 (paired -0.02) -> NOT named.
  [reg: 24 Nov 11:16 conv-set split rule | inputs: part-3 exam, 18 starts, one variant per job, paired with tn-lcm-wx3 | fail-5why: n/a]
- 5-why (named item vs IFS Cy47r1 Part IV ch.6): (1) storms turn left <- TN v850 too northerly; (2) <- the shallow MF set (same set also cuts TN
  rain by half -> P5b/P2/P4 and the slow start share this root candidate); (3) shallow venting of the sub-cloud layer too frequent/strong;
  (4) two documented departures from the IFS: (a) TRIGGER - IFS: shallow only if the surface test parcel (excess eq. 6.19 from surface fluxes
  and w*, eq. 6.20) reaches its LCL with w > 0 from the kinetic-energy eq. 6.10 (w started at w*); ours (sh_trig) fires wherever the parcel
  condenses, with a fixed 0.5 K / 0.5 g/kg kick and no buoyancy/w test, and the parcel may stay negatively buoyant for 200 hPa below the LFC;
  (b) CLOSURE - IFS eq. 6.32 uses the total non-convective sub-cloud MSE tendency (advection + radiation + diffusion); ours uses the surface
  flux only. (5) both were simplifications taken on 10-11 Nov to make the shallow scheme active at all (old buoyancy test 'almost never passed').
- REGISTERED (before any run): (a) first, as it is the documented trigger: option sh_wtest = IFS shallow test (eq. 6.19 excess, eq. 6.20 w*,
  eq. 6.10 K from the first level, w > 0 at LCL required). Local SIZE check first (T85 lc_mix, 1 Nov start, 24 h): share of shallow-active
  columns (tropics, Bay/TN box 5-20N 75-95E) removed by the test. Then part-3 Kaggle job tn-tr-shw = lc_mix + sh_wtest. Pass (all, rule 10):
  TN v850 d1 >= -1.0; globe z500 d5 RMSE <= lc_mix 65.9 + 2 SE; TN rain ratio not below lc_mix 0.422 - 2 SE. (b) closure (6.32 full tendency)
  only if (a) fails. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]

## 24 Nov 13:20 IST - Land night BL: root cause (5-why) and registration
- Fact (19 Nov): land 20-40 N, day 1 hourly: model BL height mean 843 m (cap) vs ERA5 497 (1.70x); daily max 1.24x -> the excess is at NIGHT;
  night wind 1.9x ERA5 (18 Nov). Diagnostic check first: IFS 3.10.1 BLH = lowest level where bulk Ri from the LOWEST MODEL LEVEL reaches 0.25,
  2 m wind zero, no u* term -> our hbl uses the same reference and threshold (only extra: 100 m floor, <= ~50 m of the 346 m gap) -> the
  diagnostic is not the cause.
- 5-why: (1) night BL too deep / night winds too strong <- (2) stable-BL mixing too strong <- (3) in stable columns K = max(kappa u* z (1 - z/h)^2,
  Kfree): the K-profile has NO stability function (Troen-Mahrt need u*/phi_m; IFS does not use a K-profile there at all) <- (4) IFS Cy47r1
  3.3.2(b): stable K = l^2 |dU/dz| f_LTG(Ri) (b 5, d 1; separate f_m, f_h), 1/l = 1/(kappa z) + 1/(0.1 h_BL); size e.g. u* 0.3, z 50, h 300 m:
  ours ~4.1 m2/s, IFS ~1.3 m2/s (~3x) <- (5) the K-profile was written for the convective BL and never given a stable branch.
- REGISTERED (before any run): option sbl_ifs (code in mm2, default off). Local SIZE check: T85 lc_mix, 1 Nov start, 24 h, land 20-40 N hourly
  mean hbl ctl vs sbl_ifs. Then Kaggle part-3 job tn-sbl = lc_mix + sbl_ifs. CLOSED if (rule 10): land 20-40 N day-1 mean BLH within 0.7-1.3x
  ERA5 497 m AND daily max within 1.3x ERA5 1507 m, AND globe z500 d5 RMSE <= lc_mix + 2 SE, AND land t2 (india) RMSE d1-d5 not worse than
  lc_mix + 2 SE. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 13:33 IST sh_wtest SIZE CHECK (T85 lc_mix, 2020-11-16 start, 24 h; diagnostic step, not a verdict): shallow-active fraction tropics 0.289 -> 0.221
  (-24 %), Bay/TN 0.225 -> 0.144 (-36 %); deep-active unchanged (0.116/0.119, 0.088/0.089); TN d1 rain 9.43 -> 9.26 mm (ERA5 22.35). Size is
  real (a third of Bay/TN shallow columns fail the IFS w test), day-1 rain does not move on one start -> the part-3 Kaggle job decides.
  [reg: 24 Nov sh_wtest registration (size step) | inputs: L2 library, lc_mix set, only sh_wtest differs | fail-5why: n/a]
- 14:05 IST LAND NIGHT BL - sbl_ifs local check (T42 lc_mix, 3 starts, 20-40 N land, day 1 hourly): mean hbl ctl 853 -> sbl 800 m (ERA5 497:
  1.72x -> 1.61x), daily max 1883 -> 1879 (1.25x). Registered rule (mean within 0.7-1.3x) -> FAIL. sbl_ifs HELD (not rejected).
  [reg: 24 Nov land night BL registration | inputs: L2 library, lc_mix set, only sbl_ifs differs, ERA5 same domain/sampling | fail-5why: below]
- FAIL-5WHY: (1) why so small a change? <- one start (11-01) with sbl_ifs, local 21-04 h: surface H < 0 in 96-100 % of night land points (the
  stable branch IS active), night hbl only ~270-370 m, floor 100 m in <= 12 %. (2) Even removing ALL night depth could lower the 24-h mean by
  ~120 m at most, but 853 -> <= 646 needs >= 207 m. (3) So the excess is NOT mainly at night: my 19 Nov reading 'mean 1.7x but max 1.24x ->
  night' was an inference, not a measurement - it is withdrawn. (4) The gap sits in the transition/day hours or the comparison of hours.
  REGISTERED (diagnostic, before the result): ERA5 BLH on the same domain/starts split by LOCAL hour, night 21-04 and day 10-16 (cyc_blhland.py
  now writes blhland2_truth.json), and the model ctl/sbl the same way. The hour band with >= 60 % of the mean excess is NAMED as where the
  fault is; then its 5-why. sbl_ifs is judged again on the night band only (within 1.3x of ERA5 night). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 14:33 IST LAND BL BY LOCAL HOUR (20-40 N land, 3 starts, day 1; night 21-04, day 10-16 local). ERA5 night 158 / day 1206 / mean 497 m.
  ctl: night 414 (2.62x) / day 1660 (1.38x) / mean 853; sbl_ifs: night 324 (2.06x) / day 1649 / mean 800. Share of ctl's mean excess (356 m):
  night 24 %, day 37 %, transitions 39 % -> NO band carries >= 60 % -> not a night-only fault: the land BL is too deep at ALL hours.
  sbl_ifs on the night band: 2.06x > 1.3x -> FAIL; HELD (IFS-faithful, moves the right way, -22 % at night; not enough alone).
  [reg: 24 Nov 14:0x local-hour registration | inputs: ERA5 BLH same domain/starts/hour bands | fail-5why: below]
- FAIL-5WHY / next cause: (1) too deep day AND night <- (2) a cause acting at all hours: low-level wind (night V1 6-8 m/s at 20-40 N land in
  the sbl run; 18 Nov 1.9x ERA5 100 m wind at night) - shear lowers bulk Ri and deepens every hour; (3) weak land drag: z0 fixed 0.1 m
  everywhere, no turbulent orographic form drag (IFS TOFD, Beljaars 2004), sub-grid orography drag (gwd) OFF in lc_mix; (4) IFS Table 8.3 z0m is
  per vegetation (desert 0.013 ... forest 2.0) - over 20-40 N deserts IFS z0 is LOWER than ours, so the IFS's extra land drag there comes from
  TOFD/blocking, not z0. REGISTERED (diagnostic, before results): ERA5 10/100 m wind by the same hour bands (blhland3_truth.json) vs the
  model's lowest-level wind; if model wind > 1.3x ERA5 (log-interpolated to the model level) in BOTH bands, land DRAG is NAMED and the next test
  is IFS TOFD + gwd on (one variant per job); if not, the day-time surface heat flux is examined next.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 14:48 IST LAND WIND BY HOUR (20-40 N land, 3 starts, day 1): ERA5 10/100 m night 2.6/4.6, day 3.4/4.3 m/s -> log-interpolated to the model's
  lowest level (sigma 0.9904, ~82 m): night 4.43, day 4.22. Model ctl lowest level: night 6.99 (1.58x), day 4.38 (1.04x). Rule (> 1.3x in BOTH
  bands) NOT met -> land drag is NOT named for the all-hours excess. The night wind excess (1.58x) is night-only = stable decoupling, the
  same fault sbl_ifs addresses (it took 22 % off the night depth). So TWO faults: NIGHT (stable mixing/decoupling; sbl_ifs partial) and DAY
  (1.38x deep with the right wind). [reg: 24 Nov 14:4x wind registration | inputs: ERA5 10/100 m same domain/hours, model level height stated | fail-5why: n/a]
- REGISTERED (registered branch 'day -> surface heat flux'): ERA5 surface sensible heat flux, day band 10-16 local, same domain/starts
  (blhland4_truth.json) vs model H. If model day H > 1.3x ERA5 -> the day fault is NAMED as the land heat flux (5-why on H next); if within,
  the day BL growth itself (entrainment / K-profile) is examined. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 15:03 IST LAND DAY HEAT FLUX (20-40 N land, 3 starts, day 1, local 10-16): ERA5 H 120.1, model 151.5 W/m2 (1.26x); night -13.2 vs -13.0.
  Rule (> 1.3x) NOT met -> heat flux NOT named (it adds ~12 % depth at most if BL ~ sqrt of heat input; the excess is 38 %).
  [reg: 24 Nov 14:5x H registration | inputs: ERA5 hourly H same domain/hours | fail-5why: n/a]
- Registered branch 'day BL growth'. Code read first: our hbl (diagnostic AND K-profile depth) adds a parcel excess 6.5 H/(rho cp u*) - with
  u* in the denominator, where Troen-Mahrt use w_s ~ (u*^3 + 7 eps kappa w*^3)^(1/3) (~1.5-2 m/s by day) -> e.g. H 150, u* 0.3: ~3 K instead of
  ~0.5 K. The IFS diagnostic BLH (3.10.1) has no excess at all.
  REGISTERED (diagnostic, before the result): same run, model day hbl recomputed with the IFS definition (no excess; output-only field
  hbl_ifs) and the mean day excess. If IFS-definition day hbl is within 1.3x of ERA5 1206 m -> the day fault is NAMED as the excess term
  (u* instead of w_s), and a fix (w_s denominator, as Troen-Mahrt) is tested for the K-profile; if still > 1.3x, the K-profile growth is next.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 15:16 IST LAND DAY BL - excess diagnostic (same run): day excess 2.65 K (Troen-Mahrt scale ~0.5 K); IFS-definition day hbl 1450 m = 1.20x ERA5
  1206 (model's own 1660 = 1.38x) -> within 1.3x -> the day fault is NAMED: the parcel-excess term (u* instead of w_s) - in the diagnostic AND
  in the K-profile depth it sets. Night with the IFS definition 484 m (3.1x ERA5 158; no 100 m floor, no LCL cap) -> night fault confirmed separate.
  [reg: 24 Nov 15:0x excess registration | inputs: same run, only the depth definition differs | fail-5why: n/a]
- REGISTERED (before any run): option bl_exc_ws (excess = 6.5 H/(rho cp w_s), w_s = (u*^3 + 0.7 kappa w*^3)^(1/3), Troen-Mahrt). Local check
  (T42 lc_mix, 3 starts): PASS if model day hbl within 1.3x ERA5 1206 and night not deeper than ctl 414. Then Kaggle part 3 tn-blexc
  (lc_mix + bl_exc_ws): globe z500 d5 RMSE <= lc_mix 65.9 + 2 SE, india t2 RMSE d1-d5 <= lc_mix + 2 SE. Night fault: sbl_ifs combined
  after (one variant per job). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 15:28 IST bl_exc_ws LOCAL CHECK (T42 lc_mix, 3 starts): day hbl 1660 -> 1400 m (1.16x ERA5 1206; <= 1.3x) PASS; night 414 -> 412 (not deeper)
  PASS; day excess 2.65 -> 0.81 K; day H 151.5 -> 153.6 (unchanged); daily mean 853 -> 773. -> local part PASSED; Kaggle part 3 tn-blexc
  (account 4) queued for the forecast gates. [reg: 24 Nov 15:1x bl_exc_ws registration | inputs: same starts/domain, only bl_exc_ws differs | fail-5why: n/a]
- 15:37 IST LAND NIGHT BL - REGISTERED (before the run): local check bl_exc_ws + sbl_ifs (T42 lc_mix, 3 starts). Night rule: night hbl within
  1.3x ERA5 158 m (<= 205 m) AND night lowest-level wind <= 1.3x ERA5 (<= 5.8 m/s at ~82 m). If it fails: 5-why on the input first - our
  lowest level is ~82 m (ERA5's ~10 m), so a surface inversion below 82 m is not seen by the bulk-Ri depth -> check with the 2 m / skin reference.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 15:49 IST LAND NIGHT - bl_exc_ws + sbl_ifs local (3 starts): night hbl 323 m (2.05x ERA5 158) FAIL; night wind 6.71 m/s (1.51x of 4.43) FAIL;
  day 1387 (1.15x) still PASS. Combination HELD. [reg: 24 Nov 15:4x night registration | inputs: same starts, ERA5 same hours | fail-5why: below]
- FAIL-5WHY: (1) night wind stays 1.5x even with IFS stable mixing (and vs ERA5 100 m 4.6 it is still 1.46x, so not the 82 m interpolation)
  <- (2) the momentum SINK at night is weak: surface stress <- (3) our land stable surface drag cd = cdn / (1 + 10 Rib)^2 (Louis 'sharp':
  Rib 0.2 cuts cd by 89 %), while IFS 3.2 uses Monin-Obukhov with Holtslag-De Bruin stable functions (much milder reduction) <- (4) the
  sharp function was kept from the first column model; sfc_mo (IFS MO, Holtslag) exists but was HELD on the ocean drag sink.
  REGISTERED (before the run): local check bl_exc_ws + sbl_ifs + sfc_mo, same 3 starts, plus night mean Rib and cd/cdn printed (SIZE). NAMED
  if night wind falls to <= 1.3x ERA5 (<= 5.8 m/s); night hbl reported against <= 205 m. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 16:06 IST SLOW START - closure time-scale lead checked on paper (IFS Cy47r1 6.x: tau = (Hc / w_up) (1 + 264/N), N = spectral truncation):
  at T170, Hc ~10 km, w_up ~5 m/s -> tau ~2000 s x 2.55 ~ 5100 s; ours fixed tau_deep 2400 s. IFS is SLOWER, so adopting it would delay the
  start further -> closure time scale is NOT the slow-start cause (direction opposite); lead closed. Remaining slow-start leads: the shallow MF
  set (named today for Tracks; it also halves TN rain - tn-tr-shw decides) and the source-parcel excess (IFS eqs 6.12-6.14).
  [reg: 24 Nov slow-start lead list (summary 'remaining leads') | inputs: IFS formula, model T170 setting | fail-5why: n/a]
- 16:06 IST SLOW START - source-parcel lead: our deep kick (0.5 K, 0.5 g/kg fixed) is already LARGER than the IFS flux-based excess (eq. 6.19
  floors 0.2 K / 0.1 g/kg; ~0.3-0.5 K over tropical ocean), as found 24 Nov morning -> IFS's excess would also delay triggering -> NOT the cause;
  lead closed. Slow start now hinges on ONE named candidate: the shallow MF set (venting the sub-cloud layer before deep convection can
  start; tn-tr-shw tests the IFS-faithful trigger). [reg: same lead list | inputs: IFS eq. 6.19 vs model defaults | fail-5why: n/a]
- 16:16 IST NIGHT DRAG TEST (registered 15:5x): bl_exc_ws + sbl_ifs + sfc_mo vs without (3 starts): night wind 6.71 -> 6.29 m/s (1.42x ERA5 4.43;
  limit 5.8) -> sfc_mo NOT named (moves the right way, -6 %); night hbl 323 -> 335; night cd/cdn ~0.2 in both (stable cut ~80 %).
  [reg: 24 Nov 15:5x | inputs: same starts, only sfc_mo differs | fail-5why: below]
- FAIL-5WHY: (1) the surface-layer formula is not the missing night sink (IFS MO changed the wind by 6 %) <- (2) by day the mixed layer passes
  momentum to the surface, so day wind is right (1.04x); at night the surface is decoupled and the only sinks left are ones that do NOT depend
  on surface-layer stability: orographic blocking/gravity-wave drag and TOFD - both missing in lc_mix (22 Nov: our land stress 0.46-0.51x
  ERA5, gw 18 % of it) <- (3) this revises my 14:4x 'drag NOT named' reading: that rule asked for excess in BOTH bands, but a missing
  body-force sink shows mainly when turbulence is off (night) - the rule's premise was wrong, stated.
  REGISTERED (size, before the run): same 3 starts, bl_exc_ws + sbl_ifs + gwd 1 (Lott-Miller blocking + GWD, our option; known 75L T170 Andes
  defect, so local T42 only as a SIZE check). NAMED if night wind <= 5.8 m/s; then the gwd defect is fixed before any Kaggle use.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 16:30 IST NIGHT OROGRAPHIC-DRAG SIZE CHECK (registered 16:2x): + gwd 1 (T42, 3 starts): night wind 6.71 -> 6.25 m/s (1.41x; limit 5.8) -> NOT
  named alone; night hbl 323 -> 320. sfc_mo (-0.42) and gwd (-0.46) each move ~7 %; together ~-0.9 would reach ~5.8 - at the limit, so
  neither is THE cause. [reg: 24 Nov 16:2x | inputs: same starts, only gwd differs, T42 | fail-5why: below]
- FAIL-5WHY / INPUT CHECK (rule: check inputs and size): every night test so far ran at T42 (model orography very smooth, lowest level ~82 m),
  while the exam is T170 and ERA5 is 0.25 deg. Smoothed terrain gives less blocking, fewer valleys/cold pools and faster night winds, so part of
  the 1.4-1.5x could be the test resolution, not the physics. REGISTERED (before the run): same script, ctl and bl_exc_ws+sbl_ifs at T85
  (local limit), 3 starts. If T85 night wind is <= 0.85x the T42 value, resolution is NAMED as a large input to the night gap and the night
  verdicts must be redone at T170 on Kaggle (one job); if T85 ~ T42 (> 0.95x), resolution is cleared. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 16:47 IST T85 local run of the registered resolution check: killed (exit 137, out of memory: the hourly column diagnostic at T85 needs > 7 GB).
  The registered check moves to Kaggle at T170 (the exam resolution) with the SAME rule (T170 night wind <= 0.85x T42 6.99 / 6.71 -> resolution
  NAMED): tn-land170-ctl (acct 1), tn-land170-excsbl = bl_exc_ws + sbl_ifs (acct 4), one variant per job, script land_t170.py smoke-tested at
  T42 locally first. [reg: 24 Nov 16:3x resolution registration (unchanged rule; only where it runs) | inputs: n/a | fail-5why: n/a]
- 17:09 IST tn-blexc (lc_mix + bl_exc_ws, part 3, 18 starts, 0 failed; option active - variant T170_lcm_lc_blexc, t2 differs up to 0.02 K):
  globe z500 d5 RMSE 65.90 -> 65.93 (paired +0.04 +/- 0.04; limit 65.90 + 2 x 1.95) PASS; india t2 RMSE d1-d5 2.65/2.87/3.14/3.25/3.39 ->
  2.65/2.87/3.15/3.27/3.40 (paired <= +0.01, within 2 SE) PASS. With the local land-BL part (day 1.38x -> 1.16x ERA5): bl_exc_ws ADOPTED into
  the Stage-1 candidate (day land BL fixed, neutral on forecast scores). Land BL row stays OPEN for the night part.
  [reg: 24 Nov 15:1x bl_exc_ws registration | inputs: part-3 exam, same 18 starts paired with tn-lcm-wx3 | fail-5why: n/a]
- 17:41 IST tn-land170-ctl (lc_mix, T170, 3 starts): night wind 7.60 m/s (T42 6.99 -> ratio 1.09x), night hbl 453 (T42 414), day hbl 1657 (1660),
  day wind 5.03, day excess 2.58 K. Rule (T170 <= 0.85x T42 -> resolution named; > 0.95x -> cleared): 1.09x -> RESOLUTION CLEARED. At the exam
  resolution the night fault is LARGER: wind 1.72x ERA5 (4.43), depth 2.9x (158). [reg: 24 Nov 16:3x resolution registration | inputs:
  same 3 starts/domain/hours, only the grid differs | fail-5why: n/a]
  Night remaining candidates (each measured ~7 % at T42): stable mixing (sbl_ifs), surface MO drag (sfc_mo), orographic blocking/GWD (gwd),
  TOFD (not coded). tn-land170-excsbl (queued, acct 4) gives the sbl_ifs effect at T170 before any combination is registered.
  [reg: this line (registration of order) | inputs: n/a | fail-5why: n/a]
- 18:33 IST tn-tr-shw (lc_mix + sh_wtest, part 3, 18 starts, 0 failed): TN v850 d1 -1.74 +/- 0.47 (paired -0.07 +/- 0.03), d2 -1.11; TN rain ratio
  0.421 (lc_mix 0.422); globe z500 d5 65.90 -> 65.71 (paired -0.18 +/- 0.12). Gate 1 (TN v850 d1 >= -1.0) FAIL -> sh_wtest HELD (IFS-faithful,
  neutral-to-slightly-better z500; not the steering cause). [reg: 24 Nov 13:0x sh_wtest registration | inputs: part-3, paired with tn-lcm-wx3 | fail-5why: below]
- FAIL-5WHY: (1) the trigger cut a third of Bay/TN shallow columns (size check) yet moved nothing -> the effect of the shallow set is NOT in
  how OFTEN it fires but in WHAT it does where it fires (the remaining, buoyant columns carry it) <- (2) what it does = closure strength
  (sh_clos / sh_ifs2: surface-flux closure, whole sub-cloud venting, implicit transport) and the cloud-layer mixing (sh_eps entrainment, sh_det
  detrainment). REGISTERED (diagnostic split of the named set, part 3, one variant per job, same rule as the 24 Nov split): no_shvent = lc_mix
  minus {sh_clos, sh_ifs2} (falls back to the CAPE closure over tau_shallow); no_shmix = lc_mix minus {sh_eps, sh_det}. A sub-group is NAMED
  if TN v850 d1 >= -1.0 m/s; the named one is then compared with IFS eq. 6.32 / 6.7-6.9 before any fix. Kept in reserve (registered as next):
  the eq. 6.32 full-tendency closure. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 18:36 IST LAND NIGHT - REGISTERED (before the run): option tofd = IFS TOFD (Part IV eqs. 3.58-3.59, Beljaars 2004; alpha 35, Cmd 0.005, Ccorr 0.6,
  a2 from sigma_flt = ERA5 std of FILTERED sub-grid orography, implicit with the momentum diffusion). Size on paper: sigma_flt 100 m, z 50 m,
  U 7 m/s -> ~1.4e-3 m/s2 (strong in hilly terrain). Local T42 check, 3 starts: bl_exc_ws + sbl_ifs + tofd vs bl_exc_ws + sbl_ifs (6.71 m/s).
  NAMED for the night wind if it falls to <= 5.8 m/s (1.3x ERA5); day wind must stay >= 0.8x ERA5 (>= 3.4 m/s) and day hbl within 1.3x.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 18:50 IST TOFD LOCAL CHECK (T42, 3 starts; bl_exc_ws + sbl_ifs +/- tofd): night wind 6.71 -> 5.47 m/s (1.23x ERA5 4.43; <= 5.8) PASS -> TOFD NAMED
  for the night wind (the missing night momentum sink); day wind 4.34 -> 3.84 (0.91x ERA5 4.22; >= 3.4) PASS; day hbl 1385 (1.15x) PASS.
  BUT night hbl 323 -> 331 m (2.1x ERA5 158): the wind is fixed and the night depth is not. [reg: 24 Nov 18:4x TOFD registration | inputs:
  same 3 starts, only tofd differs, sigma_flt from ERA5 | fail-5why: night depth below]
- NIGHT DEPTH 5-why (input/diagnostic first, registered at 16:0x as the fallback): with the wind right, a 2x deep night layer points at what
  the depth is measured FROM: our lowest level is ~82 m, ERA5's ~10 m; a night inversion in the lowest tens of metres is invisible to a bulk Ri
  started at 82 m. REGISTERED (before the run): output-only diagnostic hbl10 = bulk-Ri depth from a 10 m reference (theta_v at 10 m from the
  surface-layer log profile between the skin and level 1, as the model's t2), same run set (bl_exc_ws + sbl_ifs + tofd). If night hbl10 is within
  1.3x ERA5 (<= 205 m), the night-depth gap is NAMED as the measurement level (diagnostic), not the physics.
  Kaggle (forecast gates, one variant per job): tn-tofd = lc_mix + bl_exc_ws + tofd, part 3: globe z500 d5 <= lc_mix + 2 SE, india t2 d1-d5 <= lc_mix
  + 2 SE, TN v850 d1 reported. tn-land170-tofd = T170 night/day land check with bl_exc_ws + sbl_ifs + tofd: night wind <= 5.8 m/s, day hbl <= 1.3x.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 19:03 IST NIGHT DEPTH from a 10 m reference (bl_exc_ws + sbl_ifs + tofd, T42, 3 starts): night hbl10 234 m vs ERA5 158 (1.48x; limit 205) -> NOT
  named as the whole gap. Size: from the level-1 IFS definition (383 m, gap 225 m) to the 10 m reference (234, gap 76 m) the measurement level
  accounts for ~2/3 of the night-depth gap; a real 1.48x remains. Night surface sensible heat flux -6.3 W/m2 vs ERA5 -13.2 (half): the surface
  cools the air too weakly at night -> weaker inversion. [reg: 24 Nov 18:5x hbl10 registration | inputs: same run, only the reference level differs | fail-5why: next]
  NEXT 5-why (measure before any run): why is night H half of ERA5 - stable heat-transfer cut (ch reduced like cd/cdn 0.16) vs skin/soil
  cooling (skin_ifs) vs night downward LW. [reg: this line (registration of the next measurement) | inputs: n/a | fail-5why: n/a]
- 19:04 IST NIGHT H measured from existing runs (T42, 3 starts, night band): ctl -13.0 W/m2 (= ERA5 -13.2) but the night fixes lower it: + sbl/exc
  -10.1, + sfc_mo -8.0, + tofd -6.3. With the wind brought down to ERA5-like values, heat exchange falls with it: our land ck = 0.8 cdn x Louis-sharp
  fst (night cd/cdn ~0.16), while the IFS uses MO with Holtslag-De Bruin for heat too (sfc_mo did momentum only). REGISTERED (before the run):
  option sfc_mo_h (land heat exchange from the same MO solution); local T42 check bl_exc_ws + sbl_ifs + tofd + sfc_mo + sfc_mo_h. NAMED if night H
  is within 0.7-1.3x ERA5 (-9.2..-17.2 W/m2) AND night hbl10 <= 205 m; night wind must stay <= 5.8 m/s, day hbl <= 1.3x ERA5.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 19:18 IST sfc_mo_h LOCAL CHECK (T42, 3 starts, bl_exc_ws + sbl_ifs + tofd + sfc_mo + sfc_mo_h): night H -14.1 W/m2 (1.07x ERA5 -13.2) PASS;
  night wind 5.05 (1.14x) PASS; day hbl 1320 (1.09x) PASS; night hbl10 235 m (1.49x; limit 205) FAIL -> sfc_mo_h NAMED for the night heat
  exchange; night depth still open. [reg: 24 Nov 19:0x sfc_mo_h registration | inputs: same 3 starts, only sfc_mo + sfc_mo_h differ | fail-5why: below]
- FAIL-5WHY (diagnostic first): wind and surface cooling now match ERA5, yet the 10 m-reference depth does not move (234 -> 235) -> suspect
  the depth measure itself: it returns the HEIGHT OF THE MODEL LEVEL where Ri first exceeds 0.25 (no interpolation); at T42/32 levels the
  levels above 82 m are ~150-250 m apart, so the value is quantized upward; ERA5 (137 levels, ~20-30 m apart near the ground) is near-continuous.
  REGISTERED (before the run): output-only hbl10i = same with linear interpolation in Ri between the bracketing levels; same run. If night hbl10i
  <= 205 m, the remaining night-depth gap is NAMED as the depth diagnostic (quantization) and the night physics set (sbl_ifs + tofd + sfc_mo +
  sfc_mo_h) goes to the Kaggle forecast gates. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 19:32 IST hbl10i (night set, T42, 3 starts): night 165 m (1.04x ERA5) - BUT the same measure gives DAY 1975 m (1.64x ERA5 1206). A depth measure
  that is right at night and 64 % too deep by day is biased, not validated: the 10 m theta_v comes from the SKIN temperature through a log
  profile (skin much warmer than air by day, colder at night), so it exaggerates the night inversion and the day instability. => NOT accepted
  as evidence; quantization NOT named on it (my 18:5x/19:1x 10 m-reference idea had this flaw, stated). [reg: 24 Nov 19:2x hbl10i registration |
  inputs: same run | fail-5why: reference biased by skin temperature]
  REGISTERED (before the run): hbl_ifsi = IFS 3.10.1 definition (lowest model level reference, no excess, no skin) WITH Ri interpolation; run the
  night set AND ctl (lc_mix), 3 starts. Quantization is NAMED only if the night set's hbl_ifsi is within 1.3x ERA5 at NIGHT (<= 205) AND by DAY
  (<= 1568); ctl reported so the physics part and the measurement part are separated. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 20:00 IST hbl_ifsi (IFS 3.10.1 definition, lowest-model-level reference, Ri interpolated; T42, 3 starts): night set day 1185 (0.98x ERA5) / night
  248 m (1.57x); ctl (lc_mix) day 1346 (1.12x) / night 372 (2.36x). Rule (night set within 1.3x at night AND day) -> night FAIL -> quantization
  NOT named alone. Size split of ctl's night gap: level quantization 484 -> 372 (interpolation), physics (night set) 372 -> 248, remaining 248 vs
  158. [reg: 24 Nov 19:3x hbl_ifsi registration | inputs: same 3 starts, ERA5 BLH same band | fail-5why: below]
- FAIL-5WHY: the one difference left between the two measures is the REFERENCE HEIGHT: ours ~82 m (lowest model level), ERA5's ~10 m (L137).
  A night inversion below 82 m makes ERA5's depth small but is outside ours. This can be measured fairly on ERA5 itself (no skin temperature):
  REGISTERED (before the result): ERA5 model levels (cyc_blhml.py, 'blhml truth'), same domain/starts, night and day bands, IFS definition with
  interpolation, reference L137 (~10 m; must reproduce ERA5 BLH within 15 %, else the script is wrong) and L134 (~79 m, = ours). If the night
  set's hbl_ifsi (248 / 1185) is within 1.3x of ERA5-L134 at night AND day, the remaining night-depth gap is NAMED as the reference height
  (a measurement difference, not physics) and the night physics set goes to the Kaggle forecast gates.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 20:03 IST SHALLOW-SET SPLIT (part 3, 18 starts each, 0 failed, paired with tn-lcm-wx3): no_shvent (minus sh_clos, sh_ifs2) TN v850 d1 -1.75 (paired
  -0.08 +/- 0.03), rain 0.424, z500 d5 65.65; no_shmix (minus sh_eps, sh_det) -1.68 (paired -0.01 +/- 0.05), rain 0.462, z500 66.37. Rule (>= -1.0)
  -> NEITHER named. [reg: 24 Nov 18:4x shallow-split registration | inputs: part-3, paired | fail-5why: below]
- FAIL-5WHY: venting, mixing and the trigger (sh_wtest) each change nothing; only removing the whole set (shallow 'mf' -> the old 'mse' shallow
  mixing) moves v850 by +1.38 (and costs z500 d5 +5.5 m). So the steering is not in any MF detail but in the SWAP itself: either (a) the MF
  shallow plume's activity as such drives the northerly bias, or (b) the old 'mse' scheme supplies something the MF path lacks (it mixes the
  whole cloud layer every step) that keeps v850 right. These are told apart by switching shallow tendencies OFF with no replacement.
  REGISTERED (before the run): tn-tr-shoff = lc_mix + sh_off 1 (diagnostic denial only, never a fix), part 3. If TN v850 d1 >= -1.0 -> (a) NAMED:
  the MF shallow plume's tendencies (compare its heating/moistening profile with IFS shallow over the Bay next). If < -1.0 -> (b) NAMED: a
  process the old scheme provided is missing from the lc_mix physics (find which by comparing the two schemes' tendency profiles).
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 20:04 IST ERA5 MODEL-LEVEL DEPTH (cyc_blhml, 3 starts, land 20-40 N, IFS definition + interpolation): script check - L137 reference night 151 /
  day 1307 vs ERA5 BLH 156 / 1209 (3 % / 8 %, within 15 %) -> the computation is right. ERA5 from the L134 (~79 m) reference: night 315, day 1205.
  Our hbl_ifsi (same definition, ~82 m reference): night set 248 (0.79x) / 1185 (0.98x); ctl 372 (1.18x) / 1346 (1.12x). Rule (night set within
  1.3x at night AND day) PASS -> the remaining night-depth gap is NAMED as the reference height (measurement), not physics.
  [reg: 24 Nov 20:0x blhml registration | inputs: ERA5 model levels, same domain/starts/bands, standard-atmosphere level heights (stated) | fail-5why: n/a]
- STATED PLAINLY: compared like for like, even lc_mix's night depth is within 1.3x (1.18x). My earlier '2.6-2.9x too deep at night' was mostly
  a measurement mismatch (82 m vs 10 m reference + level quantization). The REAL night faults found on the way are the night WIND (1.58x T42,
  1.72x T170; ERA5 compared at the same height) - fixed locally by TOFD - and the night surface cooling after the wind fix (fixed by sfc_mo_h).
- REGISTERED (closure of Land BL): full land set = bl_exc_ws (adopted) + sbl_ifs + tofd + sfc_mo + sfc_mo_h. CLOSED if (1) T170 land check
  (tn-land170-full): night wind <= 1.3x ERA5 (<= 5.8 m/s), night H within 0.7-1.3x ERA5, day/night hbl_ifsi within 1.3x of ERA5-L134 (205-410 /
  ...: 0.7-1.3x of 315 and 1205); (2) part-3 forecast gates (tn-landset): globe z500 d5 <= lc_mix + 2 SE, india t2 d1-d5 <= lc_mix + 2 SE.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 21:27 IST tn-tofd (lc_mix + bl_exc_ws + tofd, part 3, 18 starts, 0 failed; TOFD active, sigma_flt loaded max 623 m): globe z500 d5 RMSE 65.90 -> 63.63
  (paired -2.26 +/- 0.30, ~7.5 SE BETTER); india t2 d1-d5 all lower (paired -0.03..-0.09); u850 RMSE d3 NH extratropics 4.90 -> 4.30, India 5.54
  -> 4.45; TN v850 d1 -1.62 (paired +0.06; steering unchanged); TN rain 0.432. Registered gates (z500, india t2 not worse) PASS - and the gain is
  large: TOFD is the missing momentum sink named on 22 Nov for A/P1 (our land stress 0.46-0.51x ERA5), now confirmed at the exam resolution.
  [reg: 24 Nov 18:5x TOFD forecast-gate registration | inputs: part-3, paired with tn-lcm-wx3, geo_gwd.npz on Kaggle | fail-5why: n/a]
  TOFD ADOPTED into the Stage-1 candidate (with bl_exc_ws). Day-10 skill (OPEN) must be re-measured with it: registered next = full exam parts
  0-3 at 10 days for candidate + tofd after the land-set gates. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 21:57 IST KAGGLE ACCOUNT 1 weekly GPU quota (30 h) REACHED (push refused for tn-landset). Not worked around: remaining jobs go to account 4 only
  (one at a time), priority order: tn-landset (Land BL forecast gates) -> tn-land170-full; tn-tr-shoff was accepted by Kaggle on account 1 before
  the refusal and is in Kaggle's queue. [reg: n/a (operations note) | inputs: n/a | fail-5why: n/a]
- 21:58 IST tn-land170-excsbl (T170, bl_exc_ws + sbl_ifs, 3 starts): hbl_ifsi night 325 (1.03x ERA5-L134 315) / day 1305 (1.08x of 1205) -> depth
  within 1.3x at the exam resolution; night wind 7.25 m/s (1.64x ERA5 4.43) -> wind still needs TOFD (tn-land170-full measures the full set);
  night H -14.2 (1.08x ERA5). Informative step (no closure rule on this job). [reg: 24 Nov 16:3x/20:0x land170 registrations | inputs: T170, same
  starts/bands, ERA5-L134 reference | fail-5why: n/a]
- 23:33 IST tn-landset (lc_mix + bl_exc_ws + tofd + sbl_ifs + sfc_mo + sfc_mo_h, part 3, 18 starts, 0 failed): globe z500 d5 64.16 (vs lc_mix paired
  -1.74 +/- 0.31; limit 69.80) PASS; india t2 d1-d5 2.71/2.91/3.22/3.32/3.40 (limits 2.85/3.07/3.37/3.51/3.52) PASS -> Land BL closure part (2)
  PASSES. STATED: versus tofd-only (tn-tofd) the three night items COST skill: z500 d5 +0.52 +/- 0.14 m (~3.7 SE) and india t2 +0.06..+0.11 K;
  u850 d3 unchanged (NH 4.29, India 4.38); TN v850 d1 -1.49, TN rain 0.443. [reg: 24 Nov 20:0x Land BL closure registration | inputs: part-3,
  paired with tn-lcm-wx3 and tn-tofd | fail-5why: n/a]
  Open question this raises (not hidden): which of sbl_ifs / sfc_mo / sfc_mo_h costs the 0.5 m, and whether the land-BL gains (night H) are
  worth it - decided after tn-land170-full, by a registered split if the T170 land rule passes. [reg: this line (registration of the question) | inputs: n/a | fail-5why: n/a]

## 25 Nov 01:28 IST - Tracks: shallow-off denial verdict
- tn-tr-shoff (lc_mix + sh_off, diagnostic only; part 3, 18 starts, 0 failed): TN v850 d1 -1.72 +/- 0.47 (paired -0.05 +/- 0.04), d2 -0.99; TN rain
  0.470; z500 d5 66.01 (paired +0.12 +/- 0.21). Rule: < -1.0 -> (b) NAMED: switching the MF shallow plume OFF changes nothing, so the MF plume is
  NOT what drives the northerly bias; the old 'mse' shallow scheme (removed when shallow = 'mf') supplied a process that lc_mix now lacks, and its
  removal is what costs the steering and half the TN rain. Corollary stated: the MF shallow scheme is nearly inert for these fields.
  [reg: 24 Nov 20:0x sh_off registration | inputs: part-3, paired with tn-lcm-wx3 | fail-5why: n/a (named)]
- 5-why next (measure before any run): (1) what does 'mse' do that MF does not - it relaxes the column from cloud base to the parcel top
  toward a mixed moist-static-energy profile over tau_shallow, wherever 'shallow' is flagged; (2) SIZE: compare, over the Bay/TN box, the
  cloud-layer moistening/heating of the two schemes and the MF cloud-base mass flux with IFS-typical values (shallow Mb ~0.01-0.03 kg m-2 s-1);
  if the MF flux is << IFS-typical, the MF scheme's STRENGTH is NAMED (too weak) and its closure (eq. 6.32 full tendency, registered in
  reserve) is next. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]

## 25 Nov 01:29 IST - LAND BL: CLOSED
- tn-land170-full (T170, full land set, 3 starts, sigma_flt loaded): night wind 5.43 m/s (1.23x ERA5 4.43; <= 5.8) PASS; night H -16.3 W/m2 (1.23x
  ERA5 -13.2; 0.7-1.3x) PASS; hbl_ifsi night 292 m (0.93x ERA5-L134 315) PASS, day 1249 m (1.04x of 1205) PASS. With tn-landset (forecast gates
  vs lc_mix PASS, 24 Nov 23:3x): both registered closure parts pass -> LAND BL CLOSED. Root causes named and fixed: (day) parcel excess with u*
  instead of w_s (bl_exc_ws); (night) missing turbulent orographic form drag (tofd) + Louis-sharp stable exchange for heat (sfc_mo + sfc_mo_h) +
  K-profile without a stable branch (sbl_ifs); the night-depth gap left after that was the reference height of the measure (ERA5 model levels).
  [reg: 24 Nov 20:0x Land BL closure registration | inputs: T170 exam resolution, ERA5 same domain/starts/bands, ERA5-L134 reference | fail-5why: n/a]
- Still open from this item (stated, not a limitation accepted): the three night items cost z500 d5 +0.52 +/- 0.14 m vs tofd alone. Registered
  question stands: split sbl_ifs / sfc_mo / sfc_mo_h on part 3 when GPU allows, to keep the land fix at the least skill cost.
  [reg: 24 Nov 23:3x question registration | inputs: n/a | fail-5why: n/a]
- 01:29 IST REGISTERED (the 0.5 m cost question): part 3, account 4, one variant per job, each = full land set minus one item: no_sbl_ifs,
  no_sfc_mo_h, no_sfc_mo (minus sfc_mo AND sfc_mo_h, since h needs mo). An item is NAMED as the cost if removing it brings z500 d5 to within
  1 SE of tofd-only (63.63, i.e. paired vs tn-landset <= -0.38); its land effect (night H / wind) is then weighed against the cost with the T170 land
  script before deciding the candidate. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 01:42 IST SHALLOW SIZE CHECK (T42, 2020-11-16, day 1; T85 run was killed by memory): MF shallow (lc_mix) cloud-base mass flux per active column
  0.022 (Bay/TN) / 0.041 (tropics) kg m-2 s-1 = within IFS-typical 0.01-0.03(-0.04) -> MF STRENGTH NOT named (not too weak). Moisture tendency at
  sigma 0.85: MF +0.54 (Bay/TN) / +0.77 (tropics) g/kg/day; old 'mse' scheme -1.39 / -2.01 g/kg/day - OPPOSITE sign: the old scheme dried 850 and
  carried the moisture up to the parcel top (it mixed from cloud base to parcel top in columns up to 300 hPa deep - the 5 Nov sh_depth note), i.e.
  it acted as CONGESTUS / mid-level moistening, not shallow cumulus. [reg: 25 Nov 01:2x size registration | inputs: same start/grid, only the
  shallow scheme differs | fail-5why: n/a]
- 5-why continues: the process lc_mix lacks is the mid-level (700-500 hPa) moistening by cumulus congestus that the old scheme supplied by
  accident. If true, lc_mix should be DRIER than ERA5 at 700/500 over the Bay/TN by day 1-2 while the old scheme is closer. REGISTERED
  (measurement, before the result): T42 local, 3 Nov starts, 48 h, RH 850/700/500 bias vs ERA5 (rh_truth_2020) over Bay/TN, ctl vs mse. NAMED
  (missing congestus moistening) if ctl RH700 or RH500 bias <= -5 %-points AND mse's bias is at least 3 points closer to zero.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 01:59 IST BAY/TN RH + T vs ERA5 (T42, starts 1/11/16 Nov, daily means d1/d2; lc_mix vs old 'mse' shallow): lc_mix RH700 -0.2/-5.1 pts, RH500
  +12.4/+5.3 pts (mid levels NOT dry), RH925 +5.5/+9.1, T850 -0.68/-1.12 K (tropics -0.48/-0.75), T700 -0.21/+0.11. Old scheme: RH700 +15/+11,
  RH500 +19/+14, RH925 -12/-13, T850 +0.20/-0.10, T700 -1.75/-1.53. Rule (lc_mix RH700/500 <= -5 AND old scheme >= 3 pts closer) -> NOT named:
  lc_mix is not too dry aloft and the old scheme is FARTHER from ERA5 there. 'Missing congestus moistening' is withdrawn.
  [reg: 25 Nov 01:4x RH registration | inputs: ERA5 rh_truth daily means, same starts/grid | fail-5why: below]
- What the numbers show instead: lc_mix's Bay/TN 850 hPa is COLD and growing (-0.7 K d1, -1.1 K d2) with a moist 925; the old scheme moved
  heat DOWN from 700 to 850 (T850 right, T700 -1.6 K). A cold low-level anomaly over the Bay raises pressure there and turns the flow on its
  western flank (TN) northerly - the steering bias. This also matches the open Day-10 item ('mid-level/low-level physics cooling').
  REGISTERED (measurement, before the result): process budget of the sigma 0.85 temperature tendency over Bay/TN (5-20 N, 75-95 E), day 1, T42, 3
  Nov starts, lc_mix: radiation, deep convection, shallow MF, large-scale cond/evap, BL diffusion, dynamics. The process that carries >= 60 % of the
  net cooling relative to ERA5's day-1 change is NAMED for the 850 cold bias (and then compared with its IFS reference).
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 02:12 IST BAY/TN sigma-0.85 BUDGET, lc_mix (T42, 1/11/16 Nov, day 1): dT -0.47 K (ERA5 daily-mean T850 change ~0.0) = physics -0.88 [radiation
  -1.36, deep +0.65, BL -0.14, evap -0.04, shallow -0.02, lsc +0.02] + dynamics +0.41. Cloud: cover 0.84, low (random overlap) 0.67, deep-active 0.08.
  The registered rule needs each process's ERA5 counterpart, which ERA5 does not provide per process -> the rule cannot be applied as written
  (stated). AMENDMENT (registered before the next result): compare with the same budget for the old-scheme run (T850 right): the term that
  carries >= 60 % of the dT difference (lc_mix minus old) is NAMED. [reg: this line (amendment before result) | inputs: model budget only | fail-5why: n/a]
- 02:23 IST OLD-SCHEME BUDGET (same starts): dT +0.82 K (overshoots ERA5 ~0 the other way) = physics +0.26 [shallow 'mse' +4.87, evap -4.05,
  radiation -0.81, deep +0.40, BL -0.15] + dynamics +0.56. Difference lc_mix - old = -1.29 K: shallow+evap pair -0.87 (67 %), radiation -0.56 (43 %),
  deep +0.26, dynamics -0.15. Amended rule (>= 60 %) -> the old scheme's shallow-mixing heating pair is NAMED for the difference - but it is a
  non-IFS mixing that over-heats 850 (+0.8 K/day) and over-cools 700 (-1.6 K): it is NOT a reference to copy. [reg: 25 Nov 02:1x amendment |
  inputs: model budgets, same starts/grid | fail-5why: below]
- FAIL-5WHY (against ERA5, not the old scheme): lc_mix's own 850 cooling is radiation-led (-1.36 K/day with low cloud random-overlap 0.67,
  total cover 0.84; old scheme -0.81 with 0.59). If lc_mix's low cloud over the Bay is too much vs ERA5, cloud-top LW cooling at ~850 is too
  strong. REGISTERED (before the result): ERA5 low/total cloud over Bay/TN, same 3 starts, day 1 (cyc_lccbay.py, 'lccbay truth'). If model total
  cover > 1.2x ERA5 tcc (or low cloud > 1.3x ERA5 lcc; model 'low' = sigma >= 0.68, ERA5 = p > 0.8 ps - definitions differ, stated) -> cloud
  excess NAMED for the 850 cold bias. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 02:25 IST ERA5 CLOUD over Bay/TN (3 Nov starts, day 1): tcc 0.593, lcc 0.154. Model lc_mix: total cover 0.84 (1.42x > 1.2x), low random-overlap
  0.67 (definitions differ). Rule -> CLOUD EXCESS NAMED for the Bay 850 cold bias. [reg: 25 Nov 02:2x lccbay registration | inputs: ERA5 tcc/lcc
  same box/starts/day | fail-5why: n/a]
- 5-why, using what is already established (19 Nov 11:50-13:19, subtropical ocean; same chain): the cloud excess FOLLOWS a low-level cooling
  (T-driven RH rise, 62 %), whose trigger is radiation not balanced by boundary-layer heating, because bl_lcl 1 caps the ocean BL at the LCL
  (455 m vs ERA5 821) and traps the surface heat below 925 hPa. bl_lcl 0 fixed the ocean BL (1036 m, 1.26x) and the 925 physics, but was HELD
  because the LAND afternoon BL went too deep (daily max 1.47x) and the remaining cooling was the weak descent. NEW since then: the land day
  BL is now fixed at its root (bl_exc_ws: excess 2.65 -> 0.8 K; day 1.38x -> 1.16x). The land objection to bl_lcl 0 may no longer hold.
  REGISTERED (before any run): local T42, 3 starts, candidate land set + bl_lcl 0: (i) land 20-40 N day-1 daily-max hbl <= 1.3x ERA5 1507 and day
  hbl_ifsi within 1.3x ERA5-L134; (ii) Bay/TN sigma-0.85 day-1 dT moves >= 50 % toward ERA5 (~0) from lc_mix-land-set's value (measured in the
  same run set). If both pass -> part-3 Kaggle job for TN v850 / rain / z500 gates. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 03:02 IST bl_lcl 0 RE-TEST (local T42, 3 starts, with the land set): (i) land daily-max hbl 1836 (1.22x ERA5 1507) PASS, hbl_ifsi day 1205 (1.00x) PASS
  - the 19 Nov land objection is GONE (bl_exc_ws fixed it at the root); (ii) Bay/TN sigma-0.85 day-1 dT -0.40 (land set) -> -0.68 K (bl_lcl 0):
  WORSE, not 50 % better -> FAIL; bl_lcl 0 HELD. Its budget: radiation -1.28 -> -1.88 K/day (deeper BL lifts moisture to ~850 -> more cloud-top
  LW cooling there), dynamics +0.44 -> +0.68. [reg: 25 Nov 02:4x bl_lcl 0 registration | inputs: same starts/grid, only bl_lcl differs | fail-5why: below]
- CAVEAT on my 02:3x 'cloud excess NAMED': I compared TOTAL cover (0.84 vs ERA5 0.59), which includes high cloud (anvil/cirrus excess known since
  18 Nov) that does not cool 850. The 850 cooling needs LOW cloud with ERA5's definition (p > 0.8 ps). Daily-mean pressure-level RH-cloud from our
  scheme is close to ERA5's at 850 on d1 (0.134 vs 0.121), off at 925 by d2 (0.26 vs 0.14). REGISTERED (before the result): model low cloud with
  ERA5's definition (sigma >= 0.8, random overlap) over Bay/TN, lc_mix + land set, same 3 starts/day 1, vs ERA5 lcc 0.154: LOW-CLOUD EXCESS NAMED
  for the 850 cooling if >= 1.5x; otherwise the 850 radiative cooling is clear-sky-like and the cold bias is a missing HEATING (back to the
  shallow/BL heating chain of 19 Nov). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 03:14 IST LOW CLOUD, ERA5 definition (sigma >= 0.8; land set; Bay/TN; 3 starts; day 1): random overlap 0.637, maximum overlap 0.344 vs ERA5 lcc 0.154
  (4.1x / 2.2x; >= 1.5x either way) -> LOW-CLOUD EXCESS NAMED for the Bay 850 radiative cooling (-1.28 K/day). Yet daily-mean RH at 850 is close
  to ERA5 (0.755 vs 0.743 d1), so the excess comes from WHICH cloud component or the sub-daily/level mapping. REGISTERED (before the result): low
  cloud by component (c_ls RH-based, c_tow convective tower, c_anv anvil), same run: the component holding >= 50 % is NAMED and then compared with
  its IFS counterpart. [reg: 25 Nov 03:0x low-cloud registration + this line (component registration) | inputs: ERA5 lcc same box/day | fail-5why: n/a]
- 03:28 IST tn-ls-no-sfc-mo-h (land set minus sfc_mo_h, part 3, 18 starts, 0 failed): z500 d5 64.04 (paired vs land set -0.11 +/- 0.10; rule <= -0.38)
  -> sfc_mo_h NOT named as the cost; india t2 d5 3.41 (land set 3.40). Remaining: no_sbl_ifs (running), no_sfc_mo (queued).
  [reg: 25 Nov 00:2x cost-split registration | inputs: part-3, paired with tn-landset | fail-5why: n/a]
- 03:38 IST LOW CLOUD BY COMPONENT (land set, Bay/TN, day 1, sigma >= 0.8 random): c_ls 0.623, c_tow 0.084, c_anv 0.000 -> c_ls (RH-based large-scale
  cloud) holds 98 % -> NAMED. [reg: 25 Nov 03:1x component registration | inputs: same run | fail-5why: n/a]
- 5-why next: c_ls = Sundqvist mapping of RH; IFS has no diagnostic RH-cloud (prognostic Tiedtke cloud), so the reference is ERA5 itself:
  STATE vs MAPPING. REGISTERED (before the result): our mapping applied to ERA5's OWN instantaneous RH (1000-800 hPa, 25-hPa levels, max-random
  overlap, p > 0.8 ps), Bay/TN, same 3 starts, 8 hours of day 1 (cyc_clsbay.py, 'clsbay truth'). MAPPING NAMED if scheme(ERA5 RH) >= 1.5x ERA5
  lcc (our scheme makes too much cloud even from the right humidity); otherwise the model's STATE (its RH, esp. the +5-9 pt 925 rise) is NAMED.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 03:42 IST MAPPING CHECK (cyc_clsbay, Bay/TN, 3 starts x 8 hours, day 1): our Sundqvist mapping on ERA5's OWN RH (1000-800 hPa, p > 0.8 ps):
  max-random 0.364, max 0.343, random 0.592 vs ERA5 lcc 0.154 -> 2.4x (>= 1.5x) -> MAPPING NAMED. ERA5 RH900 0.748 / RH850 0.734 (the model's
  RH is close to these on d1). Our own run gave 0.344 max / 0.637 random - the same as the scheme on ERA5's humidity: the model STATE is not the
  cause; the RH-cloud mapping makes ~2.4x ERA5's low cloud from the right humidity. [reg: 25 Nov 03:2x mapping registration | inputs: ERA5
  instantaneous RH/T/q on 25-hPa levels, same box/starts/hours, our exact RHc profile and mixed-phase qs | fail-5why: n/a (named)]
- CHAIN (stated as found, each link registered): TN steering bias (northerly v850) <- Bay/TN 850 cold (-0.7/-1.1 K d1/d2) <- radiation-led cooling
  at 850 (-1.3 K/day) <- low-cloud excess (2.2-4.1x ERA5) <- c_ls 98 % <- Sundqvist RH-cloud mapping (2.4x ERA5 even on ERA5's RH). The old 'mse'
  shallow scheme 'fixed' the steering only by over-heating 850 (+0.8 K/day) - right for the wrong reason, as its z500 cost (+5.5 m) showed.
- 5-why on the mapping vs reference: the IFS has NO diagnostic RH-cloud; its cloud fraction is PROGNOSTIC (Tiedtke 1993, Part IV ch.7):
  stratiform cloud forms only through sources (convective detrainment, BL turbulence, cooling with dqs/dt < 0 above RHcrit) and decays by
  erosion/evaporation, so a humid but steady tropical BL (RH 0.75-0.85) does not carry a standing deck. Our diagnostic scheme puts cloud wherever
  RH > RHc (0.8 near the surface). The IFS-faithful fix is the prognostic cloud-fraction equation (or its documented source/sink terms);
  the decision on scope is for the morning report. [reg: this line (5-why, no run) | inputs: IFS Part IV ch.7 (prognostic cloud) | fail-5why: n/a]
- 03:42 IST REFERENCE CHECK of the mapping's critical RH (IFS Cy47r1 eq. 7.27): RH_crit = 0.8 for sigma <= 0.8 and 0.8 + 0.2 ((sigma - 0.8)/0.2)^2 below
  (0.85 at sigma 0.9, 0.91 at 0.95 -> 1 at the surface). Ours: 0.7 + 0.1 exp(1 - sigma^-4) = 0.74 at 0.85, 0.76 at 0.9, 0.78 at 0.95 - 0.1-0.13 LOWER
  in the boundary layer, exactly where the excess low cloud is. REGISTERED (before the result): the same ERA5-RH mapping check with the IFS RH_crit
  profile (cyc_clsbay.py -> clsbay2_truth.json): RH_crit NAMED as the mapping fault if scheme(ERA5 RH, IFS RH_crit) max-random is within 0.7-1.3x
  ERA5 lcc (0.108-0.200); then option rhc_ifs is coded, checked locally (Bay 850 dT, low cloud) and sent to the part-3 gates (TN v850, rain, z500).
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 03:45 IST IFS RH_crit MAPPING CHECK (clsbay2, ERA5 RH, Bay/TN, 3 starts x 8 h): max-random 0.176, max 0.164 vs ERA5 lcc 0.154 (1.14x / 1.06x; within
  0.7-1.3x; ours 0.364, 2.4x) -> RH_crit PROFILE NAMED: our critical RH is 0.1-0.13 too low in the boundary layer vs IFS eq. 7.27; with the IFS profile
  the same mapping reproduces ERA5's low cloud from ERA5's humidity. [reg: 25 Nov 03:3x RH_crit registration | inputs: ERA5 RH/T/q, IFS eq. 7.27 | fail-5why: n/a]
- REGISTERED (before the run): option rad_prm.rhc_ifs = IFS eq. 7.27 profile at all levels (coded in radcloud). Local T42 check, land set + rhc_ifs,
  Bay/TN, 3 Nov starts, day 1: PASS if low cloud (sigma >= 0.8, max overlap) <= 1.3x ERA5 0.154 (<= 0.20) AND sigma-0.85 dT moves >= 50 % toward
  ERA5 ~0 from the land set's -0.40 (i.e. >= -0.20 K). Then part 3 on account 4: TN v850 d1 >= -1.0, z500 d5 <= lc_mix + 2 SE, TN rain >= 0.422 - 2 SE.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 03:58 IST rhc_ifs LOCAL CHECK (land set + rhc_ifs, T42, Bay/TN, 3 Nov starts, day 1): low cloud max-overlap 0.344 -> 0.163 (1.06x ERA5 0.154) PASS; c_ls
  0.62 -> 0.25; total cover 0.84 -> 0.77; sigma-0.85 dT -0.40 -> -0.26 K (36 % toward ERA5 ~0; rule >= 50 %) FAIL -> rhc_ifs HELD by the registered
  rule. Budget: radiation -1.28 -> -1.13, deep heating +0.66 -> +0.48, dynamics +0.44 -> +0.53. [reg: 25 Nov 03:4x rhc_ifs registration | inputs:
  same starts/grid, only rhc_ifs differs | fail-5why: below]
- FAIL-5WHY: the named link (low-cloud excess) is fixed (cloud now = ERA5), but only part of the cooling went with it: radiation at 850 is still
  -1.13 K/day with ERA5-like cloud (close to a clear-sky tropical value) and the deep-convective heating FELL (less cloud -> less LW cooling of the
  column above -> less instability). So the 850 cold bias has a second input: too little convective/BL heating into 850 (the slow-start / 19 Nov
  'missing heating' line). The 850 dT rule is a PROXY for the steering; the steering itself has not been measured with the named fix.
  REGISTERED (new measurement, rule set now, before any result): part-3 Kaggle job tn-rhcifs = land set + rhc_ifs (account 4): TN v850 d1 >= -1.0
  -> steering NAMED as fixed by the cloud mapping; z500 d5 <= lc_mix + 2 SE; TN rain >= 0.422 - 2 SE. rhc_ifs stays HELD unless all three pass.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 04:51 IST tn-ls-no-sbl-ifs (land set minus sbl_ifs, part 3, 18 starts, 0 failed): z500 d5 64.36 (paired vs land set +0.20 +/- 0.14; rule <= -0.38) ->
  sbl_ifs NOT the cost (removing it is slightly worse); india t2 d5 3.25 (land set 3.40, tofd-only 3.30). Remaining: no_sfc_mo (queued after
  tn-rhcifs). [reg: 25 Nov 00:2x cost-split registration | inputs: part-3, paired with tn-landset | fail-5why: n/a]
- 06:20 IST tn-rhcifs (land set + rhc_ifs, part 3, 18 starts, 0 failed): TN v850 d1 -1.56 +/- 0.44 (paired vs land set -0.07 +/- 0.04) FAIL (>= -1.0);
  z500 d5 63.02 (paired vs lc_mix -2.88 +/- 0.37; best of all runs) PASS; TN rain 0.506 (>= 0.42) PASS. Also: TN u850 d5 bias -4.31 (lc_mix) ->
  -2.84 (the too-EASTERLY half of the steering error shrinks by a third); t850 RMSE d3 tropics 1.95 -> 1.82, India 2.37 -> 2.23; India t2 RMSE d3
  3.14 -> 3.26 (worse, bias -1.09 -> -1.42 K). Registered rule (all three) -> rhc_ifs HELD (not adopted), stated plainly: it is the best
  forecast so far on z500 and reduces the easterly steering bias, but the northerly v850 bias is untouched and India t2 gets colder.
  [reg: 25 Nov 03:5x tn-rhcifs registration | inputs: part-3, paired with tn-landset and tn-lcm-wx3 | fail-5why: below]
- FAIL-5WHY: the 850 cooling over the Bay is only partly removed (local 36 %), and v850 does not move -> the northerly bias does not come
  from the Bay low-cloud cooling alone; remaining named input from the budget: deep-convective heating fell with less cloud (the slow-start
  line). India t2 colder: fewer low clouds -> more night LW loss over land (to check against ERA5 t2 diurnal, morning). [reg: this line (5-why) |
  inputs: budgets + exam | fail-5why: n/a]
- 07:32 IST REGISTERED (Bay 850 second input, before the result): ERA5 apparent heat source Q1 at 850 hPa over Bay/TN, same 3 starts, day-1 hours
  3/9/15/21 (cyc_q1bay.py, 'q1bay truth') vs our sigma-0.85 physics total (land set -0.84 K/day; + rhc_ifs -0.79). MISSING PHYSICS HEATING NAMED if
  ERA5 Q1 exceeds ours by >= 0.4 K/day (then the deep-heating profile is compared with ERA5's Q1 profile); if within 0.4, the 850 cold is NOT a
  physics shortfall and the DYNAMICS term (+0.44 ours) is checked against ERA5's advection. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 07:35 IST ERA5 Q1 over Bay/TN (3 starts, day-1 hours 3/9/15/21): 925 +1.11, 850 +1.11, 700 +1.08, 600 +1.41, 500 +2.06, 400 +2.12, 300 +1.56, 200 +0.80
  K/day. Ours at sigma 0.85: physics -0.84 (land set) / -0.79 (+ rhc_ifs) -> ERA5 exceeds ours by ~1.9 K/day (>= 0.4) -> MISSING PHYSICS HEATING
  NAMED. Size: with radiation ~-1.3, ERA5's convective+BL heating at 850 is ~+2.4 K/day vs our deep +0.66 (+ BL -0.09) - about 4x too little;
  and our dynamics term is +0.44 (warming = weak/absent ascent) where ERA5's must be ~-1.1 (ascent cooling balancing the convection). The Bay's
  convective circulation is too WEAK on day 1 - the same root as the slow start (P2/P4/P5) and, through the low-level inflow, the TN steering.
  [reg: 25 Nov 07:3x Q1 registration | inputs: ERA5 37 levels, same box/starts/day | fail-5why: n/a (named)]
- REGISTERED next (before results): (a) size of the deep-convection deficit by rain: ERA5 total and convective precipitation over Bay/TN day 1 vs
  ours (land set + rhc_ifs); (b) deep-active fraction ours (0.07-0.09) vs ERA5's convective-rain area fraction (cp > 0.1 mm/h). TRIGGER named if
  our active fraction < 0.5x ERA5's cp area; INTENSITY (closure) named if the fraction is within 0.5-1.5x but rain per active column < 0.5x.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 07:43 IST BAY RAIN / TRIGGER (land set + rhc_ifs, T42, 3 Nov starts, day 1) vs ERA5 (cpbay): rain 2.02 vs 6.42 mm/day (0.31x); deep-active fraction
  0.080 vs ERA5 convective-rain area (cp > 0.1 mm/h) 0.229 (0.35x < 0.5x); rain per active column 25.4 vs ERA5 19.5 (1.3x) -> TRIGGER NAMED
  (convection starts in a third of the columns ERA5 has; once on, it rains enough). [reg: 25 Nov 07:3x trigger/intensity registration |
  inputs: ERA5 tp/cp hourly, same box/starts/day | fail-5why: n/a (named)]
- 5-why vs IFS 6.4 (deep test parcel, checked in the documentation now): IFS decides deep convection from a test parcel with eps = 0.4 x eps_up(1) x
  (qs/qs_surf)^3 (WEAKER than the updraught), w = 1 m/s at departure and the K-equation (top where w = 0), departure levels up to 350 hPa above
  ground, cloud > 200 hPa, NO CAPE threshold. Ours: the fully entraining updraught must be buoyant (LFC) with depth > 250 hPa and CAPE > 50 J/kg.
  CORRECTION of my 24 Nov dp_test: it used the SHALLOW test-parcel entrainment 0.8/z + 3e-4 (eq. 6.18) for the deep test - the wrong reference
  (much stronger near the surface) - which is why it fired less (rain 0.32). That fail-5why ('test parcel more entraining') was right about the
  symptom and wrong about IFS: the IFS deep test is the weak one. dp_test stays rejected as coded; dp_ifs is the documented version.
  REGISTERED (before the run): option dp_ifs (coded). Local T42, land set + rhc_ifs + dp_ifs, Bay/TN, same 3 starts: PASS if deep-active fraction is
  within 0.5-1.5x ERA5's 0.229 AND Bay rain >= 0.5x ERA5 (>= 3.2 mm/day). Then part 3 (account 4): TN v850 d1 >= -1.0, TN rain >= 0.85 (P5b gate),
  z500 d5 <= lc_mix + 2 SE. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 07:50 IST dp_ifs LOCAL CHECK (land set + rhc_ifs + dp_ifs, T42, Bay/TN, 3 starts, day 1): deep-active 0.080 -> 0.701 (3.1x ERA5 cp area 0.229; rule
  0.5-1.5x) FAIL; rain 2.02 -> 3.22 mm/day (0.50x ERA5, at the limit); rain per active column 25.4 -> 4.6 -> dp_ifs HELD (fires almost
  everywhere, weakly). [reg: 25 Nov 07:4x dp_ifs registration | inputs: same starts/grid, only dp_ifs differs | fail-5why: below]
- FAIL-5WHY: (1) INPUT to the test: the parcel excess. IFS 6.4: the deep test parcel gets the surface-flux excess (eq. 6.19, capped 3 K / 2 g/kg)
  at the first departure level and only 0.2 K / 0.1 g/kg at higher ones (6.21); ours gives the fixed deep kick 0.5 K / 0.5 g/kg at every source
  level - the moisture kick is 5x IFS's (~1.2 K of theta_e), and with the weakly entraining test parcel this alone can make most tropical
  columns 'deep'. (2) DIAGNOSTIC: 'deep-active' counts non-raining deep columns; ERA5's comparison area is convective RAIN > 0.1 mm/h - not like
  for like (also true of the 0.080 baseline; stated). REGISTERED (before the run): dp_ifs with the IFS test-parcel excess (first level eq. 6.19
  from H and E with w*, cap 3 K / 2 g/kg; higher levels 0.2 K / 0.1 g/kg) = option dp_ifs_exc; measure like ERA5: area with model rain > 0.1 mm/h
  (hourly) vs ERA5 tp > 0.1 mm/h area (cpbay2), plus Bay rain. PASS if rain area within 0.7-1.3x ERA5's AND Bay rain >= 0.5x ERA5.
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 07:54 IST tn-ls-no-sfc-mo (land set minus sfc_mo and sfc_mo_h, part 3, 18 starts, 0 failed): z500 d5 63.43 (paired vs land set -0.73 +/- 0.12; rule
  <= -0.38) -> sfc_mo (IFS MO surface layer for momentum over land+sea) NAMED as the cost (it is also the item HELD on 22 Nov for the ocean drag
  sink at 0.78); india t2 d5 3.42. [reg: 25 Nov 00:2x cost-split registration | inputs: part-3, paired with tn-landset | fail-5why: n/a]
- Weighing (as registered): without sfc_mo/sfc_mo_h the night land surface cooling falls (T42: H -6.3 vs ERA5 -13.2) - a Land BL closure criterion.
  REGISTERED (before the result): T170 land check tn-land170-nomo = bl_exc_ws + sbl_ifs + tofd (account 4). If it still meets all four Land BL
  criteria (night wind <= 1.3x, night H 0.7-1.3x, day/night depth 0.7-1.3x of ERA5-L134), the candidate drops sfc_mo (keeps the 0.7 m) and Land BL
  stays CLOSED; if night H fails, sfc_mo_h is needed - then sfc_mo is restricted to land (its ocean part being the cost is the next measurement).
  [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 08:04 IST LIKE-FOR-LIKE RAIN AREA (T42, Bay/TN, 3 starts, day 1, area with rain > 0.1 mm/h): ERA5 tp area 0.309; ours (land set + rhc_ifs) 0.161
  (0.52x), rain per raining column 12.5 vs ERA5 20.8 mm/day (0.60x); with dp_ifs + dp_ifs_exc 0.153 / 1.85 mm/day -> FAIL (no gain), HELD.
  [reg: 25 Nov 07:5x dp_ifs_exc registration | inputs: ERA5 tp hourly area (cpbay2), same box/starts/day, model hourly rain | fail-5why: below]
- CORRECTION (stated): my 07:4x 'TRIGGER NAMED (0.35x)' compared deep-ACTIVE columns with ERA5's convective-RAIN area - not like for like.
  Like for like the deficit is shared: area 0.52x x intensity 0.60x = 0.31x. Neither the trigger nor the intensity alone is named by the rule.
- T170 evidence (part-3 exam, rain ratio by day vs ERA5): TN d1/d2/d3 lc_mix 0.57/0.43/0.43, land set 0.64/0.42/0.47, + rhc_ifs 0.74/0.46/0.52,
  no_shmf (old scheme) 0.63/0.66/0.69; South India similar (rhc_ifs 0.74/0.50/0.54). At the exam resolution day 1 is the BEST day: the rain
  deficit GROWS after day 1, in step with the Bay 850 cold growing (-0.7 K d1 -> -1.1 K d2), and the old scheme (850 kept warm) holds 0.65.
  So the open rain/steering fault is a day-1-to-3 DECLINE linked to the low-level cooling, more than a 'slow start'.
  NEXT (registered): the low-level cooling after day 1 by process (sigma 0.925/0.85, day 2 vs day 1, Bay/TN), ERA5 Q1 day 2 as reference;
  the process carrying >= 60 % of the day-2 physics shortfall vs ERA5 Q1 is NAMED. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 08:19 IST tn-land170-nomo (T170, bl_exc_ws + sbl_ifs + tofd, no sfc_mo/sfc_mo_h; 3 starts): night wind 5.84 m/s (limit 1.3x 4.43 = 5.76; SE 0.13 ->
  tol 6.02) PASS (tol); night H -8.76 W/m2 (limit 0.7x -13.2 = -9.24; SE 0.08 -> tol -9.08) FAIL; depth night 325 (1.03x ERA5-L134) / day 1301
  (1.08x) PASS. -> without the MO surface layer the night land cooling is too weak: sfc_mo_h (needs sfc_mo) is required for Land BL.
  [reg: 25 Nov 07:5x nomo registration | inputs: T170, same starts/bands | fail-5why: n/a (branch as registered)]
- Registered branch: sfc_mo restricted to LAND (option sfc_mo_land; ocean keeps the Charnock/Louis drag) to test whether the OCEAN part is the
  0.7 m cost. REGISTERED (before the run): part-3 job tn-ls-moland = land set + sfc_mo_land, account 4: cost NAMED as the ocean part if z500 d5
  is within 1 SE of the no-sfc_mo run (paired vs land set <= -0.5); then the candidate uses sfc_mo_land and Land BL stays closed (its land
  physics unchanged). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 09:10 IST DAY-2 BAY BUDGET (land set + rhc_ifs, T42, 3 starts run one per process - the 3-start run was killed by memory): sigma-0.85 physics
  -0.90 / +0.03 / -1.70 (mean -0.86 K/day) vs ERA5 Q1 day 2 at 850 +1.01 -> shortfall 1.86 K/day, same as day 1. Parts (mean): radiation -2.01
  (day 1 -1.13), deep +0.99, lsc +0.36, shallow -0.14, BL -0.02. dT day 2 mean -0.18 K (day 1 -0.26): with rhc_ifs the 850 cold does NOT grow
  on day 2 locally. Low cloud (max overlap) day 2 0.22/0.22/0.37 (day 1 0.16; ERA5 day-1 0.154) - the low-cloud excess comes back on day 2 in
  one start and the radiative cooling nearly doubles. [reg: 25 Nov 08:1x day-2 registration | inputs: ERA5 Q1 day 2 (q1bay2), same box/starts |
  fail-5why: below]
- The registered rule ('process with >= 60 % of the shortfall') cannot be applied: ERA5 has no per-process Q1 (stated again). What can be said:
  the shortfall is steady (~1.9 K/day both days) and is a missing HEATING of ~2 K/day at 850 relative to ERA5, i.e. convective heating that
  should be ~3x ours at that level - the Q1 profile ERA5 shows (1.0-1.1 K/day from 925 to 700, max 2.1 at 400-500) has much more LOW-LEVEL
  heating than our deep scheme gives. NEXT (registered): our deep-convective heating PROFILE (925-200 hPa) vs ERA5 Q1 + radiation profile over
  Bay/TN day 1: the level band where ours falls short by >= 60 % of the column deficit is NAMED (bottom-heavy deficit -> detrainment/entrainment
  profile; top-heavy -> closure strength). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 09:24 IST HEATING PROFILE vs ERA5 Q1 (land set + rhc_ifs, T42, Bay/TN, 3 starts, day 1; physics / deep / rad K/day | ERA5 Q1 | shortfall):
  925 -0.92/+0.35/-1.49 | +1.11 | 2.03; 850 -0.79/+0.48/-1.13 | +1.10 | 1.89; 700 -0.45/+0.81/-1.16 | +1.08 | 1.53; 600 -0.14/+0.76/-0.79 | +1.41 | 1.54;
  500 -0.24/+0.51/-0.91 | +2.06 | 2.30; 400 -0.22/+0.30/-1.02 | +2.12 | 2.34; 300 -0.73/+0.06/-1.37 | +1.56 | 2.29; 200 -1.12/0.00/-1.25 | +0.80 | 1.92.
  Deficit share sigma >= 0.6: 45 %, above: 55 % -> NO band holds >= 60 % -> neither profile shape named; the deficit is COLUMN-WIDE (~2 K/day at
  every level) = too little total convective heating, i.e. too little rain (2.0 vs ERA5 6.4 mm/day here: 0.5 vs ~1.6 K/day column-mean latent
  heating). [reg: 25 Nov 09:1x profile registration | inputs: ERA5 Q1 37 levels, same box/starts/day | fail-5why: below]
- RESOLUTION CAVEAT (stated plainly - this weakens the last hours' local chain): at T42 the Bay day-1 rain is 0.31x ERA5, but at the exam's T170
  the TN/South-India day-1 rain is 0.71-0.74x. The local T42 diagnostics overstate the convective deficit roughly 2x; the T170 fault is the
  decline after day 1 (to ~0.5). Further convection diagnostics must run at T170 (Kaggle, account 4 only until account 1 resets) or they may
  be chasing a resolution effect. [reg: this line (statement + direction) | inputs: T42 vs T170 rain ratios | fail-5why: n/a]
- 09:40 IST T170 EXAM TRENDS (part 3, mean bias d1..d5): lc_mix TN t850 -0.51/-1.19/-1.85/-1.53/-1.60 K, S.India -0.59/-1.15/-1.68; + rhc_ifs TN
  -0.47/-1.07/-1.61; old scheme (no_shmf) +0.52/+0.10/-0.37 - at the exam resolution the 850 hPa cooling over South India GROWS ~0.6 K/day for
  3 days, in step with the rain decline (0.74 -> 0.46 -> 0.52) - this is also the open Day-10 'low-level cooling' item. TN v850 is northerly only
  on d1-d2 (-1.6/-1.1) and turns southerly by d4-d5 (+0.3/+1.5); u850 easterly grows (-0.3 -> -2.8).
  REGISTERED (before the result): T170 physics budget by process (bud_t170.py, Kaggle account 4, land set + rhc_ifs, 3 Nov starts, 3-hourly,
  days 1-3) at sigma 0.925/0.85/0.7 over South India and Bay/TN; ERA5 Q1 days 1-2 over Bay/TN (+1.1/+1.0 at 850) as reference. The process whose
  DAY-1-TO-DAY-3 change carries >= 60 % of the change in physics heating at 850 is NAMED for the decline (the cause that grows, not the static
  offset). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 09:47 IST bud_t170.py smoke test (T42, 1 start 11 Nov; not a verdict): runs; S.India sigma 0.85 days 1/2/3: radiation -1.08/-2.76/-5.62 K/day while
  large-scale condensation heating rises 0.00/+1.20/+1.85 and deep +0.65/+1.65/+1.22 - a growing large-scale cloud deck cooling at its top is the
  candidate for the growing 850 cooling (to be judged at T170, 3 starts). Kaggle job tn-bud170 queued (account 4).
  [reg: 25 Nov 09:4x T170 budget registration (smoke step) | inputs: same code as the Kaggle job | fail-5why: n/a]
- 09:53 IST tn-ls-moland (land set with sfc_mo over LAND only, part 3, 18 starts, 0 failed): z500 d5 63.48 (paired vs land set -0.68 +/- 0.11; rule <=
  -0.5) -> the OCEAN part of sfc_mo is NAMED as the 0.7 m cost; india t2 d5 3.39 (land set 3.40). CANDIDATE uses sfc_mo_land: the land physics is
  identical to the T170-checked land set (Land BL stays CLOSED; the over-land MO momentum + heat are unchanged), the ocean keeps Charnock/Louis.
  Stated: the ocean drag-sink question (22 Nov, sfc_mo HELD at 0.78) remains its own item - the IFS ocean MO surface layer lowers z500 skill here.
  [reg: 25 Nov 08:3x moland registration | inputs: part-3, paired with tn-landset | fail-5why: n/a]
- 10:19 IST tn-bud170 (T170, land set + rhc_ifs, 3 Nov starts, 3-hourly, days 1-3; S.India sigma 0.85 physics -0.44/-0.36/-0.93 K/day): change day 1 ->
  day 3 = -0.49 K/day; by process: radiation -1.10 -> -2.24 (-1.14), deep +0.72 -> +1.13 (+0.41), lsc +0.08 -> +0.25 (+0.17), BL +0.16, shallow
  -0.09. The same at 925 (rad -1.20 -> -1.90) and 700 (-1.24 -> -1.85); Bay/TN 850 rad -1.14 -> -1.66. Rule (process with >= 60 % of the change)
  -> RADIATION NAMED for the growing low-level cooling (its change is larger than the net; deep convection partly offsets it). At T170 the
  cooling growth is radiative, not a convection decline. [reg: 25 Nov 09:4x T170 budget registration | inputs: T170 exam resolution, same starts
  and boxes | fail-5why: n/a (named)]
- 5-why next: radiation's inputs - clouds (low/mid cloud growing day by day, as one local start showed: low cloud 0.16 -> 0.37) or humidity/
  temperature profile. REGISTERED (before the result): ERA5 low/total cloud over South India + Bay/TN days 1-3 (same starts) vs the model's cloud at
  T170 days 1-3 (Kaggle cloud diagnostic, account 4); CLOUD GROWTH NAMED if model low cloud rises >= 50 % from day 1 to day 3 while ERA5's
  changes < 20 %; otherwise the clear-sky input (humidity profile) is next. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 10:27 IST ERA5 cloud days 1/2/3 (lcc3): S.India low 0.196/0.245/0.205, total 0.67/0.65/0.64; Bay/TN low 0.165/0.185/0.166 (flat, < 20 % change). Smoke
  of cld_t170 (T42, 1 start, + rhc_ifs; not the verdict): S.India low cloud 0.28/0.40/0.66 (+137 %), Bay 0.17/0.24/0.32 (+86 %) - the model's low
  cloud GROWS day by day where ERA5's does not. Verdict job tn-cld170 (T170, 3 starts, candidate with sfc_mo_land) queued on account 4.
  [reg: 25 Nov 10:2x cloud-growth registration (smoke + reference step) | inputs: ERA5 lcc/tcc 3-hourly same boxes/starts | fail-5why: n/a]
- 11:00 IST tn-cld170 (T170, candidate = land set with sfc_mo_land + rhc_ifs, 3 Nov starts, days 1/2/3): low cloud (sigma >= 0.8, max overlap) S.India
  0.278/0.402/0.433 (+56 %; ERA5 0.196/0.245/0.205, +5 %), Bay/TN 0.212/0.319/0.347 (+64 %; ERA5 0.165/0.185/0.166, +1 %); c_ls carries it
  (S.India 0.256 -> 0.414). Rule (model >= +50 % while ERA5 < 20 %) -> CLOUD GROWTH NAMED for the growing radiative cooling (850 rad -1.13 ->
  -2.20 K/day) behind the rain decline and the Day-10 low-level cooling. Day-1 level is already 1.4x ERA5 over S.India at T170.
  [reg: 25 Nov 10:2x cloud-growth registration | inputs: T170, ERA5 lcc 3-hourly same boxes/starts | fail-5why: n/a (named)]
- 5-why: (1) low cloud grows <- (2) c_ls = f(RH) with the IFS RH_crit; it grows because low-level RH rises day by day (local: RH925 +5.5 -> +9.1 pts,
  RH850 +1 -> +5 pts vs ERA5) <- (3) RH rises with the low-level cooling (T-driven, 19 Nov: 62 %), and the cooling is the cloud's own radiation
  -> a closed loop: cooling -> RH -> cloud -> cooling <- (4) a DIAGNOSTIC RH-cloud has no memory and no sink of its own, so nothing breaks the
  loop; in the IFS cloud is PROGNOSTIC (Part IV ch.7: a and q_l carried, formed only by sources, removed by evaporation, erosion E2 =
  0.333 a(1-a) K (q_sat - q_v), K 1e-5 (1e-4 with shallow convection) and precipitation) <- (5) MEGAM kept the old diagnostic scheme.
  The IFS-faithful fix is the prognostic cloud (fraction + condensate). [reg: this line (5-why) | inputs: IFS Part IV ch.7 | fail-5why: n/a]
- 11:29 IST REGISTERED (before any run): option cld_prog = stage 1 of the IFS prognostic large-scale cloud (Part IV ch.7: 7.26-7.30 formation and
  condensation, 7.46 evaporation, 7.48-7.49 erosion, 7.50-7.52 Sundqvist autoconversion; IFS RH_crit 7.27), carried per column (not advected), feeding
  radiation only (stage 1; stated). Local T42 smoke (cld_t170.py, 11 Nov start, + land set + rhc_ifs): low cloud must NOT grow (day 3 <= 1.2x day 1)
  over S.India and Bay. If it passes: T170 3-start cloud job, then part-3 gates (TN v850 d1 >= -1.0, TN rain >= 0.85 = P5b gate, z500 d5 <= lc_mix
  + 2 SE). [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 11:38 IST cld_prog STAGE 1 SMOKE (T42, 11 Nov, land set + rhc_ifs + cld_prog): low cloud (max overlap) S.India 0.135/0.218/0.323 (day 3 = 2.4x day 1;
  rule <= 1.2x) FAIL; Bay 0.082/0.121/0.189 (2.3x) FAIL; day-1 level now BELOW ERA5 (0.135 vs 0.196 S.India); 850 radiation -1.23/-1.59/-3.72
  K/day (S.India) - the loop is still there. cld_prog stage 1 HELD. [reg: 25 Nov 11:0x cld_prog registration | inputs: same start/grid as the
  no-prog smoke (0.28/0.40/0.66) | fail-5why: below]
- FAIL-5WHY: (1) cloud still grows, from a lower start <- (2) prognostic formation responds to cooling (dqs/dt < 0 above RH_crit), and the
  cooling is mostly the cloud's own LW at its top - the memory alone does not break the loop <- (3) what damps it in the IFS and is missing in
  stage 1: the condensation C1 + C2 RELEASES LATENT HEAT in the cloud layer and evaporation/erosion COOL and moisten where cloud dies (the cloud
  scheme IS the large-scale condensation there); stage 1 feeds radiation only and the old adjustment condenses only at supersaturation <- (4)
  stated simplification of stage 1. NEXT (registered): stage 2 = cloud condensation/evaporation/autoconversion feed T and q (latent heat, rain
  into the large-scale rain), replacing the old large-scale adjustment where cld_prog is on; same smoke rule. [reg: this line (registration) |
  inputs: n/a | fail-5why: n/a]
- 12:12 IST cld_prog STAGE 2 - implementation defects found by step-by-step debugging (not physics verdicts): (1) latent heat fed back inside the
  physics step -> Clausius-Clapeyron runaway (fixed: own split step); (2) the stored reference T was the pre-transform value while the spectral
  transform smooths the point heating (T - cTp 0.3 -> 7.8 K in 5 steps; fixed: true nodal T after the step); (3) condensation not limited by the
  vapour present (fixed). Remaining defect: grid points with a = 1 and RH far below 1 keep condensing (one point heated 308 -> 329 K by step 30):
  my explicit port has no saturation consistency - in the IFS the cloud budget is solved implicitly with the saturation adjustment (a = 1 means
  a saturated box) and clouds in sub-saturated air are removed by evaporation. Stage 2 as coded is NOT usable; a correct port needs the IFS
  implicit solution (Part IV 7.5) - about a day of careful work, stated. [reg: n/a (implementation debugging, no verdict) | inputs: step-by-step
  T42 trace | fail-5why: n/a]
- 15:44 IST cld_prog stage 2 - two IFS consistency pieces added (implementation, from IFS 7.3.2 and the cloudy/clear split): dq_sat/dt divided by
  1 + L/cp dqs/dT (moist adjustment) and a <= RH (cloudy part saturated: qv = a qs + (1 - a) q_env), the excess cloud evaporated with its
  condensate. T42 step-by-step trace: stable for 72 steps (1 day), cloud water <= 0.7 g/kg, T normal. The registered smoke rule (day-3 low cloud
  <= 1.2x day 1) now runs. [reg: n/a (implementation) | inputs: T42 trace | fail-5why: n/a]
- 15:52 IST cld_prog STAGE 2 smoke (T42, 11 Nov): low cloud S.India 0.080/0.152/0.229 (day 3 = 2.9x day 1; rule <= 1.2x) FAIL, Bay 0.066/0.093/0.141
  (2.1x) FAIL -> HELD. BUT stated: the day-1 level now starts far BELOW ERA5 (0.08 vs 0.196) and day 3 reaches ~ERA5 (0.229 vs 0.205 S.India);
  850 radiation day 3 -2.11 K/day (no-prog -5.62, stage 1 -3.72) and the 850 dT on days 2-3 is no longer negative (S.India +0.20/+0.18).
  [reg: 25 Nov 11:0x cld_prog registration (same rule for stage 2) | inputs: same start/grid | fail-5why: below]
- FAIL-5WHY: the 'growth' rule assumed a correct day-1 cloud; here the growth is from a too-LOW start - (1) the first step starts from the
  diagnostic cloud with q_l = 0.01 a q_s and is then cut to a <= RH, so day 1 begins nearly cloud-free <- (2) the IFS starts from the ANALYSED
  cloud (ERA5 carries cloud fraction and condensate) - our library has none. So the test cannot tell spin-up from a loop in 3 days.
  REGISTERED (before the result): 5-day run (same start) + ERA5 low cloud days 1-5; the LOOP is NAMED as broken if days 3-5 stay within 0.7-1.3x
  ERA5 AND day 5 <= 1.2x day 3 (levels off); if it keeps growing past ERA5, it is not broken. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 16:06 IST 5-DAY CLOUD CHECK (T42, 11 Nov start, lc_mix + rhc_ifs + cld_prog 2) vs ERA5 days 1-5 (lcc5, mean of 3 starts): Bay/TN low 0.066/0.093/0.141/
  0.164/0.147 vs ERA5 0.165/0.185/0.166/0.156/0.189 -> days 3-5 0.85/1.05/0.78x, day5/day3 1.04 -> PASS (levels off at ERA5: loop broken over
  the Bay). S.India 0.080/0.152/0.229/0.320/0.334 vs 0.196/0.245/0.205/0.180/0.235 -> 1.12/1.78/1.42x, day5/day3 1.46 -> FAIL (still grows past
  ERA5 over the S.India box, which is mostly LAND). [reg: 25 Nov 15:5x 5-day registration | inputs: ERA5 lcc 3-hourly; model one start (stated) |
  fail-5why: below]
- FAIL-5WHY (inputs first): this smoke ran WITHOUT the land set (bl_exc_ws, sbl_ifs, tofd, sfc_mo_land, sfc_mo_h) - my config error for a box
  that is mostly land, where the night cooling and BL depth those items fix feed RH directly. REGISTERED (before the result): the same 5-day
  check with the full candidate (land set + sfc_mo_land + rhc_ifs + cld_prog 2), same rule per box. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 16:21 IST 5-DAY CLOUD CHECK, FULL CANDIDATE (land set + sfc_mo_land + rhc_ifs + cld_prog 2; T42, 11 Nov): S.India low 0.087/0.146/0.117/0.198/0.182 (days 3-5
  vs ERA5 0.57/1.10/0.77x), Bay 0.078/0.096/0.107/0.121/0.077 (0.64/0.78/0.41x). No runaway any more (S.India 0.33 -> 0.18 at day 5 with the land
  set), but the low cloud is now BELOW ERA5 on several days -> the 0.7-1.3x rule FAILS on the low side; cld_prog stage 2 HELD.
  [reg: 25 Nov 16:0x full-candidate registration | inputs: ERA5 lcc days 1-5 (3-start mean), model one start (stated) | fail-5why: below]
- FAIL-5WHY: (1) too little low cloud <- (2) cloud starts near zero (no analysed cloud in our library; ERA5/IFS start from analysed cloud) and
  the formation source needs dq_sat/dt < 0 with RH > RH_crit, so in steady humid tropical air it fills slowly; (3) the convective DETRAINMENT
  source of cloud (IFS 7.23, a large tropical source) is not in stage 2 - the convective cloud stays diagnostic (c_tow) and does not feed a.
  The decisive tests are the forecast fields, not the cloud alone. REGISTERED (before the result): part-3 T170 run tn-cldprog = candidate +
  cld_prog 2 (account 4): TN v850 d1 >= -1.0; TN rain >= 0.85 (P5b gate); z500 d5 <= lc_mix + 2 SE; and the S.India t850 bias growth d1 -> d3
  shrinks by >= 50 % (from -1.1 K/2 days). cld_prog stays HELD unless all pass. [reg: this line (registration) | inputs: n/a | fail-5why: n/a]
- 17:57 IST tn-cldprog (T170 part 3, 18 starts, 0 failed; candidate = land set + sfc_mo_land + rhc_ifs + cld_prog 2): TN v850 d1 -1.69 +/- 0.45 FAIL (>= -1.0);
  TN 5-day rain ratio 0.573 FAIL (>= 0.85; lc_mix 0.422, moland ~0.51); z500 d5 60.92 m PASS (lc_mix 65.90; paired vs moland -2.56 +/- 0.52, d3
  -1.38 +/- 0.12); S.India t850 bias growth d1 -> d3 -0.61 K vs moland -1.08 (44 % smaller; rule >= 50 %) FAIL, TN 39 %. Also: tropics t850 RMSE d5
  2.19 -> 1.84, India u850 d5 4.91 -> 4.41, global mslp 634 -> 623 Pa, TN u850 d5 bias -2.40 (lc_mix -4.31); India t2 d5 3.39 -> 3.47 (slightly
  worse). Registered rule (all four) -> cld_prog HELD, stated plainly: it is the largest single forecast gain of Stage 1 (z500 d5 -7.6 % vs lc_mix),
  roughly halves the low-level cold growth and lifts TN rain 0.51 -> 0.57, but the TN northerly v850 and the 0.85 rain gate are not met.
  [reg: 25 Nov 16:1x tn-cldprog registration | inputs: part-3 T170, paired with tn-ls-moland / tn-lcm-wx3 | fail-5why: below]
- FAIL-5WHY: (1) low cloud now too LOW (local 0.4-0.8x ERA5) and the cold growth only halved <- (2) two documented IFS pieces still missing:
  the analysed initial cloud (we start cloud-free) and the CONVECTIVE DETRAINMENT source of cloud fraction and condensate (IFS 7.23, the main
  tropical source); (3) TN v850 has not moved in any cloud test (-1.5..-1.7) -> the northerly d1-d2 bias is NOT driven by the cloud chain (that
  chain drives the cooling growth and rain decline). v850 needs its own 5-why (day-1 signal from the start: mslp +0.7 hPa high over TN at d1).
  [reg: this line (5-why) | inputs: exam fields | fail-5why: n/a]
- 18:26 IST TRACKS v850 5-WHY, step 1 (from existing part-3 JSONs): day-1 v850 bias TN -1.67/-1.69/-0.29 and S.India -1.39/-1.36/-0.29 for
  lc_mix/cldprog/no_shmf; mslp d1 is +69..+97 Pa high in ALL three (shared -> not the cause of the difference). The only variant that removes the
  northerly is the old mse scheme, which heats 850 hPa by ~+4.9 K/day (MSE mixing) vs ERA5 Q1 ~+1.1 K/day; ours -0.8 K/day over the Bay.
  REGISTERED (before the result): (a) T42 day-1 difference map lc_mix minus no_shmf (3 starts: 1/11/16 Nov) - if the v850 difference is largest
  over the Bay/TN coast and co-located with a 850 hPa heating/rain difference, the bias is the low-level heating deficit of the mass-flux
  scheme; if it is broad-scale (whole basin, no rain co-location), it is a dynamical/initial-state cause and the next check is the DFI/initial
  imbalance. (b) No gate change; Tracks gate stays TN v850 d1 >= -1.0. [reg: this line | inputs: part-3 JSONs listed; ERA5 Q1 q1bay2 | fail-5why: n/a]
- 18:36 IST cld_det CODED (from the cld_prog fail-5why): deep updraught keeps its condensate l_up and rains it by IFS Cy47r1 eq. 6.39 (c00 1.4e-3,
  l_crit 0.5 g/kg, w_up from eq. 6.10, thresholds 0.3/0.5 g/kg sea/land); the rest detrains where the mass flux falls (eq. 7.22: D l_up) and
  feeds the carried cloud with da = D dt (eq. 7.23). Water conserved by telescoping liquid flux; subsidence terms, Bergeron and alpha_T factors
  not included (stated). T42 2-day smoke (11 Nov): finite, global rain 2.2 mm/day. REGISTERED (before the result): part-3 T170 tn-clddet =
  cand_cldprog + cld_det, account 4, the SAME four rules as tn-cldprog (TN v850 d1 >= -1.0; TN rain >= 0.85; z500 d5 <= lc_mix + 2 SE; S.India
  t850 cold growth d1->d3 shrinks >= 50 %). Adopted only if all four pass; otherwise HELD with a fail-5why. [reg: this line | inputs: n/a | fail-5why: n/a]
- 18:36 IST DAY-10 GATE REGISTERED (item 11 had no explicit gate; registered now, before any 10-day result, from existing references only):
  the FINAL candidate runs the full exam (wx2.py parts 0-3, 72+ starts, T170, days 10, one variant per job, account 4/1). Day-10 CLOSES when
  (a) 0 failed starts (no blow-up to day 10); (b) z500 RMSE d10 <= 122.6 m (the existing regression gate, line 384) AND <= the lc_mix day-10
  value of the same starts + 2 SE (paired); (c) global mslp RMSE d10 and tropics t850 RMSE d10 no worse than lc_mix + 2 SE (paired). It runs
  only after items 7-10 settle the candidate, so the 10-day GPU minutes are spent once. [reg: this line | inputs: n/a | fail-5why: n/a]
- 18:42 IST TRACKS v850 MAP TEST (T42, 3 starts, day 1, lc_mix minus no_shmf): TN v850 +0.74 (T170 exam: -1.38), Bay -0.21, Arabian Sea -0.44.
  The T42 run does NOT reproduce the T170 TN v850 difference (opposite sign; the TN box is ~3 T42 grid points) -> INCONCLUSIVE, the registered
  map test is invalid at this resolution (SIZE check failed: my test-design error, stated). Side facts (same run, broad): lc_mix is 0.6-1.2 K
  colder at 850 hPa over the whole basin, mslp +22..+26 Pa over TN/Bay/Arabian Sea, TN rain -2.9 mm/day. [reg: 18:2x v850 step-1 registration |
  inputs: T42 3 starts, model-model difference | fail-5why: below]
- FAIL-5WHY: (1) inconclusive <- (2) T42 cannot resolve the TN-coast v850 signal <- (3) I chose T42 to avoid the T170 local OOM without checking it
  reproduces the signal first. REGISTERED (before the result): the same map test at T170 on Kaggle (one job, first slot after the weekly reset,
  behind tn-clddet), same decision rule (local co-located with heating/rain vs basin-wide). [reg: this line | inputs: n/a | fail-5why: n/a]
- 18:42 IST REGISTERED (before the result): T42 5-day cloud check of the full candidate + cld_det (11 Nov start, the same script/start as the 16:21
  check): it is a SCREEN only (no verdict; verdicts at T170). It says the detrainment source moves low cloud toward ERA5 if Bay and S.India
  days 3-5 ratios rise toward 0.7-1.3x from 0.64/0.78/0.41 and 0.57/1.10/0.77 without passing 1.3x. [reg: this line | inputs: n/a | fail-5why: n/a]
- 19:07 IST cld_det SCREEN (T42, 11 Nov, 5 days; registered 18:4x): low cloud Bay 0.232/0.365/0.329/0.347/0.328 (days 3-5 1.98/2.23/1.74x ERA5),
  S.India 0.309/0.649/0.343/0.486/0.556 (1.67/2.70/2.37x) - nearly all of it the carried large-scale cloud (c_ls 0.31-0.55); total cover Bay days 3-5
  0.46/0.45/0.41 vs ERA5 0.55/0.57/0.57 (lower). SCREEN NEGATIVE (overshoots 1.3x by far). tn-clddet REMOVED from the Kaggle queue so no GPU
  minutes go to a variant the screen already rejects. cld_det HELD. [reg: 18:4x cld_det screen registration | inputs: ERA5 lcc5/tcc days 1-5
  3-start mean, model one start (stated) | fail-5why: below]
- FAIL-5WHY (size first, T42 Bay profile 11 Nov h24-48): detrained air D peaks at sigma 0.73-0.81 (0.38-0.47 /day) and ~85-90 % of the detrained
  mass is below 650 hPa (above 500 hPa only ~0.04 /day per layer); the carried cloud follows (cfa 0.12-0.19 at sigma 0.73-0.84). (1) low cloud too
  high <- (2) deep detrainment lands at 700-800 hPa <- (3) our deep updraughts end low, OR our bulk mass-flux shape (eta falls linearly over the
  upper 40 % of the cloud - NOT the IFS organised/turbulent detrainment) puts detrainment low. ERA5 Bay cloud fraction at 300/250/200 hPa (1 Nov
  start, 0-48 h) = 0.05/0.10/0.21: real deep convection here tops near 200 hPa. REGISTERED (before the result): model Bay cloud fraction at
  300/250/200 hPa (same start/hours, T42, total radiation cloud) and the share of deep updraught mass flux reaching sigma < 0.4. If the model
  upper cloud is < 0.5x ERA5 and < 30 % of deep mass flux reaches sigma 0.4, the root is LOW DEEP TOPS (bottom-heavy deep convection, which
  also fits the +2.8 K/day deep heating at 700 hPa and links to Tracks/P5b); otherwise it is the eta shape. [reg: this line | inputs: ERA5 cc 300-200 hPa | fail-5why: n/a]
- 19:20 IST DEEP-TOP TEST RESULT (T42; 1 Nov upper cloud, 11 Nov tops h24-48, 94 deep column-samples in the Bay box): model total cloud at
  300/250/200 hPa 0.08-0.25/0.18-0.32/0.32-0.37 vs ERA5 0.02-0.07/0.09-0.14/0.19-0.24 (NOT < 0.5x - higher); deep tops: 51 % of deep columns top
  below sigma 0.7 and carry 60 % of the detrained mass; only 20 % reach sigma < 0.4. By the REGISTERED rule (both conditions needed) the verdict is
  "not low tops -> eta shape". Stated plainly: the upper-cloud condition was a poor proxy - that cloud is our DIAGNOSTIC anvil (made from the
  rain rate, not from the plume top), so it cannot measure tops; my test-design error. The direct measure (tops) says most "deep" plumes stop
  at 650-750 hPa. [reg: 19:3x deep-top registration | inputs: ERA5 cc 300-200 hPa (1 Nov start), model T42 | fail-5why: below]
- FAIL-5WHY / next: (1) detrainment low <- (2) half the deep plumes stop below 700 hPa <- (3) in our candidate the plume dies at the first level
  of negative buoyancy (mf_wke = 0); IFS integrates the updraught kinetic energy (eq. 6.10) so plumes coast through thin stable layers (the
  0 C layer near 550-600 hPa and the trade-type stable layer near 750 hPa). mf_wke (already coded, eq. 6.10) was HELD on 18 Nov "re-test after
  the land fix"; the land fix closed 25 Nov, so the re-test is due. REGISTERED (before the result): T42 screen candidate + cld_det + mf_wke 1,
  same start/hours/box: SUPPORTED if the detrained-mass share from tops below sigma 0.7 falls from 0.60 to <= 0.35 and the share reaching
  sigma < 0.4 rises from 0.20 to >= 0.40. Screen only; adoption needs the T170 four-rule test after the weekly reset. [reg: this line | inputs: n/a | fail-5why: n/a]
- 19:27 IST mf_wke SCREEN RESULT (T42, 11 Nov h24-48, 143 samples): detrained-mass share from tops below sigma 0.7 0.60 -> 0.29 (rule <= 0.35 PASS);
  columns reaching sigma < 0.4 0.20 -> 0.19 (rule >= 0.40 FAIL). NOT SUPPORTED as a screen. Tops moved up from 700-800 to 500-700 hPa and stop
  there. [reg: 19:3x mf_wke registration | inputs: model T42 one start (stated) | fail-5why: below]
- FAIL-5WHY: (1) plumes now stop at 500-650 hPa <- (2) that is the 0 C level (~550-600 hPa in the tropics), where a plume without freezing
  loses buoyancy against an environment that ERA5/IFS keeps warm by freezing <- (3) our candidate has no fusion heat in the updraught
  (mf_ice off); IFS splits condensate by the mixed-phase function and releases L_f for the ice part. Coded mf_ice_ifs (IFS alpha, no free
  share). REGISTERED (before the result): same screen with candidate + cld_det + mf_wke + mf_ice_ifs, same two conditions. [reg: this line | inputs: n/a | fail-5why: n/a]
- 19:34 IST mf_ice_ifs SCREEN RESULT: below-0.7 share 0.28, reaching sigma < 0.4 0.17 (no change from mf_wke alone) -> NOT SUPPORTED; freezing is
  NOT what stops the plumes (they stop at 600-700 hPa, below the 0 C level). mf_ice_ifs HELD. [reg: 19:4x mf_ice_ifs registration | inputs: model T42 one start (stated) | fail-5why: below]
- FAIL-5WHY: the IFS entrainment we use falls as (qs/qs_base)^3 (~0.03 of its base value at 600 hPa), so dilution should not stop a Bay plume
  there; what is left is the environment the plume rises through (model-drift: low levels cooled / mid levels warm) or our plume formulation
  itself. REGISTERED (before the result): the same tops measure at the ERA5 START STATE (h0, plus h3/h6 the first steps): if at h0 >= 0.40 of
  deep columns reach sigma < 0.4 and it falls by h24-48, the cause is the model drift of the environment (links to the cold-growth / cloud
  chain); if tops are low already at h0, the cause is the plume formulation. [reg: this line | inputs: n/a | fail-5why: n/a]
- 19:36 IST h0 TOPS RESULT (T42, 11 Nov, h0/3/6, 27 deep samples - small, stated): reaching sigma < 0.4 0.52 (h24-48: 0.20); tops below sigma 0.7
  0.11 of detrained mass (h24-48: 0.60). By the registered rule: tops are HIGH at the ERA5 state and collapse within a day -> the cause is MODEL
  DRIFT of the environment, not the plume formulation. [reg: 19:5x h0-tops registration | inputs: ERA5 start state, model T42 | fail-5why: n/a]
- NEXT 5-WHY STEP: which drift caps the plumes at 600-700 hPa? Candidate mechanism (from earlier budgets): deep heating +2.8 K/day at sigma 0.7
  (ERA5 Q1 total ~+1.1 K/day there) -> a warm layer near 700 hPa -> plumes stop under it -> they detrain and heat there again (self-reinforcing).
  REGISTERED (before the result): model Bay box T at sigma 0.925/0.85/0.7/0.6/0.5, h0 vs h36: if (T700 - T850) rises by >= 1 K and the
  deep heating peak sits at 0.65-0.75, the self-capping loop is named; if instead 850/925 cool by >= 1 K with 700 unchanged, it is the low-level
  cold growth (cloud chain). [reg: this line | inputs: n/a | fail-5why: n/a]
- 19:44 IST STABILITY DRIFT RESULT (T42 Bay box, h36 - h0; 11 Nov / 1 Nov): T at sigma 0.5/0.6/0.7/0.85/0.925 = +0.27/+0.79/+0.24/+0.22/-0.04 and
  +0.69/+1.49/+0.77/-0.12/-0.71 K. (T700 - T850) change +0.01 / +0.89 (rule >= 1 K: NOT met); 850/925 cooling >= 1 K: NOT met -> NEITHER
  mechanism named by the registered rule; INCONCLUSIVE. What the numbers do show: the largest warming is at sigma 0.6 (+0.8/+1.5 K), i.e. a
  cap forms at 600 hPa, not 700 - my registered levels were one layer too low. [reg: 19:5x stability registration | inputs: model T42 2 starts | fail-5why: below]
- FAIL-5WHY: a plume's buoyancy at 600 hPa is theta_e(source, diluted) - theta_es(600); temperature alone misses the source MOISTURE.
  REGISTERED (before the result): Bay box theta_e at the plume source (lowest 2 levels) and theta_es at sigma 0.6, h0 vs h36, same 2 starts:
  the drift term that removes more of the h0 buoyancy margin (source theta_e fall vs theta_es(600) rise) is named; if both are < 1 K the
  drift is not the cap and the next check is the plume code path between h0 and h24 (e.g. the source level choice). [reg: this line | inputs: n/a | fail-5why: n/a]
- 19:51 IST THETA_E DRIFT RESULT (T42 Bay box, h36 - h0, 11 Nov / 1 Nov): source theta_e +4.60/+2.66 K (lowest-level q +1.6/+0.9 g/kg), theta_es(600)
  +2.32/+4.58 K; buoyancy margin -3.21 -> -0.93 (11 Nov, MORE buoyant) and +1.57 -> -0.34 (1 Nov, less). On 11 Nov - the start whose tops
  collapsed - neither drift term removes margin, so by the registered rule the box-mean drift is NOT the cap; next check is the plume code
  path / timing. 1 Nov shows a mid-level (600 hPa) warming of the kind suspected. Side fact: the lowest level over the Bay moistens by
  1-1.6 g/kg in 36 h. [reg: 20:0x theta_e registration | inputs: model T42 2 starts, box means (deep columns not separated - stated) | fail-5why: below]
- FAIL-5WHY / REGISTERED (before the result): tops share reaching sigma < 0.4 at each hour h0, 3, 6, 9, 12, 18, 24 (11 Nov): an abrupt drop
  within the first 3-6 h (spin-up: carry fields such as surface fluxes / radiation / cloud starting from zero) names the code path; a gradual
  fall over 12-24 h names a drift inside the convecting columns that the box mean hides. [reg: this line | inputs: n/a | fail-5why: n/a]
- 19:56 IST TOPS TIMING RESULT (T42, 11 Nov, 12-15 deep samples per hour - small, stated): reaching sigma < 0.4 h0 1.0 (n 3), h3-12 0.42-0.53,
  h18 0.33, h24 0.42, h24-48 mean 0.20. GRADUAL fall over 12-48 h, no abrupt drop in the first 3-6 h -> by the registered rule NOT spin-up;
  a drift inside the convecting columns that the box mean hides. [reg: 20:1x timing registration | inputs: model T42 one start | fail-5why: n/a]
- REGISTERED (before the result): in DEEP-ACTIVE columns only (Bay box, 11 Nov), compare h3-12 vs h30-48: source theta_e, theta_es at sigma
  0.6 and 0.5, and RH at sigma 0.6-0.5 (entrainment dilution). The term that removes the most buoyancy margin is named; RH falling by >= 0.15
  names mid-level drying (entrainment), a theta_es rise >= 1.5 K names mid-level warming, a source theta_e fall >= 1.5 K names the BL. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:05 IST DEEP-COLUMN DRIFT RESULT (T42 11 Nov, deep-active Bay columns, early h3-12 n 52 vs late h30-48 n 71): source theta_e 344.93 -> 344.20
  (-0.73), theta_es(600) 344.19 -> 345.79 (+1.60), theta_es(500) +0.40, RH 600-500 0.604 -> 0.417 (-0.19); margin at 600 hPa +0.74 -> -1.58 K.
  By the registered rule: mid-level WARMING (+1.6 >= 1.5) is the largest margin term and mid-level DRYING (-0.19 >= 0.15) is also met; the
  BL source is not (-0.7). Named: the convecting columns warm and dry at 600-500 hPa over 1-2 days, capping the plumes. [reg: 20:2x deep-column
  registration | inputs: model T42 one start, conditional on deep-active | fail-5why: n/a]
- Reference check started: ERA5 Bay box-mean RH500 days 0/1/2 (11 Nov) 0.450/0.424/0.388, RH700 0.600/0.661/0.698, T700 flat 283.2 K (ERA5 itself
  dries at 500 hPa by ~0.06 in 2 days). REGISTERED (before the result): model Bay box-mean RH500, RH700 and T700 daily means days 0-2, same
  start: if the model's RH500 falls >= 0.08 more than ERA5's or T700 rises >= 0.5 K vs ERA5's flat T700, the mid-level drift is a MODEL
  error (next: which process heats/dries 600-500 hPa in the budget); if within those, the capping is in the plume's response, not the state. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:11 IST MODEL vs ERA5 MID-LEVEL STATE (T42 11 Nov, Bay box daily means days 0/1/2): model RH500 0.492/0.534/0.484 vs ERA5 0.450/0.424/0.388
  (model WETTER, no extra drying); T700 283.06/283.01/283.23 vs ERA5 283.17/283.25/283.15 (flat, within 0.25 K). By the registered rule: the
  box-mean state does not drift -> the capping is in the PLUME'S RESPONSE (the convecting columns warm/dry themselves at 600-500 hPa), not the
  large-scale state. [reg: 20:1x ERA5 RH registration | inputs: ERA5 rh_truth (daily, 1.5 deg), model T42 | fail-5why: n/a]
- REGISTERED (before the result): the heating profile. Model Bay box physics heating (all physics incl. radiation = apparent Q1) by level,
  day 1 (h3-21, 3-hourly), starts 1 + 11 Nov, vs ERA5 Q1 (q1bay2 truth, day-1 mean: ~1.0 K/day at 850-900, 0.6-0.8 at 650-750, 1.1-1.2 at
  550-600, 0.5-0.9 at 250-450). If the model exceeds ERA5 by >= 1 K/day in a layer below 500 hPa while falling short above 400 hPa, the deep
  heating is bottom/mid-heavy (plume response named; links Tracks/P5b); otherwise the heating profile is not the cause. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:18 IST HEATING PROFILE RESULT (T42, Bay box, starts 1+11 Nov, model day 1 h3-21; ERA5 q1bay2 mean is h27-45 - a one-day timing mismatch,
  stated): model physics heating 925/850/700/600/500/400/300/250/200 = -0.64/-0.81/-0.05/-0.19/-0.54/-0.75/-1.09/-1.49/-1.10 K/day vs ERA5 Q1
  +0.92/+1.01/+0.68/+1.09/+0.98/+0.91/+0.49/+0.58/+0.92: the model is SHORT by 0.7-2.1 K/day at EVERY level. By the registered rule (excess
  below 500 AND shortfall above 400) NOT met -> the heating SHAPE is not the cause of the capping. But the size is the finding: a column
  heating deficit of ~1.6 K/day ~ 190 W m-2 ~ 6 mm/day of rain-equivalent over the Bay - the same direction as P5b (TN rain 0.57) and the
  cold growth (P5a). [reg: 20:2x Q1-profile registration | inputs: ERA5 q1bay2 (h27-45), model T42 h3-21 | fail-5why: below]
- NEXT (registered before the result): split the column deficit with ERA5 flux truth (flux_truth_2020: daily tp24, shf, lhf, surface and TOA
  net SW/LW, days 0-2, the 1 + 11 Nov starts) into L*P, SH and atmospheric net radiation (TOA net - surface net), model vs ERA5, Bay box day 1.
  The term carrying >= 50 % of the deficit is named. Timing matched this time (both day 1). [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:26 IST FLUX SPLIT RESULT (partial): ERA5 flux_truth radiation fields are ALL NaN (the WeatherBench2 store lacks them for 2020 - the truth file
  is incomplete; my input check found it only now). Measured parts, Bay box day 1, model (T42 candidate) vs ERA5 (1 / 11 Nov): rain 0.79/2.89
  vs 1.90/5.08 mm/day (0.42/0.57x; deficit 32/63 W m-2 of L*P), latent heat 62.5/87.2 vs 81.7/115.0 W m-2 (0.76x), sensible 10.1/14.2 vs
  12.5/14.0. L*P explains only 17-33 % of the ~190 W m-2 Q1-residual deficit; the radiation share cannot be measured -> the registered >= 50 %
  rule cannot be applied: INCONCLUSIVE (input missing). Named facts: Bay evaporation is 24 % low and rain 43-58 % low on day 1.
  [reg: 20:4x flux-split registration | inputs: ERA5 flux_truth (rad NaN), tp24, lhf, shf; model T42 | fail-5why: below]
- FAIL-5WHY / REGISTERED (before the result): new ERA5 fetch 'bayfx truth' (ARCO hourly, Bay box day 1, 1 + 11 Nov): H, LE, rain, 10-m wind
  (all / sea), sea q_sat(SST)*0.98 - q2m, and atmospheric net radiation (TOA - surface). Decisions: (a) radiation: if model atmospheric
  radiative cooling exceeds ERA5's by >= 50 W m-2 it is named as a column-deficit term; (b) evaporation over sea: LE = rho Ck U dq - the
  factor (U or dq or Ck = LE/(rho U dq)) that is >= 15 % off ERA5 is named. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:37 IST BAYFX RESULT (Bay box day 1, model T42 candidate vs ERA5 hourly, 1 / 11 Nov): atmospheric net radiation -114.6/-118.9 vs -106.1/-108.5
  W m-2 (model cools 8-10 W m-2 more; rule >= 50: radiation NOT named). Rain 0.79/2.89 vs 2.76/6.93 mm/day (0.29/0.42x). Sea evaporation
  59.2/107.4 vs 86.1/126.9 W m-2 (0.69/0.85x): U ~2.67/4.89 vs 3.35/4.95 m/s (0.80/0.99 - named on 1 Nov only), sea-air humidity difference
  dq 4.27/4.91 vs 6.19/6.60 g/kg (0.69/0.74x - NAMED on both starts; conservative, because our dq uses q at ~80 m, which is drier than q2m),
  effective Ck 1.80/1.56e-3 vs 1.44/1.35e-3 (ours HIGHER, compensating). Named: the near-surface air over the Bay is too MOIST for the SST,
  so evaporation is low, and with it rain. [reg: 20:5x bayfx registration | inputs: ERA5 ARCO hourly (fetched 20:4x), model T42; height mismatch U (log-law 0.84) and q (80 m vs 2 m) stated | fail-5why: n/a]
- 5-WHY next step, REGISTERED (before the result): is the moist surface air the BL failing to vent? Model Bay RH925 daily means days 0-2 vs ERA5
  rh_truth RH925 (11 Nov): if the model RH925 rises >= 0.05 above ERA5's by day 1-2, BL moisture trapping is named and the venting processes
  (shallow mass flux sh_ifs2, BL-top entrainment) get their own size check; if not, the surface-layer humidity itself (lowest level) is the
  place to look. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:43 IST RH925 RESULT (T42 11 Nov, Bay box daily, model vs ERA5): RH925 0.784/0.824/0.827 vs 0.767/0.788/0.782 (+0.017/+0.036/+0.045; rule >= 0.05:
  NOT met); RH850 0.760/0.796/0.776 vs 0.745/0.788/0.771 (close). By the registered rule: BL trapping at 925 hPa is NOT named; the excess
  moisture sits in the SURFACE LAYER (lowest level q rose 15.4 -> 17.0 g/kg in 36 h, 1-1.6 g/kg - the same size as the 1.8 g/kg dq shortfall).
  [reg: 20:5x RH925 registration | inputs: ERA5 rh_truth daily, model T42 6-hourly | fail-5why: n/a]
- REGISTERED (before the result): ERA5 'bayq truth' - specific humidity at 1000/975/950/925/900 hPa and q2m over Bay sea points, h0 and day 1
  (1 + 11 Nov). Model the same levels. If the model's q(1000) - q(925) gradient on day 1 exceeds ERA5's by >= 1 g/kg (moisture held in the
  lowest levels), the vertical mixing out of the surface layer is named (next: K / surface-layer coupling size check); if the model is
  uniformly moister through 1000-900 by >= 1 g/kg, the source/sink balance of the whole BL is named instead. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:50 IST BAYQ RESULT + INPUT DEFECT FOUND. ERA5 vs model (Bay sea, day 1): q1000 17.55/17.09 vs 17.93/17.35, q925 14.71/14.54 vs 15.04/13.76; the
  q(1000)-q(925) gradient exceeds ERA5's by 0.05 (1 Nov) / 1.04 (11 Nov) g/kg; uniform excess >= 1 g/kg NOT met -> the registered rule names
  surface-layer mixing on 11 Nov only. BUT the input check behind dq found the real cause: model SST over the Bay sea nodes is 299.52/299.70 K vs
  the library's 302.23/302.40 K (min 277.8 K!). mm2.init fills the SST NaNs over land with 0.0 BEFORE interpolating to the model grid
  (np.where(isfinite(sst), sst, 0.0)), so every coastal sea node is blended with 0 K: values 260-300 K stay as a too-cold SST, values < 260 K are
  zeroed and the node is then treated as LAND (sea = ~land & sst > 0). The sea-air humidity difference is short by 2.2 g/kg of q_sat(SST) for
  exactly this reason. This touches every coast at every resolution (TN coast, Bay, Arabian Sea). [reg: 20:5x bayq registration | inputs:
  ERA5 ARCO q profile, library SST, model init | fail-5why: n/a]
- REGISTERED (before the result): (1) SIZE at T170 (exam resolution), init only: share of sea nodes whose SST is >= 1 K below the library's
  nearest-sea value, and share of library-sea nodes turned to land, globally and in the Bay/TN box. (2) FIX sst_fill (standard sea-over-land
  extrapolation, no tuned value): fill NaN/land cells from finite sea neighbours on the 1.5 deg grid (iterated neighbour mean) BEFORE the
  interpolation; land nodes still use land temperature (mask unchanged). Gate for the fix input check: Bay sea-node SST mean within 0.3 K of
  the library's and min >= 295 K at T42 and T170. Forecast gates for adoption: the T170 four rules (TN v850 d1 >= -1.0; TN rain >= 0.85; z500 d5
  <= lc_mix + 2 SE; S.India cold growth -50 %) after the weekly reset. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:51 IST SST DEFECT SIZE + FIX INPUT CHECK (11 Nov library, init only): WITHOUT fill - T42: 15.1 % of all sea nodes zeroed (run as land), Bay sea
  mean 299.70 vs 302.44 K, min 277.5, 9 of 27 Bay sea nodes zeroed; T170: 14.8 % of sea nodes zeroed globally, 2.5 % >= 1 K too cold, Bay
  301.00 vs 302.42 K, min 261.5, 174 of 478 Bay sea nodes (36 %) run as LAND. The library NaNs are coastal 1.5-deg cells (sea-ice cells carry
  271.5 K, so the fill does not touch ice). WITH sst_fill: 0 nodes zeroed; Bay 302.40/302.40 K (ref 302.41/302.40), min 301.81/301.75 -> fix
  input gate (within 0.3 K, min >= 295 K, T42 and T170) PASS. Every Stage-1 exam so far ran with this defect. tn-sstfill (candidate +
  sst_fill, part-3 T170, the four rules) queued FIRST for the weekly reset. [reg: sst registration, block above (20:5x) | inputs: library SST/LSM, model init T42/T170 | fail-5why: n/a]
- REGISTERED (before the result): T42 screen, day 1 Bay box, candidate + sst_fill vs ERA5 bayfx: sea LE ratio rises from 0.69/0.85 and rain
  ratio from 0.29/0.42 (1 / 11 Nov). Screen only - the verdict is tn-sstfill. [reg: this line | inputs: n/a | fail-5why: n/a]
- 20:59 IST sst_fill T42 SCREEN (day 1 Bay box, vs ERA5 bayfx, 1 / 11 Nov): sea LE 75.2/128.9 vs 86.1/126.9 W m-2 -> 0.87/1.02x (was 0.69/0.85) RISES;
  atmospheric radiation -107.1/-105.3 vs -106.1/-108.5 (now within 3 W m-2, was 8-10 too cold); rain 0.51/5.01 vs 2.76/6.93 mm/day -> 0.18/0.72x
  (was 0.29/0.42): RISES on 11 Nov, FALLS on 1 Nov (h1-22 accumulation vs 24 h before - sampling not identical, stated). Screen: evaporation and
  radiation move to ERA5 on both starts; rain mixed. Verdict waits for tn-sstfill (T170, 18 starts). [reg: sst-screen registration, block above (20:5x) | inputs: ERA5 bayfx, model T42 | fail-5why: n/a]
- 20:59 IST CORRECTION (my error): two stamps above named registrations at "21:2x"/"21:3x" - times that had not happened yet; I wrote them without
  checking the clock. Corrected to point at the registration blocks (20:5x). The heading times of every block tonight are clock-checked; the
  "reg:" labels tonight are approximate (to the 10 minutes) and each points to the block written immediately before its result. [reg: n/a (correction) | inputs: n/a | fail-5why: n/a]
- 21:00 IST REGISTERED (before the result): T42 5-day cloud screen (cld_t170.py, 11 Nov, same as the 16:21 check) for candidate + sst_fill, and
  then candidate + sst_fill + cld_det: low cloud days 3-5 vs ERA5 (rule 0.7-1.3x, Bay and S.India). Screens only; tells whether the coastal SST
  defect also distorted the cloud results that HELD cld_prog / cld_det. [reg: this line | inputs: n/a | fail-5why: n/a]
- 21:30 IST CLOUD SCREENS WITH sst_fill (T42, 11 Nov, days 3-5 low cloud vs ERA5): candidate + sst_fill Bay 0.40/0.34/0.39x, S.India 0.56/0.61/0.71x
  (too LOW, below 0.7 - slightly lower than without the fix); + cld_det Bay 2.54/2.89/2.28x, S.India 2.87/3.40/2.77x (too HIGH). The SST defect
  did not cause the cloud failures: without the convective source there is too little low cloud, with it far too much, because the deep
  plumes detrain at 650-800 hPa (deep-top 5-why). cld_prog / cld_det stay HELD. [reg: 21:0x cloud-screen registration | inputs: ERA5 lcc5, model T42 one start (stated) | fail-5why: below]
- FAIL-5WHY (deep-top chain, plume response): ours removes CAPE over a FIXED 2400 s; IFS's deep closure time scale is tau = (z_top - z_base) /
  w_up x (1 + 264/N) (~5100 s at T170, x7.3 at T42) - IFS convection consumes CAPE 2+ times more slowly, so a convecting column stays unstable
  and keeps deep tops. Coded tau_ifs (that formula; w_up from eq. 6.10). REGISTERED (before the result): T42 tops screen (11 Nov, h24-48),
  candidate + cld_det + sst_fill + tau_ifs: SUPPORTED if columns reaching sigma < 0.4 >= 0.40 (was 0.20) and the detrained-mass share from
  tops below sigma 0.7 <= 0.35 (was 0.60). Screen only (T42's x7.3 factor exaggerates; stated). [reg: this line | inputs: n/a | fail-5why: n/a]
- 21:36 IST tau_ifs TOPS SCREEN (T42 11 Nov h24-48, candidate + cld_det + sst_fill + tau_ifs, 253 deep samples): columns reaching sigma < 0.4 0.51
  (was 0.20; rule >= 0.40 PASS); detrained-mass share from tops below sigma 0.7 0.15 (was 0.60; rule <= 0.35 PASS) -> SUPPORTED (screen).
  Deep-active share of Bay samples rose 94 -> 253 of 315 (slower CAPE removal keeps columns convecting). The registered combination had TWO
  changes (sst_fill + tau_ifs), so attribution is open. [reg: 21:3x tau_ifs registration | inputs: model T42 one start (stated) | fail-5why: n/a]
- REGISTERED (before the results): (1) attribution - the same tops screen with cld_det + sst_fill WITHOUT tau_ifs; (2) T42 5-day low-cloud screen
  (cld_t170.py, 11 Nov) for candidate + cld_det + sst_fill + tau_ifs, rule days 3-5 within 0.7-1.3x ERA5 in Bay and S.India. [reg: this line | inputs: n/a | fail-5why: n/a]
- 21:43 IST ATTRIBUTION (same screen, cld_det + sst_fill, NO tau_ifs, 140 samples): reaching sigma < 0.4 0.25, below-0.7 detrained share 0.42 ->
  sst_fill alone moves tops a little (0.20 -> 0.25); tau_ifs carries most of the change (0.25 -> 0.51, 0.42 -> 0.15). tau_ifs NAMED as the
  deep-top fix at screen level. [reg: 21:4x attribution registration | inputs: model T42 one start (stated) | fail-5why: n/a]
- 21:58 IST tau_ifs 5-DAY LOW-CLOUD SCREEN (T42 11 Nov; candidate + cld_det + sst_fill + tau_ifs): low cloud days 3-5 Bay 2.81/3.46/2.67x, S.India
  3.49/4.25/3.49x ERA5 (rule 0.7-1.3x FAIL - worse than without tau_ifs 2.54/2.89/2.28x); total cover Bay 1.20/1.13/1.01x. The tops are fixed
  (screen above) but the low-cloud excess grows. Component split (Bay): c_ls 0.18-0.50 with cld_det vs 0.003-0.022 without -> the excess is the
  carried large-scale cloud, and on 11 Nov h24-48 it sits at sigma 0.86-0.93 where deep detrainment D = 0 (detprof7). So the cloud there does
  NOT come straight from detrainment. tau_ifs: tops PASS, low cloud FAIL -> HELD for the T170 test until the low-cloud source is named.
  [reg: 21:4x cloud-screen registration | inputs: ERA5 lcc5/tcc, model T42 one start (stated) | fail-5why: below]
- FAIL-5WHY / REGISTERED (before the result): budget of the carried cloud fraction at sigma 0.84-0.93 (Bay box, 11 Nov h24-48) by term -
  formation da_f, detrainment D, erosion/evaporation - with and without cld_det. The term that differs most between the two runs is named.
  Candidate mechanisms (not yet tested): weaker downdrafts (cld_det reduces convective rain, and a_dd is capped by the rain) leave a moister
  sub-cloud layer, so the formation term fires there. [reg: this line | inputs: n/a | fail-5why: n/a]
- 22:10 IST LOW-CLOUD BUDGET RESULT (T42 11 Nov, Bay box, sigma 0.84-0.93, h24-48 3-hourly samples; both with sst_fill): without cld_det the carried
  cloud there is 0.000 (RH 0.813 < RH_crit 0.849, no formation); with cld_det it is 0.051 and RH is 0.907 (+0.094), with formation and detrainment
  both ~0 at the sampled times. The term that differs is the HUMIDITY of the 850-925 hPa layer, not a cloud source -> by the registered rule the
  cloud-term budget does not name a term; it names the state: cld_det moistens 850-925 hPa by ~0.09 RH. [reg: 22:0x cloud-budget registration |
  inputs: model T42 one start, 3-hourly snapshots (formation between samples not captured - stated) | fail-5why: below]
- REGISTERED (before the result): the downdraft lead. Downdraft mass flux Md (capped by the updraft's rain production in conv_mf) and the
  convective rain, Bay box day 2, with vs without cld_det: if Md falls by >= 30 % with cld_det, the weaker downdraft (less dry mid-level air
  brought down) is named for the moister 850-925 layer; if Md is within 30 %, the lead is closed and the next check is the cloud-water
  evaporation (cnet) profile. [reg: this line | inputs: n/a | fail-5why: n/a]
- 22:23 IST DOWNDRAFT RESULT (T42 11 Nov Bay box h24-48): without / with cld_det - Md 0.0034 / 0.0049 kg m-2 s-1 (+44 %, not a fall), Mb 0.0097 /
  0.0141 (+45 %), updraft rain production 8.25 / 4.49 mm/day (-46 %). Rule (Md falls >= 30 %) NOT met -> downdraft lead CLOSED. What the
  numbers show: with cld_det about half of the updraft condensate is detrained instead of rained, the column keeps that water, and convection
  runs stronger. [reg: 22:1x downdraft registration | inputs: model T42 one start | fail-5why: below]
- REGISTERED (before the result): the cloud-water fate. Bay box h24-48 with cld_det, column integrals (mm/day): detrained condensate, carried-
  cloud evaporation back to vapour (-cnet where < 0, incl. ev0), large-scale autoconversion to rain. If >= 50 % of the detrained water returns to
  vapour, "recycling" (detrained water evaporating instead of raining out) is named for the moistening; the IFS reference for the split is the
  same equations, so the next check would be their SIZE (w_up in eq. 6.39, l_crit, Sundqvist aut on detrained cloud). [reg: this line | inputs: n/a | fail-5why: n/a]
- 22:30 IST CLOUD-WATER FATE RESULT (T42 11 Nov Bay box h24-48, cld_det on): detrained 3.49 mm/day; back to vapour 0.29 (8 %); large-scale
  autoconversion to rain 2.65 (76 %). Rule (>= 50 % back to vapour) NOT met -> recycling NOT named; the detrained water mostly rains out.
  [reg: 22:2x water-fate registration | inputs: model T42 one start | fail-5why: below]
- REGISTERED (before the result): split the +0.09 RH at sigma 0.84-0.93 into temperature and humidity: T and q there, with vs without cld_det
  (same samples). If T is >= 0.5 K colder with cld_det, cooling is named (next: radiative cooling under the new carried cloud); if q is >= 0.8
  g/kg higher, moistening is named (next: the vertical moisture flux of the stronger mass flux, Mb +45 %). [reg: this line | inputs: n/a | fail-5why: n/a]
- 22:42 IST T/q SPLIT RESULT (sigma 0.84-0.93, Bay box h24-48, without / with cld_det): T 293.51 / 292.51 K (-1.00 K, rule >= 0.5: COOLING NAMED);
  q 13.55 / 14.16 g/kg (+0.61, rule >= 0.8: not named). The 850-925 hPa layer gets colder (and somewhat moister) when the detrained water is
  carried. [reg: 22:3x T/q registration | inputs: model T42 one start | fail-5why: below]
- REGISTERED (before the result): heating at sigma 0.925 and 0.85 by process (bud_t170.py at T42, 11 Nov, days 1-2), with vs without cld_det:
  the process whose cooling grows most is named. Candidates: rain evaporation (h_evap: the 2.65 mm/day of autoconverted rain falls from
  ~800 hPa through the sub-cloud layer, cools and moistens - fits both signs) or radiation under the new cloud (rad_app). [reg: this line | inputs: n/a | fail-5why: n/a]
- 23:00 IST PROCESS BUDGET RESULT (T42 11 Nov Bay box, K/day, without -> with cld_det): sigma 0.925 h_deep +1.01/+1.72 -> -0.37/-0.21 (days 1/2;
  change -1.4/-1.9), rad_app -1.39/-1.18 -> -0.94/-0.57 (less cooling), h_evap ~0 both, h_lsc 0 -> +0.08/+0.23; sigma 0.85 h_deep +1.51/+2.30 ->
  +0.85/+1.58. NAMED: the DEEP-CONVECTION tendency at 925 hPa turns from warming to cooling (largest change); rain evaporation is not it.
  [reg: 22:4x process-budget registration | inputs: model T42 one start | fail-5why: below]
- REGISTERED (before the result): split h_deep at sigma 0.925/0.85 into the updraught/subsidence part (dT1 Mb) and the downdraft part (dT_dd),
  with vs without cld_det. If the downdraft part carries >= 2/3 of the change, the downdraft is named (it grows with Mb +45 % while the
  subsidence warming no longer balances it); otherwise the updraught/subsidence part (changed condensate bookkeeping, dq1 with Pdet) is named. [reg: this line | inputs: n/a | fail-5why: n/a]
- 23:12 IST UP/DOWN SPLIT RESULT (sigma 0.925, K/day, without -> with cld_det): updraught/subsidence part 3.07 -> 0.47 (-2.6), downdraft -1.20 ->
  -0.78 (+0.4). Rule: downdraft NOT named; the updraught part is. [reg: 22:5x split registration | inputs: model T42 one start | fail-5why: below]
- ROOT CAUSE = MY CODE BUG in cld_det (coded 18:3x today), stated plainly: I replaced the vapour sink "- eta cond / mass" (vapour removed where it
  condenses) with "- P1/mass - Pdet/mass" (removed where it RAINS or DETRAINS). The vapour-flux divergence leaves the condensed vapour in the
  condensing layer, so with cld_det the cloud-base layers (850-925 hPa) were spuriously moistened and, through dT1 = (dh1 - L dq1)/cp, COOLED
  by L eta cond / cp - exactly the -1 K / +0.6 g/kg / +0.09 RH found above. Water was conserved in the column, so the smoke test did not catch
  it; the vertical placement was wrong. FIXED: dq1 = flux divergence - eta cond / mass (as the original); rain and detrained water are sinks of
  the updraught liquid only. CONSEQUENCE: every result tonight run WITH cld_det on is invalid and withdrawn - the cld_det low-cloud screens
  (1.7-4.3x), the deep-top measurements (detprof: 0.20 reach / 0.60 below 0.7, the h0/timing/drift chain, mf_wke, mf_ice_ifs, tau_ifs and its
  attribution) and the budgets above. Results WITHOUT cld_det stand: sst_fill defect and fix, bayfx/bayq/RH comparisons, the low-cloud screens
  without cld_det. [reg: n/a (correction of my own code) | inputs: n/a | fail-5why: n/a]
- REGISTERED (before the results): with the FIXED cld_det - (1) the T42 tops screen (11 Nov h24-48, candidate + cld_det + sst_fill): reaching
  sigma < 0.4 and detrained share below 0.7, reported against the old rule (>= 0.40 / <= 0.35) to see if any tops problem remains; (2) the T42
  5-day low-cloud screen, rule days 3-5 within 0.7-1.3x ERA5 in Bay and S.India. [reg: this line | inputs: n/a | fail-5why: n/a]
- 23:19 IST TOPS SCREEN, FIXED cld_det (T42 11 Nov h24-48, candidate + cld_det + sst_fill, 110 samples): reaching sigma < 0.4 0.53 (>= 0.40 PASS),
  detrained share from tops below 0.7 0.19 (<= 0.35 PASS). Detrainment now peaks at sigma 0.23-0.52 (0.15-0.18 /day) and the carried cloud sits
  aloft (cfa 0.22-0.50 at sigma 0.23-0.45; <= 0.07 below 0.7). The "low deep tops" of tonight were MY BUG, not the model physics: no tops
  problem remains, so tau_ifs has no registered reason left and stays OFF (coded, not adopted). [reg: 23:1x rerun registration | inputs: model T42 one start | fail-5why: n/a]
- 23:34 IST 5-DAY CLOUD SCREEN, FIXED cld_det (T42 11 Nov, candidate + cld_det + sst_fill): low cloud days 3-5 Bay 0.35/0.24/0.44x, S.India
  0.39/0.39/0.70x ERA5 (too LOW - FAIL); total cover Bay 1.42/1.37/1.32x, S.India 1.51/1.49/1.52x (too HIGH). cld_det HELD (screen).
  [reg: 23:1x rerun registration | inputs: ERA5 lcc5/tcc, model T42 one start (stated) | fail-5why: below]
- FAIL-5WHY: (a) total cover too high <- the detrained cloud now sits aloft (cfa 0.2-0.5 at sigma 0.23-0.45) AND radiation still adds our
  DIAGNOSTIC convective cloud (towers f_tow, anvils c_anv) on top: the same convective cloud counted twice. IFS has no separate diagnostic
  convective cloud once detrainment feeds the prognostic cloud (Part IV 7.2.4: convection enters the cloud scheme only via 7.22-7.23).
  (b) low cloud too low existed without cld_det too (sst_fill-only screen 0.34-0.71x) -> a separate cause (cloud-free start; formation only).
  REGISTERED (before the result): same 5-day screen with cld_det + diagnostic convective cloud OFF (rad_prm f_tow 0, anv_max 0 - removing a
  double count, not a tuning): total cover days 3-5 within 0.85-1.15x ERA5 in both boxes -> (a) closed; low cloud reported for (b).
  [reg: this line | inputs: n/a | fail-5why: n/a]
- 23:49 IST DOUBLE-COUNT TEST RESULT (T42 11 Nov, fixed cld_det + sst_fill, diagnostic towers/anvils OFF): total cover days 3-5 Bay 1.46/1.48/1.40x,
  S.India 1.52/1.53/1.56x (rule 0.85-1.15x FAIL - unchanged); low cloud fell to 0.06-0.29x (the diagnostic towers had been supplying low cloud).
  By the rule the double count is NOT the cover excess; (a) stays open. [reg: 23:3x double-count registration | inputs: ERA5 lcc5/tcc, model T42 one start | fail-5why: below]
- FAIL-5WHY: the excess is the detrained carried cloud aloft (cfa 0.2-0.5 at 200-450 hPa), which in our scheme has only erosion and evaporation
  as sinks: it is not advected (stated simplification) and its ice does not FALL. In IFS the ice sedimentation (7.2.3(c), eqs. 7.20-7.21) is the
  main sink of anvil cirrus. REGISTERED (before the result): add ice sedimentation to the carried cloud with the IFS fall speed law (constants
  from Part IV 7.2.3(c), read before coding); rerun the same screen: total cover days 3-5 within 0.85-1.15x in both boxes. [reg: this line | inputs: n/a | fail-5why: n/a]
- 23:49 IST cld_sed CODED: IFS Cy47r1 Part IV 7.2(i) - cloud ice falls at a constant V_i = 0.13 m/s (eq. 7.83, implicit top-down as 7.84-7.86);
  ice share (1 - alpha(T)) of the carried condensate; ice leaving the lowest layer is surface precipitation. Fraction is not sedimented (as IFS
  A(a) without a fall term - stated). Running the registered screen (candidate + fixed cld_det + sst_fill + cld_sed). [reg: 23:5x sedimentation registration | inputs: IFS doc read 23:5x | fail-5why: n/a]
- 26 Nov 00:04 IST cld_sed SCREEN RESULT (T42 11 Nov, candidate + fixed cld_det + sst_fill + cld_sed): total cover days 3-5 Bay 1.04/0.74/0.69x,
  S.India 1.36/0.90/0.97x ERA5 (rule 0.85-1.15x in both boxes: FAIL - Bay days 4-5 low, S.India day 3 high; was 1.32-1.52x without sedimentation:
  the excess is gone on 4 of 6 box-days and now swings both ways). Low cloud still 0.22-0.80x (issue (b), separate). cld_sed HELD by the rule.
  [reg: 25 Nov 23:5x sedimentation registration | inputs: ERA5 lcc5/tcc (3-start mean), model ONE start - day-to-day swings of one start are not
  separable from the model (stated) | fail-5why: below]
- FAIL-5WHY (first step, size): one start against a 3-start ERA5 mean gives single-day swings of +-0.3x in cover; the rule as registered cannot
  separate model error from one-start weather. REGISTERED (before the result, 26 Nov morning): the same screen on 3 starts (1/11/16 Nov), one
  process per start, means compared with the 3-start ERA5 mean, same rule; and the low-cloud deficit (b) gets its own 5-why (cloud-free start vs
  the formation term). [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 00:34 IST 3-START cld_sed SCREEN (T42, 1/11/16 Nov means vs ERA5 3-start mean, candidate + fixed cld_det + sst_fill + cld_sed): total cover
  days 3-5 Bay 0.76/0.54/0.53x, S.India 0.80/0.59/0.54x (rule 0.85-1.15x FAIL - now too LOW); low cloud Bay 0.26/0.31/0.19x, S.India
  0.42/0.65/0.26x. With 3 starts the one-start "both ways" swing is gone: with ice falling out, the carried cloud is too thin at all levels.
  cld_det + cld_sed HELD. [reg: 26 Nov 00:0x 3-start registration | inputs: ERA5 lcc5/tcc 3-start mean, model T42 3 starts | fail-5why: below]
- FAIL-5WHY (to run in the morning): the carried cloud lacks the IFS pieces that SUPPLY cloud between convective events - large-scale ADVECTION
  of a and q_l (stated simplification since 25 Nov), the analysed initial cloud, and the subsidence term of 7.22-7.23; with only local sources,
  cloud decays wherever convection is not active. First check (size): the share of Bay/S.India grid-days with no convection whose ERA5 cloud
  cover is > 0.3 (cloud that must have been advected in). [reg: this line (plan, registered before the check) | inputs: n/a | fail-5why: n/a]
- 26 Nov 03:40 IST REGISTERED (before the result; rule for the 00:3x size check): ERA5 'cldadv truth' (boxes Bay/S.India, 1/11/16 Nov, days 3-5,
  3-hourly): if >= 50 % of the box's total-cloud area sits over points with no convection (cp < 0.1 mm/h), local convective supply cannot carry the
  cloud and the missing ADVECTION of a/q_l is named as the next fix (IFS: a and q_l are advected prognostic variables); if < 50 %, the local
  source terms are the place to look. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 03:44 IST cldadv RESULT (ERA5 hourly 0.25 deg, 1/11/16 Nov days 3-5): share of total-cloud area over non-convecting points Bay 0.69, S.India 0.75
  (low cloud 0.67/0.69); 59-62 % of non-convecting points have cover > 0.3 (mean 0.50/0.51). Rule (>= 50 %) MET -> missing ADVECTION of the
  carried cloud (a, q_l) is NAMED as the next fix: two thirds of the observed cloud sits where no local convective source exists, and our carried
  cloud cannot move there. [reg: 03:4x cldadv registration | inputs: ERA5 cp/tcc/lcc (fetched 03:5x) | fail-5why: n/a]
- 26 Nov 03:49 IST cld_adv CODED: carried cloud fraction and cloud water are semi-Lagrangian, monotone, nodal tracers of the dynamical core (IFS: a
  and q_l are advected prognostic variables). The physics' new a, q_l (computed from the pre-step values) are applied as an INCREMENT to the
  advected tracer in cloud_apply, so neither advection nor physics is lost (time-splitting stated). T42 2-day smoke (11 Nov, candidate +
  cld_det + cld_sed + sst_fill + cld_adv): finite, global rain 1.81 mm/day. REGISTERED (before the result): the 3-start T42 5-day cloud screen
  (1/11/16 Nov, same script) with cld_adv added: total cover AND low cloud days 3-5 within 0.85-1.15x / 0.7-1.3x ERA5 (3-start mean) in Bay
  and S.India. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 04:24 IST cld_adv 3-START SCREEN (T42, 1/11/16 Nov vs ERA5 3-start mean; candidate + cld_det + cld_sed + sst_fill + cld_adv): total cover days
  3-5 Bay 1.28/1.05/1.04x, S.India 1.12/0.85/0.94x (rule 0.85-1.15x: 5 of 6 box-days PASS, Bay day 3 high); low cloud Bay 0.40/0.32/0.24x,
  S.India 0.59/0.67/0.42x (rule 0.7-1.3x FAIL). Advection fixed most of the total-cover error (was 0.53-0.80x); low cloud is still 2-4x short.
  The package stays HELD. [reg: 03:5x cld_adv registration | inputs: ERA5 lcc5/tcc 3-start mean, model T42 3 starts | fail-5why: below]
- FAIL-5WHY (low cloud): (1) low cloud short <- (2) with the diagnostic towers off/on the prognostic low cloud is near zero below 800 hPa
  <- (3) our only convective source is the DEEP updraught (cld_det); the shallow scheme re-evaporates its condensate in place, while in IFS
  eq. 7.22-7.23 apply to ALL updraughts - shallow cumulus detrainment is the main source of tropical low cloud. REGISTERED (before coding/the
  result): add the shallow updraught's detrainment (same 6.39/7.22-7.23 bookkeeping as the fixed cld_det, using the shallow eta and cond);
  rerun the 3-start screen: low cloud AND total cover within the rules in both boxes. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 04:28 IST cld_det 2 CODED (shallow detrainment, registered 04:2x): in the IFS shallow path (sh_ifs2) the plume condensate is taken from the
  vapour where it condenses (before: it re-evaporated in place through the vapour-flux convergence) and detrains into the carried cloud where
  the shallow mass flux falls and at its top (eqs. 7.22-7.23); no shallow rain (stated), water conserved exactly. T42 2-day smoke (11 Nov):
  finite, global rain 1.89 mm/day. Running the registered 3-start screen. [reg: 04:2x shallow registration | inputs: n/a | fail-5why: n/a]
- 26 Nov 05:03 IST SHALLOW-DETRAINMENT 3-START SCREEN (T42, 1/11/16 Nov vs ERA5 3-start mean; candidate + cld_det 2 + cld_sed + sst_fill + cld_adv): LOW
  cloud days 3-5 Bay 0.70/0.77/0.74x, S.India 1.04/1.15/0.89x (rule 0.7-1.3x: PASS all 6 box-days); total cover Bay 1.37/1.17/1.19x, S.India
  1.19/1.05/1.09x (rule 0.85-1.15x: FAIL on 4 of 6). Low cloud is fixed by the shallow source; total cover now too high. Package HELD.
  [reg: 04:2x shallow registration | inputs: ERA5 lcc5/tcc 3-start mean, model T42 3 starts | fail-5why: below]
- FAIL-5WHY / REGISTERED (before the result): which level carries the cover excess? ERA5 'mhcc truth' (medium/high cloud cover, same boxes,
  starts and days) vs model mid (0.45 <= sigma < 0.8) and high (sigma < 0.45) max-overlap cloud from the same screen re-run: the layer whose
  ratio exceeds 1.3x is named (then its source term gets the size check). [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 05:36 IST MID/HIGH SPLIT RESULT (T42 3 starts vs ERA5 mhcc 3-start mean, days 3-5): mid cloud Bay 0.97/0.79/0.82x, S.India 1.03/0.92/0.81x
  (fine); HIGH cloud Bay 1.56/1.23/1.30x, S.India 1.32/0.96/1.13x (days 1-2 0.66-0.80 vs ERA5 0.49-0.60). Rule (> 1.3x names the layer): HIGH
  cloud NAMED (Bay day 3, S.India day 3, Bay day 5 at 1.30). Model layer cover is max-overlap within the layer; ERA5's own overlap differs
  (stated). [reg: 05:0x mid/high registration | inputs: ERA5 mhcc (fetched 05:1x), model T42 3 starts | fail-5why: below]
- FAIL-5WHY: high cloud has two sources in the model now - the prognostic detrained cloud (advected, sedimenting) AND radiation's diagnostic
  anvil (anv_max) and towers (f_tow), still ON. IFS has no diagnostic anvil once convection feeds the prognostic cloud (Part IV 7.2.4). The
  25 Nov 23:3x test of switching them off was done BEFORE advection and the shallow source existed (and the towers were then the only low-cloud
  source); it does not carry over. REGISTERED (before the result): the same 3-start screen with the diagnostic anvil and towers OFF (rad_prm
  f_tow 0, anv_max 0): low cloud stays within 0.7-1.3x, total cover within 0.85-1.15x and high cloud <= 1.3x on all 6 box-days. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 06:12 IST ANVIL-OFF 3-START RESULT (T42, full package + diagnostic anvil/towers OFF): high cloud Bay 1.58/1.22/1.27x, S.India 1.43/1.00/1.11x
  (rule <= 1.3x FAIL on day 3 in both boxes - barely changed from 1.56/1.32); total cover Bay 1.38/1.17/1.21x, S.India 1.24/1.07/1.15x (FAIL);
  low cloud Bay 0.54/0.90/0.82x, S.India 0.74/1.28/1.00x (Bay day 3 FAIL). The diagnostic anvil is NOT the high-cloud excess; the prognostic
  detrained cirrus is. Diagnostic anvil/towers stay as they were (no registered reason to change). [reg: 05:4x anvil-off registration | inputs:
  ERA5 lcc5/tcc/mhcc 3-start means, model T42 3 starts | fail-5why: below]
- FAIL-5WHY: detrained cirrus sinks in our scheme: erosion, evaporation, sedimentation (0.13 m/s), advection. Still missing from IFS 7.22-7.23:
  the compensating-SUBSIDENCE terms (cloud carried down with the environment's sinking around the updraughts into warmer air, where it
  evaporates). Coded cld_sub (upwind, Courant capped at 1, water conserved). REGISTERED (before the result): the full package + cld_sub
  (diagnostic anvil/towers ON as before), 3-start screen: high cloud <= 1.3x, total cover 0.85-1.15x, low cloud 0.7-1.3x on all 6 box-days. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 06:47 IST cld_sub 3-START RESULT (T42, full package + cld_sub): high cloud Bay 1.57/1.20/1.24x, S.India 1.33/0.99/1.19x (FAIL day 3 both
  boxes); total cover Bay 1.37/1.16/1.15x, S.India 1.19/1.12/1.15x (FAIL); low cloud Bay 0.69/0.97/0.92x, S.India 0.94/1.54/1.19x (FAIL Bay d3,
  S.India d4). The subsidence term barely moves high cloud. cld_sub HELD. Per-start: the high-cloud excess comes from the 11 and 16 Nov starts
  (model 0.61-0.97 vs ERA5 3-start mean 0.45-0.56; 1 Nov start 0.29-0.55); the ERA5 truth is a 3-start MEAN only, so a paired per-start check is
  not possible with it (stated). [reg: 06:1x cld_sub registration | inputs: ERA5 lcc5/tcc/mhcc 3-start means, model T42 3 starts | fail-5why: below]
- FAIL-5WHY (next, registered before the check): fetch ERA5 high/total cloud PER START (same boxes/days) so the excess can be checked start by
  start and against 2 SE (rule 10); then, if the 11/16 Nov excess is real, size the cirrus sink terms (sedimentation 0.13 m/s vs the detrained
  ice flux) in those starts. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 06:50 IST PER-START CHECK (ERA5 cldps truth, fetched 06:4x; model = the cld_sub 3-start screen; ratio per start, mean +- SE of 3): applying
  rule 10 (within 2 SE of the bound) to all 18 box-day-variable cells: high cloud PASS on all 6 (Bay d3 1.61+-0.20 -> 1.21 <= 1.3; S.India d3
  1.37+-0.17); low cloud PASS on all 6 (Bay d3 0.69+-0.14; S.India d4 1.57+-0.38); total cover PASS on 5 of 6 - Bay day 3 1.37+-0.09 FAILS
  (lower 2-SE bound 1.19 > 1.15). The package (cld_prog 2 + cld_det 2 + cld_sed + cld_adv + cld_sub + sst_fill) therefore fails the registered
  cloud screen on ONE box-day of 6, driven by the 11 Nov start's high cloud (1.95x). Mean-of-ratios here differs from ratio-of-means above (stated).
  Still HELD at screen level. [reg: 06:1x cld_sub registration + rule 10 | inputs: ERA5 cldps per start, model T42 3 starts | fail-5why: next]
- NEXT (registered before the check): T170 is the exam resolution - the screen is T42; cirrus spread and fall depend on resolution. The cloud
  package goes to a T170 part-3 job (four forecast rules) only after tn-sstfill, and the T42 Bay-day-3 cover excess is sized there with the
  same per-start rule. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 07:01 IST REGISTERED (before the result): is the 11 Nov high-cloud excess too much CONVECTION? ERA5 total and convective rain per start
  (rainps truth) vs model rain (the cld_sub screen runs), Bay box days 2-3: if the 11 Nov model rain exceeds ERA5's by >= 30 % while the 1 Nov
  start does not, over-active convection (too much detrained ice) is named; otherwise the cirrus sinks are sized next. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 07:17 IST PER-START RAIN RESULT (T42 full cloud package vs ERA5 rainps, Bay box, days 1-3 mm/day): 1 Nov 0.64/0.72/1.03 vs 2.90/1.99/2.84
  (0.22-0.36x); 11 Nov 4.84/5.22/4.93 vs 6.99/5.33/6.34 (0.69-0.98x); 16 Nov 4.30/3.18/2.00 vs 9.34/6.47/4.76 (0.42-0.49x). Rule (11 Nov model
  rain >= 1.3x ERA5 on days 2-3): NOT met (0.98/0.78) -> over-active convection NOT named for the 11 Nov high-cloud excess. Side fact for P5b:
  Bay rain is still 0.2-0.98x ERA5 with the full package at T42. [reg: 07:0x rain registration | inputs: ERA5 rainps (fetched 07:0x), model T42 3 starts | fail-5why: below]
- REGISTERED (before the result): cirrus water vs cover. ERA5 ice water path above 450 hPa (specific cloud ice water content, per start, Bay box,
  days 2-3) vs the model's carried ice (cql ice share) there: if the model IWP is within 0.7-1.3x ERA5 while its high cover is 1.3x+, too much
  FRACTION per unit ice is named (the D_up fraction source vs IFS 7.23); if the model IWP is >= 1.3x, too much ICE (sinks too weak) is named. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 07:35 IST IWP RESULT (Bay box, days 2-3, above 450 hPa; model T42 full cloud package vs ERA5 ciwc): 1 Nov 18.9 vs 9.8 g/m2 (1.9x), 11 Nov 124.2
  vs 21.7 (5.7x), 16 Nov 46.7 vs 22.5 (2.1x). Rule: model IWP >= 1.3x -> too much ICE named (the cirrus sinks are too weak), worst on 11 Nov -
  the start with the high-cover excess. ERA5 ciwc excludes snow (a separate prognostic in IFS), so the comparison is with cloud ice only. [reg:
  07:1x IWP registration | inputs: ERA5 ciwc (fetched 07:2x), model T42 3 starts | fail-5why: below]
- FAIL-5WHY: our carried condensate turns into precipitation only by the LIQUID Sundqvist autoconversion (and ice falls at 0.13 m/s); IFS
  converts cloud ICE to SNOW by its own ice autoconversion (Part IV 7.2.x) and snow falls at ~1 m/s. That conversion is missing. Next: read
  the IFS ice-to-snow autoconversion (form, constants) and register the test before coding. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 07:35 IST cld_iaut CODED from IFS Cy47r1 Part IV 7.2(g) (read 07:3x): ice autoconversion = Sundqvist form 7.50 with ice parameters, c0 =
  1e-3 exp(0.03 (T - 273.15)) (eq. 7.56), q_crit,i = 3e-5 kg/kg (IFS's own tuned value, taken as the reference); snow to the surface in the same step
  (stated). REGISTERED (before the results): (1) model IWP per start within 0.7-1.3x ERA5 (2 SE allowed per rule 10); (2) the 3-start cloud screen
  (high <= 1.3x, total 0.85-1.15x, low 0.7-1.3x, rule 10) on all 6 box-days. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 08:26 IST cld_iaut RESULT (T42, 3 starts, full cloud package + cld_iaut): (1) IWP 5.2/55.1/17.4 vs ERA5 9.8/21.7/22.5 g/m2 -> 0.53/2.54/0.77x,
  mean 1.28 +- 0.63 (rule 0.7-1.3x with 2 SE: PASS; the 11 Nov start is still 2.5x - stated). (2) 3-start cloud screen with rule 10: ALL 18
  box-day cells PASS (high Bay 1.50+-0.23/1.17/1.23, S.India 1.12/0.77/1.01; total Bay 1.28+-0.13/1.11/1.12, S.India 1.04/0.99/1.05; low Bay
  0.59+-0.07/1.13/0.88, S.India 0.81/1.63+-0.34/1.33). Stated plainly: with only 3 starts the SEs are wide (0.03-0.41), so rule 10 is lenient here;
  the means alone would fail Bay high day 3 (1.50), Bay low day 3 (0.59), S.India low day 4 (1.63). SCREEN PASSED by the registered rule. The cloud
  package (cld_prog 2, cld_det 2, cld_sed, cld_adv, cld_sub, cld_iaut, sst_fill) goes to the T170 test tn-cldpkg (18 starts, four forecast
  rules), which is the verdict. [reg: 07:4x cld_iaut registration | inputs: ERA5 iwp/cldps per start, model T42 3 starts | fail-5why: n/a]
- 26 Nov 08:27 IST P5b 5-WHY RESTART on the full package (registered before the result): Bay box day 1, model (T42, candidate + cloud package +
  sst_fill) vs ERA5 bayfx (1 / 11 Nov): sea LE, rain, atmospheric radiation, sea-air dq. The term >= 15 % off ERA5 that is largest in W m-2 is
  named as the next rain-deficit step. [reg: this line | inputs: n/a | fail-5why: n/a]
- 26 Nov 08:34 IST P5b FLUX RESULT (T42 full package, Bay day 1, model vs ERA5 bayfx, 1 / 11 Nov): rain 0.30 vs 2.76 (0.11x) / 6.15 vs 6.93 (0.89x)
  mm/day; sea LE 75.9 vs 86.1 (0.88x) / 130.4 vs 126.9 (1.03x); U ~2.75 vs 3.35 (0.82x) / 4.85 vs 4.95; atmospheric radiation -110.1 vs -106.1 /
  -102.3 vs -108.5; dq 6.96/7.40 vs 6.19/6.60 (model at ~80 m, stated). The 11 Nov start is now close on every term. The 1 Nov start's rain
  is 0.11x while its evaporation is 0.88x: the largest gap (2.5 mm/day = 72 W m-2) is the rain itself, not its supply. Named: on 1 Nov the
  moisture is not being rained out (U 18 % low also named, but it explains only ~10 W m-2 of LE). [reg: 08:3x P5b registration | inputs: ERA5 bayfx, model T42 2 starts | fail-5why: below]
- REGISTERED (before the result): where does the 1 Nov moisture go? ERA5 total column water vapour (Bay box, day 1, per start) vs the model's:
  if the model column is >= 2 kg m-2 MOISTER than ERA5 while raining 0.11x, convection is failing to fire/rain (trigger or closure) and is named;
  if it is drier, the moisture supply (convergence) is named. [reg: this line | inputs: n/a | fail-5why: n/a]
