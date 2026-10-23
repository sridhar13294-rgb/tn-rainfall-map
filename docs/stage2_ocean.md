# Stage 2: a moving ocean under the weather model

Plain-words summary of what was built for the ocean under the moist model (scripts/cyclone/mm/mm2.py), what the tests
show, and what to do next. Code: `scripts/ocean3d/`. Date: 23 October 2026.

## Where we started

The model already has a 1-D ocean column (24 levels, 0-300 m) under every sea grid point (`scripts/cyclone/mm/ocean.py`).
Each column heats and cools from the surface, is stirred by the wind, and grows a cold wake under a cyclone. But each
column only knows what is directly below it. Water never moves sideways, and cold water never rises from below because
of the wind's pattern. Those two things cause the big cold patches of the north Indian Ocean: the Somali and Oman
coasts in the south-west monsoon, the Sri Lanka dome, the south-west coast of India, and the equator under easterly winds.

## Step A: currents and upwelling for the existing columns (`currents.py`)

At every model step, a 3-D water velocity is built from three parts, and it carries the columns' temperature and salt:

1. **Wind-driven (Ekman) drift** in the top 40 m. Far from the equator it runs 90 degrees to the right of the wind in
   the northern hemisphere. Near the equator a friction term keeps it finite. The result: easterly winds push water
   away from the equator on both sides, and water rises on the equator.
2. **Return flow** below 40 m, with the same amount of water going the opposite way. No water piles up anywhere. Where
   the surface drift spreads apart (or leaves a coast), water rises from below at the speed set by the wind pattern,
   w = curl(tau/f)/rho. Where it converges, water sinks.
3. **Density-driven (geostrophic) current** from the columns' own temperature and salinity, which carries warm and cold
   water along fronts. It is optional.

The transport scheme is simple and robust (first-order upwind). It conserves heat and salt exactly, never makes new
extremes, and blocks flow at coasts and the sea floor. It is written for both numpy and JAX, like ocean.py.

Tests (`test_currents.py`, CPU, about 45 s; all pass):

| test | result |
|---|---|
| heat and salt conservation, 200 steps, random winds, coast, island, shelf | error 0 (round-off), no new extremes |
| upwelling speed vs the textbook curl(tau/f)/rho | matches (same discretisation) |
| coastal upwelling, 0.15 N/m2 along a Somali-like coast, 10 days, with column mixing | coast SST -2.5 K (w = +5.7 m/day), offshore -0.3 K; reversed wind: no cooling (w = -5.8 m/day); column alone: -0.3 K |
| equatorial easterlies 0.05 N/m2, 10 days | upwelling +2.4 m/day on the equator, SST -0.6 K there, 0.0 K at 8N |

## Step B: a 3-D ocean

### Option 1: Veros (full ocean model in JAX). Speed measured on a Kaggle T4

Job `tn-oc-veros1` (data/cyclone/kaggle/tn-oc-veros1/veros_bench.json; it ran on account 1 because slot 7 was not set
up yet). Veros's own global set-ups started from climatology:

| set-up | grid | precision | seconds per model day | first step (compile) | model days per hour |
|---|---|---|---|---|---|
| global 2 deg | 180x80x40, dt 30 min | float64 | 12.6 | 25 s | 285 |
| global 2 deg | 180x80x40 | float32 | 10.1 | 21 s | 356 |
| global 1 deg | 360x160x60, dt 15 min | float64 | 73 | 27 s | 49 |
| global 1 deg | 360x160x60 | float32 | 34 | 23 s | 106 |
| global 2 deg, CPU (2 cores) | 180x80x40 | float64 | 63 | | 57 |

All runs stayed finite (SST -2.5 to 30.4 C, currents up to 1.2 m/s). Set-up takes 20-30 s.

For comparison, the atmosphere takes 3.4 s per model day at T85 and 24 s at T170 on the same T4 (tn-mm2-bench). The
current physics is heavier than that benchmark.

**Verdict: Veros is fast enough.** A 10-day forecast needs about 2 minutes of ocean at 2 degrees, or about 6 minutes
at 1 degree in float32. The real obstacles are elsewhere:
- **Spin-up.** Veros starts at rest from a yearly-average climatology. Its currents need months to years to settle,
  which costs about 1 hour per model year at 2 degrees and 3.4 hours at 1 degree. This is a one-off run whose result
  is stored as a restart file, but it is still needed.
