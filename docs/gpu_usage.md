# Kaggle GPU account usage (weekly quota 30 h per account; all accounts assumed reset 2 Nov)
Updated each cycle. Times IST.

## 3 Nov 21:15 (track error + common-cause test)
| Acct | Job | Purpose | State |
|---|---|---|---|
| 1 | tn-shmf-tnr | P4: shallow mass-flux plume, TN rain | running |
| 2 | tn-shmf-evo | P1: same, budget evolution | running |
| 3-4 | tn-shmf-wx-q0/q1 | track/steering: Oct-Dec u850 bias; exam | running |
| 5 | tn-shmf-gen0 | genesis gate | running |
| 6 | tn-shmf-sb | P3: does an inserted storm survive (Nivar/Michaung/Vardah) | running |
| 7 | tn-tr75-0609b | P2: 9 Jun start to 240 h, hot-spot location | running |
| 8-14 | - | free | free |

## 3 Nov 13:15 cycle
| Acct | Job | Purpose | Started | State |
|---|---|---|---|---|
| 1 | tn-sb-p3a | P3: control storm budget Nivar/Michaung/Vardah (vs ERA5 offline) | 3 Nov 13:10 | running |
| 2 | tn-tp75f2-wx-q0 | P2: 75L F2 exam q0 | 3 Nov 12:26 | running |
| 3 | tn-tp75f2-tnr | P2a: 75L F2 TN rain | 3 Nov 12:27 | running |
| 4 | tn-scm-ref | P1 tool: SCM run (MPI-as-root fix) | 3 Nov 13:09 | running |
| 5-7 | tn-evi/lwc/ckz-wx-q0 | Decomposition: exam q0 | 3 Nov 12:29 | running |
| 8 | tn-sb-p3b | P3: control storm budget Fengal/Ockhi/Ditwah | 3 Nov 13:11 | running |
| 9-10 | tn-p4dry-a/b | P4: control TN rain on 12 Apr-Jun starts (dry-regime dataset) | 3 Nov 13:12 | running |
| 11-13 | tn-evi/lwc/ckz-gen0 | Decomposition: genesis | 3 Nov 12:34 | running |
| 14 | tn-evo-f2q | P1/P4: F2 moisture by process + cloud fraction | 3 Nov 12:45 | running |

## 3 Nov 12:30 cycle (previous cycle's jobs all finished; scored in rootcause.md)
| Acct | Job | Purpose | Started | State |
|---|---|---|---|---|
| 1 | tn-tr75-f2fix2 | P2: fixed F2 at 75L, full per-step JSON (q gate steps 1-9) | 3 Nov 12:25 | running |
| 2 | tn-tp75f2-wx-q0 | P2: 75L F2 exam quarter 0 (no blow-up in any start) | 3 Nov 12:26 | running |
| 3 | tn-tp75f2-tnr | P2a: 75L F2 TN rain (registered gate) | 3 Nov 12:27 | running |
| 4 | tn-scm-ref | P1: GFS v16 single column (builds now; 'time' shim for the run) | 3 Nov 12:28 | running |
| 5-7 | tn-evi/lwc/ckz-wx-q0 | Decomposition: each correctness item alone, exam q0 | 3 Nov 12:29 | running |
| 8-10 | tn-evi/lwc/ckz-tnr | Decomposition: each item alone, TN rain | 3 Nov 12:32 | running |
| 11-13 | tn-evi/lwc/ckz-gen0 | Decomposition: each item alone, genesis | 3 Nov 12:34 | running |
| 14 | tn-evo-f2q | P1: F2 budget with moisture-by-process + cloud fraction (850-925 hPa source) | 3 Nov 12:45 | running |

## 3 Nov 07:00 cycle (all finished)
| Acct | Job | Outcome |
|---|---|---|
| 1 | tn-tr75-f2fix | 75L F2 fixed: no blow-up in 24 h |
| 2 | tn-evo-f2fix | 32L F2 unchanged by the fix |
| 3 | tn-tr75-shm | sh_mflux alone stable at 75L |
| 4 | tn-scm-ref | built; run failed on missing 'time' |
| 5-10, 14 | tn-corr-* | correctness items together fail regression |
| 11-12 | tn-tnr-f2d / f2corrd | TN rain 1.85 / 1.98 |
| 13 | tn-evo-corr | BL evaporation doubles in the control regime |

## 2 Nov 23:35 cycle (all finished by 3 Nov 01:30)
| Acct | Job | Outcome |
|---|---|---|
| 1-3 | tn-tr75-f2/pbl/shm | void (trace script defect, fixed) |
| 4 | tn-scm-ref | build failed: NCEP libraries missing (fixed) |
| 5-8 | tn-base-wx-q0..q3 | baseline: z500 RMSE d1/d5/d10 20.2/73.3/120.2 m (73 starts) |
| 9-10 | tn-base-gen0/1 | baseline: genesis 31 % / 45 % |
| 11-13 | tn-evo-ctl/f2/tp75 | budget evolution (6/6/5 of 10 starts; OOM-killed after) |
| 14 | tn-base-tnr | baseline: TN box rain +43 % |
