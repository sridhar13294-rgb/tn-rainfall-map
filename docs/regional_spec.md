# MEGAM-R: regional model specification (Stage 3) - DRAFT for Sridhar's approval
5 Nov 2026 18:45 IST. Stage 3 started in parallel with Stage 1 (Sridhar 18:31). Option A recorded 29 Oct: our own regional
model (no WRF in production; WRF only as an optional benchmark). Stage 1 keeps priority for time and GPUs.

## 1. What it must do
- 9 km window over the North Indian Ocean + India, days 1-5, driven one-way by MEGAM global (80 km) at its boundaries.
- 3 km window over Tamil Nadu (+ adjacent sea), driven by the 9 km run, later (Jan-Apr 2027).
- Whole 80 + 9 + 3 km cycle in 1-1.5 h (needs paid GPUs in 2027; built and tested on free Kaggle now).

## 2. Why a new core is needed
MEGAM global is a hydrostatic, global spectral core (Dinosaur). It cannot run a limited area and is not valid at 3 km
(vertical accelerations matter in convection). One regional core is planned for both 9 and 3 km.

## 3. Proposed formulation (all from published, operationally used designs)
| Part | Choice | Reference | Why |
|---|---|---|---|
| Equations | Fully compressible, non-hydrostatic, flux form, dry-air mass coordinate | Skamarock & Klemp (2008) JCP; WRF-ARW tech note (Skamarock et al. 2019/2021) | One core for 9 and 3 km; best-documented open formulation; conserves mass |
| Vertical coordinate | Hybrid terrain-following -> pressure aloft (50-60 levels, top ~30 hPa) | Park et al. (2019) MWR (WRF hybrid); Simmons & Burridge (1981) | Avoids the sigma pressure-gradient error over the Himalaya (P5 lesson) |
| Horizontal grid | Arakawa C-grid on a Mercator projection | WRF-ARW | Domain is tropical (0-35 N): Mercator map factor small, simple |
| Time stepping | 3rd-order Runge-Kutta with split-explicit acoustic sub-steps | Wicker & Skamarock (2002) MWR | Standard, robust, GPU-friendly (no global solver) |
| Advection | 5th-order upwind horizontal, 3rd-order vertical; positive-definite / monotone moisture | Wicker & Skamarock (2002); Skamarock & Weisman (2009) | Same as WRF; no negative moisture |
| Lateral boundaries | One-way, Davies relaxation zone 8-10 points, hourly MEGAM (or ERA5 for tests) fields | Davies (1976) QJRMS | Standard for one-way nesting |
| Model top | Rayleigh damping of w in the top ~5 km | Klemp, Dudhia & Hassiotis (2008) MWR | Absorbs upward gravity waves |
| Terrain | ERA5/GMTED orography filtered to keep >= 6 grid lengths | GEM/IFS practice | Steep terrain is the main source of numerical noise |
| Physics at 9 km | MEGAM column physics (same code as global) + scale-aware deep convection (cloud-base mass flux reduced with resolution) | Arakawa & Wu (2013) JAS; IFS 9 km practice | Grey zone: 9 km does not resolve convection fully |
| Physics at 3 km | Deep scheme off, shallow on, prognostic microphysics (cloud water/ice/rain/snow/graupel, single-moment) | Hong & Lim (2006) WSM6 | Convection-permitting; needs the Stage 1 cloud-water work first |

## 4. Proposed domains (to confirm)
- 9 km: 40-100 E, 5 S-35 N (~730 x 490 points, 50 levels; Bay of Bengal, Arabian Sea, India, Sri Lanka).
- 3 km: 75-82 E, 7-15 N (~260 x 300 points; Tamil Nadu, Puducherry, adjacent sea).
Rough cost (to MEASURE before any commitment): 9 km, 5 days, dt ~45 s -> ~9,600 steps; first guess 20-60 min on one T4 and
~3 GB memory. Benchmark is step 2 below; numbers are not promised until measured.

## 5. Build and test order (each step passes its test before the next)
1. 2-D dry core (x-z): warm bubble (Bryan & Fritsch 2002 MWR) and density current (Straka et al. 1993 IJNMF) vs published
   reference solutions - local CPU.
2. 3-D dry core: resting atmosphere over Himalaya-like terrain must stay at rest (pressure-gradient error test);
   Schar et al. (2002) MWR mountain wave vs the analytic solution; GPU speed / memory benchmark at 9 km (Kaggle).
3. Lateral boundaries: a global field advected through the domain without reflection (boundary relaxation check).
4. Moist core + MEGAM physics: idealised tropical cyclone (Reed & Jablonowski 2011, DCMIP) at 9 km.
5. Real cases at 9 km driven by ERA5: Nivar, Michaung, Vardah, Fengal + Tamil Nadu rain events; scored vs IMD best
   track, ERA5 and GPM rain; then driven by MEGAM global.
6. 9 km into daily validation (target 1 Jan 2027, fallback mid-Jan). 3 km non-hydrostatic + microphysics Jan-Apr 2027,
   freeze ~end May before the SW monsoon, full 2027 validation (timeline as recorded 29 Oct).

Acceptance gates for step 5/6 are registered before the first real-case run (e.g. storm intensity closer to the best
track than the 80 km global; TN rain within the Stage-1 rain gate), never relaxed afterwards.

## 6. What Stage 3 needs from Stage 1
- Final column physics (shallow scheme, boundary layer, rain) - the 9 km window reuses it.
- Prognostic cloud water (Stage 1 cloud-water stage) - prerequisite for 3 km microphysics.
- Steps 1-3 above do NOT depend on Stage 1 and start now.

## 7. Decisions for Sridhar
1. Approve the formulation (non-hydrostatic from the start, one core for 9 and 3 km)?
2. Domains in section 4 - wider (e.g. include the South Indian Ocean to 20 S) or as proposed?
3. Accounts 15-18, when added, used mainly for Stage 3 tests?
