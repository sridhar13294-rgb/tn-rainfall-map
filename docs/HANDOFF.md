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