- **It does not fit inside the jitted run.** Veros runs its own Python time loop, so the atmosphere's scan would have
  to be cut into 1-3 hour pieces with a hand-over in between. Ensembles would need one ocean per member, or one shared
  ocean.
- **Initial state.** Veros cannot easily start from today's ocean analysis (RTOFS/WOA). That needs nudging, which has
  not been written yet.
- **TPU.** A TPU has no float64. The float32 runs here were stable over 1-2 days. Longer runs are untested.

A wrapper with the coupling interface is in `veros_coupled.py`. It does the following:

- The atmosphere passes these fields every 1-3 h: wind stress taux and tauy (N/m2), non-solar heat into the sea
  (W/m2), net shortwave (W/m2), and evaporation minus precipitation (kg/m2/s).
- The ocean passes back SST (K) and the surface current (m/s).
- Fields are regridded both ways. Where Veros has no sea, the model's own columns are kept.

The wrapper's first real runs are the Kaggle jobs in test 3 below.

### Option 2: our own layered ocean in JAX (`rgo.py`), the recommended next step for the forecast model

This is a 1.5-layer reduced-gravity ocean on the model's own grid. It has one active warm upper layer, of thickness h
(roughly the depth of the 20 C water), above deep still water. It carries the wind-driven currents and the up-and-down
movement of the thermocline. Kelvin waves run along the equator and around the Bay of Bengal rim. Rossby waves carry
the thermocline westward. Everything runs inside the model's jitted step at almost no cost. The 24-level columns keep
doing the mixing. Their T and S are carried by the layer's currents plus the Ekman shear, and the levels near the
thermocline rise and sink with h. The layer starts from the depth of the 20 C isotherm in WOA23/RTOFS, with currents
in balance with it.

Tests (`test_rgo.py`, CPU, about 2 min; all pass):

| test | result |
|---|---|
| volume conservation, 500 steps | exact |
| equatorial Kelvin wave speed | 1.93 m/s vs theory 1.87 m/s |
| thermocline response to wind curl, first 3 days | 0.98 x the Ekman pumping, correlation 0.99 |
| coastal upwelling with the columns, 10 days | thermocline 21 m shallower at the coast; SST at the coast -0.5 K without the Ekman shear (default), -2.9 K with it; offshore -0.3 K |

## Ocean-only skill tests (against ERA5 SST)

The project's files have winds, SST and 925 hPa air, but no surface heat fluxes. So the CPU tests use simple bulk
formulas (`forcing.py`), the same for every run. The difference between runs is what the ocean dynamics adds. The
heat-flux part is crude, so absolute numbers carry its errors.

### 1. Summer-monsoon cooling, 15 May to 15 August (ERA5 1990-2019 daily climatology winds), `skill_monsoon.py`

Grid: 1.5 degrees, 0-39N 51-110E. Scored over 3-25N. Values are the SST change in K.

| run | pattern corr. | RMS (bias removed) | bias | Somalia | Oman | SW India | Sri Lanka dome | central Bay |
|---|---|---|---|---|---|---|---|---|
| ERA5 | 1 | 0 | 0 | -4.05 | -4.40 | -2.22 | -1.39 | -1.29 |
| columns only | 0.82 | 0.70 | -0.02 | -3.80 | -2.70 | -2.22 | -1.88 | -2.24 |
| + A (Ekman drift + return flow) | 0.59 | 1.60 | -1.20 | -8.02 | -5.83 | -3.05 | -3.93 | -3.06 |
| + A with geostrophic current | 0.81 | 1.02 | -0.93 | -7.09 | -5.74 | -2.75 | -3.68 | -2.49 |
| + reduced-gravity layer (B) with Ekman shear | 0.82 | 0.69 | -0.82 | **-3.91** | **-4.88** | -3.21 | -2.58 | -2.69 |
| + reduced-gravity layer, no Ekman shear (now the default) | **0.85** | **0.64** | -0.32 | -3.33 | -3.44 | -2.60 | -2.01 | -2.31 |

What this shows:
- **Step A on its own overdoes upwelling over three months.** Somalia and the Sri Lanka dome come out about twice too
  cold. A diagnostic drift with a fixed return flow keeps pumping cold water up for as long as the wind blows. The real
  ocean adjusts within weeks: waves carry the raised thermocline away, and the currents come into balance with it.
- **The layered ocean (B) fixes most of that.** It gets the Somali (-3.9 vs -4.05) and Oman (-4.9 vs -4.4) coastal
  cooling about right, where the columns alone miss Oman by 1.7 K. Without the Ekman shear it has the best overall
  pattern (0.85 vs 0.82).
