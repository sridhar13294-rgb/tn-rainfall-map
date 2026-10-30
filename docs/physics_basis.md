# MEGAM physics basis register (equation-driven, not parameter-driven)
Rule (Sridhar, 30 Oct): for every process - governing law -> derived equation -> assumptions -> units and signs -> conservation -> limiting cases -> literature -> status. A simplified rule is replaced only when the physics and the evidence justify it; every replacement is derived and checked offline before any GPU test (as done for mass-flux CMT, scratchpad deriv/cmt.py -> scripts/cyclone/mm/cmt_derivation.py).

| Process | Governing law / reference | Current implementation | Basis status | Action |
| --- | --- | --- | --- | --- |
| Dynamics | Hydrostatic primitive equations (Dinosaur, semi-Lagrangian semi-implicit) | library | derived (library) | A-A2 limiter: horizontal-only as IFS |
| Surface fluxes | Monin-Obukhov bulk formulas (Louis 1979 stability), Charnock | bulk formulas | VERIFIED (audit 30 Oct) | - |
| Boundary layer | K-profile (Troen & Mahrt 1986, Hong & Pan 1996) | old velocity scale (pbl_tm 0) | DEFECT: velocity scale ~2.3x too small (B-L1) | pbl_tm 1 (derived form exists) |
| Cloud-top mixing | Radiatively driven entrainment (Lock et al. 2000; IFS) | absent | MISSING (B-L3) | derive + implement |
| Shallow convection | Mass-flux (Siebesma et al. 2003; IFS) | MSE relaxation to column mean, tau 1 h | NOT physically based (B-C2): implied flux 10-40x observed | sh_mflux interim; mass-flux shallow plume as final |
| Shallow/deep decision | One plume, cloud depth (IFS) | two parcels | inconsistent (B-C1) | single plume decision |
| Deep convection | Entraining mass-flux plume, CAPE closure (Tiedtke 1989, Bechtold 2008) | conv_mf | VERIFIED by reading (flux form, condensation sink correct) | B-C3 source layer, B-C4 cap |
| Momentum transport | Mass-flux CMT (Gregory et al. 1997) | relaxation tau 6 h | NOT physically based (B-M1): offline derivation shows shear erased +50..+80 m/s/day | cmt_mf implemented + derived; testing |
| Grid-scale condensation | Saturation adjustment + sub-grid cloud fraction (Sundqvist 1989 / Tiedtke 1993) | 100% RH, instant rain-out | inconsistent with radiation clouds (B-G1) | consistent cloud fraction (F6) |
| Rain evaporation | Kessler-type, IFS form | tuned k_evap | basis unclear (B-G2) | derive dimensionally |
| Radiation | 2-stream LW/SW, diagnostic clouds | radcloud | heating conversion VERIFIED; cloud threshold inconsistent (B-R1) | F6 |
| Inserted vortex | Gradient-wind + hydrostatic balance (Holland 1980) | bogus() | balance VERIFIED; moisture profile assumed (A-B4) | use analysed / observed humidity |
| Ocean mixed layer | Slab + wind cooling | simple | simplified (Stage 2 replaces) | Stage 2 |
| Drag | Lott & Miller 1997 | gwd_tend (new) | derived, offline-checked | score winds |

