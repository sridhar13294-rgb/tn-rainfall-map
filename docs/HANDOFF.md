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