- **Everything is too cold in the central Bay and the dome.** This is already true of the columns alone, so it mostly
  comes from the crude heat flux and the missing river freshwater, not from the currents.

### 2. Cold wakes of seven post-monsoon Bay of Bengal storms (ERA5 cases, 11 days, 0.5 degrees), `skill_wake.py`

Storms: Nivar 2020, Fengal 2024, Michaung 2023, Vardah 2016, Burevi 2020, Ockhi 2017, Ditwah 2025. Scored in the Bay,
5-23N 77-95E. Mean over the seven cases:

| run | pattern corr. | RMS (bias removed) | mean change where ERA5 cools > 1 K (ERA5: -1.30) | coolest 2 % (ERA5: -1.62) |
|---|---|---|---|---|
| columns only | 0.32 | 0.38 | -0.44 | -0.38 |
| + A (Ekman) | 0.32 | 0.43 | -0.63 | -0.52 |
| + A with geostrophic current | 0.34 | 0.41 | -0.62 | -0.49 |
| + A, columns' own slab current | 0.32 | 0.43 | -0.63 | -0.53 |
| + reduced-gravity layer (B) with Ekman shear | 0.33 | 0.46 | -0.67 | -0.56 |
| + reduced-gravity layer, no Ekman shear (default) | 0.32 | 0.41 | -0.51 | -0.45 |

What this shows:
- **Currents push the right way where ERA5 cools.** The cooling there grows from -0.44 K to -0.6/-0.7 K. But the wake
  is still only about half as cold as in ERA5, so the forcing is too weak. ERA5's 0.5-degree winds peak at only about
  17-24 m/s in these storms. The bulk heat flux is crude, and the columns start from monthly climatology rather than
  that day's ocean.
- **Pattern skill does not improve, and the RMS gets worse.** The cause is too much coastal upwelling right at the
  southern tip of Sri Lanka (Fengal, Ditwah: up to -4 to -5.6 K in one cell). ERA5 does cool the east and south coasts
  of Sri Lanka in Fengal (-1 to -2 K), and the currents put the cooling in the right place, but too strong and too
  concentrated. Extra sideways mixing (kh = 2000-3000 m2/s) helps only a little: the minimum goes from -4.1 to -3.6 K.
- The best single case is Fengal with A + geostrophic current: correlation 0.71 vs 0.58 for the columns alone.

### 3. Real ERA5 fluxes, summer monsoon 2019 (Kaggle, account 7: `tn-oc-era5mon`, `tn-oc-era5mon2`, `tn-oc-era5mon3`)

`era5_ocean_test.py`: 6-hourly ERA5 from the WeatherBench2 archive (10 m wind -> stress, plus ERA5's own latent,
sensible, net long-wave and net short-wave fluxes, rain and evaporation). Same grid and scores as test 1, 15 May to
15 August 2019, start from WOA23 shifted to the ERA5 SST. Heat flux into the model sea:
Q = Q_ERA5 + lam (SST_ERA5 - SST_model), with lam = 30 W/m2/K (the usual correction for ERA5's fluxes having been
computed over the observed SST). With lam = 30 the SST is pulled back toward the observed value with an e-folding time
of about 1.5 months in a 30 m mixed layer, so the lam = 0 lines are the stricter test.

| run | pattern corr. | RMS (bias removed) | bias | Somalia | Oman | SW India | Sri Lanka dome | central Bay |
|---|---|---|---|---|---|---|---|---|
| ERA5 2019 | 1 | 0 | 0 | -4.82 | -5.40 | -1.92 | -0.54 | -1.21 |
| columns only, lam 30 | **0.947** | 0.60 | +0.41 | -4.14 | -3.56 | -1.10 | -1.07 | -1.15 |
| layer with Ekman shear, lam 30 | 0.871 | 0.85 | -0.98 | -5.81 | -6.42 | -2.05 | -2.16 | -2.33 |
| layer, no shear, lam 30 | 0.930 | 0.59 | -0.21 | **-4.75** | **-4.87** | -1.44 | -1.14 | -1.31 |
| layer, no shear, kh 2000, lam 30 | 0.932 | **0.58** | -0.22 | -4.71 | -4.77 | -1.47 | -1.13 | -1.31 |
| Veros 2 deg (spun up by ERA5 from 15 Mar only), lam 30 | 0.871 | 0.84 | +0.43 | -4.28 | -4.48 | -0.94 | **-0.63** | -0.98 |
| columns only, lam 0 | 0.760 | 1.04 | +0.49 | -3.47 | -3.50 | -0.67 | -1.29 | -1.22 |
| layer, no shear, lam 0 | 0.716 | 1.19 | -0.45 | -3.99 | -4.86 | -1.26 | -1.18 | -1.51 |

