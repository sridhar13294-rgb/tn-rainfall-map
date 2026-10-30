# Handoff (read this first in a new chat)

## WHY this project exists (Sridhar's intent - read before anything else)
- Sridhar and his brother Adhitya run a Tamil Nadu rainfall website (TNSDMA TN SMART gauges + IMD; forecasts from GFS/ECMWF/ICON/GEM/ECMWF-AI, an ensemble outlook, a cyclone tab - now hidden). Adhitya is the main part of the idea.
- They want THEIR OWN professional weather model, built from scratch on free hardware, "as close to ECMWF as possible", so the site no longer depends only on other centres. Sridhar: "I believe in you. We together can build the professional model and its product as close as possible to ECMWF and GFS."
- It must be a GENERAL daily model used 365 days ("Don't call it a cyclone model... it should behave like how GFS/ECMWF works daily"): runs 00Z/12Z, 10-day main run + 51-member 15-day ensemble, and must perform in the Bay of Bengal, Arabian Sea and South Indian Ocean - not only the Bay. Products (rain maps, cyclone tracks/scenarios incl. several systems at once, outlooks) come after the model is good.
- Order he set: Stage 1 = 11 fixes (grid, speed, convection, stability, clouds/radiation, ocean, start data, ensemble spread, multi-system tracker, rain, track skill vs ECMWF) -> Stage 2 = 3-D ocean (currents/upwelling, then Veros) -> Stage 3 = India in detail (9 km all India + 3 km windows). He also approved starting Stage 2 and LETKF data assimilation in parallel ("both one after other").
- Start data: "add as much as possible" (more centres, observations, land states) so the model depends less on other centres' analyses.
- Convection: "if the new scheme is not working, correct the equation until it works, don't go back to the old scheme."
- He wants honest, plain-language reports, fact-checking and pushback, no hype; he works from a phone. He was unhappy when earlier "website method" forecasts were unrealistic - realism matters more than pretty output.
- He stopped the old 6-hourly ensembles and the ECMWF/GFS watch; keep only the daily 10:30 IST rain skill check and the site's TN SMART update. Nothing goes live on the website without his explicit "go live".
- He is funding this with free tools: up to 8 Kaggle accounts (each a different real person with own phone), GitHub Actions, his Claude weekly usage (wants it used fully before Mon 26 Oct 22:29 IST, but without hitting the 5-hour limit: lean cycles).
- Target dates given to him: Stage 1 complete (built, tested, scored - not "equal to ECMWF") ~28 Oct, fallback 30 Oct; to be confirmed to him on 24 Oct evening. Stage 2 ~20 Nov, Stage 3 early Dec, LETKF Dec-Jan (Stage 2 and LETKF already started early).
- MODEL NAME (decided 24 Oct 2026): MEGAM - Multi-scale Engine for Global Atmospheric Modelling (Tamil 'megam' = cloud).

## How we got here (short history)
- 22 Oct: moved from a "past-storm analog" method (gave unrealistic jumps) to our own multi-level spectral model (Dinosaur/JAX), tested on 84 past Bay storms, then 1000 Indian Ocean storms 1980-2025, a storm-forming test and a 2020 general-weather exam scored the same way as ECMWF.
- 23 Oct: found and fixed real bugs (terrain-pressure start, shallow-cloud heat creation, rain spin-up), ruled out others by tests (radiation, coupling, dynamics core), repaired the mass-flux convection (best general forecast so far) and hit the key trade-off: realistic physics forms few storms on the 140 km grid. Stage 2 ocean built; LETKF started; TPU needs Kaggle identity verification (only account 1 verified).


## Who / rules
- Sridhar (phone only, plain words, honest pushback). Brother Adhitya co-runs the site. Model name: MEGAM - Multi-scale Engine for Global Atmospheric Modelling (decided 24 Oct).
- Repo sridhar13294-rgb/tn-rainfall-map, work branch `cases`. `main` (the website) only with Sridhar's explicit "go live".
- Secrets only in GitHub secrets (ECMWF_DS_KEY/CDS_KEY, KAGGLE_*, KAGGLE2_..KAGGLE8_*). Never print/commit them. One Kaggle account per real person.
- Messages: NONE between 00:30 and 07:00 IST. Daytime: one short status every 3 h. Daily rain skill check at 10:30 IST (scratchpad/dailyNN scripts; see the skill-check routine text in the old chat / docs/cyclone_model_status.md).
- Convection: never fall back to the old scheme as the answer; keep repairing the mass-flux scheme (old BMJ = yardstick).
- Live doc: https://claude.ai/artifact/GttzHBxsJbyAh9HSW1NcFi (change-log table, newest rows on top). Update on decisions.
- Usage: Sridhar's weekly limit resets Mon 26 Oct 22:29 IST; 5-hour session limit applies. Keep each cycle lean (see "How to run cheaply").

## Schedules (set 23 Oct 21:15 IST)
- Scheduled tasks: 'MEGAM work cycle' (every 2 h) and 'Daily rain skill check' (10:30 IST). Each run starts a fresh session and clones `cases`.
- Last status sent: 23 Oct 21:08 IST (old chat); next status due 07:00 IST (quiet 00:30-07:00).
- 23 Oct 22:30 IST: Stage 1 jobs still running (tn-gen-t170a/b, tn-gen-full-mf8, tn-wx-ice05, tn-tpu-wx, tn-io-si5 acct6). tn-io-as2 failed (release download reset) -> kernel.py now retries downloads + checks npz; rerun as tn-io-as3 (acct4). Next cycle: collect all, then decide default convection.
- Stage 2 in parallel (Sridhar 22:10: start it, Stage 1 stays priority): tn-oc-jaxspin on acct7 (2nd job beside LETKF tn-da-osse2) = scripts/ocean3d/test_jax_gpu.py (numpy vs jax.jit, speed, global 30 d) then veros_spin.py (Veros 2 deg ERA5 spin-up 2017-01 -> 2019-05, monthly drift, state saved as Kaggle output veros_state_20190515.npz, monsoon-2019 score vs old 0.87/0.84). Other Stage 2 items still open: coastal upwelling band, RTOFS currents, momentum advection/throughflow/rivers, weak cold wake, Veros nudging/ensembles/TPU, then coupling (needs Stage 1 settled).

## Goal
General daily global model like ECMWF/GFS (00/12Z, 10-day + 51-member 15-day), good in Bay of Bengal, Arabian Sea, South Indian Ocean. Stage 1 = 11 fixes (target ~28 Oct, fallback 30 Oct). Stage 2 = 3-D ocean (built). LETKF data assimilation (in progress). Stage 3 = India detail (9 km + 3 km windows).

