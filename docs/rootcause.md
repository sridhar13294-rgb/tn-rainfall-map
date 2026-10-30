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
