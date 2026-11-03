# Kaggle GPU account usage (weekly quota 30 h per account; all accounts assumed reset 2 Nov)
Updated each cycle. Times IST.

## 3 Nov 07:00 cycle
| Acct | Job | Purpose | Started | State |
|---|---|---|---|---|
| 1 | tn-tr75-f2 (rerun, 72 steps) | P2: 75L + F2 crash trace (first run void: script defect) | 3 Nov 07:20 | running |
| 2 | tn-tr75-pbl (rerun) | P2: 75L + pbl_tm only | 3 Nov 07:21 | running |
| 3 | tn-tr75-shm (rerun) | P2: 75L + sh_mflux only | 3 Nov 07:22 | running |
| 4 | tn-scm-ref (rerun) | P1: NOAA CCPP SCM GFS v16 build (now builds bacio/sp/w3emc) + BOMEX/TWP-ICE | 3 Nov 07:40 | running |
| 5-8 | tn-corr-wx-q0..q3 | Regression: correctness items (evap_ifs, lw_cnt, ck_z) on the 2020 exam | 3 Nov 08:35 | running |
| 9-10 | tn-corr-gen0/1 | Regression: correctness items, genesis (with the static-setting fix) | 3 Nov 08:40 | running |
| 11 | tn-tnr-f2d | P4: deterministic F2 TN-rain reference | 3 Nov 08:42 | running |
| 12 | tn-tnr-f2corrd | P4: deterministic F2 + correctness items TN rain | 3 Nov 08:43 | running |
| 13 | tn-evo-corr | P1: budget time-evolution, control + correctness items | 3 Nov 08:44 | running |
| 14 | tn-corr-tnr | Regression: correctness items, TN rain | 3 Nov 08:45 | running |

## 2 Nov 23:35 cycle (all finished by 3 Nov 01:30)
| Acct | Job | Outcome |
|---|---|---|
| 1-3 | tn-tr75-f2/pbl/shm | void (trace script defect, fixed) |
| 4 | tn-scm-ref | build failed: NCEP libraries missing (fixed) |
| 5-8 | tn-base-wx-q0..q3 | baseline: z500 RMSE d1/d5/d10 20.2/73.3/120.2 m (73 starts) |
| 9-10 | tn-base-gen0/1 | baseline: genesis 31 % / 45 % |
| 11-13 | tn-evo-ctl/f2/tp75 | budget evolution (6/6/5 of 10 starts; OOM-killed after) |
| 14 | tn-base-tnr | baseline: TN box rain +43 % |
