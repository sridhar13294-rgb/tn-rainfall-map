# Our own data assimilation: LETKF groundwork (23 Oct 2026)

## What this is, in plain words
Today our forecasts start from the average of other centres' analyses, corrected a little by observations
(`docs/obs_assimilation.md`, optimal interpolation). The next step is to make our own analysis: every 6 hours, take our
own 6-hour forecast from an ensemble of 20-50 members, compare it with the observations, and pull every member toward
them. The method is the **LETKF** (Local Ensemble Transform Kalman Filter, Hunt et al. 2007), used operationally by
JMA, DWD (with 4D-Var/EnVar) and in many research systems.

Why an ensemble: the members' differences tell us, for today's weather, how an error at one place and variable is
connected to errors elsewhere (a pressure error near a cyclone comes with a wind error around it). The OI we have now
uses fixed, textbook connections; the LETKF uses today's.

How it works:
1. **Each member makes a 6-hour forecast.**
2. **Observation operator H(x)**: for every observation we compute what each member "would have observed"
   (station pressure at the station's height, 2-m temperature, 10-m wind, radiosonde values at their pressure levels,
   scatterometer winds over sea).
3. **Quality control**: observations that disagree with the ensemble mean by more than 5 times their combined error
   are thrown out (and the other wind component of a rejected wind with them); stations whose height differs too much
   from the model terrain are not used for pressure/temperature.
4. **Local analysis**: every grid column (32 768 at T85), at 10 heights, solves a small problem in "member space"
   (20 x 20 for 20 members) using only observations within ~1400-1800 km horizontally and ~0.6 in ln(pressure)
   vertically, weighted down smoothly with distance (Gaspari-Cohn). The answer is a recipe: "analysis member k =
   mean + this mix of the background members". Heights between the 10 analysis heights get blended recipes.
5. **Inflation**: a small ensemble always underestimates its own error. After the analysis the spread is pushed back
   halfway back toward the forecast spread (RTPS 0.5); an adaptive global factor is also available.
6. The increments go back into each member's model state (temperature and log surface pressure through the spectral
   transform, wind increments as vorticity/divergence increments, humidity directly, never negative).