## Constants and simplified numbers inventory (30 Oct 14:15) - which can be solved instead of fixed
A = physically derivable now (replace the constant with the equation); B = empirical, derive from observations/literature; C = fine as is.
| # | Where | Fixed now | Can be solved as | Class | Problems | Expected effect (derived where marked) |
| 1 | conv_mf plume + grid-scale condensation | ice phase OFF (mf_ice 0, bmj_ice 0); latent heat Lv only; saturation over water at all temperatures | condensate freezes between 0 and -20 C, latent heat L = Lv + f_ice Lf; saturation over ice below 0 C (mixed-phase qsat) | A | P1, P3 | DERIVED (ice_derivation.py, undilute tropical parcel): +1.4 K at 300 hPa, +1.5 K at 250, CAPE 1684 -> 2056 J/kg, top 170 -> 160 hPa. Earlier ice tests showed ~0 because deep convection fired in only 5% of columns - confounded; must be re-tested after F2 |
| 2 | PBL velocity scale | 0.6 x 0.1 x kappa, w* with fixed 1000 m | Troen-Mahrt: 7 x 0.1 x kappa, w* with h_bl | A | P1, P4 | in F2 (pbl_tm 1) |
| 3 | Shallow mixing | tau 1 h relaxation | mass flux from closure (Grant 2001: Mb = 0.03 w* rho) | A | P1, P2, P4 | interim sh_mflux; final = plume |
| 4 | CMT | tau 6 h | mass-flux form | A | P3 | DERIVED + implemented (cmt_mf) |
| 5 | Heights of layers | dz from T (dry) | from virtual temperature Tv = T (1 + 0.61 q) | A | small | ~1% in moist low levels |
| 6 | Heat capacity | cp of dry air | cp = cpd (1 - q) + cpv q | A | small | <1% |
| 7 | Gust in surface fluxes | constant 1 m/s | convective gustiness w_g = 1.2 w* (Beljaars 1995) | A | P4, rain | more evaporation in light-wind convective regimes |
| 8 | Ck at the lowest level | 10 m value x (log ratio)^0.5 (ck_z 0.5: half a correction) | full log-law transfer to z1 (ck_z 1) or roughness lengths z0q, z0t (COARE) | A | P3, steering | ck_z 1 tested before: shear better, upper air worse -> re-test after F2 |
| 9 | Rain evaporation | k (1-RH) sqrt(a P), k tuned | Kessler (1969)/IFS: E = 5.44e-4 (1-RH) (sqrt(p/ps) P / 5.9e-3)^0.577 | A | P1, P4 | changes low-level cooling profile (B-G2) |
| 10 | Free-atmosphere mixing length | 30 m | Blackadar l = kappa z / (1 + kappa z / 150 m) | A | small | - |
| 11 | Cloud fraction for condensation | 100% RH | Sundqvist cloud fraction, same RHc as radiation | A | P1, P2, P4 | F6 |
| 12 | Updraft mass-flux shape | 1 up to 60% of cloud depth, then linear | from entrainment/detrainment rates of the plume | A | P1 | heating height |
| 13 | Deep closure time | tau_deep 40 min fixed | convective turnover time (cloud depth / updraft speed) - option mf_wup exists | A | P1, P3 | - |
| 14 | Inserted vortex density | rho = 1.15 constant | rho = p / (Rd Tv) at the surface | A | small | pressure deficit +-3% |
| 15 | Inserted vortex moisture | 0.9 qsat to 400 hPa | analysed humidity | A | P3 | A-B4 |
| 16 | Ocean cooling | (V - 10)^2 / 225 empirical | mixed-layer entrainment from u*^3 (Niiler-Kraus) | B | P3 | Stage 2 ocean |
| 17 | Albedos | land 0.2, sea 0.07 constant | ERA5 land albedo; sea albedo from solar zenith angle (Taylor 1996) | A | P1, P4 (land heating) | - |
| 18 | Land heat capacity, bucket | 2e5 J/m2/K, 0.15 m | soil type from ERA5 | B | P4 | - |
| 19 | Radiation clouds | RHc 0.70 / 0.80, b_ls 1% | consistent with condensation (F6) | A | P1 | F6 |
| 20 | Constants g, Rd, Rv, cp, Lv, solar 1361, CO2 420 ppm, Earth rotation | standard values | - | C | - | fine (CO2 ~425 ppm in 2026, negligible) |
Order: 1 (ice) after F2; 9 and 7 with the rain work (P4); 5, 6, 10, 14 together as small consistency fixes; 17, 18 in Stage 2 land work.

## Evidence levels (from 30 Oct): every change carries one
L1 equation derived (offline, with expected numbers) -> L2 implementation verified (code reproduces the offline numbers; conservation and limiting cases checked) -> L3 forecast validated (pre-registered quick test passed + full regression passed). Nothing is called validated below L3.
Current: mass-flux CMT L2 (quick test running); ice phase L1 (must also add MELTING of falling ice/snow below the 0 C level (-Lf cooling) so energy is conserved; deposition/sublimation consistent with the mixed-phase qsat); F2 (pbl_tm + sh_mflux) L2, quick test failed 850 hPa; drag L2.
