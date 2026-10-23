# Handoff (read this first in a new chat) - 23 Oct 2026, 21:15 IST

## Who / rules
- Sridhar (phone only, plain words, honest pushback). Brother Adhitya co-runs the site. Model name: Sridhar proposed MEGAM; suggested "Multi-scale Ensemble Global Atmospheric Model" - waiting for his final wording, do not rename yet.
- Repo sridhar13294-rgb/tn-rainfall-map, work branch `cases`. `main` (the website) only with Sridhar's explicit "go live".
- Secrets only in GitHub secrets (ECMWF_DS_KEY/CDS_KEY, KAGGLE_*, KAGGLE2_..KAGGLE8_*). Never print/commit them. One Kaggle account per real person.
- Messages: NONE between 00:30 and 07:00 IST. Daytime: one short status every 3 h. Daily rain skill check at 10:30 IST (scratchpad/dailyNN scripts; see the skill-check routine text in the old chat / docs/cyclone_model_status.md).
- Convection: never fall back to the old scheme as the answer; keep repairing the mass-flux scheme (old BMJ = yardstick).
- Live doc: https://claude.ai/artifact/GttzHBxsJbyAh9HSW1NcFi (change-log table, newest rows on top). Update on decisions.
- Usage: Sridhar's weekly limit resets Mon 26 Oct 22:29 IST; 5-hour session limit applies. Keep each cycle lean (see "How to run cheaply").

## Schedules (set 23 Oct 21:15 IST)
- Scheduled tasks: 'MEGAM work cycle' (every 2 h) and 'Daily rain skill check' (10:30 IST). Each run starts a fresh session and clones `cases`.
- Last status sent: 23 Oct 21:15 IST
- 23 Oct 21:20 IST: no Kaggle results back yet (jobs launched ~21:07 IST); next cycle collects them.

## Goal
General daily global model like ECMWF/GFS (00/12Z, 10-day + 51-member 15-day), good in Bay of Bengal, Arabian Sea, South Indian Ocean. Stage 1 = 11 fixes (target ~28 Oct, fallback 30 Oct). Stage 2 = 3-D ocean (built). LETKF data assimilation (in progress). Stage 3 = India detail (9 km + 3 km windows).

## Kaggle (job launcher)
- Write data/cyclone/KAGGLE (line1 slug, line2 release files, line3 command run in repo/scripts/cyclone/mm, line4 accelerator NvidiaTeslaT4 or TpuV5E8, line5 account 1-8, line6 #comment) and push to `cases`; results return to data/cyclone/kaggle/<slug>/ (status.txt, *.json, kernel_*.log). Workflow refuses unconfigured slots.
- Accounts: Stage 1 uses 1-6 and 8; account 7 = helper agents (LETKF now). GPU ~30 h/week each.
- TPU: needs Kaggle IDENTITY verification. Only account 1 is verified (TPU quota 20 h/week). Pushed jobs on unverified accounts silently get a plain CPU. tn-tpu-wx (acct1) checks if TPU attaches.
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

## More context to read
- docs/cycle_notes_2026-10-23.json: every test result and decision from 22-23 Oct, in time order (the detailed log).
- docs/cyclone_model_status.md, docs/night_plan.md, docs/stage2_ocean.md, docs/letkf.md (when present), docs/obs_assimilation.md.
- Live doc (all parts, equations, change log): https://claude.ai/artifact/GttzHBxsJbyAh9HSW1NcFi