## Files (all new, under `scripts/da/`)
| File | What |
|---|---|
| `letkf.py` | LETKF core: Gaspari-Cohn, local observation search (KD-tree on the sphere), batched K x K solve (numpy or jax, jitted in chunks), RTPS, adaptive inflation, vertical weight blending |
| `obsop.py` | observation operators, errors (nudge.py's tables, one source for OI and LETKF), QC, preparation of real `obs_<run>.npz` records |
| `analysis.py` | one analysis of mm2's nodal fields (T, q, u, v on 32 sigma levels, ps) for K members |
| `network.py`, `stations_obs2026102212.json` | OSSE observing network: real Indian SYNOP (306), METAR (465, 30-120E) and radiosonde (16) positions + a plausible global network |
| `mmstate.py` | model state <-> nodal fields, increments into the state, verification fields (needs jax + dinosaur) |
| `osse.py` | the OSSE driver (Kaggle GPU) |
| `test_letkf.py`, `test_obsop.py`, `test_analysis.py` | CPU tests (numpy) |
| `HOOKS.md` | patches proposed for live2.py / mm2.py / obs_fetch.py / a workflow (not applied) |

## Tests (CPU, numpy)
- `test_letkf.py`: with every observation at full weight, the LETKF gives exactly the Kalman-filter mean and covariance
  of the ensemble's sample covariance (difference < 1e-5). Lorenz-96 (40 variables, F = 8, 20 members, sigma_o = 1):
  analysis error **0.20** (published value for this set-up ~0.18-0.20; observation error 1.0; free run 4.9); every
  second variable observed: 0.35; adaptive inflation instead of RTPS: 0.25. A jax-equals-numpy check runs where jax is
  installed.
- `test_obsop.py`: interpolation exact for fields linear in lon/lat/ln p; station pressure at 300 m above the model
  terrain = the hypsometric value (~35 hPa less); 10-m wind factors 0.84 sea / 0.68 land; radiosonde levels below
  ground rejected; QC catches gross errors, wind partners, scatterometer over land, terrain height.
- `test_analysis.py`: whole analysis on a coarse synthetic globe (truth and members from the same random
  distribution, ~25 000 observations): surface pressure error 135 -> 82 Pa, temperature near radiosondes 1.53 -> 1.11 K,
  wind 2.6 -> 2.2 m/s, O-A < O-B for every observation type, never worse on the global mean. ~8 s on one CPU core.

## OSSE with the real model (T85, Kaggle T4)
Set-up (`osse.py`, Kaggle jobs `tn-da-osse1`, `tn-da-osse2`, account 7; results in `data/cyclone/kaggle/tn-da-osse*/`):
- **Nature run** ("the truth"): mm2 T85 from ERA5 14 Jul 2020 00Z, 10 days.
- **Observations** every 6 h from the nature run plus Gaussian noise of the size of the observation errors:
  2 374 surface stations (306 Indian SYNOP and 465 METAR at their real positions + a plausible global land network),
  338 radiosondes (16 real Indian + ~320 global; all at 00/12Z, 15 % at 06/18Z), 350 buoys/ships,
  ~3 000 scatterometer winds (ASCAT-like swaths). About 29 600 observations per cycle, ~98 % pass QC.
- **Ensemble** start: nature + 0.5 x (ERA5 on another date within +-60 days - ERA5 on the start date), digitally
  filtered. The ensemble mean starts 1.65 K (t850), 41 m (z500), 2.7 m/s (u850), 3.4 hPa (ps) off the truth - like a
  2-3 day old forecast. **Free run**: the ensemble-mean start, no observations.
- Identical twin: the same model makes the truth and the forecasts (no model error) - the easiest case; see open problems.

Global RMSE against the nature run, 20 members, RTPS 0.8 (first run):

| day | t850 analysis (K) | t850 free | z500 analysis (m) | z500 free | u850 analysis (m/s) | u850 free | ps analysis (Pa) | ps free |
|---|---|---|---|---|---|---|---|---|
| 0 | 1.65 | 1.65 | 41.2 | 41.2 | 2.73 | 2.73 | 339 | 339 |
| 0.25 (first analysis) | 1.28 | 1.68 | 24.5 | 40.8 | 1.57 | 2.88 | 92 | 332 |
| 1 | 1.03 | 1.98 | 17.2 | 42.7 | 1.56 | 3.62 | 79 | 359 |
| 2 | 0.80 | 2.33 | 11.5 | 44.0 | 1.61 | 4.53 | 68 | 412 |
| 4 | 0.70 | 2.87 | 8.0 | 48.6 | 1.48 | 5.30 | 59 | 480 |
| 6 | 0.57 | 3.06 | 7.3 | 63.4 | 1.46 | 6.39 | 52 | 645 |
| 10 | 0.50 | 3.29 | 6.0 | 76.3 | 1.42 | 8.01 | 50 | 822 |

So after 10 days the analysis error is 1/6 (t850) to 1/16 (ps) of the free run's, and still falling slowly. Regions
(days 5-10 mean, analysis / free): tropics t850 0.47 / 1.11 K, z500 4.3 / 11.4 m, u850 1.79 / 4.43 m/s; India t850
0.40 / 1.35 K, z500 3.2 / 17.3 m, u850 1.28 / 4.84 m/s, ps 31 / 169 Pa; southern hemisphere (few observations)
z500 8.1 / 97 m. The 6-h background is only slightly worse than the analysis (z500 7.2 vs 6.7 m), as it should be.
Tropical wind is the weakest field (u850 ~1.8 m/s): there the wind is not tied to the pressure field, and only
radiosondes, ships and scatterometers measure it.

Inflation and ensemble size (global, mean over days 4-6; analysis RMSE; background spread vs error in brackets):

| run | t850 K | z500 m | u850 m/s | ps Pa | z500 bg spread / error | India z500 m |
|---|---|---|---|---|---|---|
| 20 members, RTPS 0.8 | 0.63 | 7.9 | 1.51 | 59 | 13.3 / 8.6 | 3.3 |
| 20 members, RTPS 0.5 | 0.57 | 7.5 | 1.43 | 55 | 9.7 / 8.3 | 3.2 |
| 20 members, adaptive (rho -> 1.04) | 0.53 | 7.3 | 1.40 | 54 | 9.4 / 8.1 | 3.2 |
| 40 members, RTPS 0.5 | 0.52 | 6.7 | 1.33 | 51 | 10.9 / 7.5 | 3.1 |
| free run (same days) | 2.89 | 55 | 5.91 | 544 | | 15 |

RTPS 0.8 spreads the ensemble too much in this perfect-model case (spread 1.5x the error); 0.5 or the adaptive factor
is about right; 40 members cut the error another ~8-10 %. Default now RTPS 0.5; the real model will need more.

## Plan for real-data cycling
### Which observations (from `obs_fetch.py`, `obsop.prepare_real`)
| Type | Variables used | Notes |
|---|---|---|
| SYNOP land | station pressure (MSLP only when a report has none), 2-m q; 2-m T and 10-m wind **off** at first | land T2m and wind carry diurnal/terrain representativeness errors at 140 km; switch on after O-B statistics (they were on in the OSSE, where they cost nothing) |
| METAR | station pressure from QNH, 2-m q | ~5 800 reports per window over 30-120E; **superob** to 1-degree boxes with SYNOP (nudge.py's rule) before the LETKF, otherwise India gets hundreds of correlated reports |
| SHIP / BUOY | pressure, wind | |
| TEMP (radiosonde) | T, u, v at standard levels 1000-100 hPa, q up to 300 hPa | heights monitored only |
| ASCAT-B/C | 10-m u, v over sea | already 0.5-degree superobs; thin to 1 degree; passes over India fall in the 06Z/18Z windows |
| Consensus pseudo-observations | T, u, v at 850/500/250 hPa every 5 degrees, ps every 3 degrees | error = max(centre spread, the OI 'analysis' table); this is what keeps the cycle from drifting where we have no observations (oceans, southern hemisphere, upper air away from radiosondes) because we have **no satellite radiances or aircraft**. Down-weight later, region by region, as O-B shows our background is good enough |
Rain and lightning stay with latent-heat nudging in the forecast (nudge.py), not in the LETKF.

The current feed is regional (METAR 30-120E; SYNOP and TEMP effectively India only). A global cycle needs the global
GTS feed (HOOKS.md section 3); until then, cycle with the regional real observations plus global consensus
pseudo-observations, so outside the region our analysis simply follows the consensus.

### Ensemble size and settings
- **20 members** to start (OSSE: works, 1 min of GPU per cycle); 40 if the OSSE comparison below shows a clear gain.
- Localisation 700 km near the ground widening to 900 km at the top (Gaspari-Cohn half-widths; zero beyond twice that),
  0.6 in ln p vertically; at most 400 observations per local problem.
- Inflation: RTPS (0.5-0.8; tuned below) **plus** the model-error question: the OSSE is a perfect-model twin, the real
  model has a cold upper-troposphere drift of a few K in 5 days. Expect to need more inflation (RTPS ~0.8-0.9 or
  adaptive) and an additive part (e.g. random scaled 6-h tendencies of past cycles, or SPPT in the members as live2
  already does).
- Members' physics: as live2 (convection humidity/time scale, sea exchange, SPPT) so the ensemble also samples model error.

### Cost per 6-h cycle on a Kaggle T4 (measured in the OSSE, T85, 32 levels)
Measured per cycle (T85, 32 levels, ~29 600 observations):

| step | 20 members | 40 members |
|---|---|---|
| 6-h forecasts (Python loop of jitted `mm2.integrate`, ~1.0 s per member) | 20 s | 40 s |
| H(x) for all members (GPU) | 2.2 s | 2.4 s |
| local observation search (CPU, scipy KD-tree, 10 vertical groups x 32 768 columns) | 31 s | 31 s |
| LETKF solve (GPU, batched 20x20 / 40x40 eigen-decompositions, 327 680 local problems) | 1.2 s | 2.8 s |
| applying weights, RTPS | 1.0 s | 1.1 s |
| **total compute** | **~56 s** | **~78 s** |

(The OSSE also ran the nature and free runs: 22 s per cycle forecasts and 36 s analysis observed with 20 members.)
The neighbour search dominates and is easy to cut ~10x: the station positions are the same every cycle (cache), or one
horizontal query per column instead of one per vertical group. GPU memory: < 3 GB at 40 members.

Per real 6-h cycle as a separate Kaggle session: ~1.5 min setup (jax, Dinosaur, clone), downloads (previous members'
states ~0.2-0.4 GB + the analysis-time fields), ~1 min model compile, ~1-1.5 min compute -> **~5 min of T4 per cycle,
~20 min per day, ~2.5 GPU-hours per week** (of 30 per account). Running 4 cycles in one session (catch-up) cuts the
overhead to ~2 min per cycle.

### How it replaces / augments the consensus start
1. **Shadow cycling (2-4 weeks)**: cycle every 6 h from a consensus start, with real observations + consensus
   pseudo-observations; nothing in the live forecast changes. Log O-B / O-A per type (Desroziers check: E[d_o-a d_o-b]
   = R tells whether sigma_o is right; spread vs |O-B| tells whether inflation is right).
2. **Half the members**: live2 starts odd members from LETKF analysis members (HOOKS.md section 1), even members from
   the consensus as now; compare tracks and rain over a few systems.
3. **Switch**: the LETKF analysis ensemble becomes the start of all 51 members (the 20-40 analysis members reused with
   the physics variations), consensus kept only as pseudo-observations.
The OI (`nudge.py`) stays as the fallback when a cycle fails (no observations, a Kaggle session lost): restart from
consensus + OI, re-spin 1-2 days.

### How to verify against ERA5
ERA5 arrives ~5 days late (WeatherBench2 / ARCO, the `cyc_libm.py` path). For each analysis time: RMSE / ACC of
t850, z500, u850/v850, mslp of (a) our LETKF analysis mean, (b) the consensus start, (c) our 6-h background, against
ERA5, with `scripts/cyclone/mm/wxscore.py` (same regions: globe, tropics, India, Tamil Nadu). And forecasts: day 1-5
scores of live2 control from LETKF vs from consensus. Independent check: withhold 10 % of radiosondes each cycle and
score O-A on them (ERA5 has assimilated them, so ERA5 alone is not independent).

## Open problems (honest list)
- **Perfect-model twin.** The OSSE has no model error, so it is the best case. With the real mm2 (cold upper
  troposphere drift, convection still being repaired) inflation must be larger, an additive/model-error term is likely
  needed, and observation bias correction (station types, radiosonde humidity) will matter.
- **No satellite radiances or aircraft.** The OSSE gave the filter a global conventional network that does not exist in
  our real feed. Real cycling needs the global GTS feed (HOOKS.md section 3) and consensus pseudo-observations over
  data voids, or it will drift away from reality over the oceans and the southern hemisphere.
- **Balance after the analysis.** Increments go in without a digital filter (`dfi_after` option exists, untested); the
  OSSE stayed stable for 40 cycles, but surface-pressure noise in the first forecast hours was not measured.
- **Representativeness.** Land 2-m temperature and 10-m wind were used in the OSSE at face value; in reality they are
  off by default (as in the OI) until O-B statistics say otherwise. METAR density over India needs superobbing.
- **Neighbour search on the CPU** is 31 of the ~36 s analysis; cache it (fixed stations) or do one query per column.
- **Members are run one after another** (no `vmap`, mm2's step reads `M._carry` as an attribute; HOOKS.md section 2).
- Humidity analysis is univariate-ish (q from the ensemble only, clipped at 0 and 0.04); supersaturation after the
  analysis is left to the model's condensation.

## Next steps
1. Cache the local-observation search; test `dfi_after` and an OSSE with model error (nature run with different
   convection settings than the members), which is the realistic test of inflation.
2. `scripts/da/cycle.py`: the OSSE loop with `obsop.prepare_real` + superobbing + consensus pseudo-observations,
   saving member states and carries between Kaggle sessions.
3. Shadow cycling for 2-4 weeks with O-B monitoring and ERA5 verification (above), then the live2 hook.
