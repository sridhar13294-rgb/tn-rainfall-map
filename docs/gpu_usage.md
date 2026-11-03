# Kaggle GPU account usage (weekly quota 30 h per account; all accounts assumed reset 2 Nov)
Updated each cycle. Times IST.

## 3 Nov 07:00 cycle
| Acct | Job | Purpose | Started | State |
|---|---|---|---|---|
| 1 | tn-tr75-f2fix | P2: 75L + F2 with the fixed counter-gradient flux (registered gates) | 3 Nov 07:25 | running |
| 2 | tn-evo-f2fix | P1: 32L F2 budget evolution with the fix (registered direction gates) | 3 Nov 07:26 | running |
| 3 | - | tn-tr75-shm done (stable 24 h); free for the 13:00 cycle | - | free |
| 4 | tn-scm-ref (rerun) | P1: NOAA CCPP SCM GFS v16 build (now builds bacio/sp/w3emc) + BOMEX/TWP-ICE | 3 Nov 07:12 | running |
| 5-8 | tn-corr-wx-q0..q3 | Regression: correctness items (evap_ifs, lw_cnt, ck_z) on the 2020 exam | 3 Nov 07:05 | running |
| 9-10 | tn-corr-gen0/1 (gen1 relaunched 07:27) | Regression: correctness items, genesis (with the static-setting fix) | 3 Nov 07:10 | running |
| 11 | tn-tnr-f2d | P4: deterministic F2 TN-rain reference | 3 Nov 07:28 | running |
| 12 | tn-tnr-f2corrd | P4: deterministic F2 + correctness items TN rain | 3 Nov 07:28 | running |
| 13 | tn-evo-corr | P1: budget time-evolution, control + correctness items | 3 Nov 07:28 | running |
| 14 | tn-corr-tnr | Regression: correctness items, TN rain | 3 Nov 07:28 | running |

## 2 Nov 23:35 cycle (all finished by 3 Nov 01:30)
| Acct | Job | Outcome |
|---|---|---|
| 1-3 | tn-tr75-f2/pbl/shm | void (trace script defect, fixed) |
| 4 | tn-scm-ref | build failed: NCEP libraries missing (fixed) |
| 5-8 | tn-base-wx-q0..q3 | baseline: z500 RMSE d1/d5/d10 20.2/73.3/120.2 m (73 starts) |
| 9-10 | tn-base-gen0/1 | baseline: genesis 31 % / 45 % |
| 11-13 | tn-evo-ctl/f2/tp75 | budget evolution (6/6/5 of 10 starts; OOM-killed after) |
| 14 | tn-base-tnr | baseline: TN box rain +43 % |