What this shows:
- **With real fluxes, the columns alone already reproduce the large-scale pattern** (correlation 0.95). They miss the
  Oman upwelling by 1.8 K and leave the region 0.4 K too warm on average.
- **The layer without Ekman shear gets the coasts right.** Somalia is -4.75 vs -4.82, and Oman -4.9 vs -5.4, where the
  columns alone give -3.6. The overall RMS is the same or slightly better (0.58-0.59 vs 0.60), and the bias drops from
  +0.41 to -0.21 K. The pattern correlation is a little lower (0.93 vs 0.95). Small upwelling cells in the wrong place
  cost more in correlation than they gain.
- **The Ekman shear overdoes everything by about 1 K**, as in the climatology test. It is therefore now off by default
  (`rgo.PRM['shear'] = False`). The cost: in the 10-day coastal test the surface responds much more slowly without the
  shear (-0.5 K instead of -2.9 K at the coast), even though the thermocline rises just as much (21 m).
- **Without the flux correction (lam = 0)** both runs lose skill. The layer still improves Oman and Somalia but cools
  the Bay too much.
- **Veros at 2 degrees, forced the same way**, ran the 153 days (2 months spin-up plus 3 months scored) in 1387 s on
  a T4. That is 9 s per model day including the 6-hourly coupling hand-over. It gets the Sri Lanka dome right
  (-0.63 vs -0.54; every column-based run is about twice too cold there) and Oman better than the columns alone
  (-4.5). But its overall pattern is weaker (correlation 0.87, RMS 0.84). It started from a yearly-mean climatology at
  rest with only two months of spin-up, and its 10 m top level and 2-degree grid smooth the coastal upwelling. A
  properly spun-up Veros will do better. That is the next Veros experiment.

## Recommendation

1. **Couple step B (`ocean3d='rgo'`, Ekman shear off, see `scripts/ocean3d/MM2_HOOK.md`) into mm2.py first**, with
   currents.py doing the transport. It is cheap and runs inside jit. With real ERA5 fluxes it fixes the
   Somali/Oman coastal cooling at no loss in RMS. It also adds the Kelvin/Rossby thermocline dynamics that matter for
   the Bay of Bengal in the weeks before and after a storm. For cyclone cold wakes over 11 days it is neutral: it
   neither helps nor hurts.
2. **Treat step A on its own (`ocean3d='ekman'`) as a short-range option only** (a few days). Over weeks it overdoes
   upwelling.
3. **Keep Veros as the full 3-D path, for later.** Do a one-off 2-degree spin-up (2-5 model years, about 1 h each on a
   T4), then nudge to WOA/RTOFS at each start, then couple every 1-3 h through `veros_coupled.py`. It becomes worth it
   for runs of weeks to seasons, or when deep and remote ocean processes matter.

## Open problems

- **Coastal upwelling squeezed into one grid cell** (south of Sri Lanka): too cold. It needs a coastal band about one
  Rossby radius wide, or more sideways mixing near coasts.
- **Missing surface heat fluxes.** The ocean-only tests use crude bulk fluxes, so their absolute errors (central Bay
  too cold) are mostly forcing errors. The ERA5-flux run on Kaggle is the cleaner test.
- **No momentum advection** in the layered ocean, and no barotropic flow. There is no Indonesian throughflow and no
  river freshwater. The salinity barrier layer comes only from the WOA/RTOFS start profile.
- **Not yet run inside mm2.py or under JAX jit.** No JAX was available here. The code uses only operations that
  ocean.py already uses under jit, plus roll and stack.
- **Analysis currents (RTOFS u, v) are not fetched yet.** currents.py can take them (u_ext, v_ext). cyc_ocean.py would
  need the RTOFS 3zuio/3zvio files added, which is not done because that file belongs to the atmosphere side.
- **Veros:** the coupling wrapper works (Kaggle tn-oc-era5mon3, float32, 153 days stable). Still untested: a
  multi-year spin-up, nudging to RTOFS, ensembles, and TPU.