## Kaggle (job launcher)
- Write data/cyclone/KAGGLE (line1 slug, line2 release files, line3 command run in repo/scripts/cyclone/mm, line4 accelerator NvidiaTeslaT4 or TpuV5E8, line5 account 1-8, line6 #comment) and push to `cases`; results return to data/cyclone/kaggle/<slug>/ (status.txt, *.json, kernel_*.log). Workflow refuses unconfigured slots.
- Accounts: slot 6 was a second account of Sridhar himself (retired 24 Oct morning); on 24 Oct 11:50 IST Sridhar replaced it with a NEW PERSON's own phone-verified account - slot 6 is usable again (first job ran fine). Stage 1 uses 1-6, 8, 9 and 10 (slot 9 added 24 Oct 12:26 IST, slot 10 at 12:59 IST; KAGGLE9_*/KAGGLE10_* secrets); account 7 = helper agents (LETKF now). GPU ~30 h/week each.
- TPU: DROPPED by Sridhar (23 Oct 22:43) - do not use TPU; GPU T4 only.
- Result watcher: scratchpad/watch.sh (background) - optional; it costs a turn per wake.

## Stage 1 state (details: scratchpad/cycle_state.json notes in old session; summary here)
- Fixed: terrain-pressure start bug; ECMWF-style output (mslp, t2, below-ground t850); new radiation (radcloud) default; shallow-convection heat bug (mixes moist static energy now); defaults rh_deep 0.8, ck 1.2e-3, sh_top 0.7, tau_shallow 3 h (for the old scheme), bmj_ice 0 (option), mf_ice 0 (option), ck_z 0 (option, height-corrected sea exchange), ensemble bv_amp 2.2, SPPT x2.4 (live2.member).
- Energy: dynamics core fine (-0.05 K/day). Cold upper troposphere comes from convection physics (no freezing heat; spin-up). Freezing heat in old scheme: upper air better but column colder, storms form far less.
- Mass-flux (new scheme) repaired: shallow mixing was ruining its boundary layer. Best general exam: conv=mf, mf_kick_t 0.5, mf_kick_q 0.0005, mf_dd 0.5, tau_shallow 1e12 (shallow off): z500 RMSE d1/5/10 = 22.7/72.6/115.9 m (ECMWF 4.8/31/83), smallest tropical drift. BUT storm forming at T85 only 2% (old scheme 40%).
- Best Bay tracks (84 storms, T85): old scheme + bmj_ice 0.5: 92/211/351/567 km (24-96 h).
- Running at handoff: tn-gen-t170a (acct3, T170 storm forming old scheme, ice 0.5 vs 0), tn-gen-t170b (acct8, T170 mass-flux shallow off vs slow shallow), tn-gen-full-mf8 (acct2), tn-wx-ice05 (acct5), tn-tpu-wx (acct1 TPU), acct6 older jobs. DECISION PENDING on these: if mass-flux forms storms at T170 -> make it default (plus Stage 3 finer grids for cyclones).
- Remaining Stage 1 items: settle default physics; rain check vs TN SMART (#10); observations into the start (#7, nudge.py OI + LHN design); ensemble check with final settings (#8); multi-system tracker test (#9); ocean on/off (#6, apply scripts/ocean3d/MM2_HOOK.md with ocean3d='rgo'); final exam 2018-2025 + final ECMWF scoring (#11).

## Tools / scripts (scripts/cyclone/mm)
- wx2.py + score_wx.py (73-start 2020 exam vs ECMWF HRES in data/cyclone/wx/hres_2020_scores.json); wx_prof.py (5-day tropical T/q profile bias + energy budget; 4th arg JSON dict of named settings, "_split": true option); wx_energy.py, wx_step.py, wx_tend.py (diagnostics); hind2.py + score_hind.py (Bay storms); genesis2.py (storm forming; count formed = dist<=300 km, vo>=5, depth>=2 hPa); hindens2.py + score_ens2.py (ensemble).
- Configs in data/cyclone/kaggle_cfg/.

## Stage 2 (ocean) - built
scripts/ocean3d/ (currents.py, rgo.py reduced-gravity JAX ocean, veros_coupled.py), docs/stage2_ocean.md, MM2_HOOK.md. 2019 monsoon test: Somali/Oman coastal cooling close to ERA5. Veros 2 deg ~10 s/model-day on T4. Not yet coupled into mm2.

## LETKF - in progress (helper agent in old chat, account 7)
Work in scripts/da/ (worktree /home/claude/wt-da), docs/letkf.md. If the agent is gone, continue from the files.

## How to run cheaply (5-hour limit)
- Work cycles every 2 h (not hourly), no background watcher, batch all checks in one cycle.
- Short notes, short statuses; read only result summaries (grep the "tropics mean d5" / score lines), not whole logs.
- One helper agent at a time.
- Medium effort.
- Start a fresh chat every day or two (long chats make every message cost more).

## Daily rain skill check (10:30 IST, Sridhar wants it every day)
Copies of the scripts are in scripts/daily_check/ (skill23.py, hg23.py, verify_hg.py). They expect a checkout of origin/main
(run from inside it) and the sat-radar branch for satellite rain; edit dates and the paths at the top (they point to the old
chat's scratchpad). 23 Oct result: state obs 19.2 mm vs our v4 18.2 (closest); lead-1 MAE ICON 13.5, v4 14.3; heavy rain still
weak (v4 caught 19 of 67 squares >= 20 mm); the ensemble week outlook looked too dry (6.4 mm vs normal 51.7, five models 49.7).
The message lists per-model MAE, bias ratio, POD, FAR, ETS, heavy hit/miss/false for lead 1 and 2, for the day and all days;
state average obs vs forecast; odd gauges (Aliyar misplaced, fix awaiting approval); outlook vs fallen; downloads status
(data/forecast_status.json). Corrections only on a new branch with Sridhar's approval.


## 27 Oct 00:55 IST - HEAT BUDGET by process (tn-budget-def / -noshal, tropics day 5, K/day)
DEFAULT: shallow (mse mixing) heats the lowest 200 hPa by +8..+12 K/day and cools 400-450 hPa by -2; rain evaporation cools the lowest 200 hPa by -6..-7 (real ~-1..-2); large-scale condensation heats 400-450 hPa by +3.7 (bigger than deep convection +1.5); radiation ~-1.2 mid, -0.6 at 150 hPa. => a spurious loop: shallow mixing lifts moisture -> mid-level grid-scale saturation -> large-scale rain -> evaporates in the boundary layer -> shallow mixing brings heat down again. Deep convection is starved. The -0.5 K/day at sigma 0.15 is mostly radiation (normal), not a bug.
SHALLOW OFF: deep convection heating rises to +3..+4.6 but peaks LOW (sigma 0.8-0.9; real Q1 peaks ~400-500 hPa) -> deep plumes detrain too low; evaporation -2, lsc smaller; low levels then -2 K cold.
Equation targets: (1) shallow scheme must be a non-raining mass-flux plume (shallow='mf' looked inactive - checking h_shal in tn-budget-shmf), (2) deep plume heating profile too low (entrainment/detrainment) - tn-budget-org tests organised entrainment with shallow off; (3) rain evaporation formula has no precipitation-area fraction.

## 26 Oct 23:00 IST - MOSDAC ready (Sridhar added MOSDAC_USER/MOSDAC_PASSWORD)
Login from GitHub Actions WORKS (obs_probe2.py: token OK via https://mosdac.gov.in/download_api/gettoken). mdapi endpoints: apios/datasets.json (search), download_api/download, refresh-token, logout; mdapi.py source saved in data/cyclone/mosdac_mdapi_src.txt. Next: find INSAT-3D/3DR/3DS atmospheric motion vector (AMV, cloud-drift winds) and rain product IDs (e.g. 3DIMG_L2B_*/3SIMG_*; catalog https://mosdac.gov.in/catalog-app/satellite.php), add mosdac_amv() to obs_fetch.py (wind obs type 'amv', errors ~3-5 m/s, upper levels), then use in #7 trials. Licence: MOSDAC/ISRO terms - check before any commercial use. Revised stage dates given to Sridhar: Stage 1 2 Nov (latest 4 Nov), Stage 2 13 Nov (16 Nov), Stage 3 10 Dec (20 Dec).

## 26 Oct 22:45 IST - high shallow cap (600/500 hPa) + ck_z: NOT adopted
Genesis (tn-gen-top60): default 21%, top60 15%, top50 23%, top60ck 25%. Column rms: top50 2.86, top60ck 3.21 (default 3.09). Shear: top50 6.9/4.4/5.3, top60ck 4.4/3.3/4.7 (default 6.0/4.2/5.4). Same-run exams (default/top60ck/top50ck): z500 globe d5 74.6/78.3/78.2, tropics d5 34.3/43.3/43.0 (ck_z drift); tracks 96 h Bay 558/562/564, AS 476/486/527, SI 412/406/437 (all within noise). => no combination beats the default overall yet; less shear did not improve tracks, so the shear bias is not the main track-error driver. ck_z keeps cooling the tropical column. #7 trial tn-obs-2026102500 done (score next). Credit-limit period (Sridhar) until 26 Oct 23:00 IST; the session was idle ~29 h (cycle of 25 Oct 17:00 stopped after launching jobs; 26 Oct 10:30 rain check missed).

## 25 Oct 11:55 IST - boundary-layer fix results; Sridhar: viewer paused, focus Stage 1
pbl_tm=1 alone: column rms 2.92 K (default 3.09), shear 7.2/4.7/6.2 (worse), genesis 20% (default 23%), Bay tracks ~same (96 h 433 vs 561 median, noisy). tmtap (pbl_tm + org1 + sh_top 0.80 + taper 0.15): column 1.93 K (best yet) but genesis 6%, shear 8.4/5.0/5.6. => every cut of shallow mixing above ~800 hPa kills genesis: our storms rely on it for mid-level moistening (congestus role). Testing a high cap: sh_top 0.60 / 0.50 (+ck_z): tn-gen-top60 (acct8, gatekeeper), tn-prof-top60 (9), tn-wind-top60 (10). Map viewer v3 (soundings) published; Sridhar 11:44: focus on Stage 1, viewer later.

## 25 Oct 10:50 IST - capped shallow REJECTED; boundary-layer equation bug found
Same-run exams (default / top80 = org1+sh_top0.80 / top80ck = +ck_z): z500 globe d5 74.6/74.2/77.5, d10 119/116.8/119.9; tropics z500 d10 45.4/37.9/52.8; t850 India d1 2.5/3.2/3.2 (worse); rain24 India d5 11.0/10.0/9.9 (better); Bay tracks 96 h 501/679/679 km (MUCH worse, lon bias -1.8/-3.2/-2.7); AS mixed; SI ~same; storm forming 20%/8%/11% (collapse). Taper (sh_taper 0.15): column rms 2.16 K but shear 7.0/4.0/4.4 (no gain). => cutting shallow mixing removes needed boundary-layer mixing.
ROOT CAUSE candidate: K-profile boundary layer had ws = cbrt(u*^3 + 0.6 kappa w*^3 x 0.1) (~12x too small vs Troen-Mahrt 7 eps kappa = 0.28), w* used a fixed 1000 m, no counter-gradient term -> daytime BL mixing ~2.3x too weak, shallow scheme was doing BL work. New option pbl_tm=1 (Troen-Mahrt/Hong-Pan: correct ws, w* from hbl, counter-gradient gamma = 6.5 flux/(ws h) for theta and q). Tests: tn-prof-tm (acct9), tn-wind-tm (10), tn-gen-tm (8), tn-base-tm (2); variants tm (pbl_tm only) and tmtap (pbl_tm + org1 + sh_top 0.80 + sh_taper 0.15).
#7: fetching centres + obs for 2026102500 -> launch tn-obs-2026102500 next cycle.

## 25 Oct 08:40 IST - capped shallow mixing = best column so far
Tropics day-5 T/q rms over 200-1000 hPa: default 3.09 K / 1.17 g/kg; ckz1 3.66/1.38; top85 2.65/0.47; top75 2.69/0.79; top80 (ck_z+org1+sh_top 0.80) 2.68/0.68; top80noz (org1+sh_top 0.80) 2.11/0.68 (BEST). Remaining: cold/moist 850 hPa (-3.2 K, +1.6 g/kg) right at the hard top. Shear (Bay/AS/SI): top80 4.3/3.2/3.8; top80noz 5.9/3.9/2.9 (default 6.0/4.2/5.4; ckz1 2.5/2.5/3.7).
Same-run exams launched (variants default / top80 = org1+sh_top0.80 / top80ck = +ck_z): tn-wx-top80 (acct1), tn-base-top80 (2), tn-io-as-top80 (3), tn-io-si-top80 (4), tn-gen-top80 (8).
New mm2 option sh_taper (DYN): shallow mixing fades linearly over sh_taper sigma above sh_top, tendencies re-centred (conserving); default 0 = unchanged. Tests tn-prof-taper (acct9), tn-wind-taper (acct10): tap = org1+sh_top0.80+sh_taper0.15, tapck = +ck_z.
Morning status sent 08:30 IST.

## 25 Oct 05:30 IST - night cycle 3
shallow='mf' plume ~= shallow OFF (identical profile): upper cold much smaller (250/300/500 hPa -3.3/-2.7/-0.3 K vs -5.2/-4.7/-2.3) but low levels now too COLD (850/925/1000 -2.9/-2.9/-2.5) and 850 hPa too moist (+0.7 g/kg); shear: shmf 4.7/3.7/3.8 (worse than ckz1 2.5/2.5/3.7), shmf_noz 6.4/4.1/3.0. => old shallow mixing did needed boundary-layer work but harmful work aloft. Now testing shallow 'mse' mixing capped at the top of the boundary-layer cloud: tn-prof-shtop (sh_top 0.85 / 0.75), tn-prof-shtop2 (0.80 with/without ck_z), tn-wind-shtop (0.80+ck_z+org1), tn-wind-shtop2 (0.80, no ck_z). History note: sh_top 0.7 was in the old yardstick; uncapped was chosen 24 Oct for the mf boundary layer - recheck with all fixes together.
#7: tn-obs-2026102412b (acct5, obs refetched with GTS) and tn-obs-2026102418 (acct6) running, 3 versions each.

## 25 Oct 03:45 IST - #7 details
OI now uses winds: with obs_2026102412 (ASCAT) solved u,v 669 superobs (scat O-B 1.2 -> O-A 0.9 m/s). Land 10-m winds off by design (as ECMWF). Surface pressure obs have a steady -2 hPa (METAR) / -1 hPa (SYNOP) O-B offset vs the centre consensus (same for MSLP or station pressure) -> new nudge cfg debias_p=True (removes each type's median pressure O-B; tested: METAR mean O-B -2.1 -> -0.65 hPa). obs_trial.py now runs 3 versions: noobs, obs, obsdb (bias-corrected). Refetched obs 2026102412 (GTS fixed) and centres 2026102418: launch tn-obs-2026102412b (new obs) and tn-obs-2026102418 next cycle.

## 25 Oct 03:15 IST - night cycle 2
Heating: switch-off tests (all ck_z+org1, day-5 tropics T bias 250/300/500/700/925 hPa): org1 -5.2/-4.7/-2.3/-3.0/+1.3; noevap -6.7/-6.4/-4.0/-0.1/+4.6; NOSHAL -3.3/-2.7/-0.3/-1.2/-3.1; nodeep -5.8/-5.5/-3.2/-3.3/+0.8; nodd -5.8/-5.3/-2.9/-3.0/+1.9. => the SHALLOW scheme is the main culprit: relaxing h and q to layer means also mixes dry static energy down-gradient (warms low levels, cools 300-700 hPa) and steals instability from deep convection. Equation fix added: mm2 shallow='mf' = shallow cumulus as a non-raining mass-flux plume (conv_mf(shallow=True): clouds <250 hPa deep, source sigma>0.8, closure over tau_shallow, condensate re-evaporates in place, no downdraft). Tests: tn-prof-shmf (acct3: with/without ck_z), tn-prof-shmf2 (acct4: tau_shallow 7200), tn-wind-shmf (acct9), tn-wind-shmfnz (acct10). A ~-1 K/day physics cooling at sigma 0.15-0.19 remains in ALL variants (not evap/deep/dd/shallow) - check vertical diffusion / top-level damping / q clipping next.
#7 first score (n=2 starts day 1, n=1 day 2; vs GFS analysis): with OI slightly WORSE day 1 (z500 +9-10%, v850 +10-12%), mixed day 2. Too few starts to judge; suspects: univariate ps/T/q increments without wind balance, early trials had no GTS/ships. Keep collecting (later obs files have 115k obs incl. ships+ASCAT winds - but OI solved u,v = 0 so far: check why wind obs are not used (QC 'monitor'?)).

## 25 Oct 01:00 IST - night cycle
Heating: organised entrainment (mf_org 1/2, +mf_ice, +entr3e-4) helps only ~0.5 K at 200-300 hPa; physics heating still NEGATIVE ~-1 K/day at sigma 0.15-0.23 = the size of the cold drift. Shear with org1: 2.6/2.3/4.2 (ckz1 alone 2.5/2.5/3.7) - no gain. Finding the cooling process: tn-prof-sw1 (acct3: k_evap 0 / shallow off), tn-prof-sw2 (acct4: deep off / downdraft off), all with ck_z+org1. Suspect: rain evaporation e = k_evap (1-RH) sqrt(P) m with no precipitation-area fraction -> rain made high in the plume evaporates in the dry upper air (ECMWF scales by precip fraction). 
#7: trials launched tn-obs-2026102412 (acct5), -2026102400 (acct6), -2026102312 (acct8).
FIXED obs bug: NOAA GTS files renamed sn.NNNN.txt -> global synop/ship/temp were silently 0. obs_2026102418: 114,682 records (ships 19,892, temp 188, synop 6,534) vs 48k before. obs_fetch forces IPv4. NASA IMERG download still times out at TLS handshake (listing works) - next.

## 24 Oct 22:40 IST - tropical heating cause (tn-prof-ckz, 20 starts, day 5)
Tropics T bias: 200-300 hPa -4.2..-4.7 K (ck_z -5.2..-5.7), 400-700 -2..-3, 925-1000 +1.7..+2.3; q: 500-700 hPa +0.6..+1.8 g/kg too moist, 925-1000 -2 g/kg too dry. Physics heating peaks at sigma 0.34 (+2 K/day), NEGATIVE above sigma 0.25. => plumes die too low (entrainment constant with height, mf_org=0). Equation fix under test: ECMWF organised entrainment eps x (qsat/qsat_src)^(3 mf_org) (Bechtold 2008), + freezing heat mf_ice. Running (all with ck_z=1): tn-prof-org (acct3: org1, org1+ice), tn-prof-org2 (acct4: org1+entr3e-4, org2), tn-wind-org (acct5), tn-wind-org1ice (acct6). If upper cold bias and shear both shrink -> same-run exams (wx2, Bay/AS/SI tracks, genesis) as for ck_z.
#7 trial: tn-obs-2026102212 done (trial npz in release model-maps). Fetching centres 2412 and obs 2400, 2312 for more trial starts (centres exist for 2300, 2312, 2400, 2406).

## 24 Oct 22:15 IST - new data accounts (Sridhar added GitHub secrets EUMETSAT_KEY/SECRET, EARTHDATA_USER/PASSWORD; MOSDAC_USER/PASSWORD pending ISRO approval)
cyclone.yml fetch job now gets these secrets as env. obs_probe2.py (RUN word probe2) tests them. EUMETSAT: token OK; ASCAT 12.5 km coastal winds EO:EUM:DAT:METOP:OSI-104 now in obs_fetch.scat_eumetsat (first; KNMI shared key fallback): obs_2026102412 got 5,397 scat superobs (was 0). Meteosat IODC AMVs not found in the Data Store (collections list data/cyclone/eumetsat_collections.txt) - maybe EUMETCast only. NASA Earthdata: IMERG Early listing works (24 files), download timed out (IPv4 forced; retry with longer timeout) -> then replace PERSIANN with IMERG in obs_fetch rain and use for #10. Known bug: NOAA tgftp GTS files download as 0 MB (no global synop/ship/temp) - fix next.

## 24 Oct 21:00 IST - Sridhar: 30 Oct OK, BUT steering + tropical heating must also be fixed in Stage 1. Fix #7 started.
Fix #7 (observations into start): nudge.py OI already written + wired helper analyse_consensus(); never tested in forecasts. Tested on CPU with 22 Oct 12Z: 7 centres used, 38k obs -> 1285 superobs; MSLP O-B rms 3.0 -> O-A 1.0 hPa; increments in T, q, ps only (no wind obs pass QC yet). Live trial: obs_trial.py run (Kaggle: consensus start with/without OI, 5-day run_wx daily fields -> npz uploaded to release model-maps) and obs_trial.py score (vs later live_GFSM analyses). EVERY 00Z/12Z from now (cycle ~3.5 h after): push RUN "oursm" (line 2 empty=latest) then RUN "obs", then launch tn-obs-<run> on an idle account (FILES = live_<GFSM,ECM,ICON,CMC,ARPEGE,UKMO,GEOS>_<run>.npz,obs_<run>.npz). ours_fetch_m.py now takes a past run (RUN line 2). Past analyses 23 00Z/12Z, 24 00Z fetched for verification. First trial tn-obs-2026102212 (acct2). Score when >=4 starts have day-1..3 analyses.

## 24 Oct 20:20 IST - ck_z=1 same-run results: MIXED, not adopted yet
Exam z500 globe d1/5/10: default 23.7/74.6/119 vs ckz1 24.7/77.5/122.9 (+2.9 m d5); tropics z500 d5 34.3 -> 40.6 (column drifts); mslp, u850 India, rain24 India slightly better. Storm forming (dist<=300, vo>=5, depth>=2): 26% -> 32%. Tracks median 24/48/72/96: Bay 102/213/377/509 -> 116/243/366/521; AS 139/231/417/473 -> 139/229/432/575 (lon bias +1.1 -> +1.7); SI 113/206/320/429 -> 107/182/308/417. Reading: less sea evaporation fixes the wind shear but removes heating that was hiding the old cold-upper-troposphere error, so tropical heights fall. Next: tn-prof-ckz (acct1, wx_prof day-5 T/q profile) to find where the column cools; the real fix is the tropical heat balance (convective heating profile / radiation), then ck_z on top.
Stage 1 verdict given to Sridhar 24 Oct evening: 28 Oct does NOT hold; target 30 Oct with the steering/heat-balance item possibly carried as a documented open weakness.

## 24 Oct 18:15 IST - steering fix candidate: ck_z=1 (sea evaporation coefficient taken from 10 m down to the model's lowest level)
wx_wind day-5 shear error (u200-u850, m/s) Bay/AS/SI: default 6.0/4.2/5.4; OLD scheme 7.1/3.9/4.4 (same problem -> not the convection scheme); entr/tau/cap/dd ~no change; ck 1.0e-3 4.0/3.2/4.2; ck 0.9e-3 2.8/2.6/4.0; ck_z=1 2.5/2.5/3.7 (AS v200 +6.2 -> +3.0). ck_z is an equation correction, not a tune. Same-run exams running: tn-wx-ckz (acct4), tn-base-ckz (5), tn-io-as-ckz (6), tn-io-si-ckz (8), tn-gen-ckz (9). Adopt if exam/tracks/genesis not worse.
Map viewer started (Sridhar 17:07): scripts/viewer (index.html + pack.py), maps_run.py (run_wx map_out extras), maps_borders.py; Kaggle npz outputs go to release model-maps. Private artifact https://claude.ai/artifact/S1b5DcTXhWoWv7j4fZaPwa (v2: drag round globe, zoom). Sridhar wants UI corrected in parallel with Stage 1.

## 24 Oct 16:45 IST - new official track numbers (default inserted storm 180 km / 0.4), and the steering cause
Bay (tn-base-final2, 84 storms) median km 0/24/48/72/96/120: new 58/120/216/345/423/522 vs old yardstick 58/102/217/373/471/722 (same run). AS (tn-io-as-final2) 64/148/236/419/528/708. SI (tn-io-si-final2) new 61/113/206/322/429/603 vs old 61/94/177/285/407/599. Old scheme still better at 24 h (by ~20 km) and SI to 72 h. NOTE run-to-run noise: identical AS settings gave 96 h 473 (combo2) vs 528 (final2) -> treat <~50 km at 96 h as noise.
Steering (wx_wind.py, 40 starts, day 5 vs ERA5): low levels too EASTERLY (850 hPa du -3.0 Bay, -2.6 AS, -1.8 SI m/s), upper levels too WESTERLY (200 hPa +3.0/+1.7/+3.6), AS 200 hPa dv +6 (outflow too strong). Hour 0 fine (<0.6). Deep-layer mean cancels, so the error is too much vertical shear = tropical overturning (Hadley/Walker) too strong = too much convective heating/rain. Fits Bay storms too far west. Variant tests running (tn-wind-old acct8, -entr acct2, -tau acct6, -cap acct1, -dd acct3, -ck acct4).
#9 tracker: works (finds 59% AS / 75% Bay of other real storms); vo_min 2.5 found 61% but doubled tracks -> keep 3.5. Misses = weak systems the model does not hold (physics, not tracker). #9 counted DONE.
Ensemble start-vortex variation (tn-ens-bvary2 Bay, tn-ens-bvary-as): spread/error 0.5-0.7, no clear gain -> not adopted. Likely the error is mostly systematic (steering bias) which spread cannot cover; fix steering first.

## DECISION 24 Oct 14:50 IST - inserted starting storm smaller and weaker
mm2 bogus defaults bogus_rout 350 -> 180 km, bogus_x 0.6 -> 0.4 (mm2 line ~171, self.S.get). Same-run tests (tn-io-as-combo2, tn-io-si-combo2, tn-base-combo): 72 h lat bias AS +0.46->+0.01, SI -0.66->-0.12, Bay +1.08->+0.35; 96 h median AS 557->473, SI 442->409, Bay 505->493 km; 24 h within 10 km; winds ~3 kt weaker at 24 h. hindens2 bogus_vary ranges recentred (120-280 km, 0.3-0.6).
Fix #9 test (hind2 config systems:true, sys_kw for track_all): other real storms alive found 59% (AS runs, tn-sys9-as) / 75% (Bay runs, tn-sys9-bb); misses mostly weak depressions -> rerun with vo_min 2.5 (tn-sys9b-as, acct1).
Ensemble with member-varied start vortex (tn-ens-bvary): spread/error 0.52/0.42/0.61/0.98/0.82 at 24-120 h (before ~0.6); ens mean beats control at 72-120 h. Steering check wx_wind.py (tn-wx-wind, acct8): u/v bias vs ERA5 over Bay/AS/SI at day 5.

## DECISION 24 Oct 02:40 IST - new defaults (mm2 DEFAULTS)
conv='mf', mf_kick_t 0.5, mf_kick_q 0.0005, mf_dd 0.5, sh_top 0.0, tau_shallow 3600 s, rad='radcloud', rad_every 2 (radcloud was NOT the true default before - only in test configs). Old scheme yardstick: conv='bmj', sh_top 0.7, tau_shallow 10800, bmj_ice 0.5.
Evidence: exam 23.7/74.6/119.5 m (old 25.4/77.3/120.3); Bay 107/212/343/543 (old 100/211/388/531); storm forming T85 21%, T170 24% (old 40%/31%).
Ocean hook applied in mm2 (ocean3d None/'ekman'/'rgo'; needs config 'ocean' path + ocean_clim.npz). LETKF groundwork done (scripts/da, docs/letkf.md).
Running (final settings): tn-base-final acct8 (Bay, score_hind --final for 2018-2025), tn-ens-final acct3 (#8), tn-base-ocean acct2 (#6), tn-io-as-final acct4, tn-t170-final1 acct5, tn-io-si6 acct6. Still to do: #9 tracker test, #10 rain vs TN SMART, #7 observations into start, final ECMWF exam rerun with defaults (equals mf_sh0_t1h run: 23.7/74.6/119.5).

## More context to read
- docs/PROJECT_HISTORY.md: the whole story from day one (website + model + every request Sridhar made).
- docs/cycle_notes_2026-10-23.json: every test result and decision from 22-23 Oct, in time order (the detailed log).
- docs/cyclone_model_status.md, docs/night_plan.md, docs/stage2_ocean.md, docs/letkf.md (when present), docs/obs_assimilation.md.
- Live doc (all parts, equations, change log): https://claude.ai/artifact/GttzHBxsJbyAh9HSW1NcFi

## 27 Oct 03:15 IST - HEAT BUDGET RESULTS + THREE EQUATION FIXES UNDER TEST
Budget (tropics, day 5, K/day, 20 starts): shallow='mf' plume is INACTIVE (h_shal < 1 everywhere; same as shallow off). Its trigger needs positive buoyancy + CAPE > 0 and a cloud < 250 hPa deep - almost never true. Organised entrainment (mf_org 1, shallow off) raises deep heating at sigma 0.35-0.55 by ~0.6-1.2 and warms 200-300 hPa by ~0.8 K, but the peak stays at sigma ~0.65-0.68 (too low). Rain evaporation is -2 to -3 K/day through the whole column (sigma 0.45-1.0) in all runs = about half the rain made evaporates (formula has no precipitation-area fraction). Default run: shallow mixing +8..+12 near the surface, -6..-8 at sigma 0.6-0.68, large-scale condensation +7.7 at sigma 0.65, rain evaporation -7 in the boundary layer = the spurious loop.
New options in mm2.py (all off by default): sh_trig (shallow plume active wherever the boundary-layer parcel makes cloud < 300 hPa deep), sh_clos (ECMWF shallow closure Mb = sh_clos (H + L E) / (h_up - h_env) at the level above the source), ev_frac (precipitation-area fraction a: box-mean evaporation k (1-RH) sqrt(a P)).
Running: tn-heat-sh (acct9: shtc = shallow mf+trig+clos 0.6; shtc_org = + mf_org 1), tn-heat-ev (acct10: shallow off + org1 + ev_frac 0.3 / 0.1), tn-heat-full (acct8: all fixes; + mf_ice 0.5), tn-wind-full (acct6: shear for full / ev3org), tn-gen-heat (acct5: genesis gatekeeper default / full / ev3org).
#7: fetching GFS analyses 25 Oct 06Z - 27 Oct 00Z (oursm now takes a list) to score trials 2412..2500. Next: fetch centres + obs for a new trial.

## 27 Oct 05:30 IST - HEATING FIX RESULTS (round 1) + EXAMS LAUNCHED
Budget (tropics d5): new shallow trigger/closure still nearly inactive (h_shal <= 0.7 K/day) -> on-fraction diagnostics added (on_dp/on_sh/on_bmjsh in wx_prof) to see why. ev_frac 0.3 halves rain evaporation (-2.5 -> -1.5 K/day) and cuts the 600-850 hPa moist bias (1.05 -> 0.7 g/kg); T bias still cold 150-300 hPa (-2.5..-3.4) and 850-1000 (-2); default was -4.7 at 250 and +2.3 at 1000.
Shear error day 5 (du200-850 m/s, Bay/AS/SI): default 7.1/3.9/4.4; full 5.8/4.1/2.9; ck_z runs ~2.5/2.5/3.7.
Genesis gatekeeper (84 cases, formed = dist<=300, vo>=5, depth>=2): default 23%, full 30%, ev3org (shallow 'mse' with tau 1e12) 0% (!).
full = {"shallow":"mf","sh_trig":1,"sh_clos":0.6,"mf_org":1,"ev_frac":0.3}. Launched same-run exams default/full/fullck(+ck_z): tn-wx-full (acct1), tn-base-full (2), tn-io-as-full (3), tn-io-si-full (4); tn-gen-fullck (8: fullck, full_c10), tn-heat-ck (9), tn-wind-fullck (10).
#7 score (7 trials, vs GFS analyses): OI start roughly neutral: tropics u850/t850 within +-1%, z500 day 1 +3% worse (India/Bay +4.5%), bias-corrected variant ~neutral (n=3). Not a win yet; suspect mass increments without balanced winds. Fetched latest centres + obs for a new trial (launch next cycle, acct 5).
GFS analyses: download with gh api assets (gh release download uses GraphQL = blocked).

## 27 Oct 07:05 IST - EXAMS: full fixes NOT adopted (Bay tracks worse); ablation running
Shallow plume is ON in ~51% of tropical columns (deep 34-39%, old shallow test 44-48%) - active; it moves mostly moisture, so h_shal (T only) looks small. Not a bug.
fullck (full + ck_z): shear Bay/AS/SI 4.0/3.4/3.7 (default 7.1/3.9/4.4, full 5.8/4.1/2.9); colder (200 hPa -4.2); genesis 31%; full_c10 (sh_clos 1) 27%.
ECMWF exam d5 (default / full / fullck): z500 globe 74.7/71.4/74.0; z500 tropics 34.4/23.6/32.6; t850 India 3.14/3.66/3.90 (worse); rain24 India 11.05/10.02/9.95; rain24 TN d3 6.11/7.27/7.62 with ACC 0.34 -> 0.05 (much worse); u850 India 6.77/6.63/6.24; u200 tropics 10.14/10.36/9.59.
Tracks (--tune, median km 24/48/72/96/120): Bay default 110/243/394/584/713, full 133/315/550/771/980, fullck 125/312/487/691/1001 (MUCH WORSE: 72 h bias full dlat -1.48 dlon -3.57 vs default +0.40/-1.99 = too far west+south). AS default 140/234/410/521/737, full 136/233/389/507/642 (better, east bias removed). SI pending (tn-io-si-full acct4).
Decision: not adopted. Ablation: tn-base-abl1 (acct2: org, ev), tn-base-abl2 (acct3: sh, evsh), tn-wx-abl (acct1: org, ev, evsh) - compare with default in tn-base-full / tn-wx-full (same storms/starts, deterministic).
#7: new trial tn-obs-2026102618 (acct5). Morning report sent 07:00 IST.

## 27 Oct 09:15 IST - ABLATION: shallow plume kills TN rain; rain-evaporation fraction is the keeper
SI tracks (--tune median 72 h): default 292, full 330, fullck 325 (worse; west bias -0.8 -> -2.3 deg lon).
Bay ablation (median 24/48/72/96/120): default 110/240/394/568/700; org 120/256/407/553/603; ev 129/247/403/461/483; sh 111/242/428/649/729; evsh 123/293/426/692/816; full 133/312/550/753/1022. Each alone ~neutral within noise; the combination is much worse (nonlinear).
ECMWF exam d5 (default/org/ev/evsh): z500 globe 74.7/74.2/72.6/71.4; z500 tropics 34.4/33.5/28.0/24.6; TN rain24 d3 ACC 0.34/0.28/0.35/0.11 -> the shallow plume (sh) causes the TN rain loss; t850 India 3.14/3.33/3.26/3.54; u200 tropics 10.14/9.79/9.73/10.17.
Candidate = ev_frac 0.3 (keeps TN rain, better z500 tropics/globe, India rain, u200; Bay ~neutral). Running: tn-gen-ev (acct8: ev, evorg5=ev+mf_org0.5), tn-io-as-ev (3) / tn-io-si-ev (4): ev, evorg5; tn-base-ev (2: evorg5, ev5=ev_frac0.5); tn-wx-ev (1: evorg5, ev5); tn-wind-ev (10: ev, evorg5).
#7: trial tn-obs-2026102618 done (model-maps); fetching GFS analyses 2700/2706 for scoring.

## 27 Oct 11:05 IST - ADOPTED: ev_frac = 0.3 is the new DEFAULT (mm2.py DEFAULTS)
Evidence (vs old default): genesis 26% (ev) / 27% (evorg5); Bay tracks median 24/48/72/96/120: old 110/240/391/526/700, ev 129/247/385/421/403 (mean 72 h 436 vs 394 - within noise); AS 72 h 392/402 vs 410/430 (better); SI 72 h 277/338 vs 292/327 (~same); exam d5 z500 tropics 34.4 -> 28.0, globe 74.7 -> 72.6, TN rain ACC d3 0.35 (kept), t850 India 3.14 -> 3.26; Bay/AS/SI day-5 shear error (du200-850) ev 4.1/2.5/5.0 (old 7.1/3.9/4.4). evorg5 (+mf_org 0.5) worse on SI tracks and t850 India; ev5 (ev_frac 0.5) weaker gains.
NOTE: from now on 'default' in any new job INCLUDES ev_frac 0.3; older results' 'default' = ev_frac 0.
Other new options stay off: sh_trig, sh_clos, shallow='mf' (hurts TN rain), mf_org.
Running: tn-prof-ev (acct9: def / +ck_z / +pbl_tm budget), tn-wind-ev2 (acct10: ck, tm), tn-gen-ev2 (acct8: ck, tm). If ck or tm passes genesis and helps shear/low-level cold bias -> tracks + exam for it; otherwise go to final scoring (#11) with the new default.
#7: still neutral (7 trials scored); trial 2618 waits for GFS analyses 2700/2706 (re-fetch pushed). 11:00 report sent.

## 27 Oct 11:35 IST - LEAN MODE + BIG GPU BATCH
Sridhar: weekly usage 16% -> cycles every 3 h (work + report together) + one silent ~03:00 IST launch; give GPUs/GitHub ~3 h of work per cycle (multiple, bigger jobs).
Big batch (all with new default ev_frac 0.3): tn-wx-ev2 (acct1: exam def/ck/tm), tn-base-ev2 (2: Bay all years def/ck/tm -> score_hind --tune AND --final), tn-io-as-ev2 (3), tn-io-si-ev2 (4), tn-ens-ev (5: ensemble spread, ens_final3 settings), tn-ocean-ev (6: #6 column vs 3-D ocean 'rgo'). Still running: tn-gen-ev2 (8). Done: tn-prof-ev (9), tn-wind-ev2 (10).

## 27 Oct 14:05 IST - BATCH RESULTS (new default ev_frac 0.3) + NEXT BATCH
prof def d5 tropics T: 250 hPa -5.3, 1000 hPa +2.8 (cold top / warm bottom remains). ck: colder aloft (-6.2); tm ~same.
Shear err d5 Bay/AS/SI: def 4.1/2.5/5.0; ck 0.7/1.2/2.9; tm 4.1/3.5/5.1. Genesis: ck 19% (just under gatekeeper), tm 21%.
Tracks 72 h median (tune / final): Bay def 390/476, ck 360/347, tm 336/398; AS def 392/452, ck 401/381, tm 380/338; SI def 259/390, ck 327/337, tm 281/353.
Exam d5 def/ck/tm: z500 tropics 27.95/33.3/26.3; z500 globe 72.7/74.8/72.0; TN rain24 6.32,7.5 (d3,d5) / 5.77,6.19 / 5.35,6.47; TN ACC d5 0.19/0.30/0.27; t850 India 3.27/3.28/3.49; u200 trop 9.72/9.38/9.87.
Ensemble (tn-ens-ev): spread/error 0.83/0.74/0.82/0.84/0.92 at 24-120 h; ens mean beats control 72-120 h by 20-26%; coast-stretch Brier skill -5%.
#6 ocean: col vs col_rgo no track difference -> Stage 1 keeps column ocean.
#7: unchanged (n=7 scored).
Next batch: tn-wx-ckm (1), tn-base-ckm (2), tn-io-as-ckm (3), tn-io-si-ckm (4) [ckm = ck_z 1 + pbl_tm 1; ck05 = ck_z 0.5], tn-ens-ckm (5), tn-t170-ev0/1 (6, 9: T170 def vs ckm), tn-gen-ckm (8), tn-prof-ckm (10: budget + shear). hindens2.py now accepts 'set' (model settings for all members).
Decision rule: adopt ckm (or ck05) if genesis >= ~21% and tracks no worse in all 3 basins; then final scoring.

## 27 Oct 15:45 IST - SRIDHAR DECISIONS
- 80 km (T170) in Stage 1 - APPROVED rule: if T170 (tn-t170-ev0/1) is no worse than T85 on tracks and genesis holds (~21%), the MAIN daily run becomes T170 in Stage 1; ensemble stays ~T85. Then run the T170 full exam (wx2) + AS/SI tracks + genesis at T170. Adds ~1-2 days (Stage 1 ~4-5 Nov). If T170 is worse -> report plainly, re-tune needed.
- Nivar in the UI: after the steering add-on decision, run maps_run.py from near:2020-11-21 (libm_wx2020) with the chosen settings, pack for the viewer with our track + real Nivar track, send link in the 20:00 report (honest: our Nivar stays 7-9N going west, 315-400 km from real landfall).
- Commercial: only after all 3 stages + his personal validation through all of 2027 (SWM + NEM). Stage 3 done before 1 Jan 2027. Nov-Dec 2026 daily runs + archive = dry run (version-labelled), 2027 scores = final model only.

## 27 Oct 17:05 IST - ADOPTED ck_z = 0.5 (new DEFAULT = ev_frac 0.3 + ck_z 0.5); T170 batch
Genesis: ckm (ck_z1+pbl_tm1) 30%, ck05 29%, ck 19%. Shear d5 Bay/AS/SI: ckm -0.1/1.6/2.7, ck05 2.2/1.7/3.7 (def 4.1/2.5/5.0).
Tracks 72 h median tune|final: Bay def 390|476, ck 360|347, ckm 420|366, ck05 437|359; AS def 392|452, ck 401|381, ckm 423|464, ck05 447|404; SI def 259|379, ck 327|338, ckm 273|328, ck05 308|372. (tune vs final disagree = mostly noise.)
Exam d5 ckm/ck05 (def): z500 tropics 31.4/30.7 (28.0); t850 India 3.56/3.28 (3.27); TN rain24 6.77/6.38 (7.5), ACC 0.28/0.31 (0.19); u200 9.55/9.49 (9.72).
Ensemble with ckm: spread/error 0.72 (72 h) .. 1.12 (120 h); coast Brier skill -6%.
Chose ck05 (keeps India T, passes genesis, halves Bay shear, TN rain better). mm2 DEFAULTS ck_z=0.5.
T170 first try (tn-t170-ev0/1) OOM-killed with 2 variants in one job -> one variant per job now.
Running: tn-t170-new0/1 (6, 9: Bay T170), tn-io-as-t170 (3), tn-io-si-t170 (4), tn-gen-t170new (8), tn-wx-t170new (1), tn-ens-new2 (5, T85 new default), tn-maps-nivar (10: maps_run from near:2020-11-22, T85, 240 h -> model-maps release maps_nivar_2020.npz).
T85 reference for the new default = ck05 in tn-base-ckm / tn-io-as-ckm / tn-io-si-ckm / tn-wx-ckm / tn-gen-ckm.
#7: pushed RUN ours + obs (latest) + oursm 2706 2712 -> launch obs_trial on acct2 next cycle.

## 27 Oct 17:30 IST - Sridhar: fix the upper-air cold bias IN STAGE 1 (time box ~2 days)
Tropics d5 T bias with new default: 200-300 hPa -5..-6 K, 1000 hPa +3; z500 tropics error 31 (ECMWF 6.9). Tropical OLR ~205 W/m2 (observed ~250) -> suspect too much anvil/high cloud whose tops cool the upper air by LW.
tn-prof-rad (acct2): anv1 (anv_a 1.0, fewer anvils), anv06 (anv_max 0.6), kice (k_ice0 halved), ice05 (mf_ice 0.5). Read T bias 200-400 hPa + olr_trop + rad_Kday. Then: deep-plume detrainment height, radiation clear-sky check (test_radcloud.py vs RRTM-like reference). Winner -> genesis + tracks + exam.
#7 obs_trial moved to next free account.

## 27 Oct 18:05 IST - LIVE TEST: Cyclone Arnab (JTWC 02B, Cat 4, Bay, 16.2N 83.8E, WNW 9 kt -> Godavari delta, binary interaction with Invest 90B)
Sridhar shared JTWC prognostic reasoning (io0226prog). Launched live2 51-member ensemble (GitHub, cyclone-mmlive.yml) for 2026102706 with the new default -> data/cyclone/mm/live/2026102706-v2. Compare our tracks/landfall/intensity with JTWC (landfall Godavari delta ~TAU 12-24, stall, turn N by TAU 36, dissipate TAU 60) and ECMWF/GFS.
Ideas from the JTWC text to use: (1) a 'prognostic reasoning' product from our own run: steering ridge position, deep-layer shear, SST, outflow, interaction with other systems, ensemble spread -> confidence words (wording must not look like official IMD/JTWC warnings); (2) binary interaction test case for the multi-system tracker (#9); (3) compact pinhole-eye storm = why grid size matters for intensity (supports the T170 main run).

## 27 Oct 18:15 IST - Physics ideas from JTWC Arnab reasoning (Sridhar asked to use them)
Mechanisms in the bulletin -> our action:
1. Brown ocean effect (wet river delta keeps evaporation going, slows weakening ~24 h) -> landfall-decay exam (model decay after landfall vs best track, Kaplan-DeMaria style), split delta/wet-soil vs dry/hilly landfalls; check soil-moisture start (landinit SOILW) and land evaporation beta; consider a wetland/delta soil-moisture floor.
2. Ocean heat content / warm shelf waters (SST 29-30 C, high OHC) -> column ocean starts with a fixed mixed-layer depth; test starting mixed-layer depth / OHC from RTOFS profiles (RUN word 'ocean' already fetches RTOFS) for intensity.
3. Outflow channel + upper anticyclone -> storm strength depends on outflow temperature; our 5-6 K cold upper troposphere inflates potential intensity and distorts outflow -> another reason the cold-bias fix matters (link it in the intensity scores).
4. Pinhole eye / compact inner core -> fixed inserted-vortex size (180 km) is too big for compact storms: size the vortex from the real storm's RMW/R34 (IBTrACS usa_rmw/usa_r34, JTWC warnings) and test on tracks + intensity; also supports T170 main run.
5. Binary interaction with Invest 90B (vorticity advection, deceleration; trackers smooth it) -> test that our multi-system tracker keeps both and slows 02B in the live run.
6. Weakening steering gradient as the subtropical ridge moves east -> steering fix (ck_z) relevant; check ridge position in the live run vs ECMWF.
7. Terrain + friction decay after landfall -> part of the landfall-decay exam (z0_land).
Next free accounts: (a) vortex size from RMW/R34 test (Bay+AS tracks, intensity), (b) landfall-decay exam on all landfalling storms, (c) RTOFS mixed-layer start test.

## 27 Oct 18:40 IST - Cold upper air: two new leads (from Sridhar's RCE note)
(a) Tropopause/ozone 'lid': d5 tropics T bias +7 K at 100 hPa but -5..-6 K at 150-400 hPa -> tropopause too low / ozone heating too strong or misplaced (radcloud k_o3_lw, SW ozone absorption, top-level radiation; 32 levels coarse near tropopause). Test: ozone profile/strength variants in wx_prof (rad_prm k_o3_lw lower/higher) + check ozone climatology used.
(b) Full heat budget: add dynamics terms (vertical advection / subsidence warming + horizontal advection) to wx_prof so radiation + convection + dynamics balance is measured; if large-scale subsidence is too weak, upper air goes cold even with right physics.
Sridhar offered to read articles and help: ask him for specific reading when useful.

## 27 Oct 19:05 IST - From ECMWF IFS Cy50r1 Part IV ch.6 (Sridhar attached the PDF; text in scratchpad/ifs/ifs.txt)
ECMWF updraught: entrainment eps = 1.75e-3 m-1 x (1.3 - RH) x (qsat(T)/qsat(T_base))^3 (x2 for shallow/mid-level) [ours: 1.5e-4 x (1.3-RH), height scaling only with mf_org=1];
turbulent detrainment 0.75e-4 m-1 x (1.6 - RH); organised detrainment from the drop in updraught kinetic energy; cloud top where w = 0 (kinetic energy eq. 6.10: dK/dz = -eps(1+beta Cd)2K + g b/(f(1+gamma)Tv), beta Cd = 0.949, f(1+gamma) = 3, w = 1 m/s at cloud base) [ours: top at first level with negative buoyancy, fixed mass-flux shape]; downdraught eta = 0.3 [ours mf_dd 0.5]; freezing in the updraught included.
Hypothesis: our plumes stop at the first stable layer (tropical 0 C level ~550 hPa) -> heating peaks at 650-700 hPa -> cold upper air. Added option mf_wke (cloud top from the kinetic-energy equation). Test next free accounts (wx_prof budget + T bias): wke (mf_wke 1), wke_org (mf_wke 1 + mf_org 1), ecent (entr 1.75e-3 + mf_org 1 + mf_wke 1), wke_dd3 (mf_wke 1 + mf_dd 0.3), wke_ice (mf_wke 1 + mf_ice 0.5). Then genesis/tracks/exam for the best.

## 27 Oct 19:20 IST - From Sridhar's note on how ECMWF / GFS / ICON fixed their UTLS cold bias
ECMWF: too-moist lowermost stratosphere -> too much LW cooling (fixed with stratospheric humidity analysis + weak-constraint 4D-Var). GFS: FV3 core + GFDL microphysics (detrained ice at 200-400 hPa -> cloud radiative forcing). ICON: entrainment tuning + higher model top / damping layer so convection can deposit heat up to the tropical tropopause (~17 km).
Our checks: (1) FOUND: radiation is NOT computed above sigma 0.12 (stratosphere relaxed to its start, tau_strat 15 d) and the top sponge is sigma<0.05 - a crude lid at the tropical tropopause (~100-120 hPa). New option rad_top (default 0.12). tn-prof-radtop (acct3): rad_top 0.0 / 0.06. (2) check stratospheric humidity in ppmv at 50-150 hPa (start vs day 5); if moist, cap it. (3) ice/anvil -> tn-prof-rad (done, read next cycle). (4) entrainment -> tn-prof-wke1/2 running.

## 27 Oct 19:30 IST - Ozone (Sridhar's note: ECMWF and GFS use prognostic ozone)
Ours (radcloud.ozone_mmr): ONE fixed tropical profile for the whole globe, peak 8 ppmv at 10 hPa, 0.34 ppmv at 100 hPa (real tropical ~0.1-0.2), 0.13 at 150 hPa (real ~0.05-0.1); mid/high latitudes far too little ozone near 100-300 hPa (lower tropopause there). Prognostic ozone not needed at our level; plan: zonal-mean monthly ozone climatology from ERA5 (o3 on pressure levels via our CDS key) -> lat/pressure table in radcloud; test after tn-prof-radtop (the lid matters only if radiation is computed up there).

## 27 Oct 19:15 IST - DECISION (Sridhar: "decision is yours ... it should be a professional weather model for India and Tamil Nadu")
Stage 1 now includes (in this order, each tested with budget + genesis + tracks + exam before adoption; register = docs/simplifications.md):
1. Convection cloud top / entrainment (mf_wke, ecent, ice, dd 0.3) - tests running.
2. Stratosphere: radiation above sigma 0.12 (rad_top) + ERA5 zonal-monthly ozone climatology + stratospheric humidity check.
3. Orographic gravity-wave drag + low-level blocking (Lott & Miller 1997 as in IFS ch.4), needs ERA5 sub-grid orography fields (sdor, isor, anor, slor) via CDS key; z0_land from sub-grid orography / land cover. Then a simple non-orographic GWD.
4. Vertical levels 32 -> 50 with more levels near the tropopause (sigma_bounds) - after 1-3, test cost and scores at T85 then T170.
5. Anvil / ice cloud tuning (tn-prof-rad) and storm-vortex size from best-track RMW/R34.
Then final scoring (#11), rain vs TN SMART (#10). New estimate: Stage 1 ~10-12 Nov; Stage 2 ~20-22 Nov; Stage 3 still before 31 Dec 2026 (tight; report honestly).
Data source for 2-3: ARCO ERA5 on Google Cloud (gcsfs, as in the 'lib'/'history' jobs of cyclone.yml): static standard_deviation_of_filtered_subgrid_orography, angle/anisotropy/slope_of_sub_gridscale_orography, and ozone_mass_mixing_ratio (pressure levels) -> monthly zonal means; write a fetch script + RUN word.

## 27 Oct 19:20 IST - Sridhar: grid plan + investment rule
Global 80 km all 10 days; 9 km North Indian Ocean + India window days 1-5 (global takes over after); 3 km Tamil Nadu window. Target: full 80+9+3 set in ~1-1.5 h per run -> parallel windows on separate accounts + likely a paid fast GPU for the fine windows; benchmark 9 km / 3 km in Stage 3 before any spend. He offered 20 more accounts (hold; check Kaggle terms first).
Investment rule: he will pay for GPUs/storage only after he is convinced by the output. Build it like ECMWF - don't skip anything (docs/simplifications.md is the checklist).

## 27 Oct 20:10 IST - CYCLE RESULTS
Cold UT tests (d5 tropics T 200/250/300 hPa; def ck05 -5.3/-5.8/-5.4): anv1/anv06/kice/ice05 ~0..+0.1; wke +0.2-0.3; wke_org +0.9; ecent +0.5-0.7; wke_dd3 ~+0.1; wke_ice +0.3; radtop0/06 ~0 (100 hPa warmer +0.7-0.9). OLR 212-216 for all. Old BMJ scheme also had ~-4.7 at 250 -> probably NOT mainly convection. Diagnosis job tn-prof-diag (acct8): entr0 (undiluted plumes), lw08 (rad_prm lw_line 0.8), physoff (dynamics alone).
T170 (Bay, T170_new vs T85 ck05): tune 24/48/72/96 h 98/235/343/460 vs 119/218/437/625; final 96/216/324/492 vs 108/256/359/689 -> T170 clearly better. Genesis T170 43% (n=44). AS T170 via par.sh OOM -> rerun one process per job: tn-as-t170a/b (acct3, 6). tn-io-si-t170 (acct4) and tn-wx-t170new (acct1) still running (may OOM too - par.sh runs 2 processes; if so rerun as single-process chunks).
Ensemble T85 new default (tn-ens-new2): spread/error 1.00 (72 h), 1.20 (120 h); ens mean 306 vs control 405 km at 72 h; coast Brier skill +2%.
Arnab live (2026102706-v2, 51 members): median 24 h 17.5N 81.8E (landfall Godavari delta area), 36 h 20.6N 81.4E (too fast inland; JTWC stall ~24 h), min p ~1001 hPa (far too weak vs Cat 4).
Nivar viewer: NEW artifact https://claude.ai/artifact/ERJcNLhKojkgHv3Z4Kxogy (old viewer S1b5... has unread old files; republishing it needs reading 26 binaries). Run from 21 Nov 00Z, T85 new default, no bogus: weak low 1004-1006 hPa, 200-300 km south of real track, coast near 9-10N vs 12.5N. Viewer now draws meta.tracks + meta.note (scratchpad/viewer/index.html). Next: T170 + inserted storm run from 22 Nov 18Z (maps_run needs grid + storm options).
#7: tn-obs-2026102706 (acct2).

## 27 Oct 20:40 IST - Sridhar: Nivar benchmark must start 30 h BEFORE formation (21 Nov 00Z), no inserted storm - forming the storm AND its track both matter.
Fixed benchmark: maps_run from 21 Nov 2020 00Z, no bogus, 10 days; re-run with every adopted change (T85 done; next T170 - needs maps_run grid option + single process). Score: did a low form within ~300 km of the real genesis point (7.8N 86.1E, 22 Nov 06Z), depth/minimum pressure, track error vs best track, landfall point/time vs Puducherry 12.5N 80.0E ~25 Nov 18Z. Add more such pre-formation benchmarks (e.g. Fengal 2024, Gaja 2018, Vardah 2016, Michaung 2023) to genesis2-style scoring for Tamil Nadu coast storms.
- Add to the Nivar (and other pre-formation) benchmark: vertical wind shear along the real track (200-850 hPa, 200-800 km annulus, every 6 h) in our run vs ERA5 (fetch ERA5 u/v 200/850 for 21-28 Nov 2020 via ARCO), plus storm asymmetry (convection/rain offset from centre). Sridhar: Nivar was a sheared system - shear must be captured.

## 27 Oct 22:55 IST - T170 ADOPTED as main-run grid; cold-UT diagnosis
T170 vs T85 (ck05), 72 h median tune|final: Bay 343|324 vs 437|359; AS 416|375 vs 449|456; SI 224 (half set)|357 (mean 369 vs 433) vs 313|340. Exam T170 (n=37 starts, other chunk OOM): z500 globe d5 72.9 (ECMWF ratio 2.34x, same as T85), TN rain ACC d3 0.38. -> Sridhar's rule met: MAIN daily run = T170 (80 km); ensemble stays T85. Single-process reruns of the OOM chunks: tn-wx-t170c0 (1), tn-si-t170c0 (4), tn-gen-t170c0 (9). par.sh with two T170 processes exceeds 30 GB host RAM -> always single process for T170.
Cold UT diagnosis: entr0 (undiluted plumes) 250 hPa -5.3 (def -5.8) -> not convection depth; lw08 ~no change -> not LW line strength; physoff (no physics at all): 100 hPa +8.4, 250-300 -2.3..-2.7 -> the +7 K at 100 hPa and part of the UT cold are dynamics / vertical resolution / top treatment, not physics. Next: tn-prof-l50 (acct8: 50 levels, and 50 levels + wke_org). Then sponge/top settings and tropopause-refined levels.
Nivar benchmark at T170 (no bogus, 21 Nov 00Z): tn-maps-nivar170 (acct10).
Scripts wx_prof / wx_wind / wx2 / genesis2 / maps_run now take 'grid' and 'layers' from settings.

## 27 Oct 23:30 IST - GPS radio occultation (Sridhar: take it)
Use 1 (now): independent check of our upper-air temperature forecasts (RO is unbiased, ~0.5 K, 5-30 km) - confirms the cold UT bias vs ERA5 and tracks it. Use 2 (Stage 2-3): assimilate refractivity/bending angle (or retrieved T) in LETKF. Probe pushed (RUN probe2): EUMETSAT Data Store GRAS/ROM SAF collections + UCAR COSMIC-2 NRT listing -> data/cyclone/obs_probe2.txt. Next: fetch script obs_fetch ro_*(); verification script vs our forecasts.

## 27 Oct 23:45 IST - Sridhar: STAGE 1 DEADLINE = 10 NOV (hard, not 12). Stage 1 scope (complete list):
Done: rain-evaporation fraction, steering (ck_z 0.5), T170 main run, ensemble spread, ocean decision (column), tracker, inserted storm.
To do by 10 Nov (in priority order):
1. Cold upper air: 50 levels (tn-prof-l50 running) + top/sponge/stratosphere treatment (rad_top) + stratospheric humidity check; verify with GPS radio occultation (probe pushed).
2. Orographic gravity-wave drag + low-level blocking/form drag (Lott-Miller, IFS ch.4) using ERA5 sub-grid orography; simple non-orographic GWD.
3. Ozone: ERA5 zonal-mean monthly climatology.
4. Storm start: inserted-vortex size from best-track RMW/R34.
5. Clear-sky radiation check against a reference profile.
6. Benchmarks: pre-formation Tamil Nadu storms (Nivar, Vardah, Gaja, Michaung, Fengal) incl. shear (ERA5) + landfall-decay exam (brown ocean).
7. #10 rain vs TN SMART; #7 observations trial decision.
8. #11 final scoring: wx2 exam, tracks --final all 3 basins, genesis, ensemble, at T170 (single process).
Rule: each change passes budget + genesis + tracks + exam before adoption. If an item cannot finish by 10 Nov, record a written decision (move to Stage 2) - do not slip the date.

## 28 Oct 00:05 IST - 50 LEVELS HELPS; Nivar T170 benchmark (first fresh-session cycle)
50 levels (tn-prof-l50 vs ck05, tropics d5 T bias): 100 hPa +7.1 -> +4.5; 250 -5.8 -> -4.9; 300 -5.4 -> -4.4; 500 -3.0 -> -2.4. L50 + wke_org: 250 -3.7, 300 -3.4, 100 +4.5. -> vertical resolution is about a third of the cold-UT / warm-100 problem; rest is top treatment + convection. Candidate: L50 (plain) first; L50_org later via its own genesis/track/exam.
Nivar T170 (no bogus, 21 Nov 00Z; maps on 1.4 deg viewer grid): a weak vortex (vo850 ~10e-5, depth 2-4 hPa, pmin ~1004-1006, 10 m wind 9-14 m/s) is in the right area on 23-25 Nov and moves WNW, but ~1.5-3 deg too far south: errors 33 km (23/00), 150 (24/00), 186 (25/00), 400 km at landfall (model ~9N vs real 12.5N 80.0E). Never intensifies (real 65 kt). -> genesis signal yes, intensity and northward motion no. Follow-ups (next free accounts): Nivar at L50, and an earlier start (20 Nov 00Z).
RO probe2: COSMIC-2 NRT level2 reachable at data.cosmic.ucar.edu (2019-2026) -> use it (tropics-dense). EUMETSAT RO collections not seen in the listed names; MOSDAC/Earthdata timed out. Next: obs_fetch ro_cosmic2() + verification vs our upper-air T.
Still running from previous cycle: tn-wx-t170c0 (acct1), tn-si-t170c0 (4), tn-gen-t170c0 (9) - single-process T170 reruns, ~55 min in at 23:50 IST.
Launched (single process each): tn-gen-l50c0/c1 (acct2/3, cfg gen_l50.json, variant T170_L50), tn-bay-l50c0/c1 (5/6, bay_l50.json, Bay tracks, compare with T170_new t170_ck05), tn-wx-l50c0/c1 (8/10, wx_l50.json, exam). Acct 7 LETKF reserved.
Next cycle: score t170c0 jobs (merge with t170new/si_1/gen_1); when L50 jobs finish compare vs T170_new (genesis %, Bay tune|final, exam z500 d5 + TN rain ACC); Nivar L50 + 20 Nov start; then top/sponge (rad_top) on L50.
28 Oct 00:10 IST (second firing of the same cycle): work above was already done; t170c0 jobs still running; all accounts busy (1,4,9 t170c0; 2,3,5,6,8,10 L50); this firing only scheduled the next cycle (07:50 IST).
28 Oct 00:10 IST (third firing of the same cycle): t170c0 jobs still running; the 07:50 IST cycle (02:20Z) was NOT actually in the scheduled-task list -> created now (trig_011emkCdu6Warqo68iRhChDn, with a duplicate-firing guard). No other work, no message.

## 28 Oct 01:10 IST - Sridhar's note on GWD as cause of UT cold bias (assessment)
Our cold UT is in the TROPICS (20S-20N); orographic GWD acts mainly in the extratropics, so it is a contributor at most, not the primary cause there. Useful checks to add: (1) zonal-mean u bias at 200-300 hPa by latitude band (extend wx_wind to global zonal means) - if extratropical jets too strong -> GWD missing confirmed; (2) when raising the model top (75-level test), keep/strengthen the top sponge (currently Rayleigh on winds, sigma<0.05, 1 day) to avoid wave reflection; (3) radiative heating profile 100-200 hPa already in wx_prof (rad_Kday).

## 28 Oct 08:00 IST - T170 final + 50-level verdict
T170 final (all chunks): genesis 38% (84 cases); SI 72 h median tune 227 vs T85 317, final 355 vs 372 (mean 386 vs 446); exam d5 z500 globe 73.3, tropics 32.6, TN rain ACC d3 0.29 / d5 0.25. T170 = main run confirmed.
T170 L50 (plain): genesis 37%; Bay 72 h tune 368 vs 363, final 298 vs 324; exam z500 globe 74.5 (73.3), TN rain24 d3 8.26 vs 7.38 mm, ACC d3 0.19 vs 0.29, d5 0.11 vs 0.25 -> TN rain clearly WORSE -> NOT adopted. (Physics tuned on 32 levels; ksrc/PBL/condensation behave differently with thinner layers.)
New option layers='tpNN' (mm2.sigma_bounds): tp75 = top layer ~4 hPa, ~8 hPa layers at 170 hPa, 21 levels 100-300 hPa, 11 below 900 hPa.
Running: tn-gen-l50org0/1 (2,3), tn-bay-l50org0/1 (5,6), tn-wx-l50org0/1 (8,10) [T170 L50 + mf_wke + mf_org]; tn-prof-tp75 (4: T85 tp75 / tp75_org / L50_org budget); tn-prof-tp75t170 (9: T170 tp75 memory/time); tn-maps-nivar20 (1: Nivar T170 earlier start).

## 28 Oct 10:00 IST - Why 50 levels hurt TN rain: layer-thickness dependence found (Sridhar's retuning note)
Checked our code against his three suggestions: (1) trigger: deep test is CAPE>50 J/kg & cloud depth>250 hPa (thickness-independent) but the parcel comes from ONE layer (sigma>=0.87, max theta-e) - thinner layers = shallower, more extreme source parcel; (2) entrainment is per metre (eps*dz), so not layer-dependent in principle; (3) FOUND: cloud-base mass flux is capped at mf_cap x (mass of the THINNEST cloud layer)/dt - with 50 levels that layer is ~15 hPa vs ~24 hPa at 32 levels -> cap ~35% lower -> weaker convection, rain shifts to large-scale/less organised. New option mf_capdp (Pa): cap uses at least a mf_capdp-thick layer; mf_capdp=2400 restores the 32-level behaviour. TEST NEXT (14:00 cycle, T170 L50): capdp alone and capdp + mf_wke/mf_org, exam (TN rain ACC gate) + Bay + genesis. Also consider a 50 hPa mixed source parcel (ECMWF style) and a TN-coast time-height RH/omega cross-section for a rain event (Bay moisture inflow) - needs omega in maps_run output.

## 28 Oct 10:05 IST - WORKING RULE (Sridhar): root cause first (docs/rootcause.md: 5-Why / fault tree + reference docs), then 1-2 discriminating tests. No broad trial-and-error screening.

## 28 Oct 10:35 IST - BREAKTHROUGH on cold UT: 75 tropopause-packed levels (tp75)
Tropics d5 T bias (100/200/250/300/500 hPa): ck05 32L +7.1/-5.3/-5.8/-5.4/-3.0; tp75 +2.1/-3.6/-3.6/-3.3/-1.8; tp75_org (mf_wke 1 + mf_org 1) +2.0/-0.4/-1.7/-1.8/-1.1 (OLR 202); L50_org +4.5/-3.2/-3.7/-3.4/-2.0. T170 tp75 runs fine (no OOM, n=10): +2.7/-3.7/-4.0/-3.8/-2.2.
-> vertical resolution at the tropopause + raised top was the main dynamical cause; with ECMWF cloud top/organised entrainment most of the cold bias is gone.
Sridhar's note (P1) assessment: right that resolution at 70-150 hPa and the top/sponge matter (confirmed); WRONG numbers: sigma 0.12 ~ 120 hPa, 0.05 ~ 50 hPa (not 2.4 / 1 hPa). phys_off zeroes ALL tendencies incl. sponge and stratosphere relaxation, so the physics-off dipole = no sponge at all -> reflection plausible. New options: sp_quad/sp_top (quadratic deep sponge), wx_prof region trop_pacific (mountain-free; tests the sigma-coordinate pressure-gradient idea).
Running: tn-wx-tp75c0/c1 (accts 4, 9): T170 tp75 + mf_wke + mf_org + mf_capdp 2400 exam (TN rain gate). NEXT (14:00): genesis + Bay tracks for the same; sponge test (sp_quad 1, sp_top 0.15) with tp75; check trop_pacific vs tropics.

## 28 Oct 10:50 IST - P2 (TN rain vs levels), Sridhar's note: mixed departure layer
Checked against our code: (1) our parcel = ONE layer (max theta-e in sigma>=0.87) -> implemented src_dp (Pa): parcel MSE/q = mass-weighted mean over a src_dp-thick layer centred on the source level (ECMWF mixed departure layer); (2) trigger: CAPE>50 J/kg & depth>250 hPa, no single-layer CIN test (plume may rise 0.2 sigma below its LFC) - fine; (3) heating = flux divergence /layer mass (conservative) - fine; the layer-dependent piece is the mass-flux cap (mf_capdp, done).
14:00 cycle: if tn-wx-tp75c0/1 (tp75 + wke + org + capdp 2400) still loses TN rain skill vs T170_new (ACC d3 0.29), next exam = same + src_dp 5000 (50 hPa); then genesis + Bay tracks for the winner.

## 28 Oct 14:05 IST - L50org rejected; 75-level candidate full test battery running
T170 L50org (L50 + mf_wke + mf_org): genesis 33%; Bay 72 h tune 327 vs 343, final 341 vs 324; exam z500 tropics d5 36.4 vs 32.6 (worse), TN rain ACC d3 0.28 (=), d5 0.08 vs 0.25 (much worse) -> REJECTED.
Nivar T170 from 16 Nov (near:2020-11-20 picks 16 Nov): no real storm (depth 1-3 hPa, 175-414 km off) - 6-day lead too far for genesis.
Candidate 'tp75oc' = layers tp75 + mf_wke 1 + mf_org 1 + mf_capdp 2400 (T170). Exam tn-wx-tp75c0/c1 (accts 4, 9) still running (started 10:04 IST). Launched (each runs both halves in sequence, ~6 h): tn-gen-tp75oc (2), tn-bay-tp75oc (3), tn-as-tp75oc (5), tn-si-tp75oc (6); tn-prof-sponge (8: tp75oc vs + deep sponge sp_quad 1 sp_top 0.15; region trop_pacific); tn-maps-nivar-cand (1: Nivar 21 Nov with tp75oc); tn-maps-nivar-diff (10: Nivar T170 32L with diff_x 4).
Adopt tp75oc only if: TN rain ACC d3/d5 >= T170_new (0.29/0.25), genesis >= ~21%, tracks no worse in all 3 basins, z500 no worse. If TN rain fails -> add src_dp 5000.

## 28 Oct 14:40 IST - Sridhar's nesting/75-level guardrails (assessment)
Stage 3 design decisions recorded: (1) start with ONE-WAY nesting (80 km -> 9 km -> 3 km), wide lateral relaxation zones (~8-10 grid points, Davies), two-way only after one-way is verified; (2) grey zone: 9 km keeps mass-flux convection but scale-aware (reduce cloud-base mass flux with resolution, as IFS at 9 km); 3 km = convection-permitting: deep scheme off, shallow on, needs PROGNOSTIC cloud water/ice/rain microphysics (register item 9) - prerequisite for Stage 3; (3) Stage 1 NOW: with tp75 (~11 levels below 900 hPa) check the boundary layer is not over-mixing low-level moisture: compare d5 q bias at 1000/925/850 hPa and lowest-layer RH for tp75oc vs T170_new in tn-prof-sponge / exam; surface-exchange retune for 3 km coast = Stage 3.

## 28 Oct 15:00 IST - Sridhar's watch-outs: shallow convection is ON (moist-static-energy mixing, default 'mse'); only the mass-flux shallow PLUME was rejected. With tp75 check low-level moisture pooling (q bias 1000-850 hPa, lowest-layer RH) and grid-point storms (max 6-h rain per point). diff_x guard: watch kinetic-energy spectrum tail / max wind / NaN in tn-maps-nivar-diff; never adopt weaker diffusion without a 10-day stability check. Prognostic cloud water/ice = prerequisite for Stage 3 (and helps monsoon cloud-radiation).

## 28 Oct 15:15 IST - Peer review #1 (Gemini) - checked against our setup
Agree / act:
- Sponge must be CONFINED to the top ~10-15% (above ~15-20 hPa; sigma < ~0.02-0.03), quadratic, 12-24 h at the top. Our running test tn-prof-sponge uses sp_top 0.15 (= down to 150 hPa) -> too deep; next: sp_top 0.025, sponge 43200 s.
- Do NOT relax/damp temperature: with tp75 our stratosphere is still relaxed to its start above sigma 0.12 (rad_top) -> next test rad_top 0.0 (radiation to the top, no T relaxation) together with the confined sponge = Experiment A for the +2 K at 100 hPa.
- OLR 202 W/m2 (obs ~240-250) is a real energy-budget problem: deeper plumes -> more diagnosed anvil. Check OLR and clear-sky OLR; Experiment B (ours): keep heating aloft (tp75oc) but reduce diagnosed anvil cover (rad_prm anv_max 0.6 / anv_a 1.0) -> OLR back to ~230-245 without re-cooling 250 hPa.
- Mountain pressure-gradient error: compare trop_pacific vs tropics in tn-prof-sponge; vertical CFL with thin layers: watch for blow-ups/NaN in T170 tp75 runs (10 starts ran clean so far).
Disagree: Gemini's Experiment B (move detrainment lower) would undo the cold-bias fix - prefer the anvil-cover route first.

## 28 Oct 15:25 IST - Peer review #1 (ChatGPT) - checked; KEY FINDING from its 'diagnostics' point
Tropics day-0 vs day-5 bias (wx_prof h0/d5):
32L: day0 100 hPa +2.9, 250 -0.2 | day5 +7.1 / -5.8 | forecast drift 100 +4.3, 250 -5.6
L50: day0 +1.8 | drift 100 +2.7, 250 -4.8
tp75: day0 +1.2 | drift 100 +0.8, 250 -3.6;  tp75_org: drift 100 +0.8, 250 -1.6
-> part of the '100 hPa warm bias' is a REPRESENTATION error (sharp tropopause interpolated through coarse levels: +2.9 K already at day 0 with 32 levels, +1.2 with tp75). With tp75 the real 100 hPa forecast drift is only +0.8 K. Remaining main problem = 250 hPa drift (-1.6 K with tp75_org).
Act on (ChatGPT): (1) full temperature-tendency budget by level incl. dynamics/numerics residual (dT/dt total minus physics) for no-physics and full-physics runs, and day-0..1 adjustment (first 6-24 h) - top priority before more physics tuning; (2) sponge: smooth sin^2 ramp in log-p from 30 hPa to the 4 hPa top, 6-12 h at the top, winds only, no T relaxation (= its proposal; better than our sp_top 0.15 test); (3) OLR like-for-like: compare with a matching observed tropical OLR (NOAA interpolated OLR / CERES, same months), plus clear-sky OLR; (4) confounding: level count vs placement vs top - if needed one run with tp75 placement but old 20 hPa top. Agree with Gemini+ChatGPT: no T relaxation, confined sponge.

## 28 Oct 18:25 IST - Sridhar's idea: use the previous 72 h to build the 00Z start (assessment)
Already partly true: our start = consensus of operational analyses (ECMWF 4D-Var / GFS EnVar), which are CYCLED (each uses the previous forecast as background), so past observations are already inside them. Plan to use the idea properly: (1) Stage 2-3 LETKF in continuous 6-h cycling = memory of all past observations (instead of one long 72 h window; 4D-Var-style windows >12-24 h become nonlinear/unstable); (2) storm history for the inserted vortex: last 24-72 h best-track motion, size (RMW/R34) and intensity trend (Stage 1 item 4 extended); (3) model-bias correction learned from the last days' own forecast errors vs analyses (online / weak-constraint-like). Prove each with/without on held-out cases.

## 28 Oct 20:00 IST - cycle results
tp75oc exam (tn-wx-tp75c0/1, accts 4, 9) STILL RUNNING after ~10 h (75 levels ~2x cost; 37 starts x 10 days per half) - risk of the 12 h Kaggle limit at ~22:00 IST; if it fails rerun as 4 quarters (wx2 CHUNK 0..3 of 4). Battery tn-gen/bay/as/si-tp75oc (2, 3, 5, 6) running.
Sponge test (tn-prof-sponge, tp75oc): deep quadratic sponge only changes 100 hPa (+1.9 -> +1.2), not below -> keep a sponge (use the confined 30 -> 4 hPa sin^2 version when implemented). tp75oc with capdp: 250 hPa -2.3 (tp75_org without capdp -1.7).
Mountain pressure-gradient hypothesis RULED OUT: open tropical Pacific (no mountains) has the same cold UT (250 hPa -2.0 vs tropics -2.3).
Nivar benchmark (21 Nov 00Z, no inserted storm), daily 06Z position error / min pressure (depth): T170 32L earlier: 33/150/186/400 km, ~1004-1006 hPa. tp75oc: 188/126/277/414 km, 1005-1007 (-3..-5) -> no better. T170 + diff_x 4 (weaker hyper-diffusion): 423/368/78/68/437 km, 25 Nov 1003 hPa (-9) -> best core and near-landfall position so far (one case). Running: tn-bay-diff4 (10) + tn-gen-diff4 (8) (tracks, genesis, stability), tn-maps-nivar-best (1: all candidates together).

## 28 Oct 23:35 IST - Stage 4 adopted (user decision)
Stage 4 = WeekAI (weeks 2-4/6) + MonthAI (monthly tercile outlooks), data-driven, built in 2027. Does NOT touch Stages 1-3 or GPU budget.
- Jan-Feb 2027: data (ERA5, IMD gridded rain 1981-2025, MJO RMM, Nino3.4, IOD DMI, Bay SST, soil moisture); climatology; scoring vs climatology + IMD ERF + ECMWF extended range (RPSS, reliability).
- Mar-Apr 2027: WeekAI v0 = simple regression/logistic on 3-5 predictors, leave-years-out hindcasts.
- May 2027: MonthAI v0; freeze both before SWM onset (~1 Jun).
- Jun-Sep 2027: silent live trial SWM. Oct-Dec 2027: silent live trial NEM.
- Neural nets only if they beat the regression baseline on held-out years.
- MEGAM days 8-10 as input only after >=1 yr archive (Nov 2026 on); proper training needs reforecasts (decide in 2028).
- Jan-Mar 2028: verify both seasons, go/no-go. Any outside use only after that.

## 29 Oct 02:00 IST - silent night cycle
Kaggle workflow: new COLLECT mode (KAGGLE line 3 = COLLECT) fetches output of kernels that outlive the 6 h GitHub runner. Used it for tp75 exam + battery (all complete).
RESULTS
- tp75oc REJECTED as a package (vs T170_new, same starts/cases): exam z500 tropics d5 32.6->37.8, TN rain ACC d3 0.27->0.13, d5 0.26->-0.02; genesis 23% vs 38%; Bay 24 h track 98->134 km, 72 h equal. Upper-air T gain is real but convection/genesis/rain degrade with 75 levels -> layer-thickness dependence in convection still there (P2). Keep 32L; revisit levels after the budget.
- diff_x 4 (weaker hyper-diffusion) NEUTRAL broadly: genesis 32 vs 33 of 86; Bay tracks mixed (72 h 336 vs 331); intensity +0.5-0.8 kt only (72 h: 28.0 vs 27.2 kt, real 42 kt). Nivar improvement was one case. Diffusion is NOT the main weak-storm cause.
- Exam check for the blogger doc: T170_new d5 TN rain24 8.1 vs HRES 3.7 mm, ACC 0.26 vs 0.60; t850 India d5 3.2 vs 1.0 K (doc corrected).
WEAK-STORM ROOT CAUSE - next discriminating tests (running):
- DFI smooths the inserted vortex? Bay hindcasts do bogus THEN 6 h DFI. tn-bay-nodfi (3), tn-as-nodfi (8), tn-si-nodfi (10): same as T170_new without DFI. If day-1 spin-down vanishes -> DFI is the cause (fix: DFI before bogus).
- Resolution limit? tn-bay-t255a/b (4, 5): T255 (~50 km) on chunks 0-1 of 4. T85->T170 already +5 kt; if T255 adds more and intensifies after day 1, weak storms are mostly grid-limited (answer = Stage 3 9 km window, and stop tuning physics for intensity at 80 km).
UPPER AIR (P1) running: tn-prof-budget (1: full T budget total/phys/dyn by level, 0-24 h and 96-120 h, T170 32L + tp75oc; wx_prof setting "_budget": true), tn-prof-sp2 (2: confined sin^2 sponge 30->4 hPa sp_quad 2, 6 h / 12 h; rad_top 0), tn-prof-sp3 (9: rad_top 0 + sp6; tp75oc + sp6).
DATA: RUN geo -> scripts/cyclone/geo_fetch.py: ARCO ERA5 sub-grid orography (0.5 deg) -> release geo_gwd.npz; monthly zonal-mean ozone 2017-19 -> ozone_clim.npz. Log data/cyclone/geo_fetch.txt.
Account 6: tn-si-tp75oc collect still polling (kernel status unknown); 7 = LETKF.
02:15 IST Sridhar (via peer review): do NOT abandon 75 levels - diagnose and correct the package; keep 32L as control. Attribution note: tp75oc changed levels AND mf_wke/mf_org/mf_capdp; L50 (levels only) also cut TN rain ACC (0.29->0.19) -> levels are the driver. Next cycle: levels-only tp75 exam+genesis (clean attribution), and a column test comparing convection on 32L vs tp75 for the same start (on/off fraction, cloud top, heating profile) to find the remaining layer-thickness dependence.
02:25 IST Sridhar: 32-vs-75 convection check must save, from the same start: trigger frequency (map + tropics/TN/Western Ghats), cloud-top pressure, heating profile by process, moisture tendencies (condensation, evaporation, transport), rain amount + pattern (TN, Ghats). Goal = a demonstrated causal chain (trigger -> cloud top -> heating -> rain); no assumption without it. Also check lowest levels over the Ghats (sigma with low ps). Control is 32L (not 50).

## 29 Oct 08:00 IST cycle
Results: see docs/rootcause.md 'Findings 29 Oct'. DFI ruled out (vortex refills within 12 h either way); sponge ruled out below 100 hPa; rad_top 0 worse at 100 hPa. tn-bay-t255a/b FAILED (dinosaur has no Grid.T255) -> mm2 now builds T255 as construct(255, 192). tn-prof-budget tp75oc variant OOM-killed (two T170 models in one process) -> one variant per budget job.
Running: tn-prof-bud2 (1: 32L budget v2), tn-prof-bud2tp (2: tp75 levels-only budget v2), tn-bay-t255c/d (5, 9: T255 chunks 0-1 of 4), tn-wx-tp75lv0/1 (6, 8: levels-only tp75 exam quarters 0-1 of 4), tn-bay-nodfi (3), tn-si-nodfi (10) still running; acct 4 kernel state unclear (old t255a) - collect before reuse.
Next: genesis levels-only tp75 (gen_tp75lv.json); GWD/blocking scheme implementation (data in); TN storm benchmarks.

## 29 Oct 14:00 IST cycle
See rootcause.md 'Findings 29 Oct 14:00'. New mm2 options (default off/unchanged): mf_dmin (deep cloud min depth Pa, default 25000), sh_dtop (no shallow mixing where parcel top sigma < sh_dtop).
Running: tn-prof-trigA (1), tn-prof-trigB (2), tn-prof-shal (5) [each two single-variant processes, outputs prof_<name>.json]; tn-gen-tp75lv0/1 (6, 9); tn-wx-tp75lv1 (8, needs COLLECT); tn-si-nodfi COLLECT (10).
Accounts 3, 4: weekly GPU quota used up (30 h). Budget GPU hours: prefer short prof jobs; avoid duplicate long runs.
T255 OOM (host RAM 'Killed' right after model build) -> next: T213 or fewer storms.
GWD coding not started yet (next cycle): Lott-Miller blocking + wave drag from geo_gwd.npz.
16:05 IST Sridhar: trigger = leading hypothesis, not confirmed. Order: confirm chain (short prof tests) -> fix trigger on 32L -> retest 75L. 63 km storm test = preliminary only, not equivalent to 50 km (50 km failed on memory, not evidence). Resource-conscious: short discriminating tests before long scoring runs. Drag developed separately (default-off option, scored alone vs 32L control).
17:45 IST Sridhar: shd06 = candidate fix only if favourable on: TN rain bias + spatial error vs gauges, upper-air T RMSE (not just bias) 250-500 hPa, genesis + intensity (no new false alarms / unrealistic intensification). Residual 250 hPa cold and 850 hPa cold = separate open problems.
GAP: the exam (wx2/score_wx) has no upper-air T RMSE (only z500, t850, t2, u850, u200, mslp, rain24). TODO: add tropical/India T RMSE at 250/300/400/500 hPa vs ERA5 to wx_prof (cheap) - ours vs ours (no HRES reference for these). TN rain vs gauges: use the TN SMART comparison (#10) for 2020 NEM starts if available, else IMD gridded.
17:55 IST: upper-air T scoring added (wx_prof "_ua": true -> r['ua'][d1/d3/d5][region_level] = bias + rmse vs ERA5 at 200/250/300/400/500/850 hPa, model regridded bilinearly to the ERA5 grid, same mask; "_chunk": [0,4] = the exam's quarter-0 starts; regions tropics/tn/india/trop_pacific). Running on the 19 exam starts: tn-ua-ctl (2, T170 32L control), tn-ua-shd06 (5, sh_dtop 0.6), tn-ua-tp75 (10, 75 levels only). Plus tn-wx-shd06q0 (1, exam quarter 0). Compare per level, per day; never one combined number.

## 29 Oct 20:10 IST cycle (run by hand: the 19:50 scheduled cycle had not fired by 20:07)
See rootcause.md 'Exam 29 Oct 20:10'. sh_dtop 0.6 NOT adopted (TN rain). Account 6 also out of weekly GPU quota (3, 4, 6). tn-ua-ctl / tn-ua-shd06 still running (accts 2, 5); tn-ua-tp75 done. The stuck 20:00 scheduled task was re-pointed to the silent night cycle (20:20Z).
20:25 IST Sridhar PROPOSAL (not adopted): 40 km global + 9 km NIO + 3 km TN (one-way nesting first). Keep the 80 km results/control as the historical reference; never redefine the control silently. Feasibility before commitment. My reply: 40 km = T340 (1024x512, dt ~10 min) ~8-10x the T170 cost and ~4x memory; T255 already OOM on Kaggle T4 -> test T255/T340 on Kaggle TPU v3-8 (JAX native, 128 GB HBM); 80 km stays the Stage 1 global unless the TPU test shows 40 km fits the time budget.
20:35 IST: TPU route OUT (Sridhar: needs face verification, and it did not work for him even after). My miss acknowledged: when Stage 3 (9 km NIO / 3 km TN) was planned I did not state plainly that Dinosaur is a GLOBAL spectral, HYDROSTATIC core - it cannot run regional windows, and 3 km needs non-hydrostatic dynamics (register item 21). Stage 3 therefore needs a regional model: (A) our own JAX limited-area model (large, risky for 1 Jan), (B) an existing open regional model (e.g. WRF) driven one-way by MEGAM global output, (C) other. Decision note owed to Sridhar; benchmark cost before choosing.
20:55 IST Sridhar: fix the TN rain problem (P4) on 75 levels + 80 km itself (working config for this: T170 tp75). Regional model decision: leaning option A (own JAX regional; 9 km by ~1 Jan, 3 km ~May 2027) - not final; he is exploring GPU purchase (IndiaAI portal needs an eligible category - advised honest route: rent directly for benchmarks, Udyam MSME later).
P4 diagnosis launched: tn_rain_diag.py on 6 starts (SWM 20 May, 9 Jun, 19 Jul, 8 Aug; NEM 27 Oct, 6 Dec): tn-tnr-ctl (8, 32L) and tn-tnr-tp75 (9, 75L) -> tnr_<name>.json: 3-hourly conv vs grid-scale rain, deep share, RH 925-500, u/v850 over TN land / Ghats / TN coastal sea / Bay offshore; daily TN-box rain vs truth; day-5 TN T/q bias. Look for: extra rain convective or grid-scale? land or sea? day-time? too-moist low levels? wrong 850 hPa wind (easterly instead of westerly in SWM)?
21:25 IST Sridhar DECISION: no GPU purchase now; continue on Kaggle. Code the regional model (option A, our own) in parallel when time allows; basic testing on 10 more free Kaggle accounts he will add (accounts 11-20; workflow now reads KAGGLE11..20_USERNAME / _API_TOKEN secrets - he adds them in GitHub settings, never in chat). Regional plan: spec doc docs/regional_spec.md (draft for his approval) -> small-domain prototype + textbook tests on accts 11-20 -> 9 km NIO. Stage 1 (10 Nov) keeps priority.
22:45 IST Sridhar DECISION: Stage 3 = OPTION A (our own regional model, no WRF in production). Timeline given: spec ~8 Nov (for approval) -> 9 km prototype Nov -> 9 km NIO+India Dec -> 9 km into validation 1 Jan (fallback mid-Jan) -> 3 km non-hydrostatic + microphysics Jan-Apr 2027 -> freeze ~end May before SWM -> full 2027 validation; commercial decision Jan-Mar 2028. Operations target: whole cycle in 1-1.5 h -> needs paid GPUs in 2027 (2-3 L40S in parallel; 3 km may need H100 or smaller/shorter domain). Build/test on free Kaggle (accts 11-20 for regional work). WRF only as an optional benchmark.
23:35 IST Sridhar: Stage 1 MUST complete by 10 Nov (no slip). Day plan: 30 Oct P4 cause (ctl vs tp75 tnr) + fix design, GWD coding, T213 storm test, BL-only shallow design | 31 Oct-1 Nov P4 fix + BL shallow + GWD tests (short prof/tnr) | 2-3 Nov RC1 on 75L: full exam (4 quarters) + genesis + Bay/AS/SI | 4-5 Nov ozone, genesis-with-75L fix, TN storm benchmarks, false alarms | 6-7 Nov RC2, landfall decay, rain vs TN SMART | 8 Nov freeze + final held-back scoring | 9 Nov report + register | 10 Nov Stage 1 v1.0 for the dry run. Done = each item fixed with evidence, OR root cause proven and limit documented with its Stage 3 fix (e.g. storm intensity at 80 km). Fallback: 32L if 75L fails the gates. Preliminary P4 (75L, 6 starts): TN land/Ghats excess is GRID-SCALE rain (Ghats ~30 mm/d, TN land SWM 6-21 mm/d; convective 0.5-2) -> large-scale condensation over the Ghats at 80 km.
23:40 IST Sridhar: rain must be right across ALL India, not only TN. Exam now scores rain24 for india_nw / india_central / india_ne / india_south / west_coast / tamil_nadu / india (wxscore REGIONS; score_wx prints ours-only rmse/bias/acc - archived HRES has no such regions). ADOPTION GATE for any rain/convection change: no Indian region worse (rmse and acc at d1/d3/d5), plus TN. Old runs lack the new regions -> control must be re-run alongside each candidate (same quarter). Gauge check later: IMD gridded rain by region.

## 30 Oct 00:15 IST - live test: South Andaman low (IMD: low 29 Oct, depression ~31 Oct over SE Bay, WNW towards Andhra Pradesh coast)
12Z analysis: detect() finds the Bay system at 8.5N 97.5E (vo850 6.2, depth 1.3 hPa -> not yet 'formed'; no inserted vortex). Fixed: live2 no longer inserts a vitals storm that is over land (vitals_2026102912 held only the Arnab remnant inland 20.1N 82.1E). Sridhar: live ensemble at 80 km (not T85) from the LATEST run (12Z/18Z) and SEND THE GRAPH when done (held to 07:00 IST by the quiet hours).
Running: tn-live80-a/b/c (accts 1, 9, 10; live2.py T170 32L, config live_config_t170.json, parts 0-5/6-11/12-16 of 17) for 2026102912; T85 GitHub run (MMLIVE 2026102912) for comparison. Scheduled: 18Z fetch + 80 km ensemble at 22:45Z (silent); plots + send at 01:15Z (sent after 01:30Z = 07:00 IST).
00:40 IST: P3 approach per Sridhar/peer review: stop broad parameter tests; code-level audit + instrument one failing storm, fix a demonstrated defect, then regression. Surface-flux audit done (no defect, see rootcause.md). Next cycle: write storm_budget.py (storm-following 3-hourly budget) and run on 2-3 storms, control vs sh_dtop 0.6. Privacy: code stays out of Gemini/ChatGPT.

## 30 Oct 02:00 IST silent cycle (user awake; replied to his questions)
- sh_cap quick storm test (tn-quick-cap-c, acct 1; a/b on accts 2/5 were queued behind still-running Kaggle kernels - my mistake): REFUTED as intensity fix (rootcause.md). Keep sh_cap option off.
- GWD (Lott-Miller blocking + wave drag) coded in mm2 (gwd_tend, load_gwd), default OFF; switch gwd=1 (gwd_blk), needs geo_gwd.npz in FILES (release era5-cases). Offline numpy check: blocking strongly decelerates low levels in mountains, wave stress ~0.4 N/m2 for mu 400 m, U 10 m/s; deposits 3-7 m/s/day aloft in uniform wind. NEXT: short prof test with gwd on (T170 32L, 10 starts) + exam quarter: z500 extratropics/globe, u850 India, India rain regions.
- Live ensemble 2026102912: tn-live80-a/b done, c running; T85 GitHub run done. Plot + send at 07:00 IST (scheduled).
- tn-ua-ctl/shd06 COLLECT launched (accts 2, 5). tn-tnr-ctl (acct 8) still running.
04:30 IST: account 8 ALSO out of weekly GPU quota (tn-tnr-ctl never ran - push refused; tn-live80-18c refused too). Out: 3, 4, 6, 8. 18Z 80 km ensemble: tn-live80-18a (1), 18b (9), 18c2 (1, second session - may queue). tn-tnr-ctl must be re-run on an account with quota (P4 32L comparison).

## 30 Oct 07:00 IST - South Andaman low ensemble result (graph docs/figs/megam_andaman_low_ensemble.png; scripts live_ens_summary.py / live_ens_plot.py)
80 km 12Z (36 of 51 members - part c refused: account 10 also out of weekly quota), 80 km 18Z (51), 140 km 12Z (51). NO depression formed in MEGAM: median central pressure 1008-1013 hPa all week (IMD expects a depression ~31 Oct) -> genesis not captured (same weak-storm family as P3). Tracks: means move W/WNW across the south Bay to ~11-13N 80-82E by 2-3 Nov; strike-probability maxima offshore north TN (~11N 82E) and south AP (~13.5N 82.5E). Landfall shares 12Z/18Z: north TN 14/6 %, south TN 22/16, south AP 19/6, north AP/Odisha 3/27 (18Z - likely the separate northern circulation), Sri Lanka 3/14, at sea 39/31. 12Z vs 18Z inconsistent; 140 km keeps more at sea (53%). Low confidence.
Out of weekly GPU quota now: accounts 3, 4, 6, 8, 10.

## 30 Oct 08:00 IST cycle
CORRECTION: accounts 2 and 5 were refused for weekly GPU quota (not 'queued behind running kernels' as I told Sridhar at 01:35) - tn-ua-ctl, tn-ua-shd06, tn-quick-cap-a/b never ran. Out of quota now: 2, 3, 4, 5, 6, 8, 10 (7 = LETKF). Usable: 1, 9 only, until the weekly reset (or until KAGGLE11-20 secrets are added). Workflow now stops at once when a push is refused (no more 6-h polling).
Running: tn-quick-t213 (1: T213 ~63 km, 6 quick storms 72 h vs control -> resolution limit?), tn-gwd-prof (9: wx_prof 10 starts _ua, ctl vs gwd=1 as two processes).
Written: storm_budget.py (storm-following 3-hourly budget: pmin, v850, surface enthalpy flux core/300 km, warm core 300/500 hPa core minus 300-600 km ring, heating by process core/annulus, deep share, rain, RH700) + configs storm_budget_ctl.json (Nivar/Titli/Sidr) and storm_budget_nobogus.json (Nivar without inserted vortex). Launch when an account frees (or on GitHub CPU).
P4: tnr-ctl (32L) never ran (acct 8 quota) -> 75L-only finding stands (excess = grid-scale rain over Ghats/TN land); 32L comparison pending.
08:45 IST Sridhar: use account 7 (was reserved for LETKF/Stage 2-3 data assimilation) now. Launched tn-tnr-ctl2 (7): P4 32L rain diagnosis (comparison for tn-tnr-tp75).
10:15 IST Sridhar: until the 9 km NIO window exists, EXTRAPOLATE / calibrate storm intensity from the 80 km output. Plan: statistical-dynamical intensity layer (SHIPS-like), trained on our 80 km hindcasts (Bay 83, AS 105, SI cases; 2000-2017 train, 2018-2025 held-back test): predictors by lead time = model vmax / pmin deficit / 24 h model change, observed intensity at start (persistence), latitude, SST at the storm, distance to land; v1 adds MEGAM-forecast environment along the track (200-850 hPa shear, mid-level RH, SST/ocean heat) - needs hind2 to save it. Output labelled 'calibrated intensity'; physics fixes continue separately (calibration must not hide code bugs). CPU only.
Proposed Stage 1 exit gate (sent to Sridhar 10:10, awaiting OK): 250 hPa tropics d5 <= -3 K; storms strengthen 24->72 h in >=4/6 test storms; no Indian rain region worse + TN wet bias reduced; tracks/z500/steering no worse; drag+ozone in and tested; no blow-ups. Fix window 31 Oct-3 Nov, regression 4-7 Nov, freeze 8 Nov, v1.0 10 Nov; unfixed items documented with the stage that fixes them.
10:40 IST Sridhar: no 'known limitations' - foresee and fix; FMEA of the code. Done: Docs artifact 'MEGAM Stage 1 - Code FMEA' (https://claude.ai/artifact/EXkxxXMW5WEDicoPST5QFf): 30 failure modes, S/O/D/RPN, chain B-L1 (PBL velocity scale ~12x too weak on w*^3, default pbl_tm 0) -> B-C2 (shallow mixing over-strong compensates) -> B-C1 (two-parcel gap) -> B-G1 (100% condensation, instant rain-out) -> P1/P2/P4; B-R1 (radiation clouds from RH 0.70, OLR 202-215); storms: A-B4 (inserted core 0.9 qsat to 400 hPa -> convection off 6-12 h), B-M1 (CMT 6 h), A-A2 (quasi-monotone limiter also vertical). Action table with pre-registered predictions, dates to 10 Nov. KEY: fix B-L1 + B-C2 together (pbl_tm 1 + sh_mflux 0.03) - next test after tn-prof-shmf (alone expected to cool 850 hPa).
10:40 IST Sridhar: (1) B-L1 + B-C2 tested ONLY as the combined FMEA change (pbl_tm 1 + sh_mflux 0.03) - running as tn-prof-combo; baseline defaults untouched. (2) A-A2, A-B4, B-C1, B-G1/B-R1 stay in the queue whatever #1/#2 give - each keeps its FMEA action and date (A-A2, A-B4: 31 Oct; B-C1: 1 Nov; B-G1/B-R1: 2-3 Nov). Every cycle report lists the status of ALL FMEA actions. No accepted known limitations.
13:20 IST: account 9 now also out of weekly GPU quota. Usable: 1, 7 only. Noise-floor repeats: tn-sb-ctl-r2 (1), tn-sb-ctl-r3b (7).

## 30 Oct 14:00 IST cycle
- cmt_mf storm budget (tn-sb-cmtmf, deterministic): gate (a) PASS - Titli 993.3 / Nivar 996.3 hPa vs deepest control 998.8 / 1002.9 (beyond spread); v850 higher in 3/3. Sidr not deeper; its core collapse at 72 h is a tracker jump (~300 km) onto the Andamans, not physics.
- tn-quick6-cmtmf (account 7, started 08:04Z) running -> score gates (b) tracks <=10% worse than 202/252 km jump-cleaned, (c) mean 72 h wind > 29.7 kt. Track failure is not offset by intensity.
- KAGGLE11-20 secrets: not present yet. Usable: 1 and 7.
- Account 1 left idle on purpose: no derived-and-registered change is ready (cloud-top mixing, cloud consistency, single shallow/deep decision, vortex moisture all need derivation first). No exploratory runs.
- Derivation queue: B-L3 cloud-top mixing + F6 cloud consistency (P1 850 cold, P4) -> B-C1 single shallow/deep decision (P4) -> A-B4 vortex moisture (P3). P4 derivation must be done by 2 Nov to hold the 4-7 Nov regression.
- 14:30: cmt_mf REJECTED (tracks +15% at 48 h, +64% at 72 h; mean wind 27.2 vs target 29.7). Default stays off. Found: controls ran without the deterministic flag -> launched tn-quick6-ctl-d1 (acct 1) and -d2 (acct 7), identical deterministic controls. If d1 == d2 bit-for-bit, d1 becomes the control for all future quick tests.
- 15:30: D1 (tn-prof-d1) and D1+D2 (tn-prof-d12) scored: D1 850 -2.02 (pass) but cooling just moved down (low-level total unchanged); D2 rejected (850/q850/925). GPU-path check PASS. Key: low-level radiative cooling unchanged in every run -> missing heat is the shallow-cumulus heating with a FIXED mass flux (sh_mflux 0.03) -> derive cloud-base closure next. OLR/surface SW too low (anvil/convective cloud) -> D9. D3 orphans 25% of columns but only ~15% of grid-scale rain.
- 16:20: account 11 added by Sridhar and verified (tiny GPU job tn-acc11-check: 2x T4, completed). Usable now: 1, 7, 11.
- 16:30: account 12 verified (tn-acc12-check). Usable: 1, 7, 11, 12.
