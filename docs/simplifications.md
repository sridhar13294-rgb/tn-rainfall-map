# MEGAM simplifications register (vs ECMWF IFS) - 27 Oct 2026
Every place where our model is simpler than a professional global model, its likely effect, and the plan. Keep this updated; nothing ships to customers while an item marked HIGH is open without a written decision.

| # | Part | ECMWF IFS | MEGAM now | Likely effect | Priority | Plan / stage |
|---|------|-----------|-----------|---------------|----------|--------------|
| 1 | Vertical levels / model top | 137 levels to 0.01 hPa | 32 sigma levels, top ~20 hPa | coarse tropopause, stratosphere poorly resolved, cold UT / warm 100 hPa (physics-off run keeps +8 K at 100 hPa -> dynamics/resolution) | HIGH | 50-level test running (tn-prof-l50) |
| 2 | Stratosphere radiation | full radiation everywhere | not computed above sigma 0.12; relaxed to start T (15 d) + wind sponge sigma<0.05 | artificial lid at tropical tropopause | HIGH | rad_top test running (tn-prof-radtop) |
| 3 | Ozone | prognostic (linear chemistry + assimilation) | one fixed tropical profile for the whole globe | 100 hPa tropics ~2-3x too much; extratropics too little near tropopause | HIGH | ERA5 zonal monthly climatology |
| 4 | Stratospheric humidity | analysed + limb sounders | whatever the start gives, no check | possible excess LW cooling | MEDIUM | check ppmv at 50-150 hPa |
| 5 | Convection - cloud top | updraught kinetic energy (w=0) | first level of negative buoyancy | plumes stop at 0 C stable layer, heating too low, cold UT | HIGH | mf_wke test running |
| 6 | Convection - entrainment/detrainment | eps 1.75e-3 (1.3-RH) fscale^3; turbulent + organised detrainment | eps 1.5e-4 (1.3-RH), fixed mass-flux shape | heating profile shape | HIGH | ecent / wke_org tests running |
| 7 | Convection - freezing, downdraught 0.3, closure (CAPE + PBL), momentum transport | full | freezing off by default, downdraught 0.5, CAPE closure, momentum by simple mixing | heating / cold pools / storm structure | MEDIUM | wke_ice / wke_dd3 tests running; momentum later |
| 8 | Shallow convection | mass-flux plume, ECMWF closure | MSE mixing (mf plume tested: hurt TN rain) | spurious low-level heat loop | MEDIUM | revisit after cloud-top fix |
| 9 | Clouds / microphysics | prognostic cloud liquid, ice, rain, snow (+ cloud fraction) | saturation adjustment; diagnostic clouds for radiation; no prognostic ice | anvil/ice amount and radiation (tropical OLR ~205 vs ~250 W/m2) | HIGH | anvil/ice tests (tn-prof-rad); prognostic cloud water = Stage 3 |
| 10 | Rain evaporation | precipitation fraction, clear-sky RH | k (1-RH) sqrt(aP), a = 0.3 (fixed 27 Oct) | improved | DONE | - |
| 11 | Radiation scheme | ecRad (RRTMG-type, 16/14 bands, McICA clouds, aerosols) | our own few-band scheme, called every 2 steps | heating-rate accuracy, cloud overlap | HIGH | clear-sky check vs a reference (RRTM-like); ecRad port later |
| 12 | Aerosols | climatology (CAMS) | none | SW heating/dimming (India haze, dust) | MEDIUM | CAMS climatology later |
| 13 | Gravity-wave drag (orographic + non-orographic) | yes | NONE | upper-level winds / jets too strong over mountains, stratosphere | HIGH | add orographic GWD (Lott-Miller type) + simple non-orographic |
| 14 | Orographic blocking / turbulent form drag | yes | none (only z0_land 0.1 everywhere) | low-level winds over Ghats/Himalaya, monsoon flow | HIGH | add with item 13; z0 from land cover |
| 15 | Land surface | HTESSEL/ECLand: 4 soil layers, vegetation tiles, snow, lakes | soil temp + one bucket, analysed start | land heat/moisture fluxes, brown-ocean decay, monsoon onset | MEDIUM | multi-layer soil + vegetation (Stage 3) |
| 16 | Ocean | coupled NEMO 3-D, waves | column mixed layer (3-D test: no track change) | intensity, upwelling cold wake | MEDIUM | Stage 2 |
| 17 | Waves / sea-state roughness | coupled wave model | Charnock + cap | high-wind fluxes | LOW | later |
| 18 | Boundary layer | EDMF (eddy diffusivity + mass flux), TKE-like | K-profile, Richardson height | PBL depth, low clouds | MEDIUM | pbl_tm tested; EDMF later |
| 19 | Data assimilation | 4D-Var + EDA, ~60 M obs/day, weak constraint | starts from GFS/ECMWF analyses (consensus); OI trial neutral | start quality depends on others' analyses | HIGH (for independence) | keep using operational analyses for 2027; own DA = later project |
| 20 | Ensemble | 51 members, EDA + SVs + SPPT/SPP | 51 members: bred vectors + analysis differences + SPPT + physics factors | spread 0.7-0.9 of error | OK | tune with the final model |
| 21 | Dynamics | non-hydrostatic option, 9 km, cubic grid | hydrostatic spectral, T85 (~140 km) / T170 (~80 km) | storm cores, terrain rain | HIGH | T170 ADOPTED 27 Oct as main run (tracks better in all 3 basins); ensemble T85; 9 km India = Stage 3 |
| 22 | Tropical-cyclone start | analysis has the storm (assimilated) | inserted Holland vortex, fixed 180 km size | compact storms too broad | MEDIUM | size from best-track RMW/R34 |

Missing entirely today: gravity-wave drag, orographic blocking/form drag, aerosols, prognostic cloud water/ice, prognostic ozone, own data assimilation.
